# Baseline Report — UI Rebuild (feature/ui-olive-rebuild)

Generated: 2026-10-31

---

## 1. Baseline Test Results

| Suite | Passed | Failed | Total | Duration |
|-------|--------|--------|-------|----------|
| All tests (`pytest`) | 285 | 2 | 287 | 133 s |
| Ruff (`ruff check src tests`) | — | 8 | — | — |
| MyPy (`mypy --strict`) | — | 17 errors (7 files) | — | — |

### Pre-existing Failures (Do Not Fix)

1. **`tests/integration/test_end_to_end.py::test_real_hardware_not_available_yet`** — Placeholder integration test expecting real hardware.
2. **`tests/ui/test_admin.py::test_settings_editor_validates_and_audits`** — Settings editor validation flow changed; test expectation stale.

### Ruff Issues (8 total)

| File | Code | Issue |
|------|------|-------|
| `src/parkomate/data/records.py` | I001, F401 | Import sorting, unused `re` import |
| `src/parkomate/hardware/__init__.py` | I001 | Import sorting |
| `src/parkomate/hardware/camera.py` | B023 | Loop variable binding |
| `src/parkomate/hardware/flasher.py` | RUF100 (×2), E501 | Unused `noqa`, line length |
| `src/parkomate/hardware/measurement.py` | RUF100 | Unused `noqa` |
| `src/parkomate/workflow/engine.py` | E501 | Line length |

These are **outside** the UI layer and not addressed in this rebuild.

### MyPy Errors (17 total, 7 files)

All are in `src/parkomate/hardware/` and `src/parkomate/reports/` — missing stubs for `pyserial`, `esptool`, `pyzbar`, `openpyxl`. No UI code affected.

---

## 2. Screenshot Baseline Render

### Command

```bash
# From repo root, inside parkomate conda env (Python 3.12)
eval "$(conda shell.bash hook)" && conda activate parkomate \
  && python -m parkomate.ui.screenshots --out docs/ui_rebuild/baseline-run --lang en mr
```

### Output: 52 PNGs (26 EN + 26 MR) at 1366×768

Saved to `docs/ui_rebuild/baseline-run/`:

| # | State (EN) | MR counterpart | Description |
|---|------------|----------------|-------------|
| 01 | `en_01_login.png` | `mr_01_login.png` | Login screen, empty |
| 02 | `en_02_login_locked.png` | `mr_02_login_locked.png` | Login screen, account locked |
| 03 | `en_03_ambient.png` | `mr_03_ambient.png` | Ambient temperature reading |
| 04 | `en_04_programming_ready.png` | `mr_04_programming_ready.png` | Stage A: board connected, ready |
| 05 | `en_05_programming_failed_retry.png` | `mr_05_programming_failed_retry.png` | Stage A: upload failure, retry prompt |
| 06 | `en_06_programming_uploading.png` | `mr_06_programming_uploading.png` | Stage A: firmware upload at 52% |
| 07 | `en_07_programming_adjust_prompt.png` | `mr_07_programming_adjust_prompt.png` | Stage A: board connection prompt |
| 08 | `en_08_testing_readings.png` | `mr_08_testing_readings.png` | Stage B: sensor readings in progress |
| 09 | `en_09_testing_measured.png` | `mr_09_testing_measured.png` | Stage B: measurements captured |
| 10 | `en_10_labeling_match.png` | `mr_10_labeling_match.png` | Stage C: QR scanned, matches board ID |
| 11 | `en_11_packaging.png` | `mr_11_packaging.png` | Stage D: packaging checklist |
| 12 | `en_12_success_toast.png` | `mr_12_success_toast.png` | Success toast |
| 13 | `en_13_reject_takeover.png` | `mr_13_reject_takeover.png` | Full-screen reject takeover |
| 14 | `en_14_session_drawer.png` | `mr_14_session_drawer.png` | Slide-out session drawer |
| 15 | `en_15_end_session_confirm.png` | `mr_15_end_session_confirm.png` | End session confirmation |
| 16 | `en_16_session_summary.png` | `mr_16_session_summary.png` | Session summary report |
| 17 | `en_17_labeling_id_written.png` | `mr_17_labeling_id_written.png` | Stage C: ID written confirmation |
| 18 | `en_18_labeling_manual_entry.png` | `mr_18_labeling_manual_entry.png` | Stage C: manual serial entry |
| 19 | `en_19_error_measurement_timeout.png` | `mr_19_error_measurement_timeout.png` | Error banner: measurement timeout |
| 20 | `en_20_error_board_disconnected.png` | `mr_20_error_board_disconnected.png` | Error banner: cable pulled mid-flash |
| 21 | `en_21_admin_settings.png` | `mr_21_admin_settings.png` | Admin: Settings tab |
| 22 | `en_22_admin_operators.png` | `mr_22_admin_operators.png` | Admin: Operators tab |
| 23 | `en_23_admin_reports.png` | `mr_23_admin_reports.png` | Admin: Reports tab |
| 24 | `en_24_admin_counters.png` | `mr_24_admin_counters.png` | Admin: Counters tab |
| 25 | `en_25_admin_error_log.png` | `mr_25_admin_error_log.png` | Admin: Error log tab |
| 26 | `en_26_invalid_settings.png` | `mr_26_invalid_settings.png` | Fatal view: invalid settings |

