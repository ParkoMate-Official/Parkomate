"""Pieces of the production shell: ProductMark, SimulationBand, AccountButton, DeviceChip,
ContextBar (device · operator · session timer | counters)."""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFontMetricsF, QPainter, QPaintEvent
from PySide6.QtWidgets import QAbstractButton, QHBoxLayout, QSizePolicy, QWidget

from parkomate.ui.components.base import Divider, draw_line, fill_rounded, key_width, qcolor
from parkomate.ui.components.chips import CounterChips
from parkomate.ui.components.icons import Icon, paint_icon
from parkomate.ui.components.text import Text
from parkomate.ui.theme.fonts import font_for
from parkomate.ui.theme.tokens import ALPHA, COLORS, RADIUS, SIZES, SPACE, TYPE


class ProductMark(QWidget):
    """Blue rounded square with a white 'P'."""

    def __init__(self, size: int = SIZES.mark, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(size, size)

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())
        radius = RADIUS.control if self.width() <= SIZES.mark else RADIUS.card
        fill_rounded(painter, rect, radius, COLORS.primary)
        style = TYPE.headline if self.width() > SIZES.mark else TYPE.title
        font = font_for(style)
        font.setWeight(font.Weight.Bold)
        draw_line(painter, rect, "P", style, COLORS.on_primary, align=Qt.AlignmentFlag.AlignHCenter, font=font)
        painter.end()


class SimulationBand(QWidget):
    """Thin full-width amber band at the very top while on the simulated bench (T2)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(SIZES.sim_band)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(COLORS.warning))
        painter.end()


def initials(name: str) -> str:
    parts = [p for p in name.split() if p]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


class AccountButton(QAbstractButton):
    """Avatar (initials) + name + chevron; opens the account menu (T4)."""

    opened = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._name = ""
        self._compact = False
        self._open = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setProperty("ring_radius", RADIUS.pill)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def set_name(self, name: str) -> None:
        self._name = name
        self.setText(name)
        self.setToolTip(name)
        self.updateGeometry()
        self.update()

    def set_compact(self, compact: bool) -> None:
        if compact != self._compact:
            self._compact = compact
            self.updateGeometry()
            self.update()

    def set_open(self, is_open: bool) -> None:
        self._open = is_open
        self.update()

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt API
        width = SIZES.avatar + SPACE.xs + SIZES.icon + SPACE.s
        if not self._compact and self._name:
            width += SPACE.s + int(QFontMetricsF(font_for(TYPE.body)).horizontalAdvance(self._name)) + 1
        return QSize(width + SPACE.xs, SIZES.avatar + SPACE.xs)

    def enterEvent(self, event: object) -> None:  # noqa: N802 - Qt API
        self.update()
        super().enterEvent(event)  # type: ignore[arg-type]

    def leaveEvent(self, event: object) -> None:  # noqa: N802 - Qt API
        self.update()
        super().leaveEvent(event)  # type: ignore[arg-type]

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())
        if self.underMouse() or self._open:
            fill_rounded(painter, rect, RADIUS.pill, qcolor(COLORS.text, ALPHA.hover))
        avatar = QRectF(rect.left() + SPACE.xs / 2, rect.center().y() - SIZES.avatar / 2, SIZES.avatar, SIZES.avatar)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(COLORS.primary_cont))
        painter.drawEllipse(avatar)
        draw_line(painter, avatar, initials(self._name), TYPE.label, COLORS.on_primary_cont,
                  align=Qt.AlignmentFlag.AlignHCenter)
        x = avatar.right() + SPACE.s
        if not self._compact and self._name:
            width = draw_line(painter, QRectF(x, rect.top(), rect.width(), rect.height()),
                              self._name, TYPE.body, COLORS.text, elide=False)
            x += width + SPACE.xs
        side = SIZES.icon
        paint_icon(painter, "expand_less" if self._open else "expand_more",
                   QRectF(x, rect.center().y() - side / 2, side, side), COLORS.text_2)
        painter.end()


class DeviceChip(QWidget):
    """Device ID (big) + MAC (small, monospace); or 'No device on the bench'."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACE.s)
        self.icon = Icon("memory", SIZES.icon_m, COLORS.text_2)
        layout.addWidget(self.icon)
        self.primary = Text("", "body_lg_strong")
        self.secondary = Text("", "mono_label", "secondary")
        layout.addWidget(self.primary)
        layout.addWidget(self.secondary)
        layout.addStretch(1)
        sample_id = QFontMetricsF(font_for(TYPE.body_lg_strong)).horizontalAdvance("PKM-000000")
        sample_mac = QFontMetricsF(font_for(TYPE.mono_label)).horizontalAdvance("00:00:00:00:00:00")
        empty = key_width(font_for(TYPE.body_lg_strong), "info.device_none")
        self.setFixedWidth(
            int(SIZES.icon_m + 2 * SPACE.s + max(sample_id + sample_mac, empty)) + SPACE.s
        )
        self.set_device(None, None)

    def set_device(self, device_id: str | None, mac: str | None) -> None:
        if mac is None:
            self.primary.set_key("info.device_none")
            self.primary.set_tone("tertiary")
            self.secondary.setText("")
        elif device_id:
            self.primary.set_key(None)
            self.primary.setText(device_id)
            self.primary.set_tone("primary")
            self.secondary.setText(mac)
        else:
            self.primary.set_key(None)
            self.primary.setText(mac)
            self.primary.set_tone("primary")
            self.secondary.setText("")
        self.secondary.setVisible(bool(self.secondary.text()))
        description = " ".join(x for x in (self.primary.text(), self.secondary.text()) if x)
        self.setAccessibleName(description)


class ContextBar(QWidget):
    """48 px on surface_2: device chip · operator · session timer | counter chips (T6)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(SIZES.context_bar)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(SIZES.page_margin, 0, SIZES.page_margin, 0)
        layout.setSpacing(SPACE.m)
        self.device = DeviceChip()
        layout.addWidget(self.device)
        layout.addWidget(Divider(vertical=True))
        layout.addWidget(Icon("person", SIZES.icon_m, COLORS.text_2))
        self.operator = Text("", "body")
        self.operator_code = Text("", "mono_label", "tertiary")
        layout.addWidget(self.operator)
        layout.addWidget(self.operator_code)
        layout.addWidget(Divider(vertical=True))
        layout.addWidget(Icon("schedule", SIZES.icon_m, COLORS.text_2))
        self.timer = Text("00:00:00", "mono")
        self.timer.setFixedWidth(self.timer.sizeHint().width())
        layout.addWidget(self.timer)
        layout.addStretch(1)
        self.counters = CounterChips()
        layout.addWidget(self.counters)
        for divider in self.findChildren(Divider):
            divider.setFixedHeight(SIZES.icon_m)

    def set_operator(self, name: str, code: str) -> None:
        self.operator.setText(name)
        self.operator_code.setText(code)

    def set_elapsed(self, text: str) -> None:
        self.timer.setText(text)

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        rect = self.rect()
        painter.fillRect(rect, QColor(COLORS.surface_2))
        painter.fillRect(QRectF(0, rect.height() - SIZES.hairline, rect.width(), SIZES.hairline),
                         QColor(COLORS.outline_soft))
        painter.end()
