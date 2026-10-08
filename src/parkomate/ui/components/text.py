"""Text: a label painted on the type scale with a FIXED line box.

QLabel lets each line take the height of the tallest font it uses, so a Marathi line (or one
mixing Devanagari and Latin digits) is a few pixels taller than an English one and the whole
screen shifts when the language changes. ``Text`` lays out its lines itself: every line is
exactly ``TYPE.<style>.line`` tall with one baseline for both scripts, and a text bound to an
i18n key reserves the width of its longest translation.

* single line (default): elides with "…" and shows the full text as a tooltip;
* ``wrap=True``: word-wraps, height-for-width.
"""

from __future__ import annotations

import math
from typing import Any

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPaintEvent, QTextLayout, QTextOption
from PySide6.QtWidgets import QLabel, QSizePolicy, QWidget

from parkomate.i18n import t
from parkomate.ui.components.base import key_width, on_language_change
from parkomate.ui.theme.fonts import font_for, line_box
from parkomate.ui.theme.tokens import COLORS, TYPE

TONES = {
    "primary": COLORS.text,
    "secondary": COLORS.text_2,
    "tertiary": COLORS.text_3,
    "accent": COLORS.primary,
    "success": COLORS.on_success_cont,
    "danger": COLORS.on_danger_cont,
    "warning": COLORS.on_warning_cont,
    "info": COLORS.on_info_cont,
    "on_status": COLORS.on_status,
    "on_primary": COLORS.on_primary,
}
_LEGACY_TONES = {"pass": "success", "fail": "danger", "warn": "warning", "pending": "tertiary"}


