"""Flexible work: any range of steps A to D, stop with Finish later, continue another day."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from parkomate.auth.service import AuthService
from parkomate.config.settings import Settings
from parkomate.core.clock import FakeClock
from parkomate.core.enums import (
    AmbientReason,
    CheckCode,
    DeviceStatus,
    IdentityStatus,
    OpCode,
    Role,
    RunOutcome,
    SessionEndReason,
    Stage,
)
from parkomate.core.errors import ErrorCode, InputError, RecordStateError
from parkomate.core.events import DeviceCompleted, DeviceParked, Event, EventBus
from parkomate.core.models import DeviceKey, Measurement, Operator
from parkomate.data import Repositories
from parkomate.data.records import ProductionRecords
from parkomate.workflow import WorkflowEngine

MAC = "24:6F:28:AA:BB:01"
MAC2 = "24:6F:28:AA:BB:02"
QR = "PKM-000519"
PASSWORD = "secret-pass-1"


@pytest.fixture
def settings() -> Settings:
    return Settings()


@pytest.fixture
def wf(open_session: ProductionRecords, settings: Settings) -> WorkflowEngine:
    open_session.record_ambient(27.0, AmbientReason.SESSION_START)
    return WorkflowEngine(open_session, lambda: settings)


@pytest.fixture
def worker2(auth: AuthService, admin: Operator) -> Operator:
    return auth.create_operator(admin, "OP2", "Second Worker", PASSWORD, Role.OPERATOR)


def _measurement() -> Measurement:
    return Measurement(
        received_at=datetime.now(UTC), v_a=24.0, v_b=5.0, v_c=3.3, t_reg_c=28.5, t_amb_c=27.1
    )


def _do_a(wf: WorkflowEngine) -> None:
    wf.submit_check(CheckCode.A_WHITELIST, True)
    wf.submit_check(CheckCode.A_UPLOAD, True, text="2.3.1")


def _do_b(wf: WorkflowEngine) -> None:
    wf.submit_check(CheckCode.B1_COMM, True)
    for i in range(1, 6):
        wf.submit_check(CheckCode.reading(i), 150.0 + i)
    wf.submit_check(CheckCode.B2_SENSOR_OK, True)
    wf.submit_check(CheckCode.B2_INDICATOR_OK, True)
    assert all(o.passed for o in wf.evaluate_measurement(_measurement()))


def _do_c_code(wf: WorkflowEngine, qr: str = QR) -> None:
    wf.submit_check(CheckCode.C_QR_READ, qr)
    assert wf.reconcile_identity(qr, qr).status is IdentityStatus.MATCH
    wf.submit_check(CheckCode.C4, True)


def _tick(wf: WorkflowEngine, *codes: CheckCode) -> None:
    for code in codes:
        wf.submit_check(code, True)


def _new_day(
    records: ProductionRecords, worker: Operator, settings: Settings, clock: FakeClock
) -> WorkflowEngine:
    """End the session; another worker logs in on a fresh station the next day."""
    records.end_session(SessionEndReason.LOGOUT)
    clock.advance(hours=20)
    records.start_session(worker, language="en")
    records.record_ambient(26.5, AmbientReason.SESSION_START)
    return WorkflowEngine(records, lambda: settings)


def _events(bus: EventBus) -> list[Event]:
    seen: list[Event] = []
    bus.subscribe(Event, seen.append)
    return seen


def test_a_today_then_b_to_d_another_day(
    wf: WorkflowEngine,
    open_session: ProductionRecords,
    settings: Settings,
    worker2: Operator,
    clock: FakeClock,
) -> None:
    state = wf.start_device(MAC)
    assert state.op is OpCode.A_PROGRAM and not state.resumed
    _do_a(wf)
    result = wf.finish_later()  # A is done: nothing is lost, the board waits for B
    assert result.parked and result.next_op is OpCode.B_TEST
    assert wf.current_device() is None
    row = state.device_row_id
    assert open_session.queue(OpCode.B_TEST)[0].id == row

    later = _new_day(open_session, worker2, settings, clock)
    resumed = later.start_device(MAC)  # the same board, plugged in again
    assert resumed.device_row_id == row and resumed.resumed
    assert (resumed.stage, resumed.op) == (Stage.TESTING, OpCode.B_TEST)
    assert resumed.passed_ops == [OpCode.A_PROGRAM] and resumed.upload_attempts == 1
    _do_b(later)
    assert later.submit_and_next().stage is Stage.LABELING
    _do_c_code(later)
    _tick(later, CheckCode.C1, CheckCode.C2, CheckCode.C3)
    assert later.submit_and_next().stage is Stage.PACKAGING
    _tick(later, CheckCode.D1, CheckCode.D2, CheckCode.D3, CheckCode.D4)
    assert later.submit_and_next().complete

    history = open_session.device_history(row)
    assert history.device.status is DeviceStatus.COMPLETE
    assert history.passed_ops == list(OpCode)
    workers = {r.op_code: r.operator_id for r in history.runs}
    assert workers[OpCode.A_PROGRAM] != workers[OpCode.B_TEST] == worker2.id


def test_a_to_b_now_rest_later(
    wf: WorkflowEngine, open_session: ProductionRecords, bus: EventBus
) -> None:
    seen = _events(bus)
    wf.choose_steps({OpCode.A_PROGRAM, OpCode.B_TEST})
    assert wf.selected_steps() == [OpCode.A_PROGRAM, OpCode.B_TEST]
    wf.start_device(MAC)
    _do_a(wf)
    moved = wf.submit_and_next()  # B is chosen: the board stays on the bench
    assert (moved.stage, moved.next_op, moved.parked) == (Stage.TESTING, OpCode.B_TEST, False)
    _do_b(wf)
    parked = wf.submit_and_next()  # C-1 is not chosen: off to its tray
    assert parked.parked and parked.next_op is OpCode.C_CODE and parked.stage is Stage.LABELING
    assert wf.current_device() is None and wf.current_operation() is None
    assert [e for e in seen if isinstance(e, DeviceParked)] == [DeviceParked(1, OpCode.C_CODE)]

    wf.choose_steps(OpCode)  # later: all the remaining steps
    state = wf.start_device(MAC)
    assert state.op is OpCode.C_CODE and len(state.readings) == 5  # B results came along
    assert state.outcomes[CheckCode.B3_V_C].passed is True
    assert state.marks[CheckCode.B2_SENSOR_OK] is True
    assert wf.is_stage_complete(Stage.TESTING) and not wf.is_stage_complete(Stage.LABELING)
    _do_c_code(wf)
    _tick(wf, CheckCode.C1, CheckCode.C2, CheckCode.C3)
    assert wf.submit_and_next().stage is Stage.PACKAGING
    _tick(wf, CheckCode.D1, CheckCode.D2, CheckCode.D3, CheckCode.D4)
    assert wf.submit_and_next().complete
    assert any(isinstance(e, DeviceCompleted) for e in seen)


def _waiting_at_code_insertion(wf: WorkflowEngine, *macs: str) -> None:
    wf.choose_steps({OpCode.A_PROGRAM, OpCode.B_TEST})
    for mac in macs:
        wf.start_device(mac)
        _do_a(wf)
        wf.submit_and_next()
        _do_b(wf)
        assert wf.submit_and_next().parked


def test_batch_code_insertion_then_casing(
    wf: WorkflowEngine, open_session: ProductionRecords
) -> None:
    _waiting_at_code_insertion(wf, MAC, MAC2)
    wf.choose_steps({OpCode.C_CODE})
    for mac, qr in ((MAC, "PKM-000001"), (MAC2, "PKM-000002")):
        wf.start_device(mac)
        assert wf.missing_checks() == [CheckCode.C_QR_READ, CheckCode.C_ID_SYNC, CheckCode.C4]
        with pytest.raises(RecordStateError, match="not on the bench now"):
            wf.submit_check(CheckCode.C1, True)  # casing is not this worker's step now
        _do_c_code(wf, qr)
        result = wf.submit_and_next()
        assert result.parked and result.next_op is OpCode.C_CASING
    assert [d.device_id for d in open_session.queue(OpCode.C_CASING)] == [
        "PKM-000001",
        "PKM-000002",
    ]

    wf.choose_steps({OpCode.C_CASING})
    for qr in ("PKM-000001", "PKM-000002"):
        state = wf.pick_up(DeviceKey.qr(qr))  # no serial needed: scan the sticker
        assert state.op is OpCode.C_CASING and state.identity is IdentityStatus.MATCH
        assert wf.missing_checks() == [CheckCode.C1, CheckCode.C2]
        _tick(wf, CheckCode.C1, CheckCode.C2)
        assert wf.submit_and_next().next_op is OpCode.C_BRANDING
    assert len(open_session.queue(OpCode.C_BRANDING)) == 2


def test_mix_up_guard(
    wf: WorkflowEngine, open_session: ProductionRecords, settings: Settings
) -> None:
    wf.choose_steps({OpCode.A_PROGRAM})
    wf.start_device(MAC)
    _do_a(wf)
    assert wf.submit_and_next().next_op is OpCode.B_TEST

    wf.choose_steps({OpCode.C_CODE})
    with pytest.raises(RecordStateError) as not_chosen:
        wf.start_device(MAC)
    assert not_chosen.value.code is ErrorCode.WIP_STEP_NOT_SELECTED
    assert not_chosen.value.params == {"op_key": "op.B_TEST"}
    wf.add_step(OpCode.B_TEST)
    assert wf.start_device(MAC).op is OpCode.B_TEST
    with pytest.raises(RecordStateError, match="already on the bench"):
        wf.start_device(MAC2)
    with pytest.raises(RecordStateError):
        wf.choose_steps({OpCode.B_TEST})  # not while a board is on the bench
    wf.release_device()

    packing_only = WorkflowEngine(open_session, lambda: settings, bench=[OpCode.D_PACK])
    assert packing_only.bench_steps() == packing_only.selected_steps() == [OpCode.D_PACK]
    with pytest.raises(RecordStateError) as wrong:
        packing_only.start_device(MAC)
    assert wrong.value.code is ErrorCode.WIP_WRONG_OPERATION
    with pytest.raises(RecordStateError) as wrong_new:
        packing_only.start_device(MAC2)  # a new board needs programming first
    assert wrong_new.value.code is ErrorCode.WIP_WRONG_OPERATION
    for bad in (set(), {OpCode.A_PROGRAM}):
        with pytest.raises(InputError):
            packing_only.choose_steps(bad)
    with pytest.raises(InputError):
        packing_only.add_step(OpCode.B_TEST)
    with pytest.raises(InputError):
        WorkflowEngine(open_session, lambda: settings, bench=[])


def test_pick_up_by_qr_unknown_and_finished(wf: WorkflowEngine) -> None:
    with pytest.raises(RecordStateError) as unknown:
        wf.pick_up(DeviceKey.qr(" PKM-404 "))
    assert unknown.value.code is ErrorCode.WIP_NOT_FOUND
    assert unknown.value.params == {"value": "PKM-404"}
    wf.start_device(MAC)
    _do_a(wf)
    wf.submit_and_next()
    _do_b(wf)
    wf.submit_and_next()
    _do_c_code(wf)
    _tick(wf, CheckCode.C1, CheckCode.C2, CheckCode.C3)
    wf.submit_and_next()
    _tick(wf, CheckCode.D1, CheckCode.D2, CheckCode.D3, CheckCode.D4)
    assert wf.submit_and_next().complete
    wf.clear_finished()
    for key in (DeviceKey.mac(MAC), DeviceKey.qr(QR)):
        with pytest.raises(RecordStateError) as finished:
            wf.pick_up(key)
        assert finished.value.code is ErrorCode.WIP_FINISHED
        assert finished.value.params == {"status_key": "device_status.complete"}


def test_board_on_another_bench_is_refused(
    wf: WorkflowEngine,
    repos: Repositories,
    bus: EventBus,
    settings: Settings,
    worker2: Operator,
) -> None:
    wf.choose_steps({OpCode.A_PROGRAM})
    wf.start_device(MAC)
    _do_a(wf)
    wf.submit_and_next()  # waits for B
    other_records = ProductionRecords(repos, station_id="ST-TWO", bus=bus)
    other_records.start_session(worker2, language="en")
    other = WorkflowEngine(other_records, lambda: settings)
    other.start_device(MAC)  # station 2 takes the board for B
    wf.choose_steps(OpCode)
    with pytest.raises(RecordStateError) as taken:
        wf.start_device(MAC)
    assert taken.value.code is ErrorCode.WIP_CLAIMED
    assert taken.value.params == {"station": "ST-TWO"}


def test_finish_later_mid_step_restarts_it_but_keeps_attempts(
    wf: WorkflowEngine, open_session: ProductionRecords
) -> None:
    row = wf.start_device(MAC).device_row_id
    wf.submit_check(CheckCode.A_WHITELIST, True)
    first = wf.submit_check(CheckCode.A_UPLOAD, False)
    assert first.retry_allowed and first.attempt == 1
    result = wf.finish_later()  # A not finished: it starts again next time
    assert result.parked and result.next_op is OpCode.A_PROGRAM
    assert open_session.device_history(row).runs[-1].outcome is RunOutcome.RELEASED

    state = wf.start_device(MAC)
    assert state.op is OpCode.A_PROGRAM and state.resumed
    assert state.upload_attempts == 1 and state.upload_failures == 1
    assert CheckCode.A_WHITELIST not in state.outcomes  # the released step starts again
    wf.submit_check(CheckCode.A_WHITELIST, True)
    assert wf.submit_check(CheckCode.A_UPLOAD, False).attempt == 2
    final = wf.submit_check(CheckCode.A_UPLOAD, False)  # 3 attempts in total: rejected
    assert final.reject is not None
    assert open_session.get_device(row).status is DeviceStatus.REJECTED


def test_finish_later_keeps_the_finished_steps_of_the_sitting(
    wf: WorkflowEngine, open_session: ProductionRecords
) -> None:
    row = wf.start_device(MAC).device_row_id
    _do_a(wf)
    wf.submit_and_next()
    _do_b(wf)
    wf.submit_and_next()
    _do_c_code(wf)  # C-1 complete
    _tick(wf, CheckCode.C1)  # C-2 half done
    result = wf.finish_later()
    assert result.parked and result.next_op is OpCode.C_CASING
    history = open_session.device_history(row)
    assert OpCode.C_CODE in history.passed_ops
    c4 = next(c for c in history.checks if c.check_code is CheckCode.C4)
    c_code_run = next(r for r in history.runs if r.op_code is OpCode.C_CODE)
    assert c4.run_id == c_code_run.id  # the tick belongs to its own step

    state = wf.pick_up(DeviceKey.qr(QR))
    assert state.op is OpCode.C_CASING and state.qr_id == QR
    assert state.identity is IdentityStatus.MATCH and state.marks[CheckCode.C4] is True
    assert wf.missing_checks() == [CheckCode.C1, CheckCode.C2, CheckCode.C3]
    with pytest.raises(RecordStateError):
        wf.submit_check(CheckCode.C_QR_READ, QR)  # code insertion is already passed
    with pytest.raises(RecordStateError):
        wf.reconcile_identity(QR, QR)


def test_finish_later_when_everything_is_done(wf: WorkflowEngine) -> None:
    wf.start_device(MAC)
    _do_a(wf)
    wf.submit_and_next()
    _do_b(wf)
    result = wf.finish_later()  # B done: passed, the board waits for C-1
    assert result.parked and (result.stage, result.next_op) == (Stage.LABELING, OpCode.C_CODE)
    wf.start_device(MAC)
    _do_c_code(wf)
    _tick(wf, CheckCode.C1, CheckCode.C2, CheckCode.C3)
    wf.submit_and_next()
    _tick(wf, CheckCode.D1, CheckCode.D2, CheckCode.D3, CheckCode.D4)
    assert wf.finish_later().complete  # nothing left to do later: the board is complete


def test_logout_keeps_finished_steps_of_the_sitting(
    wf: WorkflowEngine, open_session: ProductionRecords
) -> None:
    row = wf.start_device(MAC).device_row_id
    _do_a(wf)
    wf.submit_and_next()
    _do_b(wf)
    wf.submit_and_next()
    _do_c_code(wf)
    wf.release_device()  # end of session with the board on the bench
    assert open_session.get_device(row).next_op is OpCode.C_CASING
    assert wf.current_device() is None


def test_reject_in_a_later_step_of_the_sitting(wf: WorkflowEngine) -> None:
    wf.start_device(MAC)
    _do_a(wf)
    wf.submit_and_next()
    _do_b(wf)
    wf.submit_and_next()
    _do_c_code(wf)
    instruction = wf.reject(CheckCode.C3, "reject.reason.item_missing")
    assert instruction.stage is Stage.LABELING and instruction.check_code is CheckCode.C3
    with pytest.raises(RecordStateError):
        wf.finish_later()


def test_operation_and_stage_checks(wf: WorkflowEngine) -> None:
    assert wf.operation_checks(OpCode.C_CASING) == [CheckCode.C1, CheckCode.C2]
    testing = wf.operation_checks(OpCode.B_TEST)
    assert CheckCode.B3_T_AMB not in testing and CheckCode.reading(6) not in testing
    assert wf.required_checks(Stage.LABELING) == [
        CheckCode.C_QR_READ,
        CheckCode.C_ID_SYNC,
        CheckCode.C4,
        CheckCode.C1,
        CheckCode.C2,
        CheckCode.C3,
    ]
    assert wf.required_checks(Stage.COMPLETE) == []
