"""The application stylesheet, generated from the design tokens.

Widgets opt into styles with dynamic properties, e.g. ``variant="primary"`` on a button or
``role="h1"`` on a label, so no colour is hard-coded in a view.
"""

from __future__ import annotations

from parkomate.ui.theme.tokens import COLORS, SIZES, Colors, Sizes


def build_stylesheet(c: Colors = COLORS, s: Sizes = SIZES) -> str:
    return f"""
/* Font family and the 18 px base size come from QApplication.setFont(); setting a font-size
   here would override every widget's setFont(). */
* {{
    color: {c.text};
}}
QMainWindow, QWidget#Root, QWidget#Page {{
    background: {c.bg};
}}
QToolTip {{
    background: {c.tooltip_bg};
    color: {c.tooltip_fg};
    border: none;
    padding: {s.tooltip_padding}px {s.tooltip_padding}px;
    font-size: {s.font_small}px;
}}

/* ---------- cards & text roles ---------- */
QFrame[card="true"] {{
    background: {c.surface};
    border: 1px solid {c.border};
    border-radius: {s.card_radius}px;
}}

/* Accent-bordered step cards with 2px four-sided tone borders */
QFrame[card="true"][tone="pass"] {{
    background: {c.surface};
    border: 2px solid {c.pass_fg};
    border-radius: {s.radius}px;
}}
QFrame[card="true"][tone="fail"] {{
    background: {c.surface};
    border: 2px solid {c.fail_fg};
    border-radius: {s.radius}px;
}}
QFrame[card="true"][tone="info"] {{
    background: {c.surface};
    border: 2px solid {c.info_fg};
    border-radius: {s.radius}px;
}}
QFrame[card="true"][tone="pending"] {{
    background: {c.surface};
    border: 1px solid {c.border};
    border-radius: {s.radius}px;
}}

/* Nested tint panel for metrics */
QFrame[nested_panel="true"] {{
    background: {c.surface_tint};
    border: 1px solid #E2E8DC;
    border-radius: {s.tint_radius}px;
}}

QLabel[role="h1"] {{ font-size: {s.font_h1}px; font-weight: 700; }}
QLabel[role="h2"] {{ font-size: {s.font_h2}px; font-weight: 700; }}
QLabel[role="muted"] {{ color: {c.text_muted}; }}
QLabel[role="small"] {{ font-size: {s.font_small}px; color: {c.text_muted}; }}
QLabel[role="value"] {{ font-size: {s.font_hero}px; font-weight: 700; }}
QLabel[role="value_large"] {{ font-size: {s.font_hero_large}px; font-weight: 700; }}
QLabel[role="hero"] {{ font-size: {s.font_hero}px; font-weight: 700; color: {c.text}; }}
QLabel[role="hero_large"] {{ font-size: {s.font_hero_large}px; font-weight: 700; color: {c.text}; }}
QLabel[role="hint"] {{
    font-size: {s.font_small}px;
    color: {c.text_muted};
}}

/* Tracked uppercase labels for English (handled via dynamic property) */
QLabel[tracked="true"] {{
    text-transform: uppercase;
    letter-spacing: 1.5px;
    font-weight: 700;
    font-size: {s.font_small}px;
    color: {c.accent};
}}

/* ---------- buttons ---------- */
QPushButton {{
    min-height: {s.button_height_secondary}px;
    padding: 0 {s.space_m}px;
    border-radius: {s.radius}px;
    font-weight: 600;
    background: {c.surface};
    border: 2px solid {c.border_strong};
    color: {c.text};
}}
QPushButton:hover {{ background: {c.surface_alt}; }}
QPushButton:pressed {{ background: {c.accent_soft}; }}
QPushButton:focus {{ border: {s.focus_width}px solid {c.focus}; outline: none; }}
QPushButton:disabled {{
    background: {c.disabled_bg};
    color: {c.disabled_fg};
    border: 2px solid {c.disabled_bg};
}}

/* Primary - Olive solid */
QPushButton[variant="primary"] {{
    background: {c.accent};
    color: {c.on_status_solid};
    border: 2px solid {c.accent};
    font-size: {s.font_h2}px;
    min-height: {s.button_height}px;
}}
QPushButton[variant="primary"]:hover {{ background: {c.accent_hover}; border: 2px solid {c.accent_hover}; }}
QPushButton[variant="primary"]:pressed {{ background: {c.accent_pressed}; border: 2px solid {c.accent_pressed}; }}
QPushButton[variant="primary"]:focus {{ border: {s.focus_width}px solid {c.focus}; }}
QPushButton[variant="primary"]:disabled {{
    background: {c.disabled_bg};
    color: {c.disabled_fg};
    border: 2px solid {c.disabled_bg};
}}

/* Secondary - White with border */
QPushButton[variant="secondary"] {{
    background: {c.surface};
    color: {c.text};
    border: 2px solid {c.border_strong};
    font-size: {s.font_base}px;
    min-height: {s.button_height_secondary}px;
}}
QPushButton[variant="secondary"]:hover {{ background: {c.surface_alt}; }}
QPushButton[variant="secondary"]:focus {{ border: {s.focus_width}px solid {c.focus}; }}

/* Danger outline - Red outline for destructive secondary actions */
QPushButton[variant="danger_outline"], QPushButton[variant="danger"] {{
    background: {c.surface};
    color: {c.fail_fg};
    border: 2px solid {c.fail_fg};
    font-size: {s.font_base}px;
    min-height: {s.button_height_secondary}px;
}}
QPushButton[variant="danger_outline"]:hover, QPushButton[variant="danger"]:hover {{ background: {c.fail_bg}; }}
QPushButton[variant="danger_outline"]:focus, QPushButton[variant="danger"]:focus {{ border: {s.focus_width}px solid {c.focus}; }}

/* Pass - Green outline for success actions */
QPushButton[variant="pass"] {{
    background: {c.surface};
    color: {c.pass_fg};
    border: 2px solid {c.pass_fg};
    font-size: {s.font_base}px;
    min-height: {s.button_height_secondary}px;
}}
QPushButton[variant="pass"]:hover {{ background: {c.pass_bg}; }}
QPushButton[variant="pass"]:focus {{ border: {s.focus_width}px solid {c.focus}; }}
QPushButton[variant="pass"]:checked {{
    background: {c.pass_solid};
    color: {c.on_status_solid};
    border: 2px solid {c.pass_solid};
}}
QPushButton[variant="pass"]:disabled, QPushButton[variant="danger_outline"]:disabled {{
    background: {c.disabled_bg};
    color: {c.disabled_fg};
    border: 2px solid {c.disabled_bg};
}}
QPushButton[variant="pass"]:checked:disabled {{
    background: {c.pass_solid};
    color: {c.on_status_solid};
    border: 2px solid {c.pass_solid};
}}

/* Link style */
QPushButton[variant="link"] {{
    min-height: 32px;
    border: none;
    background: transparent;
    color: {c.accent};
    text-decoration: underline;
    font-weight: 400;
    font-size: {s.font_small}px;
    padding: 0 4px;
}}
QPushButton[variant="link"]:focus {{ border: 2px solid {c.focus}; border-radius: 4px; }}

/* Toggle buttons (language switch) */
QPushButton[variant="toggle"] {{
    min-height: 44px;
    padding: 0 {s.space_m}px;
    font-weight: 600;
    background: {c.surface};
    border: 2px solid {c.border_strong};
    color: {c.text};
    border-radius: {s.radius}px;
}}
QPushButton[variant="toggle"]:checked {{
    background: {c.accent};
    color: {c.on_status_solid};
    border: 2px solid {c.accent};
}}
QPushButton[variant="toggle"]:hover {{ background: {c.surface_alt}; }}

/* Takeover - Full screen reject button */
QPushButton[variant="takeover"] {{
    background: {c.surface};
    color: {c.fail_fg};
    border: 3px solid {c.surface};
    font-size: {s.font_h1}px;
    min-height: 72px;
    padding: 0 48px;
    border-radius: {s.radius}px;
}}
QPushButton[variant="takeover"]:focus {{ border: 4px solid {c.text}; }}

/* Small top bar buttons */
QPushButton#TopButton {{ padding: 0 14px; min-height: 40px; font-size: {s.font_base}px; }}

/* ---------- inputs ---------- */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit {{
    min-height: {s.input_height}px;
    padding: 0 {s.space_s}px;
    border: 2px solid {c.border};
    border-radius: {s.radius_input}px;
    background: {c.surface};
    font-size: {s.font_base}px;
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QDateEdit:focus {{
    border: 2px solid {c.surface};
    outline: {s.focus_width}px solid {c.border_strong};
    outline-offset: {s.focus_width}px;
}}
QLineEdit[invalid="true"], QComboBox[invalid="true"], QSpinBox[invalid="true"],
QDoubleSpinBox[invalid="true"] {{
    border: 2px solid {c.fail_fg};
    outline: {s.focus_width}px solid {c.surface};
    outline-offset: {s.focus_width}px;
}}
QComboBox QAbstractItemView {{
    background: {c.surface};
    selection-background-color: {c.accent_soft};
    selection-color: {c.text};
}}
QCheckBox {{ spacing: 12px; min-height: 40px; }}
QCheckBox::indicator {{ width: 28px; height: 28px; }}
QCheckBox:focus {{ color: {c.focus}; }}
QProgressBar {{
    min-height: 16px;
    border: 2px solid {c.border};
    border-radius: 8px;
    background: {c.surface_alt};
    text-align: center;
    font-weight: 700;
    font-size: {s.font_small}px;
}}
QProgressBar::chunk {{
    background: {c.accent_deco};
    border-radius: {s.progress_chunk_radius}px;
}}

/* ---------- tables & lists ---------- */
QTableWidget, QListWidget, QPlainTextEdit {{
    background: {c.surface};
    alternate-background-color: {c.surface_alt};
    border: 1px solid {c.border};
    border-radius: 8px;
    gridline-color: {c.border};
    selection-background-color: {c.accent_soft};
    selection-color: {c.text};
}}
QTableWidget:focus, QListWidget:focus, QPlainTextEdit:focus {{
    border: {s.focus_width}px solid {c.focus};
}}
QHeaderView::section {{
    background: {c.surface_alt};
    border: none;
    border-bottom: 1px solid {c.border};
    padding: 8px;
    font-weight: 700;
    font-size: {s.font_small}px;
}}
QTabWidget::pane {{ border: none; }}
QTabBar::tab {{
    min-height: {s.tab_height}px;
    padding: 0 {s.tab_padding_h}px;
    background: transparent;
    border-bottom: 3px solid transparent;
    font-weight: 600;
    color: {c.text_muted};
    font-size: {s.font_base}px;
}}
QTabBar::tab:selected {{ color: {c.accent}; border-bottom: 3px solid {c.accent}; }}
QTabBar::tab:focus {{ color: {c.focus}; }}
QScrollArea {{ border: none; background: transparent; }}
QScrollArea#CardScroll, QScrollArea#CardScroll > QWidget, QWidget#CardInner {{
    background: transparent;
}}

/* ---------- stage stepper ---------- */
QLabel[step="current"] {{
    background: {c.accent};
    color: {c.on_status_solid};
    border-radius: {s.radius}px;
    padding: 6px 12px;
    font-weight: 600;
}}
QLabel[step="done"] {{ color: {c.pass_fg}; font-weight: 600; }}
QLabel[step="todo"] {{ color: {c.text_muted}; }}
QLabel[step="rejected"] {{
    background: {c.fail_solid};
    color: {c.on_status_solid};
    border-radius: {s.radius}px;
    padding: 6px 12px;
    font-weight: 600;
}}

/* ---------- top bar ---------- */
QFrame#TopBar {{ background: {c.surface}; border-bottom: 1px solid {c.border}; }}
QFrame#ModeBanner {{ background: {c.yellow_soft}; border: none; }}
QFrame#ModeBanner QLabel {{ color: {c.yellow_dark}; font-weight: 600; }}
QFrame#InfoStrip {{ background: {c.surface_alt}; border-bottom: 1px solid {c.border}; }}
QFrame#BottomBar {{ background: {c.surface}; border-top: 1px solid {c.border}; }}
QFrame#Drawer {{ background: {c.surface}; border-left: 2px solid {c.border_strong}; }}

/* ---------- status surfaces ---------- */
QFrame[tone="pass"] {{ background: {c.pass_bg}; border: 2px solid {c.pass_fg}; border-radius: {s.radius}px; }}
QFrame[tone="fail"] {{ background: {c.fail_bg}; border: 2px solid {c.fail_fg}; border-radius: {s.radius}px; }}
QFrame[tone="warn"] {{ background: {c.warn_bg}; border: 4px solid {c.warn_fg}; border-left-width: 4px; border-right-width: 1px; border-top-width: 1px; border-bottom-width: 1px; border-radius: {s.radius}px; }}
QFrame[tone="info"] {{ background: {c.info_bg}; border: 2px solid {c.info_fg}; border-radius: {s.radius}px; }}
QFrame[tone="pending"] {{ background: {c.surface_alt}; border: 2px solid {c.border}; border-radius: {s.radius}px; }}

/* Warning banner with thick left bar */
QFrame[tone="warn_left"] {{
    background: {c.warn_bg};
    border: none;
    border-left: 4px solid {c.warn_fg};
    border-radius: {s.radius}px;
}}

/* Error banner with thick left bar */
QFrame[tone="fail_left"] {{
    background: {c.fail_bg};
    border: none;
    border-left: 4px solid {c.fail_fg};
    border-radius: {s.radius}px;
}}

QLabel[status="pass"] {{ color: {c.pass_fg}; font-weight: 700; }}
QLabel[status="fail"] {{ color: {c.fail_fg}; font-weight: 700; }}
QLabel[status="warn"] {{ color: {c.warn_fg}; font-weight: 700; }}
QLabel[status="info"] {{ color: {c.info_fg}; font-weight: 700; }}
QLabel[status="pending"] {{ color: {c.text_muted}; font-weight: 700; }}

/* Reject takeover - full screen red overlay */
QFrame#RejectTakeover {{ background: {c.fail_solid}; }}
QFrame#RejectTakeover QLabel {{ color: {c.on_status_solid}; }}
QLabel[box_letter="true"] {{
    border: 6px solid {c.on_status_solid};
    border-radius: 24px;
    padding: 0 40px;
    color: {c.on_status_solid};
    font-size: {s.font_box_letter}px;
    font-weight: 700;
}}

/* Success toast - green */
QFrame#SuccessToast {{ background: {c.pass_solid}; border-radius: {s.radius}px; }}
QFrame#SuccessToast QLabel {{ color: {c.on_status_solid}; font-size: {s.font_h1}px; font-weight: 700; }}
"""
