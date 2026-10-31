"""Stylesheet validation: builds QSS from tokens and asserts no unresolved placeholders."""

from __future__ import annotations

import re

from parkomate.ui.theme.qss import build_stylesheet
from parkomate.ui.theme.tokens import COLORS, SIZES


def test_build_stylesheet_no_unresolved_placeholders() -> None:
    """Stylesheet built from tokens must contain zero unresolved {c.xxx} or {s.xxx} placeholders."""
    css = build_stylesheet(COLORS, SIZES)
    unresolved = re.findall(r"\{[cs]\.[a-z_]+\}", css)
    assert unresolved == [], f"Unresolved token placeholders: {unresolved}"


def test_build_stylesheet_non_empty() -> None:
    """Stylesheet must not be empty."""
    css = build_stylesheet(COLORS, SIZES)
    assert len(css) > 1000


def test_build_stylesheet_contains_key_selectors() -> None:
    """Stylesheet must contain expected key selectors for the design system."""
    css = build_stylesheet(COLORS, SIZES)

    # Core surfaces
    assert "QMainWindow" in css
    assert "QWidget#Root" in css
    assert "QWidget#Page" in css

    # Card rules
    assert 'QFrame[card="true"]' in css
    assert 'QFrame[card="true"][tone="pass"]' in css
    assert 'QFrame[card="true"][tone="fail"]' in css
    assert 'QFrame[nested_panel="true"]' in css

    # Button variants
    assert 'QPushButton[variant="primary"]' in css
    assert 'QPushButton[variant="secondary"]' in css
    assert 'QPushButton[variant="danger_outline"]' in css
    assert 'QPushButton[variant="pass"]' in css
    assert 'QPushButton[variant="link"]' in css
    assert 'QPushButton[variant="toggle"]' in css
    assert 'QPushButton[variant="takeover"]' in css

    # Input focus
    assert "QLineEdit:focus" in css
    assert "outline-offset" in css

    # Stepper
    assert 'QLabel[step="current"]' in css
    assert 'QLabel[step="done"]' in css
    assert 'QLabel[step="todo"]' in css
    assert 'QLabel[step="rejected"]' in css

    # Tracked labels
    assert 'QLabel[tracked="true"]' in css
    assert "text-transform: uppercase" in css
    assert "letter-spacing" in css

    # Box letter (reject takeover)
    assert 'QLabel[box_letter="true"]' in css
    assert "font-size: 160px" in css

    # Status tones
    assert 'QFrame[tone="pass"]' in css
    assert 'QFrame[tone="fail"]' in css
    assert 'QFrame[tone="warn"]' in css
    assert 'QFrame[tone="info"]' in css
    assert 'QFrame[tone="pending"]' in css

    # Progress bar chunk (yellow)
    assert "QProgressBar::chunk" in css
    assert COLORS.accent_deco in css

    # Focus rings (double ring via outline)
    assert "outline-offset" in css
    assert f"{SIZES.focus_width}px solid {COLORS.focus}" in css

    # Tooltips
    assert "QToolTip" in css
    assert COLORS.tooltip_bg in css
    assert COLORS.tooltip_fg in css


def test_box_letter_rule_exists() -> None:
    """box_letter dynamic property rule must exist for RejectTakeover box letter."""
    css = build_stylesheet(COLORS, SIZES)

    # Check box_letter selector
    assert 'QLabel[box_letter="true"]' in css

    # Check its key properties
    assert f"border: 6px solid {COLORS.on_status_solid}" in css
    assert f"color: {COLORS.on_status_solid}" in css
    assert f"font-size: {SIZES.font_box_letter}px" in css
    assert "font-weight: 700" in css
    assert "border-radius: 24px" in css


def test_nested_panel_rule_exists() -> None:
    """nested_panel dynamic property rule must exist for tinted metric panels."""
    css = build_stylesheet(COLORS, SIZES)

    assert 'QFrame[nested_panel="true"]' in css
    assert f"background: {COLORS.surface_tint}" in css
    assert f"border: 1px solid {COLORS.border}" in css
    assert f"border-radius: {SIZES.tint_radius}px" in css


def test_tone_border_card_rules() -> None:
    """Accent-bordered step cards with 2px four-sided tone borders."""
    css = build_stylesheet(COLORS, SIZES)

    # Pass tone card - 2px border
    assert f"border: 2px solid {COLORS.pass_fg}" in css
    # Fail tone card - 2px border
    assert f"border: 2px solid {COLORS.fail_fg}" in css
    # Info tone card - 2px border
    assert f"border: 2px solid {COLORS.info_fg}" in css
    # Pending tone card - 1px border (default)
    assert f"border: 1px solid {COLORS.border}" in css

    # All should use radius (not card_radius)
    assert f"border-radius: {SIZES.radius}px" in css


def test_progress_bar_yellow_chunks() -> None:
    """Progress bar chunks must use yellow accent_deco."""
    css = build_stylesheet(COLORS, SIZES)

    assert "QProgressBar::chunk" in css
    assert f"background: {COLORS.accent_deco}" in css
    assert f"border-radius: {SIZES.progress_chunk_radius}px" in css
