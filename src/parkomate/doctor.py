"""``python -m parkomate doctor`` - is this PC ready to run the station?

Run it after installing on a new PC (or before a demo). Every line is OK / WARN / FAIL with
a short explanation; the exit code is 1 when anything FAILs. It only reads - except that, like
the station itself, it creates the data folder and database when they do not exist yet.
"""

from __future__ import annotations

import contextlib
import importlib
import socket
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from functools import partial
from typing import Any

from parkomate import __version__
from parkomate.app_paths import AppPaths
from parkomate.config.manager import load_settings_file
from parkomate.config.secrets import KeyringSecretStore, SecretStore
from parkomate.config.settings import Settings
from parkomate.core.errors import ParkomateError


class Level(StrEnum):
    OK = "ok"
    WARN = "warn"
    FAIL = "fail"


@dataclass(frozen=True, slots=True)
class Finding:
    level: Level
    key: str
    """i18n key of the line (``cli.doctor.*``)."""
    params: dict[str, Any] = field(default_factory=dict)


def _try(fn: Callable[[], Finding]) -> Finding:
    try:
        return fn()
    except Exception as exc:  # a broken PC must still get a full report
        return Finding(Level.FAIL, "cli.doctor.crashed", {"error": f"{type(exc).__name__}: {exc}"})


def run_checks(paths: AppPaths | None = None, secrets: SecretStore | None = None) -> list[Finding]:
    paths = paths or AppPaths.default()
    findings: list[Finding] = [
        Finding(
            Level.OK,
            "cli.doctor.version",
            {"version": __version__, "python": sys.version.split()[0]},
        )
    ]
    findings.append(_try(lambda: _data_folder(paths)))
    settings_holder: list[Settings] = []
    findings.append(_try(lambda: _settings(paths, settings_holder)))
    settings = settings_holder[0] if settings_holder else Settings()
    findings.append(
        Finding(Level.OK, "cli.doctor.station", {"station": settings.station.station_id})
    )
    findings.append(_try(lambda: _mode(settings)))
    findings.append(_try(lambda: _database(paths)))
    for module, key in (
        ("esptool", "cli.doctor.lib_esptool"),
        ("serial", "cli.doctor.lib_serial"),
        ("cv2", "cli.doctor.lib_camera"),
        ("openpyxl", "cli.doctor.lib_excel"),
    ):
        findings.append(_try(partial(_library, module, key)))
    findings.append(_try(_qr_decoder))
    findings.append(_try(_ports))
    findings.append(_try(lambda: _network(settings)))
    findings.append(_try(lambda: _listen_port(settings)))
    findings.append(_try(lambda: _email(settings, secrets or KeyringSecretStore())))
    return findings


def _data_folder(paths: AppPaths) -> Finding:
    paths.ensure()
    probe = paths.root / ".doctor-write-test"
    probe.write_text("ok", encoding="utf-8")
    probe.unlink()
    return Finding(Level.OK, "cli.doctor.data_ok", {"path": str(paths.root)})


def _settings(paths: AppPaths, holder: list[Settings]) -> Finding:
    if not paths.settings_file.exists():
        return Finding(
            Level.WARN, "cli.doctor.settings_default", {"path": str(paths.settings_file)}
        )
    try:
        holder.append(load_settings_file(paths.settings_file))
    except ParkomateError as exc:
        return Finding(
            Level.FAIL,
            "cli.doctor.settings_bad",
            {"path": str(paths.settings_file), "error": exc.message},
        )
    return Finding(Level.OK, "cli.doctor.settings_ok", {"path": str(paths.settings_file)})


def _mode(settings: Settings) -> Finding:
    dev = settings.dev
    if dev.use_mock_hardware:
        key = "cli.doctor.mode_mock"
    elif dev.bench_test:
        key = "cli.doctor.mode_bench"
    else:
        key = "cli.doctor.mode_real"
    level = Level.OK if key == "cli.doctor.mode_real" else Level.WARN
    wifi = dev.real_measuring_device and key != "cli.doctor.mode_real"
    return Finding(level, key, {"wifi": "✓" if wifi else "-"})


def _database(paths: AppPaths) -> Finding:
    from parkomate.data import open_database
    from parkomate.data.migrate import current_version

    db = open_database(paths.database_file, backup_dir=paths.backups_dir)
    try:
        version = current_version(db)
        admins = db.scalar("SELECT COUNT(*) FROM operators WHERE role = 'admin' AND is_active = 1")
    finally:
        db.close()
    if not admins:
        return Finding(Level.FAIL, "cli.doctor.no_admin", {"version": version})
    return Finding(Level.OK, "cli.doctor.db_ok", {"version": version, "admins": admins})


def _library(module: str, key: str) -> Finding:
    try:
        importlib.import_module(module)
    except Exception as exc:
        return Finding(Level.FAIL, key, {"state": f"{type(exc).__name__}: {exc}"})
    return Finding(Level.OK, key, {"state": "OK"})


def _qr_decoder() -> Finding:
    """ZBar is best; without it (its DLL needs the Visual C++ 2013 runtime) OpenCV decodes."""
    zbar = _library("pyzbar.pyzbar", "cli.doctor.lib_qr")
    if zbar.level is Level.OK:
        return zbar
    opencv = _library("cv2", "cli.doctor.lib_camera")
    if opencv.level is Level.OK:
        return Finding(Level.WARN, "cli.doctor.lib_qr_fallback", zbar.params)
    return zbar


def _ports() -> Finding:
    from parkomate.hardware.ports import PortScanner

    ports = PortScanner().list_ports()
    esp = [p.name for p in ports if p.is_esp_candidate]
    names = ", ".join(f"{p.name}{'*' if p.is_esp_candidate else ''}" for p in ports) or "-"
    level = Level.OK if esp else Level.WARN
    return Finding(level, "cli.doctor.ports", {"ports": names, "esp": len(esp)})


def _network(settings: Settings) -> Finding:
    from parkomate.hardware.measurement import local_ipv4_addresses

    m = settings.measurement
    addresses = local_ipv4_addresses()
    if not addresses:
        return Finding(Level.FAIL, "cli.doctor.no_network", {})
    urls = ", ".join(f"http://{a}:{m.listen_port}{m.path}" for a in addresses)
    return Finding(Level.OK, "cli.doctor.network", {"urls": urls, "allowed": m.allowed_ip})


def _listen_port(settings: Settings) -> Finding:
    m = settings.measurement
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind((m.listen_host, m.listen_port))
        except OSError:
            return Finding(Level.WARN, "cli.doctor.port_busy", {"port": m.listen_port})
    return Finding(Level.OK, "cli.doctor.port_free", {"port": m.listen_port})


def _email(settings: Settings, secrets: SecretStore) -> Finding:
    email = settings.email
    if not email.enabled:
        return Finding(Level.WARN, "cli.doctor.mail_off", {})
    if email.security != "none" and email.auth_method == "password":
        secret: str | None = None
        with contextlib.suppress(ParkomateError):
            secret = secrets.get(email.password_ref)
        if not secret:
            return Finding(Level.FAIL, "cli.doctor.mail_no_password", {"ref": email.password_ref})
    return Finding(
        Level.OK,
        "cli.doctor.mail_ok",
        {"host": email.host, "port": email.port, "to": ", ".join(email.recipients)},
    )
