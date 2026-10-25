"""Records API for the multi-worker line: claim, pass, release, queue, find, history."""

from __future__ import annotations

from pathlib import Path

import pytest

import parkomate.data.migrate as migrate_module
from parkomate.auth.service import AuthService
from parkomate.core.clock import FakeClock
from parkomate.core.enums import (
    CheckCode,
    CounterEvent,
    DeviceStatus,
    IdentifyBy,
    IdEntryMethod,
    OpCode,
    Role,
    RunOutcome,
    SessionEndReason,
    Stage,
)
from parkomate.core.errors import DatabaseError, InputError, RecordStateError
from parkomate.core.events import DeviceAbandoned, DeviceReleased, EventBus
from parkomate.core.models import Operator
from parkomate.data import Repositories, open_database
from parkomate.data.migrate import discover_migrations, migrate
from parkomate.data.records import ProductionRecords
from parkomate.data.recovery import recover_unclosed_sessions

MAC = "24:6F:28:AA:BB:01"
MAC2 = "24:6F:28:AA:BB:02"
PASSWORD = "secret-pass-1"


@pytest.fixture
def station2(
    repos: Repositories, bus: EventBus, auth: AuthService, admin: Operator
) -> ProductionRecords:
    """A second station on the same database, with its own worker logged in."""
    worker = auth.create_operator(admin, "OP2", "Second Worker", PASSWORD, Role.OPERATOR)
    other = ProductionRecords(repos, station_id="ST-TWO", bus=bus)
    other.start_session(worker, language="en")
    return other


def _program(r: ProductionRecords, mac: str = MAC) -> int:
    """New board through A on this bench; it then waits for B_TEST."""
    row = r.start_device(mac)
    r.record_check(row, Stage.PROGRAMMING, CheckCode.A_WHITELIST, passed=True)
    r.record_check(row, Stage.PROGRAMMING, CheckCode.A_UPLOAD, passed=True)
    assert r.pass_run() is OpCode.B_TEST
    return row


def test_new_board_is_on_the_bench_for_programming(open_session: ProductionRecords) -> None:
    row = open_session.start_device(MAC)
    run = open_session.open_run()
    assert run is not None and run.is_open
    assert (run.device_row_id, run.op_code, run.identified_by) == (
        row,
        OpCode.A_PROGRAM,
        IdentifyBy.NEW,
    )
    assert run.station_id == "ST-TEST"
    assert open_session.active_device() == open_session.get_device(row)
    assert open_session.get_device(row).next_op is OpCode.A_PROGRAM


def test_pass_moves_the_board_to_the_next_tray(open_session: ProductionRecords) -> None:
    row = _program(open_session)
    assert open_session.open_run() is None and open_session.active_device() is None
    device = open_session.get_device(row)
    assert device.status is DeviceStatus.IN_PROGRESS and device.next_op is OpCode.B_TEST
    assert open_session.queue(OpCode.B_TEST) == [device]
    assert open_session.queue(OpCode.A_PROGRAM) == []
    counts = open_session.queue_counts()
    assert counts[OpCode.B_TEST] == 1 and sum(counts.values()) == 1
    with pytest.raises(RecordStateError, match="no board on the bench"):
        open_session.pass_run()


def test_one_board_on_a_bench(open_session: ProductionRecords) -> None:
    first = _program(open_session)
    open_session.start_device(MAC2)
    with pytest.raises(RecordStateError, match="still on the bench"):
        open_session.claim(first, OpCode.B_TEST, IdentifyBy.MAC)
    with pytest.raises(RecordStateError, match="still on the bench"):
        open_session.start_device("24:6F:28:AA:BB:03")


