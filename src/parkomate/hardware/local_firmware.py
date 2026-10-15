"""Firmware from a local build folder - bench tests only.

Production downloads the firmware from the Parkomate server (:mod:`.server`). For a bench
test without the server the station can instead load a build from a folder on this PC,
e.g. the ``build/esp32`` folder Arduino CLI writes:

    Blink.ino.bootloader.bin   -> programming.bootloader_offset (0x1000 on ESP32)
    Blink.ino.partitions.bin   -> programming.partitions_offset (0x8000)
    Blink.ino.bin              -> programming.app_offset        (0x10000)

``bootloader.bin`` / ``partitions.bin`` / ``partition-table.bin`` are recognised too.
Without a bootloader and partition table only the application is written (the board must
already have a compatible bootloader). ``*.merged.bin`` and ``boot_app0.bin`` are ignored;
``.elf`` / ``.map`` are not ``.bin`` files. ``firmware_dir`` may also name one ``.bin`` file
(application only).

The folder comes from ``PARKOMATE_FIRMWARE_DIR`` (set by ``--firmware-dir``) or
``dev.firmware_dir``, read again on every load. Files are read straight into ``bytearray``
buffers that :class:`~parkomate.hardware.firmware.FirmwareStore` zeroes like downloaded
firmware. There is no trusted hash to compare against, so the result has
``hash_verified=False``; each image's header is checked instead (ESP image magic ``0xE9``,
partition table magic ``0xAA 0x50``).
"""

from __future__ import annotations

import hashlib
import logging
import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from parkomate.config.settings import ProgrammingSettings, Settings
from parkomate.core.errors import ErrorCode, HardwareError
from parkomate.core.models import FirmwareInfo
from parkomate.hardware.firmware import FirmwareImage, combined_sha256, zero

log = logging.getLogger(__name__)

ENV_FIRMWARE_DIR = "PARKOMATE_FIRMWARE_DIR"
MAX_IMAGE_BYTES = 16 * 1024 * 1024  # largest ESP32 flash

_IGNORED_SUFFIXES = (".merged.bin",)
_IGNORED_NAMES = ("boot_app0.bin",)
_BOOTLOADER_NAMES = ("bootloader.bin",)
_PARTITION_NAMES = ("partitions.bin", "partition-table.bin", "partition_table.bin")
_ESP_IMAGE_MAGIC = 0xE9
_PARTITION_MAGIC = b"\xaa\x50"


@dataclass(frozen=True, slots=True)
class PlannedImage:
    """One file of the local build and where it goes in flash."""

    name: str  # "bootloader" | "partitions" | "app"
    path: Path
    offset: int


def resolve_firmware_dir(configured: str) -> str:
    """``PARKOMATE_FIRMWARE_DIR`` wins over ``dev.firmware_dir``."""
    return (os.environ.get(ENV_FIRMWARE_DIR) or configured).strip()


def _invalid(message: str, path: Path | str) -> HardwareError:
    return HardwareError(
        message,
        code=ErrorCode.FW_LOCAL_INVALID,
        params={"path": str(path)},
        context={"path": str(path)},
    )


def _kind(file: Path) -> str | None:
    name = file.name.lower()
    if name in _IGNORED_NAMES or name.endswith(_IGNORED_SUFFIXES):
        return None
    if name in _BOOTLOADER_NAMES or name.endswith(".bootloader.bin"):
        return "bootloader"
    if name in _PARTITION_NAMES or name.endswith(".partitions.bin"):
        return "partitions"
    return "app"


def plan_images(location: str | Path, programming: ProgrammingSettings) -> list[PlannedImage]:
    """Which files of ``location`` are written where, lowest offset first."""
    if not str(location).strip():
        raise _invalid("no local firmware folder set (dev.firmware_dir / --firmware-dir)", "-")
    path = Path(location).expanduser()
    if path.is_file():
        if path.suffix.lower() != ".bin":
            raise _invalid(f"{path} is not a .bin file", path)
        return [PlannedImage("app", path, programming.app_offset)]
    if not path.is_dir():
        raise _invalid(f"firmware folder {path} does not exist", path)
    found: dict[str, list[Path]] = {"bootloader": [], "partitions": [], "app": []}
    for file in sorted(path.iterdir()):
        if file.is_file() and file.suffix.lower() == ".bin":
            kind = _kind(file)
            if kind is not None:
                found[kind].append(file)
    for kind, files in found.items():
        if len(files) > 1:
            names = ", ".join(f.name for f in files)
            raise _invalid(f"more than one {kind} image in {path}: {names}", path)
    if not found["app"]:
        raise _invalid(f"no application .bin in {path}", path)
    offsets = {
        "bootloader": programming.bootloader_offset,
        "partitions": programming.partitions_offset,
        "app": programming.app_offset,
    }
    plan = [PlannedImage(kind, files[0], offsets[kind]) for kind, files in found.items() if files]
    plan.sort(key=lambda image: image.offset)
    if len({image.offset for image in plan}) != len(plan):
        raise _invalid(
            "two firmware images share a flash offset - check programming.*_offset", path
        )
    return plan


def _read(planned: PlannedImage) -> bytearray:
    path = planned.path
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise _invalid(f"cannot read {path}: {exc}", path) from exc
    if size == 0 or size > MAX_IMAGE_BYTES:
        raise _invalid(f"{path.name} has an impossible size ({size} bytes)", path)
    data = bytearray(size)  # pre-sized: never reallocated, so no stale copy is left
    received = 0
    try:
        with path.open("rb", buffering=0) as handle, memoryview(data) as view:
            while received < size:
                count = handle.readinto(view[received:])
                if not count:
                    break
                received += count
    except OSError as exc:
        zero(data)
        raise _invalid(f"cannot read {path}: {exc}", path) from exc
    if received != size:
        zero(data)
        raise _invalid(f"{path.name} changed while it was read", path)
    if planned.name == "partitions":
        valid = data[:2] == _PARTITION_MAGIC
    else:
        valid = data[0] == _ESP_IMAGE_MAGIC
    if not valid:
        zero(data)
        raise _invalid(f"{path.name} is not an ESP32 {planned.name} image (wrong header)", path)
    return data


class LocalFirmwareSource:
    """Loads a local build into RAM (bench test). Same result shape as the server client."""

    def __init__(self, settings: Callable[[], Settings]) -> None:
        self._settings = settings

    def location(self) -> str:
        return resolve_firmware_dir(self._settings().dev.firmware_dir)

    def plan(self) -> list[PlannedImage]:
        return plan_images(self.location(), self._settings().programming)

    def fetch_firmware(self) -> tuple[FirmwareInfo, list[FirmwareImage]]:
        plan = self.plan()
        images: list[FirmwareImage] = []
        try:
            for planned in plan:
                data = _read(planned)
                images.append(
                    FirmwareImage(
                        name=planned.name,
                        offset=planned.offset,
                        data=data,
                        sha256=hashlib.sha256(data).hexdigest(),
                    )
                )
        except BaseException:
            for image in images:
                zero(image.data)
            raise
        app = next(p for p in plan if p.name == "app")
        built = datetime.fromtimestamp(app.path.stat().st_mtime)
        info = FirmwareInfo(
            name=app.path.name,
            version=f"local {built:%Y-%m-%d %H:%M}",
            sha256=combined_sha256(images),
            size=sum(len(i.data) for i in images),
            hash_verified=False,
        )
        log.warning(
            "BENCH TEST: firmware %s loaded from %s (%s) - not from the server",
            info.name,
            app.path.parent,
            ", ".join(f"{i.name}@0x{i.offset:X}" for i in images),
        )
        return info, images
