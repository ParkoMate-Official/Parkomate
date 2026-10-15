"""Fakes for bench-test tests: a local build folder, serial ports and an esptool stand-in."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from parkomate.config.secrets import MemorySecretStore
from parkomate.config.settings import DevSettings, Settings
from parkomate.core.errors import ErrorCode
from parkomate.core.interfaces import ProgressCallback
from parkomate.core.models import FlashResult
from parkomate.hardware import RealHardwareService
from parkomate.hardware.bench import BenchTestHardwareService
from parkomate.hardware.firmware import FirmwareImage
from parkomate.hardware.flasher import ChipInfo, EsptoolFlasher
from parkomate.hardware.link import PortGuard
from parkomate.hardware.local_firmware import LocalFirmwareSource
from parkomate.hardware.mocks import MockHardwareService, MockScenario
from parkomate.hardware.ports import PortScanner

BOOTLOADER = b"\xe9\x03\x02\x2f" + bytes(60)
PARTITIONS = b"\xaa\x50\x01\x02" + bytes(28)
APP = b"\xe9\x06\x02\x2f" + bytes(200)


def build_folder(folder: Path, *, app: bytes = APP, full: bool = True, extras: bool = True) -> Path:
    """An Arduino-style ``build/esp32`` folder with tiny but well-formed images."""
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "Blink.ino.bin").write_bytes(app)
    if full:
        (folder / "Blink.ino.bootloader.bin").write_bytes(BOOTLOADER)
        (folder / "Blink.ino.partitions.bin").write_bytes(PARTITIONS)
    if extras:  # an Arduino build folder also holds these - never flashed
        (folder / "Blink.ino.merged.bin").write_bytes(b"\xff" * 64)
        (folder / "Blink.ino.elf").write_bytes(b"\x7fELF")
        (folder / "Blink.ino.map").write_text("map", encoding="utf-8")
    return folder


def settings_for(folder: Path | str) -> Settings:
    return Settings(dev=DevSettings(firmware_dir=str(folder)))


@dataclass
class ComPort:
    """What ``serial.tools.list_ports.comports`` yields."""

    device: str
    description: str = "Silicon Labs CP210x USB to UART Bridge"
    vid: int | None = 0x10C4
    pid: int | None = 0xEA60
    serial_number: str | None = "0001"


class FakeFlasher(EsptoolFlasher):
    """Records what esptool would write; no serial port."""

    def __init__(self, settings: Settings, *, succeed: bool = True) -> None:
        super().__init__(lambda: settings, PortGuard())
        self.succeed = succeed
        self.written: list[tuple[str, int, bytes]] = []

    def chip_info(self, port: str) -> ChipInfo:
        return ChipInfo(mac="24:6f:28:aa:bb:cc", description="ESP32-D0WD-V3 (revision v3.1)")

    def flash(
        self, port: str, images: Sequence[FirmwareImage], progress: ProgressCallback
    ) -> FlashResult:
        self.written = [(i.name, i.offset, bytes(i.data)) for i in images]
        progress(100)
        if not self.succeed:
            return FlashResult(success=False, error_code=ErrorCode.HW_FLASH_FAILED, message="x")
        return FlashResult(success=True, bytes_written=sum(len(i.data) for i in images))


def make_bench(
    folder: Path, ports: list[ComPort], *, succeed: bool = True
) -> tuple[BenchTestHardwareService, FakeFlasher]:
    """Bench test whose real side is the fake ports + fake esptool; build in ``folder``."""
    settings = settings_for(build_folder(folder))
    flasher = FakeFlasher(settings, succeed=succeed)
    real = RealHardwareService(
        lambda: settings,
        MemorySecretStore(),
        scanner=PortScanner(lambda: list(ports)),
        flasher=flasher,
        firmware_source=LocalFirmwareSource(lambda: settings),
    )
    simulated = MockHardwareService(MockScenario.ALL_PASS, delay_scale=0, seed=3)
    return BenchTestHardwareService(real, simulated), flasher
