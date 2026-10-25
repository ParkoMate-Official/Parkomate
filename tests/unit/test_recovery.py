"""Crash recovery: unfinished sessions are closed and the board on the bench is released."""

from __future__ import annotations

from parkomate.core.clock import FakeClock
from parkomate.core.enums import (
    CheckCode,
    DeviceStatus,
    OpCode,
    RunOutcome,
    SessionEndReason,
    Stage,
)
from parkomate.core.models import Operator
from parkomate.data import Repositories
from parkomate.data.records import ProductionRecords
from parkomate.data.recovery import recover_unclosed_sessions


def test_nothing_to_recover(repos: Repositories) -> None:
    result = recover_unclosed_sessions(repos)
    assert not result.recovered and result.released_device_ids == []


def test_unclosed_session_recovered(
    repos: Repositories, operator: Operator, clock: FakeClock
) -> None:
    crashed = ProductionRecords(repos, station_id="ST1")
    crashed.start_session(operator, language="en")
    done = crashed.start_device("24:6F:28:AA:BB:01")
    crashed.complete_device(done)
    clock.advance(seconds=30)
    unfinished = crashed.start_device("24:6F:28:AA:BB:02")
    clock.advance(seconds=12)
    crashed.record_check(unfinished, Stage.PROGRAMMING, CheckCode.A_WHITELIST, passed=True)
    last_write = clock.now()
    session_id = crashed.require_session().id
    clock.advance(hours=3)  # the app was dead for a while; "crash" = we just drop `crashed`

    result = recover_unclosed_sessions(repos)

    assert result.session_ids == [session_id]
    assert result.released_device_ids == [unfinished]
    session = repos.sessions.require(session_id)
    assert session.end_reason is SessionEndReason.CRASH_RECOVERED
    assert session.ended_at == last_write  # closed at the last recorded activity, not "now"
    # The board is not lost: it waits for the step it was on, for any session to continue.
    device = repos.devices.require(unfinished)
    assert device.status is DeviceStatus.IN_PROGRESS and device.next_op is OpCode.A_PROGRAM
    run = repos.runs.latest_for_device(unfinished)
    assert run is not None and run.outcome is RunOutcome.RELEASED
    assert run.finished_at == last_write
    assert repos.devices.queue(OpCode.A_PROGRAM) == [device]
    assert repos.devices.require(done).status is DeviceStatus.COMPLETE
    assert repos.audit.list_entries(action="session.crash_recovered")[0].details == {
        "session_id": session_id,
        "released_devices": [unfinished],
    }
    assert not recover_unclosed_sessions(repos).recovered  # idempotent