---

## 3. Additional States StationDriver Can Render

The `StationDriver` in `src/parkomate/ui/screenshots.py` can also capture these states from the plan's "not captured" list:

| State | Method / Scenario | Notes |
|-------|-------------------|-------|
| **StartingView** (ambient init) | `d.c.ambient_result_ms = 60_000` then `d.login()` | Already rendered as `03_ambient` |
| **RejectChooser** (inline "which item failed") | Trigger reject on Stage C/D checklist → `d.c.reject.choosing` | Requires `RejectChooser` to be visible in view |
| **Disabled/invalid input states** | `d.c.login_error = ParkomateError(...)` or `field.setProperty("invalid", True)` | Can be scripted |
| **Admin validation error** | `admin.tabs.setCurrentIndex(0)` then submit invalid settings | Already captured as `26_invalid_settings` via `FatalView` |

### To Render RejectChooser Explicitly

Add to `capture()` in `screenshots.py`:

```python
# --- RejectChooser (Stage C checklist failure)
d = fresh()
d.start()
d.login()
d.through_programming()
d.through_testing()
# Force a reject on C3
d.c.labeling.toggle(CheckCode.C1)
d.c.labeling.toggle(CheckCode.C2)
d.c.labeling.toggle(CheckCode.C3)  # this triggers reject
d.wait(lambda: d.c.reject is not None and d.c.vm.choosing_reject, what="reject chooser")
save(d, "27_reject_chooser")
d.close()
```

### To Render Disabled/Invalid States

```python
# --- Login with invalid COM port (disabled state)
d = fresh()
d.start()
d.c.programming.port_combo.setCurrentIndex(0)  # placeholder
d.c.programming.port_combo.setProperty("invalid", True)
d.process(20)
save(d, "28_programming_port_invalid")
```

---

## 4. Re-run Instructions

```bash
# 1. Activate env
eval "$(conda shell.bash hook)" && conda activate parkomate

# 2. Run tests
python -m pytest --tb=no -q

# 3. Lint (UI only)
python -m ruff check src/parkomate/ui tests/ui

# 4. Type-check (UI only)
python -m mypy src/parkomate/ui --strict

# 5. Render screenshots (baseline or after changes)
python -m parkomate.ui.screenshots --out docs/ui_rebuild/baseline-run --lang en mr

# 6. Compare with before/ (manual diff or `imgdiff` tool)
# diff -r docs/screenshots/ docs/ui_rebuild/baseline-run/
```