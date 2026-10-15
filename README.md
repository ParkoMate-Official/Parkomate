# Parkomate Station

Windows desktop application for the Parkomate production line. It takes one controller PCB
at a time through **A Programming → B Testing → C Labeling → D Packaging**, records every
result locally, rejects failing devices into the right box, lets a technician **repair, test
again, then accept or scrap** faulty boards, and e-mails each person's Excel report when their
session ends. English and Marathi.

> Status: every screen, the workflow, the Repair tab, the reports and e-mail are done and
> tested. The measuring device works over Wi-Fi (real HTTP listener + a simulator that plays
> the device). The real server API, the board's serial protocol and the QR camera are written
> but still untried with the client's production firmware / server. A Windows installer is
> built with `packaging/build.ps1`. **Demo: [docs/DEMO_GUIDE.md](docs/DEMO_GUIDE.md).**

![Testing screen](docs/screenshots/en_09_testing_measured.png)

## Setup

Requirements: Windows 10/11 (Linux/macOS work for development) and
[uv](https://docs.astral.sh/uv/). uv downloads Python 3.12 by itself.

```bash
cd parkomate-station
uv sync                       # creates .venv with all runtime + dev dependencies
uv run python -m parkomate admin create      # first administrator (asks for ID, name, password)
```

## Run

```bash
uv run python -m parkomate --mock            # station on the simulated bench
uv run python -m parkomate --mock --kiosk    # full screen, no window frame
uv run python -m parkomate --mock --scenario v_c_out_of_range
uv run python -m parkomate --gallery         # every UI component in every state (design review)
uv run python -m parkomate --mock --real-measuring-device   # + the REAL Wi-Fi measuring device
uv run python -m parkomate measuring-device --to 127.0.0.1  # play the device (other window/PC)
```

### Measuring device over Wi-Fi

The device POSTs one JSON packet per measurement to `http://<station PC>:8765/measurement`
(the Testing screen shows the address while it waits). Allowed senders:
`measurement.allowed_ip` - one address or a network like `192.168.1.0/24` - and the station PC
itself. A packet whose `station` field names another station is refused, so several stations
can share one Wi-Fi network. `measuring-device` sends good packets (**Enter**) or packets with
one value out of limits (**1-4**) and prints the station's answer.

### Repair tab

Switch **Production | Repair** in the top bar (not while a board is on the line). Every
rejected board is listed with what failed. Write the repair → **Test again** (the board runs the
whole line again; the station checks its MAC) → **Accept** after a passed retest, or **Scrap**
with a reason at any time. Every step goes into that person's session report (Repairs sheet).

The UI follows a small design system - tokens, type scale, components, do / don't:
[`docs/design/DESIGN_SYSTEM.md`](docs/design/DESIGN_SYSTEM.md); what changed in the redesign,
with before / after screenshots: [`docs/design/CHANGES.md`](docs/design/CHANGES.md).

Data folder: `%PROGRAMDATA%\Parkomate` (Windows) or `~/.parkomate`. It holds `settings.toml`,
`parkomate.db`, `logs/`, `reports/`, `outbox/`, `backups/`. Use
`--data-dir <folder>` or `PARKOMATE_DATA_DIR=<folder>` for a scratch station.

A default `settings.toml` is written on first start; every key is documented in
[`config/settings.example.toml`](config/settings.example.toml). An invalid file stops the
station with a page naming each bad key.

### Mock scenarios

Choose with `--scenario`, `PARKOMATE_MOCK_SCENARIO` or `dev.mock_scenario`.
`PARKOMATE_MOCK_DELAY=0` makes the bench instant; `PARKOMATE_MOCK_SEED=7` repeatable.

| Scenario | What happens |
|---|---|
| `all_pass` | every board passes |
| `upload_fails_then_succeeds` | 1st flash fails, retry passes → "remove 1 failure?" prompt |
| `upload_always_fails` | rejected at A after the maximum attempts |
| `whitelist_denied` | server refuses the MAC → rejected at A |
| `com_disconnect_mid_flash` | cable "pulled" at 40 % → "Board not connected" steps → retry |
| `comm_fail` | board does not answer the communication test → rejected at B |
| `v_c_out_of_range` | Point C reads 3.21 V → rejected at B |
| `temp_too_high` | regulator 4.6 °C above ambient → rejected at B |
| `measurement_timeout` | 1st measurement times out → "Measure again" passes |
| `qr_unreadable` | 1st scan sees nothing → "Scan again" passes |
| `id_differs` | board holds a factory ID → QR ID written and confirmed |
| `id_write_fails` | read-back after writing differs → rejected at C |
| `camera_missing` | no camera → "Camera not found" steps |
| `mixed` | a random scenario per board (60 % pass) - realistic demo |

### Bench test - a real ESP32 with a local firmware build

To check flashing on a real board before the Parkomate server is available, the firmware can
come from a folder on this PC instead of the server, for example the Blink test build in
[`firmware/esp32-blink/`](firmware/esp32-blink/README.md). **Real runs keep downloading the
firmware from the server.** The local folder is only read in these two modes:

```powershell
# 1. No screens: read the chip and MAC, flash, show progress (picks the only ESP32 USB port)
uv run python -m parkomate flash --firmware-dir firmware\esp32-blink
uv run python -m parkomate flash --port COM5 --firmware-dir firmware\esp32-blink

# 2. The whole station: the real board is flashed in Programming, the rest is simulated
uv run python -m parkomate --bench-test --firmware-dir firmware\esp32-blink
```

| Part | In the bench test |
|---|---|
| Serial ports, MAC, chip, flashing (esptool) | **real** |
| Firmware | **local folder** (`--firmware-dir`, `PARKOMATE_FIRMWARE_DIR` or `dev.firmware_dir`) |
| Server whitelist, communication test, sensor readings, device ID, measuring device, camera | simulated (the mock scenario still applies) |

* Arduino build folders work as they are: `*.bootloader.bin` → `0x1000`, `*.partitions.bin` →
  `0x8000`, the app `.bin` → `0x10000` (the `programming.*_offset` settings). `*.merged.bin`,
  `.elf` and `.map` are ignored. Without a bootloader and partition table, only the app is written.
* Blink does not speak the station protocol, so the communication test passes when the last
  flash of that board succeeded and it is still plugged in.
* The amber simulation band and chip stay on, so a bench test can never pass for production.
  `--mock` with a `--firmware-dir` shows the local build on the fully simulated bench
  (nothing is flashed).
* Close the Arduino Serial Monitor first, because it holds the port.

### Keyboard shortcuts

| Key | Action |
|---|---|
| **Enter** | the primary (blue, bottom-right) button; also "Device placed in box" and "Yes" on confirmations |
| **Space** | tick / untick the focused checklist row |
| **F1–F4** | tick checklist rows 1–4 (Labeling, Packaging) |
| **F5** | refresh serial ports (Programming, before connecting) |
| **F9** | re-measure ambient temperature |
| **Esc** | cancel a confirmation, close the session panel, leave the admin area - never deletes, rejects or logs out |
| **Tab** | move between controls (visible amber focus ring) |

## Command line

```bash
uv run python -m parkomate settings check            # validate settings.toml
uv run python -m parkomate secrets set smtp_password # store a secret in Windows Credential Manager
uv run python -m parkomate admin unlock OP12
uv run python -m parkomate admin reset-password OP12
uv run python -m parkomate outbox send               # send waiting report e-mails now
uv run python -m parkomate report 12 --format both --out C:\temp
uv run python -m parkomate flash --firmware-dir firmware\esp32-blink   # bench test, see above
uv run python -m parkomate doctor                    # is this PC ready? OK / WARN / FAIL
uv run python -m parkomate measuring-device [--to IP] [--send good|v_a_high|v_b_low|v_c_low|too_hot]
```

## Installer (other PCs)

```powershell
powershell -ExecutionPolicy Bypass -File packaging\build.ps1
```
Runs the tests, builds `dist\ParkomateStation\` with PyInstaller (`ParkomateStation.exe` +
`parkomate.exe` for commands), checks the built program, then makes
`dist\ParkomateStation-Setup-<version>.exe` with Inno Setup 6.3+
(`winget install JRSoftware.InnoSetup`) - or a portable zip when Inno Setup is missing. The
Setup asks each PC's station name and the measuring device address, opens TCP 8765 in the
firewall, keeps `C:\ProgramData\Parkomate` on updates and uninstall.

## Tests and quality

```bash
uv run pytest                          # unit + integration + UI (pytest-qt, off-screen)
uv run pytest --cov=parkomate          # coverage (backend ≈ 97 %, whole package ≈ 91 %)
uv run pytest -m "not slow"            # skip the timing test
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy                            # strict, whole package
uv run python -m parkomate.ui.screenshots --out docs/screenshots   # 26 screens × EN/MR
```

## Documents

| File | For |
|---|---|
| [docs/DEMO_GUIDE.md](docs/DEMO_GUIDE.md) | the end-to-end demo, step by step (one or two PCs, Gmail, real ESP32) |
| [docs/OPERATOR_GUIDE.md](docs/OPERATOR_GUIDE.md) | bench operators (simple words, pictures) |
| [docs/ADMIN_GUIDE.md](docs/ADMIN_GUIDE.md) | supervisors: settings, operators, reports, e-mail |
| [docs/screenshots/](docs/screenshots/) | every screen in English (`en_*`) and Marathi (`mr_*`) |
| [CONTRACTS.md](CONTRACTS.md) | interfaces for Aditya (hardware) and Piyush (workflow) |
| [DECISIONS.md](DECISIONS.md) | every assumption, contract changes, open client questions |
| [CLAUDE.md](CLAUDE.md) | project memory and rules for Claude Code |
| [src/parkomate/i18n/REVIEW.md](src/parkomate/i18n/REVIEW.md) | Marathi texts to be checked by a native speaker |

## Layout

```
src/parkomate/
  core/         shared models, enums, errors, event bus, contracts (interfaces.py)
  config/       settings (pydantic + TOML), secrets (keyring)
  data/         SQLite, migrations/, repositories/, records.py (production API), recovery.py
  auth/         operators, Argon2 passwords, lockout, roles
  reports/      layout.py (THE report layout), Excel/CSV writers, exporter
  mail/         SMTP + OAuth2 mailers, outbox with retry, session reporter
  i18n/         en.json, mr.json, t()/tr()
  hardware/     real service, bench test, hybrid (Wi-Fi device), measuring_sim, mocks/
  workflow/     engine.py (state machine), repair.py (repair → retest → accept / scrap)
  ui/           theme/, components/, viewmodels/, views/, workers/, screenshots.py
  station.py    login / logout / start-up facade      app.py   composition root
  doctor.py     "parkomate doctor" checks
packaging/      PyInstaller spec, Inno Setup script, build.ps1, icon
tests/          unit/, integration/, ui/
```
