"""The four stage screens on the 12-column grid: left 5 columns = steps / checks, right
7 columns = live data / result. One level of cards on the page background."""

from __future__ import annotations

import re
from datetime import datetime

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget

from parkomate.core.enums import (
    MAX_SENSOR_READINGS,
    CheckCode,
    IdentityStatus,
    IdEntryMethod,
    Stage,
)
from parkomate.core.models import CheckOutcome, PortInfo
from parkomate.i18n import t
from parkomate.ui.components.base import Divider
from parkomate.ui.components.buttons import AppButton
from parkomate.ui.components.camera import CameraFrame
from parkomate.ui.components.cards import Banner, Card, IconBadge
from parkomate.ui.components.checklist import ChecklistRow
from parkomate.ui.components.chips import StatusChip
from parkomate.ui.components.icons import Icon
from parkomate.ui.components.inputs import ROLE_SECONDARY, ROLE_SHORT, Select, TextField
from parkomate.ui.components.layout import ScrollArea, column_grid
from parkomate.ui.components.measure import Band, ReadingSlots, ValueRow
from parkomate.ui.components.progress import AttemptDots, ProgressBar, ProgressRing
from parkomate.ui.components.segmented import PassFailToggle
from parkomate.ui.components.stepper import StepList
from parkomate.ui.components.text import Text, TrText
from parkomate.ui.qt_i18n import language_notifier
from parkomate.ui.theme.tokens import COLORS, SIZES, SPACE
from parkomate.ui.viewmodels.base import StageViewModel
from parkomate.ui.viewmodels.labeling import ChecklistMixin, LabelingViewModel, PackagingViewModel
from parkomate.ui.viewmodels.programming import ProgrammingViewModel, StepState
from parkomate.ui.viewmodels.station import StationController
from parkomate.ui.viewmodels.testing import TestingViewModel

CHIP = {
    StepState.PENDING: "neutral",
    StepState.WORKING: "working",
    StepState.PASS: "success",
    StepState.FAIL: "danger",
    StepState.ERROR: "warning",
}
STEP = {
    StepState.PENDING: "pending",
    StepState.WORKING: "working",
    StepState.PASS: "pass",
    StepState.FAIL: "fail",
    StepState.ERROR: "error",
}
CHECK_ICONS = {
    CheckCode.C1: "developer_board",
    CheckCode.C2: "build",
    CheckCode.C3: "label",
    CheckCode.C4: "qr_code_2",
    CheckCode.D1: "sensors",
    CheckCode.D2: "lightbulb",
    CheckCode.D3: "cable",
    CheckCode.D4: "build",
}
_BRIDGE = re.compile(r"\b(CP\d{3,4}\w*|CH\d{3}\w*|FT\d{3}\w*|PL\d{4}\w*|ESP32\S*)", re.IGNORECASE)
CAMERA_POLL_MS = 66  # ~15 fps preview


def local_time(value: datetime) -> str:
    return value.astimezone().strftime("%H:%M:%S")


def short_bridge(port: PortInfo) -> str:
    """'Silicon Labs CP210x USB to UART Bridge' -> 'CP210x' (P4)."""
    match = _BRIDGE.search(port.description or "")
    if match:
        return match.group(1)
    return " ".join((port.description or "").split()[:2])


class StageView(QWidget):
    vm: StageViewModel

    def __init__(self, controller: StationController, vm: StageViewModel) -> None:
        super().__init__()
        self.c = controller
        self.vm = vm
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.left_scroll = ScrollArea()
        self.right_scroll = ScrollArea()
        self.left_layout = self.left_scroll.layout_
        self.right_layout = self.right_scroll.layout_
        layout.addLayout(column_grid(self.left_scroll, self.right_scroll))
        vm.changed.connect(self.update_view)
        language_notifier().changed.connect(self.update_view)

    def finish_columns(self) -> None:
        self.left_layout.addStretch(1)
        self.right_layout.addStretch(1)

    def update_view(self, *_args: object) -> None:
        raise NotImplementedError


