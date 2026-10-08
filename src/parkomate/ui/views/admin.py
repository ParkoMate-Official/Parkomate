"""Admin area (role-gated): settings, operators, reports + e-mail outbox, counters, error log.

Page header (back button + 'Admin'), Material tabs, each tab built from cards on the page
background (A1-A7).
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, time, timedelta
from typing import Any, ClassVar, Literal, cast, get_args, get_origin

from pydantic import BaseModel
from PySide6.QtCore import QDate, QEvent, QRectF, QSize, Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QEnterEvent, QPainter, QPaintEvent, QResizeEvent
from PySide6.QtWidgets import (
    QAbstractButton,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QHBoxLayout,
    QLineEdit,
    QPlainTextEdit,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from parkomate.config.settings import Settings
from parkomate.core.enums import OutboxStatus, Role
from parkomate.core.errors import ErrorCode, ParkomateError, SettingsError
from parkomate.core.models import Operator
from parkomate.i18n import LANGUAGES, t, translator
from parkomate.logging_setup import read_error_log
from parkomate.ui.components.base import draw_line, fill_rounded, qcolor, set_prop
from parkomate.ui.components.buttons import AppButton
from parkomate.ui.components.cards import Card, InlineConfirm, InlineMessage, KpiTile
from parkomate.ui.components.data import ChipDelegate, DataTable
from parkomate.ui.components.inputs import (
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
from parkomate.ui.components.segmented import SegmentedControl
from parkomate.ui.components.tabs import Tabs
from parkomate.ui.components.text import Text, TrText
from parkomate.ui.qt_i18n import language_notifier
from parkomate.ui.theme import motion
from parkomate.ui.theme.fonts import font_for
from parkomate.ui.theme.tokens import ALPHA, COLORS, RADIUS, SIZES, SPACE, TYPE
from parkomate.ui.viewmodels.station import StationController

log = logging.getLogger(__name__)

Editor = QCheckBox | QSpinBox | QDoubleSpinBox | QComboBox | QLineEdit
ExportFormat = Literal["xlsx", "csv", "both"]

# Section order of the settings form (and of its section index).
SECTION_ORDER = (
    "general",
    "station",
    "limits",
    "timeouts",
    "server",
    "measurement",
    "camera",
    "email",
    "reports",
    "programming",
    "serial",
    "workflow",
    "auth",
    "ui",
    "logging",
    "dev",
)
# Fields shown as one range row: "Point A voltage  [23.850 V] – [24.150 V]" (A2).
RANGES = {
    "limits.v_a_low": ("limits.v_a_high", "check.B3_V_A"),
    "limits.v_b_low": ("limits.v_b_high", "check.B3_V_B"),
    "limits.v_c_low": ("limits.v_c_high", "check.B3_V_C"),
}
RANGE_HIGHS = {high for high, _label in RANGES.values()}


def unit_key(dotted: str) -> str | None:
    """The unit suffix of a numeric setting."""
    name = dotted.rsplit(".", 1)[-1]
    if dotted.startswith("limits.v_"):
        return "unit.v"
    if name == "temp_margin_c":
        return "unit.c"
    if name.endswith("_days"):
        return "unit.days"
    if name.endswith("_minutes"):
        return "unit.minutes"
    if name.endswith("_s"):
        return "unit.s"
    if name in ("baud", "flash_baud"):
        return "unit.baud"
    if name == "fps":
        return "unit.fps"
    if dotted in ("camera.width", "camera.height"):
        return "unit.px"
    if name == "max_bytes":
        return "unit.bytes"
    return None


def settings_issue_text(issue: Any) -> str:
    """Translated text for a ``SettingsIssue`` (falls back to the English detail)."""
    key = f"settings.err.{issue.type}"
    if translator().has(key, "en"):
        params = {k: v for k, v in issue.ctx.items() if not isinstance(v, list | dict)}
        return t(key, **params)
    return t("settings.err.generic", detail=issue.message)


def _local(value: datetime | None) -> str:
    return "" if value is None else value.astimezone().strftime("%Y-%m-%d %H:%M")


# Kept under its old name: a one-line outcome message with an icon.
ResultLine = InlineMessage


def _tab_scroll() -> tuple[ScrollArea, QVBoxLayout]:
    scroll = ScrollArea()
    layout = scroll.layout_
    layout.setContentsMargins(0, SPACE.l, 0, SPACE.l)
    return scroll, layout


# =========================================================================== settings


class _EditedDot(QWidget):
    """Small primary dot next to a field that was changed but not saved yet (A2)."""

    def __init__(self) -> None:
        super().__init__()
        self.setFixedSize(SIZES.edited_dot, SIZES.edited_dot)
        policy = self.sizePolicy()
        policy.setRetainSizeWhenHidden(True)
        self.setSizePolicy(policy)
        self.setVisible(False)

    def paintEvent(self, _event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(COLORS.primary))
        painter.drawEllipse(QRectF(self.rect()))
        painter.end()


class _FieldRow(QWidget):
    """Label (left) | editor(s) + edited dot | error below the editor."""

    def __init__(
        self,
        label: Text,
        editors: Sequence[QWidget],
        dots: Sequence[_EditedDot],
        errors: Sequence[Text],
    ) -> None:
        super().__init__()
        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(SPACE.l)
        grid.setVerticalSpacing(SPACE.xs)
        label.setWordWrap(True)
        label.setFixedWidth(SIZES.section_index)
        grid.addWidget(label, 0, 0, Qt.AlignmentFlag.AlignVCenter)
        row = QHBoxLayout()
        row.setSpacing(SPACE.s)
        for index, editor in enumerate(editors):
            if index:
                row.addWidget(Text("–", "body_lg", "secondary"))
            row.addWidget(editor)
            row.addWidget(dots[index])
        row.addStretch(1)
        grid.addLayout(row, 0, 1)
        column = QVBoxLayout()
        column.setSpacing(0)
        for error in errors:
            column.addWidget(error)
        grid.addLayout(column, 1, 1)
        grid.setColumnStretch(1, 1)


class _IndexItem(QAbstractButton):
    def __init__(self, key: str) -> None:
        super().__init__()
        self.key = key
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setProperty("ring_radius", RADIUS.pill)
        self.setFixedHeight(SIZES.button_compact)
        language_notifier().changed.connect(self.retranslate)
        self.retranslate()

    def retranslate(self, *_args: object) -> None:
        self.setText(t(self.key))
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(SIZES.section_index, SIZES.button_compact)

    def enterEvent(self, event: QEnterEvent) -> None:
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent) -> None:
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, _event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())
        if self.isChecked():
            fill_rounded(painter, rect, RADIUS.pill, COLORS.primary_cont)
        elif self.underMouse():
            fill_rounded(painter, rect, RADIUS.pill, qcolor(COLORS.text, ALPHA.hover))
        draw_line(
            painter,
            rect.adjusted(SPACE.l, 0, -SPACE.l, 0),
            self.text(),
            TYPE.body_strong if self.isChecked() else TYPE.body,
            COLORS.on_primary_cont if self.isChecked() else COLORS.text_2,
        )
        painter.end()


class _SectionIndex(QWidget):
    """Left index of the settings sections; scrolls the form to a section (A2)."""

    def __init__(self, sections: Sequence[str], on_select: Callable[[str], None]) -> None:
        super().__init__()
        self.setFixedWidth(SIZES.section_index)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, SPACE.l, 0, SPACE.l)
        layout.setSpacing(SPACE.xs)
        self.items: dict[str, _IndexItem] = {}
        for section in sections:
            item = _IndexItem(f"settings.section.{section}")
            item.clicked.connect(lambda _c=False, s=section: on_select(s))
            self.items[section] = item
            layout.addWidget(item)
        layout.addStretch(1)

    def set_current(self, section: str) -> None:
        for name, item in self.items.items():
            item.setChecked(name == section)


class _SaveBar(QWidget):
    def paintEvent(self, _event: QPaintEvent) -> None:
        painter = QPainter(self)
        rect = self.rect()
        painter.fillRect(QRectF(0, 0, rect.width(), SIZES.hairline), QColor(COLORS.outline_soft))
        painter.end()


class SettingsTab(QWidget):
    def __init__(self, controller: StationController) -> None:
        super().__init__()
        self.c = controller
        self.editors: dict[str, Editor] = {}
        self.errors: dict[str, Text] = {}
        self.labels: dict[str, Text] = {}
        self.dots: dict[str, _EditedDot] = {}
        self.groups: dict[str, Card] = {}
        self._rows: dict[str, list[_FieldRow]] = {}
        self._grids: dict[str, QGridLayout] = {}
        self._loaded: dict[str, Any] = {}
        self._columns = 0
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        body = QHBoxLayout()
        body.setSpacing(SPACE.xl)
        self.index = _SectionIndex([*SECTION_ORDER, "secrets"], self.scroll_to)
        body.addWidget(self.index, 0, Qt.AlignmentFlag.AlignTop)
        self.form_scroll, self.form_layout = _tab_scroll()
        self.form_scroll.verticalScrollBar().valueChanged.connect(self._sync_index)
        body.addWidget(self.form_scroll, 1)
        outer.addLayout(body, 1)
        self._build()
        self._build_secrets()
        self.form_layout.addStretch(1)
        # sticky save bar (A2)
        bar = _SaveBar()
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(0, SPACE.m, 0, 0)
        bar_layout.setSpacing(SPACE.m)
        self.result = InlineMessage()
        bar_layout.addWidget(self.result, 1)
        self.unsaved = Text("", "body_strong", "accent")
        bar_layout.addWidget(self.unsaved)
        self.reload = AppButton("action.reload_settings", variant="outlined", icon="restart_alt")
        self.reload.clicked.connect(self.load)
        self.save = AppButton("action.save_settings", variant="filled")
        self.save.clicked.connect(self.save_settings)
        bar_layout.addWidget(self.reload)
        bar_layout.addWidget(self.save)
        outer.addWidget(bar)
        language_notifier().changed.connect(self.retranslate)
        self.retranslate()
        self.load()

    # ---------------------------------------------------------------- build
    def _build(self) -> None:
        fields: dict[str, list[tuple[str, Any]]] = {
            "general": [("retention_days", Settings.model_fields["retention_days"])]
        }
        for section, info in Settings.model_fields.items():
            model = info.annotation
            if isinstance(model, type) and issubclass(model, BaseModel):
                fields[section] = [
                    (f"{section}.{key}", field) for key, field in model.model_fields.items()
                ]
        for section in SECTION_ORDER:
            if section not in fields:
                continue
            card = self._section_card(section)
            infos = dict(fields[section])
            rows: list[_FieldRow] = []
            for dotted, info in fields[section]:
                if dotted in RANGE_HIGHS:
                    continue
                if dotted in RANGES:
                    high, label_key = RANGES[dotted]
                    rows.append(self._range_row(dotted, info, high, infos[high], label_key))
                else:
                    rows.append(self._field_row(dotted, info))
            self._rows[section] = rows
            grid = QGridLayout()
            grid.setHorizontalSpacing(SPACE.xxl)
            grid.setVerticalSpacing(SPACE.l)
            self._grids[section] = grid
            card.body.addLayout(grid)
        self._reflow(1)

    def _section_card(self, section: str) -> Card:
        card = Card(f"settings.section.{section}", subtitle_key=f"settings.desc.{section}")
        self.groups[section] = card
        self.form_layout.addWidget(card)
        return card

    def _field_parts(self, dotted: str, info: Any) -> tuple[Editor, _EditedDot, Text]:
        editor = self._editor_for(dotted, info)
        error = Text("", "caption", "danger", wrap=True)
        error.setVisible(False)
        dot = _EditedDot()
        self.editors[dotted] = editor
        self.errors[dotted] = error
        self.dots[dotted] = dot
        self._watch(editor)
        return editor, dot, error

    def _field_row(self, dotted: str, info: Any) -> _FieldRow:
        editor, dot, error = self._field_parts(dotted, info)
        label = Text("", "body")
        self.labels[dotted] = label
        return _FieldRow(label, [editor], [dot], [error])

    def _range_row(
        self, low: str, low_info: Any, high: str, high_info: Any, label_key: str
    ) -> _FieldRow:
        low_editor, low_dot, low_error = self._field_parts(low, low_info)
        high_editor, high_dot, high_error = self._field_parts(high, high_info)
        label = TrText(label_key, "body")
        self.labels[low] = label
        self.labels[high] = label
        return _FieldRow(
            label, [low_editor, high_editor], [low_dot, high_dot], [low_error, high_error]
        )

    def _reflow(self, columns: int) -> None:
        """One column, or two from 1600 px (A2)."""
        if columns == self._columns:
            return
        self._columns = columns
        for section, rows in self._rows.items():
            grid = self._grids[section]
            for row in rows:
                grid.removeWidget(row)
            for index, row in enumerate(rows):
                grid.addWidget(row, index // columns, index % columns)
            for column in range(2):
                grid.setColumnStretch(column, 1 if column < columns else 0)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        window = self.window()
        width = window.width() if window is not None else self.width()
        self._reflow(2 if width >= SIZES.settings_two_column else 1)

    @staticmethod
    def _bounds(info: Any) -> tuple[float | None, float | None]:
        low = high = None
        for meta in info.metadata:
            for attr in ("ge", "gt"):
                if getattr(meta, attr, None) is not None:
                    low = getattr(meta, attr)
            for attr in ("le", "lt"):
                if getattr(meta, attr, None) is not None:
                    high = getattr(meta, attr)
        return low, high

    def _editor_for(self, dotted: str, info: Any) -> Editor:
        annotation = info.annotation
        low, high = self._bounds(info)
        if annotation is bool:
            return Switch()
        if annotation is int:
            spin = IntField(unit_key(dotted))
            spin.setRange(
                int(low if low is not None else -1_000_000),
                int(high if high is not None else 1_000_000_000),
            )
            return spin
        if annotation is float:
            dspin = DecimalField(unit_key(dotted))
            dspin.setSingleStep(0.01)
            dspin.setRange(
                float(low if low is not None else -1_000_000.0),
                float(high if high is not None else 1_000_000.0),
            )
            return dspin
        if get_origin(annotation) is Literal:
            combo = Select()
            for option in get_args(annotation):
                label = t(f"language.{option}") if option in LANGUAGES else str(option)
                combo.addItem(label, option)
            combo.setFixedWidth(max(combo.sizeHint().width(), SIZES.number_field))
            return combo
        return TextField()

    def _build_secrets(self) -> None:
        card = self._section_card("secrets")
        self.secret_help = Text("", "body", "secondary", wrap=True)
        card.body.addWidget(self.secret_help)
        row = QHBoxLayout()
        row.setSpacing(SPACE.m)
        self.secret_name = Select()
        self.secret_name.setFixedWidth(SIZES.select_max * 2 // 3)
        self.secret_value = PasswordField("settings.secret_value")
        self.secret_save = AppButton("action.store_secret", variant="tonal", icon="key")
        self.secret_save.clicked.connect(self._store_secret)
        row.addWidget(self.secret_name)
        row.addWidget(self.secret_value, 1)
        row.addWidget(self.secret_save)
        card.body.addLayout(row)
        self.secret_state = Text("", "body", "secondary", wrap=True)
        card.body.addWidget(self.secret_state)

    # ---------------------------------------------------------------- navigation
    def scroll_to(self, section: str) -> None:
        card = self.groups.get(section)
        if card is not None:
            self.form_scroll.verticalScrollBar().setValue(card.y() - SPACE.l)
            self.index.set_current(section)

    def _sync_index(self, value: int) -> None:
        current = SECTION_ORDER[0]
        for section, card in self.groups.items():
            if card.y() - SPACE.xl <= value:
                current = section
        self.index.set_current(current)

    # ---------------------------------------------------------------- data
    def _watch(self, editor: Editor) -> None:
        if isinstance(editor, QCheckBox):
            editor.toggled.connect(self._update_dirty)
        elif isinstance(editor, QSpinBox | QDoubleSpinBox):
            editor.valueChanged.connect(self._update_dirty)
        elif isinstance(editor, QComboBox):
            editor.currentIndexChanged.connect(self._update_dirty)
        else:
            editor.textChanged.connect(self._update_dirty)

    def load(self) -> None:
        values = self.c.settings.model_dump(mode="json")
        for dotted, editor in self.editors.items():
            value: Any = values
            for part in dotted.split("."):
                value = value[part]
            editor.blockSignals(True)
            self._set_value(editor, value)
            editor.blockSignals(False)
            editor.update()
        self._loaded = self._values()
        self._clear_errors()
        self._refresh_secrets()
        self._update_dirty()
        self.index.set_current(SECTION_ORDER[0])

    @staticmethod
    def _set_value(editor: Editor, value: Any) -> None:
        if isinstance(editor, QCheckBox):
            editor.setChecked(bool(value))
        elif isinstance(editor, QSpinBox):
            editor.setValue(int(value))
        elif isinstance(editor, QDoubleSpinBox):
            editor.setValue(float(value))
        elif isinstance(editor, QComboBox):
            editor.setCurrentIndex(max(0, editor.findData(value)))
        elif isinstance(value, list):
            editor.setText(", ".join(str(v) for v in value))
        else:
            editor.setText(str(value))

    @staticmethod
    def _value(editor: Editor) -> Any:
        if isinstance(editor, QCheckBox):
            return editor.isChecked()
        if isinstance(editor, QSpinBox | QDoubleSpinBox):
            return editor.value()
        if isinstance(editor, QComboBox):
            return editor.currentData()
        return editor.text().strip()

    def _values(self) -> dict[str, Any]:
        return {dotted: self._value(editor) for dotted, editor in self.editors.items()}

    def _update_dirty(self, *_args: object) -> None:
        changed = 0
        for dotted, editor in self.editors.items():
            edited = self._loaded.get(dotted) != self._value(editor)
            self.dots[dotted].setVisible(edited)
            changed += int(edited)
        if changed:
            self.unsaved.set_key("settings.unsaved", n=changed)
        else:
            self.unsaved.set_key(None)
        self.unsaved.setVisible(bool(changed))

    def collect(self) -> dict[str, Any]:
        current_values = self.c.settings.model_dump(mode="json")
        data: dict[str, Any] = {}
        for dotted, editor in self.editors.items():
            value = self._value(editor)
            current: Any = current_values
            for part in dotted.split("."):
                current = current[part]
            if isinstance(current, list) and isinstance(value, str):
                # every list setting (e-mail recipients, retried checks) is typed comma-separated
                value = [part.strip() for part in value.split(",") if part.strip()]
            target = data
            parts = dotted.split(".")
            for part in parts[:-1]:
                target = target.setdefault(part, {})
            target[parts[-1]] = value
        return data

    def _clear_errors(self) -> None:
        for dotted, label in self.errors.items():
            label.setVisible(False)
            set_prop(self.editors[dotted], "invalid", False)

    def save_settings(self) -> None:
        operator = self.c.operator
        if operator is None:
            return
        self._clear_errors()
        try:
            changes = self.c.ctx.settings_manager.save(self.collect(), operator)
        except SettingsError as exc:
            self._show_issues(exc)
            self.result.fail(exc)
            return
        except ParkomateError as exc:
            self.result.fail(exc)
            return
        if changes:
            self.result.ok(t("settings.saved", n=len(changes)))
        else:
            self.result.info(t("settings.no_changes"))
        motion.configure(bool(self.c.settings.ui.reduce_motion))
        self.load()

    def _show_issues(self, exc: SettingsError) -> None:
        first: QWidget | None = None
        for issue in exc.issues:
            keys = issue.ctx.get("keys") if isinstance(issue.ctx.get("keys"), list) else [issue.key]
            for key in keys:
                label = self.errors.get(key)
                if label is None:
                    continue
                label.setText(settings_issue_text(issue))
                label.setVisible(True)
                set_prop(self.editors[key], "invalid", True)
                first = first or self.editors[key]
        if first is not None:
            first.setFocus()
            self.form_scroll.ensureWidgetVisible(first)

    def _secret_names(self) -> list[str]:
        settings = self.c.settings
        return [
            settings.email.password_ref,
            settings.email.oauth_token_ref,
            settings.server.api_token_ref,
        ]

    def _refresh_secrets(self) -> None:
        current = self.secret_name.currentText()
        self.secret_name.clear()
        names = self._secret_names()
        self.secret_name.addItems(names)
        if current in names:
            self.secret_name.setCurrentText(current)
        states = []
        for name in names:
            stored = self.c.ctx.secrets.get(name) is not None
            state = t("settings.secret_stored" if stored else "settings.secret_missing")
            states.append(t("settings.secret_state", name=name, state=state))
        self.secret_state.setText("\n".join(states))

    def _store_secret(self) -> None:
        operator = self.c.operator
        value = self.secret_value.text()
        name = self.secret_name.currentText()
        if operator is None or not operator.is_admin or not value or not name:
            return
        try:
            self.c.ctx.secrets.set(name, value)
        except Exception:  # keyring backends raise their own types
            self.result.fail(
                ParkomateError(
                    "keyring write failed", code=ErrorCode.SECRET_MISSING, params={"name": name}
                )
            )
            return
        self.c.ctx.repos.audit.record(operator.id, "secret.set", {"name": name})
        self.secret_value.clear()
        self.result.ok(t("settings.secret_saved", name=name))
        self._refresh_secrets()

    def retranslate(self, *_args: object) -> None:
        for dotted, label in self.labels.items():
            text = t(f"settings.f.{dotted}")
            if dotted not in RANGES and dotted not in RANGE_HIGHS:
                label.setText(text)
            self.editors[dotted].setAccessibleName(text)
            self.editors[dotted].setToolTip(f"{text}  ·  {dotted}")
        self.secret_help.setText(t("settings.secrets_help"))
        self.secret_value.setAccessibleName(t("settings.secret_value"))
        self._refresh_secrets()
        self._update_dirty()


# =========================================================================== operators


class OperatorsTab(QWidget):
    COLUMNS = (
        "admin.op.code",
        "admin.op.name",
        "admin.op.role",
        "admin.op.active",
        "admin.op.locked",
    )

    def __init__(self, controller: StationController) -> None:
        super().__init__()
        self.c = controller
        scroll, content = _tab_scroll()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        columns = QHBoxLayout()
        columns.setSpacing(SPACE.l)
        content.addLayout(columns)
        left = QVBoxLayout()
        left.setSpacing(SPACE.l)
        list_card = Card("admin.tab.operators", icon="group")
        self.table = DataTable(
            self.COLUMNS, mono=(0,), empty=("group", "admin.op.empty_title", None)
        )
        for column in (3, 4):
            self.table.setItemDelegateForColumn(column, ChipDelegate({}, self.table))
        self.table.itemSelectionChanged.connect(self._selection_changed)
        self.table.setMinimumHeight(SIZES.table_row * 5)
        list_card.body.addWidget(self.table)
        left.addWidget(list_card)
        selected = Card("admin.op.selected_title", icon="manage_accounts")
        actions = QHBoxLayout()
        actions.setSpacing(SPACE.s)
        self.toggle_active = AppButton("action.deactivate", variant="outlined", size="compact")
        self.toggle_active.clicked.connect(self._toggle_active)
        self.unlock = AppButton(
            "action.unlock", variant="outlined", size="compact", icon="lock_open"
        )
        self.unlock.clicked.connect(self._unlock)
        self.toggle_role = AppButton("action.make_admin", variant="outlined", size="compact")
        self.toggle_role.clicked.connect(self._toggle_role)
        for button in (self.toggle_active, self.unlock, self.toggle_role):
            actions.addWidget(button)
        actions.addStretch(1)
        selected.body.addLayout(actions)
        reset_row = QHBoxLayout()
        reset_row.setSpacing(SPACE.s)
        self.reset_pw = PasswordField("admin.op.new_password")
        self.reset_pw2 = PasswordField("admin.op.password_again")
        self.reset_button = AppButton(
            "action.reset_password", variant="tonal", size="compact", icon="key"
        )
        self.reset_button.clicked.connect(self._reset_password)
        reset_row.addWidget(self.reset_pw, 1)
        reset_row.addWidget(self.reset_pw2, 1)
        reset_row.addWidget(self.reset_button)
        selected.body.addLayout(reset_row)
        self.result = InlineMessage()
        selected.body.addWidget(self.result)
        left.addWidget(selected)
        left.addStretch(1)
        columns.addLayout(left, SIZES.grid_columns - SIZES.left_columns)

        add_card = Card("admin.op.add_title", icon="person_add")
        self.new_code = TextField(max_width=None)
        self.new_name = TextField(max_width=None)
        self.new_role = Select(max_width=None)
        self.new_pw = PasswordField()
        self.new_pw2 = PasswordField()
        for key, widget in (
            ("admin.op.code", self.new_code),
            ("admin.op.name", self.new_name),
            ("admin.op.role", self.new_role),
            ("admin.op.password", self.new_pw),
            ("admin.op.password_again", self.new_pw2),
        ):
            add_card.body.addWidget(FormField(key, widget))
        self.add_button = AppButton("action.add_operator", variant="filled", icon="person_add")
        self.add_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.add_button.clicked.connect(self._add)
        add_card.body.addWidget(self.add_button)
        right = QVBoxLayout()
        right.addWidget(add_card)
        right.addStretch(1)
        columns.addLayout(right, SIZES.left_columns)
        language_notifier().changed.connect(self.retranslate)
        self.retranslate()

    def refresh(self) -> None:
        operators = self.c.ctx.auth.list_operators()
        rows = []
        for op in operators:
            locked = op.locked_until is not None and op.locked_until > self.c.ctx.repos.clock.now()
            rows.append(
                [
                    op.operator_code,
                    op.full_name,
                    t(op.role.label_key),
                    t("common.yes" if op.is_active else "common.no"),
                    t("common.yes" if locked else "common.no"),
                ]
            )
        self.table.fill(rows, [op.id for op in operators])
        self._selection_changed()

    def _chip_tones(self) -> None:
        yes, no = t("common.yes").upper(), t("common.no").upper()
        for column, yes_tone in ((3, "success"), (4, "warning")):
            delegate = self.table.itemDelegateForColumn(column)
            if isinstance(delegate, ChipDelegate):
                delegate.tones = {yes: yes_tone, no: "neutral"}

    def _selected(self) -> Operator | None:
        ids = self.table.selected_data()
        return self.c.ctx.repos.operators.get(ids[0]) if ids else None

    def _selection_changed(self) -> None:
        selected = self._selected()
        for button in (self.toggle_active, self.unlock, self.toggle_role, self.reset_button):
            button.setEnabled(selected is not None)
        if selected is not None:
            self.toggle_active.set_text_key(
                "action.deactivate" if selected.is_active else "action.activate"
            )
            self.toggle_role.set_text_key(
                "action.make_operator" if selected.is_admin else "action.make_admin"
            )

    def _run(self, fn: Any, ok_key: str, **params: Any) -> None:
        actor = self.c.operator
        if actor is None:
            return
        try:
            fn(actor)
        except ParkomateError as exc:
            self.result.fail(exc)
            return
        except Exception as exc:  # never let an admin action crash the station
            log.exception("operator admin action failed")
            self.result.fail(ParkomateError(str(exc), code=ErrorCode.UNEXPECTED))
            return
        self.result.ok(t(ok_key, **params))
        self.refresh()

    def _toggle_active(self) -> None:
        op = self._selected()
        if op is not None:
            self._run(
                lambda a: self.c.ctx.auth.set_active(a, op.id, not op.is_active),
                "admin.op.updated",
                code=op.operator_code,
            )

    def _unlock(self) -> None:
        op = self._selected()
        if op is not None:
            self._run(
                lambda a: self.c.ctx.auth.unlock(a, op.id),
                "admin.op.unlocked",
                code=op.operator_code,
            )

    def _toggle_role(self) -> None:
        op = self._selected()
        if op is not None:
            role = Role.OPERATOR if op.is_admin else Role.ADMIN
            self._run(
                lambda a: self.c.ctx.auth.set_role(a, op.id, role),
                "admin.op.updated",
                code=op.operator_code,
            )

    def _reset_password(self) -> None:
        op = self._selected()
        if op is None:
            return
        if self.reset_pw.text() != self.reset_pw2.text():
            self.result.info(t("admin.op.passwords_differ"))
            return
        password = self.reset_pw.text()
        self._run(
            lambda a: self.c.ctx.auth.reset_password(a, op.id, password),
            "admin.op.password_reset",
            code=op.operator_code,
        )
        self.reset_pw.clear()
        self.reset_pw2.clear()

    def _add(self) -> None:
        if self.new_pw.text() != self.new_pw2.text():
            self.result.info(t("admin.op.passwords_differ"))
            return
        code, name = self.new_code.text(), self.new_name.text()
        role = Role(self.new_role.currentData())  # Qt hands enum data back as str
        password = self.new_pw.text()
        self._run(
            lambda a: self.c.ctx.auth.create_operator(a, code, name, password, role),
            "admin.op.created",
            code=code.strip(),
        )
        if self.result.property("status") == "pass":
            for field in (self.new_code, self.new_name, self.new_pw, self.new_pw2):
                field.clear()

    def retranslate(self, *_args: object) -> None:
        self.table.setAccessibleName(t("admin.tab.operators"))
        for field, key in (
            (self.new_code, "admin.op.code"),
            (self.new_name, "admin.op.name"),
            (self.new_pw, "admin.op.password"),
            (self.new_pw2, "admin.op.password_again"),
            (self.reset_pw, "admin.op.new_password"),
            (self.reset_pw2, "admin.op.password_again"),
        ):
            field.setAccessibleName(t(key))
        current = self.new_role.currentData()
        self.new_role.clear()
        for role in (Role.OPERATOR, Role.ADMIN):
            self.new_role.addItem(t(role.label_key), role)
        self.new_role.setCurrentIndex(max(0, self.new_role.findData(current)))
        self.new_role.setAccessibleName(t("admin.op.role"))
        self._chip_tones()


# =========================================================================== reports


class ReportsTab(QWidget):
    SESSION_COLUMNS = (
        "admin.rep.session",
        "admin.rep.operator",
        "admin.rep.started",
        "admin.rep.ended",
        "admin.rep.devices",
    )
    OUTBOX_COLUMNS = (
        "admin.out.id",
        "admin.out.created",
        "admin.out.subject",
        "admin.out.status",
        "admin.out.attempts",
        "admin.out.error",
    )
    SCOPES = ("selected", "range", "device")
    OUTBOX_TONES: ClassVar[dict[OutboxStatus, str]] = {
        OutboxStatus.SENT: "success",
        OutboxStatus.FAILED: "danger",
        OutboxStatus.PENDING: "warning",
    }

    def __init__(self, controller: StationController) -> None:
        super().__init__()
        self.c = controller
        scroll, content = _tab_scroll()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        top = QHBoxLayout()
        top.setSpacing(SPACE.l)
        sessions_card = Card("admin.rep.sessions_title", icon="history")
        self.sessions = DataTable(
            self.SESSION_COLUMNS,
            numeric=(0, 4),
            empty=("history", "admin.rep.empty_title", "admin.rep.empty_body"),
        )
        self.sessions.setMinimumHeight(SIZES.table_row * 6)
        sessions_card.body.addWidget(self.sessions)
        top.addWidget(sessions_card, SIZES.grid_columns - SIZES.left_columns)
        top.addWidget(self._export_card(), SIZES.left_columns)
        content.addLayout(top)
        content.addWidget(self._outbox_card())
        content.addStretch(1)
        language_notifier().changed.connect(self.retranslate)
        self.retranslate()

    def _export_card(self) -> Card:
        """ONE export card: scope · format · Export (A3)."""
        card = Card("admin.rep.export_title", icon="download")
        card.body.addWidget(TrText("admin.rep.scope", "label", "secondary"))
        self.scope = SegmentedControl(
            [
                ("selected", "admin.rep.scope_selected"),
                ("range", "admin.rep.scope_range"),
                ("device", "admin.rep.scope_device"),
            ]
        )
        self.scope.changed.connect(self._scope_changed)
        card.body.addWidget(self.scope)
        self.scope_stack = QStackedWidget()
        self.scope_stack.addWidget(TrText("admin.rep.select_hint", "body", "secondary", wrap=True))
        today = QDate.currentDate()
        self.date_range = DateRangePicker(today.addDays(-7), today)
        self.scope_stack.addWidget(self.date_range)
        self.device_search = TextField("admin.rep.device_search", max_width=None)
        self.scope_stack.addWidget(self.device_search)
        self.scope_stack.setFixedHeight(SIZES.input)
        card.body.addWidget(self.scope_stack)
        card.body.addWidget(TrText("admin.rep.format", "label", "secondary"))
        self.format = SegmentedControl(
            [
                ("xlsx", "admin.rep.format_xlsx"),
                ("csv", "admin.rep.format_csv"),
                ("both", "admin.rep.format_both"),
            ]
        )
        card.body.addWidget(self.format)
        self.export_button = AppButton("action.export", variant="filled", icon="download")
        self.export_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.export_button.clicked.connect(self.export)
        card.body.addWidget(self.export_button)
        self.result = InlineMessage()
        card.body.addWidget(self.result)
        card.body.addStretch(1)
        return card

    def _outbox_card(self) -> Card:
        card = Card("admin.out.title", icon="outbox")
        self.outbox = DataTable(
            self.OUTBOX_COLUMNS,
            numeric=(0, 4),
            empty=("inbox", "admin.out.empty_title", "admin.out.empty_body"),
        )
        self.outbox.setItemDelegateForColumn(3, ChipDelegate({}, self.outbox))
        self.outbox.setMinimumHeight(SIZES.table_row * 5)
        card.body.addWidget(self.outbox)
        buttons = QHBoxLayout()
        buttons.setSpacing(SPACE.s)
        self.open_folder = AppButton(
            "action.open_reports_folder", variant="text", size="compact", icon="folder_open"
        )
        self.open_folder.clicked.connect(self._open_folder)
        self.resend = AppButton("action.resend", variant="outlined", size="compact", icon="send")
        self.resend.clicked.connect(self._resend)
        self.send_now = AppButton(
            "action.send_pending", variant="outlined", size="compact", icon="mail"
        )
        self.send_now.clicked.connect(self._send_now)
        buttons.addWidget(self.open_folder)
        buttons.addStretch(1)
        buttons.addWidget(self.resend)
        buttons.addWidget(self.send_now)
        card.body.addLayout(buttons)
        return card

    def _scope_changed(self, scope: object) -> None:
        self.scope_stack.setCurrentIndex(self.SCOPES.index(str(scope)))

    def refresh(self) -> None:
        repos = self.c.ctx.repos
        sessions = repos.sessions.list_sessions(limit=200)
        rows = []
        for session in sessions:
            operator = repos.operators.get(session.operator_id)
            count = len(repos.devices.list_for_session(session.id))
            name = f"{operator.full_name} ({operator.operator_code})" if operator else ""
            rows.append(
                [
                    str(session.id),
                    name,
                    _local(session.started_at),
                    _local(session.ended_at),
                    str(count),
                ]
            )
        self.sessions.fill(rows, [s.id for s in sessions])
        items = self.c.ctx.outbox.list_items()
        self.outbox.fill(
            [
                [
                    str(i.id),
                    _local(i.created_at),
                    i.subject,
                    t(i.status.label_key),
                    str(i.attempts),
                    i.last_error or "",
                ]
                for i in items
            ],
            [i.id for i in items],
        )

    def _status_tones(self) -> None:
        delegate = self.outbox.itemDelegateForColumn(3)
        if isinstance(delegate, ChipDelegate):
            delegate.tones = {
                t(status.label_key).upper(): self.OUTBOX_TONES.get(status, "neutral")
                for status in OutboxStatus
            }

    def export(self) -> None:
        scope = self.scope.value()
        if scope == "range":
            self._export_range()
        elif scope == "device":
            self._export_device()
        else:
            self._export_selected(str(self.format.value() or "xlsx"))

    def _done(self, paths: list[Any]) -> None:
        self.result.ok(t("admin.rep.written", files=", ".join(str(p) for p in paths)))

    def _export_selected(self, fmt: str) -> None:
        ids = sorted(self.sessions.selected_data())
        if not ids:
            self.result.info(t("admin.rep.select_session"))
            return
        exporter = self.c.ctx.exporter
        self.result.info(t("admin.rep.working"))
        self.c.bg.submit(
            lambda: exporter.export_sessions(ids, fmt=fmt),  # type: ignore[arg-type]
            on_success=self._done,
            on_error=self.result.fail,
            name="export",
        )

    def _export_range(self) -> None:
        start_day = self.date_range.start_date()
        end_day = self.date_range.end_date()
        start = datetime.combine(start_day, time.min).astimezone()
        end = datetime.combine(end_day + timedelta(days=1), time.min).astimezone()
        fmt = cast(ExportFormat, self.format.value() or "xlsx")
        exporter = self.c.ctx.exporter
        self.result.info(t("admin.rep.working"))
        self.c.bg.submit(
            lambda: exporter.export_range(start.astimezone(UTC), end.astimezone(UTC), fmt=fmt),
            on_success=self._done,
            on_error=self.result.fail,
            name="export_range",
        )

    def _export_device(self) -> None:
        text = self.device_search.text().strip()
        matches = self.c.ctx.repos.devices.search(text) if text else []
        if not matches:
            self.result.info(t("admin.rep.no_device", text=text))
            return
        exporter = self.c.ctx.exporter
        row_id = matches[0].id
        self.c.bg.submit(
            lambda: [exporter.export_device(row_id)],
            on_success=self._done,
            on_error=self.result.fail,
            name="export_device",
        )

    def _open_folder(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.c.ctx.exporter.reports_dir)))

    def _resend(self) -> None:
        ids = self.outbox.selected_data()
        operator = self.c.operator
        if not ids or operator is None:
            self.result.info(t("admin.out.select_item"))
            return
        outbox = self.c.ctx.outbox
        item_id = ids[0]

        def done(sent: object) -> None:
            if sent:
                self.result.ok(t("admin.out.sent"))
            else:
                self.result.info(t("admin.out.not_sent"))
            self.refresh()

        self.c.bg.submit(
            lambda: outbox.resend(operator, item_id),
            on_success=done,
            on_error=self.result.fail,
            name="resend",
        )

    def _send_now(self) -> None:
        def done(report: Any) -> None:
            if report.skipped:
                self.result.info(t("admin.out.disabled"))
            else:
                self.result.info(t("admin.out.result", sent=report.sent, failed=report.failed))
            self.refresh()

        self.c.bg.submit(
            self.c.ctx.station.send_pending,
            on_success=done,
            on_error=self.result.fail,
            name="send_pending",
        )

    def retranslate(self, *_args: object) -> None:
        self.sessions.setAccessibleName(t("admin.rep.sessions_title"))
        self.outbox.setAccessibleName(t("admin.out.title"))
        self.device_search.setAccessibleName(t("admin.rep.device_search"))
        self.scope.setAccessibleName(t("admin.rep.scope"))
        self.format.setAccessibleName(t("admin.rep.format"))
        self._status_tones()


# =========================================================================== counters


class CountersTab(QWidget):
    """KPI tiles of the live counters; Reset is tonal red with an inline confirm (A5)."""

    def __init__(self, controller: StationController) -> None:
        super().__init__()
        self.c = controller
        scroll, content = _tab_scroll()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        content.addWidget(TrText("admin.cnt.title", "title"))
        self.since = Text("", "caption", "secondary")
        content.addWidget(self.since)
        tiles = QGridLayout()
        tiles.setSpacing(SPACE.l)
        self.tiles = {
            "ok": KpiTile("counter.uploads_ok", "check_circle", COLORS.success),
            "fail": KpiTile("counter.uploads_fail", "cancel", COLORS.danger),
            "adjusted": KpiTile("counter.failures_adjusted", "restart_alt", COLORS.text_2),
            "done": KpiTile("counter.completed", "task_alt", COLORS.primary),
            "rejected": KpiTile("counter.rejected", "block", COLORS.danger),
        }
        for index, tile in enumerate(self.tiles.values()):
            tiles.addWidget(tile, 0, index)
        content.addLayout(tiles)
        content.addWidget(TrText("admin.cnt.help", "body", "secondary", wrap=True))
        self.confirm = InlineConfirm()
        self.confirm.setVisible(False)
        self.confirm.answered.connect(self._answered)
        content.addWidget(self.confirm)
        row = QHBoxLayout()
        self.reset = AppButton("action.reset_counters", variant="danger_tonal", icon="restart_alt")
        self.reset.clicked.connect(self._ask)
        row.addWidget(self.reset)
        row.addStretch(1)
        content.addLayout(row)
        self.result = InlineMessage()
        content.addWidget(self.result)
        content.addStretch(1)
        controller.counters_changed.connect(self.refresh)
        language_notifier().changed.connect(self.refresh)

    def refresh(self, *_args: object) -> None:
        counters = self.c.counters
        if counters is None:
            self.since.set_key("admin.cnt.no_session")
            for tile in self.tiles.values():
                tile.set_value("-")
            self.reset.setEnabled(False)
            return
        self.reset.setEnabled(True)
        since = _local(counters.since) if counters.since else t("admin.cnt.since_start")
        self.since.set_key("admin.cnt.since", since=since)
        values = {
            "ok": counters.upload_success,
            "fail": counters.upload_failure,
            "adjusted": counters.failures_adjusted,
            "done": counters.completed,
            "rejected": counters.rejected,
        }
        for name, value in values.items():
            self.tiles[name].set_value(str(value))

    def _ask(self) -> None:
        self.confirm.show_confirm(
            t("confirm.reset_counters"), "action.reset_counters", "action.cancel", True
        )

    def _answered(self, yes: bool) -> None:
        self.confirm.setVisible(False)
        operator = self.c.operator
        if not yes or operator is None:
            return
        try:
            self.c.ctx.records.reset_counters(operator)
        except ParkomateError as exc:
            self.result.fail(exc)
            return
        self.result.ok(t("admin.cnt.reset_done"))
        self.c.refresh_counters()


# =========================================================================== error log


class ErrorLogTab(QWidget):
    COLUMNS = ("admin.log.time", "admin.log.level", "admin.log.code", "admin.log.message")
    LEVELS: ClassVar[dict[str, str]] = {
        "CRITICAL": "danger",
        "ERROR": "danger",
        "WARNING": "warning",
        "INFO": "info",
    }

    def __init__(self, controller: StationController) -> None:
        super().__init__()
        self.c = controller
        self._entries: list[dict[str, Any]] = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, SPACE.l, 0, SPACE.l)
        layout.setSpacing(SPACE.l)
        row = QHBoxLayout()
        row.setSpacing(SPACE.m)
        self.filter = Select()
        self.filter.setFixedWidth(SIZES.select_max)
        self.filter.currentIndexChanged.connect(self._filter_changed)
        self.refresh_button = AppButton("action.refresh", variant="outlined", icon="refresh")
        self.refresh_button.clicked.connect(self.refresh)
        row.addWidget(self.filter)
        row.addWidget(self.refresh_button)
        row.addStretch(1)
        layout.addLayout(row)
        card = Card()
        self.table = DataTable(
            self.COLUMNS,
            mono=(2,),
            empty=("task_alt", "admin.log.empty_title", "admin.log.empty_body"),
        )
        self.table.setItemDelegateForColumn(1, ChipDelegate(self.LEVELS, self.table))
        self.table.itemSelectionChanged.connect(self._show_details)
        card.body.addWidget(self.table)
        layout.addWidget(card, 2)
        self.details_card = Card("admin.log.details", icon="description", compact=True)
        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setFont(font_for(TYPE.mono_label))
        self.details_card.body.addWidget(self.details)
        self.details_card.setVisible(False)  # only when a row is selected (A4)
        layout.addWidget(self.details_card, 1)
        language_notifier().changed.connect(self.retranslate)
        self.retranslate()

    def _filter_changed(self, _index: int) -> None:
        self.refresh()

    def refresh(self) -> None:
        code = self.filter.currentData()
        self._entries = read_error_log(self.c.ctx.paths.logs_dir, limit=200, error_code=code)
        rows = [
            [
                str(e.get("time", "")),
                str(e.get("level", "")),
                str(e.get("error_code") or ""),
                str(e.get("message", "")),
            ]
            for e in self._entries
        ]
        self.table.fill(rows, list(range(len(rows))))
        self.details.setPlainText("" if rows else t("admin.log.empty"))
        self.details_card.setVisible(False)

    def _show_details(self) -> None:
        selected = self.table.selected_data()
        if selected:
            entry = self._entries[int(selected[0])]
            self.details.setPlainText(json.dumps(entry, ensure_ascii=False, indent=2))
            self.details_card.setVisible(True)
        else:
            self.details_card.setVisible(False)

    def retranslate(self, *_args: object) -> None:
        self.table.setAccessibleName(t("admin.tab.errors"))
        self.details.setAccessibleName(t("admin.log.details"))
        current = self.filter.currentData()
        self.filter.blockSignals(True)
        self.filter.clear()
        self.filter.addItem(t("admin.log.all_codes"), None)
        for code in ErrorCode:
            self.filter.addItem(code.value, code.value)
        self.filter.setCurrentIndex(max(0, self.filter.findData(current)))
        self.filter.setAccessibleName(t("admin.log.filter"))
        self.filter.blockSignals(False)


# =========================================================================== page


class AdminView(QWidget):
    TABS = (
        "admin.tab.settings",
        "admin.tab.operators",
        "admin.tab.reports",
        "admin.tab.counters",
        "admin.tab.errors",
    )

    def __init__(self, controller: StationController) -> None:
        super().__init__()
        self.c = controller
        self.setObjectName("Page")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(SIZES.page_margin, SPACE.l, SIZES.page_margin, SPACE.l)
        self._layout.setSpacing(SPACE.s)
        header = QHBoxLayout()
        header.setSpacing(SPACE.l)
        # tonal/outlined with a back arrow - primary colour is for each tab's main action (A7)
        self.back = AppButton(
            "action.back_to_production", variant="outlined", icon="arrow_back", hint_key="key.esc"
        )
        self.back.clicked.connect(controller.close_admin)
        header.addWidget(self.back)
        header.addWidget(TrText("admin.title", "headline"), 1)
        self._layout.addLayout(header)
        self.tabs = Tabs()
        self.settings_tab = SettingsTab(controller)
        self.operators_tab = OperatorsTab(controller)
        self.reports_tab = ReportsTab(controller)
        self.counters_tab = CountersTab(controller)
        self.errors_tab = ErrorLogTab(controller)
        tabs = (
            self.settings_tab,
            self.operators_tab,
            self.reports_tab,
            self.counters_tab,
            self.errors_tab,
        )
        for tab, key in zip(tabs, self.TABS, strict=True):
            self.tabs.add_tab(tab, key)
        self._layout.addWidget(self.tabs, 1)

    def refresh(self) -> None:
        self.settings_tab.load()
        self.operators_tab.refresh()
        self.reports_tab.refresh()
        self.counters_tab.refresh()
        self.errors_tab.refresh()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        width = self.width()
        margin = SIZES.page_margin_wide if width >= SIZES.wide_breakpoint else SIZES.page_margin
        margin = max(margin, (width - SIZES.content_max) // 2)
        self._layout.setContentsMargins(margin, SPACE.l, margin, SPACE.l)
