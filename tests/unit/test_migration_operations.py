"""Migration 0004_operations: next_op, operation runs, run ids on checks and transitions."""

from __future__ import annotations

from pathlib import Path

import pytest

import parkomate.data.migrate as migrate_module
from parkomate.core.clock import FakeClock
from parkomate.core.enums import (
    CheckCode,
    DeviceStatus,
    IdentifyBy,
    OpCode,
    Role,
    RunOutcome,
    Stage,
)
from parkomate.core.errors import DatabaseError
from parkomate.data import Database, Repositories, open_database
from parkomate.data.migrate import discover_migrations, migrate

T0 = "2026-10-25T08:00:00.000000+00:00"
T1 = "2026-10-25T08:05:00.000000+00:00"
INSERT_CHECK = (
    "INSERT INTO check_results (device_row_id, stage, check_code, passed, operator_marked,"
    " created_at, run_id) VALUES (?, 'programming', 'A_UPLOAD', 1, 0, ?, ?)"
)


def _session(repos: Repositories, code: str = "OP1") -> tuple[int, int]:
    """(operator id, session id)."""
    operator_id = repos.operators.create(code, "Name", "hash", Role.OPERATOR).id
    return operator_id, repos.sessions.create(operator_id, "STATION-01", "en").id


def _open_run(
    db: Database,
    device_row_id: int,
    session_id: int,
    operator_id: int,
    op: str = OpCode.A_PROGRAM,
    identified_by: str = IdentifyBy.NEW,
) -> int:
    with db.transaction() as conn:
        cursor = conn.execute(
            "INSERT INTO operation_runs (device_row_id, op_code, session_id, operator_id,"
            " station_id, identified_by, started_at) VALUES (?, ?, ?, ?, 'STATION-01', ?, ?)",
            (device_row_id, op, session_id, operator_id, identified_by, T0),
        )
        assert cursor.lastrowid is not None
        return cursor.lastrowid


def _close_run(db: Database, run_id: int, outcome: str = RunOutcome.PASSED) -> None:
    with db.transaction() as conn:
        conn.execute(
            "UPDATE operation_runs SET finished_at = ?, outcome = ? WHERE id = ?",
            (T1, outcome, run_id),
        )


def _next_op(db: Database, device_row_id: int) -> object:
    return db.scalar("SELECT next_op FROM devices WHERE id = ?", (device_row_id,))


def _columns(db: Database, table: str) -> set[str]:
    return {row["name"] for row in db.query(f"PRAGMA table_info({table})")}


def test_schema(db: Database) -> None:
    assert "next_op" in _columns(db, "devices")
    assert "run_id" in _columns(db, "check_results")
    assert "run_id" in _columns(db, "stage_transitions")
    indexes = {row[0] for row in db.query("SELECT name FROM sqlite_master WHERE type = 'index'")}
    assert "ux_devices_one_active" not in indexes
    assert {"ux_runs_open_device", "ux_runs_open_session", "ix_devices_queue"} <= indexes


def test_new_board_waits_for_programming(repos: Repositories, db: Database) -> None:
    _, session_id = _session(repos)
    device = repos.devices.create(session_id, "AA:BB:CC:DD:EE:01")
    assert _next_op(db, device.id) == OpCode.A_PROGRAM


def test_a_session_may_leave_many_boards_in_progress(repos: Repositories) -> None:
    _, session_id = _session(repos)
    repos.devices.create(session_id, "AA:BB:CC:DD:EE:01")
    repos.devices.create(session_id, "AA:BB:CC:DD:EE:02")
    statuses = [d.status for d in repos.devices.list_for_session(session_id)]
    assert statuses == [DeviceStatus.IN_PROGRESS, DeviceStatus.IN_PROGRESS]


def test_next_op_values_are_checked(repos: Repositories, db: Database) -> None:
    _, session_id = _session(repos)
    device = repos.devices.create(session_id, "AA:BB:CC:DD:EE:01")
    for code in OpCode:
        with db.transaction() as conn:
            conn.execute("UPDATE devices SET next_op = ? WHERE id = ?", (code, device.id))
    with pytest.raises(DatabaseError), db.transaction() as conn:
        conn.execute("UPDATE devices SET next_op = 'C_GLUE' WHERE id = ?", (device.id,))


def test_one_open_run_per_board(repos: Repositories, db: Database) -> None:
    op1, s1 = _session(repos, "OP1")
    op2, s2 = _session(repos, "OP2")
    device = repos.devices.create(s1, "AA:BB:CC:DD:EE:01")
    run = _open_run(db, device.id, s1, op1)
    with pytest.raises(DatabaseError, match="UNIQUE"):
        _open_run(db, device.id, s2, op2, OpCode.A_PROGRAM, IdentifyBy.MAC)
    _close_run(db, run, RunOutcome.RELEASED)
    _open_run(db, device.id, s2, op2, OpCode.A_PROGRAM, IdentifyBy.MAC)  # free again


def test_one_open_run_per_session(repos: Repositories, db: Database) -> None:
    operator_id, session_id = _session(repos)
    first = repos.devices.create(session_id, "AA:BB:CC:DD:EE:01")
    second = repos.devices.create(session_id, "AA:BB:CC:DD:EE:02")
    run = _open_run(db, first.id, session_id, operator_id)
    with pytest.raises(DatabaseError, match="UNIQUE"):
        _open_run(db, second.id, session_id, operator_id)
    _close_run(db, run)
    _open_run(db, second.id, session_id, operator_id)


