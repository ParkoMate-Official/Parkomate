"""Collect everything a report needs from the database in one pass."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime

from parkomate.core.enums import CheckCode, RepairEventKind
from parkomate.core.models import (
    CheckResult,
    Device,
    Operator,
    RepairCase,
    RepairEventRecord,
    SessionSummary,
)
from parkomate.data import Repositories
from parkomate.reports.summary import build_session_summary


@dataclass(frozen=True, slots=True)
class DeviceRowContext:
    """One device plus the latest result of each of its checks."""

    device: Device
    latest: dict[CheckCode, CheckResult]
    upload_failures: int


@dataclass(frozen=True, slots=True)
class CheckRowContext:
    device: Device
    check: CheckResult


@dataclass(frozen=True, slots=True)
class RejectionRowContext:
    device: Device
    failed_check: CheckResult | None
    """The failing result of ``device.reject_check_code``, if one was recorded."""
    case: RepairCase | None = None
    """The repair case of the board (opened by this reject, or the retest's case)."""


@dataclass(frozen=True, slots=True)
class RepairRowContext:
    """One repair step done in a reported session (repair, retest, accept, scrap)."""

    event: RepairEventRecord
    case: RepairCase
    origin: Device
    """The rejected run that opened the case."""
    board_id: str
    operator: Operator | None


@dataclass(frozen=True, slots=True)
class ReportData:
    language: str
    station_id: str
    generated_at: datetime
    summaries: list[SessionSummary]
    devices: list[DeviceRowContext] = field(default_factory=list)
    checks: list[CheckRowContext] = field(default_factory=list)
    rejections: list[RejectionRowContext] = field(default_factory=list)
    repairs: list[RepairRowContext] = field(default_factory=list)

    @property
    def max_reading_index(self) -> int:
        """Highest sensor-reading slot used by any device (0 if none)."""
        highest = 0
        for row in self.devices:
            for code in row.latest:
                index = code.reading_index
                if index is not None:
                    highest = max(highest, index)
        return highest


def collect_report_data(
    repos: Repositories, session_ids: Sequence[int], *, language: str, station_id: str
) -> ReportData:
    """Load summaries, devices, checks and rejections for ``session_ids`` (in that order)."""
    summaries = [build_session_summary(repos, sid) for sid in session_ids]
    devices = repos.devices.list_for_sessions(list(session_ids))
    all_checks = repos.checks.list_for_devices([d.id for d in devices])
    by_device: dict[int, list[CheckResult]] = {}
    for check in all_checks:
        by_device.setdefault(check.device_row_id, []).append(check)

    device_rows: list[DeviceRowContext] = []
    check_rows: list[CheckRowContext] = []
    rejection_rows: list[RejectionRowContext] = []
    for device in devices:
        checks = by_device.get(device.id, [])
        latest: dict[CheckCode, CheckResult] = {}
        for check in checks:
            latest[check.check_code] = check
            check_rows.append(CheckRowContext(device, check))
        failures = sum(
            1 for c in checks if c.check_code is CheckCode.A_UPLOAD and c.passed is False
        )
        device_rows.append(DeviceRowContext(device, latest, failures))
        if device.reject_check_code is not None:
            failed = next(
                (
                    c
                    for c in reversed(checks)
                    if c.check_code is device.reject_check_code and c.passed is False
                ),
                None,
            )
            case = (
                repos.repairs.get(device.repair_case_id)
                if device.repair_case_id is not None
                else repos.repairs.for_device(device.id)
            )
            rejection_rows.append(RejectionRowContext(device, failed, case))

    return ReportData(
        language=language,
        station_id=station_id,
        generated_at=repos.clock.now(),
        summaries=summaries,
        devices=device_rows,
        checks=check_rows,
        rejections=rejection_rows,
        repairs=collect_repair_rows(repos, session_ids),
    )


def collect_repair_rows(repos: Repositories, session_ids: Sequence[int]) -> list[RepairRowContext]:
    """Repair steps done in ``session_ids`` (case openings are in the Rejections sheet)."""
    rows: list[RepairRowContext] = []
    cases: dict[int, tuple[RepairCase, Device, str]] = {}
    operators: dict[int, Operator | None] = {}
    for event in repos.repairs.events_for_sessions(list(session_ids)):
        if event.event is RepairEventKind.OPENED:
            continue
        if event.case_id not in cases:
            case = repos.repairs.require(event.case_id)
            origin = repos.devices.require(case.device_row_id)
            runs = repos.devices.list_for_repair_case(case.id)
            ids = [d.device_id for d in (origin, *runs) if d.device_id]
            cases[case.id] = (case, origin, ids[-1] if ids else case.mac_address)
        case, origin, board_id = cases[event.case_id]
        operator_id = event.operator_id
        if operator_id is not None and operator_id not in operators:
            operators[operator_id] = repos.operators.get(operator_id)
        operator = operators.get(operator_id) if operator_id is not None else None
        rows.append(RepairRowContext(event, case, origin, board_id, operator))
    return rows