def test_claim_rules(open_session: ProductionRecords, station2: ProductionRecords) -> None:
    row = _program(open_session)
    with pytest.raises(InputError):
        open_session.claim(row, OpCode.B_TEST, IdentifyBy.NEW)
    with pytest.raises(RecordStateError, match="waits for B_TEST") as wrong:
        open_session.claim(row, OpCode.C_CODE, IdentifyBy.MAC)
    assert wrong.value.context["next_op"] == OpCode.B_TEST
    run = open_session.claim(row, OpCode.B_TEST, IdentifyBy.MAC)
    assert run.op_code is OpCode.B_TEST and run.identified_by is IdentifyBy.MAC
    with pytest.raises(RecordStateError, match="on the bench of ST-TEST") as taken:
        station2.claim(row, OpCode.B_TEST, IdentifyBy.QR)
    assert taken.value.context["station_id"] == "ST-TEST"


def test_a_board_continues_at_another_station(
    open_session: ProductionRecords, station2: ProductionRecords
) -> None:
    row = _program(open_session)
    run = station2.claim(row, OpCode.B_TEST, IdentifyBy.MAC)
    check = station2.record_check(row, Stage.TESTING, CheckCode.B1_COMM, passed=True)
    assert check.run_id == run.id
    with pytest.raises(RecordStateError, match="not on this session's bench"):
        open_session.record_check(row, Stage.TESTING, CheckCode.B1_COMM, passed=True)
    assert station2.pass_run() is OpCode.C_CODE
    history = station2.device_history(row)
    assert history.passed_ops == [OpCode.A_PROGRAM, OpCode.B_TEST]
    assert [r.station_id for r in history.runs] == ["ST-TEST", "ST-TWO"]
    assert {r.operator_id for r in history.runs} == {
        open_session.require_operator().id,
        station2.require_operator().id,
    }


def test_release_keeps_the_board_waiting(open_session: ProductionRecords, bus: EventBus) -> None:
    seen: list[DeviceReleased] = []
    bus.subscribe(DeviceReleased, seen.append)
    assert open_session.release_run() is None  # empty bench: nothing to release
    row = _program(open_session)
    open_session.claim(row, OpCode.B_TEST, IdentifyBy.MAC)
    open_session.record_check(row, Stage.TESTING, CheckCode.B1_COMM, passed=True)
    released = open_session.release_run()
    assert released is not None and released.outcome is RunOutcome.RELEASED
    assert seen == [DeviceReleased(row, OpCode.B_TEST)]
    device = open_session.get_device(row)
    assert device.status is DeviceStatus.IN_PROGRESS and device.next_op is OpCode.B_TEST
    assert open_session.queue(OpCode.B_TEST) == [device]
    history = open_session.device_history(row)
    assert history.passed_ops == [OpCode.A_PROGRAM]  # the half-done step does not count
    assert history.checks[-1].run_id == released.id  # but its results stay in the history
    assert history.open_run is None


def test_end_session_releases_the_board(
    open_session: ProductionRecords, operator: Operator
) -> None:
    row = _program(open_session)
    open_session.claim(row, OpCode.B_TEST, IdentifyBy.MAC)
    open_session.end_session(SessionEndReason.LOGOUT)
    entry = open_session.repos.audit.list_entries(action="session.end")[0]
    assert entry.details["released"] == [row]
    open_session.start_session(operator, language="en")
    assert open_session.queue(OpCode.B_TEST)[0].id == row
    open_session.claim(row, OpCode.B_TEST, IdentifyBy.MAC)  # anyone may continue it


def test_new_board_refused_when_already_in_progress(open_session: ProductionRecords) -> None:
    row = _program(open_session)
    with pytest.raises(RecordStateError, match="already in progress") as known:
        open_session.start_device(MAC.lower().replace(":", "-"))
    assert known.value.context == {"device_row_id": row, "next_op": OpCode.B_TEST}


def _last_outcome(r: ProductionRecords, row: int) -> RunOutcome | None:
    run = r.repos.runs.latest_for_device(row)
    return None if run is None else run.outcome


