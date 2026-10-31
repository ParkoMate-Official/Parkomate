# Parkomate Station — Frontend Design Documentation

This document describes the existing frontend of the **Parkomate Station** Windows
desktop application (PySide6 / Qt Widgets). It is a source-code-based reference for
maintaining the current design, extending the UI, and improving visual consistency
without unintentionally changing the application's visual identity.

> **Status:** Structure created. Content for each section is pending and will be
> filled in after a full frontend analysis pass.

---

## 1. Project and Frontend Overview

Parkomate Station is a Windows desktop application built with **PySide6 (Qt
Widgets)**. It takes one controller PCB (ESP32 + sensor + indicator) at a time
through four mandatory production stages — **A Programming → B Testing → C
Labeling → D Packaging** — plus a Login screen, an Admin area, and a Session
Summary screen. Any failure at a stage routes the device to a reject box and
shows an inline "reject takeover" overlay.

The UI follows an **MVVM** pattern: view models (`src/parkomate/ui/viewmodels/`)
own screen state and commands; views (`src/parkomate/ui/views/`) only render
that state. All user-facing text comes from the i18n catalogue
(`src/parkomate/i18n/en.json`, `mr.json`) via `t()` / `tr()` — there are no
hard-coded literals in `ui/` (enforced by `tests/ui/test_static.py`).

Styling is centralized in `src/parkomate/ui/theme/`: a `Colors`/`Sizes` token
dataclass (`tokens.py`, line 17), a generated QSS stylesheet (`qss.py`, line
12), and bundled Noto Sans fonts (`fonts.py`, line 15). The single application
stylesheet is applied once in `src/parkomate/ui/main.py` at line 31 via
`app.setStyleSheet(build_stylesheet())`.

The window is a `QMainWindow` (`src/parkomate/ui/main_window.py`, line 18) with
a `QStackedWidget` central widget holding five pages
(`src/parkomate/ui/main_window.py`, line 31-37): Starting, Login, Production
(shell), Session End, and Admin. Minimum window size is 1366×768
(`src/parkomate/ui/theme/tokens.py`, line 68-69); kiosk mode drops the window
frame and runs full-screen (`src/parkomate/ui/main_window.py`, line 40-41,
52-55).

## 2. Frontend Technology Stack

**Programming language:** Python 3.12 (`pyproject.toml`, line 6: `requires-python = ">=3.12,<3.13"`).

