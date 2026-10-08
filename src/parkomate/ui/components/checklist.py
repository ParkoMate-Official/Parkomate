"""ChecklistRow: the whole 64 px row is the touch target; 32 px rounded checkbox with an
animated tick, illustrative icon, label, 'Done' word when ticked, F-key chip on the right
(L4, K1)."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import (
    QEnterEvent,
    QFontMetricsF,
    QKeyEvent,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QPen,
)
from PySide6.QtWidgets import QAbstractButton, QSizePolicy, QWidget

from parkomate.i18n import t
from parkomate.ui.components.base import (
    draw_line,
    fill_rounded,
    key_width,
    mix,
    on_language_change,
    qcolor,
    translations,
)
from parkomate.ui.components.buttons import keycap_size, paint_keycap
from parkomate.ui.components.icons import paint_icon
from parkomate.ui.theme.fonts import font_for
from parkomate.ui.theme.motion import Tween
from parkomate.ui.theme.tokens import ALPHA, COLORS, MOTION, RADIUS, SIZES, SPACE, TYPE


class ChecklistRow(QAbstractButton):
    def __init__(
        self, key: str, icon: str, hint_key: str | None = None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._key = key
        self._icon = icon
        self._hint_key = hint_key
        self._tick = Tween(self, lambda _v: self.update(), ms=MOTION.medium)
        self._hover = Tween(self, lambda _v: self.update(), ms=MOTION.fast)
        self.setCheckable(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(SIZES.list_row)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setProperty("ring_radius", RADIUS.control)
        self.toggled.connect(lambda on: self._tick.to(1.0 if on else 0.0))
        on_language_change(self, self.retranslate)
        self.retranslate()

    def setChecked(self, checked: bool) -> None:
        if checked != self.isChecked():
            super().setChecked(checked)  # animates via toggled
        elif abs(self._tick.value - (1.0 if checked else 0.0)) > 0.5:
            self._tick.jump(1.0 if checked else 0.0)

    def sizeHint(self) -> QSize:
        return QSize(
            self._fixed_width() + key_width(font_for(TYPE.body_lg), self._key), SIZES.list_row
        )

    def _fixed_width(self) -> int:
        done = key_width(font_for(TYPE.label), "status.word.done")
        cap = (
            max((keycap_size(x).width() for x in translations(self._hint_key)), default=0)
            if self._hint_key
            else 0
        )
        return (
            2 * SPACE.l
            + SIZES.checkbox
            + SPACE.l
            + SIZES.icon_m
            + SPACE.m
            + SPACE.l
            + done
            + SPACE.m
            + cap
        )

    def label(self) -> str:
        return t(self._key)

    def retranslate(self, *_args: object) -> None:
        self.setText(self.label())
        self.setAccessibleName(self.label())
        self.update()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            event.ignore()  # Enter is the primary action, never a toggle
            return
        super().keyPressEvent(event)

    def enterEvent(self, event: QEnterEvent) -> None:
        self._hover.to(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event: object) -> None:
        self._hover.to(0.0)
        super().leaveEvent(event)  # type: ignore[arg-type]

    def paintEvent(self, _event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())
        k = self._tick.value
        enabled = self.isEnabled()
        base = mix(COLORS.surface_2, COLORS.success_cont, k)
        if enabled and self._hover.value > 0:
            base = mix(base.name(), COLORS.text, ALPHA.hover * self._hover.value * 0.6)
        if not enabled:
            painter.setOpacity(ALPHA.disabled + (1 - ALPHA.disabled) * k)
        fill_rounded(painter, rect, RADIUS.control, base)
        # checkbox
        side = SIZES.checkbox
        box = QRectF(rect.left() + SPACE.l, rect.center().y() - side / 2, side, side)
        border = mix(COLORS.outline_strong, COLORS.on_success_cont, k)
        fill = mix(COLORS.surface, COLORS.on_success_cont, k)
        fill_rounded(
            painter,
            box,
            RADIUS.chip,
            fill,
            border,
            SIZES.active_outline * (1 - k) + SIZES.hairline * k,
        )
        if k > 0:
            self._paint_tick(painter, box, k)
        # icon + label
        icon = QRectF(
            box.right() + SPACE.l, rect.center().y() - SIZES.icon_m / 2, SIZES.icon_m, SIZES.icon_m
        )
        paint_icon(painter, self._icon, icon, COLORS.text_2)
        right = rect.right() - SPACE.l
        if self._hint_key:
            hint = t(self._hint_key)
            cap = keycap_size(hint)
            cap_rect = QRectF(
                right - cap.width(), rect.center().y() - cap.height() / 2, cap.width(), cap.height()
            )
            paint_keycap(painter, cap_rect, hint, COLORS.text_2)
            right = cap_rect.left() - SPACE.m
        if k > 0.5:
            width = key_width(font_for(TYPE.label), "status.word.done")
            draw_line(
                painter,
                QRectF(right - width, rect.top(), width, rect.height()),
                t("status.word.done"),
                TYPE.label,
                COLORS.on_success_cont,
                align=Qt.AlignmentFlag.AlignRight,
            )
        right -= key_width(font_for(TYPE.label), "status.word.done") + SPACE.l
        text_left = icon.right() + SPACE.m
        draw_line(
            painter,
            QRectF(text_left, rect.top(), right - text_left, rect.height()),
            self.text(),
            TYPE.body_lg,
            COLORS.text,
        )
        too_long = (
            QFontMetricsF(font_for(TYPE.body_lg)).horizontalAdvance(self.text()) > right - text_left
        )
        self.setToolTip(self.text() if too_long else "")
        painter.end()

    @staticmethod
    def _paint_tick(painter: QPainter, box: QRectF, k: float) -> None:
        """The check mark draws itself (stroke grows with ``k``)."""
        s = box.width()
        points = [
            QPointF(box.left() + s * 0.24, box.top() + s * 0.52),
            QPointF(box.left() + s * 0.42, box.top() + s * 0.70),
            QPointF(box.left() + s * 0.76, box.top() + s * 0.32),
        ]
        first = points[1] - points[0]
        second = points[2] - points[1]
        len1 = (first.x() ** 2 + first.y() ** 2) ** 0.5
        len2 = (second.x() ** 2 + second.y() ** 2) ** 0.5
        drawn = (len1 + len2) * min(1.0, k)
        path = QPainterPath(points[0])
        if drawn <= len1:
            path.lineTo(points[0] + first * (drawn / len1))
        else:
            path.lineTo(points[1])
            path.lineTo(points[1] + second * ((drawn - len1) / len2))
        pen = QPen(qcolor(COLORS.on_status), SIZES.spinner_stroke)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.save()
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)
        painter.restore()