class RejectChooser(Card):
    """'Which item failed?' - inline, never a dialog."""

    def __init__(self, vm: ChecklistMixin, parent: QWidget | None = None) -> None:
        super().__init__("reject.choose_item", icon="error", parent=parent)
        self.vm = vm
        self.set_variant("danger")
        self._grid = QGridLayout()
        self._grid.setSpacing(SPACE.s)
        self.body.addLayout(self._grid)
        self.cancel = AppButton("action.cancel", variant="outlined", hint_key="key.esc")
        self.cancel.clicked.connect(vm.cancel_reject)
        self.body.addWidget(self.cancel, 0, Qt.AlignmentFlag.AlignRight)
        self._buttons: dict[CheckCode, AppButton] = {}
        self.setVisible(False)

    def update_view(self) -> None:
        codes = self.vm.reject_codes()
        if list(self._buttons) != codes:
            for button in self._buttons.values():
                button.deleteLater()
            self._buttons = {}
            for index, code in enumerate(codes):
                button = AppButton(code.label_key, variant="danger_tonal", size="compact")
                button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                button.clicked.connect(lambda _c=False, code=code: self.vm.reject_for(code))
                self._grid.addWidget(button, index // 2, index % 2)
                self._buttons[code] = button
        self.setVisible(self.vm.choosing_reject)


# =========================================================================== Programming


class ResultHero(Card):
    """The right half of Programming - what is happening, big and calm (P3)."""

    def __init__(self) -> None:
        super().__init__()
        self.body.setSpacing(SPACE.m)
        self.body.addStretch(1)
        center = Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
        self.badge = IconBadge("usb", "neutral", size=SIZES.ring)
        self.ring = ProgressRing()
        self.body.addWidget(self.badge, 0, Qt.AlignmentFlag.AlignHCenter)
        self.body.addWidget(self.ring, 0, Qt.AlignmentFlag.AlignHCenter)
        self.title = Text("", "headline", wrap=True, align=center)
        self.text = Text("", "body_lg", "secondary", wrap=True, align=center)
        self.body.addWidget(self.title)
        self.body.addWidget(self.text)
        dots_row = QHBoxLayout()
        dots_row.setSpacing(SPACE.s)
        dots_row.addStretch(1)
        self.dots = AttemptDots()
        self.dots_caption = Text("", "caption", "secondary")
        dots_row.addWidget(self.dots)
        dots_row.addWidget(self.dots_caption)
        dots_row.addStretch(1)
        self.body.addLayout(dots_row)
        self.body.addStretch(1)
        self.adjust = Banner("info", actions_below=True)
        self.adjust_yes = AppButton("action.adjust_yes", variant="tonal")
        self.adjust_no = AppButton("action.adjust_no", variant="outlined")
        self.adjust.action_box.addWidget(self.adjust_no)
        self.adjust.action_box.addWidget(self.adjust_yes)
        self.body.addWidget(self.adjust)

    def show_badge(self, icon: str, tone: str) -> None:
        self.ring.setVisible(False)
        self.ring.set_indeterminate(False)
        self.badge.setVisible(True)
        self.badge.set_icon(icon, tone)

    def show_ring(self, value: int | None, state: str = "running") -> None:
        self.badge.setVisible(False)
        self.ring.setVisible(True)
        self.ring.set_state(state)
        self.ring.set_indeterminate(value is None)
        if value is not None:
            self.ring.set_value(value)


class ProgrammingView(StageView):
    vm: ProgrammingViewModel

    def __init__(self, controller: StationController) -> None:
        super().__init__(controller, controller.programming)
        steps_card = Card("prog.steps_title")
        self.steps = StepList(
            ["prog.step.connect", "prog.step.authorised", "prog.step.firmware", "prog.step.upload"]
        )
        self.step_connect, self.step_whitelist, self.step_firmware, self.step_upload = (
            self.steps.items
        )
        steps_card.body.addWidget(self.steps)
        self.left_layout.addWidget(steps_card)
        # 1 - connect
        self.port_combo = Select()
        self.port_combo.set_placeholder_key("prog.choose_port")
        self.port_combo.activated.connect(self._port_chosen)
        self.chip = Text("", "caption", "secondary")
        self.step_connect.body.addWidget(self.port_combo)
        self.step_connect.body.addWidget(self.chip)
        # 2 - whitelist
        self.mac = Text("", "mono_title")
        self.step_whitelist.body.addWidget(self.mac)
        # 3 - firmware
        self.firmware_text = Text("", "body", "secondary", wrap=True)
        self.step_firmware.body.addWidget(self.firmware_text)
        # 4 - upload
        self.progress = ProgressBar()
        self.upload_info = Text("", "caption", "secondary")
        self.step_upload.body.addWidget(self.progress)
        self.step_upload.body.addWidget(self.upload_info)
        self.left_layout.addStretch(1)
        # result hero
        self.hero = ResultHero()
        self.hero.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.right_layout.addWidget(self.hero, 1)
        self.adjust = self.hero.adjust
        self.adjust_yes = self.hero.adjust_yes
        self.adjust_no = self.hero.adjust_no
        self.adjust_yes.clicked.connect(lambda: self.vm.answer_adjust(True))
        self.adjust_no.clicked.connect(lambda: self.vm.answer_adjust(False))
        controller.session_changed.connect(self.update_view)
        self.update_view()

    def _port_chosen(self, index: int) -> None:
        self.vm.select_port(self.port_combo.itemData(index))

    # ------------------------------------------------------------------ render
    def update_view(self, *_args: object) -> None:
        vm = self.vm
        self._render_ports()
        self.step_connect.set_state(
            STEP[vm.connect_state],
            {
                StepState.WORKING: "gate.connecting",
                StepState.PASS: "status.word.done",
                StepState.ERROR: "prog.connect_failed",
            }.get(vm.connect_state),
        )
        self.chip.setText(t("prog.chip", chip=vm.chip) if vm.chip else "")
        self.chip.setVisible(bool(vm.chip))
        # 2 - whitelist
        if vm.mac:
            self.mac.set_key(None)
            self.mac.setText(vm.mac)
            self.mac.set_style("mono_title")
            self.mac.set_tone("primary")
        else:
            self.mac.set_key("prog.mac_unknown")
            self.mac.set_style("body")
            self.mac.set_tone("tertiary")
        self.step_whitelist.set_state(
            STEP[vm.whitelist_state],
            {
                StepState.WORKING: "prog.whitelist.checking",
                StepState.PASS: "prog.whitelist.allowed",
                StepState.FAIL: "prog.whitelist.denied",
                StepState.ERROR: "prog.whitelist.error",
            }.get(vm.whitelist_state),
        )
        # 3 - firmware
        firmware = self.c.firmware
        if self.c.firmware_loading:
            self.firmware_text.setText("")
            self.step_firmware.set_state("working", "prog.firmware.loading")
        elif self.c.firmware_error is not None:
            self.firmware_text.setText("")
            self.step_firmware.set_state("error", "prog.firmware.error")
        elif firmware is not None:
            self.firmware_text.setText(
                t("prog.firmware.info", name=firmware.name, version=firmware.version)
            )
            self.step_firmware.set_state(
                "pass", "prog.firmware.hash_ok" if firmware.hash_verified else "status.word.done"
            )
        else:
            self.firmware_text.setText("")
            self.step_firmware.set_state("pending")
        self.firmware_text.setVisible(bool(self.firmware_text.text()))
        self._render_upload()
        self._render_hero()

    def _render_upload(self) -> None:
        """The bar appears only once an upload has started (P2); red keeps the % reached."""
        vm = self.vm
        started = vm.upload_state is not StepState.PENDING or vm.attempts > 0
        self.progress.setVisible(started)
        if vm.upload_state is StepState.PASS:
            self.progress.set_state("success")
        elif vm.upload_state in (StepState.FAIL, StepState.ERROR):
            self.progress.set_state("danger")
        else:
            self.progress.set_state("running")
        self.progress.set_value(vm.progress, animate=vm.upload_state is StepState.WORKING)
        self.progress.setAccessibleName(t("prog.step.upload"))
        info = []
        if started:
            info.append(f"{vm.progress} %")
            info.append(t("prog.elapsed", s=f"{vm.elapsed_s:.1f}"))
        if vm.attempts or vm.upload_state is StepState.WORKING:
            shown = vm.attempts + (1 if vm.upload_state is StepState.WORKING else 0)
            info.append(t("prog.attempt", n=max(1, shown), total=vm.max_attempts))
        self.upload_info.setText("  ·  ".join(info))
        self.upload_info.setVisible(bool(info))
        caption = {
            StepState.WORKING: "status.word.uploading",
            StepState.PASS: "status.word.done",
            StepState.FAIL: "status.word.fail",
        }.get(vm.upload_state)
        self.step_upload.set_state(STEP[vm.upload_state], caption)

    def _render_ports(self) -> None:
        vm = self.vm
        combo = self.port_combo
        combo.blockSignals(True)
        combo.clear()
        for port in vm.ports:
            secondary = port.description + (f"  ({port.vid_pid})" if port.vid_pid else "")
            combo.addItem(port.name, port.name)
            index = combo.count() - 1
            combo.setItemData(index, f"{port.name} · {short_bridge(port)}", ROLE_SHORT)
            combo.setItemData(index, secondary, ROLE_SECONDARY)
            combo.setItemData(index, f"{port.name}  -  {secondary}", Qt.ItemDataRole.ToolTipRole)
        index = combo.findData(vm.selected_port) if vm.selected_port else -1
        combo.setCurrentIndex(index)
        combo.setToolTip(
            str(combo.itemData(index, Qt.ItemDataRole.ToolTipRole)) if index >= 0 else ""
        )
        combo.setEnabled(not vm.device_started and not vm.ports_loading)
        combo.setAccessibleName(t("prog.step.connect"))
        combo.blockSignals(False)
        combo.update()

    def _render_hero(self) -> None:
        vm = self.vm
        hero = self.hero
        firmware = self.c.firmware
        version = firmware.version if firmware else "-"
        passed = vm.upload_state is StepState.PASS
        results = [False] * max(0, vm.attempts - (1 if passed else 0))
        if passed:
            results.append(True)
        hero.dots.set_attempts(results, vm.max_attempts)
        show_dots = vm.attempts > 0 or vm.upload_state is StepState.WORKING
        hero.dots.setVisible(show_dots)
        hero.dots_caption.setVisible(show_dots)
        shown = vm.attempts + (1 if vm.upload_state is StepState.WORKING else 0)
        hero.dots_caption.setText(t("prog.attempt", n=max(1, shown), total=vm.max_attempts))
        state = vm.upload_state
        if state is StepState.WORKING:
            hero.show_ring(vm.progress)
            hero.title.setText(t("prog.hero.uploading", version=version))
            hero.text.setText(t("prog.elapsed", s=f"{vm.elapsed_s:.1f}"))
        elif passed:
            hero.show_badge("check_circle", "success")
            hero.title.setText(t("prog.hero.pass", version=version))
            hero.text.setText(t("prog.result.pass"))
        elif state in (StepState.FAIL, StepState.ERROR) and vm.attempts:
            hero.show_badge("cancel", "danger")
            outcome = vm.last_outcome
            reason = t(outcome.reason_key) if outcome and outcome.reason_key else ""
            hero.title.setText(t("prog.hero.fail"))
            retry_left = vm.attempts < vm.max_attempts
            hero.text.setText(t("prog.hero.fail_hint") if retry_left else reason)
        elif vm.whitelist_state is StepState.FAIL:
            hero.show_badge("block", "danger")
            hero.title.setText(t("prog.whitelist.denied"))
            hero.text.setText(t("prog.mac", mac=vm.mac or "-"))
        elif vm.connect_state is StepState.WORKING or vm.whitelist_state is StepState.WORKING:
            hero.show_ring(None)
            connecting = vm.connect_state is StepState.WORKING
            hero.title.setText(t("prog.hero.connecting" if connecting else "prog.hero.checking"))
            hero.text.setText(vm.selected_port or "")
        elif vm.whitelist_state is StepState.PASS and vm.firmware_ready:
            hero.show_badge("verified_user", "info")
            hero.title.setText(t("prog.hero.ready"))
            hero.text.setText(t("prog.hero.ready_text", version=version, mac=vm.mac or "-"))
        elif vm.device_started:
            hero.show_badge("memory", "info")
            hero.title.setText(t("prog.hero.preparing"))
            hero.text.setText("" if vm.firmware_ready else t("gate.firmware_loading"))
        else:
            hero.show_badge("usb", "neutral")
            hero.title.setText(t("prog.hero.idle"))
            hero.text.setText(self._port_hint())
        hero.text.setVisible(bool(hero.text.text()))
        if vm.adjust_prompt:
            hero.adjust.set_texts(t("prog.adjust.question"), t("prog.adjust.help"))
        self.adjust.setVisible(vm.adjust_prompt)
        hero.set_variant(
            {StepState.PASS: "success", StepState.FAIL: "danger"}.get(state, "default")
        )

    def _port_hint(self) -> str:
        vm = self.vm
        if vm.ports_loading:
            return t("status.prog.looking_for_ports")
        if not vm.ports:
            return t("prog.hero.no_port")
        if vm.selected_port is None:
            return t("prog.hero.choose_port")
        port = next((p for p in vm.ports if p.name == vm.selected_port), None)
        return t(
            "prog.hero.port_hint", port=vm.selected_port, chip=short_bridge(port) if port else ""
        )


# =========================================================================== Testing


class DecisionRow(QWidget):
    """'Sensor readings' + help line + [Success | Failure] toggle (S2)."""

    def __init__(
        self, code: CheckCode, title_key: str, help_key: str, vm: TestingViewModel
    ) -> None:
        super().__init__()
        self.code = code
        self.vm = vm
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACE.l)
        text = QVBoxLayout()
        text.setSpacing(0)
        text.addWidget(TrText(title_key, "body_lg_strong"))
        text.addWidget(TrText(help_key, "caption", "secondary", wrap=True))
        layout.addLayout(text, 1)
        self.toggle = PassFailToggle()
        self.success = self.toggle.success
        self.failure = self.toggle.failure
        layout.addWidget(self.toggle, 0, Qt.AlignmentFlag.AlignVCenter)
        self.success.clicked.connect(self._success)
        self.failure.clicked.connect(self._failure)

    def _success(self) -> None:
        self.vm.mark(self.code, True)

    def _failure(self) -> None:
        self.vm.mark(self.code, False)

    def update_view(self, enabled: bool, lock_key: str | None, **params: object) -> None:
        value = self.vm.marks[self.code]
        self.success.setChecked(value is True)
        self.failure.setChecked(value is False)
        self.success.setEnabled(enabled and value is None)
        self.failure.setEnabled(enabled and value is None)
        locked = not enabled and value is None
        self.toggle.set_locked(lock_key if locked else None)
        if locked and lock_key:
            tip = t(lock_key, **params)
            for widget in (self.toggle.lock, self.success, self.failure):
                widget.setToolTip(tip)


