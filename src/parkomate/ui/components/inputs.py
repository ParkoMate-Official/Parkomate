"""Inputs: TextField, PasswordField (eye inside the field), IntField / DecimalField (unit
suffix), Select (custom popup, two-line items), Switch, DateRangePicker, FormField.

Inputs are 52 px, radius 12, filled surface_2 when idle, white + primary border when focused,
danger border + helper text when invalid (property ``invalid``). Native combo arrows, spin
buttons and date-edit dropdowns never appear (G5).
"""

from __future__ import annotations

from datetime import date
from typing import Any

from PySide6.QtCore import QDate, QEvent, QModelIndex, QPersistentModelIndex, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFontMetricsF,
    QKeyEvent,
    QPainter,
    QPaintEvent,
    QResizeEvent,
    QTextCharFormat,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCalendarWidget,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLineEdit,
    QListView,
    QSizePolicy,
    QSpinBox,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QVBoxLayout,
    QWidget,
)

from parkomate.i18n import t
from parkomate.ui.components.base import draw_line, fill_rounded, mix, on_language_change, qcolor, set_prop
from parkomate.ui.components.buttons import AppButton, IconButton
from parkomate.ui.components.icons import paint_icon
from parkomate.ui.components.popup import Popup
from parkomate.ui.components.text import Text, TrText
from parkomate.ui.theme.fonts import font_for, line_box
from parkomate.ui.theme.motion import Tween
from parkomate.ui.theme.tokens import ALPHA, COLORS, MOTION, RADIUS, SIZES, SPACE, TYPE

# Select item roles (in addition to the display text).
ROLE_SHORT = int(Qt.ItemDataRole.UserRole) + 10  # text of the closed field
ROLE_SECONDARY = int(Qt.ItemDataRole.UserRole) + 11  # second line in the list


def _field_colors(widget: QWidget, focused: bool) -> tuple[str, str, float]:
    """(fill, border, border width) for a painted field."""
    if not widget.isEnabled():
        return COLORS.surface_3, COLORS.outline_soft, SIZES.hairline
    if widget.property("invalid") is True:
        return COLORS.surface, COLORS.danger, SIZES.hairline
    if focused:
        return COLORS.surface, COLORS.primary, SIZES.hairline
    if widget.underMouse():
        return COLORS.surface_2, COLORS.outline_strong, SIZES.hairline
    return COLORS.surface_2, COLORS.outline, SIZES.hairline


class TextField(QLineEdit):
    def __init__(
        self,
        placeholder_key: str | None = None,
        *,
        max_width: int | None = SIZES.text_field_max,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._placeholder_key = placeholder_key
        self.setFont(font_for(TYPE.body_lg))
        self.setFixedHeight(SIZES.input)
        self.setProperty("ring_radius", RADIUS.control)
        if max_width:
            self.setMaximumWidth(max_width)
        on_language_change(self, self.retranslate)
        self.retranslate()

    def set_placeholder_key(self, key: str | None) -> None:
        self._placeholder_key = key
        self.retranslate()

    def retranslate(self, *_args: object) -> None:
        if self._placeholder_key:
            self.setPlaceholderText(t(self._placeholder_key))

    def set_invalid(self, invalid: bool) -> None:
        set_prop(self, "invalid", invalid)


class PasswordField(TextField):
    """Password with the show/hide eye INSIDE the field (N1). ``eye`` is focusable."""

    def __init__(self, placeholder_key: str | None = None, parent: QWidget | None = None) -> None:
        super().__init__(placeholder_key, parent=parent)
        self.setEchoMode(QLineEdit.EchoMode.Password)
        self.setProperty("trailing", True)
        self.eye = IconButton("visibility", "action.show_password", parent=self)
        self.eye.setCheckable(True)
        self.eye.toggled.connect(self._toggle)
        self.eye.setFixedSize(SIZES.button_compact, SIZES.button_compact)

    def _toggle(self, shown: bool) -> None:
        self.setEchoMode(QLineEdit.EchoMode.Normal if shown else QLineEdit.EchoMode.Password)
        self.eye.set_icon("visibility_off" if shown else "visibility")
        self.eye.set_tip_key("action.hide_password" if shown else "action.show_password")

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802 - Qt API
        super().resizeEvent(event)
        side = self.eye.width()
        self.eye.move(self.width() - side - SPACE.xs, (self.height() - side) // 2)


class _NumberMixin:
    _unit_key: str | None

    def _setup(self, widget: QWidget, unit_key: str | None) -> None:
        self._unit_key = unit_key
        widget.setFont(font_for(TYPE.body_lg))  # type: ignore[attr-defined]
        widget.setFixedHeight(SIZES.input)
        widget.setFixedWidth(SIZES.number_field)
        widget.setProperty("ring_radius", RADIUS.control)
        widget.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)  # type: ignore[attr-defined]
        widget.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)  # type: ignore[attr-defined]
        widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        on_language_change(widget, self._retranslate_unit)
        self._retranslate_unit()

    def _retranslate_unit(self, *_args: object) -> None:
        suffix = f" {t(self._unit_key)}" if self._unit_key else ""
        self.setSuffix(suffix)  # type: ignore[attr-defined]


