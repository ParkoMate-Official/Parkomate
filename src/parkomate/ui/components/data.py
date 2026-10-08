"""DataTable (styled QTableWidget: 48 px rows, sticky header, hover, right-aligned numbers,
column widths that fit the longest header translation, empty state) and StackedBar."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

from PySide6.QtCore import QEvent, QModelIndex, QObject, QPersistentModelIndex, QRectF, QSize, Qt
from PySide6.QtGui import QFontMetricsF, QPainter, QPaintEvent, QResizeEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QSizePolicy,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from parkomate.i18n import t
from parkomate.ui.components.base import draw_line, fill_rounded, key_width, on_language_change
from parkomate.ui.components.cards import EmptyState
from parkomate.ui.components.chips import CHIP_STATES
from parkomate.ui.components.icons import paint_icon
from parkomate.ui.components.text import Text
from parkomate.ui.theme.fonts import font_for
from parkomate.ui.theme.tokens import COLORS, RADIUS, SIZES, SPACE, TYPE


class ChipDelegate(QStyledItemDelegate):
    """Paints a cell as a compact status chip; ``tones`` maps the cell text to a chip state."""

    def __init__(self, tones: dict[str, str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.tones = tones

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> None:
        super().paint(painter, option, QModelIndex())  # background (hover / selection) only
        text = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        if not text:
            return
        state = self.tones.get(text.upper(), "neutral")
        tone, icon, _ = CHIP_STATES.get(state, CHIP_STATES["neutral"])
        graphic, container, on_container = COLORS.status(tone)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        font = font_for(TYPE.caption)
        width = QFontMetricsF(font).horizontalAdvance(text) + SIZES.icon_s + 3 * SPACE.s
        rect = QRectF(
            option.rect.left() + SPACE.l,
            option.rect.center().y() - SIZES.chip_compact / 2,
            width,
            SIZES.chip_compact,
        )
        fill_rounded(painter, rect, RADIUS.chip, container)
        side = SIZES.icon_s
        paint_icon(
            painter,
            icon,
            QRectF(rect.left() + SPACE.s, rect.center().y() - side / 2, side, side),
            graphic,
            filled=True,
        )
        draw_line(
            painter,
            QRectF(rect.left() + SPACE.s * 2 + side, rect.top(), width, rect.height()),
            text,
            TYPE.caption,
            on_container,
        )
        painter.restore()


class DataTable(QTableWidget):
    def __init__(
        self,
        header_keys: Sequence[str],
        *,
        numeric: Iterable[int] = (),
        mono: Iterable[int] = (),
        empty: tuple[str, str, str | None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(0, len(header_keys), parent)
        self._keys = list(header_keys)
        self._numeric = set(numeric)
        self._mono = set(mono)
        self.setFont(font_for(TYPE.body))
        self.setShowGrid(False)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setMouseTracking(True)
        self.setWordWrap(False)
        self.setAlternatingRowColors(False)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setProperty("ring_radius", RADIUS.control)
        vertical = self.verticalHeader()
        vertical.setVisible(False)
        vertical.setDefaultSectionSize(SIZES.table_row)
        vertical.setMinimumSectionSize(SIZES.table_row)
        vertical.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        header = self.horizontalHeader()
        header.setFont(font_for(TYPE.label))
        header.setFixedHeight(SIZES.table_row)
        header.setHighlightSections(False)
        header.setStretchLastSection(True)
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._empty: EmptyState | None = None
        if empty is not None:
            icon, title, body = empty
            self._empty = EmptyState(icon, title, body, parent=self.viewport())
            self.viewport().installEventFilter(self)
        on_language_change(self, self.retranslate)
        self.retranslate()
        self._update_empty()

    # ------------------------------------------------------------------ data
    def fill(self, rows: list[list[str]], data: list[Any] | None = None) -> None:
        self.setRowCount(len(rows))
        mono = font_for(TYPE.mono)
        for r, row in enumerate(rows):
            for c, value in enumerate(row):
                item = QTableWidgetItem(value)
                if c in self._numeric:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                else:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                    )
                if c in self._mono:
                    item.setFont(mono)
                if c == 0 and data is not None:
                    item.setData(Qt.ItemDataRole.UserRole, data[r])
                self.setItem(r, c, item)
        self.fit_columns()
        self._update_empty()

    def selected_data(self) -> list[Any]:
        rows = sorted({index.row() for index in self.selectionModel().selectedRows()})
        values = []
        for row in rows:
            item = self.item(row, 0)
            if item is not None:
                values.append(item.data(Qt.ItemDataRole.UserRole))
        return values

    def fit_columns(self) -> None:
        """Size each column to its content and its LONGEST header translation."""
        header_font = font_for(TYPE.label)
        last = self.columnCount() - 1
        for column, key in enumerate(self._keys):
            if column == last:
                continue
            header = key_width(header_font, key) + 2 * SPACE.l + SPACE.s
            content = self.sizeHintForColumn(column) if self.rowCount() else 0
            self.setColumnWidth(column, max(header, content + SPACE.l))

    def retranslate(self, *_args: object) -> None:
        self.setHorizontalHeaderLabels([t(k) for k in self._keys])
        for column in self._numeric:
            item = self.horizontalHeaderItem(column)
            if item is not None:
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.fit_columns()

    # ------------------------------------------------------------------ empty state
    def _update_empty(self) -> None:
        if self._empty is None:
            return
        self._empty.setVisible(self.rowCount() == 0)
        self._empty.setGeometry(self.viewport().rect())

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._update_empty()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is self.viewport() and event.type() in (QEvent.Type.Resize, QEvent.Type.Show):
            self._update_empty()
        return super().eventFilter(watched, event)

    def empty_state(self) -> EmptyState | None:
        return self._empty

    def sizeHint(self) -> QSize:
        return QSize(super().sizeHint().width(), SIZES.table_row * 6)


class StackedBar(QWidget):
    """Horizontal stacked bar with a legend: e.g. rejected by stage A / B / C / D."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._segments: list[tuple[str, int, str]] = []  # (label, value, colour)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACE.m)
        self._bar = _Bar(self)
        layout.addWidget(self._bar)
        self._legend = QGridLayout()
        self._legend.setHorizontalSpacing(SPACE.xl)
        self._legend.setVerticalSpacing(SPACE.s)
        layout.addLayout(self._legend)
        self._legend_items: list[tuple[_Swatch, Text]] = []

    def set_segments(self, segments: list[tuple[str, int, str]]) -> None:
        self._segments = segments
        while len(self._legend_items) < len(segments):
            row = QHBoxLayout()
            row.setSpacing(SPACE.s)
            swatch = _Swatch()
            label = Text("", "caption", "secondary")
            row.addWidget(swatch)
            row.addWidget(label, 1)
            index = len(self._legend_items)
            self._legend.addLayout(row, index // 2, index % 2)
            self._legend_items.append((swatch, label))
        for index, (swatch, label) in enumerate(self._legend_items):
            if index < len(segments):
                text, value, color = segments[index]
                swatch.color = color
                swatch.update()
                label.setText(f"{text}  {value}")
            swatch.setVisible(index < len(segments))
            label.setVisible(index < len(segments))
        self._bar.update()
        self.setAccessibleDescription(", ".join(f"{s[0]} {s[1]}" for s in segments))

    def segments(self) -> list[tuple[str, int, str]]:
        return list(self._segments)


class _Swatch(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.color = COLORS.outline
        self.setFixedSize(SPACE.m, SPACE.m)

    def paintEvent(self, _event: QPaintEvent) -> None:
        painter = QPainter(self)
        fill_rounded(painter, QRectF(self.rect()), RADIUS.keycap, self.color)
        painter.end()


class _Bar(QWidget):
    def __init__(self, owner: StackedBar) -> None:
        super().__init__(owner)
        self.owner = owner
        self.setFixedHeight(SIZES.stacked_bar)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def paintEvent(self, _event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())
        segments = [s for s in self.owner.segments() if s[1] > 0]
        total = sum(s[1] for s in segments)
        radius = rect.height() / 2
        if total == 0:
            fill_rounded(painter, rect, radius, COLORS.surface_3)
            painter.end()
            return
        gap = SIZES.active_outline
        usable = rect.width() - gap * (len(segments) - 1)
        x = rect.left()
        for _label, value, color in segments:
            width = usable * value / total
            fill_rounded(
                painter, QRectF(x, rect.top(), width, rect.height()), min(radius, width / 2), color
            )
            x += width + gap
        painter.end()