def test_finished_boards_wait_for_nothing(open_session: ProductionRecords) -> None:
    good = open_session.start_device(MAC)
    assert open_session.complete_device(good).next_op is None
    assert _last_outcome(open_session, good) is RunOutcome.PASSED
    bad = open_session.start_device(MAC2)
    rejected = open_session.reject_device(
        bad, Stage.PROGRAMMING, CheckCode.A_UPLOAD, "reject.reason.manual"
    )
    assert rejected.next_op is None
    assert _last_outcome(open_session, bad) is RunOutcome.REJECTED
    assert sum(open_session.queue_counts().values()) == 0
    with pytest.raises(RecordStateError, match="already complete"):
        open_session.claim(good, OpCode.A_PROGRAM, IdentifyBy.MAC)
    again = open_session.start_device(MAC)  # a finished MAC may start a new row
    assert again != good


def test_last_step_completes_instead_of_passing(open_session: ProductionRecords) -> None:
    row = open_session.start_device(MAC)
    for _ in range(len(OpCode) - 1):
        following = open_session.pass_run()
        open_session.claim(row, following, IdentifyBy.QR)
    assert open_session.open_run().op_code is OpCode.D_PACK  # type: ignore[union-attr]
    with pytest.raises(RecordStateError, match="last operation"):
        open_session.pass_run()
    assert open_session.complete_device(row).status is DeviceStatus.COMPLETE


def test_find_by_mac_or_qr(open_session: ProductionRecords) -> None:
    assert open_session.find_device(mac=MAC) is None
    row = open_session.start_device(MAC)
    open_session.set_device_id(row, "PKM-000519", IdEntryMethod.CAMERA)
    assert open_session.find_device(mac="246f28aabb01").id == row  # type: ignore[union-attr]
    assert open_session.find_device(device_id=" PKM-000519 ").id == row  # type: ignore[union-attr]
    assert open_session.find_device(device_id="pkm-000519") is None  # IDs are case-sensitive
    open_session.complete_device(row)
    newer = open_session.start_device(MAC)
    assert open_session.find_device(mac=MAC).id == newer  # type: ignore[union-attr]
    finished = open_session.find_device(device_id="PKM-000519")
    assert finished is not None and finished.status is DeviceStatus.COMPLETE
    for bad in ({}, {"mac": MAC, "device_id": "PKM-1"}):
        with pytest.raises(InputError):
            open_session.find_device(**bad)
    with pytest.raises(InputError):
        open_session.find_device(device_id="  ")


def test_one_qr_label_on_one_board_in_progress(open_session: ProductionRecords) -> None:
    first = open_session.start_device(MAC)
    open_session.set_device_id(first, "PKM-000519", IdEntryMethod.CAMERA)
    open_session.release_run()  # labelled board waits in a tray
    second = open_session.start_device(MAC2)
    with pytest.raises(DatabaseError, match="UNIQUE"):
        open_session.set_device_id(second, "PKM-000519", IdEntryMethod.CAMERA)


def test_write_off_from_a_tray_or_another_bench(
    open_session: ProductionRecords, station2: ProductionRecords, bus: EventBus
) -> None:
    seen: list[DeviceAbandoned] = []
    bus.subscribe(DeviceAbandoned, seen.append)
    waiting = _program(open_session)
    assert open_session.abandon_device(waiting).next_op is None
    held = station2.start_device(MAC2)
    open_session.abandon_device(held)
    run = open_session.repos.runs.latest_for_device(held)
    assert run is not None and run.outcome is RunOutcome.ABANDONED
    assert station2.open_run() is None
    assert seen == [DeviceAbandoned(waiting), DeviceAbandoned(held)]
    with pytest.raises(RecordStateError, match="already abandoned"):
        open_session.abandon_device(held)


