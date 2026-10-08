"""Layout helpers: transparent scroll areas and the 12-column production grid."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from parkomate.ui.theme.tokens import SIZES, SPACE


class ScrollArea(QScrollArea):
    """Frameless scroll area whose viewport is ALWAYS transparent (the A1 bug: an unstyled
    viewport took the OS dark palette)."""

    def __init__(self, parent: QWidget | None = None, *, horizontal: bool = False) -> None:
        super().__init__(parent)
        self.setObjectName("Scroll")
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        if not horizontal:
            self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.viewport().setAutoFillBackground(False)
        self.content = QWidget()
        self.content.setObjectName("ScrollContent")
        self.content.setAutoFillBackground(False)
        self.content.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.layout_ = QVBoxLayout(self.content)
        self.layout_.setContentsMargins(0, 0, 0, 0)
        self.layout_.setSpacing(SPACE.l)
        self.setWidget(self.content)


def column_grid(left: QWidget, right: QWidget) -> QHBoxLayout:
    """Two columns on the 12-column grid: left 5 / right 7, gutter 16 - exact proportions,
    independent of the content (and so of the language)."""
    layout = QHBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(SPACE.l)
    for widget in (left, right):
        policy = widget.sizePolicy()
        policy.setHorizontalPolicy(QSizePolicy.Policy.Ignored)
        widget.setSizePolicy(policy)
    layout.addWidget(left, SIZES.left_columns)
    layout.addWidget(right, SIZES.grid_columns - SIZES.left_columns)
    return layout
