"""Serial link to the board firmware (items 22, 23, 32, 34): PING, READ_SENSOR, GET_ID, SET_ID.

A fake serial port answers like the firmware; a fake clock makes timeouts instant.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from parkomate.config.settings import SerialSettings, Settings
from parkomate.core.errors import ErrorCode, HardwareError, InputError
from parkomate.core.models import PortInfo
from parkomate.hardware.link import DeviceLink
from parkomate.hardware.ports import PortScanner
from parkomate.hardware.service import RealHardwareService

PORT = "COM7"


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


class FakeBoard:
    """Answers commands like the firmware. ``replies`` maps a command word to reply lines."""

    def __init__(self, clock: Clock, replies: dict[str, list[str]] | None = None) -> None:
        self.clock = clock
        self.is_open = True
        self.device_id = "PKM-000100"
        self.replies = replies if replies is not None else {}
        self.written: list[str] = []
        self.pending: list[bytes] = []
        self.fail_with: BaseException | None = None
        self.opens = 0

    # -- SerialLike
    def write(self, data: bytes) -> int:
        if self.fail_with is not None:
            raise self.fail_with
        command = data.decode("ascii").strip()
        self.written.append(command)
        word, _, arg = command.partition(" ")
        if word in self.replies:
            lines = self.replies[word]
        elif word == "PING":
            lines = ["PONG"]
        elif word == "GET_ID":
            lines = [f"ID {self.device_id}" if self.device_id else "ID"]
        elif word == "SET_ID":
            self.device_id = arg
            lines = ["OK"]
        elif word == "READ_SENSOR":
            lines = ["SENSOR 151.25 cm"]
        else:
            lines = ["ERR UNKNOWN"]
        self.pending = [f"{line}\r\n".encode() for line in lines]
        return len(data)

    def readline(self) -> bytes:
        self.clock.now += 0.1  # each read waits up to the serial timeout
        return self.pending.pop(0) if self.pending else b""

    def reset_input_buffer(self) -> None:
        self.pending = []

    def close(self) -> None:
        self.is_open = False


def _link(board: FakeBoard, **serial: object) -> DeviceLink:
    settings = Settings(serial=SerialSettings(**serial))  # type: ignore[arg-type]

    def factory(port: str, _baud: int, _timeout: float) -> FakeBoard:
        assert port == PORT
        board.opens += 1
        board.is_open = True
        return board

    link = DeviceLink(
        lambda: settings, factory=factory, monotonic=board.clock.monotonic, sleep=board.clock.sleep
    )
    link.attach(PORT)
    return link


@pytest.fixture
def board() -> FakeBoard:
    return FakeBoard(Clock())


# ------------------------------------------------------------------ B1 communication test


def test_ping_ok(board: FakeBoard) -> None:
    assert _link(board).ping() is True
    assert board.written == ["PING"]


def test_ping_silent_board_is_false_not_an_error(board: FakeBoard) -> None:
    board.replies["PING"] = []
    assert _link(board, command_retries=1).ping() is False
    assert board.written == ["PING", "PING"]  # retried once, then "no answer"


def test_ping_ignores_boot_log_lines(board: FakeBoard) -> None:
    board.replies["PING"] = ["ets Jun  8 2016 00:22:57", "rst:0x1 (POWERON_RESET)", "PONG"]
    assert _link(board).ping() is True


def test_ping_device_error_raises(board: FakeBoard) -> None:
    board.replies["PING"] = ["ERR BUSY"]
    with pytest.raises(HardwareError) as info:
        _link(board).ping()
    assert info.value.code is ErrorCode.HW_DEVICE_ERROR
    assert board.written == ["PING"]  # a device-side error is never retried


def test_cable_pulled_is_com_disconnected(board: FakeBoard) -> None:
    board.fail_with = OSError("device not configured")
    with pytest.raises(HardwareError) as info:
        _link(board, command_retries=0).ping()
    assert info.value.code is ErrorCode.HW_COM_DISCONNECTED


# ------------------------------------------------------------------ B2 sensor readings


def test_read_sensor_value_and_unit(board: FakeBoard) -> None:
    reading = _link(board).read_sensor()
    assert (reading.value, reading.unit, reading.raw) == (151.25, "cm", "151.25 cm")


def test_read_sensor_without_unit(board: FakeBoard) -> None:
    board.replies["READ_SENSOR"] = ["SENSOR 42"]
    reading = _link(board).read_sensor()
    assert (reading.value, reading.unit) == (42.0, "")


@pytest.mark.parametrize("reply", ["SENSOR", "SENSOR abc cm"])
def test_read_sensor_garbage_is_device_error(board: FakeBoard, reply: str) -> None:
    board.replies["READ_SENSOR"] = [reply]
    with pytest.raises(HardwareError) as info:
        _link(board).read_sensor()
    assert info.value.code is ErrorCode.HW_DEVICE_ERROR


def test_five_readings_in_a_row(board: FakeBoard) -> None:
    link = _link(board)
    values = [link.read_sensor().value for _ in range(5)]
    assert values == [151.25] * 5 and board.written == ["READ_SENSOR"] * 5
    assert board.opens == 1  # the port stays open between commands


def test_silent_sensor_times_out(board: FakeBoard) -> None:
    board.replies["READ_SENSOR"] = []
    with pytest.raises(HardwareError) as info:
        _link(board, command_retries=0).read_sensor()
    assert info.value.code is ErrorCode.HW_TIMEOUT


# ------------------------------------------------------------------ C device ID


def test_get_id(board: FakeBoard) -> None:
    assert _link(board).get_id() == "PKM-000100"


def test_get_id_blank_board(board: FakeBoard) -> None:
    board.device_id = ""
    assert _link(board).get_id() == ""


def test_set_id_then_read_back(board: FakeBoard) -> None:
    link = _link(board)
    assert link.set_id("PKM-000519") is True
    assert link.get_id() == "PKM-000519"
    assert board.written == ["SET_ID PKM-000519", "GET_ID"]


def test_set_id_refused_by_board(board: FakeBoard) -> None:
    board.replies["SET_ID"] = ["ERR LOCKED"]
    assert _link(board).set_id("PKM-000519") is False


@pytest.mark.parametrize("bad", ["", "PKM 1", "PKM-1\nSET_ID X", "x" * 65, "PKM-ü"])
def test_set_id_never_sends_unsafe_text(board: FakeBoard, bad: str) -> None:
    with pytest.raises(InputError):
        _link(board).set_id(bad)
    assert board.written == []


def test_no_port_selected() -> None:
    link = DeviceLink(Settings)
    with pytest.raises(HardwareError) as info:
        link.get_id()
    assert info.value.code is ErrorCode.HW_COM_DISCONNECTED


def test_board_still_booting_is_waited_for(board: FakeBoard) -> None:
    link = _link(board, command_retries=0, boot_wait_s=4.0)
    silent_until = board.clock.now + 2.0
    real_write = board.write

    def write(data: bytes) -> int:
        count = real_write(data)
        if board.clock.now < silent_until:
            board.pending = []  # firmware not up yet
        return count

    board.write = write  # type: ignore[method-assign]
    link.expect_boot()
    assert link.get_id() == "PKM-000100"
    assert len(board.written) > 1  # kept asking while the board booted


# ------------------------------------------------------------------ through the service


class _Port:
    def __init__(self, device: str) -> None:
        self.device = device
        self.description = "CP2102 USB to UART"
        self.vid, self.pid, self.serial_number = 0x10C4, 0xEA60, "0001"


def _service(board: FakeBoard, present: Callable[[], bool]) -> RealHardwareService:
    settings = Settings()

    def factory(_port: str, _baud: int, _timeout: float) -> FakeBoard:
        board.is_open = True
        return board

    link = DeviceLink(
        lambda: settings, factory=factory, monotonic=board.clock.monotonic, sleep=board.clock.sleep
    )
    scanner = PortScanner(lambda: [_Port(PORT)] if present() else [])

    class _Unused:
        def __getattr__(self, name: str) -> object:
            raise AssertionError(f"{name} must not be used in this test")

    return RealHardwareService(
        lambda: settings,
        _Unused(),  # type: ignore[arg-type]
        scanner=scanner,
        link=link,
        flasher=_Unused(),  # type: ignore[arg-type]
        server=_Unused(),  # type: ignore[arg-type]
        measurement=_Unused(),  # type: ignore[arg-type]
        camera=_Unused(),  # type: ignore[arg-type]
    )


def test_service_identity_round_trip(board: FakeBoard) -> None:
    hw = _service(board, lambda: True)
    ports = hw.list_ports()
    assert ports == [
        PortInfo(
            name=PORT,
            description="CP2102 USB to UART",
            vid=0x10C4,
            pid=0xEA60,
            serial_number="0001",
            is_esp_candidate=True,
        )
    ]
    hw.connect(PORT)
    assert hw.is_connected() and hw.ping()
    assert hw.get_device_id() == "PKM-000100"
    assert hw.set_device_id("PKM-000519") and hw.get_device_id() == "PKM-000519"


def test_service_unplugged_board(board: FakeBoard) -> None:
    plugged = {"value": True}
    hw = _service(board, lambda: plugged["value"])
    hw.connect(PORT)
    plugged["value"] = False
    assert not hw.is_connected()
    for call in (hw.ping, hw.read_sensor, hw.get_device_id):
        with pytest.raises(HardwareError) as info:
            call()
        assert info.value.code is ErrorCode.HW_COM_DISCONNECTED
    with pytest.raises(HardwareError) as missing:
        hw.connect("COM99")
    assert missing.value.code is ErrorCode.HW_NO_PORT
