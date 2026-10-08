"""The application palette, built from the tokens.

Windows 11 in dark mode hands Qt a dark palette (window #1E1E1E, white placeholder text).
Every widget the stylesheet does not paint fell back to it - that was the near-black Admin
Settings scroll area (A1) and the invisible placeholders. The station is a light UI: the
palette is always this one, whatever the OS colour scheme.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication, QPalette

from parkomate.ui.theme.tokens import COLORS, Colors


def build_palette(c: Colors = COLORS) -> QPalette:
    palette = QPalette()
    roles = {
        QPalette.ColorRole.Window: c.bg,
        QPalette.ColorRole.WindowText: c.text,
        QPalette.ColorRole.Base: c.surface,
        QPalette.ColorRole.AlternateBase: c.surface_2,
        QPalette.ColorRole.Text: c.text,
        QPalette.ColorRole.Button: c.surface,
        QPalette.ColorRole.ButtonText: c.text,
        QPalette.ColorRole.BrightText: c.on_primary,
        QPalette.ColorRole.Highlight: c.primary_cont,
        QPalette.ColorRole.HighlightedText: c.text,
        QPalette.ColorRole.ToolTipBase: c.text,
        QPalette.ColorRole.ToolTipText: c.surface,
        QPalette.ColorRole.PlaceholderText: c.text_3,
        QPalette.ColorRole.Link: c.primary,
        QPalette.ColorRole.LinkVisited: c.primary_hov,
        QPalette.ColorRole.Light: c.surface,
        QPalette.ColorRole.Midlight: c.surface_2,
        QPalette.ColorRole.Mid: c.outline,
        QPalette.ColorRole.Dark: c.outline_strong,
        QPalette.ColorRole.Shadow: c.text,
        QPalette.ColorRole.Accent: c.primary,
    }
    for role, value in roles.items():
        palette.setColor(role, QColor(value))
    for role in (
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
    ):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(c.text_3))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Base, QColor(c.surface_3))
    return palette


def force_light_scheme() -> None:
    """Ask Qt for the light colour scheme (Qt >= 6.8); harmless where unsupported."""
    app = QGuiApplication.instance()
    if not isinstance(app, QGuiApplication):
        return
    hints = app.styleHints()
    setter = getattr(hints, "setColorScheme", None)
    if setter is not None:
        setter(Qt.ColorScheme.Light)
