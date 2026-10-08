"""CameraFrame: rounded live preview (16 px) with framing corners, a scan line while it is
searching, and a green flash + corner pulse when a code is read (L3)."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter, QPainterPath, QPaintEvent, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from parkomate.ui.components.base import draw_line, qcolor
from parkomate.ui.theme.motion import FrameClock, Tween
from parkomate.ui.theme.tokens import ALPHA, COLORS, MOTION, RADIUS, SIZES, SPACE, TYPE


class CameraFrame(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._image: QImage | None = None
        self._scanning = False
        self._placeholder = ""
        self._flash = Tween(self, lambda _v: self.update(), ms=MOTION.flash)
        self.setMinimumHeight(SIZES.camera_min_height)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_image(self, image: QImage | None) -> None:
        self._image = image
        self.update()

    def set_placeholder(self, text: str) -> None:
        self._placeholder = text
        self.update()

    def set_scanning(self, scanning: bool) -> None:
        if scanning == self._scanning:
            return
        self._scanning = scanning
        clock = FrameClock.instance()
        if scanning:
            clock.subscribe(self, self.update)
        else:
            clock.unsubscribe(self)
        self.update()

    def scanning(self) -> bool:
        return self._scanning

    def flash_success(self) -> None:
        """Green flash + corner pulse when a code is read."""
        self._flash.jump(1.0)
        self._flash.to(0.0)

    def _guide(self, rect: QRectF) -> QRectF:
        side = min(rect.width() * 0.5, rect.height() * 0.72)
        return QRectF(rect.center().x() - side / 2, rect.center().y() - side / 2, side, side)

    def paintEvent(self, _event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())
        clip = QPainterPath()
        clip.addRoundedRect(rect, RADIUS.card, RADIUS.card)
        painter.setClipPath(clip)
        painter.fillRect(rect, QColor(COLORS.camera_bg))
        if self._image is not None and not self._image.isNull():
            image = self._image
            scale = max(rect.width() / image.width(), rect.height() / image.height())
            width, height = image.width() * scale, image.height() * scale
            painter.drawImage(
                QRectF(
                    rect.center().x() - width / 2, rect.center().y() - height / 2, width, height
                ),
                image,
            )
        flash = self._flash.value
        if flash > 0:
            painter.fillRect(rect, qcolor(COLORS.success, ALPHA.flash * flash))
        guide = self._guide(rect)
        grow = SPACE.s * flash
        guide = guide.adjusted(-grow, -grow, grow, grow)
        corner_color = QColor(COLORS.success) if flash > 0.05 else QColor(COLORS.surface)
        pen = QPen(corner_color, SIZES.camera_stroke)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        arm = SIZES.camera_corner
        for x, y, dx, dy in (
            (guide.left(), guide.top(), 1, 1),
            (guide.right(), guide.top(), -1, 1),
            (guide.left(), guide.bottom(), 1, -1),
            (guide.right(), guide.bottom(), -1, -1),
        ):
            painter.drawLine(QPointF(x, y), QPointF(x + dx * arm, y))
            painter.drawLine(QPointF(x, y), QPointF(x, y + dy * arm))
        if self._scanning:
            phase = FrameClock.instance().phase(MOTION.scan_period)
            sweep = phase * 2 if phase < 0.5 else (1 - phase) * 2  # down, then back up
            y = guide.top() + guide.height() * sweep
            glow = QLinearGradient(QPointF(0, y - SPACE.l), QPointF(0, y + SPACE.l))
            glow.setColorAt(0.0, qcolor(COLORS.camera_line, 0.0))
            glow.setColorAt(0.5, qcolor(COLORS.camera_line, ALPHA.glow))
            glow.setColorAt(1.0, qcolor(COLORS.camera_line, 0.0))
            painter.fillRect(QRectF(guide.left(), y - SPACE.l, guide.width(), 2 * SPACE.l), glow)
            painter.setPen(QPen(QColor(COLORS.camera_line), SIZES.active_outline))
            painter.drawLine(
                QPointF(guide.left() + SPACE.s, y), QPointF(guide.right() - SPACE.s, y)
            )
        if self._image is None and self._placeholder:
            draw_line(
                painter,
                QRectF(rect.left() + SPACE.l, rect.top() + SPACE.m, rect.width() / 2, SIZES.chip),
                self._placeholder,
                TYPE.label,
                COLORS.surface,
            )
        painter.end()