class TestingView(StageView):
    vm: TestingViewModel

    ROWS = (
        (CheckCode.B3_V_A, "bolt"),
        (CheckCode.B3_V_B, "bolt"),
        (CheckCode.B3_V_C, "bolt"),
        (CheckCode.B3_T_REG, "device_thermostat"),
    )

    def __init__(self, controller: StationController) -> None:
        super().__init__(controller, controller.testing)
        # B1 communication
        self.card_comm = Card("test.step.comm", icon="cable", compact=True)
        self.comm_chip = StatusChip(compact=True)
        self.card_comm.add_trailing(self.comm_chip)
        self.comm_text = self.card_comm.subtitle
        self.left_layout.addWidget(self.card_comm)
        # B2 sensor
        self.card_sensor = Card("test.step.sensor", icon="sensors", compact=True)
        self.sensor_chip = StatusChip(compact=True)
        self.card_sensor.add_trailing(self.sensor_chip)
        self.reading_title = self.card_sensor.subtitle
        self.reading_title.setVisible(True)
        self.slots = ReadingSlots(MAX_SENSOR_READINGS)
        self.card_sensor.body.addWidget(self.slots)
        self.card_sensor.body.addWidget(Divider())
        self.sensor_row = DecisionRow(
            CheckCode.B2_SENSOR_OK, "test.mark.sensor", "test.mark.sensor_help", self.vm
        )
        self.indicator_row = DecisionRow(
            CheckCode.B2_INDICATOR_OK, "test.mark.indicator", "test.mark.indicator_help", self.vm
        )
        self.card_sensor.body.addWidget(self.sensor_row)
        self.card_sensor.body.addWidget(self.indicator_row)
        self.left_layout.addWidget(self.card_sensor)
        # B3 electrical
        self.card_elec = Card("test.step.electrical", icon="bolt", compact=True)
        self.elec_chip = StatusChip(compact=True)
        self.card_elec.add_trailing(self.elec_chip)
        grid = QGridLayout()
        grid.setHorizontalSpacing(SPACE.l)
        grid.setVerticalSpacing(SPACE.m)
        headers = ("test.col.check", "test.col.measured", "test.col.allowed", "test.col.result")
        aligns = (
            Qt.AlignmentFlag.AlignLeft,
            Qt.AlignmentFlag.AlignRight,
            Qt.AlignmentFlag.AlignHCenter,
            Qt.AlignmentFlag.AlignRight,
        )
        for column, (key, align) in enumerate(zip(headers, aligns, strict=True)):
            header = TrText(key, "label", "tertiary", align=align | Qt.AlignmentFlag.AlignVCenter)
            grid.addWidget(header, 0, column)
        self.cells: dict[CheckCode, ValueRow] = {
            code: ValueRow(grid, row, code.label_key, icon)
            for row, (code, icon) in enumerate(self.ROWS, start=1)
        }
        grid.setColumnStretch(2, 1)
        grid.setColumnMinimumWidth(
            0, max(row.name_box.sizeHint().width() for row in self.cells.values())
        )
        self.card_elec.body.addLayout(grid)
        self.waiting = Text("", "body", "info")
        self.card_elec.body.addWidget(self.waiting)
        self.send_to = Text("", "caption", "secondary")
        self.card_elec.body.addWidget(self.send_to)
        self.card_elec.body.addWidget(Divider())
        ambient = QHBoxLayout()
        ambient.setSpacing(SPACE.s)
        ambient.addWidget(Icon("device_thermostat", SIZES.icon_m, COLORS.text_2))
        self.ambient = Text("", "body_lg")
        ambient.addWidget(self.ambient, 1)
        self.remeasure = AppButton(
            "action.remeasure_ambient", variant="outlined", size="compact", hint_key="key.f9"
        )
        self.remeasure.clicked.connect(controller.remeasure_ambient)
        ambient.addWidget(self.remeasure)
        self.card_elec.body.addLayout(ambient)
        self.right_layout.addWidget(self.card_elec)
        self.finish_columns()
        self.update_view()

    def _band(self, code: CheckCode) -> tuple[Band, str]:
        limits = self.c.settings.limits
        decimals = limits.decimals
        if code is CheckCode.B3_T_REG:
            ambient = self.c.ambient_c
            margin = f"{limits.temp_margin_c:g}"
            if ambient is None:
                return Band(None, None), t("test.allowed_temp_unknown", margin=margin)
            limit = ambient + limits.temp_margin_c
            return Band(None, limit), t("test.allowed_temp", limit=f"{limit:.1f}", margin=margin)
        point = code.value[-1].lower()
        low, high = limits.voltage_range(point)
        caption = t(
            "test.allowed_range", low=f"{low:.{decimals}f}", high=f"{high:.{decimals}f}", unit="V"
        )
        return Band(low, high), caption

    def update_view(self, *_args: object) -> None:
        vm = self.vm
        # B1
        self.comm_chip.set_state(CHIP[vm.comm_state])
        self.comm_text.setText(
            {
                StepState.PENDING: "",
                StepState.WORKING: t("test.comm.working"),
                StepState.PASS: t("test.comm.ok"),
                StepState.FAIL: t("test.comm.fail"),
                StepState.ERROR: t("test.comm.error"),
            }[vm.comm_state]
        )
        self.comm_text.setVisible(True)
        # B2
        total = vm.total_readings
        count = len(vm.readings)
        if any(v is False for v in vm.marks.values()):
            sensor_state = StepState.FAIL
        elif vm.readings_done and vm.marks_ok:
            sensor_state = StepState.PASS
        elif count or vm.reading_busy:
            sensor_state = StepState.WORKING
        else:
            sensor_state = StepState.PENDING
        self.sensor_chip.set_state(CHIP[sensor_state])
        progress = t("test.reading_progress", n=count, total=total)
        unit = vm.readings[0].unit if vm.readings else ""
        self.reading_title.setText(f"{progress}  ·  {unit}" if unit else progress)
        self.slots.set_count(total)
        self.slots.set_readings(
            [(f"{r.value:g}", r.unit, local_time(r.read_at)) for r in vm.readings]
        )
        comm_ok = vm.comm_state is StepState.PASS
        self.sensor_row.update_view(
            comm_ok and vm.readings_done,
            "test.mark.locked_readings" if comm_ok else "test.mark.locked_comm",
            n=total,
        )
        self.indicator_row.update_view(comm_ok, "test.mark.locked_comm")
        # B3
        results: dict[CheckCode, CheckOutcome] = {o.check_code: o for o in vm.results}
        for code, value_row in self.cells.items():
            band, caption = self._band(code)
            outcome = results.get(code)
            if outcome is None or outcome.value_num is None:
                working = vm.measure_state is StepState.WORKING
                value_row.set_value(None, None, band, caption, "working" if working else "neutral")
                continue
            unit = "°C" if code is CheckCode.B3_T_REG else "V"
            if outcome.passed is None:
                state = "neutral"
            else:
                state = "success" if outcome.passed else "danger"
            value_row.set_value(
                f"{outcome.value_num:g} {unit}", outcome.value_num, band, caption, state
            )
        self.elec_chip.set_state(CHIP[vm.measure_state])
        if vm.measure_state is StepState.WORKING:
            self.waiting.setText(t("test.waiting", s=vm.seconds_left))
        elif vm.measure_state is StepState.ERROR:
            self.waiting.setText(t("test.measure_error"))
        else:
            self.waiting.setText("")
        self.waiting.setVisible(bool(self.waiting.text()))
        urls = self._listen_urls() if vm.measure_state is StepState.WORKING else []
        self.send_to.setText(t("test.send_to", url=urls[0]) if urls else "")
        self.send_to.setToolTip("\n".join(urls))
        self.send_to.setVisible(bool(urls))
        self.ambient.setText(
            t("test.ambient", value=f"{self.c.ambient_c:.1f}")
            if self.c.ambient_c is not None
            else t("drawer.ambient_unknown")
        )
        self._render_cards(sensor_state)

    def _listen_urls(self) -> list[str]:
        """Where the real measuring device must send (empty when it is simulated)."""
        hardware = self.c.ctx.hardware
        urls = getattr(hardware, "listen_urls", None)
        if not getattr(hardware, "real_measuring_device", False) or not callable(urls):
            return []
        try:
            return [str(url) for url in urls()]
        except OSError:
            return []

    def _render_cards(self, sensor_state: StepState) -> None:
        """Exactly one active card (S5); a failed step is outlined red."""
        vm = self.vm
        if vm.comm_state is not StepState.PASS:
            active: Card | None = self.card_comm
        elif not (vm.readings_done and vm.marks_ok):
            active = self.card_sensor
        elif vm.measure_state is not StepState.PASS:
            active = self.card_elec
        else:
            active = None
        for card, state in (
            (self.card_comm, vm.comm_state),
            (self.card_sensor, sensor_state),
            (self.card_elec, vm.measure_state),
        ):
            if state is StepState.FAIL:
                card.set_variant("danger")
            elif card is active:
                card.set_variant("active")
            else:
                card.set_variant("default")


