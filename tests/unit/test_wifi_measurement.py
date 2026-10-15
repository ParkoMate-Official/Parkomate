"""The measuring device over Wi-Fi: the real HTTP listener, the simulator that plays the device,
the simulated bench with the real device on top, and ``parkomate doctor``."""

from __future__ import annotations

import random
import socket
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest

from parkomate.app_paths import AppPaths
from parkomate.config.manager import validate_settings
from parkomate.config.secrets import MemorySecretStore
from parkomate.config.settings import Settings
from parkomate.core.errors import ErrorCode, MeasurementError
from parkomate.doctor import Level, run_checks
from parkomate.hardware.hybrid import RealMeasuringDevice
from parkomate.hardware.measurement import HttpMeasurementListener, ip_allowed
from parkomate.hardware.measuring_sim import PRESETS, make_packet, send_packet, station_url
from parkomate.hardware.mocks import MockHardwareService, MockScenario
from parkomate.workflow.validation import measurement_verdicts


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def settings_for(port: int, **measurement: object) -> Settings:
    data: dict[str, object] = {
        "listen_host": "127.0.0.1",
        "listen_port": port,
        "allowed_ip": "127.0.0.1",
        **measurement,
    }
    return validate_settings({"station": {"station_id": "STATION-01"}, "measurement": data})


@pytest.fixture
def port() -> int:
    return free_port()


@pytest.fixture
def listener(port: int) -> Iterator[HttpMeasurementListener]:
    current = {"settings": settings_for(port)}
    item = HttpMeasurementListener(lambda: current["settings"])
    item.current = current  # type: ignore[attr-defined]  # tests change settings live
    yield item
    item.stop()


def url(port: int) -> str:
    return station_url("127.0.0.1", port, "/measurement")


def measure_while_sending(
    listener: HttpMeasurementListener, port: int, packet: dict[str, object]
) -> tuple[object, int]:
    """Open a listening window and send ``packet`` into it from another thread."""
    listener.start()
    replies: list[int] = []

    def send() -> None:
        threading.Event().wait(0.2)
        replies.append(send_packet(url(port), packet).status)

    sender = threading.Thread(target=send)
    sender.start()
    try:
        result: object = listener.measure(5.0)
    except MeasurementError as exc:
        result = exc
    sender.join()
    return result, replies[0]


# ------------------------------------------------------------------ settings and addresses


@pytest.mark.parametrize(
    ("client", "allowed", "ok"),
    [
        ("192.168.1.50", "192.168.1.50", True),
        ("192.168.1.51", "192.168.1.50", False),
        ("192.168.1.77", "192.168.1.0/24", True),
        ("192.168.2.77", "192.168.1.0/24", False),
        ("::ffff:192.168.1.77", "192.168.1.0/24", True),
        ("not-an-ip", "192.168.1.0/24", False),
        ("127.0.0.1", "192.168.1.50", True),  # this PC itself (simulator next to the station)
        ("::1", "192.168.1.50", True),
    ],
)
def test_ip_allowed(client: str, allowed: str, ok: bool) -> None:
    assert ip_allowed(client, allowed) is ok


def test_allowed_ip_accepts_a_network_but_not_rubbish() -> None:
    assert validate_settings({"measurement": {"allowed_ip": "10.0.0.0/8"}}).measurement
    with pytest.raises(Exception, match="allowed_ip"):
        validate_settings({"measurement": {"allowed_ip": "10.0.0.0/99"}})


# ------------------------------------------------------------------ the listener


def test_packet_in_the_window_is_used(listener: HttpMeasurementListener, port: int) -> None:
    packet = make_packet("good", station="STATION-01", seq=1, rng=random.Random(1))
    result, status = measure_while_sending(listener, port, packet)
    assert status == 200
    assert not isinstance(result, MeasurementError)
    assert result.v_c == packet["v_c"] and result.seq == 1  # type: ignore[attr-defined]


def test_packet_outside_a_window_is_ignored(listener: HttpMeasurementListener, port: int) -> None:
    listener.start()
    packet = make_packet("good", station="STATION-01", seq=1)
    assert send_packet(url(port), packet).status == 202


def test_another_station_is_refused(listener: HttpMeasurementListener, port: int) -> None:
    listener.start()
    packet = make_packet("good", station="STATION-02", seq=1)
    result = send_packet(url(port), packet)
    assert result.status == 409 and "STATION-01" in result.message
    packet["station"] = "station-01"  # names are compared without case
    _measured, status = measure_while_sending(listener, port, packet)
    assert status == 200
    listener.current["settings"] = settings_for(port, check_station=False)  # type: ignore[attr-defined]
    assert send_packet(url(port), make_packet("good", station="X", seq=2)).status == 202


