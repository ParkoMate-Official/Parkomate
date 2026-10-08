"""Tabs: Material-style 48 px tabs with an animated underline indicator (A6). Every tab is
as wide as its longest translation, so the tab row never moves on a language switch."""

from __future__ import annotations

import math

from PySide6.QtCore import QEvent, QRectF, QSize, Qt
from PySide6.QtGui import QPainter, QPaintEvent
from PySide6.QtWidgets import QTabBar, QTabWidget, QWidget

from parkomate.i18n import t
from parkomate.ui.components.base import (
    draw_line,
    fill_rounded,
    key_width,
    on_language_change,
    qcolor,
)
from parkomate.ui.theme.fonts import font_for
from parkomate.ui.theme.motion import Tween
from parkomate.ui.theme.tokens import ALPHA, COLORS, MOTION, RADIUS, SIZES, SPACE, TYPE


class _TabBar(QTabBar):
    def __init__(self, tabs: Tabs) -> None:
        super().__init__(tabs)
        self.tabs = tabs
        self._position = Tween(self, lambda _v: self.update(), ms=MOTION.medium)
        self._hovered = -1
        self.setFont(font_for(TYPE.label))
        self.setDrawBase(False)
        self.setExpanding(False)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setProperty("ring_radius", RADIUS.chip)
        self.currentChanged.connect(lambda index: self._position.to(float(index)))

    def tabSizeHint(self, index: int) -> QSize:
        key = self.tabs.key(index)
        width = key_width(font_for(TYPE.body_strong), key) + 2 * SPACE.xl
        return QSize(width, SIZES.tab)

    def minimumTabSizeHint(self, index: int) -> QSize:
        return self.tabSizeHint(index)

    def mouseMoveEvent(self, event: object) -> None:
        self._hovered = self.tabAt(event.position().toPoint())  # type: ignore[attr-defined]
        self.update()
        super().mouseMoveEvent(event)  # type: ignore[arg-type]

    def leaveEvent(self, event: QEvent) -> None:
        self._hovered = -1
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, _event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        current = self.currentIndex()
        for index in range(self.count()):
            rect = QRectF(self.tabRect(index))
            if index == self._hovered and index != current:
                fill_rounded(
                    painter,
                    rect.adjusted(0, SPACE.xs, 0, -SPACE.xs),
                    RADIUS.chip,
                    qcolor(COLORS.text, ALPHA.hover),
                )
            selected = index == current
            draw_line(
                painter,
                rect,
                self.tabText(index).replace("&&", "&"),
                TYPE.body_strong if selected else TYPE.body,
                COLORS.primary if selected else COLORS.text_2,
                align=Qt.AlignmentFlag.AlignHCenter,
            )
        if self.count():
            position = max(0.0, min(self._position.value, self.count() - 1))
            low = math.floor(position)
            high = min(low + 1, self.count() - 1)
            k = position - low
            a, b = QRectF(self.tabRect(low)), QRectF(self.tabRect(high))
            inset = SPACE.l
            left = a.left() + (b.left() - a.left()) * k + inset
            right = a.right() + (b.right() - a.right()) * k - inset
            bar = SIZES.tab_indicator
            fill_rounded(
                painter,
                QRectF(left, self.height() - bar, right - left, bar),
                bar / 2,
                COLORS.primary,
            )
        painter.end()


class Tabs(QTabWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._keys: list[str] = []
        self.setTabBar(_TabBar(self))
        self.setDocumentMode(True)
        self.setUsesScrollButtons(False)
        on_language_change(self, self.retranslate)

    def key(self, index: int) -> str:
        return self._keys[index] if 0 <= index < len(self._keys) else ""

    def add_tab(self, widget: QWidget, key: str) -> int:
        self._keys.append(key)
        index = self.addTab(widget, "")
        self.retranslate()
        return index

    def retranslate(self, *_args: object) -> None:
        for index, key in enumerate(self._keys):
            self.setTabText(index, t(key).replace("&", "&&"))  # '&' is not a mnemonic