# =========================================================================== Labeling


class CameraPreview(CameraFrame):
    """Live camera frames, polled from the hardware service while Labeling is shown."""

    def __init__(self, controller: StationController, vm: LabelingViewModel) -> None:
        super().__init__()
        self.c = controller
        self.vm = vm
        self._timer = QTimer(self)
        self._timer.setInterval(CAMERA_POLL_MS)
        self._timer.timeout.connect(self._poll)
        self._last_qr: str | None = None
        self.setAccessibleName(t("camera.preview"))

    def set_active(self, active: bool) -> None:
        if active and not self._timer.isActive():
            self._timer.start()
        elif not active:
            self._timer.stop()
            self.update()

    def _poll(self) -> None:
        frame = self.c.ctx.hardware.get_preview_frame()
        if frame is not None:
            image = QImage(
                frame.rgb, frame.width, frame.height, frame.width * 3, QImage.Format.Format_RGB888
            )
            self.set_image(image.copy())

    def sync(self) -> None:
        scanning = self.vm.camera_state is StepState.WORKING
        self.set_scanning(scanning)
        if scanning:
            self.set_placeholder(t("camera.scanning"))
        else:
            self.set_placeholder(t("camera.simulated" if self.c.ctx.using_mocks else "camera.idle"))
        if self.vm.qr_id and self.vm.qr_id != self._last_qr:
            self.flash_success()  # a code was read: green flash + corner pulse (L3)
        self._last_qr = self.vm.qr_id


