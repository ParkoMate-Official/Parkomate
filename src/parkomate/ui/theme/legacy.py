"""TEMPORARY: the pre-redesign token names, mapped onto the new tokens, so the old screens
keep working while they are rebuilt one by one. Deleted when the last old screen is gone."""

from __future__ import annotations

from types import SimpleNamespace

from PySide6.QtGui import QFont

from parkomate.ui.theme.fonts import font_for
from parkomate.ui.theme.tokens import COLORS as C
from parkomate.ui.theme.tokens import RADIUS, SPACE, TYPE, TypeStyle
from parkomate.ui.theme.tokens import SIZES as S

COLORS = SimpleNamespace(
    bg=C.bg, surface=C.surface, surface_alt=C.surface_2, border=C.outline,
    border_strong=C.outline_strong, text=C.text, text_muted=C.text_2, accent=C.primary,
    accent_hover=C.primary_hov, accent_pressed=C.primary_pressed, accent_soft=C.primary_cont,
    on_accent=C.on_primary, focus=C.primary, pass_bg=C.success_cont, pass_fg=C.on_success_cont,
    pass_solid=C.on_success_cont, fail_bg=C.danger_cont, fail_fg=C.on_danger_cont,
    fail_solid=C.danger, warn_bg=C.warning_cont, warn_fg=C.on_warning_cont,
    info_bg=C.info_cont, info_fg=C.on_info_cont, on_status_solid=C.on_status,
    disabled_bg=C.surface_3, disabled_fg=C.text_3,
)
SIZES = SimpleNamespace(
    font_base=TYPE.body_lg.size, font_small=TYPE.caption.size, font_h2=TYPE.title.size,
    font_h1=TYPE.headline.size, font_value=TYPE.value_xl.size, font_value_large=TYPE.display.size,
    font_takeover=TYPE.display.size, font_box_letter=TYPE.box_letter.size,
    button_height=S.button, check_row_height=S.list_row, radius=RADIUS.control,
    space_xs=SPACE.xs, space_s=SPACE.s, space_m=SPACE.l, space_l=SPACE.xl, space_xl=SPACE.xxl,
    focus_width=S.focus_ring, min_window_width=S.min_window_width,
    min_window_height=S.min_window_height,
)


def font(px: int, *, bold: bool = False) -> QFont:
    return font_for(TypeStyle(px, 700 if bold else 400, px + px // 2))