class IntField(_NumberMixin, QSpinBox):
    def __init__(self, unit_key: str | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup(self, unit_key)

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802 - Qt API
        if self.hasFocus():
            super().wheelEvent(event)
        else:
            event.ignore()  # scrolling the settings page never changes a value


class DecimalField(_NumberMixin, QDoubleSpinBox):
    def __init__(
        self, unit_key: str | None = None, *, decimals: int = 3, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setDecimals(decimals)
        self._setup(self, unit_key)

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802 - Qt API
        if self.hasFocus():
            super().wheelEvent(event)
        else:
            event.ignore()


class _ItemDelegate(QStyledItemDelegate):
    """Two-line items: bold primary text, secondary text below (P4)."""

    def __init__(self, select: Select) -> None:
        super().__init__(select)
        self.select = select

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex | QPersistentModelIndex) -> QSize:  # noqa: N802
        two = bool(index.data(ROLE_SECONDARY))
        return QSize(option.rect.width(), SIZES.list_row if two else SIZES.button_compact + SPACE.xs)

    def paint(
        self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex | QPersistentModelIndex
    ) -> None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(option.rect).adjusted(SPACE.xs, 0, -SPACE.xs, 0)
        from PySide6.QtWidgets import QStyle

        selected = index.row() == self.select.currentIndex()
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        if selected:
            fill_rounded(painter, rect, RADIUS.chip, COLORS.primary_cont)
        elif hovered:
            fill_rounded(painter, rect, RADIUS.chip, qcolor(COLORS.text, ALPHA.hover))
        primary = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        secondary = str(index.data(ROLE_SECONDARY) or "")
        x = rect.left() + SPACE.m
        width = rect.width() - 2 * SPACE.m - (SIZES.icon + SPACE.s if selected else 0)
        main = line_box(TYPE.body_strong if secondary else TYPE.body)
        sub = line_box(TYPE.caption)
        total = main.height + (sub.height if secondary else 0)
        top = rect.center().y() - total / 2
        draw_line(painter, QRectF(x, top, width, main.height), primary,
                  TYPE.body_strong if secondary else TYPE.body,
                  COLORS.on_primary_cont if selected else COLORS.text)
        if secondary:
            draw_line(painter, QRectF(x, top + main.height, width, sub.height), secondary,
                      TYPE.caption, COLORS.text_2)
        if selected:
            side = SIZES.icon
            paint_icon(
                painter,
                "check",
                QRectF(rect.right() - SPACE.m - side, rect.center().y() - side / 2, side, side),
                COLORS.primary,
            )
        painter.restore()


class Select(QComboBox):
    """A combo box painted as a field, with a custom popup list (G5, P4).

    Items may carry ``ROLE_SHORT`` (text shown when closed, e.g. 'COM4 · CP210x') and
    ``ROLE_SECONDARY`` (second line in the list). The full text is the tooltip.
    """

    def __init__(
        self,
        *,
        compact: bool = False,
        max_width: int | None = SIZES.select_max,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._compact = compact
        self._popup: Popup | None = None
        self._placeholder_key: str | None = None
        self.setFont(font_for(TYPE.body))
        self.setFixedHeight(SIZES.button_compact if compact else SIZES.input)
        if max_width:
            self.setMaximumWidth(max_width)
        self.setProperty("ring_radius", RADIUS.control)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.currentIndexChanged.connect(self._sync_tooltip)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

    def set_placeholder_key(self, key: str | None) -> None:
        self._placeholder_key = key
        self.update()

    def _sync_tooltip(self, *_args: object) -> None:
        self.setToolTip(self.currentText() if self.currentIndex() >= 0 else "")

    def closed_text(self) -> str:
        index = self.currentIndex()
        if index < 0:
            return t(self._placeholder_key) if self._placeholder_key else ""
        short = self.itemData(index, ROLE_SHORT)
        return str(short) if short else self.itemText(index)

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt API
        metrics = QFontMetricsF(self.font())
        widest = 0.0
        for index in range(self.count()):
            short = self.itemData(index, ROLE_SHORT)
            widest = max(widest, metrics.horizontalAdvance(str(short or self.itemText(index))))
        width = int(widest) + 2 * SPACE.l + SIZES.icon_m + SPACE.s
        return QSize(max(width, SIZES.button_min_width), self.height())

    def minimumSizeHint(self) -> QSize:  # noqa: N802 - Qt API
        return QSize(SIZES.button_min_width, self.height())

    # ------------------------------------------------------------------ popup
    def showPopup(self) -> None:  # noqa: N802 - Qt API
        if self.count() == 0 or not self.isEnabled():
            return
        popup = Popup(self)
        view = QListView()
        view.setObjectName("SelectList")
        view.setModel(self.model())
        view.setItemDelegate(_ItemDelegate(self))
        view.setMouseTracking(True)
        view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        view.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        rows = sum(view.sizeHintForRow(r) for r in range(self.count()))
        view.setFixedHeight(min(rows + 2 * SPACE.xs, SIZES.popup_max_height))
        view.setCurrentIndex(self.model().index(max(0, self.currentIndex()), 0))
        view.clicked.connect(lambda index: self._choose(index.row()))
        view.activated.connect(lambda index: self._choose(index.row()))
        popup.content.addWidget(view)
        popup.closed.connect(self._popup_closed)
        self._popup = popup
        popup.open_at(self, width=max(self.width(), self.sizeHint().width()))
        view.setFocus()

    def _choose(self, row: int) -> None:
        popup = self._popup
        if popup is not None:
            popup.close()
        changed = row != self.currentIndex()
        self.setCurrentIndex(row)
        self.activated.emit(row)
        self.textActivated.emit(self.itemText(row))
        if changed:
            self.update()

    def _popup_closed(self) -> None:
        popup = self._popup
        self._popup = None
        if popup is not None:
            popup.deleteLater()
        self.update()

    def hidePopup(self) -> None:  # noqa: N802 - Qt API
        if self._popup is not None:
            self._popup.close()

    def popup_open(self) -> bool:
        return self._popup is not None

    # ------------------------------------------------------------------ painting
    def enterEvent(self, event: QEvent) -> None:  # noqa: N802 - Qt API
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent) -> None:  # noqa: N802 - Qt API
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())
        fill, border, width = _field_colors(self, self.hasFocus() or self._popup is not None)
        fill_rounded(painter, rect, RADIUS.control, fill, border, width)
        side = SIZES.icon_m
        chevron = QRectF(rect.right() - SPACE.l - side, rect.center().y() - side / 2, side, side)
        paint_icon(
            painter,
            "expand_less" if self._popup is not None else "expand_more",
            chevron,
            COLORS.text_2 if self.isEnabled() else COLORS.text_3,
        )
        placeholder = self.currentIndex() < 0
        area = QRectF(rect.left() + SPACE.l, rect.top(), chevron.left() - SPACE.s - rect.left() - SPACE.l, rect.height())
        draw_line(painter, area, self.closed_text(), TYPE.body,
                  COLORS.text_3 if placeholder or not self.isEnabled() else COLORS.text)
        painter.end()

    def set_invalid(self, invalid: bool) -> None:
        set_prop(self, "invalid", invalid)


