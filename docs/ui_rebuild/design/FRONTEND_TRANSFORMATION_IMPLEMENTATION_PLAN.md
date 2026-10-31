# FRONTEND TRANSFORMATION IMPLEMENTATION PLAN

## Change Log

| Revision | Date | Author / Role | Summary of Changes & Rationale |
| :--- | :--- | :--- | :--- |
| **v2.0.0** | 2026-10-31 | Lead UI/UX Systems Architect | **Approved Design Alignment**: Removed all "Proposal A / Proposal B" wording and resolved all open brand decisions in accordance with finalized owner requirements. Shifted brand identity from legacy blue (`#1D4ED8`) to factory-approved Olive (`#5A6F2D`) and decorative yellow (`#B59E2B`). Enforced 2 px four-sided tone borders on accent cards (rejecting thick left bars). Adopted uppercase tracked labels (English only; disabled for Marathi to preserve script integrity). Standardized huge black numbers (`#111111`) for bench metrics and nested olive/sage tint panels (`#F1F4E8`). Integrated ambient temperature directly into Login card. Embedded exact WCAG contrast ratios computed via Python. Verified all source file paths and line numbers against active codebase. Maintained 7 implementation phases. |
| **v1.0.0** | 2026-10-28 | Senior Frontend Engineer | Initial architectural audit, defect catalogue (D1–D17), and preliminary token proposals. |

---

## 1. Executive Summary & Transformation Overview

[DOC] Parkomate Station is a mission-critical Windows desktop application built with PySide6 (Qt Widgets) deployed in high-throughput PCB assembly and flashing benches. The workstation operates across four mandatory manufacturing stages: Stage A (Programming), Stage B (Testing), Stage C (Labeling), and Stage D (Packaging).

[DECIDE] The system owner has reviewed and finalized the brand identity and design language. Blue is strictly deprecated as a primary brand colour. The application identity is established as **Olive + Yellow** (`#5A6F2D` olive primary, `#B59E2B` yellow deco). All previous exploratory alternatives ("Proposal A" and "Proposal B") are superseded.

[DECIDE] The following owner decisions are finalized and classified as **Verified Requirements** (`[DECIDE]`):
1. **Olive + Yellow Identity**: Primary interactive brand surfaces use Olive (`#5A6F2D`). Yellow/gold (`#B59E2B`) is reserved for decorative progress fills, mode warnings, and simulation callouts.
2. **Typography**: Uppercase tracked labels (`letter-spacing: 1px` to `2px`) for English section headers, step categories, and field prompts. Letter-spacing and uppercase transformations are strictly disabled for Marathi (`mr`) to preserve Devanagari headline (*shirorekha*) continuity and legibility.
3. **Data Hierarchy**: Prominent display of huge black numbers (`#111111`, 28–36 px bold) for primary readings (voltages, temperatures, sensor distances, upload counters) to enable at-a-glance visibility from standing bench positions.
4. **Nested Tint Panels**: Secondary data and grouped metrics are housed in rounded nested tint panels (`#F1F4E8` soft olive tint) inside parent white cards.
5. **Card Geometry**: Large rounded card containers (`border-radius: 16px` to `24px`) with clean 1 px borders (`#E4E7EC`) replacing dated 8 px rectangular frames.
6. **Card Tone Accent**: Step cards and status containers use a **2 px FOUR-SIDED border in the tone colour** (e.g., `#0B5D35` for Pass, `#1D4ED8` for Active/Working, `#991B1B` for Reject/Fail), explicitly rejecting one-sided thick left bars.
7. **Status Indicators**: Status badges are pill-shaped (`StatusPill`) combining an icon, text label, and tone colour (`[ICON] + [WORD] + [COLOUR]`) satisfying WCAG 1.4.1 (no colour-only signaling).
8. **Factory Ergonomics**: Touch- and glove-friendly minimum tap targets: 56 px primary buttons, 48 px inputs, and 18 px base body typography.
9. **Reject Takeover**: Full-screen high-urgency red takeover (`#991B1B`) retained for hardware faults and out-of-tolerance rejects, displaying bold box designation and actionable routing instructions.

---

## 2. Frontend Architecture & Technology Stack

[DOC] Parkomate Station runs on Python 3.12 (`pyproject.toml:6`) and PySide6 (Qt 6.7–6.10, `pyproject.toml:9`). 

### 2.1 MVVM Architectural Pattern
- **View Layer (`src/parkomate/ui/views/`)**: Pure presentation components constructed with Qt Widgets (`QWidget`, `QFrame`, `QLabel`, `QPushButton`, `QLineEdit`, `QStackedWidget`). Views bind to ViewModel signals and emit user intentions via commands. Views contain zero business logic and zero hardcoded display literals.
- **ViewModel Layer (`src/parkomate/ui/viewmodels/`)**: Manages UI state machines, input validation, background worker coordination, and device transition guards.
- **Theme & Token Subsystem (`src/parkomate/ui/theme/`)**: Centralized design tokens (`tokens.py:17`), stylesheet generation (`qss.py:12`), and font asset loaders (`fonts.py:28`). Styles are compiled once at application boot (`src/parkomate/ui/main.py:31`).
- **Internationalization Engine (`src/parkomate/ui/qt_i18n.py`)**: Custom reactive i18n layer backed by `en.json` and `mr.json`. A global `LanguageNotifier` emits signals on language toggle, causing all active `TrLabel` and compound widgets to retranslate dynamically.

### 2.2 Framework Constraints & Rendering Model
[INF] PySide6 QSS renders via the native Qt style engine (Breeze/WindowsVista rasterizer). Advanced CSS3 features (such as CSS grid, `backdrop-filter`, or nested CSS variables) are unsupported. Layouts rely on `QVBoxLayout`, `QHBoxLayout`, and `QGridLayout` with fixed size policies and stretch factors. Dynamic state transitions rely on Qt dynamic properties (`setProperty("tone", "pass")`) paired with `style()->unpolish()` / `style()->polish()`.

---

## 3. Project Structure & Directory Layout

[DOC] The UI subsystem is organized modularly under `src/parkomate/ui/`:

```
src/parkomate/ui/
├── __init__.py
├── main.py                  # [DOC] Application entrypoint, font registry, QSS builder application
├── main_window.py           # [DOC] Root QMainWindow, QStackedWidget router, kiosk full-screen logic
├── qt_i18n.py               # [DOC] Reactive LanguageNotifier, translation helpers, error string formatters
├── screenshots.py           # [DOC] Off-screen headless Qt screenshot harness (StationDriver)
├── components/
│   ├── icons.py             # [DOC] Programmatic vector drawing (QPainter path renderer, 21 icons)
│   ├── overlays.py          # [DOC] ErrorBanner, RejectTakeover, SuccessToast global layers
│   └── widgets.py           # [DOC] BigButton, StatusPill, CheckRow, StageStepper, TrLabel, ValueRow
├── theme/
│   ├── fonts.py             # [DOC] Bundled Noto Sans loader and font utility helpers
│   ├── qss.py               # [DOC] QSS stylesheet string generator compiled from design tokens
│   └── tokens.py            # [DOC] Colors and Sizes dataclasses, contrast calculation utilities
├── viewmodels/
│   ├── base.py              # [DOC] Observable ViewModel base class with Signal emitter helpers
│   ├── bridge.py            # [DOC] Hardware event translation bridge to UI signals
│   ├── labeling.py          # [DOC] Stage C ViewModel (barcode/QR verification, checklist gate)
│   ├── programming.py       # [DOC] Stage A ViewModel (ESP32 COM detection, firmware flashing)
│   ├── station.py           # [DOC] StationController orchestrating session, login, and step progression
│   └── testing.py           # [DOC] Stage B ViewModel (electrical measurements, sensor tolerance)
├── views/
│   ├── admin.py             # [DOC] Tabbed supervisor interface (Settings, Operators, Reports, Counters, Logs)
│   ├── pages.py             # [DOC] Top-level stacked pages (LoginView, StartingView, SessionEndView, FatalView)
│   ├── shell.py             # [DOC] ProductionShell (TopBar, InfoStrip, BottomBar, SessionDrawer)
│   └── stages.py            # [DOC] Stage container views (ProgrammingView, TestingView, LabelingView, PackagingView)
└── workers/
    └── runner.py            # [DOC] Background QThreadPool worker execution wrapper (TaskRunner)
```

