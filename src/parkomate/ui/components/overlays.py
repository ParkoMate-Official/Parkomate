"""ErrorBanner, RejectTakeover and Toast."""

from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QObject,
    QPoint,
    QPropertyAnimation,
    QRectF,
    Qt,
    QTimer,
    QVariantAnimation,
    Signal,
)
from PySide6.QtGui import QColor, QKeyEvent, QPainter, QPaintEvent, QRadialGradient
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from parkomate.core.enums import Severity
from parkomate.core.errors import ParkomateError
from parkomate.core.models import RejectInstruction
from parkomate.i18n import t, tr_message
from parkomate.ui.components.base import add_shadow, fill_rounded, on_language_change, qcolor
from parkomate.ui.components.buttons import AppButton
from parkomate.ui.components.cards import Banner
from parkomate.ui.components.icons import Icon
from parkomate.ui.components.text import SelectableText, Text, TrText
from parkomate.ui.qt_i18n import error_cause, error_steps, error_title
from parkomate.ui.theme.motion import duration, motion_enabled
from parkomate.ui.theme.tokens import ALPHA, COLORS, MOTION, RADIUS, SIZES, SPACE


class ErrorBanner(Banner):
    """Tells the operator what to do: title, one-line cause, numbered steps, ONE 'Try again'.

    Technical details are hidden behind a small 'Details for support' link.
    """

    retry_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("error", parent)
        self.setObjectName("ErrorBanner")
        self._error: ParkomateError | None = None
        self._retry_key = "action.try_again"
        self._has_retry = False
        self.cause = self.body
        self.details = SelectableText("", "caption", "secondary")
        self.details.setVisible(False)
        self.text_column.addWidget(self.details)
        self.retry_button = AppButton("action.try_again", variant="outlined", icon="refresh")
        self.retry_button.clicked.connect(self.retry_requested.emit)
        self.details_link = AppButton("action.details_for_support", variant="text", size="compact")
        self.details_link.clicked.connect(self._toggle_details)
        self.add_action(self.retry_button)
        self.add_action(self.details_link)
        self.action_box.addStretch(1)
        self.setVisible(False)
        on_language_change(self, self.retranslate)

    def show_error(self, error: ParkomateError, *, has_retry: bool, retry_key: str) -> None:
        self._error = error
        self._has_retry = has_retry
        self._retry_key = retry_key
        severe = error.severity in (Severity.ERROR, Severity.CRITICAL)
        self.set_tone("error" if severe else "warning")
        self.details.setVisible(False)
        self.retranslate()
        self.setVisible(True)

    def clear(self) -> None:
        self._error = None
        self.setVisible(False)

    def error(self) -> ParkomateError | None:
        return self._error

    def _toggle_details(self) -> None:
        self.details.setVisible(not self.details.isVisible())

    def retranslate(self, *_args: object) -> None:
        error = self._error
        if error is None:
            return
        self.set_texts(error_title(error), error_cause(error), error_steps(error))
        self.retry_button.set_text_key(self._retry_key)
        self.retry_button.setVisible(self._has_retry)
        self.details.setText(t("error.details", code=error.code.value, message=error.message))
        self.setAccessibleName(f"{error_title(error)}. {error_cause(error)}")


class _OverlayMixin(QFrame):
    """Keeps the overlay sized to its parent."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        parent.installEventFilter(self)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is self.parent() and event.type() == QEvent.Type.Resize:
            self.reposition()
        return False

    def reposition(self) -> None:
        parent = self.parentWidget()
        if parent is not None:
            self.setGeometry(parent.rect())


class _BoxTile(QWidget):
    """The big reject box letter on a translucent white tile, with a one-time pulse."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.letter = Text("", "box_letter", "on_status", align=Qt.AlignmentFlag.AlignCenter)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.letter)
        self._pulse = 0.0
        self._animation = QVariantAnimation(self)
        self._animation.setStartValue(1.0)
        self._animation.setEndValue(0.0)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._animation.valueChanged.connect(self._set_pulse)
        self.setFixedSize(SIZES.takeover_tile, SIZES.takeover_tile)

    def _set_pulse(self, value: object) -> None:
        self._pulse = float(value)  # type: ignore[arg-type]
        self.update()

    def pulse(self) -> None:
        if not motion_enabled():
            return
        self._animation.stop()
        self._animation.setDuration(MOTION.pulse)
        self._animation.start()

    def paintEvent(self, _event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())
        fill_rounded(
            painter,
            rect,
            RADIUS.hero,
            qcolor(COLORS.on_status, ALPHA.track),
            COLORS.on_status,
            SIZES.camera_stroke,
        )
        if self._pulse > 0:
            fill_rounded(
                painter, rect, RADIUS.hero, qcolor(COLORS.on_status, ALPHA.track * self._pulse * 2)
            )
        painter.end()


