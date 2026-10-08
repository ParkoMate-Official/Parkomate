"""Bundled fonts and the type scale as QFonts.

Noto Sans (Latin), Noto Sans Devanagari (Marathi), Noto Sans Mono (MAC addresses, IDs,
error codes), Noto Sans Symbols 2 (fallback for stray symbols). Regular / Medium / SemiBold /
Bold so the type scale's 400 / 500 / 600 / 700 weights are real faces, not synthesised.
All SIL Open Font License (``assets/fonts/OFL.txt``).

Every type style has ONE fixed line box (``tokens.TYPE``) that fits both scripts, and a fixed
baseline inside it, so a line is exactly as tall in English as in Marathi and switching
language never moves the layout.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources

from PySide6.QtGui import QFont, QFontDatabase, QFontMetricsF

from parkomate.ui.theme.tokens import TYPE, TypeStyle

log = logging.getLogger(__name__)

FONT_FILES = (
    "NotoSans-Regular.ttf",
    "NotoSans-Medium.ttf",
    "NotoSans-SemiBold.ttf",
    "NotoSans-Bold.ttf",
    "NotoSansDevanagari-Regular.ttf",
    "NotoSansDevanagari-Medium.ttf",
    "NotoSansDevanagari-SemiBold.ttf",
    "NotoSansDevanagari-Bold.ttf",
    "NotoSansMono-Regular.ttf",
    "NotoSansMono-SemiBold.ttf",
    "NotoSansSymbols2-Regular.ttf",
)
LATIN = "Noto Sans"
DEVANAGARI = "Noto Sans Devanagari"
MONO = "Noto Sans Mono"
SYMBOLS = "Noto Sans Symbols 2"
# Qt falls back in this order (per glyph).
FAMILIES = [LATIN, DEVANAGARI, SYMBOLS]
MONO_FAMILIES = [MONO, DEVANAGARI, LATIN, SYMBOLS]

_loaded: list[str] = []


def load_fonts() -> list[str]:
    """Register the bundled fonts with Qt (idempotent). Returns the loaded families."""
    if _loaded:
        return list(_loaded)
    folder = resources.files("parkomate.ui.assets").joinpath("fonts")
    for name in FONT_FILES:
        data = folder.joinpath(name).read_bytes()
        font_id = QFontDatabase.addApplicationFontFromData(data)
        if font_id < 0:
            log.warning("could not load bundled font %s", name)
            continue
        for family in QFontDatabase.applicationFontFamilies(font_id):
            if family not in _loaded:
                _loaded.append(family)
    # Qt shapes '·', '°' etc. inside Marathi text with the Devanagari font, which lacks them.
    # Substitutes make Qt fall back per glyph (otherwise they show as empty boxes).
    QFont.insertSubstitutions(DEVANAGARI, [LATIN, SYMBOLS])
    QFont.insertSubstitutions(LATIN, [DEVANAGARI, SYMBOLS])
    QFont.insertSubstitutions(MONO, [LATIN, DEVANAGARI, SYMBOLS])
    _font.cache_clear()
    line_box.cache_clear()
    return list(_loaded)


def font_for(style: TypeStyle) -> QFont:
    """The QFont of a type style: family stack, pixel size, real weight, tabular figures.

    Returns a copy - callers may modify it."""
    return QFont(_font(style))


@lru_cache(maxsize=64)
def _font(style: TypeStyle) -> QFont:
    font = QFont()
    font.setFamilies(MONO_FAMILIES if style.mono else FAMILIES)
    font.setPixelSize(style.size)
    font.setWeight(QFont.Weight(style.weight))
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    if style.tracking:
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, style.tracking)
    font.setFeature(QFont.Tag("tnum"), 1)  # tabular figures: numbers never jiggle
    return font


def font_named(name: str) -> QFont:
    return font_for(TYPE.style(name))


def app_font() -> QFont:
    """Base UI font (body_lg)."""
    return QFont(font_for(TYPE.body_lg))


@dataclass(frozen=True, slots=True)
class LineBox:
    height: int  # the fixed line height (tokens)
    baseline: float  # baseline position from the top of the line box


@lru_cache(maxsize=64)
def line_box(style: TypeStyle) -> LineBox:
    """Fixed line box with one baseline for both scripts.

    The baseline sits where a line mixing Latin and Devanagari would put it (largest ascent
    and descent of the two families), centred in the token line height.
    """
    ascent = descent = 0.0
    families = (MONO, DEVANAGARI) if style.mono else (LATIN, DEVANAGARI)
    for family in families:
        font = QFont(family)
        font.setPixelSize(style.size)
        font.setWeight(QFont.Weight(style.weight))
        metrics = QFontMetricsF(font)
        ascent = max(ascent, metrics.ascent())
        descent = max(descent, metrics.descent())
    height = max(style.line, math.ceil(ascent + descent))
    return LineBox(height, (height - (ascent + descent)) / 2 + ascent)
