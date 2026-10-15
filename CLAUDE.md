# CLAUDE.md - project memory for Claude Code sessions

## What this is
Parkomate Station: a Windows desktop app (PySide6) for the Parkomate factory. It takes **one
controller PCB (ESP32 + sensor + indicator) at a time** through four mandatory stages:

```
Login → A Programming → B Testing → C Labeling → D Packaging → Complete
                 any failure → REJECTED at that stage → "Place device in the <Stage> reject box (A-D)"
```

* **A Programming** - pick COM port, MAC on server whitelist, firmware from the server (RAM only),
  flash with progress, count success/fail, retry, "remove 1 failure" after a successful retry.
* **B Testing** - ping, exactly N (5) sensor readings, operator marks sensor + indicator OK,
  measuring device JSON: V_A 23.85-24.15, V_B 4.90-5.10, V_C 3.25-3.35, T_reg ≤ ambient + 3 °C.
* **C Labeling** - checklist C1-C4, QR scan, device ID read / write / read-back.
* **D Packaging** - checklist D1-D4 → complete.
* **Repair tab** (top-bar switch *Production | Repair*) - every rejected board opens a repair
  case: write the repair → **Test again** (the whole line A → D again, same MAC) → **Accept**
  (only after a passed retest) or **Scrap** (with a reason). `workflow/repair.py`.
* Data stored locally (SQLite, one database per PC). On session close: report files (Summary,
  Devices, Checks, Rejections, Repairs) + summary e-mail (outbox, retried).
* The measuring device POSTs JSON over Wi-Fi / LAN (format confirmed by the client).
* UI in English and Marathi.

## Owners and folders (one codebase)
| Owner | Folder | Role |
|---|---|---|
| Aditya | `src/parkomate/hardware/` | `HardwareService`: serial, esptool, server API, measuring device (HTTP listener), camera; mocks, bench test, `hybrid.py` (simulated bench + real Wi-Fi device), `measuring_sim.py` (plays the device). |
| Piyush | `src/parkomate/workflow/` | `WorkflowEngine` (state machine, gates, limits, reject/retry) and `RepairService` (repair → retest → accept / scrap). |
| Yugant | everything else | `core/` contracts, `config/`, `data/`, `auth/`, `reports/`, `mail/`, `i18n/`, `logging_setup.py`, `station.py`, `app.py`, `ui/` |

Contracts: `src/parkomate/core/interfaces.py` + `CONTRACTS.md`. Decisions: `DECISIONS.md`
(contract changes are listed at its top - keep doing that).

## Stack
Python 3.12 · uv · PySide6 (Widgets, Fusion, painted components, generated QSS) · SQLite (WAL, FK on, numbered SQL migrations) ·
pydantic v2 · TOML settings (tomllib / tomli-w) · argon2-cffi · keyring · openpyxl ·
smtplib (+ XOAUTH2) · pytest / pytest-qt · ruff · mypy --strict.

## Commands
```bash
uv sync                                       # install (Python 3.12 is fetched by uv)
uv run python -m parkomate --mock             # run the station on the simulated bench
PARKOMATE_MOCK_SCENARIO=v_c_out_of_range uv run python -m parkomate --mock
uv run python -m parkomate --bench-test --firmware-dir firmware\esp32-blink  # real ESP32, local build
uv run python -m parkomate flash --firmware-dir firmware\esp32-blink         # flash once, no screens
uv run python -m parkomate --mock --real-measuring-device   # simulated bench + REAL Wi-Fi measuring device
uv run python -m parkomate measuring-device --to 127.0.0.1  # play the measuring device (Enter / 1-4)
uv run python -m parkomate doctor             # is this PC ready? (OK / WARN / FAIL)
uv run python -m parkomate admin create       # first administrator
uv run pytest                                 # all tests (unit, integration, ui)
uv run pytest --cov=parkomate                 # with coverage
uv run ruff check src tests && uv run ruff format --check src tests
uv run mypy                                   # strict, whole package
uv run python -m parkomate.ui.screenshots --out docs/screenshots   # EN + MR PNGs (guides)
uv run python -m parkomate.ui.screenshots --design --out docs/design/after  # every state, 2 sizes
uv run python -m parkomate --gallery          # every UI component in every state (EN / MR)
uv run python -m parkomate.ui.gallery --out docs/design   # gallery_en.png + gallery_mr.png
powershell -ExecutionPolicy Bypass -File packaging\build.ps1   # program folder + Setup.exe (Inno Setup)
```
Use `PARKOMATE_DATA_DIR=<temp dir>` to keep experiments out of the real data folder.

## Rules that must never be broken
1. **All UI text via i18n.** Every user-facing string comes from `src/parkomate/i18n/en.json`
   and `mr.json` through `t()` / `tr()`; no literals in `ui/` (a test scans for them). Add the
   key to **both** files (parity test) and list new Marathi in `i18n/REVIEW.md`.
2. **Firmware only in RAM.** The BIN lives in a `bytearray` inside the hardware service, never
   on disk, temp files, logs, reports or the DB (only name/version/SHA-256 are stored);
   zeroed on `shutdown()`. Production firmware always comes from the server; only the bench
   test (`--bench-test`, `flash`) *reads* a local test build (`hardware/local_firmware.py`).
3. **Counters are computed from events.** Never store a counter number; append
   `counter_events` (`upload_success`, `upload_failure`, `failure_adjusted`, `reset`) and
   compute. `failure_adjusted` at most once per device, only after failure → success.
4. History tables (`check_results`, `counter_events`, `audit_log`) are append-only (DB triggers).
5. Business rules live in the WorkflowService, not in the UI. Hardware calls never run on the
   GUI thread (use `TaskRunner`).
6. Secrets only in the OS keyring; settings hold `*_ref` names.
7. Errors are `ParkomateError(code=ErrorCode.X)`; the UI shows `error.<x>.title/cause/action`.
8. One primary button per screen, bottom-right; Esc never destroys work; no OS dialogs in the
   normal flow.
9. **UI design system** (`docs/design/DESIGN_SYSTEM.md`): every colour / size / radius / duration
   comes from `ui/theme/tokens.py` - no hex colour, no `px` string and no literal size in a
   layout call outside `ui/theme` (a test scans for them). Screens use only `ui/components/`
   (`Text`/`TrText` for text, `AppButton`, `Card`, ...). Translated texts must reserve the room of
   their longest translation (`set_key`, `reserve`) - switching language must move nothing
   (tested at 1366x768 and 1920x1080). Status = icon + word + colour. Material Symbols icons only.

## Build phases
* **P1 backend (Yugant)** - foundation, DB, records, counters, reports, e-mail, logs, auth,
  settings, i18n, mocks + stub. ✅
* **P2 UX (Yugant)** - every screen on mocks, screenshots, guides. ✅
* **P3 full build** - real `HardwareService` (Aditya), real `WorkflowService` (Piyush),
  composition in `app.py` (`create_hardware`), PyInstaller + Inno Setup installer
  (`packaging/`). Written; real server / board protocol / camera still untried on the bench.
* **Client answers (Oct 2026)** - Repair tab, Wi-Fi measuring device (network allow-list,
  station check, simulator), `doctor`, test e-mail, Repairs report sheet, demo guide
  (`docs/DEMO_GUIDE.md`). See DECISIONS "Client answers" and RP/MW/PK.
