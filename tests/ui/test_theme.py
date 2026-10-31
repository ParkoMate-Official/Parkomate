"""WCAG contrast verification for the olive + yellow design system."""

from __future__ import annotations

import pytest

from parkomate.ui.theme.tokens import COLORS, contrast_ratio


class TestTokenContrast:
    """All token pairs that must meet WCAG contrast minimums."""

    # --- Primary text on surfaces (AAA: 7:1) ---
    @pytest.mark.parametrize(
        "fg,bg,minimum",
        [
            (COLORS.text, COLORS.bg, 7.0),
            (COLORS.text, COLORS.surface, 7.0),
            (COLORS.text, COLORS.surface_tint, 7.0),
        ],
    )
    def test_text_on_surfaces(self, fg: str, bg: str, minimum: float) -> None:
        assert contrast_ratio(fg, bg) >= minimum

    # --- Muted text on surfaces (AA: 4.5:1) ---
    @pytest.mark.parametrize(
        "fg,bg,minimum",
        [
            (COLORS.text_muted, COLORS.surface, 4.5),
            (COLORS.text_muted, COLORS.surface_tint, 4.5),
        ],
    )
    def test_text_muted_on_surfaces(self, fg: str, bg: str, minimum: float) -> None:
        assert contrast_ratio(fg, bg) >= minimum

    # --- White on accent (AA: 4.5:1 for large text) ---
    def test_white_on_accent(self) -> None:
        assert contrast_ratio("#FFFFFF", COLORS.accent) >= 4.5

    # --- Status foreground on status backgrounds (AAA: 7:1) ---
    @pytest.mark.parametrize(
        "fg,bg,minimum",
        [
            (COLORS.pass_fg, COLORS.pass_bg, 7.0),
            (COLORS.fail_fg, COLORS.fail_bg, 7.0),
            (COLORS.warn_fg, COLORS.warn_bg, 7.0),
            (COLORS.info_fg, COLORS.info_bg, 7.0),
        ],
    )
    def test_status_fg_on_status_bg(self, fg: str, bg: str, minimum: float) -> None:
        assert contrast_ratio(fg, bg) >= minimum

    # --- Status foreground on surface (AAA: 7:1 for badges) ---
    @pytest.mark.parametrize(
        "fg,bg,minimum",
        [
            (COLORS.pass_fg, COLORS.surface, 7.0),
            (COLORS.fail_fg, COLORS.surface, 7.0),
        ],
    )
    def test_status_fg_on_surface(self, fg: str, bg: str, minimum: float) -> None:
        assert contrast_ratio(fg, bg) >= minimum

    # --- On-status-solid on solid status backgrounds (AAA: 7:1) ---
    @pytest.mark.parametrize(
        "fg,bg,minimum",
        [
            (COLORS.on_status_solid, COLORS.pass_solid, 7.0),
            (COLORS.on_status_solid, COLORS.fail_solid, 7.0),
        ],
    )
    def test_on_status_solid_on_solid(self, fg: str, bg: str, minimum: float) -> None:
        assert contrast_ratio(fg, bg) >= minimum

    # --- Focus ring against all surfaces (non-text: 3:1) ---
    @pytest.mark.parametrize(
        "fg,bg,minimum",
        [
            (COLORS.focus, COLORS.surface, 3.0),
            (COLORS.focus, COLORS.bg, 3.0),
            (COLORS.focus, COLORS.surface_tint, 3.0),
            (COLORS.focus, COLORS.surface_alt, 3.0),
            (COLORS.focus, COLORS.pass_bg, 3.0),
            (COLORS.focus, COLORS.fail_bg, 3.0),
            (COLORS.focus, COLORS.warn_bg, 3.0),
            (COLORS.focus, COLORS.info_bg, 3.0),
        ],
    )
    def test_focus_ring_on_surfaces(self, fg: str, bg: str, minimum: float) -> None:
        assert contrast_ratio(fg, bg) >= minimum

    # --- Disabled text on disabled background (AA: 4.5:1) ---
    def test_disabled_contrast(self) -> None:
        assert contrast_ratio(COLORS.disabled_fg, COLORS.disabled_bg) >= 4.5

    # --- Tooltip text on tooltip background (AA: 4.5:1) ---
    def test_tooltip_contrast(self) -> None:
        assert contrast_ratio(COLORS.tooltip_fg, COLORS.tooltip_bg) >= 4.5


class TestTokenInvariants:
    """Design invariants that must never be violated."""

    def test_accent_deco_never_used_for_text(self) -> None:
        """accent_deco is a decorative yellow; white text on it fails AA."""
        # White on accent_deco should fail AA (4.5:1) - it's too light
        assert contrast_ratio("#FFFFFF", COLORS.accent_deco) < 4.5

    def test_status_colors_reserved(self) -> None:
        """Green/red/amber/blue only appear in status tokens, not in brand tokens.
        Exception: yellow_dark == warn_fg is intentional (shared warning text color)."""
        brand_tokens = [
            COLORS.accent,
            COLORS.accent_hover,
            COLORS.accent_pressed,
            COLORS.accent_soft,
            COLORS.accent_brand,
            COLORS.accent_deco,
            COLORS.yellow_soft,
            # yellow_dark is intentionally same as warn_fg for warning text
        ]
        status_green = COLORS.pass_fg
        status_red = COLORS.fail_fg
        status_amber = COLORS.warn_fg
        status_blue = COLORS.info_fg

        for token in brand_tokens:
            assert token != status_green
            assert token != status_red
            assert token != status_amber
            assert token != status_blue

    def test_accent_not_a_status_color(self) -> None:
        """Primary accent is olive, not green/red/amber/blue."""
        assert COLORS.accent != COLORS.pass_fg
        assert COLORS.accent != COLORS.fail_fg
        assert COLORS.accent != COLORS.warn_fg
        assert COLORS.accent != COLORS.info_fg

    def test_reject_takeover_red_preserved(self) -> None:
        """fail_solid (reject takeover background) must remain #991B1B."""
        assert COLORS.fail_solid == "#991B1B"

    def test_toast_green_preserved(self) -> None:
        """pass_solid (success toast background) must remain #0B5D35."""
        assert COLORS.pass_solid == "#0B5D35"
