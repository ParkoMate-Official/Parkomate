# Real-bench tests (hardware in the loop) - Group 2

`tests/hil/` drives the **real** `RealHardwareService` (serial, measuring device, camera,
server) and hands every result to the real `WorkflowEngine`, exactly as the UI does. A plain
`uv run pytest` skips them; they run only on the bench PC.

## Bench setup

| Item | Needed for |
|---|---|
| **Golden board**: a known-good controller PCB, firmware already running, QR sticker applied | every test |
| USB cable to the bench PC (CP210x / CH340 / native USB) | every test |
| Measuring device on the bench network, sending to `measurement.listen_port` from `measurement.allowed_ip` | measurement, golden-board run |
| USB camera at `camera.index` | QR scan, golden-board run |
| Server reachable, API token in the keyring (`secrets set server_api_token`) | `hil_full` only |

## Run

```bat
set PARKOMATE_HIL=1
set PARKOMATE_HIL_PORT=COM5
set PARKOMATE_HIL_SETTINGS=C:\ProgramData\Parkomate\settings.toml
uv run pytest tests/hil -v
```

| Variable | Effect |
|---|---|
| `PARKOMATE_HIL=1` | enables `tests/hil` (otherwise every test there is skipped) |
| `PARKOMATE_HIL_PORT` | serial port of the board (default: first ESP32 USB bridge found) |
| `PARKOMATE_HIL_SETTINGS` | station `settings.toml` with the bench's server / measurement / camera values (default: built-in defaults) |
| `PARKOMATE_HIL_FULL=1` | also runs `hil_full`: whitelist + firmware download + **flashing** the board |
| `PARKOMATE_HIL_UNPLUG=1` | interactive cable-pull test (run with `-s`, pull the cable when asked) |

The tests write only to a scratch database in a temporary folder, never to the station's
data folder. `test_device_id_write_and_read_back` writes a probe ID (`…-HIL`) and restores the
board's original ID afterwards.

## What each test proves

| Test | Group 2 items |
|---|---|
| `test_communication_test` | 22 communication test |
| `test_exactly_n_sensor_readings` | 23 five readings |
| `test_measurement_packet_has_every_value` | 26, 27 values arrive for the voltage / temperature checks |
| `test_qr_scan_matches_id_pattern` | 30, 31 camera + decoder |
| `test_device_id_write_and_read_back` | 32, 34 read / write / read back the device ID |
| `test_golden_board_through_all_stages` | 19-21, 24-29, 33, 35-37, 42: the whole line, gates, limits, identity, COMPLETE |
| `test_unplugged_board_mid_testing_is_handled` | cable pulled → `HW_COM_DISCONNECTED`, nothing recorded as a failure |
| `test_full_line_with_server_and_flashing` (`hil_full`) | stage A for real: whitelist, firmware in RAM, flash + progress, then stage B |

Reject paths (38-41: failure detection, reject box, retry) are covered by the unit tests with
exact edge values (`tests/unit/test_workflow_engine.py`) and by the UI tests on the mock bench
(`tests/ui/test_flow.py`, one test per mock scenario); they need no real board.

## Manual acceptance on the bench (operator view)

Run the station on the real bench (`uv run python -m parkomate`) and tick each line:

- [ ] Good board: A → B → C → D → green "Complete"; next board starts at Programming.
- [ ] Second board cannot start while the first is still on the bench.
- [ ] "Submit and next" stays disabled until every check of the stage is done.
- [ ] Testing: exactly 5 readings shown; sensor and indicator marks; all four values PASS/green.
- [ ] Point C on a bad board (or `limits.v_c_low` raised above the reading) → FAIL/red, "Place
      device in the Testing reject box (B)".
- [ ] Regulator hotter than ambient + 3 °C → FAIL, reject box B; "Re-measure ambient" (F9) works.
- [ ] Labeling: QR scanned; board with a different ID gets the QR ID written and read back.
- [ ] QR sticker covered → "Scan again", nothing rejected.
- [ ] A checklist item marked missing → reject box C (Labeling) or D (Packaging) with that item named.
- [ ] Flash failure (cable pulled at ~40 %) → retry → success → "remove 1 failure?" prompt.
- [ ] Session closed → report lists every device with its stage, checks and reject reason.