def test_failure_adjust_only_for_the_board_on_the_bench(open_session: ProductionRecords) -> None:
    row = open_session.start_device(MAC)
    open_session.counter_event(CounterEvent.UPLOAD_FAILURE, row)
    open_session.counter_event(CounterEvent.UPLOAD_SUCCESS, row)
    open_session.release_run()
    assert not open_session.can_adjust_failure(row)
    open_session.claim(row, OpCode.A_PROGRAM, IdentifyBy.MAC)
    assert open_session.can_adjust_failure(row)
    open_session.release_run()
    with pytest.raises(RecordStateError, match="not on this session's bench"):
        open_session.counter_event(CounterEvent.UPLOAD_SUCCESS, row)


def test_transition_links_the_latest_run(
    open_session: ProductionRecords, station2: ProductionRecords
) -> None:
    row = open_session.start_device(MAC)
    started = open_session.record_transition(row, None, Stage.PROGRAMMING)
    assert started.run_id == open_session.open_run().id  # type: ignore[union-attr]
    open_session.pass_run()
    with pytest.raises(RecordStateError, match="not worked on by this session"):
        station2.record_transition(row, Stage.PROGRAMMING, Stage.TESTING)
    moved = open_session.record_transition(row, Stage.PROGRAMMING, Stage.TESTING)
    assert moved.run_id == started.run_id


def test_recovery_times_each_station_by_its_own_work(
    repos: Repositories,
    open_session: ProductionRecords,
    station2: ProductionRecords,
    clock: FakeClock,
) -> None:
    row = _program(open_session)  # started and programmed by station 1
    first_done = clock.now()
    clock.advance(minutes=5)
    station2.claim(row, OpCode.B_TEST, IdentifyBy.MAC)
    clock.advance(minutes=2)
    station2.record_check(row, Stage.TESTING, CheckCode.B1_COMM, passed=True)
    second_done = clock.now()
    one, two = open_session.require_session().id, station2.require_session().id
    clock.advance(hours=1)  # both stations lose power

    result = recover_unclosed_sessions(repos)

    assert result.session_ids == [one, two] and result.released_device_ids == [row]
    # Station 2's work on a board started at station 1 does not stretch station 1's session.
    assert repos.sessions.require(one).ended_at == first_done
    assert repos.sessions.require(two).ended_at == second_done
    assert repos.devices.require(row).next_op is OpCode.B_TEST


def test_migration_0005_keeps_one_row_per_board_in_progress(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clock: FakeClock
) -> None:
    before = [m for m in discover_migrations() if m.version < 5]
    monkeypatch.setattr(migrate_module, "discover_migrations", lambda: before)
    db = open_database(tmp_path / "v4.db")
    repos = Repositories.create(db, clock)
    operator_id = repos.operators.create("OP9", "Name", "hash", Role.OPERATOR).id
    session_id = repos.sessions.create(operator_id, "ST1", "en").id
    older = repos.devices.create(session_id, MAC)
    newer = repos.devices.create(session_id, MAC)  # duplicate MAC, both in progress
    labelled = repos.devices.create(session_id, MAC2)
    copy = repos.devices.create(session_id, "24:6F:28:AA:BB:03")
    repos.devices.set_device_id(labelled.id, "PKM-1", IdEntryMethod.CAMERA)
    repos.devices.set_device_id(copy.id, "PKM-1", IdEntryMethod.CAMERA)  # same sticker twice

    monkeypatch.undo()
    assert migrate(db) == discover_migrations()[-1].version
    status = {d.id: d.status for d in repos.devices.list_for_session(session_id)}
    assert status == {
        older.id: DeviceStatus.ABANDONED,
        newer.id: DeviceStatus.IN_PROGRESS,
        labelled.id: DeviceStatus.ABANDONED,
        copy.id: DeviceStatus.IN_PROGRESS,
    }
    assert repos.devices.require(older.id).next_op is None
    with pytest.raises(DatabaseError, match="UNIQUE"):
        repos.devices.create(session_id, MAC)
    db.close()