class Text(QLabel):
    def __init__(
        self,
        text: str = "",
        style: str = "body",
        tone: str = "primary",
        *,
        wrap: bool = False,
        align: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._style_name = style
        self._style = TYPE.style(style)
        self._color = TONES["primary"]
        self._key: str | None = None
        self._params: dict[str, Any] = {}
        self._listening = False
        self._auto_tip = False
        self._strike = False
        self._reserve = 0  # extra width reserved (e.g. for numbers that grow)
        self._min_lines = 1
        self.setFont(font_for(self._style))
        self.setAlignment(align)
        self.setWordWrap(wrap)
        self.set_tone(tone)
        self._apply_policy()
        self.setText(text)

    # ------------------------------------------------------------------ API
    def set_key(self, key: str | None, **params: Any) -> None:
        """Show ``t(key, **params)`` and follow language changes."""
        self._key = key
        self._params = params
        if key and not self._listening:
            on_language_change(self, self._retranslate)
            self._listening = True
        self._retranslate()

    def key(self) -> str | None:
        return self._key

    def _retranslate(self, *_args: object) -> None:
        self.setText(t(self._key, **self._params) if self._key else "")
        self.updateGeometry()

    def set_style(self, style: str) -> None:
        if style == self._style_name:
            return
        self._style_name = style
        self._style = TYPE.style(style)
        font = QFont(font_for(self._style))
        font.setStrikeOut(self._strike)
        self.setFont(font)
        self._apply_policy()
        self.updateGeometry()
        self.update()

    def style_name(self) -> str:
        return self._style_name

    def set_tone(self, tone: str) -> None:
        tone = _LEGACY_TONES.get(tone, tone)
        self.set_color(TONES.get(tone, tone if tone.startswith("#") else COLORS.text))

    def set_color(self, color: str) -> None:
        if color != self._color:
            self._color = color
            self.update()

    def color(self) -> str:
        return self._color

    def set_strike(self, strike: bool) -> None:
        self._strike = strike
        font = QFont(font_for(self._style))
        font.setStrikeOut(strike)
        self.setFont(font)
        self.update()

    def set_min_lines(self, lines: int) -> None:
        """Reserve the height of ``lines`` lines (wrapping text that must not move things)."""
        self._min_lines = max(1, lines)
        self.updateGeometry()

    def reserve_width(self, width: int) -> None:
        self._reserve = width
        self.updateGeometry()

    def setWordWrap(self, on: bool) -> None:  # noqa: N802 - Qt API
        super().setWordWrap(on)
        self._apply_policy()

    def _apply_policy(self) -> None:
        if self.wordWrap():
            policy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
            policy.setHeightForWidth(True)
        else:
            policy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.setSizePolicy(policy)

    # ------------------------------------------------------------------ geometry
    @property
    def line_height(self) -> int:
        return line_box(self._style).height

    def _paragraphs(self) -> list[str]:
        return self.text().split("\n") if self.text() else [""]

    def _natural_width(self) -> int:
        metrics = QFontMetricsF(self.font())
        width = max(metrics.horizontalAdvance(p) for p in self._paragraphs())
        if self._key:
            width = max(width, key_width(self.font(), self._key, **self._params))
        margins = self.contentsMargins()
        return math.ceil(width) + self._reserve + margins.left() + margins.right() + 1

    def _layouts(self, width: float) -> list[QTextLayout]:
        option = QTextOption()
        option.setWrapMode(
            QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere
            if self.wordWrap()
            else QTextOption.WrapMode.NoWrap
        )
        layouts = []
        for paragraph in self._paragraphs():
            layout = QTextLayout(paragraph, self.font())
            layout.setTextOption(option)
            layout.beginLayout()
            while True:
                line = layout.createLine()
                if not line.isValid():
                    break
                line.setLineWidth(max(1.0, width))
            layout.endLayout()
            layouts.append(layout)
        return layouts

    def _line_count(self, width: float) -> int:
        if not self.wordWrap():
            return len(self._paragraphs())
        return max(1, sum(layout.lineCount() for layout in self._layouts(width)))

    def _content_height(self, lines: int) -> int:
        margins = self.contentsMargins()
        return max(lines, self._min_lines) * self.line_height + margins.top() + margins.bottom()

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt API
        natural = self._natural_width()
        if self.wordWrap():
            width = min(natural, max(self.maximumWidth(), 1))
            return QSize(width, self._content_height(self._line_count(width)))
        return QSize(natural, self._content_height(len(self._paragraphs())))

    def minimumSizeHint(self) -> QSize:  # noqa: N802 - Qt API
        if self.wordWrap():
            return QSize(self.line_height * 2, self._content_height(1))
        ellipsis = QFontMetricsF(self.font()).horizontalAdvance("…")
        return QSize(
            min(self._natural_width(), math.ceil(ellipsis) + self.line_height * 2),
            self._content_height(len(self._paragraphs())),
        )

    def hasHeightForWidth(self) -> bool:  # noqa: N802 - Qt API
        return self.wordWrap()

    def heightForWidth(self, width: int) -> int:  # noqa: N802 - Qt API
        margins = self.contentsMargins()
        inner = width - margins.left() - margins.right()
        return self._content_height(self._line_count(inner))

    # ------------------------------------------------------------------ painting
    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802 - Qt API
        rect = QRectF(self.contentsRect())
        if rect.width() <= 0:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        color = QColor(self._color)
        if not self.isEnabled():
            color = QColor(COLORS.text_3)
        painter.setPen(color)
        painter.setFont(self.font())
        box = line_box(self._style)
        align = self.alignment()
        lines: list[tuple[QTextLayout, int]] = []
        elided_any = False
        if self.wordWrap():
            for layout in self._layouts(rect.width()):
                lines.extend((layout, i) for i in range(layout.lineCount()))
        else:
            metrics = QFontMetricsF(self.font())
            for paragraph in self._paragraphs():
                shown = paragraph
                if metrics.horizontalAdvance(paragraph) > rect.width() + 0.5:
                    shown = metrics.elidedText(
                        paragraph, Qt.TextElideMode.ElideRight, rect.width()
                    )
                    elided_any = True
                layout = QTextLayout(shown, self.font())
                option = QTextOption()
                option.setWrapMode(QTextOption.WrapMode.NoWrap)
                layout.setTextOption(option)
                layout.beginLayout()
                line = layout.createLine()
                if line.isValid():
                    line.setLineWidth(rect.width() * 4)
                layout.endLayout()
                lines.append((layout, 0))
        total = len(lines) * box.height
        if total > rect.height():  # squeezed: never draw above the widget
            top = rect.top()
        elif align & Qt.AlignmentFlag.AlignBottom:
            top = rect.bottom() - total
        elif align & Qt.AlignmentFlag.AlignTop:
            top = rect.top()
        else:
            top = rect.top() + (rect.height() - total) / 2
        for index, (layout, number) in enumerate(lines):
            line = layout.lineAt(number)
            width = line.naturalTextWidth()
            if align & Qt.AlignmentFlag.AlignHCenter:
                x = rect.left() + (rect.width() - width) / 2
            elif align & Qt.AlignmentFlag.AlignRight:
                x = rect.right() - width
            else:
                x = rect.left()
            baseline = top + index * box.height + box.baseline
            line.draw(painter, QPointF(x - line.x(), baseline - line.ascent() - line.y()))
        painter.end()
        self._update_tooltip(elided_any)

    def _update_tooltip(self, elided: bool) -> None:
        if elided:
            if not self.toolTip() or self._auto_tip:
                self.setToolTip(self.text())
                self._auto_tip = True
        elif self._auto_tip:
            self.setToolTip("")
            self._auto_tip = False


class TrText(Text):
    """``Text`` bound to an i18n key."""

    def __init__(
        self,
        key: str,
        style: str = "body",
        tone: str = "primary",
        *,
        wrap: bool = False,
        align: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        parent: QWidget | None = None,
        **params: Any,
    ) -> None:
        super().__init__("", style, tone, wrap=wrap, align=align, parent=parent)
        self.set_key(key, **params)


class SelectableText(QLabel):
    """Plain QLabel for text the operator may copy (paths, error details).

    Single line, fixed line-box height so it never moves the layout.
    """

    def __init__(
        self, text: str = "", style: str = "body", tone: str = "secondary", parent: QWidget | None = None
    ) -> None:
        super().__init__(text, parent)
        style_ = TYPE.style(style)
        self.setFont(font_for(style_))
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setWordWrap(True)
        self.setStyleSheet(f"color: {TONES.get(tone, COLORS.text_2)};")
        self.setMinimumHeight(line_box(style_).height)
