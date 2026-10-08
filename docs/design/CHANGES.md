# UI redesign - what changed

Every item of the design review (Part 1), plus the language-switch jump reported on the bench,
with before / after screenshots. `B` = `docs/design/before/`, `A` = `docs/design/after/`
(each in `1366x768/` and `1920x1080/`, `en_` and `mr_`).

## Reported on the bench

**Switching English ↔ मराठी moved the layout.** Cause: QLabel gives each line the height of the
tallest font it uses - Marathi lines (and lines mixing Devanagari with Latin digits such as
"COM4") were 2-3 px taller, and buttons, the stepper, chips and tabs took the width of whatever
text they showed. Fix: `Text` lays out every line in a fixed line box with one baseline for
both scripts; every translated label, button, chip, segment, tab and table header reserves the
width - and a wrapping text the number of lines - of its LONGEST translation; selects and
grid columns are sized independently of their text. Result: nothing moves.
Guarded by `tests/ui/test_redesign.py::test_language_switch_never_moves_the_layout` (every
production screen, the login page and every admin tab, at 1366 x 768 and 1920 x 1080).
Compare `B/1366x768/en_05_programming_failed_retry.png` with `mr_05_…` (stepper, buttons and
card heights differ) and `A/1366x768/en_08_testing_in_progress.png` with `mr_08_…` (identical).

## Global

| Item | What was done | Before → after |
|---|---|---|
| **G1** everything bold | Type scale (Part 2): body Regular, labels Medium, only titles / key values SemiBold-Bold; real Medium + SemiBold faces bundled. | `B/1366x768/en_09_testing_measured.png` → `A/1366x768/en_09_testing_all_pass.png` |
| **G2** focus ring orange/blue, on untouched controls | One style (1 px primary + 3 px halo at 40 %), drawn by one overlay, only after keyboard navigation; nothing focused on load except Operator ID. Tested. | `B/1920x1080/en_21_admin_settings.png` (orange "Back to production") → `A/1920x1080/en_30_admin_settings_empty.png` |
| **G3** nested cards | One level of `Card` on the tinted page; step rows, counters and decision rows are no longer boxed inside cards. | `B/1366x768/en_04_programming_ready.png` → `A/1366x768/en_04_programming_idle.png` |
| **G4** uneven spacing | 4 / 8 grid only (`SPACE`); a test rejects literal sizes in layout calls. | all screens |
| **G5** native widgets leak | Fusion + token palette; custom `Select` (popup, chevron icon), `Switch`, `DateRangePicker` with a styled calendar; thin scroll bars without arrows; tables without grid lines; no group boxes. | `B/1920x1080/en_21_admin_settings.png` → `A/1920x1080/en_30_admin_settings_empty.png` |
| **G6** noisy pills | Pending = small grey clock + word, no fill; only the active step and results are coloured. | `B/1366x768/en_04_programming_ready.png` → `A/1366x768/en_04_programming_idle.png` |
| **G7** mixed glyph icons | Material Symbols Rounded SVGs tinted from tokens; ✓ ✕ removed from all texts (catalogue values updated, keys unchanged). | all screens |
| **G8** space at 1920, cramped at 1366 | Content max 1600 px centred, 12-column grid (5 / 7), numbers 160 px wide with units, port shown as "COM4 · CP210x"; every screen checked at both sizes. | `B/1920x1080/en_04_programming_ready.png` → `A/1920x1080/en_04_programming_idle.png` |

## Top bar / shell

| Item | What was done | Before → after |
|---|---|---|
| **T1** stepper | Numbered circles joined by a line that fills; upcoming / active (halo) / done (tick) / rejected (cross). | `B/1366x768/en_08_testing_readings.png` → `A/1366x768/en_08_testing_in_progress.png` |
| **T2** "SIMULATED · …" looked like an error | Amber 4 px band across the top AND an amber "Simulation mode" chip; scenario in the tooltip. | same |
| **T3** two language buttons | One segmented control with a sliding thumb. | same |
| **T4** big Session / Admin buttons | Account button (initials + name at ≥1600 px) → menu: Session details, Admin (admins only; hidden for operators, disabled with the reason while a board is on the bench), Log out. | same |
| **T5** counters twice + Reset on the operator screen | One counter group (✓ n, ✕ n, Completed n, Rejected n) in the context bar; the Programming counter card is gone; Reset only in Admin → Counters. | `B/1366x768/en_05_programming_failed_retry.png` → `A/1366x768/en_05_programming_fail_attempt_1.png` |
| **T6** cramped grey strip | Context bar 48 px: device chip (ID big, MAC small monospace), operator + code, session timer \| counters. | same |
| **B1** three things compete in the bottom bar | Left: one status (icon + text; in Testing also a progress chip). Right: secondary (Reject = tonal red) + primary; the disabled reason is a caption INSIDE the primary button. | `B/1366x768/en_10_labeling_match.png` → `A/1366x768/en_10_labeling_match.png` |
| **B2** "[Enter]" in the label | Key-cap chip inside the button, right-aligned, 70 % opacity. | all screens |

