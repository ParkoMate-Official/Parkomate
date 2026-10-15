"""Bench test: a real board and real flashing; everything else simulated.

For trying the station with an ESP32 on USB before the Parkomate server, the production
firmware and the measuring device are available (``--bench-test`` / ``dev.bench_test``):

    real        serial ports, MAC + chip from the ROM bootloader, flashing with esptool
    local       the firmware: a build folder on this PC (``dev.firmware_dir`` /
                ``--firmware-dir``), e.g. Arduino's ``build/esp32``
    simulated   server whitelist, communication test, sensor readings, device ID,
                measuring device, QR camera - the mock scenario still applies to them

A test firmware such as Blink does not speak the station protocol, so the communication
test passes when the last flash of this board succeeded and its port is still there. The UI
shows the simulation band and chip, so a bench test can never pass for production.

:func:`flash_folder` is the same flashing path without the UI (``python -m parkomate flash``).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass

from parkomate.config.settings import Settings
from parkomate.core.errors import ErrorCode, HardwareError
from parkomate.core.interfaces import ProgressCallback
from parkomate.core.models import (
    FirmwareInfo,
    FlashResult,
    Measurement,
    PortInfo,
    PreviewFrame,
    SensorReading,
    WhitelistResult,
)
from parkomate.hardware.firmware import FirmwareImage, zero
from parkomate.hardware.flasher import ChipInfo, EsptoolFlasher
from parkomate.hardware.link import PortGuard
from parkomate.hardware.local_firmware import LocalFirmwareSource
from parkomate.hardware.mocks.mock_service import MockHardwareService
from parkomate.hardware.ports import PortScanner
from parkomate.hardware.service import RealHardwareService

log = logging.getLogger(__name__)


class BenchTestHardwareService:
    """``HardwareService`` for the bench test (see the module docstring)."""

    real_board = True
    """Read by the UI: the simulation chip explains that the board itself is real."""

    def __init__(self, real: RealHardwareService, simulated: MockHardwareService) -> None:
        self._real = real
        self._sim = simulated

    @property
    def scenario(self) -> str:
        return f"bench-test · {self._sim.scenario.value}"

    # ------------------------------------------------------------------ real board
    def list_ports(self) -> list[PortInfo]:
        return self._real.list_ports()

    def connect(self, port: str) -> None:
        self._real.connect(port)
        self._sim.attach(port)

    def disconnect(self) -> None:
        self._real.disconnect()
        self._sim.disconnect()

    def is_connected(self) -> bool:
        return self._real.is_connected()

    def read_mac(self) -> str:
        return self._real.read_mac()

    def chip_name(self) -> str:
        return self._real.chip_name()

    def fetch_firmware(self) -> FirmwareInfo:
        return self._real.fetch_firmware()

    def firmware_info(self) -> FirmwareInfo | None:
        return self._real.firmware_info()

    def flash(self, progress_cb: ProgressCallback) -> FlashResult:
        result = self._real.flash(progress_cb)
        if result.success:
            self._sim.firmware_written()
        return result

    # ------------------------------------------------------------------ simulated
    def check_whitelist(self, mac: str) -> WhitelistResult:
        return self._sim.check_whitelist(mac)

    def ping(self) -> bool:
        return self._real.is_connected() and self._sim.ping()

    def read_sensor(self) -> SensorReading:
        return self._sim.read_sensor()

    def get_device_id(self) -> str:
        return self._sim.get_device_id()

    def set_device_id(self, device_id: str) -> bool:
        return self._sim.set_device_id(device_id)

    def measure(self, timeout_s: float) -> Measurement:
        return self._sim.measure(timeout_s)

    def measure_ambient(self) -> float:
        return self._sim.measure_ambient()

    def open_camera(self) -> None:
        self._sim.open_camera()

    def read_qr(self, timeout_s: float) -> str | None:
        return self._sim.read_qr(timeout_s)

    def get_preview_frame(self) -> PreviewFrame | None:
        return self._sim.get_preview_frame()

    def close_camera(self) -> None:
        self._sim.close_camera()

    # ------------------------------------------------------------------ lifecycle
    def shutdown(self) -> None:
        try:
            self._real.shutdown()
        finally:
            self._sim.shutdown()


# ====================================================================== flash without the UI


@dataclass(frozen=True, slots=True)
class FlashReport:
    port: str
    chip: ChipInfo
    firmware: FirmwareInfo
    images: tuple[tuple[str, int, int], ...]  # (name, offset, size)
    result: FlashResult


def pick_port(ports: list[PortInfo], wanted: str | None) -> str:
    """``wanted`` if it exists, else the only ESP32-looking port. Raises ``HW_NO_PORT``."""
    names = [p.name for p in ports]
    if wanted:
        if wanted not in names:
            raise HardwareError(
                f"port {wanted} not found", code=ErrorCode.HW_NO_PORT, params={"port": wanted}
            )
        return wanted
    candidates = [p.name for p in ports if p.is_esp_candidate]
    if len(candidates) == 1:
        return candidates[0]
    found = ", ".join(candidates) or "none"
    raise HardwareError(
        f"cannot choose the board's port by itself (ESP32-looking ports: {found})",
        code=ErrorCode.HW_NO_PORT,
        params={"port": "?"},
    )


def flash_folder(
    settings: Callable[[], Settings],
    port: str,
    progress: ProgressCallback,
    *,
    flasher: EsptoolFlasher | None = None,
    source: LocalFirmwareSource | None = None,
    on_ready: Callable[[ChipInfo, FirmwareInfo, list[FirmwareImage]], None] | None = None,
) -> FlashReport:
    """Read the chip, load the local build into RAM and flash it (``parkomate flash``)."""
    flasher = flasher or EsptoolFlasher(settings, PortGuard())
    source = source or LocalFirmwareSource(settings)
    info, images = source.fetch_firmware()
    try:
        chip = flasher.chip_info(port)
        if on_ready is not None:
            on_ready(chip, info, images)
        result = flasher.flash(port, images, progress)
        layout = tuple((i.name, i.offset, len(i.data)) for i in images)
    finally:
        for image in images:
            zero(image.data)
    return FlashReport(port=port, chip=chip, firmware=info, images=layout, result=result)


def list_ports() -> list[PortInfo]:
    return PortScanner().list_ports()