---

## 4. Screenshot Inventory & Visual Audit

### 4.1 Target Approved Mockups (`design/` / `docs/ui_rebuild/design/`)
[SHOT] High-fidelity target screenshots represent the approved design standard at 2732×1536 resolution (@2x native scale, mapping to 1366×768 @1x):

| Filename | Resolution | Shown Screen / State | Key Visual Elements Visible |
| :--- | :--- | :--- | :--- |
| `Login@2x.png` | 2732×1536 (@2x) | Operator Login (Account Locked State) | Centered rounded white card (24 px radius) on warm tinted background; full-width top simulated mode banner (`#FFF1DB`); tracked uppercase `PRODUCTION STATION`; bold black header `Parkomate Station`; segmented language switch (`English` active in solid olive, `मराठी` inactive outline); nested olive-tinted ambient panel (`#F1F4E8`) with huge `27.1 °C` text and `✓ OK` status pill; double-ring focused input with white gap; soft-red locked banner (`#FDE9E7`) with dark red left accent border; solid olive login button (`#5A6F2D`, 56 px); version text. |
| `Stage A · Programming@2x.png` | 2732×1536 (@2x) | Stage A Flashing (In-Progress Flashing State) | TopBar with black/olive logo, olive pill stepper (`1 Programming`), language switch, Session and Admin buttons; yellow mode strip; white InfoStrip with device MAC and session timer; 2-column workspace; left column has 4 step cards with 2 px four-sided borders (3 green `✓ PASS`, 1 blue `↻ WORKING` with olive-yellow progress bar at 52%); right column has white Result card (`↻ UPLOADING...`), nested olive tint panel (`#F1F4E8`) with huge numbers for `0 UPLOADS ✓`, `1 UPLOADS ✕`, `0 FAILURES REMOVED`, and red outline `Reset counters` button; bottom bar with blue working text and disabled primary button. |
| `Stage B · Testing@2x.png` | 2732×1536 (@2x) | Stage B Hardware Testing (Checks Complete State) | TopBar with completed step checkmark (`✓ Programming`) and active olive pill (`2 Testing`); warm yellow notice banner (`⚠ Earlier reading timed out`); left column with B1 and B2 2 px green-bordered cards, compact inline sensor readings (`157 · 148.6 · 151.2 · 154.6 · 152.9 cm`), two nested-tint decision rows (Sensor readings, Indicator light) with deep green `✓ Success` and neutral `✕ Failure` buttons; right column with B3 Electrical card containing nested olive tint panel (`#F1F4E8`) with 4 huge black voltage/temp values (`24.01 V`, `5.01 V`, `3.31 V`, `28.57 °C`), ambient temp, and `Re-measure [F9]` button; bottom bar with green status message and olive primary button `Submit and next [Enter]`. |

### 4.2 Before Screenshots (`docs/screenshots/` - Current Implementation)
[SHOT] 52 baseline screenshots (1366×768 @1x) documenting English (`en_*.png`) and Marathi (`mr_*.png`) states:

1. `en_01_login.png` / `mr_01_login.png`: Login screen, default empty state.
2. `en_02_login_locked.png` / `mr_02_login_locked.png`: Login screen, locked account error.
3. `en_03_ambient.png` / `mr_03_ambient.png`: StartingView, ambient temp reading.
4. `en_04_programming_ready.png` / `mr_04_programming_ready.png`: Stage A, board connected and ready.
5. `en_05_programming_failed_retry.png` / `mr_05_programming_failed_retry.png`: Stage A, upload failure with retry prompt.
6. `en_06_programming_uploading.png` / `mr_06_programming_uploading.png`: Stage A, firmware upload in progress (52%).
7. `en_07_programming_adjust_prompt.png` / `mr_07_programming_adjust_prompt.png`: Stage A, board connection prompt.
8. `en_08_testing_readings.png` / `mr_08_testing_readings.png`: Stage B, electrical readings in progress.
9. `en_09_testing_measured.png` / `mr_09_testing_measured.png`: Stage B, measurements captured, awaiting verification.
10. `en_10_labeling_match.png` / `mr_10_labeling_match.png`: Stage C, QR code scanned and matched with board ID.
11. `en_11_packaging.png` / `mr_11_packaging.png`: Stage D, final packing checklist.
12. `en_12_success_toast.png` / `mr_12_success_toast.png`: Global success toast notification.
13. `en_13_reject_takeover.png` / `mr_13_reject_takeover.png`: Global full-screen reject takeover overlay.
14. `en_14_session_drawer.png` / `mr_14_session_drawer.png`: Slide-out session statistics drawer.
15. `en_15_end_session_confirm.png` / `mr_15_end_session_confirm.png`: Session termination modal dialog.
16. `en_16_session_summary.png` / `mr_16_session_summary.png`: Post-session production metrics report.
17. `en_17_labeling_id_written.png` / `mr_17_labeling_id_written.png`: Stage C, ID written confirmation.
18. `en_18_labeling_manual_entry.png` / `mr_18_labeling_manual_entry.png`: Stage C, fallback manual serial entry.
19. `en_19_error_measurement_timeout.png` / `mr_19_error_measurement_timeout.png`: Global error banner, multimeter timeout.
20. `en_20_error_board_disconnected.png` / `mr_20_error_board_disconnected.png`: Global error banner, serial disconnection.
21. `en_21_admin_settings.png` / `mr_21_admin_settings.png`: Admin tab, hardware/workflow configuration.
22. `en_22_admin_operators.png` / `mr_22_admin_operators.png`: Admin tab, operator PIN management.
23. `en_23_admin_reports.png` / `mr_23_admin_reports.png`: Admin tab, CSV/Excel export management.
24. `en_24_admin_counters.png` / `mr_24_admin_counters.png`: Admin tab, persistent batch counter configuration.
25. `en_25_admin_error_log.png` / `mr_25_admin_error_log.png`: Admin tab, chronological audit log.
26. `en_26_invalid_settings.png` / `mr_26_invalid_settings.png`: Admin tab, validation error highlight.

### 4.3 Missing-States Inventory
[INF] The following production edge states lack screenshots in both the before and target sets and require state-handling rules:
- Stage A: COM port auto-detection timeout / multi-device conflict modal.
- Stage B: Live voltage fluctuating out-of-spec prior to settling.
- Stage C: Camera feed hardware error / video capture disconnection.
- Stage D: Incomplete checklist attempt triggering inline warning highlight.
- Global: Database corruption recovery view on initial application startup.

---

## 5. Screen Inventory & Defect Analysis

### 5.1 Screen Mapping Matrix (Approved Target vs. Before)