def test_wrong_sender_and_bad_json(
    listener: HttpMeasurementListener, port: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    import parkomate.hardware.measurement as measurement

    monkeypatch.setattr(measurement, "ip_allowed", lambda _client, _allowed: False)
    listener.start()
    assert send_packet(url(port), make_packet("good", station="STATION-01", seq=1)).status == 403
    monkeypatch.undo()
    result, status = measure_while_sending(listener, port, {"v_a": "lots"})
    assert status == 400
    assert isinstance(result, MeasurementError) and result.code is ErrorCode.MEAS_BAD_DATA


def test_nothing_in_time_is_a_timeout(listener: HttpMeasurementListener) -> None:
    with pytest.raises(MeasurementError) as info:
        listener.measure(0.2)
    assert info.value.code is ErrorCode.MEAS_TIMEOUT


def test_listen_urls_name_this_pc(port: int) -> None:
    listener = HttpMeasurementListener(lambda: settings_for(port))
    assert listener.listen_urls() == [f"http://127.0.0.1:{port}/measurement"]
    everywhere = HttpMeasurementListener(lambda: settings_for(port, listen_host="0.0.0.0"))  # noqa: S104
    assert all(u.endswith(f":{port}/measurement") for u in everywhere.listen_urls())


# ------------------------------------------------------------------ the simulator


@pytest.mark.parametrize("preset", PRESETS)
def test_presets_fail_exactly_what_they_say(preset: str) -> None:
    packet = make_packet(preset, station="S", seq=3, rng=random.Random(7))
    assert set(packet) == {"station", "seq", "ts", "v_a", "v_b", "v_c", "t_reg_c", "t_amb_c"}
    from datetime import UTC, datetime

    from parkomate.core.models import Measurement

    measurement = Measurement(
        received_at=datetime.now(UTC),
        **{k: packet[k] for k in ("v_a", "v_b", "v_c", "t_reg_c", "t_amb_c")},
    )
    limits = Settings().limits
    failed = [
        v.check_code.value
        for v in measurement_verdicts(measurement, limits, packet["t_amb_c"])
        if not v.passed
    ]
    expected = {
        "good": [],
        "v_a_high": ["B3_V_A"],
        "v_b_low": ["B3_V_B"],
        "v_c_low": ["B3_V_C"],
        "too_hot": ["B3_T_REG"],
    }[preset]
    assert failed == expected


def test_simulator_without_a_station_says_so() -> None:
    result = send_packet(url(free_port()), make_packet("good", station="S", seq=1), timeout_s=1)
    assert result.status == 0 and result.message
    with pytest.raises(ValueError):
        make_packet("nonsense", station="S", seq=1)
    assert station_url("http://x:1/m", 2, "/y") == "http://x:1/m"


# ------------------------------------------------------------------ simulated bench + Wi-Fi


def test_hybrid_takes_measurements_from_wifi(port: int) -> None:
    settings = settings_for(port)
    mock = MockHardwareService(MockScenario.ALL_PASS, delay_scale=0, seed=1)
    hybrid = RealMeasuringDevice(mock, lambda: settings)
    try:
        assert hybrid.scenario == "all_pass" and not hybrid.real_board
        assert hybrid.listen_urls() == [f"http://127.0.0.1:{port}/measurement"]
        hybrid.connect("COM4")
        mac = hybrid.read_mac()
        assert mac.startswith("24:6F:28")
        hybrid.expect_board("24:6f:28:00:00:42")  # forwarded to the mock (retest)
        hybrid.disconnect()
        hybrid.connect("COM4")
        assert hybrid.read_mac() == "24:6F:28:00:00:42"
        packet = make_packet("v_c_low", station="STATION-01", seq=9)
        sender = threading.Timer(0.2, lambda: send_packet(url(port), packet))
        sender.start()
        measurement = hybrid.measure(5.0)
        sender.join()
        assert measurement.v_c == 3.10
    finally:
        hybrid.shutdown()


# ------------------------------------------------------------------ doctor


def test_doctor_on_a_fresh_pc(tmp_path: Path) -> None:
    findings = run_checks(AppPaths(tmp_path / "data"), MemorySecretStore())
    by_key = {f.key: f for f in findings}
    assert by_key["cli.doctor.data_ok"].level is Level.OK
    assert by_key["cli.doctor.settings_default"].level is Level.WARN
    assert by_key["cli.doctor.no_admin"].level is Level.FAIL  # run "admin create" first
    assert by_key["cli.doctor.mail_off"].level is Level.WARN
    assert by_key["cli.doctor.lib_excel"].level is Level.OK
    assert "cli.doctor.mode_real" in by_key


def test_doctor_reports_missing_mail_password(tmp_path: Path) -> None:
    paths = AppPaths(tmp_path / "data").ensure()
    paths.settings_file.write_text(
        '[email]\nenabled = true\nhost = "smtp.gmail.com"\nsender = "a@b.co"\n'
        'recipients = ["c@d.co"]\n',
        encoding="utf-8",
    )
    findings = {f.key: f for f in run_checks(paths, MemorySecretStore())}
    assert findings["cli.doctor.settings_ok"].level is Level.OK
    assert findings["cli.doctor.mail_no_password"].level is Level.FAIL
    store = MemorySecretStore({"smtp_password": "app-password"})
    findings = {f.key: f for f in run_checks(paths, store)}
    assert findings["cli.doctor.mail_ok"].params["host"] == "smtp.gmail.com"