## Programming

| Item | What was done | Before → after |
|---|---|---|
| **P1** step numbers collide with the stage numbers | Vertical step list: small 28 px dots on a connecting line, state caption on the right. | `B/1366x768/en_04_programming_ready.png` → `A/1366x768/en_04_programming_idle.png` |
| **P2** "0 %" before anything happens | The 8 px bar appears when the upload starts, with "% · time · attempt"; red keeps the % reached, green fills. | `B/1366x768/en_06_programming_uploading.png` → `A/1366x768/en_06_programming_uploading_56.png`, `A/1366x768/en_05_programming_fail_attempt_1.png` |
| **P3** empty Result panel | Result hero: idle (USB badge + "Connect a board to start" + port hint), connecting / checking (spinner), ready, uploading (progress ring), pass (green tick + "Firmware 2.3.1 written"), fail (red cross + hint + attempt dots ● ○ ○). The "Remove 1 failure?" question is an inline banner. | `B/1366x768/en_07_programming_adjust_prompt.png` → `A/1366x768/en_07_programming_pass.png` |
| **P4** truncated port | List rows: port bold + bridge / VID:PID second line; closed: "COM4 · CP210x", full text in the tooltip. | `A/1366x768/en_04_programming_idle.png` |

## Testing

| Item | What was done | Before → after |
|---|---|---|
| **S1** readings 1,2 / 3,4 | Five slots in one row in reading order (index, value, time); empty = dashed; the newest slides in. | `B/1366x768/en_08_testing_readings.png` → `A/1366x768/en_08_testing_in_progress.png` |
| **S2** toggles look disabled | Segmented Success / Failure: outlined neutral; Success = filled green + check; Failure = filled red + cross; not yet = 40 % + lock with the reason. | same |
| **S3** "Still needed: …" | Chip "4 of 12 checks done" + "Next: take reading 4". | same |
| **S4** B3 table | Name · measured (large, tabular) · range bar with the limits under it (same size, secondary) · result chip. | `B/1366x768/en_09_testing_measured.png` → `A/1366x768/en_09_testing_all_pass.png`, `A/1366x768/en_13_testing_one_fail.png` |
| **S5** blue-tinted active card | 2 px accent outline + subtle accent surface; exactly one active card; a failed step is outlined red. | same |

## Labeling / Packaging

| Item | What was done | Before → after |
|---|---|---|
| **L1** tiny "Read:" | "QR code read" label above the ID in large monospace. | `B/1366x768/en_10_labeling_match.png` → `A/1366x768/en_10_labeling_match.png` |
| **L2** ID update invisible | "Before" (struck through, grey) → "Now" + status chip. | `B/1366x768/en_17_labeling_id_written.png` → `A/1366x768/en_18_labeling_updated.png` |
| **L3** camera | 16 px corners, framing corners, moving scan line while searching, green flash + corner pulse when read. | `A/1366x768/en_19_labeling_unreadable_qr.png` |
| **L4** checklist rows | Whole row clickable, 32 px box (radius 8) with an animated tick, icon, "Done", F-key chip. | `A/1366x768/en_10_labeling_match.png` |
| **K1** packaging | Same checklist; right: summary of the device so far; **Complete device** turns green when it can be pressed. | `B/1366x768/en_11_packaging.png` → `A/1366x768/en_11_packaging.png` |

## Overlays and pages

| Item | What was done | Before → after |
|---|---|---|
| **R1** reject takeover | Deeper red with a lighter radial centre; "Reject box" above a 220 px translucent tile; the failed check on a translucent card; fade-in + one-time pulse (off with reduced motion). | `B/1366x768/en_13_reject_takeover.png` → `A/1366x768/en_14_reject_takeover.png` |
| **O1** success toast | Full-width green, slides down, device sentence large, auto-dismiss with a countdown line. | `B/1366x768/en_12_success_toast.png` → `A/1366x768/en_12_success_toast.png` |
| **M1** session summary | KPI tiles (devices, completed, rejected, first-pass yield), rejects by stage as a stacked bar, upload stats, report banner (info / success / warning / error) with the file name, **Open folder**, **Copy path**. | `B/1366x768/en_16_session_summary.png` → `A/1366x768/en_17_session_summary.png` |
| **N1** login | Product mark, 32 px padding, language segmented control (top right), eye inside the password field, version / simulation footer. | `B/1366x768/en_01_login.png` → `A/1366x768/en_01_login.png`, `…_02_login_error`, `…_03_login_locked` |
| **E1** settings problem | Error banner; the human field name first, the key small and monospace; numbered steps. | `B/1366x768/en_26_invalid_settings.png` → `A/1366x768/en_50_settings_problem.png` |