| Target Screen (Approved Design) | Old Screenshot Counterpart | Visible Architectural & Visual Differences |
| :--- | :--- | :--- |
| **Login (`Login@2x.png`)** | `en_01_login.png`, `en_02_login_locked.png` | - Replaced corporate blue button (`#1D4ED8`) with solid brand Olive (`#5A6F2D`).<br>- Integrated nested ambient temperature panel (`#F1F4E8`) directly into Login card with huge `27.1 °C` number and `✓ OK` pill (previously isolated on `en_03_ambient.png`).<br>- Added uppercase tracked category label `PRODUCTION STATION`.<br>- Upgraded card corner radius from 8 px to 24 px.<br>- Added high-visibility double-ring input focus ring with white gap.<br>- Moved simulation mode banner from cramped logo text to full-width warm yellow top banner.<br>- Streamlined Account Locked alert box to soft pink panel with red left accent bar and concise copy. |
| **Stage A Flashing (`Stage A · Programming@2x.png`)** | `en_04_programming_ready.png`, `en_06_programming_uploading.png` | - Stepper converted from blue chevron sequence to standalone olive pill (`1 Programming`) with clean text items.<br>- Replaced COM port QComboBox with clean formatted metadata label (`COM4 · ESP32-D0WD-V3`).<br>- Converted step cards to **2 px four-sided tone borders** (green for pass, blue for active).<br>- Progress bar fill changed from solid blue to warm yellow/gold deco accent (`#B59E2B`).<br>- Upload counters housed in rounded nested tint panel (`#F1F4E8`) with huge numbers (`0`, `1`, `0`) and red outline reset button.<br>- Subtitle and logo refined with olive accent on `Station`. |
| **Stage B Hardware Testing (`Stage B · Testing@2x.png`)** | `en_08_testing_readings.png`, `en_09_testing_measured.png` | - Added top warm amber warning banner (`⚠ Earlier reading timed out`) with thick left bar.<br>- Stepper shows completed stage checkmark (`✓ Programming`).<br>- Step B2 sensor readings condensed from multi-line timestamp table to single inline series (`157 · 148.6 · 151.2 · ...`).<br>- Decision rows styled as nested tint panels (`#F1F4E8`) with high-contrast deep green `✓ Success` and neutral `✕ Failure` buttons.<br>- Electrical readings converted from generic table with individual pills into a nested tint panel featuring huge bold black values (`24.01 V`, `5.01 V`, etc.) and a single card-level `✓ PASS` badge.<br>- Primary button converted from blue to brand Olive (`#5A6F2D`). |

### 5.2 Old Screens with NO Approved Design Counterpart
[INF] The following screens have no approved mockup and must be **derived from the same tokens - no approved mockup**:
1. **StartingView (`en_03_ambient.png`)**: Standalone ambient initialization (now redundant given Login integration, but retained as fallback).
2. **Stage C Labeling (`en_10_labeling_match.png`, `en_17_labeling_id_written.png`, `en_18_labeling_manual_entry.png`)**: Checklist cards, camera preview, manual serial entry.
3. **Stage D Packaging (`en_11_packaging.png`)**: Accessory packaging checklist and device summary.
4. **Global Overlays**:
   - `en_12_success_toast.png` (Success Toast)
   - `en_13_reject_takeover.png` (Reject Takeover)
   - `en_14_session_drawer.png` (Session Drawer)
   - `en_15_end_session_confirm.png` (Modal Confirmation)
   - `en_16_session_summary.png` (Session Summary Report)
   - `en_19_error_measurement_timeout.png` / `en_20_error_board_disconnected.png` (Error Banners)
5. **Admin Views (`en_21_admin_settings.png` – `en_26_invalid_settings.png`)**: Settings, Operators, Reports, Counters, Error Logs.

### 5.3 New Design Screens with NO Old Counterpart
None. All 3 approved designs map directly to existing core functional views (Login, Stage A, Stage B).

### 5.4 Observed Visual Defects Analysis (D1–D17)
[SHOT] Comparison between old implementation screenshots and approved designs reveals 17 distinct visual defects:

- **D1 (Generic Brand Palette)**: UI used default corporate blue (`#1D4ED8`) across buttons, pills, and active tabs. *Status: FIXED in new design (Olive `#5A6F2D` + Yellow `#B59E2B`).*
- **D2 (Weak Input Focus Ring)**: Input focus used a brownish/orange 1 px outline without separation. *Status: FIXED in new design (High-contrast dark ring with clean white gap).*
- **D3 (Cramped Stepper with Carets)**: Stepper relied on `›` characters and lacked completed checkmarks. *Status: FIXED in new design (Olive pill active indicator, clean spacing, `✓ Programming` check).*
- **D4 (Misplaced Simulation Banner)**: Simulation indicator was crammed as small text beneath the logo. *Status: FIXED in new design (Full-width warm yellow `#FFF1DB` top banner).*
- **D5 (Isolated Ambient Reading)**: Operators had to navigate through a separate ambient screen before login. *Status: FIXED in new design (Ambient panel embedded in Login card).*
- **D6 (Lack of Categorical Tracking)**: Section headers lacked tracking, leading to poor visual scan speeds. *Status: FIXED in new design (Uppercase tracked labels for English).*
- **D7 (Small Numeric Data Display)**: Critical factory measurements were rendered in 14 px table text. *Status: FIXED in new design (Huge bold black numbers 28–36 px).*
- **D8 (Absence of Visual Grouping Panels)**: Secondary data sat directly on white cards without containment. *Status: FIXED in new design (Nested olive/sage tint panels `#F1F4E8`).*
- **D9 (Boxy 8 px Card Geometry)**: Card corners felt rigid and dated. *Status: FIXED in new design (Large 16–24 px rounded corners).*
- **D10 (Weak Card Border Hierarchy)**: Step cards lacked clear status distinction. *Status: FIXED in new design (Prominent 2 px four-sided tone borders).*
- **D11 (Monochromatic Progress Bar)**: Flashing progress bar was blue on gray. *Status: FIXED in new design (High-visibility yellow deco `#B59E2B` fill).*
- **D12 (Cluttered Sensor Timestamp Table)**: B2 sensor readings occupied unnecessary vertical space with raw timestamps. *Status: FIXED in new design (Clean inline reading chain).*
- **D13 (Redundant Electrical Status Badges)**: Every voltage row repeated an identical `✓ PASS` pill. *Status: FIXED in new design (Single card-level status pill).*
- **D14 (Low-Contrast Decision Toggle Buttons)**: Pass/Fail decision buttons lacked clear active/inactive visual hierarchy. *Status: FIXED in new design (Solid deep green active vs soft neutral inactive).*
- **D15 (Unstyled Secondary Actions)**: Reset counters button lacked warning outline. *Status: FIXED in new design (Clean dark red outline button).*
- **D16 (Disjointed Header Controls)**: Language and session controls lacked unified geometry. *Status: FIXED in new design (Standardized pill components).*
- **D17 (Inconsistent Alert Banner Hierarchy)**: Error/warning banners had conflicting borders and padding. *Status: FIXED in new design (Consistent left accent bars on tinted backgrounds).*

---

## 6. Component Inventory & Anatomy

[DOC] Core reusable components defined in `src/parkomate/ui/components/widgets.py`:

### 6.1 `BigButton` (`widgets.py:77`)
- **Anatomy**: `QPushButton` subclass with custom painting for focus rings, icons, and keyboard shortcuts.
- **Variants**:
  - `primary`: Olive solid background (`#5A6F2D`), bold white text, 56 px bench height.
  - `secondary`: White background, 1 px border (`#E4E7EC`), dark text, 48–56 px height.
  - `danger_outline`: White background, 2 px red outline (`#991B1B`), red text (`Reset counters`, `Reject device`).
  - `disabled`: Neutral light gray background (`#E2E8F0`), muted text (`#94A3B8`).

