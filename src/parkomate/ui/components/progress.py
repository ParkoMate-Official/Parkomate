"""ProgressBar (slim, 8 px), ProgressRing (hero) and Spinner. Colour follows the state:
running = primary, success = green, danger = red (a failed bar keeps the % it reached)."""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from parkomate.ui.components.base import draw_line, fill_rounded, qcolor
from parkomate.ui.components.buttons import paint_spinner
from parkomate.ui.theme.motion import FrameClock, Tween
from parkomate.ui.theme.tokens import ALPHA, COLORS, MOTION, SIZES, TYPE

STATE_COLORS = {
    "running": COLORS.primary,
    "success": COLORS.success,
    "danger": COLORS.danger,
    "neutral": COLORS.outline_strong,
}


class ProgressBar(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._value = 0
        self._state = "running"
        self._shown = Tween(self, lambda _v: self.update(), ms=MOTION.medium)
        self.setFixedHeight(SIZES.progress_bar)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_value(self, value: int, *, animate: bool = True) -> None:
        value = max(0, min(100, int(value)))
        self._value = value
        if animate and value >= self._shown.value:
            self._shown.to(float(value))
        else:
            self._shown.jump(float(value))
        self.setAccessibleDescription(f"{value} %")

    def value(self) -> int:
        return self._value

    def set_state(self, state: str) -> None:
        if state != self._state:
            self._state = state
            self.update()

    def state(self) -> str:
        return self._state

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())
        radius = rect.height() / 2
        fill_rounded(painter, rect, radius, COLORS.surface_3)
        width = rect.width() * self._shown.value / 100
        if width > 0:
            fill_rounded(
                painter,
                QRectF(rect.left(), rect.top(), max(width, rect.height()), rect.height()),
                radius,
                STATE_COLORS.get(self._state, COLORS.primary),
            )
        painter.end()


class ProgressRing(QWidget):
    """Large circular progress with the % in the middle; indeterminate = rotating arc."""

    def __init__(self, size: int = SIZES.ring, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._value = 0
        self._state = "running"
        self._indeterminate = False
        self._shown = Tween(self, lambda _v: self.update(), ms=MOTION.medium)
        self.setFixedSize(size, size)

    def set_value(self, value: int) -> None:
        self._value = max(0, min(100, int(value)))
        self._shown.to(float(self._value))
        self.setAccessibleDescription(f"{self._value} %")

    def value(self) -> int:
        return self._value

    def set_state(self, state: str) -> None:
        self._state = state
        self.update()

    def set_indeterminate(self, on: bool) -> None:
        self._indeterminate = on
        clock = FrameClock.instance()
        if on:
            clock.subscribe(self, self.update)
        else:
            clock.unsubscribe(self)
        self.update()

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        stroke = SIZES.ring_stroke
        rect = QRectF(self.rect()).adjusted(stroke / 2, stroke / 2, -stroke / 2, -stroke / 2)
        color = STATE_COLORS.get(self._state, COLORS.primary)
        if self._indeterminate:
            paint_spinner(
                painter, QRectF(self.rect()), color, FrameClock.instance().phase(MOTION.spin_period)
            )
            painter.end()
            return
        track = QPen(qcolor(color, ALPHA.track), stroke)
        painter.setPen(track)
        painter.drawEllipse(rect)
        pen = QPen(QColor(color), stroke)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        span = -int(360 * 16 * self._shown.value / 100)
        if span:
            painter.drawArc(rect, 90 * 16, span)
        draw_line(painter, QRectF(self.rect()), f"{round(self._shown.value)} %", TYPE.headline,
                  COLORS.text, align=Qt.AlignmentFlag.AlignHCenter)
        painter.end()


class Spinner(QWidget):
    """Small 'working' spinner; animates only while visible (still with reduced motion)."""

    def __init__(
        self, size: int = SIZES.spinner, color: str = COLORS.primary, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._color = color
        self.setFixedSize(QSize(size, size))
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def set_color(self, color: str) -> None:
        self._color = color
        self.update()

    def showEvent(self, event: object) -> None:  # noqa: N802 - Qt API
        FrameClock.instance().subscribe(self, self.update)
        super().showEvent(event)  # type: ignore[arg-type]

    def hideEvent(self, event: object) -> None:  # noqa: N802 - Qt API
        FrameClock.instance().unsubscribe(self)
        super().hideEvent(event)  # type: ignore[arg-type]

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        paint_spinner(
            painter, QRectF(self.rect()), self._color, FrameClock.instance().phase(MOTION.spin_period)
        )
        painter.end()
