"""Repair tab: faulty boards - repair, test again (full line), then accept or scrap.

The list and the case details come from :class:`~parkomate.workflow.repair.RepairService`;
every rule (who may accept, when scrap is allowed, notes) lives there. The bottom bar shows
the next step of the selected case as THE primary action:

    waiting   →  Test again (disabled: "save what you repaired first")
    repaired  →  Test again        (the board then runs Programming → Packaging again)
    passed    →  Accept board      (green)
    closed    →  nothing left to do

Scrap is a secondary action that opens a small form (reason + note); while it is open the
primary action is "Scrap board".
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from parkomate.core.enums import RepairAction, RepairStatus, ScrapReason, Stage
from parkomate.core.errors import ParkomateError
from parkomate.ui.viewmodels.base import Action, StageViewModel, StatusLine
from parkomate.workflow.repair import RepairCaseDetail, RepairCaseView, RepairService

if TYPE_CHECKING:
    from parkomate.ui.viewmodels.station import StationController


class RepairViewModel(StageViewModel):
    stage = Stage.REJECTED  # not a production stage; the repair tab has its own page state

    def __init__(self, controller: StationController) -> None:
        super().__init__(controller)
        self.show_open = True
        self.search = ""
        self.cases: list[RepairCaseView] = []
        self.open_count = 0
        self.selected_id: int | None = None
        self.detail: RepairCaseDetail | None = None
        self.reset()

    # ------------------------------------------------------------------ state
    def reset(self) -> None:
        self.selected_id = None
        self.detail = None
        self.cases = []
        self.search = ""
        self.show_open = True
        self._clear_forms()
        self.message: tuple[str, dict[str, object]] | None = None

    def _clear_forms(self) -> None:
        self.action: RepairAction | None = None
        self.note = ""
        self.scrapping = False
        self.scrap_reason: ScrapReason | None = None
        self.scrap_note = ""

    @property
    def service(self) -> RepairService:
        return self.c.ctx.repairs

    @property
    def case_status(self) -> RepairStatus | None:
        return self.detail.case.status if self.detail is not None else None

    def enter(self) -> None:
        self.refresh()

    def leave(self) -> None:
        if self.scrapping:
            self.scrapping = False
            self.notify()

    # ------------------------------------------------------------------ list
    def refresh(self) -> None:
        try:
            self.cases = self.service.list_cases(open_only=self.show_open, search=self.search)
            self.open_count = self.service.open_count()
        except ParkomateError as exc:
            self.c.show_error(exc)
            self.cases = []
        ids = [view.case.id for view in self.cases]
        if self.selected_id not in ids:
            self.selected_id = ids[0] if ids else None
            self._clear_forms()
        self._load_detail()
        self.notify()

    def _load_detail(self) -> None:
        if self.selected_id is None:
            self.detail = None
            return
        try:
            self.detail = self.service.detail(self.selected_id)
        except ParkomateError as exc:
            self.detail = None
            self.c.show_error(exc)

    def select(self, case_id: int | None) -> None:
        if case_id == self.selected_id:
            return
        self.selected_id = case_id
        self._clear_forms()
        self.message = None
        self._load_detail()
        self.notify()

    def show(self, case_id: int) -> None:
        """Open the tab on ``case_id`` (after its retest): the case is listed whatever its
        status."""
        case = self.service.get(case_id)
        self.show_open = case.status.is_open
        self.search = ""
        self.selected_id = case_id
        self.message = None
        self._clear_forms()
        self.refresh()

    def set_show_open(self, show_open: bool) -> None:
        if show_open != self.show_open:
            self.show_open = show_open
            self.message = None
            self.refresh()

    def set_search(self, text: str) -> None:
        text = text.strip()
        if text != self.search:
            self.search = text
            self.refresh()

    # ------------------------------------------------------------------ repair form
    def set_action(self, action: RepairAction | None) -> None:
        self.action = action
        self.notify()

    def set_note(self, text: str) -> None:
        self.note = text
        self.notify()

    def repair_reason(self) -> str | None:
        """Why "Save repair" is disabled (``None`` = it is enabled)."""
        detail = self.detail
        if detail is None:
            return "repair.gate.choose_board"
        blocked = RepairService.repair_blocker(detail.case)
        if blocked:
            return blocked
        if self.action is None:
            return "repair.gate.choose_action"
        if self.action.needs_note and not self.note.strip():
            return "repair.gate.write_note"
        return None

    def save_repair(self) -> None:
        detail, action = self.detail, self.action
        if detail is None or action is None or self.repair_reason() is not None:
            return
        case = self.guard(lambda: self.service.record_repair(detail.case.id, action, self.note))
        if case is None:
            return
        self.action = None
        self.note = ""
        self.message = ("repair.msg.saved", {})
        self.refresh()

    # ------------------------------------------------------------------ test again / accept
    def test_again(self) -> None:
        detail = self.detail
        if detail is None or RepairService.retest_blocker(detail.case) is not None:
            return
        self.c.start_retest(detail.case.id, detail.view.board_id)

    def accept(self) -> None:
        detail = self.detail
        if detail is None or RepairService.accept_blocker(detail.case) is not None:
            return
        case = self.guard(lambda: self.service.accept(detail.case.id))
        if case is None:
            return
        self.message = ("repair.msg.accepted", {"board": detail.view.board_id})
        self.refresh()

    # ------------------------------------------------------------------ scrap
    def open_scrap(self) -> None:
        detail = self.detail
        if detail is None or RepairService.scrap_blocker(detail.case) is not None:
            return
        self.scrapping = True
        self.scrap_reason = None
        self.scrap_note = ""
        self.notify()

    def cancel_scrap(self) -> None:
        if self.scrapping:
            self.scrapping = False
            self.notify()

    def set_scrap_reason(self, reason: ScrapReason | None) -> None:
        self.scrap_reason = reason
        self.notify()

    def set_scrap_note(self, text: str) -> None:
        self.scrap_note = text
        self.notify()

    def scrap_reason_missing(self) -> str | None:
        if self.scrap_reason is None:
            return "repair.gate.choose_reason"
        if self.scrap_reason.needs_note and not self.scrap_note.strip():
            return "repair.gate.write_note"
        return None

    def confirm_scrap(self) -> None:
        detail, reason = self.detail, self.scrap_reason
        if detail is None or reason is None or self.scrap_reason_missing() is not None:
            return
        case = self.guard(lambda: self.service.scrap(detail.case.id, reason, self.scrap_note))
        if case is None:
            return
        self.scrapping = False
        self.message = ("repair.msg.scrapped", {"board": detail.view.board_id})
        self.refresh()

    # ------------------------------------------------------------------ bottom bar
    def primary(self) -> Action:
        enter = "key.enter"
        detail = self.detail
        if self.scrapping:
            missing = self.scrap_reason_missing()
            return Action(
                "action.scrap_board",
                self.confirm_scrap,
                enabled=missing is None,
                reason_key=missing,
                hint_key=enter,
                variant="danger",
                name="scrap_confirm",
            )
        if detail is None:
            return Action(
                "action.test_again",
                enabled=False,
                reason_key="repair.gate.choose_board",
                hint_key=enter,
                name="retest",
            )
        if detail.case.status is RepairStatus.PASSED:
            return Action(
                "action.accept_board", self.accept, hint_key=enter, variant="success", name="accept"
            )
        blocked = RepairService.retest_blocker(detail.case)
        if blocked is None and self.c.device_in_progress:
            blocked = "gate.admin_device_busy"
        return Action(
            "action.test_again",
            self.test_again,
            enabled=blocked is None,
            reason_key=blocked,
            hint_key=enter,
            name="retest",
        )

    def secondary(self) -> list[Action]:
        if self.scrapping:
            return [
                Action(
                    "action.cancel",
                    self.cancel_scrap,
                    hint_key="key.esc",
                    variant="secondary",
                    name="scrap_cancel",
                )
            ]
        detail = self.detail
        if detail is None or RepairService.scrap_blocker(detail.case) is not None:
            return []
        return [Action("action.scrap_board", self.open_scrap, variant="danger", name="scrap")]

    def status(self) -> StatusLine | None:
        detail = self.detail
        if self.scrapping:
            return StatusLine("status.repair.scrapping", tone="warn")
        if detail is None:
            if self.cases or self.search:
                return StatusLine("status.repair.choose", tone="pending")
            key = "status.repair.none_open" if self.show_open else "status.repair.none_closed"
            return StatusLine(key, tone="pass" if self.show_open else "info")
        status = detail.case.status
        key = f"status.repair.{status.value}"
        tone = {
            RepairStatus.WAITING: "warn",
            RepairStatus.REPAIRED: "info",
            RepairStatus.RETESTING: "pending",
            RepairStatus.PASSED: "pass",
            RepairStatus.ACCEPTED: "pass",
            RepairStatus.SCRAPPED: "fail",
        }[status]
        return StatusLine(key, {"board": detail.view.board_id}, tone=tone)

    def function_key(self, number: int) -> bool:
        if number == 5:
            self.refresh()
            return True
        return False
