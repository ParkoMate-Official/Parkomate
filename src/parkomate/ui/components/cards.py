"""Card, Banner, EmptyState, KpiTile, InlineMessage, InlineConfirm.

One level of card on the tinted page background, separated by space - never a bordered card
inside a bordered card (G3). Inside a card, groups are separated by space or a soft divider.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QPainter, QPaintEvent
from PySide6.QtWidgets import QFrame, QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget

from parkomate.core.errors import ParkomateError
from parkomate.ui.components.base import fill_rounded, mix, set_prop
from parkomate.ui.components.buttons import AppButton
from parkomate.ui.components.icons import Icon
from parkomate.ui.components.text import Text, TrText
from parkomate.ui.qt_i18n import error_cause, error_title
from parkomate.ui.theme.tokens import COLORS, RADIUS, SIZES, SPACE

CARD_VARIANTS = ("default", "active", "success", "danger", "warning", "flat")


class Card(QFrame):
    """Surface on the page background: title, optional subtitle and trailing widget, body.

    Variants: default (1 px outline), active (2 px accent outline + subtle accent surface),
    success / danger / warning (2 px status outline), flat (no outline - inset areas).
    """

    def __init__(
        self,
        title_key: str | None = None,
        *,
        subtitle_key: str | None = None,
        icon: str | None = None,
        compact: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._variant = "default"
        pad = SPACE.l + SPACE.xs if compact else SPACE.xl
        self.layout_ = QVBoxLayout(self)
        self.layout_.setContentsMargins(pad, pad, pad, pad)
        self.layout_.setSpacing(SPACE.l)
        self.header = QHBoxLayout()
        self.header.setSpacing(SPACE.m)
        self.icon: Icon | None = None
        if icon:
            self.icon = Icon(icon, SIZES.icon_m, COLORS.text_2)
            self.header.addWidget(self.icon, 0, Qt.AlignmentFlag.AlignTop)
        titles = QVBoxLayout()
        titles.setSpacing(SPACE.xs)
        self.title = TrText(title_key or "", "title")
        self.subtitle = TrText(subtitle_key or "", "body", "secondary", wrap=True)
        titles.addWidget(self.title)
        titles.addWidget(self.subtitle)
        self.title.setVisible(bool(title_key))
        self.subtitle.setVisible(bool(subtitle_key))
        self.header.addLayout(titles, 1)
        self.trailing = QHBoxLayout()
        self.trailing.setSpacing(SPACE.s)
        self.header.addLayout(self.trailing)
        self._header_widget = QWidget()
        self._header_widget.setLayout(self.header)
        self._header_widget.setVisible(bool(title_key) or bool(icon))
        self.layout_.addWidget(self._header_widget)
        self.body = QVBoxLayout()
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(SPACE.l)
        self.layout_.addLayout(self.body, 1)

    def set_title_key(self, key: str | None, **params: Any) -> None:
        self.title.set_key(key, **params)
        self.title.setVisible(bool(key))
        self._header_widget.setVisible(bool(key) or self.icon is not None)

    def set_subtitle_key(self, key: str | None, **params: Any) -> None:
        self.subtitle.set_key(key, **params)
        self.subtitle.setVisible(bool(key))

    def add_trailing(self, widget: QWidget) -> None:
        self.trailing.addWidget(widget, 0, Qt.AlignmentFlag.AlignTop)
        self._header_widget.setVisible(True)

    def set_variant(self, variant: str) -> None:
        if variant != self._variant:
            self._variant = variant
            self.update()

    def variant(self) -> str:
        return self._variant

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        rect = QRectF(self.rect())
        variant = self._variant
        if variant == "flat":
            fill_rounded(painter, rect, RADIUS.card, COLORS.surface_2)
        elif variant == "active":
            fill_rounded(
                painter,
                rect,
                RADIUS.card,
                mix(COLORS.surface, COLORS.primary_cont, 0.5),
                COLORS.primary,
                SIZES.active_outline,
            )
        elif variant in ("success", "danger", "warning"):
            graphic, _container, _on = COLORS.status(variant)
            fill_rounded(painter, rect, RADIUS.card, COLORS.surface, graphic, SIZES.active_outline)
        else:
            fill_rounded(painter, rect, RADIUS.card, COLORS.surface, COLORS.outline, SIZES.hairline)
        painter.end()


BANNER_TONES = {
    "info": ("info", "info"),
    "success": ("success", "check_circle"),
    "warning": ("warning", "warning"),
    "error": ("danger", "error"),
    "danger": ("danger", "error"),
}


class Banner(QFrame):
    """Tinted message: icon, title, body, optional numbered steps and actions."""

    def __init__(self, tone: str = "info", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._tone = "info"
        outer = QHBoxLayout(self)
        outer.setContentsMargins(SPACE.xl, SPACE.l, SPACE.xl, SPACE.l)
        outer.setSpacing(SPACE.l)
        self.icon_widget = Icon("info", SIZES.icon_l, COLORS.info, filled=True)
        outer.addWidget(self.icon_widget, 0, Qt.AlignmentFlag.AlignTop)
        self.text_column = QVBoxLayout()
        self.text_column.setSpacing(SPACE.xs)
        self.title = Text("", "body_lg_strong", wrap=True)
        self.body = Text("", "body", wrap=True)
        self.steps = Text("", "body", wrap=True)
        self.text_column.addWidget(self.title)
        self.text_column.addWidget(self.body)
        self.text_column.addWidget(self.steps)
        self.steps.setVisible(False)
        outer.addLayout(self.text_column, 1)
        self.actions = QVBoxLayout()
        self.actions.setSpacing(SPACE.s)
        outer.addLayout(self.actions)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        self.set_tone(tone)

    def set_tone(self, tone: str) -> None:
        status, icon = BANNER_TONES.get(tone, BANNER_TONES["info"])
        self._tone = tone
        graphic, _container, on_container = COLORS.status(status)
        self.icon_widget.set_icon(icon, graphic, filled=True)
        self.title.set_color(on_container)
        self.update()

    def tone(self) -> str:
        return self._tone

    def set_texts(self, title: str, body: str = "", steps: list[str] | None = None) -> None:
        self.title.setText(title)
        self.body.setText(body)
        self.body.setVisible(bool(body))
        lines = steps or []
        self.steps.setText("\n".join(f"{i}.  {step}" for i, step in enumerate(lines, start=1)))
        self.steps.setVisible(bool(lines))
        self.setAccessibleName(f"{title}. {body}".strip())

    def add_action(self, button: QWidget) -> None:
        self.actions.addWidget(button, 0, Qt.AlignmentFlag.AlignRight)

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802 - Qt API
        status, _icon = BANNER_TONES.get(self._tone, BANNER_TONES["info"])
        _graphic, container, _on = COLORS.status(status)
        painter = QPainter(self)
        fill_rounded(painter, QRectF(self.rect()), RADIUS.control, container)
        painter.end()


class EmptyState(QWidget):
    """Icon in a soft circle, title, one line of body, optional action (A4)."""

    def __init__(
        self,
        icon: str,
        title_key: str,
        body_key: str | None = None,
        *,
        action: AppButton | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE.xl, SPACE.xl, SPACE.xl, SPACE.xl)
        layout.setSpacing(SPACE.s)
        layout.addStretch(1)
        self.badge = _IconBadge(icon)
        layout.addWidget(self.badge, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(SPACE.s)
        center = Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
        self.title = TrText(title_key, "title", align=center)
        layout.addWidget(self.title)
        self.body = TrText(body_key or "", "body", "secondary", wrap=True, align=center)
        self.body.setMaximumWidth(SIZES.empty_state)
        self.body.setVisible(bool(body_key))
        layout.addWidget(self.body, 0, Qt.AlignmentFlag.AlignHCenter)
        if action is not None:
            layout.addSpacing(SPACE.s)
            layout.addWidget(action, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch(1)


class _IconBadge(QWidget):
    def __init__(self, icon: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._icon = icon
        side = SIZES.icon_hero
        self.setFixedSize(side, side)

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802 - Qt API
        from parkomate.ui.components.icons import paint_icon

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(Qt.GlobalColor.transparent)
        fill_rounded(painter, rect, RADIUS.pill, COLORS.surface_2)
        side = SIZES.icon_l
        paint_icon(
            painter,
            self._icon,
            QRectF(rect.center().x() - side / 2, rect.center().y() - side / 2, side, side),
            COLORS.text_3,
        )
        painter.end()


class KpiTile(Card):
    """Label (with icon), big value, caption - session summary and counters (M1, A5)."""

    def __init__(
        self,
        label_key: str,
        icon: str,
        icon_color: str = COLORS.text_2,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(compact=True, parent=parent)
        self.layout_.setSpacing(SPACE.xs)
        row = QHBoxLayout()
        row.setSpacing(SPACE.s)
        self.icon_widget = Icon(icon, SIZES.icon, icon_color, filled=True)
        row.addWidget(self.icon_widget)
        self.label = TrText(label_key, "label", "secondary")
        row.addWidget(self.label, 1)
        self.body.addLayout(row)
        self.body.setSpacing(SPACE.xs)
        self.value = Text("-", "headline")
        self.body.addWidget(self.value)
        self.caption = Text("", "caption", "tertiary")
        self.body.addWidget(self.caption)
        self.setMinimumHeight(SIZES.kpi)

    def set_value(self, value: str) -> None:
        self.value.setText(value)
        self.setAccessibleName(f"{self.label.text()} {value}")

    def set_caption_key(self, key: str | None, **params: Any) -> None:
        self.caption.set_key(key, **params)


class InlineMessage(QWidget):
    """One-line outcome with an icon: ok / fail / info. ``text()`` is the message only."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACE.s)
        self.icon = Icon("info", SIZES.icon, COLORS.info, filled=True)
        layout.addWidget(self.icon, 0, Qt.AlignmentFlag.AlignTop)
        self.label = Text("", "body", wrap=True)
        self.label.set_min_lines(1)
        layout.addWidget(self.label, 1)
        self.icon.setVisible(False)
        self.setProperty("status", "")

    def text(self) -> str:
        return self.label.text()

    def _show(self, status: str, icon: str, tone: str, text: str) -> None:
        self.setProperty("status", status)
        graphic, _c, _on = COLORS.status(tone)
        self.icon.set_icon(icon, graphic, filled=True)
        self.icon.setVisible(True)
        self.label.set_tone(tone if tone != "info" else "primary")
        self.label.setText(text)
        self.setAccessibleName(text)

    def ok(self, text: str) -> None:
        self._show("pass", "check_circle", "success", text)

    def fail(self, error: ParkomateError) -> None:
        self._show("fail", "error", "danger", f"{error_title(error)} - {error_cause(error)}")

    def info(self, text: str) -> None:
        self._show("info", "info", "info", text)

    def clear(self) -> None:
        self.setProperty("status", "")
        self.icon.setVisible(False)
        self.label.setText("")


