"""RepairService - faulty boards: repair, test again, then accept or scrap (owner: Piyush).

The client's flow (October 2026): *"First boards will be repaired, then tested and then
either scrapped or accepted."*

    rejected ──► waiting ──repair──► repaired ──Test again──► retesting
                   ▲  │                 │  ▲                     │
                   │  └─── scrap ───────┤  └── cancelled ────────┤
                   │                    ▼                        ├─ completed ─► passed ─► Accept
                   └──────── failed again ◄──────────────────────┘                  └──► Scrap

* A case opens by itself when a first run is rejected (``data.repair_links``).
* **Test again** = the whole line again (A → D) as a new device run linked to the case
  (``WorkflowService.start_device(mac, repair_case_id=...)``); the board's MAC must match.
* **Accept** only after a passed retest; **Scrap** at any time except while the board is on
  the line, and needs a reason.
* Everyone who is logged in may repair; every step is stored with the session and operator,
  so it appears in that person's session report.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field

from parkomate.core.enums import (
    DeviceStatus,
    RepairAction,
    RepairEventKind,
    RepairStatus,
    ScrapReason,
)
from parkomate.core.errors import InputError, RecordStateError
from parkomate.core.events import EventBus, RepairCaseChanged
from parkomate.core.models import (
    CheckResult,
    Device,
    Operator,
    RepairCase,
    RepairEventRecord,
)
from parkomate.data import Repositories
from parkomate.data.records import ProductionRecords

log = logging.getLogger(__name__)

NOTE_MAX = 300
REPAIRABLE = (RepairStatus.WAITING, RepairStatus.REPAIRED)
SCRAPPABLE = (RepairStatus.WAITING, RepairStatus.REPAIRED, RepairStatus.PASSED)


@dataclass(frozen=True, slots=True)
class Fault:
    """One rejected run of the board and the check that failed."""

    device: Device
    failed_check: CheckResult | None


@dataclass(frozen=True, slots=True)
class RepairCaseView:
    """One row of the faulty-boards list."""

    case: RepairCase
    origin: Device
    """The rejected run that opened the case."""
    board_id: str
    """QR ID when any run of the board had one, else the MAC."""
    latest_fault: Device
    """The most recent rejected run (the origin, or a failed retest)."""
    repairs: int = 0
    retests: int = 0


@dataclass(frozen=True, slots=True)
class RepairCaseDetail:
    view: RepairCaseView
    faults: list[Fault] = field(default_factory=list)
    """Every rejected run, oldest first."""
    events: list[RepairEventRecord] = field(default_factory=list)
    runs: list[Device] = field(default_factory=list)
    """Retest runs, oldest first."""
    operators: dict[int, Operator] = field(default_factory=dict)

    @property
    def case(self) -> RepairCase:
        return self.view.case

    def operator_name(self, operator_id: int | None) -> str:
        operator = self.operators.get(operator_id) if operator_id is not None else None
        return f"{operator.full_name} ({operator.operator_code})" if operator else ""


class RepairService:
    def __init__(
        self, repos: Repositories, records: ProductionRecords, bus: EventBus | None = None
    ) -> None:
        self._repos = repos
        self._records = records
        self._bus = bus or records.bus

    # ================================================================== reading
    def list_cases(
        self, *, open_only: bool | None = True, search: str = ""
    ) -> list[RepairCaseView]:
        cases = self._repos.repairs.list_cases(open_only=open_only, search=search)
        return [self._view(case) for case in cases]

    def open_count(self) -> int:
        counts = self._repos.repairs.counts()
        return sum(n for status, n in counts.items() if status.is_open)

    def get(self, case_id: int) -> RepairCase:
        return self._repos.repairs.require(case_id)

    def detail(self, case_id: int) -> RepairCaseDetail:
        case = self._repos.repairs.require(case_id)
        view = self._view(case)
        runs = self._repos.devices.list_for_repair_case(case.id)
        rejected = [view.origin, *(r for r in runs if r.status is DeviceStatus.REJECTED)]
        faults = [Fault(device, self._failed_check(device)) for device in rejected]
        events = self._repos.repairs.events_for_case(case.id)
        operators: dict[int, Operator] = {}
        for event in events:
            if event.operator_id is not None and event.operator_id not in operators:
                operator = self._repos.operators.get(event.operator_id)
                if operator is not None:
                    operators[operator.id] = operator
        return RepairCaseDetail(view, faults, events, runs, operators)

    def _view(self, case: RepairCase) -> RepairCaseView:
        origin = self._repos.devices.require(case.device_row_id)
        runs = self._repos.devices.list_for_repair_case(case.id)
        ids = [d.device_id for d in (origin, *runs) if d.device_id]
        latest = next((r for r in reversed(runs) if r.status is DeviceStatus.REJECTED), origin)
        events = self._repos.repairs.events_for_case(case.id)
        repairs = sum(1 for e in events if e.event is RepairEventKind.REPAIRED)
        return RepairCaseView(
            case=case,
            origin=origin,
            board_id=ids[-1] if ids else case.mac_address,
            latest_fault=latest,
            repairs=repairs,
            retests=len(runs),
        )

    def _failed_check(self, device: Device) -> CheckResult | None:
        if device.reject_check_code is None:
            return None
        checks = self._repos.checks.list_for_device(device.id)
        return next(
            (
                c
                for c in reversed(checks)
                if c.check_code is device.reject_check_code and c.passed is False
            ),
            None,
        )

    # ================================================================== gates
    @staticmethod
    def retest_blocker(case: RepairCase) -> str | None:
        """i18n reason why "Test again" is not possible, ``None`` when it is."""
        return {
            RepairStatus.WAITING: "repair.gate.repair_first",
            RepairStatus.RETESTING: "repair.gate.on_line",
            RepairStatus.PASSED: "repair.gate.already_passed",
            RepairStatus.ACCEPTED: "repair.gate.closed",
            RepairStatus.SCRAPPED: "repair.gate.closed",
        }.get(case.status)

    @staticmethod
    def accept_blocker(case: RepairCase) -> str | None:
        if case.status is RepairStatus.PASSED:
            return None
        if not case.status.is_open:
            return "repair.gate.closed"
        return "repair.gate.accept_after_pass"

    @staticmethod
    def scrap_blocker(case: RepairCase) -> str | None:
        if case.status in SCRAPPABLE:
            return None
        if case.status is RepairStatus.RETESTING:
            return "repair.gate.on_line"
        return "repair.gate.closed"

    @staticmethod
    def repair_blocker(case: RepairCase) -> str | None:
        if case.status in REPAIRABLE:
            return None
        if case.status is RepairStatus.PASSED:
            return "repair.gate.already_passed"
        if case.status is RepairStatus.RETESTING:
            return "repair.gate.on_line"
        return "repair.gate.closed"

    # ================================================================== actions
    def record_repair(self, case_id: int, action: RepairAction, note: str = "") -> RepairCase:
        """The technician wrote what was repaired. Another repair may follow."""
        text = _clean_note(note, required=action.needs_note)
        return self._step(
            case_id,
            RepairStatus.REPAIRED,
            REPAIRABLE,
            RepairEventKind.REPAIRED,
            action.value,
            text,
            self.repair_blocker,
        )

    def accept(self, case_id: int) -> RepairCase:
        """The retest passed every stage: the board is good."""
        return self._step(
            case_id,
            RepairStatus.ACCEPTED,
            (RepairStatus.PASSED,),
            RepairEventKind.ACCEPTED,
            None,
            None,
            self.accept_blocker,
        )

    def scrap(self, case_id: int, reason: ScrapReason, note: str = "") -> RepairCase:
        text = _clean_note(note, required=reason.needs_note)
        return self._step(
            case_id,
            RepairStatus.SCRAPPED,
            SCRAPPABLE,
            RepairEventKind.SCRAPPED,
            reason.value,
            text,
            self.scrap_blocker,
        )

    def _step(
        self,
        case_id: int,
        status: RepairStatus,
        expected: tuple[RepairStatus, ...],
        event: RepairEventKind,
        action: str | None,
        note: str | None,
        blocker: Callable[[RepairCase], str | None],
    ) -> RepairCase:
        session = self._records.require_session()
        operator = self._records.require_operator()
        repos = self._repos
        case = repos.repairs.require(case_id)
        if case.status not in expected:
            reason = blocker(case)
            raise RecordStateError(
                f"repair case {case_id} is {case.status.value}: cannot {event.value}",
                context={"case_id": case_id, "reason_key": reason},
            )
        with repos.db.transaction():
            repos.repairs.set_status(case_id, status, expected=expected)
            repos.repairs.add_event(
                case_id,
                event,
                session_id=session.id,
                operator_id=operator.id,
                action=action,
                note=note,
            )
        log.info("repair case %d: %s by %s", case_id, event.value, operator.operator_code)
        self._bus.publish(RepairCaseChanged(case_id))
        return repos.repairs.require(case_id)


def _clean_note(note: str, *, required: bool) -> str | None:
    text = " ".join(note.split())
    if required and not text:
        raise InputError("write what was done", params={"key": "repair.note_required"})
    if len(text) > NOTE_MAX:
        raise InputError(f"note longer than {NOTE_MAX} characters")
    return text or None
