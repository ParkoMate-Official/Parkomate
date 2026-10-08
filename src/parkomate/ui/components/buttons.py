"""AppButton, IconButton, and the painters they share (key cap chip, spinner).

AppButton variants: filled (THE primary action - one per screen), tonal, outlined, text,
danger_filled, danger_tonal, success_filled, on_takeover. Sizes: large (56 px) and compact
(44 px). Optional leading icon, key-cap chip ("Enter") on the right, loading spinner.
``text()`` is always just the label (shortcut hints are painted, never part of the text).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QEvent, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFontMetricsF, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QAbstractButton, QPushButton, QSizePolicy, QWidget

from parkomate.i18n import t
from parkomate.ui.components.base import (
    draw_line,
    fill_rounded,
    key_width,
    mix,
    on_language_change,
    qcolor,
)
from parkomate.ui.components.icons import paint_icon
from parkomate.ui.theme.fonts import font_for
from parkomate.ui.theme.motion import FrameClock, Tween
from parkomate.ui.theme.tokens import ALPHA, COLORS, MOTION, RADIUS, SIZES, SPACE, TYPE

LEGACY_VARIANTS = {
    "primary": "filled",
    "secondary": "outlined",
    "danger": "danger_tonal",
    "pass": "success_filled",
    "success": "success_filled",
    "link": "text",
    "takeover": "on_takeover",
    "toggle": "outlined",
}
VARIANTS = (
    "filled",
    "tonal",
    "outlined",
    "text",
    "danger_filled",
    "danger_tonal",
    "success_filled",
    "on_takeover",
)


@dataclass(frozen=True, slots=True)
class ButtonColors:
    fill: str | None
    content: str
    border: str | None
    hover: str  # state-layer colour
    hover_fill: str | None = None  # filled variants darken to this instead


def button_colors(variant: str, enabled: bool) -> ButtonColors:
    c = COLORS
    if not enabled:
        if variant in ("outlined", "text"):
            return ButtonColors(None, c.text_3, c.outline_soft if variant == "outlined" else None, c.text)
        return ButtonColors(c.surface_3, c.text_3, None, c.text)
    return {
        "filled": ButtonColors(c.primary, c.on_primary, None, c.on_primary, c.primary_pressed),
        "tonal": ButtonColors(c.primary_cont, c.on_primary_cont, None, c.on_primary_cont),
        "outlined": ButtonColors(None, c.text, c.outline_strong, c.text),
        "text": ButtonColors(None, c.primary, None, c.primary),
        "danger_filled": ButtonColors(c.danger, c.on_status, None, c.on_status, c.danger_hov),
        "danger_tonal": ButtonColors(c.danger_cont, c.on_danger_cont, None, c.on_danger_cont),
        "success_filled": ButtonColors(
            c.on_success_cont, c.on_status, None, c.on_status, c.success_hov
        ),
        "on_takeover": ButtonColors(c.surface, c.takeover, None, c.takeover),
    }.get(variant, ButtonColors(None, c.text, c.outline_strong, c.text))


def keycap_size(text: str) -> QSize:
    font = font_for(TYPE.keycap)
    width = math.ceil(QFontMetricsF(font).horizontalAdvance(text)) + 2 * SIZES.keycap_pad
    return QSize(max(width, SIZES.keycap), SIZES.keycap)


def paint_keycap(painter: QPainter, rect: QRectF, text: str, color: str) -> None:
    """Small rounded key cap ('Enter', 'F1') at 70 % of the content colour."""
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    tint = qcolor(color, ALPHA.keycap)
    pen = QPen(tint, SIZES.hairline)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    inset = SIZES.hairline / 2
    painter.drawRoundedRect(
        rect.adjusted(inset, inset, -inset, -inset), RADIUS.keycap, RADIUS.keycap
    )
    draw_line(painter, rect, text, TYPE.keycap, tint, align=Qt.AlignmentFlag.AlignHCenter)
    painter.restore()


def paint_spinner(painter: QPainter, rect: QRectF, color: str, phase: float) -> None:
    """Indeterminate arc (the 'working' spinner)."""
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    stroke = SIZES.spinner_stroke * rect.width() / SIZES.spinner
    area = rect.adjusted(stroke / 2, stroke / 2, -stroke / 2, -stroke / 2)
    track = QPen(qcolor(color, ALPHA.track), stroke)
    painter.setPen(track)
    painter.drawEllipse(area)
    pen = QPen(QColor(color), stroke)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    start = int((90 - phase * 360) * 16)
    painter.drawArc(area, start, -100 * 16)
    painter.restore()


class AppButton(QPushButton):
    def __init__(
        self,
        key: str = "",
        *,
        variant: str = "outlined",
        size: str = "large",
        icon: str | None = None,
        hint_key: str | None = None,
        parent: QWidget | None = None,
        **params: Any,
    ) -> None:
        super().__init__(parent)
        self._key = key
        self._params = params
        self._hint_key = hint_key
        self._variant = LEGACY_VARIANTS.get(variant, variant)
        self._compact = size == "compact"
        self._icon = icon
        self._loading = False
        self._hover = Tween(self, lambda _v: self.update(), ms=MOTION.fast)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAutoDefault(False)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setProperty("ring_radius", RADIUS.control)
        on_language_change(self, self.retranslate)
        self.retranslate()

    # ------------------------------------------------------------------ API
    def set_text_key(self, key: str, **params: Any) -> None:
        if (key, params) != (self._key, self._params):
            self._key = key
            self._params = params
            self.retranslate()

    def set_hint_key(self, hint_key: str | None) -> None:
        if hint_key != self._hint_key:
            self._hint_key = hint_key
            self.retranslate()

    def set_variant(self, variant: str) -> None:
        variant = LEGACY_VARIANTS.get(variant, variant)
        if variant != self._variant:
            self._variant = variant
            self.update()

    def variant(self) -> str:
        return self._variant

    def set_icon(self, icon: str | None) -> None:
        if icon != self._icon:
            self._icon = icon
            self.updateGeometry()
            self.update()

    def set_loading(self, loading: bool) -> None:
        if loading == self._loading:
            return
        self._loading = loading
        clock = FrameClock.instance()
        if loading:
            clock.subscribe(self, self.update)
        else:
            clock.unsubscribe(self)
        self.updateGeometry()
        self.update()

    def is_loading(self) -> bool:
        return self._loading

    def label(self) -> str:
        return t(self._key, **self._params) if self._key else ""

    def hint(self) -> str:
        return t(self._hint_key) if self._hint_key else ""

    def retranslate(self, *_args: object) -> None:
        label = self.label()
        self.setText(label)
        self.setAccessibleName(label)
        self.updateGeometry()
        self.update()

    # ------------------------------------------------------------------ geometry
    @property
    def _style(self) -> Any:
        return TYPE.button_sm if self._compact else TYPE.button

    def _height(self) -> int:
        return SIZES.button_compact if self._compact else SIZES.button

    def _pad(self) -> int:
        return SIZES.button_pad_compact if self._compact else SIZES.button_pad

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt API
        font = font_for(self._style)
        width = 2 * self._pad()
        label_width = key_width(font, self._key, **self._params) if self._key else 0
        width += label_width
        if self._icon or self._loading:
            width += SIZES.icon + (SIZES.icon_gap if label_width else 0)
        if self._hint_key:
            width += SPACE.m + max(keycap_size(text).width() for text in self._hint_texts())
        minimum = SIZES.button_min_width if label_width else self._height()
        return QSize(max(width, minimum), self._height())

    def minimumSizeHint(self) -> QSize:  # noqa: N802 - Qt API
        return self.sizeHint()

    def _hint_texts(self) -> list[str]:
        from parkomate.ui.components.base import translations

        return translations(self._hint_key) if self._hint_key else []

    # ------------------------------------------------------------------ painting
    def enterEvent(self, event: QEvent) -> None:  # noqa: N802 - Qt API
        self._hover.to(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent) -> None:  # noqa: N802 - Qt API
        self._hover.to(0.0)
        super().leaveEvent(event)

    def _colors(self) -> ButtonColors:
        return button_colors(self._variant, self.isEnabled())

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())
        colors = self._colors()
        radius = RADIUS.control
        fill: QColor | None = QColor(colors.fill) if colors.fill else None
        if self.isEnabled():
            if colors.hover_fill and colors.fill:
                amount = 1.0 if self.isDown() else 0.5 * self._hover.value
                if amount > 0:
                    fill = mix(colors.fill, colors.hover_fill, amount)
            else:
                layer = ALPHA.pressed if self.isDown() else ALPHA.hover * self._hover.value
                if layer > 0:
                    if colors.fill is None:
                        fill = qcolor(colors.hover, layer)
                    else:
                        fill = mix(colors.fill, colors.hover, layer)
        fill_rounded(
            painter,
            rect,
            radius,
            fill,
            colors.border,
            SIZES.hairline if colors.border else 0,
        )
        self._paint_content(painter, rect, colors.content)
        painter.end()

    def _paint_content(self, painter: QPainter, rect: QRectF, content: str) -> None:
        pad = self._pad()
        inner = rect.adjusted(pad, 0, -pad, 0)
        hint = self.hint()
        if hint:
            cap = keycap_size(hint)
            cap_rect = QRectF(
                inner.right() - cap.width(),
                rect.center().y() - cap.height() / 2,
                cap.width(),
                cap.height(),
            )
            paint_keycap(painter, cap_rect, hint, content)
            inner.setRight(cap_rect.left() - SPACE.m)
        font = font_for(self._style)
        painter.setFont(font)
        label = self.text()
        metrics = QFontMetricsF(font)
        label_width = metrics.horizontalAdvance(label)
        icon_name = "progress_activity" if self._loading else self._icon
        group = label_width + (SIZES.icon + (SIZES.icon_gap if label else 0) if icon_name else 0)
        x = inner.left() + max(0.0, (inner.width() - group) / 2)
        if icon_name:
            icon_rect = QRectF(x, rect.center().y() - SIZES.icon / 2, SIZES.icon, SIZES.icon)
            if self._loading:
                paint_spinner(
                    painter, icon_rect, content, FrameClock.instance().phase(MOTION.spin_period)
                )
            else:
                paint_icon(painter, icon_name, icon_rect, content)
            x += SIZES.icon + (SIZES.icon_gap if label else 0)
        if label:
            draw_line(painter, QRectF(x, rect.top(), inner.right() - x + 1, rect.height()),
                      label, self._style, content)


class IconButton(QAbstractButton):
    """Square icon-only button (44 px by default) with a tooltip / accessible name."""

    def __init__(
        self,
        icon: str,
        tip_key: str = "",
        *,
        size: int = SIZES.button_compact,
        icon_size: int = SIZES.icon_m,
        color: str = COLORS.text_2,
        parent: QWidget | None = None,
        **params: Any,
    ) -> None:
        super().__init__(parent)
        self._icon = icon
        self._tip_key = tip_key
        self._params = params
        self._size = size
        self._icon_size = icon_size
        self._color = color
        self._hover = Tween(self, lambda _v: self.update(), ms=MOTION.fast)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFixedSize(size, size)
        self.setProperty("ring_radius", size // 2)
        on_language_change(self, self.retranslate)
        self.retranslate()

    def set_icon(self, icon: str) -> None:
        self._icon = icon
        self.update()

    def set_tip_key(self, key: str, **params: Any) -> None:
        self._tip_key = key
        self._params = params
        self.retranslate()

    def retranslate(self, *_args: object) -> None:
        text = t(self._tip_key, **self._params) if self._tip_key else ""
        self.setToolTip(text)
        self.setAccessibleName(text)

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt API
        return QSize(self._size, self._size)

    def enterEvent(self, event: QEvent) -> None:  # noqa: N802 - Qt API
        self._hover.to(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent) -> None:  # noqa: N802 - Qt API
        self._hover.to(0.0)
        super().leaveEvent(event)

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())
        layer = ALPHA.pressed if self.isDown() else ALPHA.hover * self._hover.value
        if self.isChecked():
            layer = max(layer, ALPHA.hover)
        if layer > 0 and self.isEnabled():
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(qcolor(COLORS.text, layer))
            painter.drawEllipse(rect)
        color = self._color if self.isEnabled() else COLORS.text_3
        side = self._icon_size
        paint_icon(
            painter,
            self._icon,
            QRectF(rect.center().x() - side / 2, rect.center().y() - side / 2, side, side),
            color,
        )
        painter.end()
