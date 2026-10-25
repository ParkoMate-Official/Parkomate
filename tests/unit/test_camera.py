"""USB QR camera (items 30-31): capture loop, preview, QR read rules, and a real decode."""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterator

import numpy as np
import pytest

from parkomate.config.settings import CameraSettings, Settings
from parkomate.core.errors import CameraError, ErrorCode
from parkomate.hardware.camera import PREVIEW_WIDTH, CameraService, ZbarOpenCvDecoder

cv2 = pytest.importorskip("cv2")


class FakeSource:
    """Delivers grey frames; ``None`` frames simulate a camera that stopped."""

    def __init__(self, *, dead: bool = False, width: int = 1280, height: int = 720) -> None:
        self.dead = dead
        self.shape = (height, width, 3)
        self.opened = False
        self.closed = False

    def open(self) -> None:
        self.opened = True

    def read(self) -> np.ndarray | None:
        return None if self.dead else np.full(self.shape, 128, dtype=np.uint8)

    def close(self) -> None:
        self.closed = True


class MissingSource(FakeSource):
    def open(self) -> None:
        raise CameraError("camera 0 not available", code=ErrorCode.CAM_NOT_FOUND)


class ScriptedDecoder:
    """Returns the scripted texts frame by frame, then ``tail`` forever."""

    def __init__(self, script: list[list[str]], tail: list[str] | None = None) -> None:
        self._script = list(script)
        self._tail = tail or []
        self._lock = threading.Lock()

    def decode(self, _frame: object) -> list[str]:
        with self._lock:
            return self._script.pop(0) if self._script else list(self._tail)


def _service(
    decoder: ScriptedDecoder, source: FakeSource | None = None, **camera: object
) -> tuple[CameraService, FakeSource]:
    settings = Settings(camera=CameraSettings(fps=60, **camera))  # type: ignore[arg-type]
    src = source or FakeSource()

    def factory(_settings: CameraSettings) -> FakeSource:
        return src

    return CameraService(lambda: settings, source_factory=factory, decoder=decoder), src


@pytest.fixture
def opened() -> Iterator[Callable[..., CameraService]]:
    services: list[CameraService] = []

    def make(
        decoder: ScriptedDecoder, source: FakeSource | None = None, **camera: object
    ) -> CameraService:
        service, _ = _service(decoder, source, **camera)
        service.open()
        services.append(service)
        return service

    yield make
    for service in services:
        service.close()


def test_reads_first_matching_id(opened: Callable[..., CameraService]) -> None:
    cam = opened(ScriptedDecoder([[], ["PKM-000519"]]))
    assert cam.read_qr(2.0) == "PKM-000519"


def test_skips_wrong_codes_when_a_valid_one_follows(
    opened: Callable[..., CameraService],
) -> None:
    cam = opened(ScriptedDecoder([["http://example.com/x y"], ["PKM-000520"]]))
    assert cam.read_qr(2.0) == "PKM-000520"


def test_only_wrong_codes_is_bad_format(opened: Callable[..., CameraService]) -> None:
    cam = opened(ScriptedDecoder([], tail=["not an id!"]))
    with pytest.raises(CameraError) as info:
        cam.read_qr(0.3)
    assert info.value.code is ErrorCode.QR_BAD_FORMAT
    assert info.value.params["value"] == "not an id!"


def test_nothing_readable_returns_none(opened: Callable[..., CameraService]) -> None:
    cam = opened(ScriptedDecoder([]))
    assert cam.read_qr(0.3) is None


def test_custom_id_pattern(opened: Callable[..., CameraService]) -> None:
    cam = opened(ScriptedDecoder([], tail=["PKM-000519"]), id_pattern=r"^SN\d{6}$")
    with pytest.raises(CameraError) as info:
        cam.read_qr(0.3)
    assert info.value.code is ErrorCode.QR_BAD_FORMAT


def test_read_before_open_is_camera_not_found() -> None:
    cam, _ = _service(ScriptedDecoder([["PKM-000519"]]))
    with pytest.raises(CameraError) as info:
        cam.read_qr(0.1)
    assert info.value.code is ErrorCode.CAM_NOT_FOUND


def test_missing_camera_raises_on_open() -> None:
    cam, _ = _service(ScriptedDecoder([]), MissingSource())
    with pytest.raises(CameraError) as info:
        cam.open()
    assert info.value.code is ErrorCode.CAM_NOT_FOUND
    assert not cam.is_open


def test_camera_that_stops_delivering_frames(opened: Callable[..., CameraService]) -> None:
    cam = opened(ScriptedDecoder([]), FakeSource(dead=True))
    with pytest.raises(CameraError) as info:
        cam.read_qr(5.0)
    assert info.value.code is ErrorCode.CAM_NOT_FOUND


def test_preview_is_downscaled_rgb_and_cleared_on_close() -> None:
    cam, source = _service(ScriptedDecoder([], tail=["PKM-000519"]))
    cam.open()
    try:
        assert cam.read_qr(2.0) == "PKM-000519"
        frame = cam.get_preview_frame()
        assert frame is not None
        assert frame.width == PREVIEW_WIDTH and frame.height == 360
        assert len(frame.rgb) == frame.width * frame.height * 3
    finally:
        cam.close()
    assert source.closed and cam.get_preview_frame() is None and not cam.is_open
    cam.close()  # closing twice is harmless


def test_open_twice_keeps_one_capture() -> None:
    cam, source = _service(ScriptedDecoder([]))
    cam.open()
    source.opened = False
    cam.open()
    assert not source.opened  # second open did not reopen the device
    cam.close()


# ------------------------------------------------------------------ real decoding


def _qr_image(text: str, scale: int = 8) -> np.ndarray:
    encoder = cv2.QRCodeEncoder.create()
    small = encoder.encode(text)
    big = cv2.resize(small, None, fx=scale, fy=scale, interpolation=cv2.INTER_NEAREST)
    padded = cv2.copyMakeBorder(big, 40, 40, 40, 40, cv2.BORDER_CONSTANT, value=255)
    return cv2.cvtColor(padded, cv2.COLOR_GRAY2BGR)


def test_decoder_reads_a_generated_qr_code() -> None:
    decoder = ZbarOpenCvDecoder()
    assert decoder.decode(_qr_image("PKM-000519")) == ["PKM-000519"]


def test_decoder_handles_grey_frames_and_blank_images() -> None:
    decoder = ZbarOpenCvDecoder()
    grey = cv2.cvtColor(_qr_image("PKM-123456"), cv2.COLOR_BGR2GRAY)
    assert decoder.decode(grey) == ["PKM-123456"]
    assert decoder.decode(np.full((480, 640, 3), 255, dtype=np.uint8)) == []


def test_camera_with_real_decoder_end_to_end() -> None:
    image = _qr_image("PKM-000777")

    class QrSource(FakeSource):
        def read(self) -> np.ndarray:
            return image.copy()

    settings = Settings(camera=CameraSettings(fps=30))
    cam = CameraService(lambda: settings, source_factory=lambda _s: QrSource())
    cam.open()
    try:
        assert cam.read_qr(3.0) == "PKM-000777"
    finally:
        cam.close()
