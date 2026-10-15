"""Faulty boards: a reject opens a repair case; repair → retest (whole line) → accept or scrap."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

import parkomate.data.migrate as migrate_module
from parkomate.config.settings import Settings
from parkomate.core.enums import (
    AmbientReason,
    CheckCode,
    DeviceStatus,
    IdEntryMethod,
    RepairAction,
    RepairEventKind,
    RepairStatus,
    ScrapReason,
    SessionEndReason,
    Stage,
)
from parkomate.core.errors import ErrorCode, InputError, RecordStateError
from parkomate.core.events import Event, EventBus, RepairCaseChanged
from parkomate.core.models import Measurement, Operator
from parkomate.data import Repositories, open_database
from parkomate.data.migrate import discover_migrations, migrate
from parkomate.data.records import ProductionRecords
from parkomate.data.recovery import recover_unclosed_sessions
from parkomate.reports.data import collect_report_data
from parkomate.reports.layout import build_session_tables
from parkomate.workflow import RepairService, WorkflowEngine

MAC = "24:6F:28:AA:BB:01"
OTHER_MAC = "24:6F:28:AA:BB:99"


def _measurement(**overrides: float) -> Measurement:
    values = {"v_a": 24.0, "v_b": 5.0, "v_c": 3.3, "t_reg_c": 28.5, "t_amb_c": 27.1}
    values.update(overrides)
    return Measurement(received_at=datetime.now(UTC), **values)


@pytest.fixture
def wf(open_session: ProductionRecords) -> WorkflowEngine:
    open_session.record_ambient(27.0, AmbientReason.SESSION_START)
    return WorkflowEngine(open_session, Settings)


@pytest.fixture
def repairs(open_session: ProductionRecords, repos: Repositories) -> RepairService:
    return RepairService(repos, open_session)


def _until_measure(wf: WorkflowEngine, mac: str, case_id: int | None = None) -> int:
    state = wf.start_device(mac, repair_case_id=case_id)
    wf.submit_check(CheckCode.A_WHITELIST, True)
    wf.submit_check(CheckCode.A_UPLOAD, True, text="2.3.1")
    wf.submit_and_next()
    wf.submit_check(CheckCode.B1_COMM, True)
    for i in range(1, 6):
        wf.submit_check(CheckCode.reading(i), 150.0)
    wf.submit_check(CheckCode.B2_SENSOR_OK, True)
    wf.submit_check(CheckCode.B2_INDICATOR_OK, True)
    return state.device_row_id


def reject_at_testing(wf: WorkflowEngine, mac: str = MAC, case_id: int | None = None) -> int:
    row = _until_measure(wf, mac, case_id)
    outcomes = wf.evaluate_measurement(_measurement(v_c=3.10))
    assert any(o.reject is not None for o in outcomes)
    wf.clear_finished()
    return row


def complete(wf: WorkflowEngine, mac: str = MAC, case_id: int | None = None) -> int:
    row = _until_measure(wf, mac, case_id)
    wf.evaluate_measurement(_measurement())
    wf.submit_and_next()
    wf.submit_check(CheckCode.C_QR_READ, "PKM-0001")
    wf.reconcile_identity("PKM-0001", "PKM-0001", method=IdEntryMethod.CAMERA)
    for code in (CheckCode.C1, CheckCode.C2, CheckCode.C3, CheckCode.C4):
        wf.submit_check(code, True)
    wf.submit_and_next()
    for code in (CheckCode.D1, CheckCode.D2, CheckCode.D3, CheckCode.D4):
        wf.submit_check(code, True)
    assert wf.submit_and_next() is Stage.COMPLETE
    wf.clear_finished()
    return row


def only_case(repos: Repositories) -> int:
    cases = repos.repairs.list_cases()
    assert len(cases) == 1
    return cases[0].id


# ------------------------------------------------------------------ opening


def test_reject_opens_a_case_complete_does_not(wf: WorkflowEngine, repos: Repositories) -> None:
    complete(wf, "24:6F:28:AA:BB:02")
    assert repos.repairs.list_cases() == []
    row = reject_at_testing(wf)
    case = repos.repairs.for_device(row)
    assert case is not None and case.status is RepairStatus.WAITING and case.mac_address == MAC
    events = repos.repairs.events_for_case(case.id)
    assert [e.event for e in events] == [RepairEventKind.OPENED]
    assert events[0].action == CheckCode.B3_V_C.value
    assert events[0].operator_id is not None and events[0].session_id is not None


def test_repair_events_are_append_only(wf: WorkflowEngine, repos: Repositories) -> None:
    reject_at_testing(wf)
    with pytest.raises(Exception, match="append-only"):
        repos.db.execute_script("UPDATE repair_events SET note = 'x';")


# ------------------------------------------------------------------ the whole flow


def test_repair_retest_pass_accept(
    wf: WorkflowEngine, repairs: RepairService, repos: Repositories
) -> None:
    published: list[Event] = []
    wf.records.bus.subscribe(RepairCaseChanged, published.append)
    reject_at_testing(wf)
    case_id = only_case(repos)
    case = repairs.get(case_id)
    assert repairs.retest_blocker(case) == "repair.gate.repair_first"
    assert repairs.accept_blocker(case) == "repair.gate.accept_after_pass"

    repairs.record_repair(case_id, RepairAction.REGULATOR_REPLACED, "  U3   swapped ")
    case = repairs.get(case_id)
    assert case.status is RepairStatus.REPAIRED and repairs.retest_blocker(case) is None
    assert published and isinstance(published[-1], RepairCaseChanged)

    row = complete(wf, MAC, case_id)
    device = repos.devices.require(row)
    assert device.repair_case_id == case_id and device.status is DeviceStatus.COMPLETE
    assert repairs.get(case_id).status is RepairStatus.PASSED

    accepted = repairs.accept(case_id)
    assert accepted.status is RepairStatus.ACCEPTED and accepted.closed_at is not None
    kinds = [e.event for e in repos.repairs.events_for_case(case_id)]
    assert kinds == [
        RepairEventKind.OPENED,
        RepairEventKind.REPAIRED,
        RepairEventKind.RETEST_STARTED,
        RepairEventKind.RETEST_PASSED,
        RepairEventKind.ACCEPTED,
    ]
    note = repos.repairs.events_for_case(case_id)[1].note
    assert note == "U3 swapped"
    detail = repairs.detail(case_id)
    assert detail.view.board_id == "PKM-0001"  # the QR ID from the retest run
    assert detail.view.retests == 1 and detail.view.repairs == 1
    assert repairs.list_cases(open_only=True) == []
    assert [v.case.id for v in repairs.list_cases(open_only=False)] == [case_id]


def test_failed_retest_goes_back_to_waiting(
    wf: WorkflowEngine, repairs: RepairService, repos: Repositories
) -> None:
    reject_at_testing(wf)
    case_id = only_case(repos)
    repairs.record_repair(case_id, RepairAction.SENSOR_REPLACED)
    retest_row = reject_at_testing(wf, MAC, case_id)
    assert repos.repairs.for_device(retest_row) is None  # no second case
    assert only_case(repos) == case_id
    case = repairs.get(case_id)
    assert case.status is RepairStatus.WAITING
    assert repos.repairs.events_for_case(case_id)[-1].event is RepairEventKind.RETEST_FAILED
    detail = repairs.detail(case_id)
    assert [f.device.id for f in detail.faults][-1] == retest_row
    assert detail.view.latest_fault.id == retest_row
    assert detail.faults[-1].failed_check is not None
    assert detail.faults[-1].failed_check.check_code is CheckCode.B3_V_C


def test_retest_needs_the_same_board(
    wf: WorkflowEngine, repairs: RepairService, repos: Repositories
) -> None:
    reject_at_testing(wf)
    case_id = only_case(repos)
    with pytest.raises(RecordStateError):  # not repaired yet
        wf.start_device(MAC, repair_case_id=case_id)
    repairs.record_repair(case_id, RepairAction.RESOLDERED)
    with pytest.raises(RecordStateError) as wrong:
        wf.start_device(OTHER_MAC, repair_case_id=case_id)
    assert wrong.value.code is ErrorCode.REPAIR_WRONG_BOARD
    assert wrong.value.params == {"expected": MAC, "found": OTHER_MAC}
    assert repairs.get(case_id).status is RepairStatus.REPAIRED
    assert wf.current_device() is None
    state = wf.start_device(MAC.lower(), repair_case_id=case_id)
    assert state.repair_case_id == case_id
    assert repairs.get(case_id).status is RepairStatus.RETESTING
    assert repairs.scrap_blocker(repairs.get(case_id)) == "repair.gate.on_line"


def test_cancelled_or_crashed_retest_goes_back_to_repaired(
    wf: WorkflowEngine,
    repairs: RepairService,
    repos: Repositories,
    open_session: ProductionRecords,
    operator: Operator,
) -> None:
    reject_at_testing(wf)
    case_id = only_case(repos)
    repairs.record_repair(case_id, RepairAction.NO_FAULT_FOUND)
    wf.start_device(MAC, repair_case_id=case_id)
    wf.abandon_device()
    case = repairs.get(case_id)
    assert case.status is RepairStatus.REPAIRED
    assert repos.repairs.events_for_case(case_id)[-1].event is RepairEventKind.RETEST_CANCELLED

    wf.start_device(MAC, repair_case_id=case_id)  # session ends with the retest running
    open_session.end_session(SessionEndReason.LOGOUT)
    assert repairs.get(case_id).status is RepairStatus.REPAIRED

    open_session.start_session(operator, language="en")
    open_session.record_ambient(27.0, AmbientReason.SESSION_START)
    fresh = WorkflowEngine(open_session, Settings)
    fresh.start_device(MAC, repair_case_id=case_id)  # power cut during the retest
    recovered = recover_unclosed_sessions(repos)
    assert recovered.recovered
    assert repairs.get(case_id).status is RepairStatus.REPAIRED


# ------------------------------------------------------------------ rules


def test_notes_and_scrap_rules(
    wf: WorkflowEngine, repairs: RepairService, repos: Repositories
) -> None:
    reject_at_testing(wf)
    case_id = only_case(repos)
    with pytest.raises(InputError):
        repairs.record_repair(case_id, RepairAction.OTHER, "   ")  # "other" needs a note
    with pytest.raises(InputError):
        repairs.record_repair(case_id, RepairAction.PART_REPLACED)
    with pytest.raises(InputError):
        repairs.scrap(case_id, ScrapReason.OTHER)
    with pytest.raises(InputError):
        repairs.record_repair(case_id, RepairAction.OTHER, "x" * 301)
    with pytest.raises(RecordStateError):
        repairs.accept(case_id)
    scrapped = repairs.scrap(case_id, ScrapReason.PHYSICAL_DAMAGE, "burnt track")
    assert scrapped.status is RepairStatus.SCRAPPED and scrapped.closed_at is not None
    for action in (
        lambda: repairs.record_repair(case_id, RepairAction.RESOLDERED),
        lambda: repairs.scrap(case_id, ScrapReason.NOT_REPAIRABLE),
        lambda: repairs.accept(case_id),
    ):
        with pytest.raises(RecordStateError):
            action()
    assert repairs.repair_blocker(scrapped) == "repair.gate.closed"
    last = repos.repairs.events_for_case(case_id)[-1]
    assert last.event is RepairEventKind.SCRAPPED and last.action == "physical_damage"


def test_scrap_after_a_passed_retest(
    wf: WorkflowEngine, repairs: RepairService, repos: Repositories
) -> None:
    reject_at_testing(wf)
    case_id = only_case(repos)
    repairs.record_repair(case_id, RepairAction.SENSOR_REPLACED)
    complete(wf, MAC, case_id)
    case = repairs.get(case_id)
    assert repairs.repair_blocker(case) == "repair.gate.already_passed"
    assert repairs.scrap(case_id, ScrapReason.NOT_WORTH_IT).status is RepairStatus.SCRAPPED


def test_repair_needs_a_logged_in_operator(
    wf: WorkflowEngine, repairs: RepairService, repos: Repositories, open_session: ProductionRecords
) -> None:
    reject_at_testing(wf)
    case_id = only_case(repos)
    open_session.end_session(SessionEndReason.LOGOUT)
    with pytest.raises(RecordStateError):
        repairs.record_repair(case_id, RepairAction.SENSOR_REPLACED)


def test_list_search_and_counts(
    wf: WorkflowEngine, repairs: RepairService, repos: Repositories
) -> None:
    reject_at_testing(wf, MAC)
    reject_at_testing(wf, OTHER_MAC)
    assert repairs.open_count() == 2
    assert [v.case.mac_address for v in repairs.list_cases(search="bb:99")] == [OTHER_MAC]
    assert [v.case.mac_address for v in repairs.list_cases(search="nothing")] == []
    first = repos.repairs.list_cases(search="BB:01")[0].id
    repairs.scrap(first, ScrapReason.NOT_REPAIRABLE)
    assert repairs.open_count() == 1
    assert [v.case.id for v in repairs.list_cases(open_only=False)] == [first]
    assert len(repairs.list_cases(open_only=None)) == 2


# ------------------------------------------------------------------ summary and report


def test_summary_and_repairs_sheet(
    wf: WorkflowEngine,
    repairs: RepairService,
    repos: Repositories,
    open_session: ProductionRecords,
) -> None:
    complete(wf, "24:6F:28:AA:BB:02")
    reject_at_testing(wf)
    case_id = only_case(repos)
    repairs.record_repair(case_id, RepairAction.REGULATOR_REPLACED, "U3")
    complete(wf, MAC, case_id)
    repairs.accept(case_id)
    session_id = open_session.require_session().id
    summary = open_session.session_summary(session_id)
    assert summary.total_devices == 3 and summary.complete == 2
    assert summary.retests == 1 and summary.retests_passed == 1
    assert summary.repairs_written == 1 and summary.repairs_accepted == 1
    assert summary.repairs_scrapped == 0
    # first-pass yield: 1 good first run out of 2 first runs - the retest does not count
    assert summary.first_pass_yield == 50.0

    data = collect_report_data(repos, [session_id], language="en", station_id="ST-TEST")
    tables = {t.key: t for t in build_session_tables(data)}
    sheet = tables["repairs"]
    assert sheet.title == "Repairs"
    steps = [row[sheet.headers.index("Step")] for row in sheet.rows]
    assert steps == ["Repaired", "Retest started", "Retest passed", "Accepted"]
    first = sheet.rows[0]
    assert first[sheet.headers.index("Repair / reason")] == "Voltage regulator replaced"
    assert first[sheet.headers.index("Note")] == "U3"
    assert first[sheet.headers.index("Box")] == "B"
    assert first[sheet.headers.index("Repair status")] == "Accepted"
    rejections = tables["rejections"]
    assert rejections.rows[0][rejections.headers.index("Repair case")] == case_id
    devices = tables["devices"]
    retest_of = [row[devices.headers.index("Retest of case")] for row in devices.rows]
    assert retest_of == [None, None, case_id]
    summary_rows = {row[0]: row[1] for row in tables["summary"].rows}
    assert summary_rows["Boards accepted after repair"] == 1


# ------------------------------------------------------------------ migration


def test_migration_opens_cases_for_old_rejects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A database from before the repair tab: its rejected boards get a waiting case."""
    every = discover_migrations()
    monkeypatch.setattr(migrate_module, "discover_migrations", lambda: every[:2])
    db = open_database(tmp_path / "old.db")
    db.execute_script(
        "INSERT INTO operators (id, operator_code, full_name, password_hash, role, created_at)"
        " VALUES (1, 'OP1', 'Omkar', 'x', 'operator', '2026-10-01T08:00:00+00:00');"
        "INSERT INTO sessions (id, operator_id, station_id, started_at, language)"
        " VALUES (1, 1, 'ST', '2026-10-01T08:00:00+00:00', 'en');"
        "INSERT INTO devices (id, session_id, mac_address, started_at, finished_at, status,"
        " reject_stage, reject_check_code) VALUES"
        " (1, 1, 'AA:BB:CC:DD:EE:01', '2026-10-01T08:01:00+00:00',"
        "  '2026-10-01T08:02:00+00:00', 'rejected', 'testing', 'B3_V_C'),"
        " (2, 1, 'AA:BB:CC:DD:EE:02', '2026-10-01T08:03:00+00:00',"
        "  '2026-10-01T08:04:00+00:00', 'complete', NULL, NULL);"
    )
    monkeypatch.setattr(migrate_module, "discover_migrations", lambda: every)
    migrate(db, backup_dir=tmp_path / "backups")
    rows = db.query("SELECT device_row_id, mac_address, status, opened_at FROM repair_cases")
    assert [tuple(r) for r in rows] == [
        (1, "AA:BB:CC:DD:EE:01", "waiting", "2026-10-01T08:02:00+00:00")
    ]
    events = db.query("SELECT event, operator_id, session_id FROM repair_events")
    assert [tuple(r) for r in events] == [("opened", 1, 1)]
    assert db.scalar("SELECT repair_case_id FROM devices WHERE id = 2") is None
    assert list((tmp_path / "backups").glob("*.db"))  # backed up before upgrading
    db.close()


def test_events_published_on_the_records_bus(
    open_session: ProductionRecords, repos: Repositories
) -> None:
    bus = EventBus()
    service = RepairService(repos, open_session, bus)
    seen: list[Event] = []
    bus.subscribe(Event, seen.append)
    wf = WorkflowEngine(open_session, Settings)
    open_session.record_ambient(27.0, AmbientReason.SESSION_START)
    reject_at_testing(wf)
    service.record_repair(only_case(repos), RepairAction.SENSOR_REPLACED)
    assert any(isinstance(e, RepairCaseChanged) for e in seen)