class ChecklistView(StageView):
    vm: ChecklistMixin

    def _build_checklist(self, title_key: str) -> Card:
        card = Card(title_key)
        card.body.setSpacing(SPACE.s)
        self.rows: dict[CheckCode, ChecklistRow] = {}
        for index, code in enumerate(self.vm.checklist, start=1):
            row = ChecklistRow(code.label_key, CHECK_ICONS.get(code, "fact_check"), f"key.f{index}")
            row.clicked.connect(lambda _c=False, code=code: self._clicked(code))
            self.rows[code] = row
            card.body.addWidget(row)
        self.left_layout.addWidget(card)
        self.chooser = RejectChooser(self.vm)
        self.left_layout.addWidget(self.chooser)
        return card

    def _clicked(self, code: CheckCode) -> None:
        self.vm.toggle(code)
        self.update_view()

    def _render_checklist(self) -> None:
        enabled = self.c.device_in_progress
        for code, row in self.rows.items():
            row.setChecked(bool(self.vm.ticks.get(code)))
            row.setEnabled(enabled)


class LabelingView(ChecklistView):
    vm: LabelingViewModel

    def __init__(self, controller: StationController) -> None:
        super().__init__(controller, controller.labeling)
        self._build_checklist("label.checklist_title")
        self.left_layout.addStretch(1)
        # camera + the ID that was read (L1, L3)
        camera_card = Card("label.qr_title", icon="qr_code_scanner", compact=True)
        camera_card.body.setSpacing(SPACE.m)
        self.preview = CameraPreview(controller, self.vm)
        camera_card.body.addWidget(self.preview, 1)
        read = QHBoxLayout()
        read.setSpacing(SPACE.m)
        column = QVBoxLayout()
        column.setSpacing(0)
        column.addWidget(TrText("label.qr_read", "label", "secondary"))
        self.decoded = Text("-", "value_xl")
        column.addWidget(self.decoded)
        read.addLayout(column, 1)
        self.manual_flag = StatusChip("warning", "label.manual_flag", compact=True)
        read.addWidget(self.manual_flag, 0, Qt.AlignmentFlag.AlignBottom)
        camera_card.body.addLayout(read)
        self.right_layout.addWidget(camera_card, 1)
        # typed ID (fallback)
        self.manual = Card("manual.title", icon="badge", compact=True)
        self.manual.set_variant("active")
        fields = QHBoxLayout()
        fields.setSpacing(SPACE.m)
        self.manual_first = TextField("manual.first", max_width=None)
        self.manual_second = TextField("manual.second", max_width=None)
        for field in (self.manual_first, self.manual_second):
            field.setProperty("enter_submits", True)
            field.returnPressed.connect(self._submit_manual)
            fields.addWidget(field)
        self.manual.body.addLayout(fields)
        self.manual_error = Text("", "body", "danger")
        self.manual.body.addWidget(self.manual_error)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.manual_cancel = AppButton("action.cancel", variant="outlined")
        self.manual_ok = AppButton("action.confirm_id", variant="tonal")
        self.manual_ok.clicked.connect(self._submit_manual)
        self.manual_cancel.clicked.connect(self.vm.cancel_manual)
        buttons.addWidget(self.manual_cancel)
        buttons.addWidget(self.manual_ok)
        self.manual.body.addLayout(buttons)
        self.manual.setVisible(False)
        self.right_layout.addWidget(self.manual)
        # identity: before -> now (L2)
        self.identity = Card("label.identity_title", icon="badge", compact=True)
        self.identity_pill = StatusChip()
        self.identity.add_trailing(self.identity_pill)
        rows = QGridLayout()
        rows.setHorizontalSpacing(SPACE.l)
        rows.setVerticalSpacing(SPACE.xs)
        self.board_label = TrText("label.board_id", "label", "secondary")
        self.qr_label = TrText("label.qr_id", "label", "secondary")
        self.board_value = Text("-", "mono_title")
        self.qr_value = Text("-", "mono_title")
        self.arrow = Icon("arrow_forward", SIZES.icon_m, COLORS.text_3)
        policy = self.arrow.sizePolicy()
        policy.setRetainSizeWhenHidden(True)
        self.arrow.setSizePolicy(policy)
        rows.addWidget(self.board_label, 0, 0)
        rows.addWidget(self.board_value, 1, 0)
        rows.addWidget(self.arrow, 1, 1)
        rows.addWidget(self.qr_label, 0, 2)
        rows.addWidget(self.qr_value, 1, 2)
        rows.setColumnStretch(0, 1)
        rows.setColumnStretch(2, 1)
        self.identity.body.addLayout(rows)
        self.right_layout.addWidget(self.identity)
        controller.stage_changed.connect(self._stage_changed)
        self.update_view()

    def _stage_changed(self) -> None:
        self.preview.set_active(self.c.stage is Stage.LABELING and self.c.reject is None)

    def _submit_manual(self) -> None:
        self.vm.submit_manual(self.manual_first.text(), self.manual_second.text())

    def update_view(self, *_args: object) -> None:
        vm = self.vm
        self._render_checklist()
        self.preview.set_active(self.c.stage is Stage.LABELING and self.c.reject is None)
        self.preview.sync()
        self.decoded.setText(vm.qr_id or "-")
        self.decoded.set_tone("primary" if vm.qr_id else "tertiary")
        self.manual_flag.setVisible(vm.qr_id is not None and vm.method is IdEntryMethod.MANUAL)
        was_hidden = self.manual.isHidden()
        self.manual.setVisible(vm.manual_mode)
        if vm.manual_mode and was_hidden:
            self.manual_first.clear()
            self.manual_second.clear()
            self.manual_first.setFocus()
        for field, key in (
            (self.manual_first, "manual.first"),
            (self.manual_second, "manual.second"),
        ):
            field.setAccessibleName(t(key))
            field.set_invalid(vm.manual_error_key is not None)
        self.manual_error.setText(t(vm.manual_error_key) if vm.manual_error_key else "")
        self.manual_error.setVisible(bool(vm.manual_error_key))
        self._render_identity()
        self.chooser.update_view()

    def _render_identity(self) -> None:
        vm = self.vm
        identity = vm.identity
        rewritten = vm.board_id_before is not None and identity in (
            IdentityStatus.WRITE_REQUIRED,
            IdentityStatus.CONFIRMED,
            IdentityStatus.FAILED,
        )
        if rewritten:
            self.board_label.set_key("label.before")
            self.board_value.setText(vm.board_id_before or "-")
            self.board_value.set_strike(True)
            self.board_value.set_tone("tertiary")
            self.qr_label.set_key("label.now")
            now = vm.qr_id if identity is IdentityStatus.WRITE_REQUIRED else vm.board_id
            self.qr_value.setText(now or "-")
            self.qr_value.set_tone("danger" if identity is IdentityStatus.FAILED else "primary")
        else:
            self.board_label.set_key("label.board_id")
            self.board_value.setText(vm.board_id or "-")
            self.board_value.set_strike(False)
            self.board_value.set_tone("primary" if vm.board_id else "tertiary")
            self.qr_label.set_key("label.qr_id")
            self.qr_value.setText(vm.qr_id or "-")
            self.qr_value.set_tone("primary" if vm.qr_id else "tertiary")
        self.arrow.setVisible(rewritten)
        pill = self.identity_pill
        if identity is None:
            if vm.identity_state is StepState.WORKING:
                pill.set_state("working", "label.reading_board")
            elif vm.identity_state is StepState.ERROR:
                pill.set_state("warning", "identity.failed")
            else:
                pill.set_state("neutral")
        elif identity is IdentityStatus.WRITE_REQUIRED:
            state = "warning" if vm.identity_state is StepState.ERROR else "working"
            pill.set_state(state, identity.label_key)
        elif identity is IdentityStatus.FAILED:
            pill.set_state("danger", identity.label_key)
        else:
            pill.set_state("success", identity.label_key)
        variants = {"success": "success", "danger": "danger"}
        self.identity.set_variant(variants.get(pill.state(), "default"))


