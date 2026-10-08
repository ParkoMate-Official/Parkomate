"""SegmentedControl (2-4 options, sliding thumb), LanguageSwitch, PassFailToggle.

Every segment is as wide as the widest option in ANY language, so the control never changes
width when the language changes (T3).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QEnterEvent, QFontMetricsF, QPainter, QPainterPath, QPaintEvent
from PySide6.QtWidgets import QAbstractButton, QButtonGroup, QHBoxLayout, QSizePolicy, QWidget

from parkomate.i18n import t
from parkomate.ui.components.base import (
    draw_line,
    fill_rounded,
    key_width,
    on_language_change,
    qcolor,
)
from parkomate.ui.components.icons import Icon, paint_icon
from parkomate.ui.theme.fonts import font_for
from parkomate.ui.theme.motion import Tween
from parkomate.ui.theme.tokens import ALPHA, COLORS, MOTION, RADIUS, SIZES, SPACE, TYPE


class _Segment(QAbstractButton):
    def __init__(self, control: SegmentedControl, value: Any, key: str) -> None:
        super().__init__(control)
        self.control = control
        self.value = value
        self.key = key
        self.setCheckable(True)
        self.setAutoExclusive(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setProperty("ring_radius", RADIUS.pill)
        self.setText(t(key))

    def sizeHint(self) -> QSize:
        return QSize(self.control.segment_width(), self.control.height_px)

    def paintEvent(self, _event: QPaintEvent) -> None:
        painter = QPainter(self)
        style = TYPE.body_strong if self.isChecked() and not self.control.small else TYPE.body
        color = COLORS.on_primary_cont if self.isChecked() else COLORS.text_2
        if not self.isEnabled():
            color = COLORS.text_3
        draw_line(
            painter,
            QRectF(self.rect()),
            self.text(),
            style,
            color,
            align=Qt.AlignmentFlag.AlignHCenter,
        )
        painter.end()


class SegmentedControl(QWidget):
    """Pill track with a sliding thumb behind the selected option."""

    changed = Signal(object)

    def __init__(
        self,
        options: Sequence[tuple[Any, str]],
        *,
        height: int = SIZES.segmented,
        small: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.height_px = height
        self.small = small
        self._options = list(options)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._segments: dict[Any, _Segment] = {}
        layout = QHBoxLayout(self)
        inset = SIZES.hairline + SPACE.xs // 2
        layout.setContentsMargins(inset, inset, inset, inset)
        layout.setSpacing(0)
        for value, key in self._options:
            segment = _Segment(self, value, key)
            segment.clicked.connect(lambda _c=False, v=value: self._clicked(v))
            self._group.addButton(segment)
            self._segments[value] = segment
            layout.addWidget(segment)
        self._thumb = Tween(self, lambda _v: self.update(), ms=MOTION.medium)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        on_language_change(self, self.retranslate)
        if self._options:
            self.set_value(self._options[0][0], animate=False)

    def segment_width(self) -> int:
        font = font_for(TYPE.body_strong)
        widest = max(key_width(font, key) for _value, key in self._options)
        return widest + 2 * SPACE.l

    def sizeHint(self) -> QSize:
        margins = self.contentsMargins()
        return QSize(
            self.segment_width() * len(self._options) + margins.left() + margins.right(),
            self.height_px,
        )

    def button(self, value: Any) -> QAbstractButton:
        return self._segments[value]

    def value(self) -> Any:
        for value, segment in self._segments.items():
            if segment.isChecked():
                return value
        return None

    def set_value(self, value: Any, *, animate: bool = True) -> None:
        segment = self._segments.get(value)
        if segment is None:
            return
        segment.setChecked(True)
        index = [v for v, _k in self._options].index(value)
        if animate:
            self._thumb.to(float(index))
        else:
            self._thumb.jump(float(index))

    def _clicked(self, value: Any) -> None:
        self.set_value(value)
        self.changed.emit(value)

    def retranslate(self, *_args: object) -> None:
        for segment in self._segments.values():
            segment.setText(t(segment.key))
            segment.update()

    def paintEvent(self, _event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())
        fill_rounded(painter, rect, RADIUS.pill, COLORS.surface_2, COLORS.outline, SIZES.hairline)
        segments = list(self._segments.values())
        if segments:
            first = segments[0].geometry()
            width = first.width()
            x = first.x() + self._thumb.value * width
            thumb = QRectF(x, first.y(), width, first.height())
            fill_rounded(painter, thumb, RADIUS.pill, COLORS.primary_cont)
        painter.end()


class LanguageSwitch(SegmentedControl):
    """English | मराठी - one segmented control (names always in their own script)."""

    language_selected = Signal(str)

    def __init__(self, languages: Sequence[str] = ("en", "mr"), parent: QWidget | None = None):
        super().__init__([(code, f"language.{code}") for code in languages], parent=parent)
        self.changed.connect(lambda code: self.language_selected.emit(str(code)))
        self._sync_names()

    def sync(self, language: str) -> None:
        self.set_value(language)
        self._sync_names()

    def retranslate(self, *_args: object) -> None:
        super().retranslate()
        self._sync_names()

    def _sync_names(self) -> None:
        for code, segment in self._segments.items():
            segment.setAccessibleName(t("a11y.language_switch", language=t(f"language.{code}")))


class _ToggleHalf(QAbstractButton):
    def __init__(self, owner: PassFailToggle, positive: bool, key: str) -> None:
        super().__init__(owner)
        self.owner = owner
        self.positive = positive
        self.key = key
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setProperty("ring_radius", RADIUS.control)
        self.setText(t(key))

    def sizeHint(self) -> QSize:
        return QSize(self.owner.half_width(), SIZES.button_compact)

    def paintEvent(self, _event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())
        selected = self.isChecked()
        dimmed = not self.isEnabled() and not selected
        if dimmed:
            painter.setOpacity(ALPHA.disabled)
        if selected:
            fill = COLORS.on_success_cont if self.positive else COLORS.danger
            content = COLORS.on_status
            border = None
        else:
            fill = COLORS.surface
            content = COLORS.text
            border = COLORS.outline_strong
        path = _half_path(rect, RADIUS.control, left=self.positive)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(fill))
        painter.drawPath(path)
        if border is not None:
            painter.setPen(QColor(border))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            inset = SIZES.hairline / 2
            painter.drawPath(
                _half_path(
                    rect.adjusted(inset, inset, -inset, -inset), RADIUS.control, left=self.positive
                )
            )
        if self.underMouse() and self.isEnabled() and not selected:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(qcolor(COLORS.text, ALPHA.hover))
            painter.drawPath(path)
        icon = "check" if self.positive else "close"
        font = font_for(TYPE.button_sm)
        painter.setFont(font)
        label_w = QFontMetricsF(font).horizontalAdvance(self.text())
        group = SIZES.icon + SPACE.s + label_w
        x = rect.left() + (rect.width() - group) / 2
        paint_icon(
            painter,
            icon,
            QRectF(x, rect.center().y() - SIZES.icon / 2, SIZES.icon, SIZES.icon),
            content,
        )
        draw_line(
            painter,
            QRectF(x + SIZES.icon + SPACE.s, rect.top(), label_w + 1, rect.height()),
            self.text(),
            TYPE.button_sm,
            content,
            elide=False,
        )
        painter.end()

    def enterEvent(self, event: QEnterEvent) -> None:
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event: Any) -> None:
        self.update()
        super().leaveEvent(event)


def _half_path(rect: QRectF, radius: float, *, left: bool) -> QPainterPath:
    path = QPainterPath()
    path.addRoundedRect(rect, radius, radius)
    square = QPainterPath()
    if left:
        square.addRect(QRectF(rect.center().x(), rect.top(), rect.width() / 2, rect.height()))
    else:
        square.addRect(QRectF(rect.left(), rect.top(), rect.width() / 2, rect.height()))
    return path.united(square).simplified()


class PassFailToggle(QWidget):
    """[✓ Success | ✕ Failure]: outlined neutral until marked; marked Success = filled green
    with a check, Failure = filled red with a cross; not available yet = 40 % + lock (S2)."""

    def __init__(
        self,
        success_key: str = "action.mark_success",
        failure_key: str = "action.mark_failure",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.success = _ToggleHalf(self, True, success_key)
        self.failure = _ToggleHalf(self, False, failure_key)
        layout.addWidget(self.success)
        layout.addWidget(self.failure)
        layout.addSpacing(SPACE.s)
        self.lock = Icon("lock", SIZES.icon, COLORS.text_3)
        policy = self.lock.sizePolicy()
        policy.setRetainSizeWhenHidden(True)  # the hint never moves the toggle
        self.lock.setSizePolicy(policy)
        self.lock.setVisible(False)
        layout.addWidget(self.lock)
        self._lock_key: str | None = None
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        on_language_change(self, self.retranslate)

    def half_width(self) -> int:
        font = font_for(TYPE.button_sm)
        widest = max(key_width(font, self.success.key), key_width(font, self.failure.key))
        return widest + SIZES.icon + SPACE.s + 2 * SPACE.l

    def set_locked(self, key: str | None) -> None:
        """Show the lock hint (with this reason as tooltip) while marking is not possible."""
        self._lock_key = key
        self.lock.setVisible(bool(key))
        self.retranslate()

    def retranslate(self, *_args: object) -> None:
        self.success.setText(t(self.success.key))
        self.failure.setText(t(self.failure.key))
        tip = t(self._lock_key) if self._lock_key else ""
        self.lock.setToolTip(tip)
        for half in (self.success, self.failure):
            half.setToolTip(tip if not half.isEnabled() else "")
            half.setAccessibleDescription(tip)
            half.update()
