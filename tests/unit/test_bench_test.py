"""Bench test: local firmware build, real board + flashing, the rest simulated."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from parkomate.app import create_hardware
from parkomate.cli import main as cli_main
from parkomate.config.manager import validate_settings
from parkomate.config.secrets import MemorySecretStore
from parkomate.config.settings import DevSettings, ProgrammingSettings, Settings
from parkomate.core.errors import ErrorCode, HardwareError, SettingsError
from parkomate.core.interfaces import HardwareService
from parkomate.core.models import PortInfo
from parkomate.hardware import RealHardwareService
from parkomate.hardware.bench import BenchTestHardwareService, flash_folder, pick_port
from parkomate.hardware.firmware import FirmwareImage
from parkomate.hardware.local_firmware import (
    ENV_FIRMWARE_DIR,
    LocalFirmwareSource,
    plan_images,
)
from parkomate.hardware.mocks import MockHardwareService
from tests.bench_fakes import (
    APP,
    BOOTLOADER,
    PARTITIONS,
    ComPort,
    FakeFlasher,
    make_bench,
)
from tests.bench_fakes import build_folder as _build
from tests.bench_fakes import settings_for as _settings

BLINK = Path(__file__).resolve().parents[2] / "firmware" / "esp32-blink"


@pytest.fixture(autouse=True)
def _no_env_folder(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ENV_FIRMWARE_DIR, raising=False)


# ------------------------------------------------------------------ local firmware


def test_plan_arduino_build_folder(tmp_path: Path) -> None:
    plan = plan_images(_build(tmp_path / "b"), ProgrammingSettings())
    assert [(p.name, p.path.name, p.offset) for p in plan] == [
        ("bootloader", "Blink.ino.bootloader.bin", 0x1000),
        ("partitions", "Blink.ino.partitions.bin", 0x8000),
        ("app", "Blink.ino.bin", 0x10000),
    ]


def test_plan_follows_offset_settings(tmp_path: Path) -> None:
    programming = ProgrammingSettings(bootloader_offset=0, app_offset=0x20000)
    plan = plan_images(_build(tmp_path / "b"), programming)
    assert [p.offset for p in plan] == [0, 0x8000, 0x20000]


def test_plan_app_only_and_single_file(tmp_path: Path) -> None:
    folder = _build(tmp_path / "b", full=False)
    assert [(p.name, p.offset) for p in plan_images(folder, ProgrammingSettings())] == [
        ("app", 0x10000)
    ]
    single = plan_images(folder / "Blink.ino.bin", ProgrammingSettings())
    assert [(p.name, p.offset) for p in single] == [("app", 0x10000)]


@pytest.mark.parametrize(
    ("make", "expected"),
    [
        (lambda d: d, "no application"),  # empty folder
        (lambda d: d / "missing", "does not exist"),
        (lambda d: (d / "notes.txt", (d / "notes.txt").write_text("x"))[0], "not a .bin"),
    ],
)
def test_plan_problems(tmp_path: Path, make, expected: str) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(HardwareError) as info:
        plan_images(make(tmp_path), ProgrammingSettings())
    assert info.value.code is ErrorCode.FW_LOCAL_INVALID
    assert expected in str(info.value)


def test_plan_needs_a_folder_and_one_app(tmp_path: Path) -> None:
    with pytest.raises(HardwareError, match="no local firmware folder"):
        plan_images("", ProgrammingSettings())
    folder = _build(tmp_path / "b")
    (folder / "Other.ino.bin").write_bytes(APP)
    with pytest.raises(HardwareError, match="more than one app"):
        plan_images(folder, ProgrammingSettings())


def test_plan_offsets_must_differ(tmp_path: Path) -> None:
    programming = ProgrammingSettings(bootloader_offset=0x8000)
    with pytest.raises(HardwareError, match="share a flash offset"):
        plan_images(_build(tmp_path / "b"), programming)


def test_fetch_reads_files_into_ram(tmp_path: Path) -> None:
    folder = _build(tmp_path / "b")
    info, images = LocalFirmwareSource(lambda: _settings(folder)).fetch_firmware()
    assert [(i.name, i.offset, bytes(i.data)) for i in images] == [
        ("bootloader", 0x1000, BOOTLOADER),
        ("partitions", 0x8000, PARTITIONS),
        ("app", 0x10000, APP),
    ]
    assert all(isinstance(i.data, bytearray) for i in images)
    assert info.name == "Blink.ino.bin"
    assert info.version.startswith("local ")
    assert info.size == len(BOOTLOADER) + len(PARTITIONS) + len(APP)
    assert info.hash_verified is False  # no trusted hash for a local build
    assert images[2].sha256 == hashlib.sha256(APP).hexdigest()


def test_fetch_rejects_a_wrong_file(tmp_path: Path) -> None:
    folder = _build(tmp_path / "b", app=b"PK\x03\x04 not firmware")
    with pytest.raises(HardwareError) as info:
        LocalFirmwareSource(lambda: _settings(folder)).fetch_firmware()
    assert info.value.code is ErrorCode.FW_LOCAL_INVALID
    assert info.value.params == {"path": str(folder / "Blink.ino.bin")}


def test_environment_overrides_setting(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    folder = _build(tmp_path / "b", full=False)
    monkeypatch.setenv(ENV_FIRMWARE_DIR, str(folder))
    source = LocalFirmwareSource(lambda: _settings(tmp_path / "elsewhere"))
    assert source.location() == str(folder)
    assert [i.name for i in source.fetch_firmware()[1]] == ["app"]


@pytest.mark.skipif(not BLINK.is_dir(), reason="firmware/esp32-blink not present")
def test_blink_build_goes_to_the_verified_addresses() -> None:
    info, images = LocalFirmwareSource(lambda: _settings(BLINK)).fetch_firmware()
    assert [(i.name, i.offset) for i in images] == [
        ("bootloader", 0x1000),
        ("partitions", 0x8000),
        ("app", 0x10000),
    ]
    assert info.name == "Blink.ino.bin"
    assert images[2].data[12:14] == b"\x00\x00"  # image chip ID 0 = classic ESP32


# ------------------------------------------------------------------ bench test service


def _bench(
    tmp_path: Path, ports: list[ComPort], *, succeed: bool = True
) -> tuple[BenchTestHardwareService, FakeFlasher]:
    return make_bench(tmp_path / "b", ports, succeed=succeed)


def test_bench_flashes_the_real_board_and_simulates_the_rest(tmp_path: Path) -> None:
    ports = [ComPort("COM9"), ComPort("COM3", "Bluetooth link", None, None, None)]
    hw, flasher = _bench(tmp_path, ports)
    assert isinstance(hw, HardwareService)
    assert hw.real_board and hw.scenario == "bench-test · all_pass"
    assert [p.name for p in hw.list_ports()] == ["COM9", "COM3"]  # ESP32 bridge first
    hw.connect("COM9")
    assert hw.read_mac() == "24:6F:28:AA:BB:CC"  # the real board's MAC
    assert hw.chip_name().startswith("ESP32-D0WD")
    assert hw.check_whitelist("24:6F:28:AA:BB:CC").allowed  # simulated server
    info = hw.fetch_firmware()
    assert hw.firmware_info() == info and info.name == "Blink.ino.bin"
    assert hw.ping() is False  # nothing flashed yet
    result = hw.flash(lambda _p: None)
    assert result.success
    assert [(name, offset) for name, offset, _ in flasher.written] == [
        ("bootloader", 0x1000),
        ("partitions", 0x8000),
        ("app", 0x10000),
    ]
    assert flasher.written[2][2] == APP
    assert hw.ping() is True
    assert hw.read_sensor().unit == "cm"
    assert hw.measure(5).v_c > 3
    hw.open_camera()
    qr = hw.read_qr(1)
    assert qr and hw.set_device_id(qr) and hw.get_device_id() == qr
    hw.close_camera()

    ports.clear()  # cable pulled
    assert not hw.is_connected() and hw.ping() is False
    hw.disconnect()
    ports.append(ComPort("COM9"))
    hw.connect("COM9")  # the next board starts unflashed
    assert hw.ping() is False
    hw.shutdown()
    assert hw.firmware_info() is None


def test_bench_failed_flash_keeps_ping_false(tmp_path: Path) -> None:
    hw, _ = _bench(tmp_path, [ComPort("COM9")], succeed=False)
    hw.connect("COM9")
    hw.fetch_firmware()
    assert not hw.flash(lambda _p: None).success
    assert hw.ping() is False


def test_bench_unknown_port(tmp_path: Path) -> None:
    hw, _ = _bench(tmp_path, [ComPort("COM9")])
    with pytest.raises(HardwareError) as info:
        hw.connect("COM42")
    assert info.value.code is ErrorCode.HW_NO_PORT


def test_pick_port() -> None:
    esp = PortInfo(name="COM9", description="CP210x", is_esp_candidate=True)
    other = PortInfo(name="COM3", description="Bluetooth")
    assert pick_port([other, esp], None) == "COM9"
    assert pick_port([other, esp], "COM3") == "COM3"
    for ports, wanted in (([other], None), ([esp, esp], None), ([esp], "COM1")):
        with pytest.raises(HardwareError) as info:
            pick_port(ports, wanted)
        assert info.value.code is ErrorCode.HW_NO_PORT


def test_flash_folder_zeroes_the_images(tmp_path: Path) -> None:
    settings = _settings(_build(tmp_path / "b"))
    flasher = FakeFlasher(settings)
    kept: list[FirmwareImage] = []
    report = flash_folder(
        lambda: settings,
        "COM9",
        lambda _p: None,
        flasher=flasher,
        on_ready=lambda _chip, _info, images: kept.extend(images),
    )
    assert report.result.success and report.port == "COM9"
    assert report.images == (
        ("bootloader", 0x1000, 64),
        ("partitions", 0x8000, 32),
        ("app", 0x10000, len(APP)),
    )
    assert kept and all(not any(i.data) for i in kept)  # RAM copies wiped after flashing


# ------------------------------------------------------------------ selection + settings


def test_create_hardware_modes(tmp_path: Path) -> None:
    secrets = MemorySecretStore()
    bench_on = Settings(dev=DevSettings(bench_test=True))
    hardware, simulated = create_hardware(lambda: bench_on, secrets, mock=None)
    assert simulated and isinstance(hardware, BenchTestHardwareService)
    hardware, _ = create_hardware(lambda: Settings(), secrets, mock=None, bench_test=True)
    assert isinstance(hardware, BenchTestHardwareService)
    hardware, _ = create_hardware(lambda: bench_on, secrets, mock=True)  # --mock wins
    assert isinstance(hardware, MockHardwareService)
    hardware, simulated = create_hardware(lambda: bench_on, secrets, mock=None, bench_test=False)
    assert not simulated and isinstance(hardware, RealHardwareService)


def test_simulated_bench_shows_the_local_build(tmp_path: Path) -> None:
    folder = _build(tmp_path / "b")
    settings = Settings(
        dev=DevSettings(use_mock_hardware=True, firmware_dir=str(folder), mock_delay_scale=0)
    )
    hardware, simulated = create_hardware(lambda: settings, MemorySecretStore(), mock=None)
    assert simulated and isinstance(hardware, MockHardwareService)
    hardware.connect(hardware.list_ports()[0].name)
    info = hardware.fetch_firmware()
    assert info.name == "Blink.ino.bin" and not info.hash_verified
    assert hardware.flash(lambda _p: None).success  # flashing itself stays simulated
    hardware.shutdown()
    assert hardware.firmware_info() is None


def test_mock_and_bench_test_are_exclusive() -> None:
    with pytest.raises(SettingsError) as info:
        validate_settings({"dev": {"use_mock_hardware": True, "bench_test": True}})
    issue = info.value.issues[0]
    assert issue.type == "dev_modes_exclusive"
    assert issue.ctx["keys"] == ["dev.use_mock_hardware", "dev.bench_test"]


# ------------------------------------------------------------------ CLI


def test_cli_flash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    folder = _build(tmp_path / "b")
    monkeypatch.setenv(ENV_FIRMWARE_DIR, "")  # restored after the test (main sets it)
    monkeypatch.setenv("PARKOMATE_SETTINGS", str(tmp_path / "none.toml"))
    flashers: list[FakeFlasher] = []

    def make_flasher(settings, _guard):  # type: ignore[no-untyped-def]
        flashers.append(FakeFlasher(settings()))
        return flashers[-1]

    ports = [
        PortInfo(name="COM3", description="Bluetooth"),
        PortInfo(name="COM9", description="CP210x", is_esp_candidate=True),
    ]
    monkeypatch.setattr("parkomate.hardware.bench.list_ports", lambda: ports)
    monkeypatch.setattr("parkomate.hardware.bench.EsptoolFlasher", make_flasher)

    assert cli_main(["flash", "--firmware-dir", str(folder)]) == 0
    out = capsys.readouterr().out
    assert "Board on COM9: ESP32-D0WD-V3" in out
    assert "app → 0x10000" in out and "Flashing… 100 %" in out and "Done in" in out
    assert [o for _n, o, _d in flashers[0].written] == [0x1000, 0x8000, 0x10000]

    assert cli_main(["flash", "--port", "COM1", "--firmware-dir", str(folder)]) == 1
    err = capsys.readouterr().err
    assert "HW_NO_PORT" in err and "COM9" in err and "ESP32 USB bridge" in err

    assert cli_main(["flash", "--firmware-dir", str(tmp_path / "missing")]) == 1
    assert "FW_LOCAL_INVALID" in capsys.readouterr().err
