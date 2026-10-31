"""ErrorBanner, RejectTakeover, SuccessToast overlays.

Overlays are anchored to content area and BottomBar footprint.
They do NOT resize or shift stage panes or cause scrollbars.
Border is a four-sided 2px tone border.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from parkomate.core.enums import Severity
from parkomate.core.errors import ParkomateError
from parkomate.core.models import RejectInstruction
from parkomate.i18n import t, tr_message
from parkomate.ui.components.icons import Icon
from parkomate.ui.components.widgets import BigButton, restyle, set_prop
from parkomate.ui.qt_i18n import error_cause, error_steps, error_title, language_notifier
from parkomate.ui.theme.fonts import font
from parkomate.ui.theme.tokens import COLORS, SIZES


class ErrorBanner(QFrame):
    """Inline error banner with 4-sided 2px tone border.

    Computes height from its content (sizeHint) with max height cap and scrolling.
    """

    retry_requested = Signal()

    MIN_HEIGHT = SIZES.banner_min_height
    MAX_HEIGHT = SIZES.banner_max_height
    HEIGHT = SIZES.banner_min_height

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ErrorBanner")
        self.setProperty("tone", "fail")
        self._error: ParkomateError | None = None
        self._retry_key = "action.try_again"
        self._has_retry = False
        self.setMinimumHeight(self.MIN_HEIGHT)
        self.setMaximumHeight(self.MAX_HEIGHT)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(SIZES.space_l, SIZES.space_s, SIZES.space_l, SIZES.space_s)
        outer.setSpacing(SIZES.space_m)

        self._icon = Icon("warn", 32, COLORS.fail_fg)
        outer.addWidget(self._icon, 0, Qt.AlignmentFlag.AlignTop)

        self.scroll_area = QScrollArea()
        self.scroll_area.setObjectName("BannerScroll")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self.text_inner = QWidget()
        self.text_inner.setObjectName("BannerTextInner")
        text = QVBoxLayout(self.text_inner)
        text.setContentsMargins(0, 0, 0, 0)
        text.setSpacing(SIZES.space_xs)

        self.title = QLabel()
        self.title.setFont(font(SIZES.font_h2, bold=True))
        self.title.setWordWrap(True)

        self.cause_label = QLabel()
        self.cause_label.setWordWrap(True)

        self.steps = QLabel()
        self.steps.setWordWrap(True)
        self.steps.setTextFormat(Qt.TextFormat.PlainText)
        self.steps.setFont(font(SIZES.font_base))

        self.details = QLabel()
        self.details.setProperty("role", "small")
        self.details.setWordWrap(True)
        self.details.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.details.setVisible(False)

        text.addWidget(self.title)
        text.addWidget(self.cause_label)
        text.addWidget(self.steps)
        text.addWidget(self.details)
        self.scroll_area.setWidget(self.text_inner)
        outer.addWidget(self.scroll_area, 1)

        buttons = QVBoxLayout()
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.setSpacing(SIZES.space_s)

        self.retry_button = BigButton("action.try_again", variant="secondary")
        self.retry_button.setMinimumWidth(SIZES.button_min_width_secondary)
        self.retry_button.clicked.connect(self.retry_requested.emit)

        self.details_link = BigButton("action.details_for_support", variant="link")
        self.details_link.setMinimumWidth(SIZES.button_min_width_secondary)
        self.details_link.clicked.connect(self._toggle_details)

        buttons.addWidget(self.retry_button, 0, Qt.AlignmentFlag.AlignTop)
        buttons.addWidget(self.details_link, 0, Qt.AlignmentFlag.AlignTop)
        buttons.addStretch(1)
        outer.addLayout(buttons, 0)

        self.setVisible(False)
        if parent is not None:
            parent.installEventFilter(self)
        language_notifier().changed.connect(self.retranslate)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is self.parent() and event.type() == QEvent.Type.Resize:
            self.reposition()
        return False

    def reposition(self) -> None:
        self.updateGeometry()

    def sizeHint(self) -> QSize:
        if self._error is None or not self.isVisible():
            return QSize(super().sizeHint().width(), self.MIN_HEIGHT)
        content_h = self.text_inner.sizeHint().height()
        buttons_h = (
            self.retry_button.sizeHint().height()
            + SIZES.space_s
            + self.details_link.sizeHint().height()
        )
        inner_h = max(content_h, buttons_h, 32)
        total_h = inner_h + 2 * SIZES.space_s + 4
        capped_h = max(self.MIN_HEIGHT, min(total_h, self.MAX_HEIGHT))
        return QSize(super().sizeHint().width(), capped_h)

    def show_error(self, error: ParkomateError, *, has_retry: bool, retry_key: str) -> None:
        self._error = error
        self._has_retry = has_retry
        self._retry_key = retry_key
        severe = error.severity in (Severity.ERROR, Severity.CRITICAL)
        set_prop(self, "tone", "fail" if severe else "warn")
        self._icon.set_icon("warn", COLORS.fail_fg if severe else COLORS.warn_fg)
        self.details.setVisible(False)
        self.retranslate()
        self.reposition()
        self.setVisible(True)
        self.updateGeometry()

    def clear(self) -> None:
        self._error = None
        self.setVisible(False)
        self.updateGeometry()

    def error(self) -> ParkomateError | None:
        return self._error

    def _toggle_details(self) -> None:
        self.details.setVisible(not self.details.isVisible())
        self.updateGeometry()

    def retranslate(self, *_args: object) -> None:
        error = self._error
        if error is None:
            return
        self.title.setText(error_title(error))
        self.cause_label.setText(error_cause(error))
        steps = error_steps(error)
        self.steps.setText("\n".join(f"{i}.  {step}" for i, step in enumerate(steps, start=1)))
        self.retry_button.set_text_key(self._retry_key)
        self.retry_button.setVisible(self._has_retry)
        self.details.setText(t("error.details", code=error.code.value, message=error.message))
        self.setAccessibleName(f"{error_title(error)}. {error_cause(error)}")
        self.updateGeometry()


class _OverlayMixin(QFrame):
    """Keeps overlay sized to its parent."""

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


class RejectTakeover(_OverlayMixin):
    """Full-screen red: REJECT, which box, why, and one button."""

    confirmed = Signal()

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("RejectTakeover")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._instruction: RejectInstruction | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(64, 48, 64, 48)
        layout.setSpacing(SIZES.space_l)
        layout.addStretch(1)

        top = QHBoxLayout()
        top.addStretch(1)
        top.addWidget(Icon("cross", 96, COLORS.on_status_solid))
        self.headline = QLabel()
        self.headline.setFont(font(SIZES.font_takeover, bold=True))
        top.addWidget(self.headline)
        top.addStretch(1)
        layout.addLayout(top)

        self.place = QLabel()
        self.place.setFont(font(40, bold=True))
        self.place.setWordWrap(True)
        self.place.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.place)

        box_row = QHBoxLayout()
        box_row.addStretch(1)
        self.box_caption = QLabel()
        self.box_caption.setFont(font(SIZES.font_h1, bold=True))
        self.box = QLabel()
        self.box.setFont(font(SIZES.font_box_letter, bold=True))
        self.box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Uses QSS box_letter="true" rule instead of inline stylesheet
        self.box.setProperty("box_letter", "true")
        restyle(self.box)
        box_row.addWidget(self.box_caption, 0, Qt.AlignmentFlag.AlignVCenter)
        box_row.addSpacing(SIZES.space_l)
        box_row.addWidget(self.box)
        box_row.addStretch(1)
        layout.addLayout(box_row)

        self.reason = QLabel()
        self.reason.setFont(font(SIZES.font_h1))
        self.reason.setWordWrap(True)
        self.reason.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.reason)

        layout.addStretch(1)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        self.button = BigButton("action.device_placed", variant="takeover", hint_key="key.enter")
        self.button.clicked.connect(self.confirmed.emit)
        button_row.addWidget(self.button)
        button_row.addStretch(1)
        layout.addLayout(button_row)

        self.setVisible(False)
        language_notifier().changed.connect(self.retranslate)

    def show_instruction(self, instruction: RejectInstruction) -> None:
        self._instruction = instruction
        self.retranslate()
        self.reposition()
        self.setVisible(True)
        self.raise_()
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

    def retranslate(self, *_args: object) -> None:
        instruction = self._instruction
        if instruction is None:
            return
        stage_name = t(instruction.stage.label_key)
        self.headline.setText(t("reject.headline"))
        self.place.setText(
            t(instruction.message_key, stage=stage_name.upper(), box=instruction.box_letter)
        )
        self.box_caption.setText(t("reject.box_caption"))
        self.box.setText(instruction.box_letter)
        self.reason.setText(tr_message(None, instruction.reason_key, instruction.reason_params))
        self.setAccessibleName(f"{self.headline.text()}. {self.place.text()}. {self.reason.text()}")


class SuccessToast(QFrame):
    """Green full-width confirmation that hides itself. Centered, max 560px wide."""

    WIDTH = 560

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SuccessToast")
        self.setFixedWidth(self.WIDTH)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(SIZES.space_l, SIZES.space_m, SIZES.space_l, SIZES.space_m)
        layout.setSpacing(SIZES.space_m)
        layout.addStretch(1)
        layout.addWidget(Icon("check", 44, COLORS.on_status_solid))
        self.label = QLabel()
        layout.addWidget(self.label)
        layout.addStretch(1)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)
        self._device = ""
        self.setVisible(False)
        language_notifier().changed.connect(self.retranslate)

    def show_message(self, device: str, seconds: float) -> None:
        self._device = device
        self.retranslate()
        parent = self.parentWidget()
        if parent is not None:
            # Centered below TopBar
            x = (parent.width() - self.width()) // 2
            y = 120  # Below TopBar (76) + InfoStrip (40) + ModeBanner (28) + some margin
            self.setGeometry(x, y, self.width(), 84)
        self.setVisible(True)
        self.raise_()
        self._timer.start(int(seconds * 1000))

    def retranslate(self, *_args: object) -> None:
        self.label.setText(t("toast.device_complete", device=self._device))
        self.setAccessibleName(self.label.text())