## Admin

| Item | What was done | Before → after |
|---|---|---|
| **A1** black settings background | Root cause: Windows 11 dark mode gives Qt a `#1E1E1E` palette (and white placeholder text); the unstyled scroll viewport used it. The station now always installs the light token palette on Fusion and asks Qt for the light scheme; scroll viewports are transparent. Test: `test_admin_settings_background_is_light` (dark OS palette → light background). | `B/1920x1080/en_21_admin_settings.png` → `A/1920x1080/en_30_admin_settings_empty.png` |
| **A2** group boxes | Section index on the left (scrolls to a section), section cards with a one-line description, two columns from 1600 px, numbers 160 px with units, ranges in one row ("Point A voltage [23.850 V] – [24.150 V]"), "edited" dots, sticky save bar with "n unsaved changes". | same |
| **A3** reports table / export | Operator name + code, numbers right-aligned, columns sized to content and the longest header translation, 48 px rows, hover, sticky header; ONE Export card: scope (selected sessions / date range with a calendar / single device), format (Excel / CSV / Excel + CSV kept), one Export button. | `B/1920x1080/en_23_admin_reports.png` → `A/1920x1080/en_42_admin_reports_data.png` |
| **A4** empty tables | Empty states ("No e-mails waiting", "No errors logged - all good"); severity and outbox status chips; codes in monospace; the details panel only for a selected row. | `B/1920x1080/en_25_admin_error_log.png` → `A/1920x1080/en_34_admin_errors_empty.png`, `en_44_admin_errors_data.png` |
| **A5** counters as text | KPI tiles + "Counting since …"; Reset is tonal red with an inline confirm. | `B/1920x1080/en_24_admin_counters.png` → `A/1920x1080/en_43_admin_counters_data.png` |
| **A6** tabs | 48 px Material tabs, animated indicator, width of the longest translation. | all admin shots |
| **A7** "Back to production" huge primary | Outlined with a back arrow and the Esc key cap. | all admin shots |

## Also fixed on the way

* **Saving Admin settings always failed** (before the redesign: "Settings problem - The settings
  contain an error."): list settings other than the e-mail recipients (the new
  `workflow.retriable_checks`) were sent as text. Every list setting is now split on commas.
  This made `test_settings_editor_validates_and_audits` pass again.
* **Invisible placeholders in dark mode** (white on white) - same root cause as A1.

## Things done differently from the spec (and why)

* **Line heights** are identical in both languages (spec: Marathi +4 px) - otherwise every
  language switch moves the layout, which is exactly what was reported. Values were raised
  where Devanagari needs room (see DESIGN_SYSTEM §3).
* **Colours**: `text_3` darkened to `#636E7F`; green / amber text on their containers uses new
  darker `on_*_cont` tokens - the spec values failed its own AA rule (3.7-3.8:1).
* **Camera radius 16** (L3) rather than the 24 of "camera / hero tiles" in Part 2.
* **Disabled reason inside the primary button** (B1 allowed "under or inside") - it keeps the
  88 px bar vertically centred.
* **Login language switch** in the page's top-right corner, so the card fits 1366 x 768 even
  with the lock-out message.

## Tests changed because the widget structure changed

* `tests/ui/test_flow.py`: the disabled reason is read from `bottom.primary.caption()`
  (was a separate label); the Admin entry is `top.admin_item` in the account menu (was
  `top.admin_button`); the stepper label is `stepper.label(0)` (was `label_for(stage)`).
* `tests/ui/test_admin.py`: Admin is the account-menu item; the Point C field is checked by its
  editor's accessible name (the label now names the range row, "Point C voltage"); result
  messages no longer start with "✓  " / "✕  " (an icon shows the outcome, `property("status")`
  is checked instead); exports go through the one Export card (scope + format + Export);
  the counters tab is checked through its KPI tile.
* `tests/ui/test_static.py`: contrast is checked for every token pair the UI uses.
* New: `tests/ui/test_design_system.py`, `tests/ui/test_redesign.py`.
