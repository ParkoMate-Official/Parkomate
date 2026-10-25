"""Hardware-in-the-loop (HIL) fixtures: the REAL bench, never run by a plain ``pytest``.

Enable on the bench PC::

    set PARKOMATE_HIL=1
    set PARKOMATE_HIL_PORT=COM5                      (optional: else the first ESP32 bridge)
    set PARKOMATE_HIL_SETTINGS=C:\\ProgramData\\Parkomate\\settings.toml   (optional)
    uv run pytest -m hil -v

``PARKOMATE_HIL_FULL=1`` additionally runs the tests that talk to the server and flash the
board. See ``docs/HIL_TESTING.md`` for the wiring and the golden-board requirements.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from parkomate.config.manager import load_settings_file
from parkomate.config.secrets import KeyringSecretStore
from parkomate.config.settings import Settings
from parkomate.core.enums import AmbientReason
from parkomate.data.records import ProductionRecords
from parkomate.hardware import RealHardwareService
from parkomate.workflow import WorkflowEngine

ENV_HIL = "PARKOMATE_HIL"
ENV_FULL = "PARKOMATE_HIL_FULL"
ENV_PORT = "PARKOMATE_HIL_PORT"
ENV_SETTINGS = "PARKOMATE_HIL_SETTINGS"


def _on(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    here = Path(__file__).parent
    hil = pytest.mark.skip(reason=f"real bench only: set {ENV_HIL}=1")
    full = pytest.mark.skip(reason=f"server + flashing: set {ENV_FULL}=1")
    for item in items:
        if here not in Path(str(item.fspath)).parents:
            continue
        item.add_marker(pytest.mark.hil)
        if not _on(ENV_HIL):
            item.add_marker(hil)
        elif item.get_closest_marker("hil_full") and not _on(ENV_FULL):
            item.add_marker(full)


@pytest.fixture(scope="session")
def bench_settings() -> Settings:
    path = os.environ.get(ENV_SETTINGS)
    settings = load_settings_file(Path(path)) if path else Settings()
    if settings.dev.use_mock_hardware:
        pytest.fail("the HIL settings file has dev.use_mock_hardware = true")
    return settings


@pytest.fixture
def hardware(bench_settings: Settings) -> Iterator[RealHardwareService]:
    service = RealHardwareService(lambda: bench_settings, KeyringSecretStore())
    yield service
    service.shutdown()


@pytest.fixture
def port(hardware: RealHardwareService) -> str:
    wanted = os.environ.get(ENV_PORT, "").strip()
    ports = hardware.list_ports()
    if wanted:
        if not any(p.name == wanted for p in ports):
            pytest.fail(f"{ENV_PORT}={wanted} is not connected; ports: {[p.name for p in ports]}")
        return wanted
    candidates = [p.name for p in ports if p.is_esp_candidate]
    if not candidates:
        pytest.fail(f"no ESP32 USB bridge found; ports: {[p.name for p in ports]}")
    return candidates[0]


@pytest.fixture
def connected(hardware: RealHardwareService, port: str) -> RealHardwareService:
    hardware.connect(port)
    return hardware


@pytest.fixture
def bench_workflow(
    open_session: ProductionRecords, bench_settings: Settings, connected: RealHardwareService
) -> WorkflowEngine:
    """Workflow on a scratch database with the session-start ambient from the real device."""
    open_session.record_ambient(connected.measure_ambient(), AmbientReason.SESSION_START)
    return WorkflowEngine(open_session, lambda: bench_settings)