class InlineConfirm(Banner):
    """Inline 'Are you sure?' - never an OS dialog. Cancel (Esc) / Confirm (Enter)."""

    answered = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("warning", parent)
        self.message = self.title
        self.body.setVisible(False)
        buttons = QHBoxLayout()
        buttons.setSpacing(SPACE.s)
        self.no_button = AppButton("action.cancel", variant="outlined", hint_key="key.esc")
        self.yes_button = AppButton("action.confirm", variant="danger_filled", hint_key="key.enter")
        self.no_button.clicked.connect(lambda: self.answered.emit(False))
        self.yes_button.clicked.connect(lambda: self.answered.emit(True))
        buttons.addWidget(self.no_button)
        buttons.addWidget(self.yes_button)
        self.actions.addLayout(buttons)
        self.layout().setAlignment(self.actions, Qt.AlignmentFlag.AlignVCenter)

    def show_confirm(self, message: str, yes_key: str, no_key: str, danger: bool) -> None:
        self.message.setText(message)
        self.setAccessibleName(message)
        self.yes_button.set_text_key(yes_key)
        self.no_button.set_text_key(no_key)
        self.yes_button.set_variant("danger_filled" if danger else "filled")
        self.setVisible(True)


def mark_invalid(widget: QWidget, invalid: bool) -> None:
    set_prop(widget, "invalid", invalid)
