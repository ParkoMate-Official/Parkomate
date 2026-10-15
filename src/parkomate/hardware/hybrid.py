"""Simulated bench (or bench test) + the REAL measuring device over Wi-Fi.

``--real-measuring-device`` / ``dev.real_measuring_device``: everything stays as the chosen
simulated mode (mock scenario, or the bench test with a real ESP32), except the measurement:
the station opens its HTTP listener and waits for the measuring device - or for the
simulator ``python -m parkomate measuring-device`` running on another PC or phone on the same
Wi-Fi - exactly as in production. Used to demonstrate and test the Wi-Fi link end to end
before the full bench exists.
"""

from __future__ import annotations

from collections.abc import Callable

from parkomate.config.settings import Settings
from parkomate.core.interfaces import HardwareService, ProgressCallback
from parkomate.core.models import (
    FirmwareInfo,
    FlashResult,
    Measurement,
    PortInfo,
    PreviewFrame,
    SensorReading,
    WhitelistResult,
)
from parkomate.hardware.measurement import HttpMeasurementListener, MeasurementTransport


class RealMeasuringDevice:
    """``HardwareService`` = ``inner`` with ``measure`` / ``measure_ambient`` from Wi-Fi."""

    real_measuring_device = True
    """Read by the UI (simulation chip tooltip, listening address on the Testing screen)."""

    def __init__(
        self,
        inner: HardwareService,
        settings: Callable[[], Settings],
        listener: MeasurementTransport | None = None,
    ) -> None:
        self._inner = inner
        self._settings = settings
        self._listener = listener or HttpMeasurementListener(settings)

    @property
    def inner(self) -> HardwareService:
        return self._inner

    @property
    def scenario(self) -> str:
        return str(getattr(self._inner, "scenario", ""))

    @property
    def real_board(self) -> bool:
        return bool(getattr(self._inner, "real_board", False))

    def expect_board(self, mac: str) -> None:
        """Forwarded to a simulated bench (retest of a repaired board)."""
        expect = getattr(self._inner, "expect_board", None)
        if callable(expect):
            expect(mac)

    def listen_urls(self) -> list[str]:
        urls = getattr(self._listener, "listen_urls", None)
        return list(urls()) if callable(urls) else []

    # ------------------------------------------------------------------ measuring device
    def measure(self, timeout_s: float) -> Measurement:
        return self._listener.measure(timeout_s)

    def measure_ambient(self) -> float:
        return self._listener.measure_ambient(self._settings().measurement.ambient_timeout_s)

    # ------------------------------------------------------------------ everything else
    def list_ports(self) -> list[PortInfo]:
        return self._inner.list_ports()

    def connect(self, port: str) -> None:
        self._inner.connect(port)

    def disconnect(self) -> None:
        self._inner.disconnect()

    def is_connected(self) -> bool:
        return self._inner.is_connected()

    def read_mac(self) -> str:
        return self._inner.read_mac()

    def chip_name(self) -> str:
        return self._inner.chip_name()

    def check_whitelist(self, mac: str) -> WhitelistResult:
        return self._inner.check_whitelist(mac)

    def fetch_firmware(self) -> FirmwareInfo:
        return self._inner.fetch_firmware()

    def firmware_info(self) -> FirmwareInfo | None:
        return self._inner.firmware_info()

    def flash(self, progress_cb: ProgressCallback) -> FlashResult:
        return self._inner.flash(progress_cb)

    def ping(self) -> bool:
        return self._inner.ping()

    def read_sensor(self) -> SensorReading:
        return self._inner.read_sensor()

    def get_device_id(self) -> str:
        return self._inner.get_device_id()

    def set_device_id(self, device_id: str) -> bool:
        return self._inner.set_device_id(device_id)

    def open_camera(self) -> None:
        self._inner.open_camera()

    def read_qr(self, timeout_s: float) -> str | None:
        return self._inner.read_qr(timeout_s)

    def get_preview_frame(self) -> PreviewFrame | None:
        return self._inner.get_preview_frame()

    def close_camera(self) -> None:
        self._inner.close_camera()

    def shutdown(self) -> None:
        try:
            self._inner.shutdown()
        finally:
            self._listener.stop()