class Switch(QCheckBox):
    """On/off switch (52 x 32) - replaces the checkbox in forms."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pos = Tween(self, lambda _v: self.update(), ms=MOTION.medium)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFixedSize(SIZES.switch_w, SIZES.switch_h)
        self.setProperty("ring_radius", RADIUS.pill)
        self.toggled.connect(lambda on: self._pos.to(1.0 if on else 0.0))

    def setChecked(self, checked: bool) -> None:  # noqa: N802 - Qt API
        super().setChecked(checked)
        self._pos.jump(1.0 if checked else 0.0)

    def hitButton(self, _pos: Any) -> bool:  # noqa: N802 - Qt API
        return True

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt API
        return QSize(SIZES.switch_w, SIZES.switch_h)

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())
        k = self._pos.value
        on_track = COLORS.primary if self.isEnabled() else COLORS.text_3
        off_track = COLORS.surface_3
        track = mix(off_track, on_track, k)
        fill_rounded(
            painter, rect, RADIUS.pill, track, COLORS.outline_strong if k < 0.5 else None,
            SIZES.hairline if k < 0.5 else 0,
        )
        pad = SPACE.xs
        small = rect.height() - 4 * pad
        large = rect.height() - 2 * pad
        side = small + (large - small) * k
        x = rect.left() + pad + (rect.width() - 2 * pad - large) * k + (large - side) / 2
        thumb = QRectF(x, rect.center().y() - side / 2, side, side)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(mix(COLORS.outline_strong, COLORS.surface, k))
        painter.drawEllipse(thumb)
        if k > 0.5:
            icon = side * 0.7
            paint_icon(
                painter,
                "check",
                QRectF(thumb.center().x() - icon / 2, thumb.center().y() - icon / 2, icon, icon),
                COLORS.primary,
            )
        painter.end()


class DateRangePicker(QWidget):
    """A field showing 'from – to' with a calendar popup: first click = start, second = end."""

    changed = Signal()

    def __init__(self, start: QDate, end: QDate, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._start = start
        self._end = end
        self._picking_end = False
        self._popup: Popup | None = None
        self.setFixedHeight(SIZES.input)
        self.setMinimumWidth(SIZES.number_field * 2)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setProperty("ring_radius", RADIUS.control)
        on_language_change(self, self._retranslate)
        self._retranslate()

    def start(self) -> QDate:
        return self._start

    def end(self) -> QDate:
        return self._end

    def start_date(self) -> date:
        return self._start.toPython()  # type: ignore[no-any-return]

    def end_date(self) -> date:
        return self._end.toPython()  # type: ignore[no-any-return]

    def set_range(self, start: QDate, end: QDate) -> None:
        if end < start:
            start, end = end, start
        self._start, self._end = start, end
        self._retranslate()
        self.changed.emit()

    def text(self) -> str:
        return t(
            "date.range",
            start=self._start.toString("yyyy-MM-dd"),
            end=self._end.toString("yyyy-MM-dd"),
        )

    def _retranslate(self, *_args: object) -> None:
        self.setAccessibleName(t("admin.rep.range"))
        self.setAccessibleDescription(self.text())
        self.update()

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt API
        metrics = QFontMetricsF(font_for(TYPE.body))
        width = metrics.horizontalAdvance(self.text()) + 3 * SPACE.l + SIZES.icon_m
        return QSize(int(width) + SPACE.s, SIZES.input)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 - Qt API
        if event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_F4):
            self.open_popup()
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event: Any) -> None:  # noqa: N802 - Qt API
        if event.button() == Qt.MouseButton.LeftButton:
            self.open_popup()
            return
        super().mousePressEvent(event)

    def open_popup(self) -> None:
        if self._popup is not None:
            return
        popup = Popup(self)
        popup.content.setContentsMargins(SPACE.m, SPACE.m, SPACE.m, SPACE.m)
        popup.content.setSpacing(SPACE.s)
        presets = QHBoxLayout()
        presets.setSpacing(SPACE.s)
        today = QDate.currentDate()
        for key, days in (("date.today", 0), ("date.last_7", 6), ("date.last_30", 29)):
            button = AppButton(key, variant="tonal", size="compact")
            button.clicked.connect(
                lambda _c=False, d=days: self._apply(today.addDays(-d), today, close=True)
            )
            presets.addWidget(button)
        presets.addStretch(1)
        popup.content.addLayout(presets)
        self._hint = TrText("date.pick_start", "caption", "secondary")
        popup.content.addWidget(self._hint)
        calendar = QCalendarWidget()
        calendar.setGridVisible(False)
        calendar.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        calendar.setHorizontalHeaderFormat(QCalendarWidget.HorizontalHeaderFormat.ShortDayNames)
        calendar.setFirstDayOfWeek(Qt.DayOfWeek.Monday)
        calendar.setSelectedDate(self._end)
        calendar.setFont(font_for(TYPE.body))
        calendar.clicked.connect(self._clicked)
        self._calendar = calendar
        self._picking_end = False
        self._paint_range()
        popup.content.addWidget(calendar)
        popup.closed.connect(self._closed)
        self._popup = popup
        popup.open_at(self, width=SIZES.select_max)
        calendar.setFocus()

    def _clicked(self, day: QDate) -> None:
        if not self._picking_end:
            self._start = self._end = day
            self._picking_end = True
            self._hint.set_key("date.pick_end")
            self._paint_range()
            return
        self._apply(self._start, day, close=True)

    def _apply(self, start: QDate, end: QDate, *, close: bool) -> None:
        self.set_range(start, end)
        if close and self._popup is not None:
            self._popup.close()

    def _paint_range(self) -> None:
        calendar = self._calendar
        calendar.setDateTextFormat(QDate(), QTextCharFormat())
        inside = QTextCharFormat()
        inside.setBackground(QColor(COLORS.primary_cont))
        inside.setForeground(QColor(COLORS.on_primary_cont))
        day = self._start
        while day <= self._end:
            calendar.setDateTextFormat(day, inside)
            day = day.addDays(1)

    def _closed(self) -> None:
        popup = self._popup
        self._popup = None
        if popup is not None:
            popup.deleteLater()
        self.update()

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())
        fill, border, width = _field_colors(self, self.hasFocus() or self._popup is not None)
        fill_rounded(painter, rect, RADIUS.control, fill, border, width)
        side = SIZES.icon_m
        icon = QRectF(rect.left() + SPACE.l, rect.center().y() - side / 2, side, side)
        paint_icon(painter, "calendar_month", icon, COLORS.text_2)
        draw_line(painter, QRectF(icon.right() + SPACE.m, rect.top(), rect.right() - icon.right() - SPACE.xl, rect.height()),
                  self.text(), TYPE.body, COLORS.text)
        painter.end()


class FormField(QWidget):
    """Label above the control (8 px), helper / error text below."""

    def __init__(
        self,
        label_key: str,
        editor: QWidget,
        *,
        helper_key: str | None = None,
        parent: QWidget | None = None,
        **params: Any,
    ) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACE.s)
        self.label = TrText(label_key, "label", "secondary", **params)
        self.editor = editor
        layout.addWidget(self.label)
        layout.addWidget(editor)
        self._helper_key = helper_key
        self.helper = Text("", "caption", "tertiary", wrap=True)
        self.helper.set_key(helper_key)
        self.helper.setVisible(bool(helper_key))
        layout.addWidget(self.helper)

    def set_error(self, message: str | None) -> None:
        set_prop(self.editor, "invalid", bool(message))
        self.editor.update()
        if message:
            self.helper.setText(message)
            self.helper.set_tone("danger")
            self.helper.setVisible(True)
        else:
            self.helper.set_key(self._helper_key)
            self.helper.set_tone("tertiary")
            self.helper.setVisible(bool(self._helper_key))
