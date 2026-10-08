"""Component gallery: every component in every state, in English and Marathi.

    python -m parkomate --gallery            # interactive window (language switch on top)
    python -m parkomate.ui.gallery --out docs/design   # gallery_en.png + gallery_mr.png
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QImage
from PySide6.QtWidgets import (
    QApplication,
    QGridLayout,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)

from parkomate.core.enums import CheckCode, Stage
from parkomate.core.errors import ErrorCode, ParkomateError
from parkomate.core.models import RejectInstruction
from parkomate.i18n import set_language
from parkomate.ui.components.base import Divider
from parkomate.ui.components.buttons import AppButton, IconButton
from parkomate.ui.components.camera import CameraFrame
from parkomate.ui.components.cards import Banner, Card, EmptyState, InlineConfirm, InlineMessage, KpiTile
from parkomate.ui.components.checklist import ChecklistRow
from parkomate.ui.components.chips import CounterChips, KeyCap, SimulationChip, StatusChip
from parkomate.ui.components.data import ChipDelegate, DataTable, StackedBar
from parkomate.ui.components.inputs import (
    ROLE_SECONDARY,
    ROLE_SHORT,
    DateRangePicker,
    DecimalField,
    FormField,
    IntField,
    PasswordField,
    Select,
    Switch,
    TextField,
)
from parkomate.ui.components.layout import ScrollArea
from parkomate.ui.components.measure import Band, ReadingSlots, ValueRow
from parkomate.ui.components.overlays import ErrorBanner, RejectTakeover, Toast
from parkomate.ui.components.popup import MenuItem
from parkomate.ui.components.progress import ProgressBar, ProgressRing, Spinner
from parkomate.ui.components.segmented import LanguageSwitch, PassFailToggle, SegmentedControl
from parkomate.ui.components.shellparts import AccountButton, ContextBar, ProductMark, SimulationBand
from parkomate.ui.components.stepper import Stepper, StepList
from parkomate.ui.components.tabs import Tabs
from parkomate.ui.components.text import Text, TrText
from parkomate.ui.theme.tokens import COLORS, SIZES, SPACE

SAMPLE_ID = "PKM-000519"
SAMPLE_MAC = "24:6F:28:03:9F:31"
SAMPLE_NAME = "Asha Patil"
SAMPLE_CODE = "ADM1"
SAMPLE_PORT = "COM4"
SAMPLE_PORT_SHORT = "COM4 · CP210x"
SAMPLE_PORT_LONG = "Silicon Labs CP210x USB to UART Bridge (10C4:EA60)"
SAMPLE_PORT_2 = "COM7"
SAMPLE_PORT_2_LONG = "USB Serial Device (303A:1001)"
TYPE_STYLES = ("display", "headline", "title", "body_lg", "body", "label", "caption", "value_xl")


def _row(*widgets: QWidget, spacing: int = SPACE.m) -> QHBoxLayout:
    row = QHBoxLayout()
    row.setSpacing(spacing)
    for widget in widgets:
        row.addWidget(widget)
    row.addStretch(1)
    return row


class Gallery(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("Page")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        bar = QHBoxLayout()
        bar.setContentsMargins(SPACE.xl, SPACE.l, SPACE.xl, SPACE.l)
        bar.addWidget(ProductMark())
        bar.addSpacing(SPACE.m)
        bar.addWidget(TrText("gallery.title", "headline"))
        bar.addStretch(1)
        self.language = LanguageSwitch()
        self.language.language_selected.connect(set_language)
        bar.addWidget(self.language)
        outer.addLayout(bar)
        self.scroll = ScrollArea()
        outer.addWidget(self.scroll, 1)
        self.body = QWidget()
        self.body.setObjectName("Page")
        self.columns = QHBoxLayout(self.body)
        self.columns.setContentsMargins(SPACE.xl, 0, SPACE.xl, SPACE.xl)
        self.columns.setSpacing(SPACE.l)
        self.left = QVBoxLayout()
        self.right = QVBoxLayout()
        for column in (self.left, self.right):
            column.setSpacing(SPACE.l)
            self.columns.addLayout(column, 1)
        self.scroll.layout_.addWidget(self.body)
        self._build()
        self.left.addStretch(1)
        self.right.addStretch(1)

    def section(self, key: str, build: Callable[[QVBoxLayout], None], *, right: bool = False) -> None:
        card = Card(key)
        build(card.body)
        (self.right if right else self.left).addWidget(card)

    # ------------------------------------------------------------------ sections
    def _build(self) -> None:
        self.section("gallery.type", self._type)
        self.section("gallery.colors", self._colors)
        self.section("gallery.buttons", self._buttons)
        self.section("gallery.chips", self._chips)
        self.section("gallery.segmented", self._segmented)
        self.section("gallery.stepper", self._stepper)
        self.section("gallery.inputs", self._inputs)
        self.section("gallery.checklist", self._checklist)
        self.section("gallery.banners", self._banners, right=True)
        self.section("gallery.cards", self._cards, right=True)
        self.section("gallery.measure", self._measure, right=True)
        self.section("gallery.progress", self._progress, right=True)
        self.section("gallery.data", self._data, right=True)
        self.section("gallery.shell", self._shell, right=True)
        self.section("gallery.overlays", self._overlays, right=True)

    def _type(self, body: QVBoxLayout) -> None:
        for name in TYPE_STYLES:
            line = QHBoxLayout()
            caption = Text(name, "mono_label", "tertiary")
            caption.setFixedWidth(SIZES.number_field)
            line.addWidget(caption)
            sample = TrText("gallery.sample", name)
            if name == "value_xl":
                sample = Text(SAMPLE_ID, name)
            line.addWidget(sample, 1)
            body.addLayout(line)

    def _colors(self, body: QVBoxLayout) -> None:
        grid = QGridLayout()
        grid.setSpacing(SPACE.s)
        names = (
            "bg", "surface", "surface_2", "outline", "text", "text_2", "text_3", "primary",
            "primary_cont", "success", "success_cont", "danger", "danger_cont", "warning",
            "warning_cont", "takeover",
        )
        for index, name in enumerate(names):
            swatch = _Swatch(getattr(COLORS, name), name)
            grid.addWidget(swatch, index // 4, index % 4)
        body.addLayout(grid)

    def _buttons(self, body: QVBoxLayout) -> None:
        body.addLayout(_row(
            AppButton("action.upload_firmware", variant="filled", hint_key="key.enter"),
            AppButton("action.reject_device", variant="danger_tonal"),
        ))
        body.addLayout(_row(
            AppButton("action.refresh_ports", variant="outlined", icon="refresh", hint_key="key.f5"),
            AppButton("action.adjust_yes", variant="tonal"),
            AppButton("action.details_for_support", variant="text", size="compact"),
        ))
        disabled = AppButton("action.submit_next", variant="filled", hint_key="key.enter")
        disabled.setEnabled(False)
        loading = AppButton("action.upload_firmware", variant="filled")
        loading.set_loading(True)
        loading.setEnabled(False)
        body.addLayout(_row(disabled, loading))
        body.addLayout(_row(
            AppButton("action.complete_device", variant="success_filled", hint_key="key.enter"),
            AppButton("action.end_session", variant="danger_filled", size="compact"),
            IconButton("refresh", "action.refresh"),
        ))

    def _chips(self, body: QVBoxLayout) -> None:
        body.addLayout(_row(*(StatusChip(s) for s in ("success", "danger", "warning", "info", "working", "neutral"))))
        body.addLayout(_row(*(StatusChip(s, compact=True) for s in ("success", "danger", "warning", "working", "neutral"))))
        sim = SimulationChip()
        sim.set_scenario("upload_fails_then_succeeds")
        counters = CounterChips()
        counters.set_counts(12, 1, 11, 2)
        body.addLayout(_row(sim, KeyCap("key.enter"), KeyCap("key.f1")))
        body.addLayout(_row(counters))

    def _segmented(self, body: QVBoxLayout) -> None:
        language = LanguageSwitch()
        formats = SegmentedControl([("xlsx", "admin.rep.format_xlsx"), ("csv", "admin.rep.format_csv"), ("both", "admin.rep.format_both")])
        formats.set_value("csv", animate=False)
        body.addLayout(_row(language, formats))
        neutral = PassFailToggle()
        success = PassFailToggle()
        success.success.setChecked(True)
        success.success.setEnabled(False)
        success.failure.setEnabled(False)
        failure = PassFailToggle()
        failure.failure.setChecked(True)
        failure.success.setEnabled(False)
        failure.failure.setEnabled(False)
        locked = PassFailToggle()
        locked.success.setEnabled(False)
        locked.failure.setEnabled(False)
        locked.set_locked("test.mark.locked_readings")
        body.addLayout(_row(neutral, success))
        body.addLayout(_row(failure, locked))

    def _stepper(self, body: QVBoxLayout) -> None:
        keys = [s.label_key for s in (Stage.PROGRAMMING, Stage.TESTING, Stage.LABELING, Stage.PACKAGING)]
        for states in (
            ["active", "upcoming", "upcoming", "upcoming"],
            ["done", "done", "active", "upcoming"],
            ["done", "rejected", "upcoming", "upcoming"],
        ):
            stepper = Stepper(keys)
            stepper.set_states(states)
            body.addWidget(stepper)
        steps = StepList(["prog.step.connect", "prog.step.authorised", "prog.step.firmware", "prog.step.upload"])
        for item, (state, caption) in zip(steps.items, (
            ("pass", "status.word.pass"), ("working", "prog.whitelist.checking"),
            ("error", "prog.firmware.error"), ("pending", None),
        ), strict=True):
            item.set_state(state, caption)
        body.addWidget(steps)

    def _inputs(self, body: QVBoxLayout) -> None:
        text = TextField("login.operator_id_hint")
        invalid = TextField("login.operator_id_hint")
        invalid.set_invalid(True)
        disabled = TextField("login.operator_id_hint")
        disabled.setEnabled(False)
        body.addWidget(FormField("login.operator_id", text))
        body.addWidget(FormField("login.password", PasswordField("login.password_hint")))
        field = FormField("login.operator_id", invalid)
        field.set_error(t_value("settings.err.email_incomplete"))
        body.addWidget(field)
        decimal = DecimalField("unit.v")
        decimal.setValue(3.25)
        integer = IntField("unit.days")
        integer.setValue(90)
        body.addLayout(_row(decimal, integer, Switch(), _checked_switch(), disabled))
        select = Select()
        select.addItem(SAMPLE_PORT_LONG, SAMPLE_PORT)
        select.setItemData(0, SAMPLE_PORT_SHORT, ROLE_SHORT)
        select.setItemData(0, SAMPLE_PORT_LONG, ROLE_SECONDARY)
        select.addItem(SAMPLE_PORT_2_LONG, SAMPLE_PORT_2)
        today = QDate.currentDate()
        body.addLayout(_row(select, DateRangePicker(today.addDays(-6), today)))

    def _checklist(self, body: QVBoxLayout) -> None:
        unchecked = ChecklistRow("check.C1", "developer_board", "key.f1")
        checked = ChecklistRow("check.C2", "build", "key.f2")
        checked.setChecked(True)
        disabled = ChecklistRow("check.C3", "label", "key.f3")
        disabled.setEnabled(False)
        for row in (unchecked, checked, disabled):
            body.addWidget(row)

    def _banners(self, body: QVBoxLayout) -> None:
        for tone, title, text in (
            ("info", "notice.recovered_title", "prog.adjust.help"),
            ("success", "end.sent", "end.saved_local"),
            ("warning", "notice.abandoned_title", "end.saved_retry"),
        ):
            banner = Banner(tone)
            banner.set_texts(t_value(title), t_value(text))
            body.addWidget(banner)
        error = ErrorBanner()
        error.show_error(ParkomateError("x", code=ErrorCode.MEAS_TIMEOUT, params={"seconds": 30}), has_retry=True, retry_key="action.measure_again")
        body.addWidget(error)
        confirm = InlineConfirm()
        confirm.show_confirm(t_value("confirm.reset_counters"), "action.reset_counters", "action.cancel", True)
        body.addWidget(confirm)
        messages = QHBoxLayout()
        for kind in ("ok", "fail", "info"):
            message = InlineMessage()
            if kind == "ok":
                message.ok(t_value("admin.cnt.reset_done"))
            elif kind == "fail":
                message.fail(ParkomateError("x", code=ErrorCode.SETTINGS_INVALID))
            else:
                message.info(t_value("settings.no_changes"))
            messages.addWidget(message)
        body.addLayout(messages)

    def _cards(self, body: QVBoxLayout) -> None:
        row = QHBoxLayout()
        row.setSpacing(SPACE.m)
        for variant in ("default", "active", "success", "danger", "flat"):
            card = Card("gallery.card", compact=True)
            card.set_variant(variant)
            card.body.addWidget(Text(variant, "mono_label", "secondary"))
            row.addWidget(card)
        body.addLayout(row)
        tiles = QHBoxLayout()
        for key, icon, value in (
            ("end.devices", "memory", "14"), ("end.complete", "task_alt", "11"),
            ("end.rejected", "block", "3"), ("end.yield", "monitoring", "78.6 %"),
        ):
            tile = KpiTile(key, icon)
            tile.set_value(value)
            tiles.addWidget(tile)
        body.addLayout(tiles)
        bar = StackedBar()
        bar.set_segments([("A", 1, COLORS.reject_a), ("B", 1, COLORS.reject_b), ("C", 1, COLORS.reject_c), ("D", 0, COLORS.reject_d)])
        body.addWidget(bar)
        body.addWidget(EmptyState("inbox", "admin.out.empty_title", "admin.out.empty_body"))

    def _measure(self, body: QVBoxLayout) -> None:
        grid = QGridLayout()
        grid.setHorizontalSpacing(SPACE.l)
        grid.setVerticalSpacing(SPACE.m)
        rows = (
            ("check.B3_V_A", "bolt", "24.01 V", 24.01, Band(23.85, 24.15), "23.85 – 24.15 V", "pass"),
            ("check.B3_V_C", "bolt", "3.21 V", 3.21, Band(3.25, 3.35), "3.25 – 3.35 V", "fail"),
            ("check.B3_T_REG", "device_thermostat", "28.4 °C", 28.4, Band(None, 30.1), "≤ 30.1 °C", "pass"),
            ("check.B3_V_B", "bolt", None, None, Band(4.9, 5.1), "4.90 – 5.10 V", "working"),
        )
        for index, (key, icon, shown, value, band, caption, state) in enumerate(rows):
            row = ValueRow(grid, index, key, icon)
            row.set_value(shown, value, band, caption, state)
        body.addLayout(grid)
        slots = ReadingSlots(5)
        slots.set_readings([("152.3", "cm", "10:41:02"), ("149.8", "cm", "10:41:05"), ("151.0", "cm", "10:41:08")])
        body.addWidget(slots)

    def _progress(self, body: QVBoxLayout) -> None:
        for state, value in (("running", 56), ("success", 100), ("danger", 72)):
            bar = ProgressBar()
            bar.set_state(state)
            bar.set_value(value, animate=False)
            body.addWidget(bar)
        rings = QHBoxLayout()
        for state, value in (("running", 56), ("success", 100), ("danger", 72)):
            ring = ProgressRing()
            ring.set_state(state)
            ring.set_value(value)
            rings.addWidget(ring)
        rings.addWidget(Spinner())
        rings.addStretch(1)
        body.addLayout(rings)

    def _data(self, body: QVBoxLayout) -> None:
        tabs = Tabs()
        for key in ("admin.tab.settings", "admin.tab.operators", "admin.tab.reports", "admin.tab.counters", "admin.tab.errors"):
            tabs.add_tab(QWidget(), key)
        tabs.setFixedHeight(SIZES.tab + SPACE.xs)
        body.addWidget(tabs)
        table = DataTable(("admin.log.time", "admin.log.level", "admin.log.code", "admin.log.message"), mono=(2,), empty=("task_alt", "admin.log.empty_title", "admin.log.empty_body"))
        table.setItemDelegateForColumn(1, ChipDelegate({"ERROR": "danger", "WARNING": "warning", "CRITICAL": "danger", "INFO": "info"}, table))
        table.fill([["2026-10-08 10:41", "ERROR", "MAIL_FAILED", "mail broke"], ["2026-10-08 10:12", "WARNING", "MEAS_TIMEOUT", "no measurement"]])
        table.setFixedHeight(SIZES.table_row * 4)
        body.addWidget(table)
        empty = DataTable(("admin.out.id", "admin.out.created", "admin.out.subject"), empty=("inbox", "admin.out.empty_title", "admin.out.empty_body"))
        empty.setFixedHeight(SIZES.table_row * 6)
        body.addWidget(empty)

    def _shell(self, body: QVBoxLayout) -> None:
        body.addWidget(SimulationBand())
        context = ContextBar()
        context.device.set_device(SAMPLE_ID, SAMPLE_MAC)
        context.set_operator(SAMPLE_NAME, SAMPLE_CODE)
        context.set_elapsed("01:12:09")
        context.counters.set_counts(12, 1, 11, 2)
        body.addWidget(context)
        account = AccountButton()
        account.set_name(SAMPLE_NAME)
        body.addLayout(_row(ProductMark(), ProductMark(SIZES.mark_large), account))
        menu = Card(compact=True)
        menu.body.setSpacing(0)
        for key, icon in (("menu.session", "history"), ("action.admin", "admin_panel_settings"), ("action.logout", "logout")):
            item = MenuItem(key, icon, danger=key == "action.logout")
            menu.body.addWidget(item)
        admin = menu.body.itemAt(1).widget()
        admin.setEnabled(False)
        admin.set_reason("gate.admin_device_busy")  # type: ignore[attr-defined]
        menu.setMaximumWidth(SIZES.drawer)
        body.addWidget(menu)
        camera = CameraFrame()
        camera.set_placeholder(t_value("camera.simulated"))
        camera.set_scanning(True)
        camera.setFixedHeight(SIZES.camera_min_height)
        body.addWidget(camera)

    def _overlays(self, body: QVBoxLayout) -> None:
        host = QWidget()
        host.setFixedHeight(SIZES.min_window_height - SIZES.app_bar)
        takeover = RejectTakeover(host)
        takeover.show_instruction(RejectInstruction(
            device_row_id=0, stage=Stage.TESTING, check_code=CheckCode.B3_V_C,
            reason_key="reject.reason.out_of_range",
            reason_params={"check_key": "check.B3_V_C", "value": "3.21", "unit": "V", "low": "3.25", "high": "3.35"},
        ))
        body.addWidget(host)
        toast_host = QWidget()
        toast_host.setFixedHeight(SIZES.toast + 2 * SPACE.xl)
        toast = Toast(toast_host)
        toast.show_message(SAMPLE_ID, 3600)
        body.addWidget(toast_host)
        body.addWidget(Divider())


class _Swatch(QWidget):
    def __init__(self, color: str, name: str) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACE.xs)
        block = Card(compact=True)
        block.setFixedHeight(SIZES.button_compact)
        block.paintEvent = lambda _e, b=block, c=color: _paint_swatch(b, c)  # type: ignore[method-assign]
        layout.addWidget(block)
        layout.addWidget(Text(name, "caption", "secondary"))
        layout.addWidget(Text(color, "mono_label", "tertiary"))


def _paint_swatch(widget: QWidget, color: str) -> None:
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QPainter

    from parkomate.ui.components.base import fill_rounded
    from parkomate.ui.theme.tokens import RADIUS

    painter = QPainter(widget)
    fill_rounded(painter, QRectF(widget.rect()), RADIUS.chip, color, COLORS.outline, SIZES.hairline)
    painter.end()


def _checked_switch() -> Switch:
    switch = Switch()
    switch.setChecked(True)
    return switch


def t_value(key: str) -> str:
    from parkomate.i18n import t

    return t(key)


def capture_gallery(out: Path, languages: list[str]) -> list[Path]:
    from parkomate.ui.theme import motion

    motion.force(False)
    written = []
    for language in languages:
        set_language(language)
        gallery = Gallery()
        gallery.language.sync(language)
        gallery.resize(SIZES.content_max, SIZES.min_window_height)
        gallery.show()
        QApplication.processEvents()
        body = gallery.body
        body.adjustSize()
        width = max(SIZES.content_max, body.sizeHint().width())
        height = body.heightForWidth(width) if body.hasHeightForWidth() else -1
        height = max(height, body.sizeHint().height())
        body.resize(width, height)
        QApplication.processEvents()
        height = max(height, body.layout().totalHeightForWidth(width))
        body.resize(width, height)
        QApplication.processEvents()
        image = QImage(width, height, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        body.render(image)
        path = out / f"gallery_{language}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        image.save(str(path))
        written.append(path)
        gallery.close()
        gallery.deleteLater()
    set_language("en")
    motion.force(None)
    return written


def run_gallery() -> int:
    from parkomate.ui.main import create_application

    app = create_application()
    gallery = Gallery()
    gallery.resize(SIZES.content_max, SIZES.min_window_height)
    gallery.showMaximized()
    return app.exec()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render the component gallery to PNG")
    parser.add_argument("--out", type=Path, default=Path("docs/design"))
    parser.add_argument("--lang", nargs="+", default=["en", "mr"])
    args = parser.parse_args(argv)
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from parkomate.ui.main import create_application

    create_application()
    for path in capture_gallery(args.out, args.lang):
        sys.stdout.write(f"{path}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