### 6.2 `StatusPill` (`widgets.py:132`)
- **Anatomy**: Compact `QFrame` with `QHBoxLayout` holding a 14 px vector `Icon` and `QLabel`. Full capsule radius (`border-radius: 9999px`).
- **Variants**:
  - `pass`: White bg, 1.5 px border (`#0B5D35`), text `#0B5D35` (`✓ PASS` or `✓ OK`).
  - `working`: White bg, 1.5 px border (`#1D4ED8`), text `#1D4ED8` (`↻ WORKING` or `↻ UPLOADING...`).
  - `fail`: White bg, 1.5 px border (`#991B1B`), text `#991B1B` (`✕ FAIL`).
  - `waiting`: White bg, 1.5 px border (`#64748B`), text `#64748B` (`⏱ WAITING`).

### 6.3 Accent-Bordered Step Card (`widgets.py:476`, `card`)
- **Anatomy**: `QFrame` container holding step header, metadata, and status badges.
- **Rule**: [DECIDE] Must use **2 px FOUR-SIDED border in tone colour** (`#0B5D35` pass, `#1D4ED8` active, `#991B1B` fail). Border-radius: 14 px. Background: `#FFFFFF` or soft tone tint.

### 6.4 Nested Tint Panel
- **Anatomy**: Child `QFrame` positioned inside cards for metrics, ambient values, and counters.
- **Styling**: Background `#F1F4E8` (soft olive tint), border `1px solid #E2E8DC` or borderless, border-radius 12 px, padding 16 px.

### 6.5 `StageStepper` (`widgets.py:280`)
- **Anatomy**: Horizontal stepper showing stages 1 to 4. Active stage is an olive capsule pill (`#5A6F2D`, white text). Completed stages show `✓ StageName` in dark green. Inactive stages show plain muted text. No chevron carets.

### 6.6 Input Fields & Focus Ring
- **Anatomy**: `QLineEdit` with 48 px height, 10 px radius, light gray border (`#E4E7EC`). Focus state features a dark outer ring (`#111111`, 2 px) separated from the inner control by a 2 px white gap (`outline: 2px solid #111111; outline-offset: 2px;`).

---

## 7. Complete Color Palette & Token Specifications

[MEAS] Colors extracted from approved design screenshots (`read from screenshot (estimated)`) and verified contrast tokens (`derived by me for contrast`):

### 7.1 Palette Specification

| Token Name | Hex Code | Visual Source & Role | Method |
| :--- | :--- | :--- | :--- |
| `brand_olive` | `#5A6F2D` | Primary brand accent; active stepper, primary buttons, logo accent | Read from screenshot (estimated) |
| `olive_hover` | `#4E6026` | Button hover state | Derived by me for contrast |
| `olive_pressed` | `#3F4E1E` | Button pressed / active state | Derived by me for contrast |
| `olive_soft` | `#F1F4E8` | Nested panel background, ambient tint | Read from screenshot (estimated) |
| `yellow_deco` | `#B59E2B` | Progress bar fill, decorative highlights | Read from screenshot (estimated) |
| `yellow_soft` | `#FFF1DB` | Top simulation banner, warning background | Read from screenshot (estimated) |
| `yellow_dark` | `#8C6D1F` | Simulation banner text, warning header | Derived by me for contrast |
| `bg` | `#FBFCFE` | Window root canvas background | Read from screenshot (estimated) |
| `surface` | `#FFFFFF` | Primary card background, active inputs | Read from screenshot (estimated) |
| `surface_alt` | `#F8FAFC` | Inactive tab background, table alternate row | Read from screenshot (estimated) |
| `surface_tint` | `#F1F4E8` | Nested metric panel background | Read from screenshot (estimated) |
| `border` | `#E4E7EC` | Standard card and container border | Read from screenshot (estimated) |
| `border_strong`| `#111111` | Input focus outer ring, high-contrast borders | Derived by me for contrast |
| `text` | `#111111` | Primary headings, huge numbers, input text | Read from screenshot (estimated) |
| `text_muted` | `#64748B` | Subtitles, helper text, inactive steps | Derived by me for contrast |
| `status_pass` | `#0B5D35` | Pass badges, success buttons, pass borders | Read from screenshot (estimated) |
| `status_pass_soft`|`#F4FBF6`| Pass step card background tint | Read from screenshot (estimated) |
| `status_fail` | `#991B1B` | Reject takeover, fail badges, red outline buttons | Read from screenshot (estimated) |
| `status_fail_soft`|`#FDE9E7`| Locked alert background, error banner tint | Read from screenshot (estimated) |
| `status_warn` | `#D97706` | Warning banner left bar, caution badges | Read from screenshot (estimated) |
| `status_warn_soft`|`#FFF1DB`| Warning banner background tint | Read from screenshot (estimated) |
| `status_info` | `#1D4ED8` | Working/uploading badge, active step border | Read from screenshot (estimated) |
| `status_info_soft`|`#F3F7FE`| Working step card background tint | Read from screenshot (estimated) |

---

## 8. Theme Evolution & Owner Decisions

[DECIDE] All exploratory variations (previously denoted as "Proposal A" and "Proposal B") are formally closed:

1. **Brand Identity Selection**:
   - *Previous Status*: Proposal A (Blue) vs Proposal B (Olive/Yellow).
   - *Final Decision*: **Olive + Yellow Identity Adopted**. Blue is eliminated as a brand color and relegated purely to transient working status indicators.
2. **Card Accent Geometry**:
   - *Previous Status*: Thick left border bar vs 4-sided border.
   - *Final Decision*: **2 px Four-Sided Tone Border Adopted** for all accent-bordered cards. Left thick bars are reserved exclusively for inline alert/warning banners.
3. **Typography & Script Rules**:
   - *Previous Status*: Tracked uppercase on all labels.
   - *Final Decision*: **Tracked uppercase enabled for English; strictly disabled for Marathi** to maintain script integrity.
4. **Data Presentation**:
   - *Previous Status*: Table layout vs Hero numbers.
   - *Final Decision*: **Huge Black Numbers (`#111111`) + Nested Tint Panels (`#F1F4E8`) Adopted**.

---

## 9. Final Token Table & WCAG Contrast Verification

[MEAS] Contrast ratios computed programmatically using the WCAG 2.1 relative luminance formula:
$$\text{Luminance } L = 0.2126 \cdot R + 0.7152 \cdot G + 0.0722 \cdot B$$
$$\text{Contrast Ratio } CR = \frac{L_1 + 0.05}{L_2 + 0.05}$$

### 9.1 Core Design Token & Contrast Verification Matrix

| UI Combination | Foreground | Background | Contrast Ratio | WCAG AA Level | WCAG AAA Level | Compliance Notes |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Primary Body Text** | `#111111` | `#FFFFFF` (Surface) | **18.88:1** | Pass | Pass | Exceeds 7.0:1 AAA standard. |
| **Hero Data on Tint** | `#111111` | `#F1F4E8` (Tint) | **16.95:1** | Pass | Pass | Crystal-clear bench visibility. |
| **Muted Text on Surface** | `#64748B` | `#FFFFFF` (Surface) | **4.76:1** | Pass | Fail | Meets 4.5:1 AA for small text. |
| **Muted Text on Tint** | `#64748B` | `#F1F4E8` (Tint) | **4.27:1** | Pass (Large) | Fail | Use bold weight for labels on tint. |
| **Primary Button Text** | `#FFFFFF` | `#5A6F2D` (Olive) | **5.61:1** | Pass | Fail | Solid AA compliance for 18 px text. |
| **Hover Button Text** | `#FFFFFF` | `#4E6026` (Hover) | **6.94:1** | Pass | Pass (Large) | High-contrast interactive response. |
| **Pressed Button Text** | `#FFFFFF` | `#3F4E1E` (Pressed) | **9.05:1** | Pass | Pass | Exceeds 7.0:1 AAA standard. |
| **Pass Status Badge** | `#0B5D35` | `#FFFFFF` (Surface) | **7.98:1** | Pass | Pass | Exceeds 7.0:1 AAA standard. |
| **Pass Badge on Soft** | `#0B5D35` | `#F4FBF6` (Soft) | **7.59:1** | Pass | Pass | Exceeds 7.0:1 AAA standard. |
| **Fail Status Badge** | `#991B1B` | `#FFFFFF` (Surface) | **8.31:1** | Pass | Pass | Exceeds 7.0:1 AAA standard. |
| **Fail Badge on Soft** | `#991B1B` | `#FDE9E7` (Soft) | **7.12:1** | Pass | Pass | Exceeds 7.0:1 AAA standard. |
| **Info Status Badge** | `#1D4ED8` | `#FFFFFF` (Surface) | **6.70:1** | Pass | Pass (Large) | Exceeds 4.5:1 AA standard. |
| **Yellow Deco Text** | `#111111` | `#B59E2B` (Deco) | **7.09:1** | Pass | Pass | Dark text on progress bar fill. |
| **Warning Header** | `#8C6D1F` | `#FFF1DB` (Soft) | **4.68:1** | Pass | Fail | Derived for warning text legibility. |

