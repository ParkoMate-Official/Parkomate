"""The application stylesheet, generated from the design tokens.

Most components paint themselves from the tokens (buttons, chips, cards, stepper, ...). The
stylesheet covers the native Qt widgets that remain - inputs, tables, lists, scroll bars,
tool tips, the calendar popup - so no Windows-style widget leaks through (G5).

Widgets opt into variants with dynamic properties (``invalid="true"`` on an input, ...).
"""

from __future__ import annotations

from parkomate.ui.theme.tokens import (
    COLORS,
    RADIUS,
    SIZES,
    SPACE,
    TYPE,
    Colors,
    Radius,
    Sizes,
    Spacing,
    Typography,
)


def build_stylesheet(
    c: Colors = COLORS,
    s: Sizes = SIZES,
    sp: Spacing = SPACE,
    r: Radius = RADIUS,
    ty: Typography = TYPE,
) -> str:
    field_inner = s.input - 2 * s.hairline
    return f"""
/* Fonts come from QApplication.setFont() / widget.setFont() (type scale); a font-size here
   would override them, so only the native widgets below set one. */
* {{ outline: none; }}
QMainWindow, QWidget#Root, QWidget#Page {{ background: {c.bg}; }}
QWidget#Surface {{ background: {c.surface}; }}
QToolTip {{
    background: {c.text};
    color: {c.surface};
    border: none;
    padding: {sp.s}px {sp.m}px;
    font-size: {ty.caption.size}px;
}}

/* ---------- scroll areas: always transparent (A1) ---------- */
QScrollArea, QScrollArea > QWidget, QScrollArea > QWidget > QWidget#ScrollContent {{
    background: transparent;
    border: none;
}}
QScrollBar:vertical {{
    background: transparent;
    width: {sp.m}px;
    margin: {sp.xs}px {sp.xs // 2}px;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: {sp.m}px;
    margin: {sp.xs // 2}px {sp.xs}px;
}}
QScrollBar::handle:vertical {{
    background: {c.outline};
    border-radius: {sp.xs}px;
    min-height: {sp.xxxl}px;
    margin: 0 {sp.xs // 2}px;
}}
QScrollBar::handle:horizontal {{
    background: {c.outline};
    border-radius: {sp.xs}px;
    min-width: {sp.xxxl}px;
    margin: {sp.xs // 2}px 0;
}}
QScrollBar::handle:hover {{ background: {c.outline_strong}; }}
QScrollBar::add-line, QScrollBar::sub-line {{
    width: 0; height: 0; border: none; background: none;
}}
QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}

/* ---------- inputs (TextField, PasswordField, NumberField) ---------- */
QLineEdit, QAbstractSpinBox {{
    min-height: {field_inner}px;
    max-height: {field_inner}px;
    padding: 0 {s.input_pad}px;
    border: {s.hairline}px solid {c.outline};
    border-radius: {r.control}px;
    background: {c.surface_2};
    color: {c.text};
    selection-background-color: {c.primary_cont};
    selection-color: {c.text};
}}
QLineEdit:hover, QAbstractSpinBox:hover {{ border-color: {c.outline_strong}; }}
QLineEdit:focus, QAbstractSpinBox:focus {{
    background: {c.surface};
    border: {s.hairline}px solid {c.primary};
}}
QLineEdit[invalid="true"], QAbstractSpinBox[invalid="true"] {{
    background: {c.surface};
    border: {s.hairline}px solid {c.danger};
}}
QLineEdit:disabled, QAbstractSpinBox:disabled {{
    background: {c.surface_3};
    color: {c.text_3};
    border-color: {c.outline_soft};
}}
QAbstractSpinBox::up-button, QAbstractSpinBox::down-button {{
    width: 0; height: 0; border: none;
}}
QLineEdit[trailing="true"] {{ padding-right: {s.input_pad + s.icon_m + sp.s}px; }}

/* ---------- Select popup list ---------- */
QListView#SelectList {{
    background: {c.surface};
    border: none;
    outline: 0;
    padding: {sp.xs}px 0;
}}

/* ---------- DataTable ---------- */
QTableView {{
    background: {c.surface};
    alternate-background-color: {c.surface};
    border: none;
    gridline-color: transparent;
    selection-background-color: {c.primary_cont};
    selection-color: {c.text};
    outline: 0;
}}
QTableView::item {{
    padding: 0 {sp.l}px;
    border: none;
    border-bottom: {s.hairline}px solid {c.outline_soft};
}}
QTableView::item:hover {{ background: {c.surface_2}; }}
QTableView::item:selected {{ background: {c.primary_cont}; color: {c.text}; }}
QHeaderView {{ background: {c.surface_2}; border: none; }}
QHeaderView::section {{
    background: {c.surface_2};
    color: {c.text_2};
    border: none;
    border-bottom: {s.hairline}px solid {c.outline};
    padding: 0 {sp.l}px;
    min-height: {s.table_row}px;
    font-size: {ty.label.size}px;
    font-weight: {ty.label.weight};
}}
QTableCornerButton::section {{ background: {c.surface_2}; border: none; }}

/* ---------- plain lists (session drawer) ---------- */
QListWidget {{
    background: transparent;
    border: none;
    outline: 0;
}}
QListWidget::item {{
    min-height: {s.list_row}px;
    padding: 0 {sp.s}px;
    border-bottom: {s.hairline}px solid {c.outline_soft};
    color: {c.text};
}}
QListWidget::item:selected {{ background: {c.primary_cont}; color: {c.text}; }}

/* ---------- read-only details (error log JSON) ---------- */
QPlainTextEdit {{
    background: {c.surface_2};
    border: none;
    border-radius: {r.control}px;
    padding: {sp.m}px;
    color: {c.text};
    selection-background-color: {c.primary_cont};
    selection-color: {c.text};
}}

/* ---------- calendar (DateRangePicker popup) ---------- */
QCalendarWidget QWidget#qt_calendar_navigationbar {{
    background: {c.surface};
    min-height: {s.button_compact}px;
}}
QCalendarWidget QToolButton {{
    color: {c.text};
    background: transparent;
    border: none;
    border-radius: {r.chip}px;
    padding: {sp.xs}px {sp.s}px;
    font-size: {ty.body_strong.size}px;
    font-weight: {ty.body_strong.weight};
}}
QCalendarWidget QToolButton:hover {{ background: {c.surface_2}; }}
QCalendarWidget QToolButton::menu-indicator {{ image: none; width: 0; }}
QCalendarWidget QMenu {{ background: {c.surface}; border: {s.hairline}px solid {c.outline}; }}
QCalendarWidget QSpinBox {{
    min-height: {s.button_compact - 2 * s.hairline}px;
    max-height: {s.button_compact - 2 * s.hairline}px;
    padding: 0 {sp.s}px;
}}
QCalendarWidget QAbstractItemView {{
    background: {c.surface};
    color: {c.text};
    selection-background-color: {c.primary};
    selection-color: {c.on_primary};
    outline: 0;
    border: none;
}}
QCalendarWidget QAbstractItemView:disabled {{ color: {c.text_3}; }}
"""
