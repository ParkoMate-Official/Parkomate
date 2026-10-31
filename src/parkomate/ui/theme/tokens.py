"""Design tokens: every colour, size and spacing the UI uses, in one place.

Rules (see CLAUDE.md):
* light, neutral background; ONE accent colour for actions (olive);
* green / red / amber are reserved for status and never used decoratively;
* status is never shown by colour alone (icon + word + colour);
* text contrast >= WCAG AA everywhere, >= AAA (7:1) for status text
  (checked by ``tests/ui/test_static.py``).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Colors:
    # Core surfaces
    bg: str = "#FBFCFE"  # Window root canvas background
    surface: str = "#FFFFFF"  # Primary card background, active inputs
    surface_alt: str = "#FAFAF8"  # Inactive tab background, table alternate row
    surface_tint: str = "#F1F4E8"  # Nested metric panel background (olive soft)

    # Borders
    border: str = "#DDE3CB"  # Standard card and container border
    border_strong: str = "#667085"  # Control borders

    # Text
    text: str = "#111111"  # Primary headings, huge numbers, input text
    text_muted: str = "#5B6472"  # Subtitles, helper text, inactive steps

    # Brand - Olive + Yellow identity
    accent: str = "#5A6F2D"  # Primary brand accent; active stepper, primary buttons, logo accent
    accent_hover: str = "#4A5C25"  # Button hover state
    accent_pressed: str = "#3B4A1D"  # Button pressed / active state
    accent_soft: str = "#EBEFE3"  # Selected rows, pressed secondary
    accent_brand: str = "#738B3B"  # Gradient start, large decorative only
    accent_deco: str = "#FACB34"  # Progress bar fill, decorative highlights. Never text
    yellow_soft: str = "#FFF1DB"  # Top simulation banner, warning background
    yellow_dark: str = "#6B3A00"  # Simulation banner text, warning header (same as warn_fg)

    # Keyboard focus ring (dark, >= 3:1 against white and bg)
    focus: str = "#111111"

    # Status - pass / fail / warning / info (soft background + strong foreground + solid)
    pass_bg: str = "#F4FBF6"  # Pass step card background tint
    pass_fg: str = "#0B5D35"  # Pass badges, success buttons, pass borders
    pass_solid: str = "#0B5D35"  # Pass solid badge, checked pass button
    fail_bg: str = "#FDE9E7"  # Locked alert background, error banner tint
    fail_fg: str = "#991B1B"  # Reject takeover, fail badges, red outline buttons
    fail_solid: str = "#991B1B"  # Reject takeover background, checked danger button
    warn_bg: str = "#FFF1DB"  # Warning banner background tint
    warn_fg: str = "#6B3A00"  # Warning banner left bar, caution badges (darker for AAA)
    info_bg: str = "#EFF6FF"  # Working step card background tint (lighter for contrast)
    info_fg: str = "#1E40AF"  # Working/uploading badge, active step border (darker for AAA)
    on_status_solid: str = "#FFFFFF"  # Text/icons on solid status backgrounds (pass/fail/toast)

    # Disabled
    disabled_bg: str = "#CBD5E1"  # Disabled button/control background (darker for contrast)
    disabled_fg: str = "#475569"  # Disabled control text

    # Tooltip
    tooltip_bg: str = "#111111"  # Tooltip background
    tooltip_fg: str = "#FFFFFF"  # Tooltip text

    # Glow
    glow: str = "#FEF3D3"  # Top-right radial header glow


@dataclass(frozen=True, slots=True)
class Sizes:
    # Font sizes
    font_base: int = 18  # Default body text, buttons, labels
    font_small: int = 15  # Secondary text, hints, table headers, tooltips
    font_h2: int = 22  # Section headings, button text (primary)
    font_h1: int = 28  # Page titles, major headings
    font_hero: int = 32  # Large value displays (measurements, device IDs)
    font_hero_large: int = 40  # Extra-large values (QR decoded ID)
    font_takeover: int = 56  # Reject takeover headline
    font_box_letter: int = 160  # Reject box letter (A/B/C/D)

    # Button and control heights
    button_height: int = 56  # Primary action button (bench ergonomics)
    button_height_secondary: int = 48  # Secondary inputs/buttons
    input_height: int = 48  # Input fields minimum height
    check_row_height: int = 68  # Checklist row height
    table_row_height: int = 44  # Table row height

    # Radii
    radius: int = 14  # Controls (buttons, inputs, status frames)
    card_radius: int = 24  # Main cards
    tint_radius: int = 20  # Nested tint panels
    progress_chunk_radius: int = 6  # Progress bar chunk
    radius_small: int = 12  # Small nested panels, decision rows
    radius_pill: int = 9999  # StatusPill capsule radius
    radius_input: int = 10  # Input fields

    # Spacing scale
    space_xs: int = 4  # Tight internal gaps (icon→text, checkbox gaps)
    space_s: int = 8  # Standard small gaps (pill padding, button internal)
    space_m: int = 16  # Base unit — card margins, layout spacing, button padding
    space_l: int = 24  # Large gaps (section separation, card padding, 2-col gutter)
    space_xl: int = 32  # Extra-large gaps (page-level section breaks, modal padding)

    # Focus
    focus_width: int = 2  # Focus ring width (outer ring)
    focus_gap: int = 2  # Gap between control and focus ring

    # Window dimensions
    min_window_width: int = 1366
    min_window_height: int = 768

    # Tab dimensions
    tab_height: int = 48
    tab_padding_h: int = 24

    # Tooltip
    tooltip_padding: int = 8

    # Shell elements
    info_strip_min_height: int = 40
    banner_max_height: int = 240
    banner_min_height: int = 56
    button_min_width_secondary: int = 140


COLORS = Colors()
SIZES = Sizes()


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


# Convenience assertions for tests / static analysis
def assert_contrast(foreground: str, background: str, minimum: float, label: str) -> float:
    """Assert contrast >= minimum, returning the computed ratio."""
    ratio = contrast_ratio(foreground, background)
    if ratio < minimum:
        raise AssertionError(f"{label}: contrast {ratio:.2f}:1 < {minimum}:1")
    return ratio
