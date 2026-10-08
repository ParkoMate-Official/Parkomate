"""Shared helpers for components: dynamic properties, colours, shadows, and language-stable
sizes.

Language-stable sizes: a component that shows a translated text reserves the width of the
LONGEST translation (English or Marathi), so switching language never moves anything.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable
from typing import Any

from PySide6.QtCore import QObject, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPainterPath
from PySide6.QtWidgets import QGraphicsDropShadowEffect, QWidget

from parkomate.i18n import LANGUAGES, t, tr
from parkomate.ui.qt_i18n import language_notifier
from parkomate.ui.theme.tokens import ALPHA, COLORS, ELEVATION


def restyle(widget: QWidget) -> None:
    """Re-apply the stylesheet after changing a dynamic property."""
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()


def set_prop(widget: QWidget, name: str, value: Any) -> None:
    if widget.property(name) != value:
        widget.setProperty(name, value)
        restyle(widget)


def qcolor(value: str, alpha: float = 1.0) -> QColor:
    color = QColor(value)
    color.setAlphaF(max(0.0, min(1.0, alpha)))
    return color


def mix(a: str, b: str, amount: float) -> QColor:
    """``a`` blended towards ``b`` by ``amount`` (0..1)."""
    ca, cb = QColor(a), QColor(b)
    k = max(0.0, min(1.0, amount))
    return QColor.fromRgbF(
        ca.redF() + (cb.redF() - ca.redF()) * k,
        ca.greenF() + (cb.greenF() - ca.greenF()) * k,
        ca.blueF() + (cb.blueF() - ca.blueF()) * k,
        ca.alphaF() + (cb.alphaF() - ca.alphaF()) * k,
    )


def translations(key: str, **params: Any) -> list[str]:
    """``key`` rendered in every UI language."""
    return [tr(language, key, **params) for language in LANGUAGES]


def text_width(font: QFont, texts: Iterable[str]) -> int:
    metrics = QFontMetricsF(font)
    return math.ceil(max((metrics.horizontalAdvance(text) for text in texts), default=0.0))


def key_width(font: QFont, key: str, **params: Any) -> int:
    """Width of the longest translation of ``key``."""
    return text_width(font, translations(key, **params)) if key else 0


def on_language_change(owner: QObject, slot: Callable[..., object]) -> None:
    """Connect ``slot`` (a bound method of ``owner``) to language changes.

    PySide disconnects a bound method automatically when its QObject is deleted, so no
    bookkeeping is needed - but never pass a lambda (it would outlive the widget)."""
    del owner
    language_notifier().changed.connect(slot)


def tr_key(key: str | None, **params: Any) -> str:
    return t(key, **params) if key else ""


def add_shadow(widget: QWidget) -> QGraphicsDropShadowEffect:
    """The one soft shadow - for floating things only (menus, toasts, popups, drawer)."""
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(ELEVATION.blur)
    effect.setOffset(QPointF(0, ELEVATION.offset_y))
    effect.setColor(qcolor(COLORS.shadow, ALPHA.shadow))
    widget.setGraphicsEffect(effect)
    return effect


def rounded(rect: QRectF, radius: float) -> QPainterPath:
    path = QPainterPath()
    r = min(radius, rect.height() / 2, rect.width() / 2)
    path.addRoundedRect(rect, r, r)
    return path


def fill_rounded(
    painter: QPainter,
    rect: QRectF,
    radius: float,
    fill: QColor | str | None,
    border: QColor | str | None = None,
    border_width: float = 1.0,
) -> None:
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    if border is not None and border_width > 0:
        inset = border_width / 2
        area = rect.adjusted(inset, inset, -inset, -inset)
        pen_color = QColor(border) if isinstance(border, str) else border
        painter.setPen(_pen(pen_color, border_width))
    else:
        area = rect
        painter.setPen(Qt.PenStyle.NoPen)
    if fill is None:
        painter.setBrush(Qt.BrushStyle.NoBrush)
    else:
        painter.setBrush(QColor(fill) if isinstance(fill, str) else fill)
    r = min(radius, area.height() / 2, area.width() / 2)
    painter.drawRoundedRect(area, r, r)
    painter.restore()


def _pen(color: QColor, width: float) -> Any:
    from PySide6.QtGui import QPen

    pen = QPen(color, width)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return pen


class Divider(QWidget):
    """1 px soft divider (horizontal by default)."""

    def __init__(self, vertical: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        from PySide6.QtWidgets import QSizePolicy

        from parkomate.ui.theme.tokens import SIZES

        self._vertical = vertical
        if vertical:
            self.setFixedWidth(SIZES.hairline)
            self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        else:
            self.setFixedHeight(SIZES.hairline)
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def paintEvent(self, _event: object) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(COLORS.outline_soft))
        painter.end()


def draw_line(
    painter: QPainter,
    rect: QRectF,
    text: str,
    style: Any,
    color: str | QColor,
    *,
    align: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignLeft,
    elide: bool = True,
    font: QFont | None = None,
) -> float:
    """Draw one line of ``text`` vertically centred in ``rect`` on the style's FIXED baseline
    (identical for Latin and Devanagari). Returns the drawn width."""
    from parkomate.ui.theme.fonts import font_for, line_box

    used = font or font_for(style)
    painter.save()
    painter.setFont(used)
    painter.setPen(QColor(color) if isinstance(color, str) else color)
    metrics = QFontMetricsF(used)
    shown = text
    width = metrics.horizontalAdvance(text)
    if elide and width > rect.width() + 0.5:
        shown = metrics.elidedText(text, Qt.TextElideMode.ElideRight, rect.width())
        width = metrics.horizontalAdvance(shown)
    if align & Qt.AlignmentFlag.AlignHCenter:
        x = rect.left() + (rect.width() - width) / 2
    elif align & Qt.AlignmentFlag.AlignRight:
        x = rect.right() - width
    else:
        x = rect.left()
    box = line_box(style)
    y = rect.center().y() - box.height / 2 + box.baseline
    painter.drawText(QPointF(x, y), shown)
    painter.restore()
    return width
