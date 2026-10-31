# UI rebuild rules (branch feature/ui-olive-rebuild)

Goal: rebuild the PySide6 UI layer in the new olive + yellow design. Read docs/ui-rebuild/FRONTEND_TRANSFORMATION_IMPLEMENTATION_PLAN.md and look at docs/ui-rebuild/design/*.png before any UI work.

Hard rules:
- Do NOT change viewmodels/, workers/, hardware, config, database, or i18n key names. UI only: src/parkomate/ui/theme, components, views, main_window.py, main.py.
- No hard-coded colour, size, or user-facing string in ui/ outside theme/tokens.py, theme/qss.py, theme/fonts.py. All text through t()/tr(). tests/ui/test_static.py must keep passing.
- Style with design tokens + Qt dynamic properties (variant, role, tone, status, step, card). No inline setStyleSheet.
- Keep bench ergonomics: 18 px base text, buttons >= 56 px, inputs >= 48 px, [Enter]/F-key hints, status = icon + word + colour, never colour alone.
- Keep reject takeover red (#9C1A10), toast green, status colours unchanged.
- Keep keyboard behaviour: Enter = primary action, Esc closes drawer/admin/confirm and never dismisses reject takeover, F1-F12 mappings.
- Every screen must render in English and Marathi at 1366x768 with no clipping.
- Python 3.12, mypy --strict, ruff clean. Add/adjust pytest-qt tests.
- Never claim something works unless you ran it. Report what you ran.
- Commit at the end of each batch with a conventional message. Do not push.

| Token | Value | Use |
|---|---|---|
| `accent` | `#5A6F2D` | Primary buttons, current step, selected tab |
| `accent_hover` | `#4A5C25` | Hover |
| `accent_pressed` | `#3B4A1D` | Pressed |
| `accent_soft` | `#EBEFE3` | Selected rows, pressed secondary |
| `accent_brand` | `#738B3B` | Gradient start, large decorative only |
| `accent_deco` | `#FACB34` | Progress gradient end, glow only. Never text |
| `bg` | `#FBFCFE` | Canvas |
| `surface` | `#FFFFFF` | Cards, bars |
| `surface_alt` | `#FAFAF8` | Info strip, table header |
| `surface_tint` | `#F1F4E8` | Nested tint panels |
| `border` | `#DDE3CB` | Card borders |
| `border_strong` | `#667085` | Control borders |
| `text` | `#111111` | Text, huge numbers |
| `text_muted` | `#5B6472` | Tracked labels, hints |
| `glow` | `#EEF3D3` | Top-right radial header glow |
| `status` | Unchanged from current `tokens.py` | pass / fail / warn / info |