---

## 10. Spacing, Elevation & Layout System

[DOC] Layout geometry calibrated for 1366×768 minimum display targets:

### 10.1 Spacing Scale (`Sizes`, `tokens.py:50`)
- `pad_xs`: 4 px (icon-to-text spacing)
- `pad_sm`: 8 px (pill padding, button internal gaps)
- `pad_md`: 16 px (nested panel padding, card content padding)
- `pad_lg`: 24 px (outer screen margins, 2-column gutter)
- `pad_xl`: 32 px (modal card internal padding)

### 10.2 Elevation & Shadows
[INF] Qt Widgets lacks native CSS `box-shadow`. Soft elevation is achieved using:
1. Outer 1 px border `#E4E7EC` defining card boundaries.
2. `QGraphicsDropShadowEffect` with blur radius 16 px, vertical offset 4 px, color `rgba(0, 0, 0, 0.05)` applied exclusively to primary floating cards (Login card, Modal dialogs).
3. Zero shadow on stage content cards to maximize CPU performance on low-spec bench PCs.

---

## 11. Borders, Radii, Shadows & Card Hierarchy

[DECIDE] Standardized structural radii and border tokens:

| Element Type | Border Width & Style | Corner Radius | Background Treatment |
| :--- | :--- | :--- | :--- |
| **Main Card** | 1 px solid `#E4E7EC` | 16 px (24 px for Login) | `#FFFFFF` |
| **Nested Tint Panel** | None or 1 px solid `#E2E8DC` | 12 px | `#F1F4E8` (Soft Olive) |
| **Accent Step Card (Pass)** | **2 px solid `#0B5D35`** | 14 px | `#FFFFFF` or `#F4FBF6` |
| **Accent Step Card (Active)** | **2 px solid `#1D4ED8`** | 14 px | `#FFFFFF` or `#F3F7FE` |
| **Accent Step Card (Fail)** | **2 px solid `#991B1B`** | 14 px | `#FFFFFF` or `#FDE9E7` |
| **Decision Row Panel** | None or 1 px solid `#E2E8DC` | 12 px | `#F1F4E8` |
| **Input Field** | 1 px solid `#E4E7EC` (2 px `#111111` focused) | 10 px | `#FFFFFF` |
| **Primary Button** | None | 10 px | `#5A6F2D` |
| **Status Pill** | 1.5 px solid [Tone Color] | 9999 px (Capsule) | `#FFFFFF` |
| **Warning / Alert Banner** | 4 px solid left bar (`#D97706` / `#991B1B`) | 12 px | `#FFF1DB` / `#FDE9E7` |

---

## 12. Target Screen Specifications: Approved Mockups

### 12.1 Operator Login (`Login@2x.png`)
- **Layout**: Centered card (width 580 px @1x, 1160 px @2x) within full-window canvas.
- **Top Banner**: Full-width `#FFF1DB` bar with brown text `SIMULATED · UPLOAD_FAILS_THEN_SUCCEEDS`.
- **Card Header**:
  - Category label: `PRODUCTION STATION` (`#5A6F2D`, font size 12 px, uppercase tracked).
  - Main Title: `Parkomate Station` (`#111111`, font size 28 px bold).
  - Station subtitle: `Station STATION-01` (`#64748B`, font size 14 px).
  - Language Switcher (Top-right of card): Segmented toggle. `English` button is solid `#5A6F2D` with white text. `मराठी` button is white with 1.5 px border and dark text.
- **Ambient Panel (Nested)**:
  - Background `#F1F4E8`, radius 12 px, padding 16 px.
  - Left: `AMBIENT` tracked label.
  - Center: `27.1 °C` (32 px bold black `#111111`).
  - Right: `StatusPill` with `✓ OK` (`#0B5D35`).
- **Form Controls**:
  - `OPERATOR ID` tracked label + input (48 px height, placeholder `e.g. OP12`). Dark focus ring with white gap.
  - `PASSWORD` tracked label + password input (48 px height) + `Show` button (48 px height, white bg).
- **Error / Alert Banner**:
  - Displayed if locked: `#FDE9E7` background, thick `#991B1B` left border, `⚠ Account locked` title, concise 2-sentence instruction.
- **Primary Action**: `Log in [Enter]` button (56 px height, `#5A6F2D` background, white text, 18 px bold).
- **Footer**: `Version 0.1.0` centered in `#64748B`.

### 12.2 Stage A Programming (`Stage A · Programming@2x.png`)
- **Top Bar**:
  - Logo: `Parkomate` (`#111111`) + `Station` (`#5A6F2D`).
  - Stepper: `1 Programming` in solid olive pill (`#5A6F2D`), stages 2, 3, 4 in neutral muted text.
  - Language switch, `Session` pill button, `Admin` button.
- **Mode Banner**: Warm yellow `#FFF1DB` strip.
- **Info Strip**: `Device 24:6F:28:03:9F:31 · Asha Patil (ADM1) · session 00:00:01` | `Uploads ✓ 1 ✕ 0 · Completed 0 · Rejected 0`.
- **Workspace Layout**: 2 equal columns (gutter 24 px).
  - **Left Column**: 4 Step Cards (vertical stack):
    - Step 1: `STEP 1` label, `Connect board`, `COM4 · ESP32-D0WD-V3`, `✓ PASS` badge. 2 px green border (`#0B5D35`).
    - Step 2: `STEP 2` label, `Device authorised`, `MAC 24:6F:28:03:9F:31`, `✓ PASS` badge. 2 px green border (`#0B5D35`).
    - Step 3: `STEP 3` label, `Firmware ready`, `parkomate-controller.bin v2.3.1 · hash verified`, `✓ PASS` badge. 2 px green border (`#0B5D35`).
    - Step 4: `STEP 4` label, `Upload`, `↻ WORKING` badge. 2 px blue border (`#1D4ED8`).
      - Progress bar: 16 px height, rounded track, `#B59E2B` yellow deco fill, bold `52 %` text.
      - Footer: `Attempt 2 of 3`.
  - **Right Column**:
    - Result Card: `RESULT` tracked label, `↻ UPLOADING...` badge, `Keep the board connected.` text.
    - Upload Counters (Nested Tint Panel): `#F1F4E8` background, 12 px radius. `UPLOAD COUNTERS` tracked label. 3 metric columns with huge numbers: `0` (`UPLOADS ✓`), `1` (`UPLOADS ✕`), `0` (`FAILURES REMOVED`). Right-aligned `Reset counters` button (white bg, 2 px `#991B1B` outline).
- **Bottom Bar**: Left status `↻ Uploading firmware... 52 %` (`#1D4ED8`); right disabled button `Upload firmware [Enter]`.

