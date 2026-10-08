"""Chips: StatusChip, KeyCap, SimulationChip, CounterChip / CounterChips.

StatusChip = icon + word + colour (never colour alone). Pending is deliberately quiet (no
fill, small grey clock) so a screen full of not-started steps is calm (G6); only the active
step and results carry emphasis.
"""

from __future__ import annotations

import math
from typing import Any

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QFontMetricsF, QPainter, QPaintEvent
from PySide6.QtWidgets import QHBoxLayout, QSizePolicy, QWidget

from parkomate.i18n import t
from parkomate.ui.components.base import (
    draw_line,
    fill_rounded,
    key_width,
    on_language_change,
    translations,
)
from parkomate.ui.components.buttons import keycap_size, paint_keycap, paint_spinner
from parkomate.ui.components.icons import paint_icon
from parkomate.ui.theme.fonts import font_for
from parkomate.ui.theme.motion import FrameClock
from parkomate.ui.theme.tokens import COLORS, MOTION, RADIUS, SIZES, SPACE, TYPE

# state -> (tone, icon, default word key)
CHIP_STATES: dict[str, tuple[str, str, str]] = {
    "success": ("success", "check_circle", "status.word.pass"),
    "danger": ("danger", "cancel", "status.word.fail"),
    "warning": ("warning", "warning", "status.word.warn"),
    "info": ("info", "info", "status.word.info"),
    "working": ("info", "progress_activity", "status.word.working"),
    "neutral": ("neutral", "schedule", "status.word.pending"),
}
LEGACY_STATES = {
    "pass": "success",
    "fail": "danger",
    "warn": "warning",
    "error": "warning",
    "pending": "neutral",
}


