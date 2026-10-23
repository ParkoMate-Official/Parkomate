"""StationController: the shell's view model.

Owns the page (starting / login / production / session end / admin), the mode inside the
production page (the line, or the Repair tab), the current stage, the error banner, inline
confirmations, the reject takeover, the success toast, counters, the session drawer data,
the four stage view models and the repair view model.

A **retest** (Repair tab -> "Test again") runs the repaired board through the whole line in
the normal stage screens; ``retest`` names the board, and when its run ends the station
returns to the Repair tab on that board.

Business rules stay in the WorkflowService; hardware runs in ``self.hw`` (one worker thread,
so calls never overlap); slow non-hardware work (password hashing, reports, e-mail) runs in
``self.bg``.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QApplication

from parkomate.app import AppContext
from parkomate.core.enums import (
    AmbientReason,
    DeviceStatus,
    OutboxStatus,
    PRODUCTION_STAGES,
    SessionEndReason,
    Stage,
)
from parkomate.core.errors import ErrorCode, ParkomateError
from parkomate.core.models import (
    Counters,
    Device,
    DeviceState,
    FirmwareInfo,
    Operator,
    RejectInstruction,
    Session,
    SessionSummary,
    WorkQueueItem,
)
from parkomate.i18n import get_language, set_language, t
from parkomate.mail.outbox import SendReport
from parkomate.station import LoginResult, LogoutResult, StartupResult
from parkomate.ui.viewmodels.base import ConfirmState, ErrorState, StageViewModel
from parkomate.ui.viewmodels.bridge import EventBridge
from parkomate.ui.workers.runner import TaskRunner

log = logging.getLogger(__name__)

OUTBOX_INTERVAL_MS = 5 * 60 * 1000


class Page(StrEnum):
    STARTING = "starting"
    LOGIN = "login"
    PRODUCTION = "production"
    SESSION_END = "session_end"
    ADMIN = "admin"


class Mode(StrEnum):
    """The production page shows the line (stages A-D) or the Repair tab."""

    PRODUCTION = "production"
    REPAIR = "repair"


@dataclass(frozen=True, slots=True)
class RetestTarget:
    """The repaired board that the line is testing again."""

    case_id: int
    mac_address: str
    board_id: str


class LoginPhase(StrEnum):
    FORM = "form"
    CHECKING = "checking"
    AMBIENT = "ambient"
    AMBIENT_DONE = "ambient_done"


class SendState(StrEnum):
    CLOSING = "closing"  # session being closed / report written
    SENDING = "sending"
    SENT = "sent"
    SAVED = "saved"  # queued, will retry
    DISABLED = "disabled"  # e-mail off: report on this PC only
    REPORT_ERROR = "report_error"


class StationController(QObject):
    page_changed = Signal()
    stage_changed = Signal()
    error_changed = Signal()
    confirm_changed = Signal()
    bottom_bar_changed = Signal()
    reject_shown = Signal(object)
    reject_cleared = Signal()
    toast = Signal(str)
    counters_changed = Signal()
    session_changed = Signal()
    device_changed = Signal()
    login_changed = Signal()
    session_end_changed = Signal()
    firmware_changed = Signal()
    ambient_changed = Signal()
    drawer_changed = Signal()
    mode_changed = Signal()
    retest_changed = Signal()
    queue_changed = Signal()
    tick = Signal()

    def __init__(
        self,
        ctx: AppContext,
        *,
        hw_runner: TaskRunner | None = None,
        bg_runner: TaskRunner | None = None,
        ambient_result_ms: int = 1200,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.ctx = ctx
        self.hw = hw_runner or TaskRunner(1, self)
        self.bg = bg_runner or TaskRunner(2, self)
        self.ambient_result_ms = ambient_result_ms
        self.bridge = EventBridge(ctx.bus, self)
        self.bridge.device_rejected.connect(self._on_rejected)
        self.bridge.device_completed.connect(self._on_completed)
        self.bridge.counters_changed.connect(lambda _sid: self.refresh_counters())

        self.page = Page.STARTING
        self.mode = Mode.PRODUCTION
        self.retest: RetestTarget | None = None
        self.stage = Stage.PROGRAMMING
        self.error: ErrorState | None = None
        self.confirm: ConfirmState | None = None
        self.reject: RejectInstruction | None = None
        self.operator: Operator | None = None
        self.session: Session | None = None
        self.counters: Counters | None = None
        self.ambient_c: float | None = None
        self.firmware: FirmwareInfo | None = None
        self.firmware_loading = False
        self.firmware_error: ParkomateError | None = None
        self.startup: StartupResult | None = None
        self.startup_error: ParkomateError | None = None
        self.login_phase = LoginPhase.FORM
        self.login_error: ParkomateError | None = None
        self.logout_result: LogoutResult | None = None
        self.send_state: SendState | None = None
        self.drawer_open = False
        self.session_devices: list[Device] = []
        self.queue_items: list[WorkQueueItem] = []
        self.queue_count: int = 0
        self._outbox_busy = False
        self._shut_down = False

        from parkomate.ui.viewmodels.labeling import LabelingViewModel, PackagingViewModel
        from parkomate.ui.viewmodels.programming import ProgrammingViewModel
        from parkomate.ui.viewmodels.repair import RepairViewModel
        from parkomate.ui.viewmodels.testing import TestingViewModel

        self.programming = ProgrammingViewModel(self)
        self.testing = TestingViewModel(self)
        self.labeling = LabelingViewModel(self)
        self.packaging = PackagingViewModel(self)
        self.repair = RepairViewModel(self)
        for vm in [*self.stage_vms(), self.repair]:
            vm.changed.connect(self.bottom_bar_changed.emit)

        self._clock = QTimer(self)
        self._clock.setInterval(1000)
        self._clock.timeout.connect(self.tick.emit)
        self._outbox_timer = QTimer(self)
        self._outbox_timer.setInterval(OUTBOX_INTERVAL_MS)
        self._outbox_timer.timeout.connect(self.process_outbox)

    # ================================================================== accessors
    def stage_vms(self) -> list[StageViewModel]:
        return [self.programming, self.testing, self.labeling, self.packaging]

    def vm_for(self, stage: Stage) -> StageViewModel | None:
        return {
            Stage.PROGRAMMING: self.programming,
            Stage.TESTING: self.testing,
            Stage.LABELING: self.labeling,
            Stage.PACKAGING: self.packaging,
        }.get(stage)

    @property
    def current_vm(self) -> StageViewModel | None:
        if self.mode is Mode.REPAIR:
            return self.repair
        return self.vm_for(self.stage)

    @property
    def settings(self) -> Any:
        return self.ctx.settings

    @property
    def is_admin(self) -> bool:
        return self.operator is not None and self.operator.is_admin

    @property
    def device(self) -> DeviceState | None:
        return self.ctx.workflow.current_device()

    @property
    def device_in_progress(self) -> bool:
        device = self.device
        return device is not None and device.status is DeviceStatus.IN_PROGRESS

    def session_elapsed_s(self) -> int:
        if self.session is None:
            return 0
        now = self.ctx.repos.clock.now()
        return max(0, int((now - self.session.started_at).total_seconds()))

    # ================================================================== pages
    def set_page(self, page: Page) -> None:
        if page is self.page:
            return
        self.page = page
        if page is not Page.PRODUCTION:
            self.drawer_open = False
            self.drawer_changed.emit()
        self.page_changed.emit()
        self.bottom_bar_changed.emit()

    def start(self) -> None:
        """Crash recovery + outbox purge, then the login page."""
        self.set_page(Page.STARTING)
        self.bg.submit(
            self.ctx.station.startup,
            on_success=self._started,
            on_error=self._startup_failed,
            name="startup",
        )

    def _started(self, result: StartupResult) -> None:
        self.startup = result
        self.set_page(Page.LOGIN)
        self.login_changed.emit()
        self.process_outbox()
        self._outbox_timer.start()

    def _startup_failed(self, error: ParkomateError) -> None:
        self.startup_error = error
        self.set_page(Page.LOGIN)
        self.login_changed.emit()

    # ================================================================== errors & confirms
    def show_error(
        self,
        error: ParkomateError,
        retry: Callable[[], None] | None = None,
        retry_key: str = "action.try_again",
    ) -> None:
        log.warning("shown to operator: %s %s", error.code.value, error.message)
        self.error = ErrorState(error, retry, retry_key)
        self.error_changed.emit()

    def clear_error(self) -> None:
        if self.error is not None:
            self.error = None
            self.error_changed.emit()

    def retry_error(self) -> None:
        state = self.error
        self.clear_error()
        if state is not None and state.retry is not None:
            state.retry()

    def ask(self, confirm: ConfirmState) -> None:
        self.confirm = confirm
        self.confirm_changed.emit()
        self.bottom_bar_changed.emit()

    def answer(self, yes: bool) -> None:
        confirm = self.confirm
        self.confirm = None
        self.confirm_changed.emit()
        self.bottom_bar_changed.emit()
        if confirm is None:
            return
        if yes:
            confirm.on_yes()
        elif confirm.on_no is not None:
            confirm.on_no()

    def escape(self) -> None:
        """Esc never destroys work: it only closes the confirm / drawer / error details."""
        if self.confirm is not None:
            self.answer(False)
        elif self.drawer_open:
            self.toggle_drawer(False)
        elif self.mode is Mode.REPAIR:
            self.repair.cancel_scrap()
        else:
            vm = self.current_vm
            if vm is not None and getattr(vm, "choosing_reject", False):
                vm.cancel_reject()  # type: ignore[attr-defined]

    # ================================================================== login
    def login(self, operator_code: str, password: str) -> None:
        if self.login_phase is not LoginPhase.FORM:
            return
        self.login_phase = LoginPhase.CHECKING
        self.login_error = None
        self.login_changed.emit()
        self.bg.submit(
            lambda: self.ctx.station.login(operator_code, password),
            on_success=self._logged_in,
            on_error=self._login_failed,
            name="login",
        )

    def _login_failed(self, error: ParkomateError) -> None:
        self.login_phase = LoginPhase.FORM
        self.login_error = error
        self.login_changed.emit()

    def _logged_in(self, result: LoginResult) -> None:
        self.operator = result.operator
        self.session = result.session
        self.login_error = None
        set_language(result.language)
        self.login_phase = LoginPhase.AMBIENT
        self.login_changed.emit()
        self.session_changed.emit()
        self._clock.start()
        self.refresh_counters()
        self.hw.submit(
            self.ctx.hardware.measure_ambient,
            on_success=self._session_ambient,
            on_error=self._session_ambient_failed,
            name="ambient",
        )

    def _session_ambient(self, value: float) -> None:
        if not self._record_ambient(value, AmbientReason.SESSION_START):
            self._enter_production()
            return
        self.login_phase = LoginPhase.AMBIENT_DONE
        self.login_changed.emit()
        QTimer.singleShot(self.ambient_result_ms, self._enter_production)

    def _session_ambient_failed(self, error: ParkomateError) -> None:
        self._enter_production()
        self.show_error(error, retry=self.remeasure_ambient)

    def _record_ambient(self, value: float, reason: AmbientReason) -> bool:
        try:
            self.ctx.records.record_ambient(value, reason)
        except ParkomateError as exc:
            self.show_error(exc)
            return False
        self.ambient_c = value
        self.ambient_changed.emit()
        return True

    def _enter_production(self) -> None:
        if self.operator is None or self.page is not Page.LOGIN:
            return  # only ever from the login page (the ambient-result timer may fire late)
        self.login_phase = LoginPhase.FORM
        self.login_changed.emit()
        first_stage = self.operator.effective_stages[0] if self.operator else Stage.PROGRAMMING
        self.stage = first_stage
        self.mode = Mode.PRODUCTION
        self.retest = None
        for vm in [*self.stage_vms(), self.repair]:
            vm.reset()
        self.set_page(Page.PRODUCTION)
        self.mode_changed.emit()
        self.retest_changed.emit()
        self.stage_changed.emit()
        self.refresh_queue_count()
        if first_stage is Stage.PROGRAMMING:
            self.load_firmware()
            self.programming.enter()
        else:
            vm = self.vm_for(first_stage)
            if vm is not None:
                vm.enter()

    def set_language(self, language: str) -> None:
        set_language(language)
        if self.session is not None:
            try:
                self.ctx.records.set_session_language(language)
                self.operator = self.ctx.records.operator
            except ParkomateError:
                log.exception("could not remember the language choice")
        self.bottom_bar_changed.emit()

    # ================================================================== firmware & ambient
    def load_firmware(self) -> None:
        """Download the firmware into RAM (automatically at session start)."""
        if self.firmware_loading:
            return
        self.firmware_loading = True
        self.firmware_error = None
        self.firmware_changed.emit()
        self.hw.submit(
            self.ctx.hardware.fetch_firmware,
            on_success=self._firmware_loaded,
            on_error=self._firmware_failed,
            name="fetch_firmware",
        )

    def _firmware_loaded(self, info: FirmwareInfo) -> None:
        self.firmware_loading = False
        self.firmware = info
        try:
            self.ctx.records.set_session_firmware(info)
        except ParkomateError:
            log.exception("could not store firmware info on the session")
        self.firmware_changed.emit()

    def _firmware_failed(self, error: ParkomateError) -> None:
        self.firmware_loading = False
        self.firmware_error = error
        self.firmware_changed.emit()

    def remeasure_ambient(self) -> None:
        """F9 / drawer button."""
        if self.session is None:
            return
        self.hw.submit(
            self.ctx.hardware.measure_ambient,
            on_success=self._remeasured,
            on_error=lambda err: self.show_error(err, retry=self.remeasure_ambient),
            name="remeasure_ambient",
        )

    def _remeasured(self, value: float) -> None:
        self._record_ambient(value, AmbientReason.REMEASURE)

    # ================================================================== stage flow
    def advance(self) -> None:
        """Primary "Submit and next": close the stage, go to the next one."""
        try:
            new = self.ctx.workflow.submit_and_next()
        except ParkomateError as exc:
            self.show_error(exc)
            return
        self.clear_error()
        old_vm = self.current_vm
        if old_vm is not None:
            old_vm.leave()
        if new is Stage.COMPLETE:
            return  # DeviceCompleted arrives through the event bridge

        operator = self.operator
        if operator is not None and new not in operator.effective_stages:
            state = self.device
            if state is not None and self.session is not None:
                self.ctx.repos.work_queue.enqueue(
                    device_row_id=state.device_row_id,
                    mac_address=state.mac_address,
                    device_id=state.device_id,
                    stage=new.value,
                    source_session_id=self.session.id,
                )
            self.toast.emit(t("queue.handoff"))
            self._next_device()
            return

        self.stage = new
        self.stage_changed.emit()
        self.device_changed.emit()
        vm = self.current_vm
        if vm is not None:
            vm.enter()
        self.bottom_bar_changed.emit()

    def device_updated(self) -> None:
        self.device_changed.emit()
        self.bottom_bar_changed.emit()

    def _on_rejected(self, instruction: RejectInstruction) -> None:
        self.reject = instruction
        vm = self.current_vm
        if vm is not None:
            vm.leave()
        self.confirm = None
        self.confirm_changed.emit()
        self.clear_error()
        self.device_changed.emit()
        self.bottom_bar_changed.emit()
        self.reject_shown.emit(instruction)
        if self.settings.ui.sound:
            QApplication.beep()

    def reject_confirmed(self) -> None:
        """Operator pressed "Device placed in box"."""
        if self.reject is None:
            return
        self.reject = None
        self.reject_cleared.emit()
        self._next_device()

    def _on_completed(self, _row: int, device_id: object) -> None:
        state = self.device
        label = str(device_id) if device_id else (state.mac_address if state else "")
        self.toast.emit(label)
        if self.settings.ui.sound:
            QApplication.beep()
        self._next_device()

    def _release_board(self) -> None:
        hardware = self.ctx.hardware

        def release() -> None:
            hardware.close_camera()
            hardware.disconnect()

        self.hw.submit(release, name="release_board", on_error=lambda e: log.warning("%r", e))

    def _next_device(self) -> None:
        """Clean Programming screen for the next board - or, after a retest, back to the
        Repair tab on the retested board."""
        self._release_board()
        try:
            self.ctx.workflow.clear_finished()
        except ParkomateError as exc:
            self.show_error(exc)
        for vm in self.stage_vms():
            vm.reset()
        first_stage = self.operator.effective_stages[0] if self.operator else Stage.PROGRAMMING
        self.stage = first_stage
        self.clear_error()
        retest = self.retest
        self.retest = None
        self.stage_changed.emit()
        self.device_changed.emit()
        self.refresh_counters()
        self.refresh_session_devices()
        self.refresh_queue_count()
        if retest is not None:
            self.retest_changed.emit()
            self._show_repair(retest.case_id)
        else:
            vm = self.vm_for(first_stage)
            if vm is not None:
                vm.enter()
        self.bottom_bar_changed.emit()


    # ================================================================== work queue
    def refresh_queue_count(self) -> None:
        try:
            stages = (
                tuple(s.value for s in self.operator.effective_stages)
                if self.operator
                else tuple(s.value for s in PRODUCTION_STAGES)
            )
            self.queue_items = self.ctx.repos.work_queue.list_for_operator(stages)
            self.queue_count = len(self.queue_items)
        except Exception:
            self.queue_items = []
            self.queue_count = 0
        self.queue_changed.emit()

    def pick_queue_item(self, queue_id: int) -> None:
        if self.session is None or self.operator is None:
            return
        if self.device_in_progress:
            self.show_error(
                ParkomateError(t("confirm.end_session_device"), code=ErrorCode.RECORD_STATE)
            )
            return
        try:
            item = self.ctx.repos.work_queue.pick(queue_id, self.operator.id, self.session.id)
            target_stage = item.current_stage
            self.ctx.workflow.resume_device(item.device_row_id, target_stage)
            self.stage = target_stage
            self.clear_error()
            self.stage_changed.emit()
            self.device_changed.emit()
            vm = self.current_vm
            if vm is not None:
                vm.enter()
            self.bottom_bar_changed.emit()
            self.toast.emit(t("queue.pickup_success"))
            self.refresh_queue_count()
        except ParkomateError as exc:
            self.show_error(exc)

    def pick_next_queue_item(self) -> None:
        if not self.queue_items:
            return
        for item in self.queue_items:
            if item.current_stage == self.stage:
                self.pick_queue_item(item.id)
                return
        self.pick_queue_item(self.queue_items[0].id)

    # ================================================================== repair tab
    def can_open_repair(self) -> bool:
        return (
            self.page is Page.PRODUCTION
            and not self.device_in_progress
            and self.reject is None
            and self.confirm is None
        )

    def set_mode(self, mode: Mode) -> None:
        """Top-bar switch: the line or the Repair tab (not while a board is on the line)."""
        if mode is self.mode:
            return
        if mode is Mode.REPAIR:
            if not self.can_open_repair():
                self.mode_changed.emit()  # puts the switch back
                return
            self.programming.leave()
            if self.retest is not None:  # a retest that never started is simply dropped
                self.retest = None
                self.retest_changed.emit()
            self._release_board()
            self.clear_error()
            self._show_repair(None)
            return
        self.repair.leave()
        self.mode = Mode.PRODUCTION
        self.stage = Stage.PROGRAMMING
        self.clear_error()
        self.programming.reset()
        self.mode_changed.emit()
        self.stage_changed.emit()
        self.programming.enter()
        self.bottom_bar_changed.emit()

    def _show_repair(self, case_id: int | None) -> None:
        self.mode = Mode.REPAIR
        self.toggle_drawer(False)
        self.mode_changed.emit()
        if case_id is None:
            self.repair.enter()
        else:
            try:
                self.repair.show(case_id)
            except ParkomateError as exc:
                self.show_error(exc)
                self.repair.enter()
        self.bottom_bar_changed.emit()

    def start_retest(self, case_id: int, board_id: str) -> None:
        """Repair tab -> "Test again": the board runs the whole line again."""
        if self.device_in_progress or self.page is not Page.PRODUCTION:
            return
        try:
            case = self.ctx.repairs.get(case_id)
        except ParkomateError as exc:
            self.show_error(exc)
            return
        self.retest = RetestTarget(case.id, case.mac_address, board_id)
        expect = getattr(self.ctx.hardware, "expect_board", None)
        if callable(expect):  # simulated bench: the repaired board is plugged back in
            mac = case.mac_address
            self.hw.submit(lambda: expect(mac), name="expect_board")
        self.repair.leave()
        self.mode = Mode.PRODUCTION
        self.stage = Stage.PROGRAMMING
        self.clear_error()
        self.programming.reset()
        self.retest_changed.emit()
        self.mode_changed.emit()
        self.stage_changed.emit()
        self.programming.enter()
        self.bottom_bar_changed.emit()

    def request_cancel_retest(self) -> None:
        if self.retest is None:
            return
        if not self.device_in_progress:
            self.cancel_retest()
            return
        self.ask(
            ConfirmState(
                "confirm.cancel_retest",
                self.cancel_retest,
                yes_key="action.cancel_retest",
                params={"board": self.retest.board_id},
            )
        )

    def cancel_retest(self) -> None:
        """Stop the retest: the board goes back to the repair list (case: repaired)."""
        retest = self.retest
        if retest is None:
            return
        vm = self.vm_for(self.stage)
        if vm is not None:
            vm.leave()
        if self.device_in_progress:
            try:
                self.ctx.workflow.abandon_device()
            except ParkomateError as exc:
                self.show_error(exc)
        else:
            try:
                self.ctx.workflow.clear_finished()
            except ParkomateError:
                log.debug("nothing to clear after the retest")
        self._release_board()
        self.retest = None
        for stage_vm in self.stage_vms():
            stage_vm.reset()
        self.stage = Stage.PROGRAMMING
        self.clear_error()
        self.retest_changed.emit()
        self.stage_changed.emit()
        self.device_changed.emit()
        self.refresh_session_devices()
        self._show_repair(retest.case_id)

    # ================================================================== counters / drawer
    def refresh_counters(self) -> None:
        if self.ctx.records.session is None:
            return
        try:
            self.counters = self.ctx.records.get_counters()
        except ParkomateError:
            log.exception("could not read counters")
            return
        self.counters_changed.emit()

    def reset_counters(self) -> None:
        operator = self.operator
        if operator is None or not operator.is_admin:
            return

        def do_reset() -> None:
            try:
                self.ctx.records.reset_counters(operator)
            except ParkomateError as exc:
                self.show_error(exc)
            self.refresh_counters()

        self.ask(
            ConfirmState(
                "confirm.reset_counters", do_reset, yes_key="action.reset_counters", danger=True
            )
        )

    def toggle_drawer(self, open_: bool | None = None) -> None:
        self.drawer_open = (not self.drawer_open) if open_ is None else open_
        if self.drawer_open:
            self.refresh_session_devices()
        self.drawer_changed.emit()

    def refresh_session_devices(self) -> None:
        if self.ctx.records.session is None:
            self.session_devices = []
        else:
            self.session_devices = list(reversed(self.ctx.records.list_session_devices()))
        self.session_changed.emit()

    def function_key(self, number: int) -> None:
        if self.page is not Page.PRODUCTION or self.reject is not None:
            return
        if number == 9 and self.mode is Mode.PRODUCTION:
            self.remeasure_ambient()
            return
        vm = self.current_vm
        if vm is not None:
            vm.function_key(number)

    # ================================================================== admin
    def can_open_admin(self) -> bool:
        return self.is_admin and not self.device_in_progress and self.reject is None

    def open_admin(self) -> None:
        if self.can_open_admin():
            vm = self.current_vm
            if vm is not None:
                vm.leave()
            self.set_page(Page.ADMIN)

    def close_admin(self) -> None:
        if self.page is Page.ADMIN:
            self.set_page(Page.PRODUCTION)
            self.refresh_counters()
            vm = self.current_vm
            if vm is not None:
                vm.enter()

    # ================================================================== session end
    def request_end_session(self) -> None:
        key = "confirm.end_session_device" if self.device_in_progress else "confirm.end_session"
        self.ask(ConfirmState(key, self.end_session, yes_key="action.end_session", danger=True))

    def end_session(self) -> None:
        if self.session is None:
            return
        vm = self.current_vm
        if vm is not None:
            vm.leave()
        try:
            self.ctx.workflow.abandon_device()
        except ParkomateError:
            log.exception("could not abandon the device on the bench")
        self.clear_error()
        self.toggle_drawer(False)
        self.send_state = SendState.CLOSING
        self.logout_result = None
        self.set_page(Page.SESSION_END)
        self.session_end_changed.emit()
        hardware = self.ctx.hardware

        def release() -> None:
            hardware.close_camera()
            hardware.disconnect()

        self.hw.submit(release, name="release_board", on_error=lambda e: log.warning("%r", e))
        self.bg.submit(
            lambda: self.ctx.station.logout(SessionEndReason.LOGOUT),
            on_success=self._session_closed,
            on_error=self._session_close_failed,
            name="logout",
        )

    def _session_closed(self, result: LogoutResult) -> None:
        self.logout_result = result
        self._clock.stop()
        if result.report_error is not None or result.queued is None:
            self.send_state = SendState.REPORT_ERROR
        elif result.queued.outbox_item is None:
            self.send_state = SendState.DISABLED
        else:
            self.send_state = SendState.SENDING
            item_id = result.queued.outbox_item.id
            self.bg.submit(
                lambda: self.ctx.outbox.send_item(item_id),
                on_success=lambda sent: self._report_sent(bool(sent)),
                on_error=lambda _e: self._report_sent(False),
                name="send_report",
            )
        self.session_end_changed.emit()

    def _report_sent(self, sent: bool) -> None:
        self.send_state = SendState.SENT if sent else SendState.SAVED
        self.session_end_changed.emit()

    def _session_close_failed(self, error: ParkomateError) -> None:
        self.send_state = SendState.REPORT_ERROR
        self.show_error(error)
        self.session_end_changed.emit()

    @property
    def summary(self) -> SessionSummary | None:
        return self.logout_result.summary if self.logout_result else None

    def finish_logout(self) -> None:
        """Back to the login screen after the session summary."""
        self.operator = None
        self.session = None
        self.counters = None
        self.ambient_c = None
        self.reject = None
        self.logout_result = None
        self.send_state = None
        self.login_phase = LoginPhase.FORM
        self.login_error = None
        self.startup = None
        self.mode = Mode.PRODUCTION
        self.retest = None
        for vm in [*self.stage_vms(), self.repair]:
            vm.reset()
        set_language(self.settings.station.language)
        self.set_page(Page.LOGIN)
        self.login_changed.emit()
        self.session_changed.emit()

    # ================================================================== outbox
    def process_outbox(self) -> None:
        if self._outbox_busy:
            return
        self._outbox_busy = True

        def done(_result: SendReport | ParkomateError) -> None:
            self._outbox_busy = False

        self.bg.submit(self.ctx.station.send_pending, on_success=done, on_error=done, name="outbox")

    def outbox_pending_count(self) -> int:
        counts = self.ctx.outbox.counts()
        return counts[OutboxStatus.PENDING] + counts[OutboxStatus.FAILED]

    # ================================================================== shutdown
    def shutdown(self) -> None:
        """Window closing: abandon the device, close the session, release hardware."""
        if self._shut_down:
            return
        self._shut_down = True
        self._clock.stop()
        self._outbox_timer.stop()
        self.hw.wait(10_000)
        self.bg.wait(30_000)
        if self.ctx.records.session is not None:
            try:
                self.ctx.workflow.abandon_device()
                self.ctx.station.logout(SessionEndReason.CLOSE)
            except ParkomateError:
                log.exception("closing the session on exit failed")
        self.bridge.close()
        self.ctx.close()

    def language(self) -> str:
        return get_language()