### 12.3 Stage B Hardware Testing (`Stage B · Testing@2x.png`)
- **Top Bar**: Stepper shows `✓ Programming` in dark green and `2 Testing` in solid olive pill.
- **Notice Banner**: Top left amber banner (`#FFF1DB`, left bar `#D97706`), `⚠ Earlier reading timed out`.
- **Workspace Layout**: 2 equal columns.
  - **Left Column**:
    - B1 Step Card: 2 px green border, `B1`, `Communication`, `Board answers ✓`, `✓ PASS` badge.
    - B2 Step Card: 2 px green border, `B2 · READING 5 OF 5`, `Sensor`, inline values `157 · 148.6 · 151.2 · 154.6 · 152.9 cm`, `✓ PASS` badge.
    - Decision Row 1: Nested tint panel (`#F1F4E8`), `Sensor readings`, subtitle, `✓ Success` (solid `#0B5D35`) and `✕ Failure` (neutral gray).
    - Decision Row 2: Nested tint panel (`#F1F4E8`), `Indicator light`, subtitle, `✓ Success` (solid `#0B5D35`) and `✕ Failure` (neutral gray).
  - **Right Column**:
    - B3 Electrical Card: White card with `B3`, `Electrical`, and single `✓ PASS` badge at top right.
    - Nested Tint Panel: `#F1F4E8` background. 4 rows with labels/ranges on left and **huge bold black numbers** on right:
      - `POINT A` (23.85 – 24.15 V): `24.01 V`
      - `POINT B` (4.90 – 5.10 V): `5.01 V`
      - `POINT C` (3.25 – 3.35 V): `3.31 V`
      - `REGULATOR` (max 30.1 °C): `28.57 °C`
    - Card Bottom: `AMBIENT 27.1 °C` text and `Re-measure [F9]` secondary button.
- **Bottom Bar**: Left text `✓ All checks done – press Submit and next` (`#0B5D35`); right action buttons: `Reject device` (white bg, 2 px red border) and `Submit and next [Enter]` (solid `#5A6F2D`, 56 px).

---

## 13. Target Screen Specifications: Derived Screens (No Approved Mockup)

[INF] For screens lacking mockups, the approved visual language is extrapolated deterministically:

### 13.1 Stage C Labeling (Derived from Tokens)
- **Top Bar Stepper**: `✓ Programming`, `✓ Testing`, `3 Labeling` (Olive Pill), `4 Packaging`.
- **Left Column**: Checklist cards (`CheckRow`). Checked items use solid deep green checkbox (`#0B5D35`), bold label, shortcut hint (`F1`–`F4`). Unchecked items use clean 1.5 px border.
- **Right Column**:
  - Live Camera Preview (`CameraPreview`): 16 px rounded frame, thin border `#E4E7EC`, scan reticle, and green sweep line.
  - Scanned Value Display: Hero typography for `Read: PKM-000519` (28 px bold black).
  - Device Identity Card: Nested olive tint panel (`#F1F4E8`) with `ID in the board`, `ID on the QR sticker`, and `✓ Match ✓` badge (`#0B5D35`).
- **Bottom Bar**: `Reject device` outline button and `Submit and next [Enter]` primary olive button.

### 13.2 Stage D Packaging (Derived from Tokens)
- **Left Column**: Packaging Checklist cards with F-key shortcuts (`F1` Sensor packed, `F2` Indicator packed, `F3` Connectors packed, `F4` Accessories packed).
- **Right Column**: Device summary card. Huge `PKM-000519` heading, device MAC, and green check list for completed stages.
- **Bottom Bar**: `Reject device` outline button and `Complete device [Enter]` primary olive button.

### 13.3 Session Summary & Reports (Derived from Tokens)
- **Session Summary (`en_16_session_summary.png`)**: Replaced blue button with Olive button. Converted metrics grid into a 2-column nested tint panel layout with huge black numbers for totals (`Devices started: 2`, `Completed: 1`, `First-pass yield: 0.0 %`).
- **Session Drawer (`en_14_session_drawer.png`)**: Slide-out white drawer with 1 px left border `#E4E7EC`, ambient panel at top, scrollable device list, and dark red outline button for `End session`.

### 13.4 Admin Area (Derived from Tokens)
- **Tab Navigation**: Tab bar using active olive underline / pill indicator (`#5A6F2D`), replacing legacy blue tab selection.
- **Forms**: 48 px inputs with dark focus ring and white gap; tabular data featuring alternating rows (`#FFFFFF` and `#F8FAFC`).
- **Action Buttons**: `Save settings` (Olive primary `#5A6F2D`), `Undo changes` (Neutral secondary).

---

## 14. Defect Remediation Mapping (D1–D17)

[SHOT] Verification of defect remediation status across implementation stages:

| Defect ID | Defect Description | Status in Target Mockups | Implementation Action Required |
| :--- | :--- | :--- | :--- |
| **D1** | Blue brand identity (`#1D4ED8`) | **FIXED** in Login, Stage A, Stage B | Replace all primary blue tokens with `brand_olive` (`#5A6F2D`) across `tokens.py` and `qss.py`. |
| **D2** | Weak input focus indicator | **FIXED** in Login | Add double focus ring with white gap (`outline: 2px solid #111111; outline-offset: 2px;`) to QSS. |
| **D3** | Cramped stepper with chevron carets | **FIXED** in Stage A, Stage B | Update `StageStepper` widget to render active olive capsule pill and `✓` prefix for completed stages. |
| **D4** | Cramped simulation text under logo | **FIXED** in Login, Stage A, Stage B | Implement full-width `#FFF1DB` mode banner widget at root shell layout. |
| **D5** | Isolated pre-login ambient screen | **FIXED** in Login | Embed nested ambient panel component directly into `LoginView` layout. |
| **D6** | Lack of categorical label tracking | **FIXED** in Login, Stage A, Stage B | Apply `letter-spacing: 1.5px` and `text-transform: uppercase` to English `TrLabel`; guard off for Marathi. |
| **D7** | Small 14 px numeric telemetry | **FIXED** in Stage A, Stage B | Update `ValueRow` and telemetry labels to support `role="hero-number"` (28–36 px bold `#111111`). |
| **D8** | Lack of secondary grouping panels | **FIXED** in Login, Stage A, Stage B | Introduce `nested_panel` QSS role with `#F1F4E8` background and 12 px radius. |
| **D9** | Small 8 px card border-radius | **FIXED** in Login, Stage A, Stage B | Update `SIZES.radius` and card rules to 16 px (24 px for modal/login cards). |
| **D10** | Weak card border hierarchy | **FIXED** in Stage A, Stage B | Implement **2 px four-sided tone border** on `card[tone="..."]` selectors in `qss.py`. |
| **D11** | Solid blue progress bar fill | **FIXED** in Stage A | Set `QProgressBar::chunk` background to `yellow_deco` (`#B59E2B`) in `qss.py`. |
| **D12** | Cluttered sensor reading table | **FIXED** in Stage B | Reformat B2 sensor display in `stages.py:TestingView` into compact inline bulleted series. |
| **D13** | Redundant row-level status pills | **FIXED** in Stage B | Hoist electrical status pill to card header in `TestingView`; remove duplicate row badges. |
| **D14** | Weak decision button distinction | **FIXED** in Stage B | Style `DecisionRow` buttons: deep green solid for Success, neutral outline for Failure. |
| **D15** | Unstyled secondary caution buttons | **FIXED** in Stage A, Stage B | Add `danger_outline` property for `Reset counters` and `Reject device` buttons. |
| **D16** | Disjointed header controls | **FIXED** in Stage A, Stage B | Standardize pill geometry across `LanguageSwitch`, `Session`, and `Admin` header buttons. |
| **D17** | Inconsistent alert banner hierarchy | **FIXED** in Login, Stage B | Standardize `ErrorBanner` and warning callouts with 4 px left accent bar on soft tinted backgrounds. |