def test_run_is_closed_once_and_never_rewritten(repos: Repositories, db: Database) -> None:
    operator_id, session_id = _session(repos)
    device = repos.devices.create(session_id, "AA:BB:CC:DD:EE:01")
    run = _open_run(db, device.id, session_id, operator_id)
    with pytest.raises(DatabaseError, match="append-only"), db.transaction() as conn:
        conn.execute("UPDATE operation_runs SET op_code = 'B_TEST' WHERE id = ?", (run,))
    _close_run(db, run)
    with pytest.raises(DatabaseError, match="append-only"):
        _close_run(db, run, RunOutcome.REJECTED)
    with pytest.raises(DatabaseError, match="append-only"), db.transaction() as conn:
        conn.execute("DELETE FROM operation_runs WHERE id = ?", (run,))


def test_finished_at_and_outcome_go_together(repos: Repositories, db: Database) -> None:
    operator_id, session_id = _session(repos)
    device = repos.devices.create(session_id, "AA:BB:CC:DD:EE:01")
    run = _open_run(db, device.id, session_id, operator_id)
    with pytest.raises(DatabaseError, match="CHECK"), db.transaction() as conn:
        conn.execute("UPDATE operation_runs SET finished_at = ? WHERE id = ?", (T1, run))
    with pytest.raises(DatabaseError, match="CHECK"), db.transaction() as conn:
        conn.execute("UPDATE operation_runs SET outcome = 'passed' WHERE id = ?", (run,))


def test_sql_checks_accept_every_enum_value(repos: Repositories, db: Database) -> None:
    operator_id, session_id = _session(repos)
    device = repos.devices.create(session_id, "AA:BB:CC:DD:EE:01")
    for code in OpCode:
        _close_run(db, _open_run(db, device.id, session_id, operator_id, code))
    for method in IdentifyBy:
        _close_run(db, _open_run(db, device.id, session_id, operator_id, identified_by=method))
    for outcome in RunOutcome:
        _close_run(db, _open_run(db, device.id, session_id, operator_id), outcome)
    with pytest.raises(DatabaseError, match="CHECK"):
        _open_run(db, device.id, session_id, operator_id, "Z_UNKNOWN")
    with pytest.raises(DatabaseError, match="CHECK"):
        _open_run(db, device.id, session_id, operator_id, identified_by="barcode")


def test_checks_and_transitions_point_at_their_run(repos: Repositories, db: Database) -> None:
    operator_id, session_id = _session(repos)
    device = repos.devices.create(session_id, "AA:BB:CC:DD:EE:01")
    run = _open_run(db, device.id, session_id, operator_id)
    # Rows written without a run (older code, older databases) keep run_id NULL.
    older = repos.checks.add(
        device.id, Stage.PROGRAMMING, CheckCode.A_WHITELIST, value_text="ok", passed=True
    )
    assert db.scalar("SELECT run_id FROM check_results WHERE id = ?", (older.id,)) is None
    with db.transaction() as conn:
        conn.execute(INSERT_CHECK, (device.id, T1, run))
        conn.execute(
            "INSERT INTO stage_transitions (device_row_id, from_stage, to_stage, created_at,"
            " run_id) VALUES (?, 'testing', 'labeling', ?, ?)",
            (device.id, T1, run),
        )
    assert db.scalar("SELECT COUNT(*) FROM check_results WHERE run_id = ?", (run,)) == 1
    assert db.scalar("SELECT COUNT(*) FROM stage_transitions WHERE run_id = ?", (run,)) == 1
    with pytest.raises(DatabaseError, match="FOREIGN KEY"), db.transaction() as conn:
        conn.execute(INSERT_CHECK, (device.id, T1, 999))


def test_upgrade_fills_next_op_from_the_last_stage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clock: FakeClock
) -> None:
    before = [m for m in discover_migrations() if m.version < 4]
    monkeypatch.setattr(migrate_module, "discover_migrations", lambda: before)
    db = open_database(tmp_path / "v3.db")
    repos = Repositories.create(db, clock)
    operator_id, _ = _session(repos)

    def board(mac: str, stages: list[Stage]) -> int:
        # Before 0004 a session holds one board in progress, so each board gets its own.
        session_id = repos.sessions.create(operator_id, "STATION-01", "en").id
        device = repos.devices.create(session_id, mac)
        previous: Stage | None = None
        for stage in stages:
            repos.transitions.add(device.id, previous, stage)
            previous = stage
        return device.id

    fresh = board("AA:BB:CC:DD:EE:01", [])
    programming = board("AA:BB:CC:DD:EE:02", [Stage.PROGRAMMING])
    testing = board("AA:BB:CC:DD:EE:03", [Stage.PROGRAMMING, Stage.TESTING])
    labeling = board("AA:BB:CC:DD:EE:04", [Stage.PROGRAMMING, Stage.TESTING, Stage.LABELING])
    packaging = board(
        "AA:BB:CC:DD:EE:05", [Stage.PROGRAMMING, Stage.TESTING, Stage.LABELING, Stage.PACKAGING]
    )
    done = board("AA:BB:CC:DD:EE:06", [Stage.PROGRAMMING])
    repos.devices.finish(done, DeviceStatus.COMPLETE, clock.now())

    monkeypatch.undo()
    assert migrate(db) == 4
    assert _next_op(db, fresh) == OpCode.A_PROGRAM
    assert _next_op(db, programming) == OpCode.A_PROGRAM
    assert _next_op(db, testing) == OpCode.B_TEST
    assert _next_op(db, labeling) == OpCode.C_CODE  # labeling restarts at code insertion
    assert _next_op(db, packaging) == OpCode.D_PACK
    assert _next_op(db, done) is None
    db.close()