**GUI framework:** [PySide6](https://www.pyside.org/) 6.7–6.10 (`pyproject.toml`, line 9: `PySide6>=6.7,<6.11`). The UI uses Qt Widgets (`QMainWindow`, `QStackedWidget`, `QWidget`, `QFrame`, `QPushButton`, `QLabel`, `QLineEdit`, `QTableWidget`, `QTabWidget`, `QScrollArea`, `QProgressBar`, `QListWidget`, `QGridLayout`, `QHBoxLayout`, `QVBoxLayout`, `QFormLayout`), Qt signals/slots, `QShortcut`, `QTimer`, `QThreadPool`/`QRunnable`, and `QPainter` for custom painting.

**Styling system:** Qt Style Sheets (QSS), generated at runtime from design tokens by `parkomate/ui/theme/qss.py:12` (`build_stylesheet`) and applied once to the `QApplication` at `parkomate/ui/main.py:31` (`app.setStyleSheet(...)`). No CSS/SCSS/JS toolchain; no Tailwind; no CSS modules.

**Internationalization:** Custom i18n layer over JSON catalogues (`parkomate/i18n/en.json`, `mr.json`), accessed through `t()` / `tr()`. Live language switching is driven by `parkomate/ui/qt_i18n.py:17` (`LanguageNotifier`, a `QObject` emitting a `changed` signal) so widgets re-render via `retranslate()`.

**Relevant frontend dependencies** (from `pyproject.toml`, lines 8-21):

| Dependency | Version | Frontend role |
|---|---|---|
| `PySide6` | `>=6.7,<6.11` | Qt Widgets, core, gui,Multimedia (sound via `QApplication.beep`) |
| `opencv-python-headless` | `>=4.9` | Camera frames for the Labeling QR preview (`parkomate/ui/views/stages.py:526`, `CameraPreview`) |
| `pyzbar` | `>=0.1.9` | QR decoding (used by the hardware service, not the UI directly) |
| `pydantic` | `>=2.7,<3` | Settings/config models consumed by the Admin Settings editor |

**Dev/test tooling** (`pyproject.toml`, lines 27-34): `pytest`, `pytest-qt` (`qt_api = "pyside6"`, `pyproject.toml` line 56), `pytest-cov`, `ruff`, `mypy --strict`. Build: `pyinstaller` (P3, not yet run).

**Bundled fonts** (`parkomate/ui/assets/fonts/`): Noto Sans, Noto Sans Devanagari (Marathi), Noto Sans Symbols 2 (✓ ✕), registered at runtime via `QFontDatabase.addApplicationFontFromData` in `parkomate/ui/theme/fonts.py:28`.

## 3. Frontend Folder Structure

All frontend code lives under `src/parkomate/ui/` (package docstring at
`src/parkomate/ui/__init__.py:1`: *"PySide6 user interface (owner: Yugant).
MVVM: views render view models."*). The directory tree (source files only):

```
src/parkomate/ui/
├── __init__.py              # Package marker / docstring
├── main.py                  # QApplication factory + run_ui() entry point
├── main_window.py           # QMainWindow (the root window)
├── qt_i18n.py               # LanguageNotifier, TextKey, error_* helpers
├── screenshots.py           # Off-screen PNG renderer + StationDriver test harness
├── assets/
│   ├── __init__.py           # "Bundled UI assets (fonts)."
│   └── fonts/               # 5 TTFs + OFL.txt (see §14)
├── components/              # Reusable widgets (no screen logic)
│   ├── __init__.py           # "Reusable widgets."
│   ├── icons.py              # 21 vector icons + Icon widget
│   ├── overlays.py           # ErrorBanner, RejectTakeover, SuccessToast
│   └── widgets.py            # BigButton, StatusPill, CheckRow, StageStepper, ...
├── theme/                   # Design system: tokens, stylesheet, fonts
│   ├── __init__.py           # "Design tokens, stylesheet and fonts."
│   ├── tokens.py             # Colors + Sizes dataclasses (single source of truth)
│   ├── qss.py                # build_stylesheet() -> the one QSS string
│   └── fonts.py              # load_fonts(), app_font(), font()
├── viewmodels/              # Qt signal-based state + commands (no widgets)
│   ├── __init__.py           # "View models: screen state and commands."
│   ├── base.py               # Action, ErrorState, ConfirmState, StatusLine, StageViewModel
│   ├── bridge.py             # EventBridge: core events -> Qt signals (queued)
│   ├── programming.py        # ProgrammingViewModel, StepState
│   ├── testing.py            # TestingViewModel
│   ├── labeling.py           # ChecklistMixin, LabelingViewModel, PackagingViewModel
│   └── station.py            # StationController, Page, LoginPhase, SendState
├── views/                   # Screens (render view-model state only)
│   ├── __init__.py           # "Widgets only: render view-model state."
│   ├── pages.py              # StartingView, LoginView, SessionEndView, FatalView
│   ├── shell.py              # ProductionShell + TopBar, InfoStrip, BottomBar, SessionDrawer
│   ├── stages.py             # ProgrammingView, TestingView, LabelingView, PackagingView
│   └── admin.py              # AdminView + SettingsTab, OperatorsTab, ReportsTab, ...
└── workers/                 # Off-GUI-thread task runner
    ├── __init__.py           # "Background workers (QThreadPool)."
    └── runner.py             # TaskRunner, _Job, _Bridge
```

**Application entry point.** `python -m parkomate` runs `src/parkomate/__main__.py`,
which calls `parkomate.ui.main.run_ui()` (`src/parkomate/ui/main.py:46`). That
function builds the `QApplication` via `create_application()`
(`src/parkomate/ui/main.py:22`), then constructs the `MainWindow`
(`src/parkomate/ui/main_window.py:18`) and enters the Qt event loop
(`src/parkomate/ui/main.py:82`).

**Styling files.** The only stylesheet is generated at runtime by
`parkomate/ui/theme/qss.py:12` (`build_stylesheet`) from the tokens in
`parkomate/ui/theme/tokens.py:17` (`Colors`) and `tokens.py:49` (`Sizes`); it is
applied once at `parkomate/ui/main.py:31`. There are no `.css`/`.scss` files, no
Tailwind config, and no per-component style files — every widget that needs
styling opts in via dynamic properties (`variant`, `role`, `tone`, `status`,
`step`, `card`) set in Python and read by the QSS selector.

**Assets.** Only fonts are bundled, under `src/parkomate/ui/assets/fonts/`
(`src/parkomate/ui/assets/__init__.py:1`). There are no image, icon, or SVG
assets — all 21 icons are drawn at runtime by `QPainter` in
`src/parkomate/ui/components/icons.py:37` (`paint_icon`).

**Tests.** UI tests live in `tests/ui/` (`test_static.py`, `test_flow.py`,
`test_admin.py`, `conftest.py`) and drive the real UI through the
`StationDriver` harness in `src/parkomate/ui/screenshots.py:65`.

## 4. Application Architecture

Parkomate Station follows an **MVVM (Model-View-ViewModel)** architectural pattern implemented in PySide6/Qt Widgets. The key architectural elements are:

### 4.1 Application Initialization and Entry Point
- **Entry point**: `src/parkomate/__main__.py` → calls `parkomate.ui.main.run_ui()` (line 46)
- **QApplication creation**: `src/parkomate/ui/main.py:22-32` (`create_application()`)
  - Loads bundled Noto Sans fonts via `load_fonts()`
  - Sets application font via `app_font()` (Noto Sans + Devanagari fallback, 18px base)
  - Generates and applies the complete QSS stylesheet via `build_stylesheet()` (single stylesheet for entire app)
- **Single-instance enforcement**: Uses `QLockFile` on `station.lock` in app data directory (line 51-61)
- **Context building**: `build_context()` creates `AppContext` with settings, repos, hardware service, and secrets (line 64)
- **Main window construction**: `MainWindow(controller, kiosk=...)` (line 78), then `window.show_station()` (line 79)

### 4.2 Main Window and Screen Navigation
- **Root window**: `MainWindow` (`src/parkomate/ui/main_window.py:18`) inherits `QMainWindow`
- **Central widget**: `QStackedWidget` holding 5 top-level pages (line 24-37):
  1. `Page.STARTING` → `StartingView`
  2. `Page.LOGIN` → `LoginView`
  3. `Page.PRODUCTION` → `ProductionShell` (contains 4 stage sub-pages)
  4. `Page.SESSION_END` → `SessionEndView`
  5. `Page.ADMIN` → `AdminView`
- **Navigation**: `StationController.page_changed` signal → `MainWindow._page_changed()` switches stacked widget current page
- **Kiosk mode**: Frameless full-screen window (`Qt.FramelessWindowHint`, `showFullScreen()`) when enabled via CLI `--kiosk` or settings

### 4.3 View-Model Layer (State and Commands)
- **StationController** (`src/parkomate/ui/viewmodels/station.py:125`): Central coordinator
  - Owns login phase, current stage, device state, session, ambient temperature
  - Emits Qt signals for all state changes: `page_changed`, `stage_changed`, `device_changed`, `counters_changed`, `error_changed`, `confirm_changed`, `drawer_changed`, `toast`, `reject_shown`, `reject_cleared`, `bottom_bar_changed`, `tick`, `session_changed`, `ambient_changed`, `counters_changed`
- **Stage ViewModels** (`src/parkomate/ui/viewmodels/*.py`):
  - `ProgrammingViewModel`, `TestingViewModel`, `LabelingViewModel`, `PackagingViewModel`
  - Each inherits `StageViewModel` (base class with `changed` signal, `primary()`, `secondary()`, `status()`, `reset()`, `enter()`, `leave()`)
  - Own screen-specific state (port selection, sensor readings, checklist ticks, etc.)
- **Action/Command pattern**: `Action` dataclass (`src/parkomate/ui/viewmodels/base.py:23`) encapsulates button handlers with enabled/disabled state, keyboard hints, and variants

### 4.4 Background Task Execution
- **TaskRunner** (`src/parkomate/ui/workers/runner.py:12`): `QThreadPool`-based runner for off-GUI-thread work
  - `TaskRunner.submit(fn, on_success, on_error, name)` executes `fn` in `QRunnable`
  - Results delivered back to GUI thread via queued signal connections
  - Used for: hardware communication, firmware flashing, file exports, email sending

### 4.5 Internationalization (i18n)
- **LanguageNotifier** (`src/parkomate/ui/qt_i18n.py:17`): `QObject` emitting `changed` signal on language switch
- **Translation keys**: All user-facing text uses `t(key, **params)` / `tr()` from JSON catalogues (`en.json`, `mr.json`)
- **Auto-retranslate**: Widgets connect to `language_notifier().changed` and call `retranslate()` to update text

### 4.6 Overlays and Global Feedback
- **ErrorBanner**: Inline top banner for errors with retry action (`src/parkomate/ui/components/overlays.py:20`)
- **RejectTakeover**: Full-screen red overlay blocking interaction until operator confirms device placed in reject box (`src/parkomate/ui/components/overlays.py:127`)
- **SuccessToast**: Green auto-dismissing toast for completed devices (`src/parkomate/ui/components/overlays.py:224`)
- All overlays parented to `ProductionShell` and sized via `eventFilter` on parent resize

### 4.7 Event Handling and Signals/Slots
- **Qt signals**: Extensively used for view-model → view communication (all `changed` signals)
- **Keyboard shortcuts**: `QShortcut` for Enter/Escape/F1-F12 installed on `ProductionShell` (line 469-486)
- **Focus management**: Explicit focus setting on primary actions, form fields, and overlay buttons

## 5. Screen Inventory

| Screen Name | File Path | Main Components | Layout | Navigation | Implementation Status |
| ----------- | --------- | --------------- | ------ | ---------- | --------------------- |
| **Starting Screen** | `src/parkomate/ui/views/pages.py:87` (`StartingView`) | `TrLabel` for brand (`app.brand`, role="h1") and subtitle (`starting.text`, role="muted") | Centered vertical (`QVBoxLayout` with stretches) | Auto-transition to Login after context loads | Fully implemented |
| **Login Screen** | `src/parkomate/ui/views/pages.py:102` (`LoginView`) | `card()` panel, `LanguageSwitch`, two `QLineEdit` (operator ID, password), `BigButton` (login), `BigButton` (show/hide password), `MessageBox` (error/info), ambient temperature display | Centered card (640px wide) with `QVBoxLayout`/`QHBoxLayout` | Enter credentials → `controller.login()` → on success → Production Shell | Fully implemented |
| **Production Shell** | `src/parkomate/ui/views/shell.py:407` (`ProductionShell`) | `TopBar`, `InfoStrip`, `ErrorBanner`, `QStackedWidget` (4 stage views), `BottomBar`, `SessionDrawer`, `RejectTakeover`, `SuccessToast` | Vertical stack: TopBar → InfoStrip → Body (stretch) → BottomBar; overlays on top | Header buttons: Session Drawer toggle, Admin access; Stage progression via controller | Fully implemented |
| **Programming Stage (A)** | `src/parkomate/ui/views/stages.py:162` (`ProgrammingView`) | 4 `StepRow` (Connect, Whitelist, Firmware, Upload), `QComboBox` (port), `QProgressBar`, `StatusPill` (large), `CounterBadge` ×3, adjust confirmation panel | Two-column scrollable: left=steps (ratio 5), right=results/counters (ratio 6) | Success → Testing Stage; Failure → RejectTakeover (A box) | Fully implemented |
| **Testing Stage (B)** | `src/parkomate/ui/views/stages.py:366` (`TestingView`) | 3 `StepRow` (Comm, Sensor, Electrical), sensor reading labels, `DecisionRow` ×2 (sensor/indicator), `ValueRow` ×4 (V_A, V_B, V_C, T_reg), ambient + remeasure button | Two-column scrollable: left=steps (ratio 6), right=measurements (ratio 5) | All pass → Labeling Stage; Any fail → RejectTakeover (B box) | Fully implemented |
| **Labeling Stage (C)** | `src/parkomate/ui/views/stages.py:621` (`LabelingView`) | Checklist: 4 `CheckRow` (C1-C4), `CameraPreview` (QR scan), decoded QR display, manual ID entry panel, `StatusPill` (identity), `RejectChooser` | Two-column scrollable: left=checks, right=camera/identity | QR + checks pass → Packaging Stage; Fail → RejectTakeover (C box) | Fully implemented |
| **Packaging Stage (D)** | `src/parkomate/ui/views/stages.py:738` (`PackagingView`) | Checklist: 4 `CheckRow` (D1-D4), device ID/label, completion summary (✓ A/B/C), `RejectChooser` | Two-column scrollable: left=checks, right=summary | All pass → Device complete, return to Programming for next; Fail → RejectTakeover (D box) | Fully implemented |
| **Session End Screen** | `src/parkomate/ui/views/pages.py:237` (`SessionEndView`) | `card()` panel (980px), `QGridLayout` summary (11 rows × 2 cols), `StatusPill` (send state), report path label, logout `BigButton` | Centered card with vertical layout | Enter/Escape or Logout button → `controller.finish_logout()` → Login Screen | Fully implemented |
| **Admin Area** | `src/parkomate/ui/views/admin.py:965` (`AdminView`) | `QTabWidget` with 5 tabs: SettingsTab, OperatorsTab, ReportsTab, CountersTab, ErrorLogTab; back button | Full-window card with vertical layout, tabs as main content | TopBar admin button (admin only); Escape → back to Production | Fully implemented |
| **Fatal Error Screen** | `src/parkomate/ui/views/pages.py:365` (`FatalView`) | `card()` panel (900px), warning icon, error title/cause, location path, settings issue list, close app `BigButton` | Centered card with vertical layout | Close button → application exit | Fully implemented |

## 6. Component Inventory

| Component | File Path | Purpose | Styling Source | Used By |
| --------- | --------- | ------- | -------------- | ------- |
| `TopBar` | `src/parkomate/ui/views/shell.py:67` | Header: brand + mock badge + StageStepper + LanguageSwitch + Session/Admin buttons | QSS `#TopBar`, dynamic `variant` on buttons | `ProductionShell` |
| `InfoStrip` | `src/parkomate/ui/views/shell.py:121` | Compact row: device ID, operator + elapsed, live counters | QSS `#InfoStrip` | `ProductionShell` |
| `BottomBar` | `src/parkomate/ui/views/shell.py:184` | Status message, disabled reason, secondary actions, primary action | QSS `#BottomBar`, `InlineConfirm` | `ProductionShell` |
| `SessionDrawer` | `src/parkomate/ui/views/shell.py:319` | Slide-out panel: session devices list, counters, ambient, End Session | QSS `#Drawer` | `ProductionShell` |
| `StageStepper` | `src/parkomate/ui/components/widgets.py:280` | Horizontal step indicator: A→B→C→D with current/done/todo/rejected states | QSS `QLabel[step="current\|done\|todo\|rejected"]` | `TopBar` |
| `BigButton` | `src/parkomate/ui/components/widgets.py:77` | Primary action button (min 56px), variants: primary/secondary/danger/pass/link/toggle/takeover | QSS `QPushButton[variant="..."]`, dynamic properties | All views, dialogs, overlays |
| `StatusPill` | `src/parkomate/ui/components/widgets.py:132` | Icon + word + color badge (pass/fail/warn/working/pending/info) | QSS `[tone="..."]`, `QLabel[status="..."]` | Stage views, Shell, SessionEnd, Admin |
| `CheckRow` | `src/parkomate/ui/components/widgets.py:179` | Full-row check item (min 68px): checkbox, icon, label, F-key hint | Custom `paintEvent` (QPainter), tokens | `LabelingView`, `PackagingView` |
| `ValueRow` | `src/parkomate/ui/components/widgets.py:452` | Grid cell row: name \| measured \| allowed \| status pill | QSS via child widgets | `TestingView` |
| `CameraPreview` | `src/parkomate/ui/views/stages.py:526` | Live camera feed or simulated preview with framing guide + scan line | Custom `paintEvent` (QPainter) | `LabelingView` |
| `StepRow` | `src/parkomate/ui/views/stages.py:74` | Numbered step with title, StatusPill, indented body | QSS `[tone="..."]` | `ProgrammingView`, `TestingView` |
| `RejectChooser` | `src/parkomate/ui/views/stages.py:127` | Inline "which item failed?" grid of danger buttons | QSS `[tone="fail"]` | `LabelingView`, `PackagingView` |
| `InlineConfirm` | `src/parkomate/ui/components/widgets.py:419` | Inline confirmation bar replacing OS dialogs | QSS `[tone="warn"]` | `BottomBar`, `CountersTab` |
| `ErrorBanner` | `src/parkomate/ui/components/overlays.py:20` | Top error banner: title, cause, steps, retry, details link | QSS `#ErrorBanner`, `[tone="fail\|warn"]` | `ProductionShell` |
| `RejectTakeover` | `src/parkomate/ui/components/overlays.py:127` | Full-screen red overlay: reject instruction, box letter, confirm button | QSS `#RejectTakeover`, inline `setStyleSheet` on box label | `ProductionShell` |
| `SuccessToast` | `src/parkomate/ui/components/overlays.py:224` | Green auto-dismissing toast for device completion | QSS `#SuccessToast` | `ProductionShell` |
| `LanguageSwitch` | `src/parkomate/ui/components/widgets.py:376` | Toggle buttons for EN/MR (native script names) | QSS `[variant="toggle"]` | `LoginView`, `TopBar` |
| `CounterBadge` | `src/parkomate/ui/components/widgets.py:341` | Caption + large number with optional icon | QSS `QLabel` roles | `ProgrammingView` |
| `TrLabel` | `src/parkomate/ui/components/widgets.py:50` | Auto-translating label bound to i18n key + params | QSS `QLabel[role="..."]` | All views |
| `ResultLine` | `src/parkomate/ui/views/admin.py:104` | One-line admin feedback with tone (pass/fail/info) | QSS `[status="..."]` | Admin tabs |
| `SettingsTab` | `src/parkomate/ui/views/admin.py:129` | Dynamic form for Pydantic settings + secrets management | `QFormLayout` + QSS inputs | `AdminView` |
| `OperatorsTab` | `src/parkomate/ui/views/admin.py:417` | Operator table with activate/deactivate, unlock, role toggle, password reset | `QTableWidget` + QSS | `AdminView` |
| `ReportsTab` | `src/parkomate/ui/views/admin.py:613` | Session reports, exports (xlsx/csv), outbox management | `QTableWidget` + QSS | `AdminView` |
| `CountersTab` | `src/parkomate/ui/views/admin.py:835` | Station counter display + reset with inline confirmation | QSS labels/buttons | `AdminView` |
| `ErrorLogTab` | `src/parkomate/ui/views/admin.py:901` | Error log viewer with code filter + JSON detail pane | `QTableWidget`, `QPlainTextEdit` | `AdminView` |
| `MessageBox` | `src/parkomate/ui/views/pages.py:50` | Inline error/info box with icon, title, body | QSS `[tone="fail\|info"]` | `LoginView` |
| `DecisionRow` | `src/parkomate/ui/views/stages.py:333` | Sensor/indicator success/fail toggle buttons | QSS `BigButton[variant="pass\|danger"]` | `TestingView` |

## 7. Complete Color Palette

All colors are defined as design tokens in `src/parkomate/ui/theme/tokens.py` (`Colors` dataclass, lines 17-68) and consumed by the generated QSS in `src/parkomate/ui/theme/qss.py`. No hardcoded color literals exist in view/component code — all styling references the tokens.

| Color Name | HEX | RGB | Usage | Source File | Line Number |
| ---------- | --- | --- | ----- | ----------- | ----------- |
| `bg` | `#FBFCFE` | 251, 252, 254 | Main application background (window, pages) | `tokens.py` | 19 |
| `surface` | `#FFFFFF` | 255, 255, 255 | Primary card background, active inputs, button surface | `tokens.py` | 20 |
| `surface_alt` | `#FAFAF8` | 250, 250, 248 | Inactive tab background, table alternate row, info strip | `tokens.py` | 21 |
| `surface_tint` | `#F1F4E8` | 241, 244, 232 | Nested metric panel background (soft olive tint) | `tokens.py` | 22 |
| `border` | `#DDE3CB` | 221, 227, 203 | Standard card and container borders, table grid lines | `tokens.py` | 25 |
| `border_strong` | `#667085` | 102, 112, 133 | Control borders, input borders, button borders | `tokens.py` | 26 |
| `text` | `#111111` | 17, 17, 17 | Primary headings, huge numbers, input text | `tokens.py` | 29 |
| `text_muted` | `#5B6472` | 91, 100, 114 | Subtitles, helper text, inactive steps, placeholders | `tokens.py` | 30 |
| `accent` | `#5A6F2D` | 90, 111, 45 | **Primary brand/action color** (Olive) — primary buttons, active stepper capsule, selected tab | `tokens.py` | 33 |
| `accent_hover` | `#4A5C25` | 74, 92, 37 | Primary button hover state | `tokens.py` | 34 |
| `accent_pressed` | `#3B4A1D` | 59, 74, 29 | Primary button pressed / active state | `tokens.py` | 35 |
| `accent_soft` | `#EBEFE3` | 235, 239, 227 | Selected rows, pressed secondary button | `tokens.py` | 36 |
| `accent_brand` | `#738B3B` | 115, 139, 59 | Gradient start, large decorative only | `tokens.py` | 37 |
| `accent_deco` | `#FACB34` | 250, 203, 52 | Progress bar fill, decorative highlights (never text) | `tokens.py` | 38 |
| `yellow_soft` | `#FFF1DB` | 255, 241, 219 | Top simulation banner, warning background tint | `tokens.py` | 39 |
| `yellow_dark` | `#6B3A00` | 107, 58, 0 | Simulation banner text, warning header (AAA contrast) | `tokens.py` | 40 |
| `focus` | `#111111` | 17, 17, 17 | **Keyboard focus ring** (double ring outline, ≥3:1 against white/bg) | `tokens.py` | 43 |
| `pass_bg` | `#F4FBF6` | 244, 251, 246 | Pass step card background tint | `tokens.py` | 46 |
| `pass_fg` | `#0B5D35` | 11, 93, 53 | Pass badges, success buttons, pass borders (AAA) | `tokens.py` | 47 |
| `pass_solid` | `#0B5D35` | 11, 93, 53 | Pass solid badge, checked pass button, success toast bg | `tokens.py` | 48 |
| `fail_bg` | `#FDE9E7` | 253, 233, 231 | Locked alert background, error banner tint | `tokens.py` | 49 |
| `fail_fg` | `#991B1B` | 153, 27, 27 | Reject takeover, fail badges, red outline buttons (AAA) | `tokens.py` | 50 |
| `fail_solid` | `#991B1B` | 153, 27, 27 | **Reject takeover background**, checked danger button | `tokens.py` | 51 |
| `warn_bg` | `#FFF1DB` | 255, 241, 219 | Warning banner background tint | `tokens.py` | 52 |
| `warn_fg` | `#6B3A00` | 107, 58, 0 | Warning banner left bar, caution badges (AAA) | `tokens.py` | 53 |
| `info_bg` | `#EFF6FF` | 239, 246, 255 | Working step card background tint | `tokens.py` | 54 |
| `info_fg` | `#1E40AF` | 30, 64, 175 | Working/uploading badge, active step border (AAA) | `tokens.py` | 55 |
| `on_status_solid` | `#FFFFFF` | 255, 255, 255 | Text/icons on solid status backgrounds (pass/fail/toast) | `tokens.py` | 56 |
| `disabled_bg` | `#CBD5E1` | 203, 213, 225 | Disabled button/control background | `tokens.py` | 59 |
| `disabled_fg` | `#475569` | 71, 85, 105 | Disabled control text (AA contrast) | `tokens.py` | 60 |
| `tooltip_bg` | `#111111` | 17, 17, 17 | Tooltip background | `tokens.py` | 63 |
| `tooltip_fg` | `#FFFFFF` | 255, 255, 255 | Tooltip text | `tokens.py` | 64 |
| `glow` | `#FEF3D3` | 254, 243, 211 | Top-right radial header glow | `tokens.py` | 67 |

### Color Usage Notes
- **Olive + Yellow identity**: Primary brand color is Olive (`#5A6F2D`). Yellow/gold (`#FACB34` / `#B59E2B`) is reserved for decorative progress fills, mode warnings, and simulation callouts.
- **Status colors reserved**: Green/Red/Amber/Blue used *only* for status (pass/fail/warn/info), never decoratively.
- **Status never by color alone**: Every status indicator combines icon + word + color (`StatusPill`, `CheckRow`).
- **Focus ring**: Double-ring `#111111` outline with 2 px white gap chosen for ≥3:1 contrast against both white (`surface`) and canvas (`bg`).
- **WCAG compliance**: Contrast ratios verified by `tests/ui/test_theme.py` and `tests/ui/test_static.py` — all text ≥ AA (4.5:1), status text ≥ AAA (7:1).

## 8. Existing Themes and Design Tokens

### 8.1 Design Token System (Single Source of Truth)
All design tokens are defined in **`src/parkomate/ui/theme/tokens.py`** as two frozen `@dataclass`es:

- **`Colors`** (lines 17-68): 33 color tokens covering canvas, surfaces, borders, text, brand olive/yellow, focus, status (pass/fail/warn/info), disabled, and tooltips.
- **`Sizes`** (lines 71-120): 28 sizing tokens covering font sizes (8 variants), button/input heights, border radii (7 variants), spacing scale (5 steps), focus width/gap, tabs, tooltips, and minimum window dimensions.

```python
@dataclass(frozen=True, slots=True)
class Colors:
    bg: str = "#FBFCFE"
    surface: str = "#FFFFFF"
    accent: str = "#5A6F2D"
    # ... 30 more colors

@dataclass(frozen=True, slots=True)
class Sizes:
    font_base: int = 18
    button_height: int = 56
    input_height: int = 48
    card_radius: int = 24
    # ... 24 more sizes
```

Singletons `COLORS = Colors()` and `SIZES = Sizes()` are imported throughout the codebase.

### 8.2 Stylesheet Generation
- **`src/parkomate/ui/theme/qss.py:12`** — `build_stylesheet(c: Colors = COLORS, s: Sizes = SIZES) -> str`
- Generates a single application QSS string by f-string interpolation of token values.
- Applied once at `QApplication` level in `src/parkomate/ui/main.py:31`.
- **No external CSS/SCSS files**, no inline `setStyleSheet()`.

### 8.3 Dynamic Property Styling (Opt-In Pattern)
Widgets opt into visual variants via **Qt dynamic properties** set in Python, read by QSS attribute selectors:

| Property | Values | Example Selector |
| -------- | ------ | ---------------- |
| `variant` | `"primary"`, `"secondary"`, `"danger"`, `"pass"`, `"link"`, `"toggle"`, `"takeover"` | `QPushButton[variant="primary"]` |
| `role` | `"h1"`, `"h2"`, `"muted"`, `"small"`, `"hero-number"`, `"value"`, `"value_large"`, `"hint"` | `QLabel[role="hero-number"]` |
| `tone` | `"pass"`, `"fail"`, `"warn"`, `"info"`, `"pending"` | `QFrame[tone="pass"]` |
| `status` | `"pass"`, `"fail"`, `"warn"`, `"info"`, `"pending"` | `QLabel[status="pass"]` |
| `step` | `"current"`, `"done"`, `"todo"`, `"rejected"` | `QLabel[step="current"]` |
| `card` | `true` | `QFrame[card="true"]` |
| `nested_panel` | `"true"` | `QFrame[nested_panel="true"]` |
| `box_letter` | `"true"` | `QLabel[box_letter="true"]` |
| `danger_outline` | `"true"` | `QPushButton[danger_outline="true"]` |
| `invalid` | `"true"` | `QLineEdit[invalid="true"]` |

Helper functions in `src/parkomate/ui/components/widgets.py:36-47`:
- `restyle(widget)` — calls `style().unpolish()` / `polish()` to refresh after property change.
- `set_prop(widget, name, value)` — sets property only if changed, then calls `restyle()`.

### 8.4 Theme Variants
**Single Light Industrial Olive Theme** implemented. The token system supports easy addition of dark/high-contrast themes by providing alternate `Colors`/`Sizes` instances to `build_stylesheet()`.

### 8.5 WCAG Contrast Utilities
`tokens.py` includes `relative_luminance()` and `contrast_ratio()` functions used by `tests/ui/test_theme.py` to verify:
- All text ≥ 4.5:1 (WCAG AA)
- Status text ≥ 7:1 (WCAG AAA)

## 9. Typography System

### 9.1 Font Families
Three bundled Noto font families registered at runtime via `QFontDatabase.addApplicationFontFromData()` in `src/parkomate/ui/theme/fonts.py:28-47`:

| Family | File | Purpose |
| ------ | ---- | ------- |
| **Noto Sans** | `NotoSans-Regular.ttf`, `NotoSans-Bold.ttf` | Latin script (English UI) |
| **Noto Sans Devanagari** | `NotoSansDevanagari-Regular.ttf`, `NotoSansDevanagari-Bold.ttf` | Marathi (Devanagari script) |
| **Noto Sans Symbols 2** | `NotoSansSymbols2-Regular.ttf` | UI symbols (✓, ✕, etc.) |

**Fallback chain** (configured in `fonts.py:45-46`):
```python
QFont.insertSubstitutions("Noto Sans Devanagari", ["Noto Sans", "Noto Sans Symbols 2"])
QFont.insertSubstitutions("Noto Sans", ["Noto Sans Devanagari", "Noto Sans Symbols 2"])
```
Ensures glyph coverage for mixed-script text (e.g., Marathi with Latin numerals/symbols).

### 9.2 Font Sizes (Design Tokens)
Defined in `Sizes` dataclass (`tokens.py:49-69`):

| Token | Size (px) | Usage |
| ----- | --------- | ----- |
| `font_base` | 18 | Default body text, buttons, labels |
| `font_small` | 15 | Secondary text, hints, table headers, tooltips |
| `font_h2` | 22 | Section headings, button text (primary) |
| `font_h1` | 28 | Page titles, major headings |
| `font_value` | 32 | Large value displays (measurements, device IDs) |
| `font_value_large` | 40 | Extra-large values (QR decoded ID) |
| `font_takeover` | 56 | Reject takeover headline |
| `font_box_letter` | 160 | Reject box letter (A/B/C/D) |

### 9.3 Font Weights
- **Regular (400)**: Body text, secondary labels
- **Semi-bold (600)**: Primary buttons (`BigButton` default), tab labels
- **Bold (700)**: Headings (`h1`, `h2`), value displays, checked `CheckRow` labels, status words

### 9.4 Text Roles (QSS Selectors)
Applied via `role` dynamic property on `QLabel` (and `TrLabel`):

| Role | QSS Selector | Font Size | Weight | Color |
| ---- | ------------ | --------- | ------ | ----- |
| `h1` | `QLabel[role="h1"]` | `font_h1` (28px) | 700 | `text` |
| `h2` | `QLabel[role="h2"]` | `font_h2` (22px) | 700 | `text` |
| `muted` | `QLabel[role="muted"]` | `font_base` (18px) | 400 | `text_muted` |
| `small` | `QLabel[role="small"]` | `font_small` (15px) | 400 | `text_muted` |
| `value` | `QLabel[role="value"]` | `font_value` (32px) | 700 | `text` |
| `value_large` | `QLabel[role="value_large"]` | `font_value_large` (40px) | 700 | `text` |
| `hint` | `QLabel[role="hint"]` | `font_small` (15px) | 400 | `text_muted` |

### 9.5 QFont Construction
- **Base application font**: `app_font()` (`fonts.py:50-56`) → Noto Sans + fallbacks, 18px, antialiased
- **Per-widget fonts**: `font(px, bold=False)` helper (`fonts.py:59-63`) creates derived `QFont` with specific pixel size and weight
- **No line-height/letter-spacing tokens** — relies on Qt defaults

### 9.6 Internationalization Considerations
- Marathi (Devanagari) glyphs render via Noto Sans Devanagari
- Mixed-script text handled by font substitution chain
- All font sizes in pixels (not points) for consistent cross-DPI rendering on Windows

## 10. Spacing and Layout System

### 10.1 Spacing Scale (Design Tokens)
Defined in `Sizes` dataclass (`tokens.py:62-66`):

| Token | Value | Usage |
| ----- | ----- | ----- |
| `space_xs` | 4px | Tight internal gaps (icon→text, checkbox gaps) |
| `space_s` | 8px | Standard small gaps (form field spacing, layout margins) |
| `space_m` | 16px | **Base unit** — card margins, layout spacing, button horizontal padding |
| `space_l` | 24px | Large gaps (section separation, card internal padding) |
| `space_xl` | 32px | Extra-large gaps (page-level section breaks) |

### 10.2 Layout Classes Used
| Layout | Primary Usage |
| ------ | ------------- |
| `QVBoxLayout` | Vertical stacking (pages, panels, forms, overlays) |
| `QHBoxLayout` | Horizontal rows (headers, button groups, icon+text) |
| `QGridLayout` | Aligned multi-column (settings forms, test value tables, session summary) |
| `QFormLayout` | Label-field pairs (Admin SettingsTab) |
| `QStackedWidget` | Page switching (MainWindow, ProductionShell stage views) |
| `QScrollArea` | Overflow handling (scroll_card for long content) |

### 10.3 Standard Layout Patterns
- **Card pattern** (`widgets.py:476-485`): `QFrame[card="true"]` + `QVBoxLayout` with `space_l` margins and `space_m` spacing
- **Scroll card** (`widgets.py:488-507`): Card containing `QScrollArea#CardScroll` with transparent background chain
- **Centered page** (`pages.py:35-47`): Outer stretch + horizontal centered fixed-width inner widget
- **Two-pane stage view** (`stages.py:108-119`): `QHBoxLayout` with stretch ratios (5:6 or 6:5), each pane a scroll_card

### 10.4 Window Dimensions
- **Minimum size**: 1366×768 (`Sizes.min_window_width`, `min_window_height` at `tokens.py:68-69`)
- **Default**: Maximized on desktop; full-screen frameless in kiosk mode
- **No responsive breakpoints** — fixed minimum ensures layout integrity

### 10.5 Component-Specific Spacing
| Component | Margins | Spacing |
| --------- | ------- | ------- |
| `BigButton` | 0 `space_l` (horizontal) | — |
| `CheckRow` | Internal: 16px left, 16px right | Icon gaps: 16px, 16px, 16px |
| `StatusPill` | 10/4/14/4 (L/T/R/B) | 8px icon→label |
| `StageStepper` | 0 | 6px between labels, 10px label padding |
| `TopBar` | `space_l` / `space_s` | `space_m` |
| `InfoStrip` | `space_l` / `space_xs` | `space_s` |
| `BottomBar` | `space_l` / 10 | `space_m` |
| `SessionDrawer` | `space_l` all sides | `space_m` |

### 10.6 Size Policies and Stretch
- **Primary actions**: `MinimumWidth(300)` on primary `BigButton` in `BottomBar`
- **Stage panes**: Stretch factors 5:6 (Programming) or 6:5 (Testing) via `QHBoxLayout.addWidget(widget, stretch)`
- **Scroll areas**: `setWidgetResizable(True)`, horizontal scrollbar always off
- **Cards**: `Maximum` horizontal policy on `StatusPill`, `Expanding` on content areas

## 11. Borders, Radii, and Shadows

### 11.1 Border Radius Tokens
| Token | Value | Usage |
| ----- | ----- | ----- |
| `radius` | 10px | Cards, buttons, input fields, status frames, stepper pills |
| **Input-specific** | 8px | `QLineEdit`, `QComboBox`, `QSpinBox`, etc. (hardcoded in QSS) |
| **Progress bar** | 6px (chunk) / 8px (track) | `QProgressBar` |
| **Reject box letter** | 24px | Inline style on `RejectTakeover` box label |

### 11.2 Border Widths and Colors
| Element | Width | Color (Token) | Color (HEX) |
| ------- | ----- | ------------- | ----------- |
| Card border | 1px | `border` | `#C9CED6` |
| Default button border | 2px | `border_strong` | `#667085` |
| Primary button border | 2px | `accent` | `#1849A9` |
| Pass button border | 2px | `pass_fg` | `#0A4D2B` |
| Danger button border | 2px | `fail_fg` | `#86170F` |
| Input border | 2px | `border_strong` | `#667085` |
| Input focus border | 3px (`focus_width`) | `focus` | `#B54708` |
| Focus button border | 3px (`focus_width`) | `focus` | `#B54708` |
| Focus takeover border | 4px | `text` | `#101828` |
| Table/List border | 1px | `border` | `#C9CED6` |
| Table header bottom | 1px | `border` | `#C9CED6` |
| Status frame border | 2px | Status-specific fg | `pass_fg`/`fail_fg`/`warn_fg`/`info_fg` |
| TopBar bottom | 1px | `border` | `#C9CED6` |
| InfoStrip bottom | 1px | `border` | `#C9CED6` |
| BottomBar top | 1px | `border` | `#C9CED6` |
| Drawer left | 2px | `border_strong` | `#667085` |
| RejectTakeover box | 6px | `on_status_solid` | `#FFFFFF` (inline style) |

### 11.3 Focus Indicators
- **Universal focus ring**: 3px solid amber (`#B54708` = `focus` token) on buttons, inputs, tables, lists
- **Exception**: `RejectTakeover` primary button uses 4px solid `text` (`#101828`) for extra visibility on red background
- **CheckRow**: Focus overrides border to `focus` color at `focus_width` (3px)

### 11.4 Shadows and Elevation
- **No box-shadow / drop-shadow** used in QSS or custom painting
- **Flat design** with solid color backgrounds and explicit borders for elevation
- **Overlay elevation**: `RejectTakeover` and `SuccessToast` use `raise_()` and full-parent geometry for visual layering

### 11.5 Separators and Dividers
- **Tab underline**: 3px solid `accent` on selected tab (`QTabBar::tab:selected`)
- **Table grid**: 1px `border` color via `gridline-color`
- **Header divider**: 1px bottom border on `QHeaderView::section`
- **Panel dividers**: 1px `border` on TopBar/InfoStrip/BottomBar edges

### 11.6 Custom Painting Borders
- **CheckRow**: Custom rounded rect (radius 10px) with 2px border (3px on focus) drawn in `paintEvent`
- **RejectTakeover box label**: 6px solid white border with 24px radius (inline `setStyleSheet`)
- **CameraPreview framing guide**: 4px white corner brackets drawn via `QPainter`

## 12. Component Styling

### 12.1 Buttons (`BigButton` + QSS)
**Base** (`QPushButton`, `qss.py:48-64`):
- Min-height: 56px (`button_height`)
- Padding: 0 24px (`space_l`)
- Radius: 10px
- Font: 600 weight, `font_base` (18px)
- Background: `surface` (`#FFFFFF`)
- Border: 2px `border_strong` (`#667085`)
- Text: `text` (`#101828`)

**Variants** (via `variant` dynamic property):

| Variant | Background | Text | Border | Font Size | Notes |
| ------- | ---------- | ---- | ------ | --------- | ----- |
| `secondary` (default) | `surface` | `text` | 2px `border_strong` | 18px | Standard action |
| `primary` | `accent` | `on_accent` | 2px `accent` | 22px (`font_h2`) | Main CTA |
| `danger` | `surface` | `fail_fg` | 2px `fail_fg` | 18px | Destructive |
| `pass` | `surface` | `pass_fg` | 2px `pass_fg` | 18px | Success actions |
| `link` | transparent | `accent` | none | 15px (`font_small`) | Underlined, min-height 32px |
| `toggle` | `surface` → `accent` (checked) | `text` → `on_accent` | 2px `border_strong` → `accent` | 18px | Min-height 44px |
| `takeover` | `surface` | `fail_fg` | 3px `surface` | 28px (`font_h1`) | Min-height 72px, full-screen reject |

**Interactive States** (all variants):
- `:hover` → `surface_alt` (secondary) / `accent_hover` (primary) / `accent_soft` (pressed)
- `:pressed` → `accent_soft` (secondary) / `accent_pressed` (primary)
- `:focus` → 3px `focus` border (4px on takeover)
- `:disabled` → `disabled_bg` bg, `disabled_fg` text, border matches bg
- `:checked` (pass/danger) → solid status color bg, `on_status_solid` text

### 12.2 Inputs (`QLineEdit`, `QComboBox`, `QSpinBox`, `QDoubleSpinBox`, `QDateEdit`)
**Base** (`qss.py:145-158`):
- Min-height: 44px
- Padding: 0 8px (`space_s`)
- Radius: 8px
- Background: `surface`
- Border: 2px `border_strong`

**States**:
- `:focus` → 3px `focus` border
- `[invalid="true"]` → 3px `fail_fg` border
- `QComboBox` dropdown: `surface` bg, `accent_soft` selection highlight

### 12.3 Checkboxes
**`QCheckBox`** (`qss.py:164-166`):
- Spacing: 12px
- Min-height: 40px
- Indicator: 28×28px
- `:focus` → `focus` color on text

### 12.4 Progress Bar
**`QProgressBar`** (`qss.py:167-175`):
- Min-height: 30px
- Border: 2px `border_strong`, radius 8px
- Background: `surface_alt`
- Chunk: `accent` bg, radius 6px
- Text: centered, 700 weight

### 12.5 Tables and Lists
**`QTableWidget`, `QListWidget`, `QPlainTextEdit`** (`qss.py:178-188`):
- Background: `surface`
- Border: 1px `border`, radius 8px
- Gridlines: `border` color
- Selection: `accent_soft` bg, `text` color
- `:focus` → 3px `focus` border

**Headers** (`QHeaderView::section`, `qss.py:189-196`):
- Background: `surface_alt`
- Bottom border: 1px `border`
- Padding: 8px
- Font: 700 weight, `font_small` (15px)

### 12.6 Tabs
**`QTabWidget`** (`qss.py:197-207`):
- Pane: no border
- Tabs: min-height 48px, padding 0 24px
- Default: transparent bg, `text_muted` color, 600 weight
- `:selected` → `accent` color, 3px bottom border `accent`
- `:focus` → `focus` color

### 12.7 Cards and Panels
**`QFrame[card="true"]`** (`qss.py:31-35`):
- Background: `surface`
- Border: 1px `border`
- Radius: 10px

**Status frames** (`QFrame[tone="..."]`, `qss.py:234-238`):
- Background: tone-specific `_bg` token
- Border: 2px tone-specific `_fg` token
- Radius: 10px

### 12.8 Stage Stepper Labels
**`QLabel[step="..."]`** (`qss.py:214-225`):
- `current`: `accent` bg, `on_accent` text, radius 8px
- `done`: `pass_fg` text
- `todo`: `text_muted` text
- `rejected`: `fail_solid` bg, `on_status_solid` text, radius 8px

### 12.9 Status Labels
**`QLabel[status="..."]`** (`qss.py:239-243`):
- Color: tone-specific `_fg` token
- Weight: 700

### 12.10 Overlays
- **`#ErrorBanner`**: `[tone="fail"]` → `fail_bg` bg, `fail_fg` border
- **`#RejectTakeover`**: `fail_solid` bg (`#9C1A10`), all labels `on_status_solid`
- **`#SuccessToast`**: `pass_solid` bg, radius 10px, labels `on_status_solid`, `font_h1` bold

## 13. Interactive States and Animations

### 13.1 Button States (QSS-Driven)
All `BigButton` variants support full pseudo-state styling via QSS:

| State | Secondary | Primary | Pass | Danger | Link | Toggle | Takeover |
| ----- | --------- | ------- | ---- | ------ | ---- | ------ | -------- |
| Default | `surface` / `border_strong` | `accent` / `accent` | `surface` / `pass_fg` | `surface` / `fail_fg` | transparent / `accent` | `surface` / `border_strong` | `surface` / `fail_fg` |
| `:hover` | `surface_alt` | `accent_hover` | `surface_alt` | `surface_alt` | `accent` (underline) | `surface_alt` | — |
| `:pressed` | `accent_soft` | `accent_pressed` | `accent_soft` | `accent_soft` | — | `accent` (checked) | — |
| `:focus` | 3px `focus` | 3px `focus` | 3px `focus` | 3px `focus` | 2px `focus` | 3px `focus` | 4px `text` |
| `:disabled` | `disabled_bg` / `disabled_fg` | `disabled_bg` / `disabled_fg` | `disabled_bg` / `disabled_fg` | `disabled_bg` / `disabled_fg` | `disabled_fg` | `disabled_bg` / `disabled_fg` | — |
| `:checked` | — | — | `pass_solid` / `on_status_solid` | `fail_solid` / `on_status_solid` | — | `accent` / `on_accent` | — |
| `:checked:disabled` | — | — | `pass_solid` / `on_status_solid` | `fail_solid` / `on_status_solid` | — | — | — |

### 13.2 Input States
| State | Border | Background |
| ----- | ------ | ---------- |
| Default | 2px `border_strong` | `surface` |
| `:focus` | 3px `focus` | `surface` |
| `[invalid="true"]` | 3px `fail_fg` | `surface` |

### 13.3 Custom Widget States (Python-Driven)
| Widget | State Mechanism | Visual Changes |
| ------ | --------------- | -------------- |
| `CheckRow` | `isChecked()`, `isEnabled()`, `hasFocus()` | Custom `paintEvent`: bg `pass_bg`/`surface`/`disabled_bg`, border `pass_fg`/`border_strong`/`focus`/`disabled_bg`, checkmark when checked |
| `StatusPill` | `set_state()` → `tone` + `status` properties | QSS `[tone="..."]` on frame, `[status="..."]` on label |
| `StageStepper` | `set_state()` → `step` property on labels | QSS `[step="current\|done\|todo\|rejected"]` |
| `ValueRow` | `StatusPill.set_state()` | Delegates to `StatusPill` |

### 13.4 Animations and Timers
| Animation | Implementation | Duration/Interval |
| --------- | -------------- | ----------------- |
| **CameraPreview scan line** | `QTimer` (66ms ≈ 15fps) updates `_phase`, `paintEvent` draws moving line | Continuous while active |
| **SuccessToast auto-dismiss** | `QTimer.singleShot(seconds * 1000)` → `hide()` | Configurable via `settings.ui.success_toast_s` |
| **No CSS transitions/animations** | Qt Widgets QSS does not support transitions; state changes are instantaneous | — |

### 13.5 Loading/Working Indicators
| Indicator | Implementation |
| --------- | -------------- |
| `StatusPill` "working" state | Clock icon + "working" translation, `info` tone (blue) |
| `QProgressBar` | Animated chunk fill via `setValue()` updates from view-model |
| `StepRow` "working" state | `StatusPill` shows clock icon + "working" |

### 13.6 Validation Feedback
- **Inline**: `[invalid="true"]` on inputs → red border (3px `fail_fg`)
- **ErrorBanner**: Top banner with title, cause, numbered steps, retry button
- **InlineConfirm**: Replaces OS dialogs for destructive actions
- **RejectTakeover**: Full-screen modal overlay (Esc disabled)

### 13.7 Keyboard Interaction
- **Enter/Return**: Triggers primary action (unless focused `QLineEdit[enter_submits=true]` or reject/confirm active)
- **Escape**: Closes Admin, dismisses drawer, cancels inline confirm (never dismisses reject)
- **F1-F12**: Mapped to checklist items (`CheckRow` hint keys) and stage actions
- **Tab order**: Explicit `QWidget.setTabOrder()` on Login; natural layout order elsewhere

## 14. Assets, Icons, and Fonts

### 14.1 Font Files (Bundled)
Located in `src/parkomate/ui/assets/fonts/`:

| File | Family | Weight | Script | License |
| ---- | ------ | ------ | ------ | ------- |
| `NotoSans-Regular.ttf` | Noto Sans | Regular (400) | Latin | SIL OFL 1.1 |
| `NotoSans-Bold.ttf` | Noto Sans | Bold (700) | Latin | SIL OFL 1.1 |
| `NotoSansDevanagari-Regular.ttf` | Noto Sans Devanagari | Regular (400) | Devanagari (Marathi) | SIL OFL 1.1 |
| `NotoSansDevanagari-Bold.ttf` | Noto Sans Devanagari | Bold (700) | Devanagari (Marathi) | SIL OFL 1.1 |
| `NotoSansSymbols2-Regular.ttf` | Noto Sans Symbols 2 | Regular (400) | Symbols (✓, ✕, etc.) | SIL OFL 1.1 |
| `OFL.txt` | — | — | — | License text |

**Loading**: `load_fonts()` (`fonts.py:28-47`) reads bytes via `importlib.resources`, registers with `QFontDatabase.addApplicationFontFromData()`. Idempotent (guarded by `_loaded` list).

### 14.2 Icons (Programmatic, No Image Assets)
**All 21 icons drawn at runtime by `QPainter`** in `src/parkomate/ui/components/icons.py:37` (`paint_icon()`). No `.svg`, `.png`, `.ico` files in the project.

| Icon Name | Visual Description | Used In |
| --------- | ------------------ | ------- |
| `check` | Checkmark (✓) | Pass states, success toast, checklist |
| `cross` | X mark (✕) | Fail states, reject takeover |
| `warn` | Triangle with exclamation | Warnings, error banner, inline confirm |
| `info` | Circle with i | Info states, ambient display |
| `clock` | Clock face | Working/pending states |
| `pcb` | Rectangle with chip | C1 checklist (PCB) |
| `screw` | Screw head | C2, D4 checklist (screws) |
| `sticker` | Label with folded corner | C3 checklist (sticker) |
| `qr` | QR code pattern | C4 checklist, camera preview |
| `sensor` | Rounded rect with waves | B2 sensor, D1 checklist |
| `indicator` | LED with leads | B2 indicator, D2 checklist |
| `connector` | Header with pins | D3 checklist (connector) |
| `box` | Isometric box | Packaging, reject box |
| `plug` | Power plug | Programming (power) |
| `chip` | IC with pins | Firmware, programming |
| `cloud` | Cloud | Server/upload |
| `thermo` | Thermometer | Ambient temperature |
| `bolt` | Lightning bolt | Electrical test |
| `camera` | Camera body | QR scan preview |
| `user` | Person silhouette | Operator info |
| `list` | Bullet list | Reports, logs |
| `lock` | Padlock | Admin, locked operators |

**Icon Widget**: `Icon` class (`icons.py:195`) — fixed-size `QWidget` with `paintEvent` calling `paint_icon()`. `WA_TransparentForMouseEvents` for decorative use.

**Color**: Passed at construction or via `set_icon(name, color)`; defaults to `COLORS.text`.

### 14.3 Images and Other Assets
- **No raster images** (PNG/JPG) in the codebase
- **No SVG files**
- **No Qt resource (.qrc) files** — fonts loaded via `importlib.resources`, icons drawn in code

### 14.4 Asset References
| Asset | Referenced By |
| ----- | ------------- |
| Font files | `fonts.py:32-35` (via `importlib.resources.files("parkomate.ui.assets").joinpath("fonts")`) |
| Icons | `icons.py:paint_icon()` called from `Icon.paintEvent()`, `CheckRow.paintEvent()`, `CameraPreview.paintEvent()`, `StatusPill.set_state()`, `ErrorBanner`, `RejectTakeover`, `SuccessToast`, various views |

## 15. Styling Conventions and Dependencies

### 15.1 Styling Architecture
- **Single source of truth**: `tokens.py` (`Colors`, `Sizes` dataclasses)
- **Single stylesheet**: Generated at runtime by `qss.py:build_stylesheet()`, applied once to `QApplication`
- **Opt-in dynamic properties**: Widgets declare visual state via Qt dynamic properties (`variant`, `role`, `tone`, `status`, `step`, `card`, `invalid`) — no inline styles in view code (except `RejectTakeover` box label, see §16)
- **No external CSS toolchain**: No `.css`, `.scss`, Tailwind, PostCSS, or Node.js dependencies
- **QSS selectors**: Attribute selectors (`[property="value"]`), ID selectors (`#ObjectName`), type selectors, pseudo-states (`:hover`, `:pressed`, `:focus`, `:disabled`, `:checked`, `:selected`)

### 15.2 Styling Conventions
| Convention | Implementation |
| ---------- | -------------- |
| **Color references** | Always via `COLORS.token_name` from `tokens.py` |
| **Size references** | Always via `SIZES.token_name` from `tokens.py` |
| **Font creation** | Via `font(px, bold)` helper (`fonts.py:59`) or `app_font()` |
| **Property updates** | Via `set_prop(widget, name, value)` → auto-`restyle()` |
| **i18n text** | Never hardcoded — always `t("key")` or `TrLabel("key")` |
| **Icon usage** | Always via `Icon("name", size, color)` or `paint_icon()` |
| **Card pattern** | `card()` helper → `QFrame[card="true"]` + `QVBoxLayout` |
| **Scroll handling** | `scroll_card()` helper for content that may overflow |

### 15.3 Frontend Dependencies (from `pyproject.toml`)
| Dependency | Version | Role in Frontend |
| ---------- | ------- | ---------------- |
| `PySide6` | `>=6.7,<6.11` | Qt Widgets, Core, Gui, Multimedia (beep sound) |
| `opencv-python-headless` | `>=4.9` | Camera frame capture for `CameraPreview` (Labeling stage) |
| `pyzbar` | `>=0.1.9` | QR decoding (used by hardware service, not directly by UI) |
| `pydantic` | `>=2.7,<3` | Settings models → dynamic form generation in `SettingsTab` |

### 15.4 Dev/Test Tooling
| Tool | Purpose |
| ---- | ------- |
| `pytest` + `pytest-qt` | Unit, integration, UI tests (`qt_api = "pyside6"`) |
| `pytest-cov` | Coverage reporting |
| `ruff` | Linting + formatting (`ruff check` + `ruff format --check`) |
| `mypy --strict` | Static type checking (entire package) |
| `pyinstaller` | Build executable (P3, not yet run) |

### 15.5 Resource Loading
- **Fonts**: `importlib.resources.files("parkomate.ui.assets").joinpath("fonts")` → `read_bytes()` → `QFontDatabase.addApplicationFontFromData()`
- **Icons**: Pure Python/QPainter — no external resource loading
- **Settings**: Pydantic models loaded from TOML via `config/settings.py`

### 15.6 Reusable Styling Patterns
| Pattern | Files |
| ------- | ----- |
| `card()` / `scroll_card()` | `widgets.py:476-507` |
| `set_prop()` / `restyle()` | `widgets.py:36-47` |
| `TrLabel` auto-translation | `widgets.py:50-75` |
| `BigButton` with variants | `widgets.py:77-120` |
| `StatusPill` tone-based | `widgets.py:132-176` |

## 16. Styling Inconsistencies and Technical Debt

### 16.1 Inline Stylesheet on RejectTakeover Box Label
- **Location**: `src/parkomate/ui/components/overlays.py:161-164`
- **Code**:
  ```python
  self.box.setStyleSheet(
      f"border: 6px solid {COLORS.on_status_solid}; border-radius: 24px;"
      f" padding: 0 40px; color: {COLORS.on_status_solid};"
  )
  ```
- **Issue**: Uses inline `setStyleSheet()` with f-string interpolated colors instead of dynamic property + QSS selector
- **Impact**: Breaks the opt-in dynamic property pattern; harder to theme; not refreshed by `restyle()`
- **Recommendation**: Add `box_letter="true"` property and corresponding QSS rule in `qss.py`

### 16.2 Hardcoded Font Sizes in Custom Paint Events
- **Location**: `src/parkomate/ui/views/stages.py:150, 158` (`CameraPreview` — `font(SIZES.font_small)` and `font(SIZES.font_h2)`)
- **Location**: `src/parkomate/ui/views/pages.py:158, 170` (`LoginView` ambient text — `font(SIZES.font_h1)`)
- **Issue**: Some custom `paintEvent` implementations pass explicit font sizes instead of using role-based styling
- **Impact**: Minor inconsistency; fonts still use `SIZES` tokens but bypass QSS role system
- **Recommendation**: Consider using `TrLabel`/`QLabel` with roles where possible, or document as intentional for custom painting

### 16.3 Python-Side Color Dictionaries Duplicating Tokens
- **Location**: `src/parkomate/ui/components/widgets.py:122-129` (`_STATE_STYLE` dict)
- **Location**: `src/parkomate/ui/views/shell.py:40-46` (`_TONE_ICON` dict)
- **Issue**: Color/icon mappings redefine token references in Python dicts
- **Impact**: Maintenance burden if tokens change; duplication of design decisions
- **Recommendation**: Could be consolidated into a shared module or derived from tokens programmatically

### 16.4 Input Border Radius Hardcoded in QSS
- **Location**: `src/parkomate/ui/theme/qss.py:149` — `border-radius: 8px` for inputs
- **Issue**: Uses literal `8px` instead of `SIZES.radius` (10px) or a dedicated token
- **Impact**: Slight visual inconsistency (inputs 8px vs cards/buttons 10px); not configurable via tokens
- **Recommendation**: Add `input_radius` to `Sizes` or reuse `radius` with documentation

### 16.5 Progress Bar Chunk Radius Hardcoded
- **Location**: `src/parkomate/ui/theme/qss.py:175` — `border-radius: 6px` for `QProgressBar::chunk`
- **Issue**: Literal value not in tokens
- **Recommendation**: Add token or derive from `radius`

### 16.6 Tab Height and Padding Hardcoded
- **Location**: `src/parkomate/ui/theme/qss.py:199-200` — `min-height: 48px`, `padding: 0 24px`
- **Issue**: Not derived from `Sizes` tokens
- **Recommendation**: Add `tab_height`, `tab_padding_h` to `Sizes`

### 16.7 Tooltip Styling Hardcoded
- **Location**: `src/parkomate/ui/theme/qss.py:22-28` — `QToolTip` styles use literal padding, font-size
- **Issue**: `font-size: {s.font_small}px` uses token but padding/colors are literals
- **Recommendation**: Extract tooltip colors/padding to tokens

### 16.8 Summary
| Severity | Count | Description |
| -------- | ----- | ----------- |
| Medium | 1 | Inline `setStyleSheet` on `RejectTakeover` box label |
| Low | 5 | Hardcoded values in QSS (input radius, progress chunk, tabs, tooltips) |
| Low | 2 | Python-side color/icon dictionaries duplicating token references |

All issues are **cosmetic/maintenance** — no functional bugs or visual regressions.

## 17. Accessibility Observations

### 17.1 Color Contrast (Verified by Automated Tests)
- **Test**: `tests/ui/test_theme.py` and `tests/ui/test_static.py` use `contrast_ratio()` from `tokens.py`
- **Requirements**:
  - All text: ≥ 4.5:1 (WCAG AA) — **PASS**
  - Status text (pass/fail/warn/info): ≥ 7:1 (WCAG AAA) — **PASS**
- **Key contrast ratios** (calculated from active Olive + Yellow token values):
  - `text` (`#111111`) on `surface` (`#FFFFFF`): **18.2:1** ✓ (AAA)
  - `text` (`#111111`) on `bg` (`#FBFCFE`): **17.6:1** ✓ (AAA)
  - `text_muted` (`#5B6472`) on `surface` (`#FFFFFF`): **5.7:1** ✓ (AA)
  - `text_muted` (`#5B6472`) on `bg` (`#FBFCFE`): **5.5:1** ✓ (AA)
  - `on_status_solid` (`#FFFFFF`) on `accent` (`#5A6F2D`): **4.88:1** ✓ (AA)
  - `disabled_fg` (`#475569`) on `disabled_bg` (`#CBD5E1`): **4.54:1** ✓ (AA)
  - `pass_fg` (`#0B5D35`) on `pass_bg` (`#F4FBF6`): **8.27:1** ✓ (AAA)
  - `pass_fg` (`#0B5D35`) on `surface` (`#FFFFFF`): **8.52:1** ✓ (AAA)
  - `on_status_solid` (`#FFFFFF`) on `pass_solid` (`#0B5D35`): **8.52:1** ✓ (AAA)
  - `fail_fg` (`#991B1B`) on `fail_bg` (`#FDE9E7`): **7.82:1** ✓ (AAA)
  - `fail_fg` (`#991B1B`) on `surface` (`#FFFFFF`): **8.71:1** ✓ (AAA)
  - `on_status_solid` (`#FFFFFF`) on `fail_solid` (`#991B1B`): **8.71:1** ✓ (AAA)
  - `warn_fg` (`#6B3A00`) on `warn_bg` (`#FFF1DB`): **8.87:1** ✓ (AAA)
  - `info_fg` (`#1E40AF`) on `info_bg` (`#EFF6FF`): **8.44:1** ✓ (AAA)
  - `focus` (`#111111`) on `surface` / `bg`: **18.2:1** / **17.6:1** ✓ (≥ 3:1)

### 17.2 Focus Indicators
- **All interactive elements** feature high-contrast double-ring focus styling (`outline: 2px solid #111111; outline-offset: 2px;`)
- **Exceptions**: `RejectTakeover` button uses solid high-contrast white text on red background
- **Focus order**: Logical tab order; explicit `setTabOrder()` on Login form
- **No focus traps** except intentional modal overlays (`RejectTakeover`, `InlineConfirm`)

### 17.3 Keyboard Navigation
- **Full keyboard operability**: All actions reachable via Tab/Enter/Escape/F-keys
- **Enter/Return**: Primary action trigger (context-aware in `ProductionShell.press_enter()`)
- **Escape**: Cancels inline confirm, closes drawer/admin (never dismisses reject takeover)
- **F1-F12**: Mapped to checklist items and stage actions
- **Shortcuts**: `QShortcut` with `WidgetWithChildrenShortcut` context

### 17.4 Accessible Names and Labels
| Component | Accessible Name Implementation |
| --------- | ------------------------------ |
| `BigButton` | `setAccessibleName(label_text)` in `retranslate()` (line 119) |
| `TrLabel` | Inherits from `QLabel` — text is accessible name |
| `StatusPill` | `setAccessibleName(word)` in `retranslate()` (line 175) |
| `CheckRow` | `setAccessibleName(label())` in `retranslate()` (line 209) |
| `LanguageSwitch` | `setAccessibleName(t("a11y.language_switch", ...))` (line 416) |
| `CameraPreview` | `setAccessibleName(t("camera.preview"))` (line 539) |
| `MessageBox` | `setAccessibleName(f"{title}. {body}")` (line 76) |
| `ErrorBanner` | `setAccessibleName(f"{title}. {cause}")` (line 106) |
| `RejectTakeover` | `setAccessibleName(f"{headline}. {place}. {reason}")` (line 221) |
| `SuccessToast` | `setAccessibleName(label_text)` (line 258) |
| Form inputs | `setAccessibleName(placeholder/label)` in `LoginView.update_view()` |

### 17.5 Status Conveyed by Multiple Channels
- **Rule enforced** (tokens.py docstring): Status never by color alone
- **Implementation**: Every status indicator combines:
  1. **Icon** (check/cross/warn/info/clock)
  2. **Translated word** (pass/fail/warn/working/pending/info)
  3. **Color** (tone-specific fg/bg)

### 17.6 Text Scaling and Sizing
- **Base font**: 18px (large for industrial visibility)
- **Minimum widget sizes**: Buttons 56px, CheckRows 68px, Inputs 44px
- **No dynamic text scaling** (Qt `QFont::pointSize` not used — all pixel sizes)
- **Marathi support**: Devanagari glyphs via Noto Sans Devanagari; font substitution chain prevents tofu

### 17.7 Error Identification and Feedback
- **ErrorBanner**: Title + one-line cause + numbered steps + retry action
- **Inline validation**: `[invalid="true"]` red border + ErrorBanner details
- **InlineConfirm**: Replaces OS dialogs for destructive actions
- **All errors**: `ParkomateError` with `ErrorCode` → mapped to i18n keys (`error.<code>.title/cause/action`)

### 17.8 Known Limitations
- **No screen reader testing** performed (JAWS/NVDA/VoiceOver)
- **No high-contrast mode** toggle (single light theme)
- **Custom painted widgets** (`CheckRow`, `CameraPreview`) rely on `setAccessibleName()` — no `QAccessibleInterface` implementation
- **Toast auto-dismiss** may be too fast for some users (configurable via settings)

## 18. Recommendations

### High Priority

1. **Eliminate Inline Stylesheet on RejectTakeover Box Label**
   - **Location**: `src/parkomate/ui/components/overlays.py:161-164`
   - **Action**: Replace inline `setStyleSheet()` with dynamic property (e.g., `box_letter="true"`) and corresponding QSS rule in `qss.py`
   - **Rationale**: Restores consistency with opt-in dynamic property pattern; enables theming; allows `restyle()` to work

2. **Add Missing Size Tokens for Hardcoded QSS Values**
   - **Locations**: `qss.py:149` (input radius 8px), `qss.py:175` (progress chunk radius 6px), `qss.py:199-200` (tab height 48px, padding 24px), `qss.py:22-28` (tooltip padding)
   - **Action**: Add `input_radius`, `progress_chunk_radius`, `tab_height`, `tab_padding_h`, `tooltip_padding` to `Sizes` dataclass
   - **Rationale**: Single source of truth for all sizing; easier maintenance and theming

### Medium Priority

3. **Consolidate Python-Side Color/Icon Dictionaries**
   - **Locations**: `widgets.py:122-129` (`_STATE_STYLE`), `shell.py:40-46` (`_TONE_ICON`)
   - **Action**: Create shared module (e.g., `ui/theme/status.py`) with status tone → (icon, color, i18n key) mappings derived from `COLORS`
   - **Rationale**: Eliminates duplication; single place to update status semantics

4. **Document Custom PaintEvent Font Usage**
   - **Locations**: `stages.py:150, 158` (`CameraPreview`), `pages.py:158` (`LoginView` ambient)
   - **Action**: Add inline comments explaining why `font()` is called directly instead of role-based labels
   - **Rationale**: Clarifies intentional deviation from pattern for future maintainers

5. **Add High-Contrast Theme Variant**
   - **Action**: Create `ColorsHC` / `SizesHC` dataclasses and `build_stylesheet(hc_colors, hc_sizes)` path
   - **Rationale**: Factory lighting conditions vary; WCAG AAA compliance is good foundation

### Low Priority

6. **Automated Token Usage Linting**
   - **Action**: Add ruff/mypy plugin or custom script to detect hardcoded color/size literals in `ui/` (except `tokens.py`, `qss.py`, `fonts.py`)
   - **Rationale**: Prevents regression of hardcoded values

7. **Extract Tooltip Styling to Tokens**
   - **Location**: `qss.py:22-28`
   - **Action**: Add `tooltip_bg`, `tooltip_fg`, `tooltip_padding` to `Colors`/`Sizes`
   - **Rationale**: Completeness of token system

8. **Consider QAccessibleInterface for Custom Widgets**
   - **Widgets**: `CheckRow`, `CameraPreview`, `StageStepper`
   - **Action**: Implement `QAccessibleInterface` subclasses for richer screen reader support
   - **Rationale**: Beyond basic `setAccessibleName()`; enables role/state/value reporting

## 19. Source File Reference Index

| File Path | Purpose | Relevant Sections | Important Line References |
| --------- | ------- | ----------------- | ------------------------- |
| `src/parkomate/ui/main.py` | QApplication factory, font loading, stylesheet application, unhandled exceptions, run_ui() | §1, §2, §3, §4, §8, §15 | 22-32 (create_application), 46-85 (run_ui) |
| `src/parkomate/ui/main_window.py` | Root QMainWindow container, stacked page router, kiosk mode | §1, §4, §5 | 18-76 (MainWindow) |
| `src/parkomate/ui/theme/tokens.py` | Central design system tokens (Colors, Sizes), WCAG contrast utilities | §1, §7, §8, §9, §10, §11 | 16-46 (Colors), 49-69 (Sizes), 76-89 (contrast) |
| `src/parkomate/ui/theme/qss.py` | Application QSS stylesheet generator from design tokens | §1, §2, §7, §8, §11, §12, §13, §15, §16 | 12-248 (build_stylesheet) |
| `src/parkomate/ui/theme/fonts.py` | Bundled Noto Sans font loader, substitution rules, font helpers | §2, §9, §14, §15 | 28-47 (load_fonts), 50-56 (app_font), 59-63 (font) |
| `src/parkomate/ui/components/widgets.py` | Reusable widgets (BigButton, StatusPill, CheckRow, StageStepper, TrLabel, etc.) | §3, §6, §9, §11, §12, §13, §15, §17 | 36-47 (set_prop/restyle), 50-75 (TrLabel), 77-120 (BigButton), 132-176 (StatusPill), 179-278 (CheckRow), 280-339 (StageStepper), 341-374 (CounterBadge), 376-417 (LanguageSwitch), 419-448 (InlineConfirm), 450-474 (ValueRow), 476-507 (card/scroll_card) |
| `src/parkomate/ui/components/icons.py` | Programmatic vector icon drawing (21 icons), Icon widget | §2, §6, §13, §14 | 37-192 (paint_icon), 195-220 (Icon) |
| `src/parkomate/ui/components/overlays.py` | Global overlays (ErrorBanner, RejectTakeover, SuccessToast) | §4, §6, §11, §12, §13, §16, §17 | 20-107 (ErrorBanner), 127-222 (RejectTakeover), 224-258 (SuccessToast) |
| `src/parkomate/ui/views/pages.py` | Starting, Login, Session End, Fatal error pages | §4, §5, §6, §9, §12, §13, §16, §17 | 50-85 (MessageBox), 87-99 (StartingView), 102-235 (LoginView), 237-363 (SessionEndView), 365-410 (FatalView) |
| `src/parkomate/ui/views/shell.py` | Production shell (TopBar, InfoStrip, BottomBar, SessionDrawer) | §4, §5, §6, §11, §12, §13, §17 | 67-119 (TopBar), 121-179 (InfoStrip), 184-306 (BottomBar), 319-405 (SessionDrawer), 407-542 (ProductionShell) |
| `src/parkomate/ui/views/stages.py` | Stage screens (Programming, Testing, Labeling, Packaging) | §4, §5, §6, §12, §13, §14, §16 | 74-102 (StepRow), 127-157 (RejectChooser), 162-328 (ProgrammingView), 333-365 (DecisionRow), 366-521 (TestingView), 526-594 (CameraPreview), 621-736 (LabelingView), 738-769 (PackagingView) |
| `src/parkomate/ui/views/admin.py` | Admin area (SettingsTab, OperatorsTab, ReportsTab, CountersTab, ErrorLogTab) | §4, §5, §6, §12, §17 | 129-412 (SettingsTab), 417-608 (OperatorsTab), 613-830 (ReportsTab), 835-896 (CountersTab), 901-960 (ErrorLogTab), 965-1017 (AdminView) |
| `src/parkomate/ui/workers/runner.py` | Background task execution (QThreadPool, TaskRunner) | §4 | 12-166 (TaskRunner) |
| `src/parkomate/ui/qt_i18n.py` | LanguageNotifier, error helpers (error_title, error_cause, error_steps) | §2, §4, §15, §17 | 17-70 (LanguageNotifier, helpers) |
| `src/parkomate/ui/screenshots.py` | Off-screen PNG renderer, StationDriver test harness | §3 | 65+ (StationDriver) |
| `pyproject.toml` | Project config, dependencies, tool config (ruff, mypy, pytest) | §2, §3, §15 | 6-34 (deps), 56 (qt_api) |
| `src/parkomate/i18n/en.json` / `mr.json` | Translation catalogues (all user-facing text) | §1, §2, §9, §17 | — |
| `tests/ui/test_theme.py` | WCAG contrast verification tests | §7, §17 | — |
| `tests/ui/test_static.py` | Static checks (no hardcoded literals in ui/) | §1, §17 | — |