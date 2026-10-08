"""Popup (a floating card with the one soft shadow) and Menu (rows of actions)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QEvent, QPoint, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QGuiApplication, QKeyEvent, QPainter, QPaintEvent
from PySide6.QtWidgets import QAbstractButton, QFrame, QSizePolicy, QVBoxLayout, QWidget

from parkomate.i18n import t
from parkomate.ui.components.base import Divider, add_shadow, draw_line, fill_rounded, key_width, on_language_change, qcolor
from parkomate.ui.components.icons import paint_icon
from parkomate.ui.theme.fonts import font_for, line_box
from parkomate.ui.theme.tokens import ALPHA, COLORS, RADIUS, SIZES, SPACE, TYPE


class _PopupCard(QFrame):
    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        fill_rounded(painter, QRectF(self.rect()), RADIUS.control, COLORS.surface, COLORS.outline, SIZES.hairline)
        painter.end()


class Popup(QWidget):
    """Top-level popup: translucent margin for the shadow, a rounded card inside."""

    closed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            parent,
            Qt.WindowType.Popup
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.NoDropShadowWindowHint,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        margin = SIZES.shadow_margin
        outer = QVBoxLayout(self)
        outer.setContentsMargins(margin, margin // 2, margin, margin + SPACE.s)
        self.card = _PopupCard()
        add_shadow(self.card)
        outer.addWidget(self.card)
        self.content = QVBoxLayout(self.card)
        self.content.setContentsMargins(SPACE.xs, SPACE.s, SPACE.xs, SPACE.s)
        self.content.setSpacing(0)

    def open_at(self, anchor: QWidget, *, width: int | None = None, align_right: bool = False) -> None:
        margins = self.layout().contentsMargins()
        self.adjustSize()
        card_width = width or self.card.sizeHint().width()
        self.resize(
            card_width + margins.left() + margins.right(),
            min(self.sizeHint().height(), SIZES.popup_max_height + margins.top() + margins.bottom()),
        )
        below = anchor.mapToGlobal(QPoint(0, anchor.height() + SIZES.popup_offset))
        x = below.x() - margins.left()
        if align_right:
            x = anchor.mapToGlobal(QPoint(anchor.width(), 0)).x() - card_width - margins.left()
        y = below.y() - margins.top()
        screen = QGuiApplication.screenAt(below) or QGuiApplication.primaryScreen()
        if screen is not None:
            area: QRect = screen.availableGeometry()
            if y + self.height() > area.bottom():
                above = anchor.mapToGlobal(QPoint(0, 0)).y() - SIZES.popup_offset
                y = above - self.height() + margins.bottom()
            x = max(area.left(), min(x, area.right() - self.width()))
        self.move(x, y)
        self.show()
        self.raise_()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 - Qt API
        if event.key() == Qt.Key.Key_Escape:
            self.close()
            return
        super().keyPressEvent(event)

    def hideEvent(self, event: Any) -> None:  # noqa: N802 - Qt API
        super().hideEvent(event)
        self.closed.emit()


class MenuItem(QAbstractButton):
    """Icon + label (+ a caption saying why it is disabled)."""

    def __init__(
        self,
        key: str,
        icon: str,
        *,
        danger: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.key = key
        self.icon_name = icon
        self.danger = danger
        self.reason_key: str | None = None
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setProperty("ring_radius", RADIUS.chip)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        on_language_change(self, self.retranslate)
        self.retranslate()

    def set_reason(self, key: str | None) -> None:
        self.reason_key = key
        self.retranslate()

    def retranslate(self, *_args: object) -> None:
        self.setText(t(self.key))
        reason = t(self.reason_key) if self.reason_key and not self.isEnabled() else ""
        self.setToolTip(reason)
        self.setAccessibleName(self.text())
        self.setAccessibleDescription(reason)
        self.updateGeometry()
        self.update()

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 - Qt API
        if event.type() == QEvent.Type.EnabledChange:
            self.retranslate()
        super().changeEvent(event)

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt API
        width = SPACE.l * 2 + SIZES.icon + SPACE.m + key_width(font_for(TYPE.body), self.key)
        if self.reason_key:
            width = max(width, SPACE.l * 2 + SIZES.icon + SPACE.m + key_width(font_for(TYPE.caption), self.reason_key))
        height = SIZES.button if self.reason_key and not self.isEnabled() else SIZES.button_compact + SPACE.xs
        return QSize(width, height)

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
        if self.isEnabled() and (self.underMouse() or self.hasFocus()):
            fill_rounded(painter, rect, RADIUS.chip, qcolor(COLORS.text, ALPHA.hover))
        color = COLORS.on_danger_cont if self.danger else COLORS.text
        if not self.isEnabled():
            color = COLORS.text_3
        side = SIZES.icon
        paint_icon(
            painter,
            self.icon_name,
            QRectF(rect.left() + SPACE.l, rect.center().y() - side / 2, side, side),
            color if self.danger or not self.isEnabled() else COLORS.text_2,
        )
        x = rect.left() + SPACE.l + side + SPACE.m
        reason = t(self.reason_key) if self.reason_key and not self.isEnabled() else ""
        body = line_box(TYPE.body)
        caption = line_box(TYPE.caption)
        total = body.height + (caption.height if reason else 0)
        top = rect.center().y() - total / 2
        draw_line(painter, QRectF(x, top, rect.right() - x - SPACE.l, body.height),
                  self.text(), TYPE.body, color)
        if reason:
            draw_line(painter, QRectF(x, top + body.height, rect.right() - x - SPACE.l, caption.height),
                      reason, TYPE.caption, COLORS.text_3)
        painter.end()


class Menu(Popup):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.items: list[MenuItem] = []

    def add_header(self, widget: QWidget) -> None:
        self.content.addWidget(widget)
        self.content.addSpacing(SPACE.xs)
        self.content.addWidget(Divider())
        self.content.addSpacing(SPACE.xs)

    def add_item(
        self, key: str, icon: str, callback: Callable[[], object], *, danger: bool = False
    ) -> MenuItem:
        item = MenuItem(key, icon, danger=danger)

        def run() -> None:
            self.close()
            callback()

        item.clicked.connect(run)
        self.items.append(item)
        self.content.addWidget(item)
        return item

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 - Qt API
        enabled = [i for i in self.items if i.isEnabled() and i.isVisible()]
        if event.key() in (Qt.Key.Key_Down, Qt.Key.Key_Up) and enabled:
            current = next((i for i in enabled if i.hasFocus()), None)
            index = enabled.index(current) if current in enabled else -1
            step = 1 if event.key() == Qt.Key.Key_Down else -1
            enabled[(index + step) % len(enabled)].setFocus(Qt.FocusReason.TabFocusReason)
            return
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            current = next((i for i in enabled if i.hasFocus()), None)
            if current is not None:
                current.click()
                return
        super().keyPressEvent(event)
