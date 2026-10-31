"""Component gallery: renders every widget in every state, EN and MR, to PNG.

Run: python -m tests.ui.gallery --out docs/screenshots/gallery
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtWidgets import QApplication, QGridLayout, QHBoxLayout, QVBoxLayout, QWidget

from parkomate.core.enums import Stage
from parkomate.i18n import set_language, t
from parkomate.ui.components.widgets import (
    AccentCard,
    BigButton,
    CounterBadge,
    InlineConfirm,
    LabelCaps,
    LanguageSwitch,
    ProgressBar,
    StageStepper,
    StatusPill,
    StepRow,
    TrLabel,
    ValueRow,
    card,
    tint_panel,
)
from parkomate.ui.main import create_application
from parkomate.ui.theme.tokens import SIZES


class GalleryPage(QWidget):
    """A page showing all widgets in all states."""

    def __init__(self, lang: str) -> None:
        super().__init__()
        self.lang = lang
        set_language(lang)
        self.setObjectName("Page")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SIZES.space_xl, SIZES.space_xl, SIZES.space_xl, SIZES.space_xl)
        layout.setSpacing(SIZES.space_l)

        # Title
        title = TrLabel("app.brand", role="h1")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        subtitle = TrLabel("app.production_station", role="small")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        # BigButtons
        btn_card, btn_layout = card()
        btn_layout.addWidget(TrLabel("gallery.buttons", role="h2"))
        btn_row = QHBoxLayout()
        btn_row.setSpacing(SIZES.space_m)
        for variant in ("primary", "secondary", "danger_outline", "pass", "link", "toggle"):
            btn = BigButton("action.login", variant=variant, hint_key="key.enter")
            btn_row.addWidget(btn)
        btn_layout.addLayout(btn_row)
        layout.addWidget(btn_card)

        # StatusPill
        pill_card, pill_layout = card()
        pill_layout.addWidget(TrLabel("gallery.pills", role="h2"))
        pill_row = QHBoxLayout()
        pill_row.setSpacing(SIZES.space_m)
        for state in ("pass", "fail", "warn", "working", "pending", "info"):
            pill = StatusPill(state=state, size="large")
            pill_row.addWidget(pill)
        pill_layout.addLayout(pill_row)
        layout.addWidget(pill_card)

        # LabelCaps
        caps_card, caps_layout = card()
        caps_layout.addWidget(TrLabel("gallery.tracked_labels", role="h2"))
        caps_row = QHBoxLayout()
        caps_row.setSpacing(SIZES.space_m)
        for key in ("login.operator_id", "login.password", "app.production_station"):
            label = LabelCaps(key, role="small")
            caps_row.addWidget(label)
        caps_layout.addLayout(caps_row)
        layout.addWidget(caps_card)

        # CounterBadge
        counter_card, counter_layout = card()
        counter_layout.addWidget(TrLabel("gallery.counters", role="h2"))
        counter_row = QHBoxLayout()
        counter_row.setSpacing(SIZES.space_m)
        for key in ("counter.uploads_ok", "counter.uploads_fail", "counter.completed"):
            badge = CounterBadge(key)
            badge.set_value("42")
            counter_row.addWidget(badge)
        counter_layout.addLayout(counter_row)
        layout.addWidget(counter_card)

        # StepRow
        step_card, step_layout = card()
        step_layout.addWidget(TrLabel("gallery.step_rows", role="h2"))
        step_row = QHBoxLayout()
        step_row.setSpacing(SIZES.space_m)
        for i, tone in enumerate(("pass", "fail", "info", "pending"), 1):
            row = StepRow(i, "prog.step.connect", tone=tone)
            row.set_status(tone)
            step_row.addWidget(row)
        step_layout.addLayout(step_row)
        layout.addWidget(step_card)

        # AccentCard
        accent_card, accent_layout = card()
        accent_layout.addWidget(TrLabel("gallery.accent_cards", role="h2"))
        accent_row = QHBoxLayout()
        accent_row.setSpacing(SIZES.space_m)
        for tone in ("pass", "fail", "info", "warn"):
            card_widget = AccentCard("prog.steps_title", tone=tone, icon="pcb")
            card_widget.add_widget(TrLabel("gallery.accent_card_content"))
            accent_row.addWidget(card_widget)
        accent_layout.addLayout(accent_row)
        layout.addWidget(accent_card)

        # ProgressBar
        prog_card, prog_layout = card()
        prog_layout.addWidget(TrLabel("gallery.progress_bars", role="h2"))
        prog = ProgressBar()
        prog.setValue(52)
        prog_layout.addWidget(prog)
        prog2 = ProgressBar()
        prog2.setValue(100)
        prog_layout.addWidget(prog2)
        layout.addWidget(prog_card)

        # InlineConfirm
        confirm_card, confirm_layout = card()
        confirm_layout.addWidget(TrLabel("gallery.inline_confirm", role="h2"))
        confirm = InlineConfirm()
        confirm.show_confirm(t("confirm.end_session"), "action.confirm", "action.cancel", True)
        confirm_layout.addWidget(confirm)
        layout.addWidget(confirm_card)

        # LanguageSwitch
        lang_card, lang_layout = card()
        lang_layout.addWidget(TrLabel("gallery.language_switch", role="h2"))
        lang_switch = LanguageSwitch()
        lang_layout.addWidget(lang_switch)
        layout.addWidget(lang_card)

        # ValueRow (in grid)
        grid_card, grid_layout = card()
        grid_layout.addWidget(TrLabel("gallery.value_rows", role="h2"))
        grid = QGridLayout()
        grid.setHorizontalSpacing(SIZES.space_xl)
        grid.setVerticalSpacing(SIZES.space_s)
        rows_data = [
            ("check.B3_V_A", "24.01 V", "23.85 - 24.15 V", "pass"),
            ("check.B3_V_B", "5.01 V", "4.90 - 5.10 V", "pass"),
            ("check.B3_V_C", "3.31 V", "3.25 - 3.35 V", "pass"),
            ("check.B3_T_REG", "28.57 °C", "max 30.1 °C", "pass"),
        ]
        for i, (name, measured, allowed, state) in enumerate(rows_data):
            vr = ValueRow(grid, i, name)
            vr.set_value(measured, allowed, state)
        grid_layout.addLayout(grid)
        layout.addWidget(grid_card)

        # StageStepper
        stepper_card, stepper_layout = card()
        stepper_layout.addWidget(TrLabel("gallery.stepper", role="h2"))
        stepper = StageStepper()
        stepper.set_state(Stage.PROGRAMMING)  # Shows "1 Programming"
        stepper_layout.addWidget(stepper)
        stepper2 = StageStepper()
        stepper2.set_state(Stage.TESTING)  # Shows "✓ Programming" and "1 Testing current"
        stepper_layout.addWidget(stepper2)
        layout.addWidget(stepper_card)

        # tint_panel
        panel_card, panel_layout = card()
        panel_layout.addWidget(TrLabel("gallery.panels", role="h2"))
        tp = tint_panel()
        tp[1].addWidget(TrLabel("gallery.tint_panel_content"))
        tp[1].addWidget(TrLabel("gallery.tint_panel_content"))
        panel_layout.addWidget(tp[0])
        layout.addWidget(panel_card)

        layout.addStretch(1)


def capture(out: Path, lang: str) -> Path:
    create_application()
    app = QApplication.instance()
    assert app is not None

    page = GalleryPage(lang)
    page.resize(1366, 768)
    page.show()
    app.processEvents()

    path = out / f"{lang}_gallery.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    page.grab().save(str(path))
    page.close()
    page.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)
    app.processEvents()
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render component gallery to PNG")
    parser.add_argument("--out", type=Path, default=Path("docs/screenshots/gallery"))
    parser.add_argument("--lang", nargs="+", default=["en", "mr"])
    args = parser.parse_args(argv)

    written: list[Path] = []
    for lang in args.lang:
        written.append(capture(args.out, lang))

    sys.stdout.write("\n".join(str(p) for p in written) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