class StatusChip(QWidget):
    def __init__(
        self,
        state: str = "neutral",
        key: str | None = None,
        *,
        compact: bool = False,
        parent: QWidget | None = None,
        **params: Any,
    ) -> None:
        super().__init__(parent)
        self._compact = compact
        self._state = "neutral"
        self._key: str | None = None
        self._params: dict[str, Any] = {}
        self._reserve_keys: list[str] = []
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        on_language_change(self, self._retranslate)
        self.set_state(state, key, **params)

    # ------------------------------------------------------------------ API
    def set_state(self, state: str, key: str | None = None, **params: Any) -> None:
        state = LEGACY_STATES.get(state, state)
        if state not in CHIP_STATES:
            state = "neutral"
        was_working = self._state == "working"
        self._state = state
        self._key = key
        self._params = params
        clock = FrameClock.instance()
        if state == "working":
            clock.subscribe(self, self.update)
        elif was_working:
            clock.unsubscribe(self)
        self._retranslate()

    def reserve(self, *keys: str) -> None:
        """Reserve room for these words too (so the chip never changes width)."""
        self._reserve_keys = list(keys)
        self.updateGeometry()

    def state(self) -> str:
        return self._state

    def tone(self) -> str:
        return CHIP_STATES[self._state][0]

    def word_key(self) -> str:
        return self._key or CHIP_STATES[self._state][2]

    def text(self) -> str:
        return t(self.word_key(), **self._params)

    def _retranslate(self, *_args: object) -> None:
        self.setAccessibleName(self.text())
        self.updateGeometry()
        self.update()

    # ------------------------------------------------------------------ geometry
    @property
    def _style(self) -> Any:
        return TYPE.caption if self._compact else TYPE.label

    def _height(self) -> int:
        return SIZES.chip_compact if self._compact else SIZES.chip

    def _icon(self) -> int:
        return SIZES.icon_s if self._compact else SIZES.icon

    def _pad(self) -> int:
        return SPACE.s if self._compact else SPACE.m

    def sizeHint(self) -> QSize:
        font = font_for(self._style)
        keys = [self.word_key(), *self._reserve_keys]
        word = max(key_width(font, k, **self._params) for k in keys)
        return QSize(2 * self._pad() + self._icon() + SPACE.s + word, self._height())

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    # ------------------------------------------------------------------ painting
    def paintEvent(self, _event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        tone, icon, _ = CHIP_STATES[self._state]
        graphic, container, on_container = COLORS.status(tone)
        rect = QRectF(self.rect())
        quiet = self._state == "neutral"
        if not quiet:
            fill_rounded(painter, rect, RADIUS.chip, container)
        text_color = COLORS.text_3 if quiet else on_container
        side = self._icon()
        x = rect.left() + (0 if quiet else self._pad())
        icon_rect = QRectF(x, rect.center().y() - side / 2, side, side)
        if self._state == "working":
            paint_spinner(
                painter, icon_rect, graphic, FrameClock.instance().phase(MOTION.spin_period)
            )
        else:
            paint_icon(
                painter, icon, icon_rect, COLORS.text_3 if quiet else graphic, filled=not quiet
            )
        text_x = icon_rect.right() + SPACE.s
        draw_line(
            painter,
            QRectF(text_x, rect.top(), rect.right() - text_x, rect.height()),
            self.text(),
            self._style,
            text_color,
        )
        painter.end()


class KeyCap(QWidget):
    """A standalone key cap chip ('F1') - used on checklist rows."""

    def __init__(self, key: str, color: str = COLORS.text_2, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._key = key
        self._color = color
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        on_language_change(self, self._refresh)

    def _refresh(self, *_args: object) -> None:
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(max(keycap_size(x).width() for x in translations(self._key)), SIZES.keycap)

    def paintEvent(self, _event: QPaintEvent) -> None:
        painter = QPainter(self)
        paint_keycap(painter, QRectF(self.rect()), t(self._key), self._color)
        painter.end()


class SimulationChip(StatusChip):
    """Amber 'Simulation mode' chip; the scenario is in the tooltip."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("warning", "sim.chip", parent=parent)
        self._scenario = ""

    def set_scenario(self, scenario: str) -> None:
        self._scenario = scenario
        self._retranslate()

    def _retranslate(self, *_args: object) -> None:
        super()._retranslate()
        tip = t("sim.tooltip", scenario=getattr(self, "_scenario", "") or "-")
        self.setToolTip(tip)
        self.setAccessibleDescription(tip)

    def paintEvent(self, _event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())
        inset = SIZES.hairline / 2
        fill_rounded(
            painter, rect, RADIUS.chip, COLORS.warning_cont, COLORS.warning, SIZES.hairline
        )
        side = self._icon()
        icon_rect = QRectF(rect.left() + self._pad(), rect.center().y() - side / 2, side, side)
        paint_icon(painter, "warning", icon_rect, COLORS.warning, filled=True)
        text_x = icon_rect.right() + SPACE.s
        draw_line(
            painter,
            QRectF(text_x, rect.top() + inset, rect.right() - text_x, rect.height() - 2 * inset),
            self.text(),
            TYPE.label,
            COLORS.on_warning_cont,
        )
        painter.end()


class CounterChip(QWidget):
    """Icon + number (+ optional word) for the context bar; the meaning is in the tooltip."""

    def __init__(
        self,
        icon: str,
        icon_color: str,
        tip_key: str,
        word_key: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._icon = icon
        self._icon_color = icon_color
        self._tip_key = tip_key
        self._word_key = word_key
        self._value = "0"
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        on_language_change(self, self._retranslate)
        self._retranslate()

    def set_value(self, value: int | str) -> None:
        self._value = str(value)
        self._retranslate()

    def value(self) -> str:
        return self._value

    def _retranslate(self, *_args: object) -> None:
        tip = t(self._tip_key, n=self._value)
        self.setToolTip(tip)
        self.setAccessibleName(tip)
        self.updateGeometry()
        self.update()

    def sizeHint(self) -> QSize:
        number = math.ceil(QFontMetricsF(font_for(TYPE.body_strong)).horizontalAdvance("000"))
        word = key_width(font_for(TYPE.label), self._word_key) + SPACE.s if self._word_key else 0
        return QSize(2 * SPACE.m + SIZES.icon + SPACE.s + word + number, SIZES.chip)

    def paintEvent(self, _event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())
        fill_rounded(
            painter, rect, RADIUS.chip, COLORS.surface, COLORS.outline_soft, SIZES.hairline
        )
        side = SIZES.icon
        icon_rect = QRectF(rect.left() + SPACE.m, rect.center().y() - side / 2, side, side)
        paint_icon(painter, self._icon, icon_rect, self._icon_color, filled=True)
        x = icon_rect.right() + SPACE.s
        if self._word_key:
            word = t(self._word_key)
            width = draw_line(
                painter,
                QRectF(x, rect.top(), rect.right() - x, rect.height()),
                word,
                TYPE.label,
                COLORS.text_2,
                elide=False,
            )
            x += width + SPACE.s
        draw_line(
            painter,
            QRectF(x, rect.top(), rect.right() - x, rect.height()),
            self._value,
            TYPE.body_strong,
            COLORS.text,
        )
        painter.end()


class CounterChips(QWidget):
    """Uploads OK · uploads failed · completed · rejected (the one counter group, T5)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACE.s)
        self.uploads_ok = CounterChip("check_circle", COLORS.success, "counter.tip.uploads_ok")
        self.uploads_fail = CounterChip("cancel", COLORS.danger, "counter.tip.uploads_fail")
        self.completed = CounterChip(
            "task_alt", COLORS.primary, "counter.tip.completed", "counter.completed"
        )
        self.rejected = CounterChip(
            "block", COLORS.danger, "counter.tip.rejected", "counter.rejected"
        )
        for chip in (self.uploads_ok, self.uploads_fail, self.completed, self.rejected):
            layout.addWidget(chip)

    def set_counts(self, ok: int, fail: int, completed: int, rejected: int) -> None:
        self.uploads_ok.set_value(ok)
        self.uploads_fail.set_value(fail)
        self.completed.set_value(completed)
        self.rejected.set_value(rejected)

    def summary(self) -> str:
        return " · ".join(
            chip.toolTip()
            for chip in (self.uploads_ok, self.uploads_fail, self.completed, self.rejected)
        )