# =========================================================================== Packaging


class PackagingView(ChecklistView):
    vm: PackagingViewModel

    STAGES = (
        (Stage.PROGRAMMING, "pack.detail.programming"),
        (Stage.TESTING, "pack.detail.testing"),
        (Stage.LABELING, "pack.detail.labeling"),
        (Stage.PACKAGING, "pack.detail.packaging"),
    )

    def __init__(self, controller: StationController) -> None:
        super().__init__(controller, controller.packaging)
        self._build_checklist("pack.checklist_title")
        self.left_layout.addStretch(1)
        summary = Card("pack.summary_title", icon="inventory_2")
        self.device = Text("-", "value_xl")
        self.mac = Text("", "mono_label", "secondary")
        summary.body.addWidget(self.device)
        summary.body.addWidget(self.mac)
        summary.body.addWidget(Divider())
        self.stage_rows: list[tuple[Icon, Text]] = []
        for stage, _key in self.STAGES:
            row = QHBoxLayout()
            row.setSpacing(SPACE.m)
            done = Icon("check_circle", SIZES.icon_m, COLORS.success, filled=True)
            name = TrText(stage.label_key, "body_lg_strong")
            name.setFixedWidth(name.sizeHint().width())
            detail = Text("", "body", "secondary")
            row.addWidget(done)
            row.addWidget(name)
            row.addWidget(detail, 1)
            summary.body.addLayout(row)
            self.stage_rows.append((done, detail))
        self.right_layout.addWidget(summary)
        self.right_layout.addStretch(1)
        controller.device_changed.connect(self.update_view)
        self.update_view()

    def update_view(self, *_args: object) -> None:
        self._render_checklist()
        state = self.c.device
        self.device.setText((state.device_id or state.mac_address) if state else "-")
        self.mac.setText(state.mac_address if state else "")
        firmware = self.c.firmware
        checks = len(self.c.ctx.workflow.required_checks(Stage.TESTING)) if state else 0
        ticked = len(self.vm.checklist) - len(self.vm.missing_ticks)
        details = (
            t("pack.detail.programming", version=firmware.version if firmware else "-"),
            t("pack.detail.testing", n=checks),
            t("pack.detail.labeling", id=(state.device_id or "-") if state else "-"),
            t("pack.detail.packaging", n=ticked, total=len(self.vm.checklist)),
        )
        complete = not self.vm.missing_ticks
        for index, ((icon, detail), text) in enumerate(zip(self.stage_rows, details, strict=True)):
            detail.setText(text)
            done = index < len(self.stage_rows) - 1 or complete
            icon.set_icon(
                "check_circle" if done else "schedule",
                COLORS.success if done else COLORS.info,
                filled=done,
            )
        self.chooser.update_view()
