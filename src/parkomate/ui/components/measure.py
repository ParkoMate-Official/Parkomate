"""Measurement components: RangeBar (where a value sits in its allowed band), ValueRow (one
row of the electrical check table) and ReadingSlots (the 5 sensor readings, in order).

RangeBar is the one data-viz element of the app (S4): a neutral axis, the allowed band in
green, a marker for the measured value - green inside, red outside - and the limits written
under the band in the same size as the rest of the row.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFontMetricsF, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QSizePolicy, QWidget

from parkomate.ui.components.base import draw_line, fill_rounded, qcolor
from parkomate.ui.components.chips import StatusChip
from parkomate.ui.components.icons import Icon
from parkomate.ui.components.text import Text, TrText
from parkomate.ui.theme.fonts import font_for, line_box
from parkomate.ui.theme.motion import Tween
from parkomate.ui.theme.tokens import ALPHA, COLORS, MOTION, RADIUS, SIZES, SPACE, TYPE


@dataclass(frozen=True, slots=True)
class Band:
    low: float | None  # None = open below (e.g. "max 30.1 °C")
    high: float | None


class RangeBar(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._band: Band | None = None
        self._value: float | None = None
        self._caption = ""
        self._marker = Tween(self, lambda _v: self.update(), ms=MOTION.medium)
        caption = line_box(TYPE.caption).height
        self.setFixedHeight(SIZES.range_marker + SPACE.xs + caption)
        self.setMinimumWidth(SIZES.range_bar_width)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_range(self, band: Band | None, value: float | None, caption: str) -> None:
        self._band = band
        self._caption = caption
        first = self._value is None
        self._value = value
        if value is not None:
            if first:
                self._marker.jump(self._position(value))
            else:
                self._marker.to(self._position(value))
        self.setToolTip(caption)
        self.update()

    def _axis(self) -> tuple[float, float]:
        band = self._band
        if band is None:
            return 0.0, 1.0
        if band.low is not None and band.high is not None:
            span = max(band.high - band.low, 1e-9)
            return band.low - span * 0.75, band.high + span * 0.75
        anchor = band.high if band.high is not None else (band.low or 0.0)
        span = max(abs(anchor) * 0.25, 1.0)
        return anchor - 2 * span, anchor + span

    def _position(self, value: float) -> float:
        low, high = self._axis()
        return max(0.0, min(1.0, (value - low) / (high - low)))

    def inside(self) -> bool | None:
        band, value = self._band, self._value
        if band is None or value is None:
            return None
        return (band.low is None or value >= band.low) and (band.high is None or value <= band.high)

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        width = self.width()
        bar = SIZES.range_bar
        marker = SIZES.range_marker
        cy = marker / 2
        pad = marker / 2
        track = QRectF(pad, cy - bar / 2, width - 2 * pad, bar)
        fill_rounded(painter, track, bar / 2, COLORS.surface_3)
        band = self._band
        if band is not None:
            start = self._position(band.low) if band.low is not None else 0.0
            end = self._position(band.high) if band.high is not None else 1.0
            zone = QRectF(track.left() + track.width() * start, track.top(), track.width() * (end - start), bar)
            fill_rounded(painter, zone, bar / 2, qcolor(COLORS.success, ALPHA.glow))
            painter.setPen(QPen(QColor(COLORS.on_success_cont), SIZES.hairline))
            for edge in (band.low, band.high):
                if edge is not None:
                    x = track.left() + track.width() * self._position(edge)
                    painter.drawLine(
                        QPointF(x, track.top() - SPACE.xs / 2),
                        QPointF(x, track.bottom() + SPACE.xs / 2),
                    )
        inside = self.inside()
        if self._value is not None and inside is not None:
            x = track.left() + track.width() * self._marker.value
            color = COLORS.success if inside else COLORS.danger
            painter.setPen(QPen(QColor(COLORS.surface), SIZES.active_outline))
            painter.setBrush(QColor(color))
            painter.drawEllipse(QRectF(x - marker / 2 + 1, 1, marker - 2, marker - 2))
        draw_line(painter, QRectF(0, marker + SPACE.xs, width, line_box(TYPE.caption).height),
                  self._caption, TYPE.caption, COLORS.text_2, align=Qt.AlignmentFlag.AlignHCenter)
        painter.end()


class ValueRow:
    """One row of the electrical table: name | value | range bar | result chip.

    Not a widget: its parts go into a shared ``QGridLayout`` row so columns line up.
    """

    def __init__(self, grid: QGridLayout, row: int, name_key: str, icon: str) -> None:
        name_box = QWidget()
        box = QHBoxLayout(name_box)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(SPACE.s)
        box.addWidget(Icon(icon, SIZES.icon, COLORS.text_2))
        self.name = TrText(name_key, "body")
        box.addWidget(self.name, 1)
        self.measured = Text("-", "headline", align=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        metrics = QFontMetricsF(font_for(TYPE.headline))
        # room for the widest value ('000.00 °C'), so the columns never shift
        self.measured.reserve_width(
            int(metrics.horizontalAdvance("000.00 °C") - metrics.horizontalAdvance("-"))
        )
        self.bar = RangeBar()
        self.allowed = self.bar  # compatibility: the allowed range is the bar's caption
        self.pill = StatusChip(compact=True)
        self.pill.reserve("status.word.pass", "status.word.fail", "status.word.working", "status.word.pending")
        grid.addWidget(name_box, row, 0)
        grid.addWidget(self.measured, row, 1)
        grid.addWidget(self.bar, row, 2)
        grid.addWidget(self.pill, row, 3, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

    def set_value(
        self, measured: str | None, value: float | None, band: Band | None, caption: str, state: str
    ) -> None:
        self.measured.setText(measured or "-")
        self.measured.set_tone("primary" if measured else "tertiary")
        self.bar.set_range(band, value, caption)
        self.pill.set_state(state)
        self.measured.setAccessibleName(f"{self.name.text()}: {self.measured.text()} ({caption})")


class _Slot(QWidget):
    def __init__(self, index: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.index = index
        self.value = ""
        self.unit = ""
        self.time = ""
        self._enter = Tween(self, lambda _v: self.update(), value=1.0, ms=MOTION.slow)
        self.setMinimumHeight(SIZES.reading_slot)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt API
        return QSize(SIZES.reading_slot, SIZES.reading_slot)

    def set_reading(self, value: str, unit: str, time: str) -> None:
        fresh = not self.value and bool(value)
        self.value, self.unit, self.time = value, unit, time
        if fresh:
            self._enter.jump(0.0)
            self._enter.to(1.0)
        self.update()

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())
        filled = bool(self.value)
        if filled:
            fill_rounded(painter, rect, RADIUS.control, COLORS.surface_2)
        else:
            pen = QPen(QColor(COLORS.outline_strong), SIZES.hairline, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            inset = SIZES.hairline
            painter.drawRoundedRect(rect.adjusted(inset, inset, -inset, -inset), RADIUS.control, RADIUS.control)
        pad = SPACE.m
        caption = line_box(TYPE.caption).height
        inner = rect.width() - 2 * pad
        draw_line(painter, QRectF(rect.left() + pad, rect.top() + SPACE.s, inner, caption),
                  str(self.index), TYPE.caption, COLORS.text_3)
        k = self._enter.value if filled else 1.0
        painter.setOpacity(k)
        shift = (1 - k) * SPACE.s
        value_box = line_box(TYPE.title).height
        y = rect.top() + SPACE.s + caption + shift
        draw_line(painter, QRectF(rect.left() + pad, y, inner, value_box), self.value or "—",
                  TYPE.title, COLORS.text if filled else COLORS.text_3)
        if filled:
            draw_line(painter, QRectF(rect.left() + pad, y + value_box, inner, caption),
                      f"{self.unit} · {self.time}", TYPE.caption, COLORS.text_2)
        painter.end()


class ReadingSlots(QWidget):
    """N slots in one row, in reading order; empty slots are dashed placeholders (S1)."""

    def __init__(self, count: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACE.s)
        self.slots: list[_Slot] = []
        for index in range(count):
            slot = _Slot(index + 1)
            self.slots.append(slot)
            layout.addWidget(slot)

    def set_count(self, total: int) -> None:
        for index, slot in enumerate(self.slots):
            slot.setVisible(index < total)

    def set_readings(self, readings: list[tuple[str, str, str]]) -> None:
        for index, slot in enumerate(self.slots):
            if index < len(readings):
                slot.set_reading(*readings[index])
            else:
                slot.set_reading("", "", "")
        texts = [f"{i + 1}: {v} {u} {tm}" for i, (v, u, tm) in enumerate(readings)]
        self.setAccessibleDescription("; ".join(texts))