---

## 15. Source File Reference Index & Codebase Verification

[DOC] [VERIFY] File paths and line numbers verified against active repository source:

| File Path | Verified Symbols & Roles | Verified Lines | Notes |
| :--- | :--- | :--- | :--- |
| `src/parkomate/ui/theme/tokens.py` | `Colors` dataclass<br>`Sizes` dataclass<br>`contrast_ratio` helper | Line 17<br>Line 50<br>Line 84 | Update brand palette to olive/yellow; add `yellow_deco`, `olive_soft`, `surface_tint`. |
| `src/parkomate/ui/theme/qss.py` | `build_stylesheet` | Line 12 | Inject 2 px 4-sided card borders, double focus ring, progress chunk color, pill styling. |
| `src/parkomate/ui/theme/fonts.py` | `load_fonts`<br>`app_font`<br>`font` | Line 28<br>Line 50<br>Line 52 | Ensure Noto Sans Devanagari supports Marathi without artificial tracking. |
| `src/parkomate/ui/components/widgets.py`| `BigButton`<br>`StatusPill`<br>`CheckRow`<br>`StageStepper`<br>`CounterBadge`<br>`LanguageSwitch`<br>`InlineConfirm`<br>`ValueRow`<br>`card` helper | Line 77<br>Line 132<br>Line 178<br>Line 280<br>Line 341<br>Line 376<br>Line 419<br>Line 450<br>Line 476 | Update button variants, pill capsule radii, stepper checkmarks, and nested panel layouts. |
| `src/parkomate/ui/components/overlays.py`| `ErrorBanner`<br>`RejectTakeover`<br>`SuccessToast` | Line 20<br>Line 127<br>Line 224 | Refactor reject takeover box border to dynamic property; update alert left borders. |
| `src/parkomate/ui/views/pages.py` | `StartingView`<br>`LoginView`<br>`SessionEndView`<br>`FatalView` | Line 87<br>Line 102<br>Line 237<br>Line 365 | Embed nested ambient panel into `LoginView`; update card geometry and button styling. |
| `src/parkomate/ui/views/shell.py` | `TopBar`<br>`InfoStrip`<br>`BottomBar`<br>`SessionDrawer`<br>`ProductionShell` | Line 67<br>Line 121<br>Line 181<br>Line 316<br>Line 407 | Add full-width yellow mode banner; update stepper layout; refine button styles. |
| `src/parkomate/ui/views/stages.py` | `StepRow`<br>`ProgrammingView`<br>`DecisionRow`<br>`TestingView`<br>`CameraPreview`<br>`LabelingView`<br>`PackagingView` | Line 74<br>Line 162<br>Line 333<br>Line 366<br>Line 526<br>Line 621<br>Line 738 | Update step card 2 px borders; inline sensor readings; electrical nested panel with huge numbers. |
| `src/parkomate/ui/views/admin.py` | `SettingsTab`<br>`OperatorsTab`<br>`ReportsTab`<br>`CountersTab`<br>`ErrorLogTab`<br>`AdminView` | Line 129<br>Line 417<br>Line 613<br>Line 835<br>Line 901<br>Line 965 | Update tab styling to olive; apply 48 px inputs with double focus rings. |
| `src/parkomate/ui/main.py` | `create_application`<br>`run_ui` | Line 22<br>Line 46 | Global QApplication instantiation and QSS stylesheet attachment. |
| `src/parkomate/ui/main_window.py` | `MainWindow` | Line 18 | Stacked router and kiosk window frame manager. |

---

## 16. Internationalization (i18n) & Bench Ergonomics

### 16.1 Linguistic & Script Typography Rules
[DECIDE] The workstation supports dual English (`en`) and Marathi (`mr`) operation:
1. **Shirorekha Preservation**: Devanagari script relies on a horizontal upper binding line (*shirorekha*). CSS/QSS `letter-spacing` breaks this line into illegible disconnected graphemes. Tracking is strictly conditioned:
   ```python
   # Evaluated in TrLabel and QSS generators
   tracking_css = "letter-spacing: 1.5px; text-transform: uppercase;" if current_lang == "en" else "letter-spacing: 0px;"
   ```
2. **Text Expansion Budget**: Marathi translations expand by approximately 15% to 25% compared to English. All label containers and button widths must avoid rigid pixel widths and use `sizePolicy(Expanding, Preferred)`.

### 16.2 Factory Bench Physical Ergonomics
[DECIDE] Factory workers operate standing or on elevated bench stools, frequently wearing latex or ESD nitrile gloves:
- **Primary Buttons**: 56 px minimum height (`pad_lg` touch area).
- **Secondary / Input Controls**: 48 px minimum height.
- **Base Body Text**: 18 px (`font_body`), exceeding standard desktop 14 px to ensure legibility from 1 meter distance.
- **Hero Numbers**: 28–36 px bold (`font_hero`), readable at 2 meters under overhead industrial LED lighting.

---

## 17. Accessibility, Contrast & Factory Lighting Compliance

[MEAS] Factory environments present challenging lighting, including high-lux overhead tubes, angled task lamps, and daylight glare:
1. **WCAG AAA Compliance for Primary Data**: All critical telemetry values (`#111111` on `#FFFFFF` and `#F1F4E8`) achieve contrast ratios exceeding **16.9:1** (far above the 7.0:1 AAA threshold).
2. **Double-Ring Focus Indicator**: Essential for keyboard-only bench operators. The dark outer ring (`#111111`) paired with a 2 px white gap guarantees visibility against both light cards and dark backgrounds.
3. **No Colour-Alone Signaling (WCAG 1.4.1)**: Every status change provides three redundant visual channels:
   - Icon (e.g., `✓`, `✕`, `↻`, `⚠`, `⏱`)
   - Text Word (e.g., `PASS`, `FAIL`, `WORKING`, `LOCKED`, `WAITING`)
   - Tone Border / Background Colour

---

## 18. Implementation Roadmap: 7 Phases

The transformation is structured into 7 sequential, non-breaking phases:

### Phase 1: Foundation Tokens & QSS Engine Refactor
- Update `src/parkomate/ui/theme/tokens.py`: Introduce `brand_olive` (`#5A6F2D`), `yellow_deco` (`#B59E2B`), `olive_soft` (`#F1F4E8`), `yellow_soft` (`#FFF1DB`). Deprecate blue as brand primary.
- Update `src/parkomate/ui/theme/qss.py`: Implement 2 px four-sided card borders, double focus ring with white gap, yellow progress chunk, and nested panel styling.
- Verify contrast ratios programmatically via automated tests.

### Phase 2: Component Library Modernization
- Refactor `StatusPill` (`widgets.py`): Implement full capsule radius, 1.5 px tone borders, and icon+word formatting.
- Refactor `BigButton` (`widgets.py`): Implement 56 px bench height, olive primary styling, and danger outline variant.
- Refactor `StageStepper` (`widgets.py`): Implement active olive pill, completed checkmark prefix, and clean spacing.
- Refactor `TrLabel` (`widgets.py`): Enforce uppercase tracking for English while strictly suppressing for Marathi.

### Phase 3: Shell & Global Overlays
- Update `shell.py`: Implement full-width warm yellow mode banner (`#FFF1DB`); style `TopBar` with olive logo accent and pill controls; update `BottomBar` status and action buttons.
- Update `overlays.py`: Refactor `RejectTakeover` box label from inline stylesheet to dynamic property `box_letter="true"`; align `ErrorBanner` left accent bars.

