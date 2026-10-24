"""Design tokens - the single source of truth for every colour, type style, size, radius,
spacing, elevation and motion value of the UI.

Material 3 / One UI inspired, light theme (factory floors are bright), one accent colour.

Rules (docs/design/DESIGN_SYSTEM.md):
* nothing outside ``ui/theme`` hard-codes a colour or a pixel size
  (``tests/ui/test_design_system.py`` scans for it);
* green / red / amber are reserved for status and never used decoratively;
* status is never shown by colour alone (icon + word + colour);
* every text/background pair meets WCAG AA (checked by the same test);
* line heights are identical in English and Marathi, so switching language never moves the
  layout (they are the spec values, raised where Noto Sans Devanagari needs the room).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Colors:
    # ---- neutrals (warm olive/sage brand-aligned from parkomate.com dashboard)
    bg: str = "#DEE7D4"  # page background (brand sage green)
    surface: str = "#FFFFFF"  # cards
    surface_2: str = "#EFF2EA"  # inset areas, table header, input fill
    surface_3: str = "#E4E8DE"  # hover on surface_2, disabled fill
    outline: str = "#CCD4C4"  # card / input borders (1 px)
    outline_soft: str = "#D8E0D0"  # dividers
    outline_strong: str = "#66725B"  # unselected controls (>= 3:1 on surface and surface_2)
    text: str = "#181C13"  # primary text
    text_2: str = "#4A5241"  # secondary text
    text_3: str = "#545D4C"  # captions, placeholders
    # ---- accent (Parkomate Olive Green from brand dashboard)
    primary: str = "#4C6B1D"
    primary_hov: str = "#3F5917"
    primary_pressed: str = "#334712"
    primary_cont: str = "#E6ECE0"  # tonal buttons, active card surface, badge container
    primary_cont_hov: str = "#DCE3D4"
    on_primary: str = "#FFFFFF"
    on_primary_cont: str = "#2B3C0F"
    # ---- status (never decorative). "<x>" = icons, bars and fills; "on_<x>_cont" = text on
    # the <x>_cont container and on white, and the fill behind white text.
    success: str = "#1E8E4E"
    success_cont: str = "#E3F4EA"
    on_success_cont: str = "#146B3A"
    success_hov: str = "#0F5A30"
    danger: str = "#C62828"
    danger_cont: str = "#FCE8E8"
    on_danger_cont: str = "#A61B1B"
    danger_hov: str = "#A82020"
    warning: str = "#B26A00"
    warning_cont: str = "#FFF2DA"
    on_warning_cont: str = "#8A5300"
    info: str = "#286A7B"
    info_cont: str = "#E2F0F4"
    on_info_cont: str = "#1B4E5B"
    on_status: str = "#FFFFFF"  # text and icons on filled status colours
    takeover: str = "#B3261E"  # reject takeover background
    takeover_glow: str = "#C93A2F"  # its soft lighter centre
    # ---- data viz: rejects by stage A-D (a red ramp: they are all rejects)
    reject_a: str = "#8E1B16"
    reject_b: str = "#C62828"
    reject_c: str = "#E8746A"
    reject_d: str = "#F5B8B0"
    # ---- misc
    camera_bg: str = "#0B0F17"
    camera_line: str = "#8DC48D"  # scan line on the camera preview
    shadow: str = "#000000"
    scrim: str = "#181C13"
    # ---- hero / showcase panel (Parkomate brand dashboard)
    hero_bg_start: str = "#243214"
    hero_bg_mid: str = "#435922"
    hero_bg_end: str = "#5E7930"
    hero_card_bg: str = "#4F6827"
    hero_card_border: str = "#7A9848"
    hero_gold: str = "#C5D49A"

    def status(self, tone: str) -> tuple[str, str, str]:
        """(graphic, container, text-on-container) for a tone name."""
        return {
            "success": (self.success, self.success_cont, self.on_success_cont),
            "danger": (self.danger, self.danger_cont, self.on_danger_cont),
            "warning": (self.warning, self.warning_cont, self.on_warning_cont),
            "info": (self.info, self.info_cont, self.on_info_cont),
            "neutral": (self.text_3, self.surface_2, self.text_2),
        }.get(tone, (self.text_3, self.surface_2, self.text_2))


@dataclass(frozen=True, slots=True)
class Alpha:
    focus_halo: float = 0.40  # 3 px halo around the 1 px focus border
    hover: float = 0.08  # state layer
    pressed: float = 0.12
    disabled: float = 0.40  # whole-control opacity (toggles)
    keycap: float = 0.70
    shadow: float = 0.10
    scrim: float = 0.32
    glow: float = 0.55
    flash: float = 0.45  # camera success flash
    track: float = 0.16  # progress / ring tracks


@dataclass(frozen=True, slots=True)
class TypeStyle:
    size: int
    weight: int
    line: int  # fixed line box, identical for every language
    tracking: float = 0.0  # letter spacing (px)
    mono: bool = False


@dataclass(frozen=True, slots=True)
class Typography:
    # name            size / weight / line-height        use
    display: TypeStyle = TypeStyle(40, 700, 60)  # reject title, hero result
    headline: TypeStyle = TypeStyle(28, 600, 42)  # screen titles, KPI values
    title: TypeStyle = TypeStyle(20, 600, 30)  # card titles
    body_lg: TypeStyle = TypeStyle(18, 400, 26)  # main body, checklist items
    body: TypeStyle = TypeStyle(16, 400, 24)  # secondary body, table cells
    label: TypeStyle = TypeStyle(14, 500, 22, 0.1)  # field labels, chips, tabs
    caption: TypeStyle = TypeStyle(13, 400, 20)  # hints, timestamps, footers
    value_xl: TypeStyle = TypeStyle(32, 600, 44, mono=True)  # measured values, device ID
    # derived styles (same scale, other weight / family)
    button: TypeStyle = TypeStyle(18, 600, 26)
    button_sm: TypeStyle = TypeStyle(16, 600, 24)
    body_strong: TypeStyle = TypeStyle(16, 600, 24)
    body_lg_strong: TypeStyle = TypeStyle(18, 600, 26)
    mono: TypeStyle = TypeStyle(16, 400, 24, mono=True)
    mono_label: TypeStyle = TypeStyle(14, 500, 22, mono=True)
    mono_title: TypeStyle = TypeStyle(20, 600, 30, mono=True)
    keycap: TypeStyle = TypeStyle(12, 600, 16)
    box_letter: TypeStyle = TypeStyle(120, 700, 150)  # reject box letter tile

    def style(self, name: str) -> TypeStyle:
        value = getattr(self, name, None)
        return value if isinstance(value, TypeStyle) else self.body


@dataclass(frozen=True, slots=True)
class Spacing:
    """The 4/8 grid. Nothing else is used for gaps, margins and padding."""

    xs: int = 4
    s: int = 8
    m: int = 12
    l: int = 16  # noqa: E741 - the scale reads xs/s/m/l/xl
    xl: int = 24
    xxl: int = 32
    xxxl: int = 48


@dataclass(frozen=True, slots=True)
class Radius:
    keycap: int = 4
    chip: int = 8
    control: int = 12  # inputs, buttons
    card: int = 16  # cards, camera preview
    hero: int = 24  # hero result, takeover tiles
    pill: int = 999  # segmented controls, avatars


@dataclass(frozen=True, slots=True)
class Sizes:
    # window / shell
    min_window_width: int = 1366
    min_window_height: int = 768
    app_bar: int = 72
    sim_band: int = 4
    context_bar: int = 48
    action_bar: int = 88
    page_margin: int = 24
    page_margin_wide: int = 32
    wide_breakpoint: int = 1600  # >= this window width: wider margins, centred content
    content_max: int = 1600
    grid_columns: int = 12
    left_columns: int = 5
    drawer: int = 460
    # buttons and controls
    button: int = 56
    button_compact: int = 44
    button_min_width: int = 120
    primary_action: int = 320  # THE primary button of a screen is never narrower
    button_pad: int = 24
    button_pad_compact: int = 16
    icon_gap: int = 8
    keycap: int = 22
    keycap_pad: int = 6
    input: int = 52
    input_pad: int = 16
    number_field: int = 160
    text_field_max: int = 480
    select_max: int = 520
    checkbox: int = 32
    stage_checkbox_width: int = 120
    list_row: int = 64
    table_row: int = 48
    tab: int = 48
    tab_indicator: int = 3
    chip: int = 32
    chip_compact: int = 24
    chip_hero: int = 40
    segmented: int = 44
    switch_w: int = 52
    switch_h: int = 32
    avatar: int = 40
    mark: int = 40
    mark_large: int = 56
    # icons
    icon_s: int = 16
    icon: int = 20
    icon_m: int = 24
    icon_l: int = 32
    icon_xl: int = 48
    icon_hero: int = 72
    # components
    stepper_dot: int = 32
    stepper_line: int = 2
    stepper_segment: int = 14  # connector length between two stage labels
    step_dot: int = 28
    progress_bar: int = 8
    ring: int = 168
    ring_stroke: int = 12
    spinner: int = 20
    spinner_stroke: int = 3
    range_bar: int = 8
    range_marker: int = 18
    range_bar_width: int = 180
    reading_slot: int = 88
    kpi: int = 120
    stacked_bar: int = 16
    camera_min_height: int = 160
    camera_corner: int = 28
    camera_stroke: int = 4
    toast: int = 96
    toast_countdown: int = 4
    focus_ring: int = 3
    focus_border: int = 1
    hairline: int = 1
    active_outline: int = 2
    attempt_dot: int = 12
    edited_dot: int = 8
    section_index: int = 240
    settings_two_column: int = 1600  # settings form uses two columns from this width
    empty_state: int = 360
    takeover_tile: int = 220
    popup_offset: int = 4
    popup_max_height: int = 420
    shadow_margin: int = 24  # room around a floating card for its shadow


@dataclass(frozen=True, slots=True)
class Elevation:
    """Only floating things (menus, toasts, popups, drawer) get a shadow."""

    blur: int = 24
    offset_y: int = 8


@dataclass(frozen=True, slots=True)
class Motion:
    fast: int = 120  # hover / press
    medium: int = 200  # state change
    slow: int = 280  # enter / exit
    scan_period: int = 1600  # camera scan line (one sweep)
    spin_period: int = 1000  # "working" spinner (one turn)
    flash: int = 600  # camera success flash
    pulse: int = 700  # one-time reject pulse
    frame_interval: int = 16  # ~60 fps for looping animations


@dataclass(frozen=True, slots=True)
class Tokens:
    color: Colors = field(default_factory=Colors)
    alpha: Alpha = field(default_factory=Alpha)
    type: Typography = field(default_factory=Typography)
    space: Spacing = field(default_factory=Spacing)
    radius: Radius = field(default_factory=Radius)
    size: Sizes = field(default_factory=Sizes)
    elevation: Elevation = field(default_factory=Elevation)
    motion: Motion = field(default_factory=Motion)


TOKENS = Tokens()
COLORS = TOKENS.color
ALPHA = TOKENS.alpha
TYPE = TOKENS.type
SPACE = TOKENS.space
RADIUS = TOKENS.radius
SIZES = TOKENS.size
ELEVATION = TOKENS.elevation
MOTION = TOKENS.motion


def relative_luminance(hex_color: str) -> float:
    """WCAG 2.x relative luminance of ``#RRGGBB``."""
    value = hex_color.lstrip("#")
    channels = [int(value[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast_ratio(foreground: str, background: str) -> float:
    """WCAG contrast ratio between two ``#RRGGBB`` colours (1..21)."""
    a = relative_luminance(foreground)
    b = relative_luminance(background)
    lighter, darker = max(a, b), min(a, b)
    return (lighter + 0.05) / (darker + 0.05)


def blend(foreground: str, background: str, alpha: float) -> str:
    """``foreground`` at ``alpha`` over an opaque ``background`` -> ``#RRGGBB``."""
    fg = [int(foreground.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4)]
    bg = [int(background.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4)]
    mixed = [round(f * alpha + b * (1 - alpha)) for f, b in zip(fg, bg, strict=True)]
    return "#" + "".join(f"{c:02X}" for c in mixed)


# Text/background pairs the UI actually uses - every one must meet WCAG AA (4.5:1);
# non-text pairs (icons, borders, focus) need 3:1. Checked by tests/ui/test_design_system.py.
TEXT_PAIRS: tuple[tuple[str, str], ...] = (
    ("text", "bg"),
    ("text", "surface"),
    ("text", "surface_2"),
    ("text", "primary_cont"),
    ("text_2", "surface"),
    ("text_2", "bg"),
    ("text_2", "surface_2"),
    ("text_3", "surface"),
    ("text_3", "bg"),
    ("text_3", "surface_2"),
    ("primary", "surface"),
    ("primary", "bg"),
    ("on_primary", "primary"),
    ("on_primary", "primary_hov"),
    ("on_primary_cont", "primary_cont"),
    ("on_success_cont", "success_cont"),
    ("on_success_cont", "surface"),
    ("on_danger_cont", "danger_cont"),
    ("on_danger_cont", "surface"),
    ("on_warning_cont", "warning_cont"),
    ("on_warning_cont", "surface"),
    ("on_info_cont", "info_cont"),
    ("on_status", "on_success_cont"),
    ("on_status", "danger"),
    ("on_status", "takeover"),
    ("on_status", "takeover_glow"),
    ("danger", "surface"),
    ("danger", "danger_cont"),
    ("surface", "text"),  # tooltips
)
NON_TEXT_PAIRS: tuple[tuple[str, str], ...] = (
    ("success", "surface"),
    ("warning", "surface"),
    ("danger", "surface"),
    ("primary", "surface"),
    ("outline_strong", "surface"),
    ("outline_strong", "surface_2"),
    ("primary", "bg"),
)
