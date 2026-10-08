"""Static UI rules: no hard-coded user-facing strings, accessible colours, bundled fonts."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from parkomate.ui.theme.tokens import COLORS, NON_TEXT_PAIRS, TEXT_PAIRS, contrast_ratio

UI_DIR = Path(__file__).resolve().parents[2] / "src" / "parkomate" / "ui"

TEXT_SETTERS = {
    "setText",
    "setPlaceholderText",
    "setToolTip",
    "setWindowTitle",
    "setTitle",
    "addItem",
    "addItems",
    "addTab",
    "setTabText",
    "setAccessibleName",
    "setAccessibleDescription",
    "setStatusTip",
    "setWhatsThis",
    "setHorizontalHeaderLabels",
    "setPlainText",
    "drawText",
    "show_text",
    "showMessage",
}
TEXT_WIDGETS = {
    "QLabel",
    "QPushButton",
    "QCheckBox",
    "QRadioButton",
    "QGroupBox",
    "QAction",
    "QListWidgetItem",
    "QTableWidgetItem",
}
# Files that only *produce* screenshots / debug output, never station UI text.
EXEMPT = {"screenshots.py"}


def _has_letters(text: str) -> bool:
    return any(ch.isalpha() for ch in text)


def _calls_with_literals(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    problems: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
        if name not in TEXT_SETTERS and name not in TEXT_WIDGETS:
            continue
        for arg in node.args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                if _has_letters(arg.value):
                    problems.append(f"{path.name}:{node.lineno} {name}({arg.value!r})")
            elif isinstance(arg, ast.JoinedStr):
                literal = "".join(
                    str(part.value) for part in arg.values if isinstance(part, ast.Constant)
                )
                if _has_letters(literal):
                    problems.append(f"{path.name}:{node.lineno} {name}(f-string {literal!r})")
    return problems


def test_no_hard_coded_user_facing_strings() -> None:
    problems: list[str] = []
    files = [p for p in UI_DIR.rglob("*.py") if p.name not in EXEMPT]
    assert len(files) > 10
    for path in files:
        problems.extend(_calls_with_literals(path))
    assert problems == [], "\n".join(problems)


def test_scanner_catches_literals(tmp_path: Path) -> None:
    sample = tmp_path / "sample.py"
    sample.write_text(
        "label.setText('Upload firmware')\n"
        "button = QPushButton('Start')\n"
        "x.setToolTip(f'Port {name} busy')\n"
        "ok.setText(t('action.login'))\n"
        "arrow = QLabel('›')\n",
        encoding="utf-8",
    )
    problems = _calls_with_literals(sample)
    assert len(problems) == 3


@pytest.mark.parametrize(("foreground", "background"), TEXT_PAIRS)
def test_text_contrast_aa(foreground: str, background: str) -> None:
    """Every text/background pair the UI uses meets WCAG AA (4.5:1)."""
    ratio = contrast_ratio(getattr(COLORS, foreground), getattr(COLORS, background))
    assert ratio >= 4.5, f"{foreground} on {background}: {ratio:.2f}"


@pytest.mark.parametrize(("foreground", "background"), NON_TEXT_PAIRS)
def test_non_text_contrast(foreground: str, background: str) -> None:
    """Icons, borders of controls and the focus border: >= 3:1."""
    ratio = contrast_ratio(getattr(COLORS, foreground), getattr(COLORS, background))
    assert ratio >= 3.0, f"{foreground} on {background}: {ratio:.2f}"


def test_contrast_formula() -> None:
    assert round(contrast_ratio("#000000", "#FFFFFF"), 1) == 21.0
    assert contrast_ratio("#777777", "#777777") == 1.0


def test_fonts_bundled() -> None:
    folder = UI_DIR / "assets" / "fonts"
    from parkomate.ui.theme.fonts import FONT_FILES

    for name in (*FONT_FILES, "OFL.txt"):
        assert (folder / name).is_file(), name