class RejectTakeover(_OverlayMixin):
    """Full-screen red: REJECT, which box (label ABOVE the tile), why, one button (R1)."""

    confirmed = Signal()

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("RejectTakeover")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._instruction: RejectInstruction | None = None
        center = Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE.xxxl, SPACE.xxl, SPACE.xxxl, SPACE.xxl)
        layout.setSpacing(SPACE.l)
        layout.addStretch(1)
        top = QHBoxLayout()
        top.setSpacing(SPACE.l)
        top.addStretch(1)
        top.addWidget(Icon("cancel", SIZES.icon_hero, COLORS.on_status, filled=True))
        self.headline = Text("", "display", "on_status")
        top.addWidget(self.headline)
        top.addStretch(1)
        layout.addLayout(top)
        self.place = Text("", "headline", "on_status", wrap=True, align=center)
        layout.addWidget(self.place)
        layout.addSpacing(SPACE.s)
        self.box_caption = TrText("reject.box_caption", "title", "on_status", align=center)
        layout.addWidget(self.box_caption)
        self.tile = _BoxTile()
        self.box = self.tile.letter
        layout.addWidget(self.tile, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(SPACE.s)
        self.reason_card = _ReasonCard()
        self.reason = self.reason_card.text
        layout.addWidget(self.reason_card, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch(1)
        self.button = AppButton("action.device_placed", variant="on_takeover", hint_key="key.enter")
        layout.addWidget(self.button, 0, Qt.AlignmentFlag.AlignHCenter)
        self.button.clicked.connect(self.confirmed.emit)
        self._opacity = QGraphicsOpacityEffect(self)
        self._opacity.setOpacity(1.0)
        self.setGraphicsEffect(self._opacity)
        self._fade = QPropertyAnimation(self._opacity, b"opacity", self)
        self._fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.setVisible(False)
        on_language_change(self, self.retranslate)

    def show_instruction(self, instruction: RejectInstruction) -> None:
        self._instruction = instruction
        self.retranslate()
        self.reposition()
        self.setVisible(True)
        self.raise_()
        length = duration(MOTION.slow)
        if length:
            self._fade.stop()
            self._fade.setDuration(length)
            self._fade.setStartValue(0.0)
            self._fade.setEndValue(1.0)
            self._fade.start()
        else:
            self._opacity.setOpacity(1.0)
        self.tile.pulse()
        self.button.setFocus()

    def instruction(self) -> RejectInstruction | None:
        return self._instruction

    def hide_takeover(self) -> None:
        self._instruction = None
        self.setVisible(False)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.confirmed.emit()
            return
        if event.key() == Qt.Key.Key_Escape:
            return  # Esc never dismisses a reject
        super().keyPressEvent(event)

    def paintEvent(self, _event: QPaintEvent) -> None:
        painter = QPainter(self)
        rect = QRectF(self.rect())
        gradient = QRadialGradient(rect.center(), max(rect.width(), rect.height()) * 0.6)
        gradient.setColorAt(0.0, QColor(COLORS.takeover_glow))
        gradient.setColorAt(1.0, QColor(COLORS.takeover))
        painter.fillRect(rect, gradient)
        painter.end()

    def retranslate(self, *_args: object) -> None:
        instruction = self._instruction
        if instruction is None:
            return
        stage_name = t(instruction.stage.label_key)
        self.headline.setText(t("reject.headline"))
        self.place.setText(
            t(instruction.message_key, stage=stage_name.upper(), box=instruction.box_letter)
        )
        self.box.setText(instruction.box_letter)
        self.reason.setText(tr_message(None, instruction.reason_key, instruction.reason_params))
        self.setAccessibleName(f"{self.headline.text()}. {self.place.text()}. {self.reason.text()}")


class _ReasonCard(QWidget):
    """The failed check, on a white translucent card."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACE.xl, SPACE.l, SPACE.xl, SPACE.l)
        layout.setSpacing(SPACE.m)
        layout.addWidget(
            Icon("error", SIZES.icon_m, COLORS.on_status), 0, Qt.AlignmentFlag.AlignTop
        )
        self.text = Text("", "title", "on_status", wrap=True)
        layout.addWidget(self.text, 1)
        self.setMaximumWidth(SIZES.content_max // 2)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

    def paintEvent(self, _event: QPaintEvent) -> None:
        painter = QPainter(self)
        fill_rounded(
            painter, QRectF(self.rect()), RADIUS.card, qcolor(COLORS.on_status, ALPHA.track)
        )
        painter.end()


class Toast(QFrame):
    """Full-width green confirmation sliding down from the top; the device ID is large; it
    dismisses itself after ``seconds`` with a thin countdown line (O1)."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("SuccessToast")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACE.xl, SPACE.l, SPACE.xl, SPACE.l)
        layout.setSpacing(SPACE.l)
        layout.addStretch(1)
        layout.addWidget(Icon("check_circle", SIZES.icon_xl, COLORS.on_status, filled=True))
        self.label = Text("", "headline", "on_status")
        layout.addWidget(self.label)
        layout.addStretch(1)
        add_shadow(self)
        self._device = ""
        self._seconds = 2.0
        self._remaining = 1.0
        self._slide = QPropertyAnimation(self, b"pos", self)
        self._slide.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._countdown = QVariantAnimation(self)
        self._countdown.setStartValue(1.0)
        self._countdown.setEndValue(0.0)
        self._countdown.valueChanged.connect(self._tick)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._dismiss)
        self.setVisible(False)
        on_language_change(self, self.retranslate)

    def _tick(self, value: object) -> None:
        self._remaining = float(value)  # type: ignore[arg-type]
        self.update()

    def _target(self) -> tuple[QPoint, int]:
        parent = self.parentWidget()
        width = (parent.width() if parent is not None else SIZES.min_window_width) - 2 * SPACE.xl
        return QPoint(SPACE.xl, SPACE.l), max(SIZES.empty_state, width)

    def show_message(self, device: str, seconds: float) -> None:
        self._device = device
        self._seconds = seconds
        self.retranslate()
        target, width = self._target()
        self.resize(width, SIZES.toast)
        self.setVisible(True)
        self.raise_()
        length = duration(MOTION.slow)
        self._slide.stop()
        if length:
            self._slide.setDuration(length)
            self._slide.setStartValue(QPoint(target.x(), -SIZES.toast))
            self._slide.setEndValue(target)
            self._slide.start()
        else:
            self.move(target)
        self._remaining = 1.0
        self._countdown.stop()
        self._countdown.setDuration(max(1, int(seconds * 1000)))
        self._countdown.start()
        self._timer.start(int(seconds * 1000))

    def _dismiss(self) -> None:
        length = duration(MOTION.slow)
        if not length:
            self.hide()
            return
        self._slide.stop()
        self._slide.setDuration(length)
        self._slide.setStartValue(self.pos())
        self._slide.setEndValue(QPoint(self.x(), -SIZES.toast - SIZES.shadow_margin))
        self._slide.finished.connect(self._hide_after_slide)
        self._slide.start()

    def _hide_after_slide(self) -> None:
        self._slide.finished.disconnect(self._hide_after_slide)
        if self.y() < 0:
            self.hide()

    def retranslate(self, *_args: object) -> None:
        self.label.setText(t("toast.device_complete", device=self._device))
        self.setAccessibleName(self.label.text())

    def paintEvent(self, _event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())
        fill_rounded(painter, rect, RADIUS.card, COLORS.on_success_cont)
        line = SIZES.toast_countdown
        width = (rect.width() - 2 * RADIUS.card) * self._remaining
        fill_rounded(
            painter,
            QRectF(rect.left() + RADIUS.card, rect.bottom() - line - SPACE.s, width, line),
            line / 2,
            qcolor(COLORS.on_status, ALPHA.glow),
        )
        painter.end()


# Backwards-compatible name.
SuccessToast = Toast
