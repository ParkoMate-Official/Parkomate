"""Stepper (horizontal, the four production stages) and StepList (vertical steps inside a
stage).

Stepper: numbered circles joined by a line; upcoming / active / done (check) / rejected
(cross); the line fills up to the active stage. Every label is as wide as its longest
translation, so the stepper never moves when the language changes (T1).

StepList: small indicators (28 px) on a connecting line - smaller and quieter than the stage
stepper so the numbers never compete with it (P1).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget

from parkomate.i18n import t
from parkomate.ui.components.base import draw_line, key_width, on_language_change, qcolor
from parkomate.ui.components.buttons import paint_spinner
from parkomate.ui.components.icons import paint_icon
from parkomate.ui.components.text import Text, TrText
from parkomate.ui.theme.fonts import font_for
from parkomate.ui.theme.motion import FrameClock, Tween
from parkomate.ui.theme.tokens import ALPHA, COLORS, MOTION, SIZES, SPACE, TYPE


def _paint_dot(
    painter: QPainter,
    rect: QRectF,
    state: str,
    number: str,
    *,
    small: bool = False,
    halo: float = 0.0,
) -> None:
    """One step indicator: upcoming / active / working / done / rejected / error."""
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    icon_side = rect.width() * 0.62
    icon_rect = QRectF(
        rect.center().x() - icon_side / 2, rect.center().y() - icon_side / 2, icon_side, icon_side
    )
    if halo > 0:
        grow = SPACE.xs * halo
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(qcolor(COLORS.primary, ALPHA.track * 1.5))
        painter.drawEllipse(rect.adjusted(-grow, -grow, grow, grow))
    style = TYPE.caption if small else TYPE.label
    if state in ("done", "pass"):
        fill = COLORS.on_success_cont if small else COLORS.primary
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(fill))
        painter.drawEllipse(rect)
        paint_icon(painter, "check", icon_rect, COLORS.on_status)
    elif state in ("rejected", "fail"):
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(COLORS.danger))
        painter.drawEllipse(rect)
        paint_icon(painter, "close", icon_rect, COLORS.on_status)
    elif state == "error":
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(COLORS.warning))
        painter.drawEllipse(rect)
        paint_icon(painter, "priority_high", icon_rect, COLORS.on_status)
    elif state == "working":
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(COLORS.primary_cont))
        painter.drawEllipse(rect)
        paint_spinner(
            painter, rect, COLORS.primary, FrameClock.instance().phase(MOTION.spin_period)
        )
    elif state == "active":
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(COLORS.primary))
        painter.drawEllipse(rect)
        draw_line(
            painter, rect, number, style, COLORS.on_primary, align=Qt.AlignmentFlag.AlignHCenter
        )
    else:  # upcoming / pending
        inset = SIZES.hairline
        painter.setPen(QPen(QColor(COLORS.outline_strong if not small else COLORS.outline), inset))
        painter.setBrush(QColor(COLORS.surface))
        painter.drawEllipse(rect.adjusted(inset / 2, inset / 2, -inset / 2, -inset / 2))
        draw_line(
            painter,
            rect,
            number,
            style,
            COLORS.text_2 if not small else COLORS.text_3,
            align=Qt.AlignmentFlag.AlignHCenter,
        )
    painter.restore()


class _StageDot(QWidget):
    def __init__(self, number: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.number = number
        self.state = "upcoming"
        self._halo = Tween(self, lambda _v: self.update(), ms=MOTION.medium)
        self.setFixedSize(SIZES.stepper_dot + 2 * SPACE.xs, SIZES.stepper_dot + 2 * SPACE.xs)

    def set_state(self, state: str) -> None:
        if state != self.state:
            self.state = state
            self._halo.to(1.0 if state == "active" else 0.0)
            self.update()

    def paintEvent(self, _event: QPaintEvent) -> None:
        painter = QPainter(self)
        side = SIZES.stepper_dot
        rect = QRectF(SPACE.xs, SPACE.xs, side, side)
        _paint_dot(painter, rect, self.state, str(self.number), halo=self._halo.value)
        painter.end()


class _Connector(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._fill = Tween(self, lambda _v: self.update(), ms=MOTION.slow)
        self.setFixedSize(SIZES.stepper_segment, SIZES.stepper_dot)

    def set_filled(self, filled: bool) -> None:
        self._fill.to(1.0 if filled else 0.0)

    def paintEvent(self, _event: QPaintEvent) -> None:
        painter = QPainter(self)
        y = self.height() / 2
        line = SIZES.stepper_line
        painter.fillRect(QRectF(0, y - line / 2, self.width(), line), QColor(COLORS.outline))
        done = self.width() * self._fill.value
        if done > 0:
            painter.fillRect(QRectF(0, y - line / 2, done, line), QColor(COLORS.primary))
        painter.end()


class Stepper(QWidget):
    """Stages with states. ``set_states(["done", "active", "upcoming", ...])``."""

    def __init__(self, label_keys: Sequence[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACE.xs)
        self._keys = list(label_keys)
        self._dots: list[_StageDot] = []
        self._labels: list[Text] = []
        self._connectors: list[_Connector] = []
        self._states = ["upcoming"] * len(self._keys)
        for index, key in enumerate(self._keys):
            if index:
                connector = _Connector()
                self._connectors.append(connector)
                layout.addSpacing(SPACE.xs)
                layout.addWidget(connector)
                layout.addSpacing(SPACE.xs)
            dot = _StageDot(index + 1)
            label = TrText(key, "body", "secondary")
            # reserve the semibold width of the longest translation: never moves (T1)
            label.setFixedWidth(key_width(font_for(TYPE.body_strong), key) + SIZES.hairline)
            self._dots.append(dot)
            self._labels.append(label)
            layout.addWidget(dot)
            layout.addWidget(label)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        on_language_change(self, self._describe)
        self._describe()

    def label(self, index: int) -> Text:
        return self._labels[index]

    def states(self) -> list[str]:
        return list(self._states)

    def set_states(self, states: Sequence[str]) -> None:
        self._states = list(states)
        for index, state in enumerate(self._states):
            self._dots[index].set_state(state)
            label = self._labels[index]
            # the active label is bolder; the width is reserved for the bold style anyway
            label.set_style("body_strong" if state in ("active", "rejected") else "body")
            label.set_tone(
                "primary"
                if state == "active"
                else ("danger" if state == "rejected" else "secondary")
            )
        for index, connector in enumerate(self._connectors):
            connector.set_filled(self._states[index + 1] != "upcoming")
        self._describe()

    def _describe(self, *_args: object) -> None:
        words = {
            "done": "stepper.done",
            "active": "stepper.current",
            "rejected": "stepper.rejected",
            "upcoming": "stepper.todo",
        }
        parts = [
            f"{t(key)}: {t(words.get(state, 'stepper.todo'))}"
            for key, state in zip(self._keys, self._states, strict=True)
        ]
        self.setAccessibleName(", ".join(parts))


class StepItem(QWidget):
    """One row of a StepList: indicator on the connecting line, title, caption, body."""

    def __init__(self, number: int, title_key: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.number = number
        self.state = "pending"
        self.last = False
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(SPACE.l)
        self._gutter = QWidget()
        self._gutter.setFixedWidth(SIZES.step_dot)
        outer.addWidget(self._gutter)
        column = QVBoxLayout()
        column.setContentsMargins(0, 0, 0, SPACE.xl)
        column.setSpacing(SPACE.s)
        header = QHBoxLayout()
        header.setSpacing(SPACE.s)
        self.title = TrText(title_key, "body_lg_strong", "secondary")
        self.title.setMinimumHeight(SIZES.step_dot)
        header.addWidget(self.title, 1)
        self.caption = Text("", "caption", "tertiary")
        self.caption.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        header.addWidget(self.caption)
        column.addLayout(header)
        self.body = QVBoxLayout()
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(SPACE.s)
        column.addLayout(self.body)
        outer.addLayout(column, 1)
        self._column = column

    def set_last(self, last: bool) -> None:
        self.last = last
        self._column.setContentsMargins(0, 0, 0, 0 if last else SPACE.xl)
        self.update()

    def set_state(self, state: str, caption_key: str | None = None, **params: Any) -> None:
        was_working = self.state == "working"
        self.state = state
        self.title.set_tone("primary" if state != "pending" else "secondary")
        self.caption.set_key(caption_key, **params)
        self.caption.set_tone(
            {"pass": "success", "fail": "danger", "error": "warning", "working": "info"}.get(
                state, "tertiary"
            )
        )
        clock = FrameClock.instance()
        if state == "working":
            clock.subscribe(self, self.update)
        elif was_working:
            clock.unsubscribe(self)
        self.update()

    def paintEvent(self, _event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        side = SIZES.step_dot
        top = max(0.0, self.title.geometry().center().y() - side / 2)
        dot = QRectF(0, top, side, side)
        if not self.last:
            line = SIZES.stepper_line
            color = COLORS.on_success_cont if self.state == "pass" else COLORS.outline
            painter.fillRect(
                QRectF(
                    dot.center().x() - line / 2,
                    dot.bottom() + SPACE.xs,
                    line,
                    self.height() - dot.bottom() - 2 * SPACE.xs,
                ),
                QColor(color),
            )
        _paint_dot(painter, dot, self.state, str(self.number), small=True)
        painter.end()


class StepList(QWidget):
    def __init__(self, title_keys: Sequence[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.items = [StepItem(i + 1, key) for i, key in enumerate(title_keys)]
        for item in self.items:
            layout.addWidget(item)
        self.items[-1].set_last(True)