### Phase 4: Operator Login & Ambient Temperature Integration
- Update `pages.py:LoginView`: Embed nested ambient temperature panel (`#F1F4E8`, huge number, `✓ OK` pill) directly into Login card.
- Modernize Login card geometry (24 px radius, 580 px width, tracked labels).
- Update Account Locked alert panel styling and copy.

### Phase 5: Stage A (Programming) & Stage B (Testing) Views
- Update `stages.py:ProgrammingView`: Apply 2 px four-sided tone borders to StepCards; integrate yellow deco progress bar; implement nested upload counters panel with huge black numbers and red outline reset button.
- Update `stages.py:TestingView`: Add top amber warning banner; condense B2 sensor readings to inline series; style decision rows with deep green success toggle; reformat B3 Electrical panel with nested olive tint panel and huge numbers.

### Phase 6: Stage C (Labeling), Stage D (Packaging) & Derived Views
- Update `stages.py:LabelingView`: Apply modern checklist styling, camera preview frame, and hero device identity display.
- Update `stages.py:PackagingView`: Implement packaging checklist cards and stage completion indicators.
- Update `pages.py:SessionEndView`: Reformat session summary metrics into 2-column nested tint panel layout with hero numbers.
- Update `views/admin.py`: Apply olive active tab indicator and double-ring focus inputs.

### Phase 7: Verification, Regression Testing & Screenshot Baseline Regeneration
- Execute static analysis checks (`tests/ui/test_static.py`) ensuring zero hardcoded color or size literals.
- Execute automated UI flow tests (`tests/ui/test_flow.py`) and admin tests (`tests/ui/test_admin.py`).
- Run off-screen headless screenshot renderer (`src/parkomate/ui/screenshots.py`) to generate updated 52-screenshot baseline for visual QA.

---

## 19. Testing, Verification & Screenshot Harness Strategy

[DOC] Testing ensures zero regressions across functionality, static constraints, and visual fidelity:

1. **Static Analysis Enforcement (`tests/ui/test_static.py`)**:
   - Enforces that no hardcoded hex strings, pixel sizes, or untranslated string literals exist in `src/parkomate/ui/views/` or `components/`.
   - All styling must flow exclusively through `tokens.py` and `qss.py`.
2. **WCAG Contrast Regression Test Suite (`tests/ui/test_theme.py`)**:
   - Automated unit tests asserting that all foreground/background token pairs meet minimum 4.5:1 (AA) or 7.0:1 (AAA) contrast ratios.
3. **Headless Screenshot Harness (`src/parkomate/ui/screenshots.py`)**:
   - The `StationDriver` harness executes automated workflows across mock hardware, capturing 26 English and 26 Marathi view states off-screen.
   - Enables pixel-perfect visual regression testing against target mockups.

---

## 20. Risk Mitigation, Regression Prevention & Rollback Strategy

[INF] Key architectural risks and mitigation safeguards:

1. **Risk: Marathi Script Corruption from Tracking**
   - *Mitigation*: QSS font-tracking rules are conditioned strictly on language code. Automated unit tests verify `letter-spacing: 0` when `mr` is active.
2. **Risk: QSS Specificity Clashes with Dynamic Properties**
   - *Mitigation*: Dynamic property selectors (`[tone="pass"]`, `[invalid="true"]`) use strict class-qualified selectors (e.g., `QFrame#step_card[tone="pass"]`). Explicit calls to `widget.style().unpolish()` and `widget.style().polish()` are triggered on state changes.
3. **Risk: Bench Touchscreen Lag on Weak Hardware**
   - *Mitigation*: Complex box shadows are excluded from repetitive list items. Vector icons are drawn with cached `QPainterPath` primitives in `icons.py`.
4. **Rollback Mechanism**:
   - All token modifications are isolated in `tokens.py` and `qss.py`. A rollback flag or git revert restores legacy blue stylesheets in seconds without altering database schemas or workflow engines.

---

## 21. Performance & Hardware Bench Constraints

[DOC] Factory bench PCs typically run embedded Intel Core i3 or Celeron processors with integrated graphics:
- **Memory Footprint**: Target idle UI memory under 120 MB RAM.
- **CPU Ceiling**: Steady-state CPU usage under 3% during active stage monitoring.
- **Frame Rate**: Camera preview locked to 15 FPS (`QTimer` interval 66 ms) to prevent thread starvation on the USB serial flasher.
- **Garbage Collection**: Reusable `QPainterPath` and `QPen` objects cached to eliminate allocations inside `paintEvent`.

---

## 22. Documentation & Operator Training Plan

[DOC] Handoff and training materials:
1. **Operator Visual Reference Guide**: Update `docs/OPERATOR_GUIDE.md` with new olive+yellow screen diagrams, highlighting the new ambient reading on the login screen and the simplified inline sensor readings.
2. **Supervisor Configuration Handbook**: Update `docs/ADMIN_GUIDE.md` detailing the revised Admin tab styling and error log filters.
3. **Bench Quick Reference Placard**: Physical laminated 1-page bench cards illustrating status pill meanings and keyboard shortcuts (`Enter`, `Esc`, `F1`–`F4`, `F9`).

---

## 23. Open Decisions, Unreadable Values & Technical Debts

### 23.1 Values That Cannot Be Read From Screenshots
[SHOT] The following parameters cannot be read directly from static screenshot pixels and have been derived or noted for supervisor confirmation:
1. **Button Hover & Pressed Hues**: Target mockups show static resting and disabled states. Hover (`#4E6026`) and pressed (`#3F4E1E`) shades have been mathematically derived for contrast.
2. **Figma Font Family**: Mockups display clean sans-serif typography resembling Noto Sans or Inter. The implementation uses the repository's bundled Noto Sans family.
3. **Exact Drop Shadow Opacity**: Soft card elevation opacity estimated at 5% blur radius 16 px; QSS relies on clean borders.
4. **Derived Stage C & Stage D Mockups**: Approved designs exist only for Login, Stage A, and Stage B. Layouts for Stage C, Stage D, Admin tabs, and Summary reports are derived from tokens without dedicated approved mockups.

### 23.2 Known Technical Debts to Resolve
[DOC] Identified in codebase audit:
1. Inline `setStyleSheet()` on `RejectTakeover` box label (`overlays.py:161`) must be converted to `box_letter="true"` dynamic property.
2. Input border radius hardcoded in `qss.py:149` (8 px) should be mapped to `Sizes.radius` (10 px).
3. Tab height and padding hardcoded in `qss.py:199` should be extracted to `Sizes.tab_height` (48 px) and `Sizes.tab_padding_h` (24 px).

---

## 24. Sign-off, Governance & Revision History

### 24.1 Stakeholder Approvals

| Stakeholder Role | Name / Title | Decision Authority | Sign-off Status |
| :--- | :--- | :--- | :--- |
| **Product Owner** | System Owner / Lead | Visual Identity, Brand Tone, Feature Scope | **APPROVED** (Olive + Yellow Identity Finalized) |
| **Manufacturing Lead** | Factory Bench Supervisor | Ergonomics, Key Shortcuts, Rejection Routing | **APPROVED** (56 px Buttons, 48 px Inputs Finalized) |
| **Lead UI Architect** | Senior Desktop Engineer | MVVM Architecture, QSS System, WCAG Verification | **APPROVED** (24-Section Implementation Plan Aligned) |

### 24.2 Revision Records
- **Version 1.0.0 (2026-10-28)**: Initial baseline audit, proposal documentation, and defect logging.
- **Version 2.0.0 (2026-10-31)**: Comprehensive alignment with approved design mockups (`Login@2x.png`, `Stage A · Programming@2x.png`, `Stage B · Testing@2x.png`), finalization of owner decisions, elimination of exploratory proposals, and verification of codebase line numbers.
