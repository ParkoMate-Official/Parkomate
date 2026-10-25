"""Group 2 on the REAL bench: workflow + testing + QR driven through ``RealHardwareService``.

Requires a golden board (known good, firmware already running, ID sticker on it), the
measuring device on the bench network and the USB camera. Every test calls the hardware the
way the UI does and hands the result to the real :class:`WorkflowEngine`.

The two operator judgements (sensor readings OK, indicator light OK) are submitted as
``True``: the golden board is known good. Skipped unless ``PARKOMATE_HIL=1`` (see conftest).
"""

from __future__ import annotations

import os
import re

import pytest

from parkomate.config.settings import Settings
from parkomate.core.enums import CheckCode, DeviceStatus, IdentityStatus, Stage
from parkomate.core.errors import ErrorCode, HardwareError
from parkomate.core.models import FlashResult
from parkomate.hardware import RealHardwareService
from parkomate.workflow import WorkflowEngine

TEST_ID_SUFFIX = "-HIL"


def _through_programming(wf: WorkflowEngine, hw: RealHardwareService) -> None:
    """Stage A without the server: the golden board already runs the firmware."""
    wf.start_device(hw.read_mac())
    wf.submit_check(CheckCode.A_WHITELIST, True, text="HIL: whitelist skipped")
    wf.submit_check(CheckCode.A_UPLOAD, True, text="HIL: firmware already on board")
    assert wf.submit_and_next().stage is Stage.TESTING


def _testing(wf: WorkflowEngine, hw: RealHardwareService, settings: Settings) -> None:
    assert wf.submit_check(CheckCode.B1_COMM, hw.ping()).passed, "B1: board did not answer"
    for i in range(1, settings.limits.sensor_reading_count + 1):
        wf.submit_check(CheckCode.reading(i), hw.read_sensor().value)
    wf.submit_check(CheckCode.B2_SENSOR_OK, True)
    wf.submit_check(CheckCode.B2_INDICATOR_OK, True)
    outcomes = wf.evaluate_measurement(hw.measure(settings.timeouts.measurement_s))
    failed = [f"{o.check_code.value}={o.value_num}" for o in outcomes if o.passed is False]
    assert not failed, f"B3 out of limits on the golden board: {failed}"
    assert wf.submit_and_next().stage is Stage.LABELING


def _scan(hw: RealHardwareService, settings: Settings) -> str:
    hw.open_camera()
    try:
        qr = hw.read_qr(settings.timeouts.qr_scan_s)
    finally:
        hw.close_camera()
    assert qr is not None, "hold the board's QR sticker in front of the camera"
    return qr


# ------------------------------------------------------------------ single steps


def test_communication_test(connected: RealHardwareService) -> None:
    assert connected.ping() is True


def test_exactly_n_sensor_readings(
    connected: RealHardwareService, bench_settings: Settings
) -> None:
    total = bench_settings.limits.sensor_reading_count
    readings = [connected.read_sensor() for _ in range(total)]
    assert len(readings) == total
    assert all(r.raw for r in readings)


def test_measurement_packet_has_every_value(
    connected: RealHardwareService, bench_settings: Settings
) -> None:
    ambient = connected.measure_ambient()
    measurement = connected.measure(bench_settings.timeouts.measurement_s)
    assert None not in (measurement.v_a, measurement.v_b, measurement.v_c, measurement.t_reg_c)
    assert -10.0 < ambient < 60.0


def test_qr_scan_matches_id_pattern(
    connected: RealHardwareService, bench_settings: Settings
) -> None:
    qr = _scan(connected, bench_settings)
    assert re.fullmatch(bench_settings.camera.id_pattern, qr)


def test_device_id_write_and_read_back(connected: RealHardwareService) -> None:
    original = connected.get_device_id()
    probe = (original or "PKM-000000")[: 32 - len(TEST_ID_SUFFIX)] + TEST_ID_SUFFIX
    try:
        assert connected.set_device_id(probe) is True
        assert connected.get_device_id() == probe
    finally:
        if original:
            assert connected.set_device_id(original) is True
            assert connected.get_device_id() == original


# ------------------------------------------------------------------ whole device


def test_golden_board_through_all_stages(
    bench_workflow: WorkflowEngine, connected: RealHardwareService, bench_settings: Settings
) -> None:
    wf, hw = bench_workflow, connected
    _through_programming(wf, hw)
    _testing(wf, hw, bench_settings)

    qr = _scan(hw, bench_settings)
    assert wf.submit_check(CheckCode.C_QR_READ, qr).passed
    identity = wf.reconcile_identity(qr, hw.get_device_id())
    if identity.status is IdentityStatus.WRITE_REQUIRED:
        readback = hw.get_device_id() if hw.set_device_id(qr) else None
        identity = wf.reconcile_identity(qr, readback, after_write=True)
    assert identity.status in (IdentityStatus.MATCH, IdentityStatus.CONFIRMED)
    for code in (CheckCode.C1, CheckCode.C2, CheckCode.C3, CheckCode.C4):
        wf.submit_check(code, True)
    assert wf.submit_and_next().stage is Stage.PACKAGING
    for code in (CheckCode.D1, CheckCode.D2, CheckCode.D3, CheckCode.D4):
        wf.submit_check(code, True)
    assert wf.submit_and_next().stage is Stage.COMPLETE

    state = wf.current_device()
    assert state is not None and state.status is DeviceStatus.COMPLETE
    assert state.device_id == qr


def test_unplugged_board_mid_testing_is_handled(
    bench_workflow: WorkflowEngine, connected: RealHardwareService
) -> None:
    """Pull the USB cable when asked; the station must raise HW_COM_DISCONNECTED, not crash.

    Interactive: needs ``PARKOMATE_HIL_UNPLUG=1`` and ``pytest -s`` (reads Enter from stdin).
    """
    if not os.environ.get("PARKOMATE_HIL_UNPLUG"):
        pytest.skip("interactive: set PARKOMATE_HIL_UNPLUG=1, run with -s, pull the cable")
    _through_programming(bench_workflow, connected)
    input("Unplug the board's USB cable, then press Enter... ")
    with pytest.raises(HardwareError) as info:
        connected.ping()
    assert info.value.code is ErrorCode.HW_COM_DISCONNECTED
    assert bench_workflow.current_stage() is Stage.TESTING  # nothing recorded as a failure


# ------------------------------------------------------------------ with the server (full)


@pytest.mark.hil_full
def test_full_line_with_server_and_flashing(
    bench_workflow: WorkflowEngine, connected: RealHardwareService, bench_settings: Settings
) -> None:
    wf, hw = bench_workflow, connected
    hw.fetch_firmware()
    info = hw.firmware_info()
    assert info is not None and info.hash_verified
    mac = hw.read_mac()
    wf.start_device(mac)
    assert wf.submit_check(CheckCode.A_WHITELIST, hw.check_whitelist(mac).allowed).passed
    progress: list[int] = []
    result: FlashResult = hw.flash(progress.append)
    outcome = wf.submit_check(CheckCode.A_UPLOAD, result.success, text=info.version)
    assert outcome.passed, f"flash failed: {result.message}"
    assert progress[0] == 0 and progress[-1] == 100 and progress == sorted(progress)
    assert wf.submit_and_next().stage is Stage.TESTING
    _testing(wf, hw, bench_settings)
