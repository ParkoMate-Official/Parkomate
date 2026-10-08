"""Design-system rules (docs/design/DESIGN_SYSTEM.md):

* no colour and no pixel size is hard-coded outside ``ui/theme`` (tokens are the only source);
* every icon and every i18n key the UI uses exists;
* the gallery shows every component.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from parkomate.i18n import load_catalogue
from parkomate.ui.components.icons import icon_names

UI_DIR = Path(__file__).resolve().parents[2] / "src" / "parkomate" / "ui"
THEME_DIR = UI_DIR / "theme"
HEX = re.compile(r"#[0-9A-Fa-f]{6}\b|#[0-9A-Fa-f]{3}\b")
PX = re.compile(r"\d+\s*px\b")
# Calls that take sizes; any integer literal other than 0 must come from the tokens.
SIZE_CALLS = {
    "setContentsMargins",
    "setSpacing",
    "setHorizontalSpacing",
    "setVerticalSpacing",
    "addSpacing",
    "setFixedWidth",
    "setFixedHeight",
    "setFixedSize",
    "setMinimumWidth",
    "setMinimumHeight",
    "setMinimumSize",
    "setMaximumWidth",
    "setMaximumHeight",
    "setMaximumSize",
    "setColumnMinimumWidth",
    "setDefaultSectionSize",
    "setMinimumSectionSize",
    "setIconSize",
    "setBlurRadius",
}


def _ui_files() -> list[Path]:
    return [p for p in UI_DIR.rglob("*.py") if THEME_DIR not in p.parents]


def _strings(tree: ast.AST) -> list[tuple[int, str]]:
    """String literals, without the fragments of f-strings."""
    fragments = {
        id(part)
        for node in ast.walk(tree)
        if isinstance(node, ast.JoinedStr)
        for part in node.values
    }
    found = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in fragments
        ):
            found.append((node.lineno, node.value))
    return found


def _setting_keys() -> set[str]:
    from pydantic import BaseModel

    from parkomate.config.settings import Settings

    keys = set(Settings.model_fields)
    for section, info in Settings.model_fields.items():
        model = info.annotation
        if isinstance(model, type) and issubclass(model, BaseModel):
            keys.update(f"{section}.{name}" for name in model.model_fields)
    return keys


def _docstring_lines(tree: ast.AST) -> set[int]:
    lines: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                lines.add(body[0].lineno)
    return lines


def test_no_hard_coded_colours_or_px_outside_theme() -> None:
    problems = []
    for path in _ui_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        docs = _docstring_lines(tree)
        for line, text in _strings(tree):
            if line in docs:
                continue
            if HEX.search(text):
                problems.append(f"{path.name}:{line} colour {text!r}")
            if PX.search(text):
                problems.append(f"{path.name}:{line} px {text!r}")
    assert problems == [], "\n".join(problems)


def test_no_literal_sizes_in_layout_calls() -> None:
    problems = []
    for path in _ui_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr not in SIZE_CALLS:
                continue
            for arg in node.args:
                literal = isinstance(arg, ast.Constant) and isinstance(arg.value, int | float)
                if literal and not isinstance(arg.value, bool) and arg.value != 0:
                    problems.append(f"{path.name}:{node.lineno} {node.func.attr}({arg.value})")
    assert problems == [], "\n".join(problems)


def test_scanners_catch_literals(tmp_path: Path) -> None:
    sample = (
        "x.setStyleSheet('color: #FF0000')\nlayout.setSpacing(12)\nw.setFixedWidth(SIZES.icon)\n"
    )
    tree = ast.parse(sample)
    assert any(HEX.search(text) for _line, text in _strings(tree))
    calls = [
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr in SIZE_CALLS
        and any(isinstance(a, ast.Constant) and a.value for a in n.args)
    ]
    assert len(calls) == 1


ICON_ARG_CALLS = {
    "Icon",
    "IconBadge",
    "paint_icon",
    "set_icon",
    "qicon",
    "icon_pixmap",
    "IconButton",
}


def test_every_icon_exists() -> None:
    available = set(icon_names())
    missing = []
    for path in _ui_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = (
                node.func.attr
                if isinstance(node.func, ast.Attribute)
                else getattr(node.func, "id", "")
            )
            candidates: list[ast.expr] = []
            if name in ICON_ARG_CALLS and node.args:
                candidates.append(
                    node.args[1] if name == "paint_icon" and len(node.args) > 1 else node.args[0]
                )
            candidates += [k.value for k in node.keywords if k.arg == "icon"]
            for arg in candidates:
                literal = isinstance(arg, ast.Constant) and isinstance(arg.value, str)
                if literal and arg.value not in available:  # type: ignore[attr-defined]
                    missing.append(f"{path.name}:{node.lineno} {arg.value}")  # type: ignore[attr-defined]
    assert missing == [], "\n".join(missing)


KEY = re.compile(r"[a-z][a-z_0-9]*(\.[A-Za-z0-9_]+)+")


def test_every_i18n_key_used_by_the_ui_exists() -> None:
    en, mr = load_catalogue("en"), load_catalogue("mr")
    prefixes = {key.split(".")[0] for key in en}
    settings = _setting_keys()
    missing = []
    for path in _ui_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        docs = _docstring_lines(tree)
        for line, text in _strings(tree):
            if line in docs or not KEY.fullmatch(text) or text.split(".")[0] not in prefixes:
                continue
            if text.endswith((".py", ".svg", ".ttf", ".png")) or text.startswith("parkomate."):
                continue
            if text in settings:
                continue  # a settings key, not a translation
            if text not in en or text not in mr:
                missing.append(f"{path.name}:{line} {text}")
    assert missing == [], "\n".join(missing)


def test_gallery_shows_every_component(qapp: object) -> None:
    from parkomate.ui import gallery

    source = Path(gallery.__file__).read_text(encoding="utf-8")
    for component in (
        "AppButton",
        "IconButton",
        "StatusChip",
        "KeyCap",
        "SimulationChip",
        "CounterChips",
        "SegmentedControl",
        "LanguageSwitch",
        "PassFailToggle",
        "Stepper",
        "StepList",
        "Card",
        "Banner",
        "EmptyState",
        "KpiTile",
        "StackedBar",
        "InlineMessage",
        "InlineConfirm",
        "ErrorBanner",
        "TextField",
        "PasswordField",
        "DecimalField",
        "IntField",
        "Select",
        "Switch",
        "DateRangePicker",
        "FormField",
        "ChecklistRow",
        "ValueRow",
        "ReadingSlots",
        "ProgressBar",
        "ProgressRing",
        "Spinner",
        "DataTable",
        "Tabs",
        "ContextBar",
        "AccountButton",
        "ProductMark",
        "SimulationBand",
        "CameraFrame",
        "Toast",
        "RejectTakeover",
        "MenuItem",
    ):
        assert re.search(rf"\b{component}\(", source), component
    widget = gallery.Gallery()
    assert widget.body.layout() is not None
    widget.deleteLater()
