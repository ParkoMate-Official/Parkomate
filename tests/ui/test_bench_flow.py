"""The whole station on the bench test: the (fake) real board is flashed, the rest simulated."""

from __future__ import annotations

from pathlib import Path

from parkomate.core.enums import Stage
from parkomate.i18n import t
from tests.bench_fakes import APP, ComPort, make_bench
from tests.ui.conftest import DriverFactory


def test_full_device_on_the_bench_test(make_driver: DriverFactory, tmp_path: Path) -> None:
    ports = [ComPort("COM3", "Bluetooth link", None, None, None), ComPort("COM9")]
    hardware, flasher = make_bench(tmp_path / "build", ports)
    d = make_driver(hardware=hardware)
    d.start()
    d.login()
    d.ready_for_board()
    assert d.c.firmware is not None and d.c.firmware.name == "Blink.ino.bin"
    assert d.c.programming.selected_port == "COM9"  # the ESP32 bridge, not the Bluetooth port
    assert d.window.shell.band.isVisible()  # never looks like production

    chip = d.window.shell.top.mock
    assert chip.isVisible()
    assert chip.toolTip() == t("sim.tooltip_bench", scenario="bench-test · all_pass")

    d.through_programming()
    assert d.c.device is not None and d.c.device.mac_address == "24:6F:28:AA:BB:CC"
    assert [(name, offset) for name, offset, _ in flasher.written] == [
        ("bootloader", 0x1000),
        ("partitions", 0x8000),
        ("app", 0x10000),
    ]
    assert flasher.written[2][2] == APP
    d.through_testing()  # communication test passes: flashed and still plugged in
    d.through_labeling()
    d.through_packaging()
    assert d.c.stage is Stage.PROGRAMMING and d.c.device is None
    assert d.c.counters is not None and d.c.counters.completed == 1
