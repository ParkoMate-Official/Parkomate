"""WorkflowEngine - the production implementation of ``WorkflowService`` (owner: Piyush).

One board at a time on this bench, through the steps of the line (:mod:`.operations`):

    A_PROGRAM → B_TEST → C_CODE → C_CASING → C_BRANDING → D_PACK → COMPLETE,  any → REJECTED

The worker chooses which of the bench's steps to do (default: all). A **sitting** is the
board's current step plus the following steps of the same stage that are chosen and possible
here; the gate is the sum of their checks. Passing a sitting moves the board on to its next
step on this bench when that step is chosen, else the board is **parked** for the tray of
that step. Any bench can **pick up** a waiting board later (by MAC or QR): its state is
rebuilt from the database, so A today and B to D on another day - by anyone - is one flow.

Stage gates (spread over the steps)
* A: whitelist allowed AND firmware upload succeeded.
* B: communication OK, exactly N readings, sensor marked OK, indicator marked OK,
  V_A / V_B / V_C within limits and (T_reg − ambient) ≤ margin.
* C: C-1 QR read, identity reconciled, C4; C-2 C1, C2; C-3 C3.
* D: D1–D4 ticked → COMPLETE.

Rules
* Validation is pure (:mod:`.validation`); retries follow :mod:`.policy`. Retry limits count
  every attempt on the board, on any bench (a released step never resets them).
* A released step (Finish later, end of session) starts again; passed steps are kept.
* Every result, run, stage transition, reject and completion is persisted through
  :class:`~parkomate.data.records.ProductionRecords` and published on the event bus
  (``DeviceStarted``, ``StageChanged``, ``CheckRecorded``, ``DeviceCompleted``,
  ``DeviceRejected``, ``DeviceParked``, ``DeviceReleased``).
* A final failure rejects **inside the call**; the returned outcome carries ``reject`` with
  the stage, check, measured value, limits, i18n reason and the reject-box instruction.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from parkomate.config.settings import Settings
from parkomate.core.enums import (
    LABELING_CHECKLIST,
    PACKAGING_CHECKLIST,
    CheckCode,
    CheckKind,
    CounterEvent,
    DeviceStatus,
    IdentifyBy,
    IdentityStatus,
    IdEntryMethod,
    OpCode,
    RunOutcome,
    Stage,
)
from parkomate.core.errors import ErrorCode, InputError, RecordStateError
from parkomate.core.events import (
    CheckRecorded,
    DeviceCompleted,
    DeviceParked,
    DeviceRejected,
    DeviceStarted,
    Event,
    EventBus,
    StageChanged,
)
from parkomate.core.interfaces import CheckValue
from parkomate.core.models import (
    CheckOutcome,
    Device,
    DeviceHistory,
    DeviceKey,
    DeviceState,
    IdentityOutcome,
    Measurement,
    RejectInstruction,
    StepResult,
)
from parkomate.data.records import ProductionRecords
from parkomate.workflow.operations import operation, operation_for_check, operations_of
from parkomate.workflow.policy import RetryPolicy
from parkomate.workflow.transitions import ORDER, check_transition
from parkomate.workflow.validation import (
    id_format_ok,
    ids_match,
    measurement_verdicts,
    quantize,
)

log = logging.getLogger(__name__)

CHECKLISTS = frozenset(LABELING_CHECKLIST + PACKAGING_CHECKLIST)
ELECTRICAL_CODES = (CheckCode.B3_V_A, CheckCode.B3_V_B, CheckCode.B3_V_C, CheckCode.B3_T_REG)
OPERATOR_MARKS = frozenset({CheckCode.B2_SENSOR_OK, CheckCode.B2_INDICATOR_OK})
ATTEMPT_COUNTED = frozenset({CheckCode.A_UPLOAD, CheckCode.B1_COMM, CheckCode.B3_V_A})
"""Checks whose every submission counts as an attempt (B3_V_A: one per measurement)."""


@dataclass(slots=True)
class _Active:
    """Mutable state of the board on the bench (snapshots go out as ``DeviceState``)."""

    device_row_id: int
    mac_address: str
    started_at: datetime
    stage: Stage = Stage.PROGRAMMING
    op: OpCode = OpCode.A_PROGRAM
    segment: tuple[OpCode, ...] = ()
    """Steps of this sitting still to pass; ``segment[0]`` is ``op`` (its run is open)."""
    identified_by: IdentifyBy = IdentifyBy.NEW
    passed_ops: list[OpCode] = field(default_factory=list)
    resumed: bool = False
    status: DeviceStatus = DeviceStatus.IN_PROGRESS
    attempts: dict[CheckCode, int] = field(default_factory=dict)
    upload_failures: int = 0
    readings: list[float] = field(default_factory=list)
    marks: dict[CheckCode, bool] = field(default_factory=dict)
    outcomes: dict[CheckCode, CheckOutcome] = field(default_factory=dict)
    qr_id: str | None = None
    device_id: str | None = None
    identity: IdentityStatus | None = None
    reject: RejectInstruction | None = None

    def bump(self, code: CheckCode) -> int:
        self.attempts[code] = self.attempts.get(code, 0) + 1
        return self.attempts[code]


class WorkflowEngine:
    """Production ``WorkflowService``."""

    def __init__(
        self,
        records: ProductionRecords,
        settings: Callable[[], Settings],
        bus: EventBus | None = None,
        *,
        bench: Iterable[OpCode] | None = None,
    ) -> None:
        self._records = records
        self._settings = settings
        self._bus = bus or records.bus
        self._lock = threading.RLock()
        self._active: _Active | None = None
        self._bench = frozenset(OpCode) if bench is None else frozenset(bench)
        if not self._bench:
            raise InputError("a bench must be able to do at least one step")
        self._selected = self._bench

    @property
    def records(self) -> ProductionRecords:
        return self._records

    def _policy(self) -> RetryPolicy:
        return RetryPolicy(self._settings())

    # ================================================================== steps
    def bench_steps(self) -> list[OpCode]:
        return [op for op in OpCode if op in self._bench]

    def selected_steps(self) -> list[OpCode]:
        with self._lock:
            return [op for op in OpCode if op in self._selected]

    def choose_steps(self, ops: Iterable[OpCode]) -> None:
        chosen = frozenset(ops)
        if not chosen:
            raise InputError("choose at least one step")
        if not chosen <= self._bench:
            raise InputError(f"not done on this bench: {sorted(chosen - self._bench)}")
        with self._lock:
            if self._on_bench() is not None:
                raise RecordStateError("finish or put back the board on the bench first")
            self._selected = chosen

    def add_step(self, op: OpCode) -> None:
        if op not in self._bench:
            raise InputError(f"{op.value} is not done on this bench")
        with self._lock:
            self._selected = self._selected | {op}
            active = self._on_bench()
            if active is not None:
                active.segment = self._segment(active.op)

    def _segment(self, op: OpCode) -> tuple[OpCode, ...]:
        """``op`` and the following steps of its stage that are chosen and possible here."""
        ops: list[OpCode] = []
        current: OpCode | None = op
        while (
            current is not None
            and current.stage is op.stage
            and current in self._selected
            and current in self._bench
        ):
            ops.append(current)
            current = current.next
        return tuple(ops)

    def _require_here(self, op: OpCode) -> None:
        """Mix-up guard: the board's next step must be possible here and chosen."""
        params = {"op_key": op.label_key}
        context = {"op": op.value}
        if op not in self._bench:
            raise RecordStateError(
                f"{op.value} is not done on this bench",
                code=ErrorCode.WIP_WRONG_OPERATION,
                params=params,
                context=context,
            )
        if op not in self._selected:
            raise RecordStateError(
                f"{op.value} is not one of the chosen steps",
                code=ErrorCode.WIP_STEP_NOT_SELECTED,
                params=params,
                context=context,
            )

    # ================================================================== lifecycle
    def pick_up(self, key: DeviceKey) -> DeviceState:
        if key.by is IdentifyBy.NEW:
            raise InputError("identify the board by MAC or QR")
        with self._lock:
            if self._on_bench() is not None:
                raise RecordStateError("a device is already on the bench")
            if key.by is IdentifyBy.MAC:
                device = self._records.find_device(mac=key.value)
            else:
                device = self._records.find_device(device_id=key.value)
            if device is None and key.by is not IdentifyBy.MAC:
                raise RecordStateError(
                    "no board with this ID",
                    code=ErrorCode.WIP_NOT_FOUND,
                    params={"value": key.value.strip()},
                )
            started = device is None
            if device is None:
                self._start_new(key.value)
            elif device.status is not DeviceStatus.IN_PROGRESS:
                raise RecordStateError(
                    f"device row {device.id} is already {device.status.value}",
                    code=ErrorCode.WIP_FINISHED,
                    params={"status_key": device.status.label_key},
                    context={"device_row_id": device.id},
                )
            else:
                self._resume(device, key.by)
            snapshot = self._snapshot()
        assert snapshot is not None
        if started:
            self._bus.publish(DeviceStarted(snapshot.device_row_id, snapshot.mac_address))
        return snapshot

    def start_device(self, mac: str) -> DeviceState:
        return self.pick_up(DeviceKey.mac(mac))

    def _start_new(self, mac: str) -> None:
        self._require_here(OpCode.A_PROGRAM)
        row_id = self._records.start_device(mac)
        device = self._records.get_device(row_id)
        self._active = _Active(
            row_id,
            device.mac_address,
            device.started_at,
            segment=self._segment(OpCode.A_PROGRAM),
        )
        self._records.record_transition(row_id, None, Stage.PROGRAMMING)

    def _resume(self, device: Device, by: IdentifyBy) -> None:
        op = device.next_op
        if op is None:  # pragma: no cover - every in-progress row waits for a step
            raise RecordStateError(f"device row {device.id} waits for no step")
        history = self._records.device_history(device.id)
        held = history.open_run
        if held is not None:
            raise RecordStateError(
                f"device row {device.id} is on the bench of {held.station_id}",
                code=ErrorCode.WIP_CLAIMED,
                params={"station": held.station_id},
                context={"device_row_id": device.id, "run_id": held.id},
            )
        self._require_here(op)
        self._records.claim(device.id, op, by)
        self._active = self._rebuild(history, op, by)
        log.info("device row %d picked up at %s (by %s)", device.id, op.value, by.value)

    def _rebuild(self, history: DeviceHistory, op: OpCode, by: IdentifyBy) -> _Active:
        """State of a board continued here: results of its passed steps; attempt counts of
        every step (a released step starts again, but its attempts still count)."""
        device = history.device
        passed_runs = {r.id for r in history.runs if r.outcome is RunOutcome.PASSED}
        active = _Active(
            device.id,
            device.mac_address,
            device.started_at,
            stage=op.stage,
            op=op,
            segment=self._segment(op),
            identified_by=by,
            passed_ops=history.passed_ops,
            resumed=True,
        )
        for check in history.checks:
            code = check.check_code
            if code in ATTEMPT_COUNTED:
                active.bump(code)
                if code is CheckCode.A_UPLOAD and check.passed is False:
                    active.upload_failures += 1
            if check.run_id not in passed_runs:
                continue
            active.outcomes[code] = CheckOutcome(
                check_code=code,
                stage=check.stage,
                passed=check.passed,
                value_num=check.value_num,
                value_text=check.value_text,
                unit=check.unit,
                limit_low=check.limit_low,
                limit_high=check.limit_high,
            )
            if code.reading_index is not None and check.value_num is not None:
                active.readings.append(check.value_num)
            if code in CHECKLISTS or code in OPERATOR_MARKS:
                active.marks[code] = check.passed is True
        sync = active.outcomes.get(CheckCode.C_ID_SYNC)
        if sync is not None and sync.passed:
            active.device_id = active.qr_id = device.device_id
            matched = (sync.value_text or "").startswith("match")
            active.identity = IdentityStatus.MATCH if matched else IdentityStatus.CONFIRMED
        return active

    def current_device(self) -> DeviceState | None:
        with self._lock:
            return self._snapshot()

    def current_stage(self) -> Stage:
        with self._lock:
            return self._active.stage if self._active else Stage.PROGRAMMING

    def current_operation(self) -> OpCode | None:
        with self._lock:
            active = self._on_bench()
            return active.op if active is not None else None

    def finish_later(self) -> StepResult:
        with self._lock:
            active = self._require_active()
            if not self.missing_checks():
                result, events = self._finish_sitting(active, park=True)
            else:
                result, events = self._release(active), []
        for event in events:
            self._bus.publish(event)
        return result

    def release_device(self) -> None:
        with self._lock:
            active = self._on_bench()
            if active is None:
                self._active = None
                return
            self._release(active)

    def _release(self, active: _Active) -> StepResult:
        """Keep the steps of this sitting that are complete, release the first unfinished
        one (it starts again next time) and take the board off the bench."""
        while len(active.segment) > 1 and self._op_done(active, active.op):
            self._record_ticks(active, active.op)
            self._pass_and_claim(active, active.segment[1])
            active.segment = active.segment[1:]
        self._records.release_run()
        self._active = None
        log.info("device row %d released at %s", active.device_row_id, active.op.value)
        return StepResult(stage=active.op.stage, next_op=active.op, parked=True)

    def clear_finished(self) -> None:
        with self._lock:
            if self._on_bench() is not None:
                raise RecordStateError("the device on the bench is not finished")
            self._active = None

    # ================================================================== gates
    def operation_checks(self, op: OpCode) -> list[CheckCode]:
        count = self._settings().limits.sensor_reading_count
        return [
            code
            for code in operation(op).checks
            if code is not CheckCode.B3_T_AMB
            and (code.reading_index is None or code.reading_index <= count)
        ]

    def required_checks(self, stage: Stage) -> list[CheckCode]:
        return [code for op in operations_of(stage) for code in self.operation_checks(op.code)]

    @staticmethod
    def _satisfied(active: _Active, code: CheckCode) -> bool:
        if code in CHECKLISTS:
            return active.marks.get(code) is True
        outcome = active.outcomes.get(code)
        if outcome is None:
            return False
        if code.meta.kind is CheckKind.INFO:
            return True
        return outcome.passed is True

    def _op_done(self, active: _Active, op: OpCode) -> bool:
        return all(self._satisfied(active, code) for code in self.operation_checks(op))

    def missing_checks(self) -> list[CheckCode]:
        with self._lock:
            active = self._on_bench()
            if active is None:
                return []
            return [
                code
                for op in active.segment
                for code in self.operation_checks(op)
                if not self._satisfied(active, code)
            ]

    def is_stage_complete(self, stage: Stage) -> bool:
        with self._lock:
            active = self._active
            if active is None or stage not in ORDER or active.status is DeviceStatus.REJECTED:
                return False
            current, target = ORDER.index(active.stage), ORDER.index(stage)
            if target != current:
                return target < current
            return all(
                op.code in active.passed_ops
                or (op.code in active.segment and self._op_done(active, op.code))
                for op in operations_of(stage)
            )

    def can_submit(self) -> bool:
        with self._lock:
            active = self._active
            return (
                active is not None
                and active.status is DeviceStatus.IN_PROGRESS
                and not self.missing_checks()
            )

    # ================================================================== checks
    def submit_check(
        self, check_code: CheckCode, value: CheckValue = None, *, text: str | None = None
    ) -> CheckOutcome:
        with self._lock:
            active = self._require_active()
            self._require_in_sitting(active, check_code)
            if check_code in (*ELECTRICAL_CODES, CheckCode.B3_T_AMB):
                raise RecordStateError("electrical checks go through evaluate_measurement()")
            if check_code is CheckCode.C_ID_SYNC:
                raise RecordStateError("identity goes through reconcile_identity()")
            if check_code in CHECKLISTS:
                return self._tick(active, check_code, _as_bool(value, check_code))
            if check_code is CheckCode.A_WHITELIST:
                return self._whitelist(active, _as_bool(value, check_code), text)
            if check_code is CheckCode.A_UPLOAD:
                return self._upload(active, _as_bool(value, check_code), text)
            if check_code is CheckCode.B1_COMM:
                return self._comm(active, _as_bool(value, check_code), text)
            if check_code.reading_index is not None:
                return self._reading(active, check_code, value)
            if check_code in OPERATOR_MARKS:
                return self._operator_mark(active, check_code, _as_bool(value, check_code))
            if check_code is CheckCode.C_QR_READ:
                return self._qr_read(active, value)
        raise RecordStateError(f"unsupported check {check_code.value}")  # pragma: no cover

    def _require_in_sitting(self, active: _Active, code: CheckCode) -> None:
        """Only checks of the steps on the bench; results other than checklist ticks belong
        to the step whose run is open."""
        op = operation_for_check(code).code
        if op not in active.segment:
            raise RecordStateError(
                f"{code.value} belongs to {op.value}, which is not on the bench now",
                context={"op": op.value},
            )
        if op is not active.op and code not in CHECKLISTS:
            raise RecordStateError(f"finish {active.op.value} before {code.value}")

    def _tick(self, active: _Active, code: CheckCode, ticked: bool) -> CheckOutcome:
        active.marks[code] = ticked
        return CheckOutcome(check_code=code, stage=code.stage, passed=ticked)

    def _whitelist(self, active: _Active, allowed: bool, text: str | None) -> CheckOutcome:
        detail = active.mac_address if not text else f"{active.mac_address} | {text}"
        outcome = self._record(active, CheckCode.A_WHITELIST, passed=allowed, value_text=detail)
        if not allowed:
            return self._fail(
                active, outcome, "reject.reason.whitelist_denied", {"mac": active.mac_address}
            )
        return outcome

    def _upload(self, active: _Active, success: bool, text: str | None) -> CheckOutcome:
        if not self._satisfied(active, CheckCode.A_WHITELIST):
            raise RecordStateError("whitelist must pass before uploading")
        if self._satisfied(active, CheckCode.A_UPLOAD):
            raise RecordStateError("firmware already uploaded")
        policy = self._policy()
        max_attempts = policy.max_attempts(CheckCode.A_UPLOAD)
        if active.attempts.get(CheckCode.A_UPLOAD, 0) >= max_attempts:
            raise RecordStateError("no upload attempts left")
        attempt = active.bump(CheckCode.A_UPLOAD)
        event = CounterEvent.UPLOAD_SUCCESS if success else CounterEvent.UPLOAD_FAILURE
        self._records.counter_event(event, active.device_row_id)
        if success and text:
            self._records.set_device_firmware(active.device_row_id, text)
        if not success:
            active.upload_failures += 1
        retry = not success and policy.retry_allowed(CheckCode.A_UPLOAD, attempt)
        outcome = self._record(
            active,
            CheckCode.A_UPLOAD,
            passed=success,
            value_text=text,
            attempt=attempt,
            max_attempts=max_attempts,
            retry_allowed=retry,
            reason_key=None if success else "reject.reason.upload_failed",
        )
        if not success and not retry:
            key = "reject.reason.upload_failed" + ("_max" if max_attempts > 1 else "")
            return self._fail(active, outcome, key, {"attempts": attempt})
        return outcome

    def _comm(self, active: _Active, ok: bool, text: str | None) -> CheckOutcome:
        policy = self._policy()
        attempt = active.bump(CheckCode.B1_COMM)
        retry = not ok and policy.retry_allowed(CheckCode.B1_COMM, attempt)
        outcome = self._record(
            active,
            CheckCode.B1_COMM,
            passed=ok,
            value_text=text,
            attempt=attempt,
            max_attempts=policy.max_attempts(CheckCode.B1_COMM),
            retry_allowed=retry,
            reason_key=None if ok else "reject.reason.comm_failed",
        )
        if not ok and not retry:
            return self._fail(active, outcome, "reject.reason.comm_failed", {})
        return outcome

    def _reading(self, active: _Active, code: CheckCode, value: CheckValue) -> CheckOutcome:
        if not self._satisfied(active, CheckCode.B1_COMM):
            raise RecordStateError("communication test must pass before sensor readings")
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise InputError(f"{code.value} needs a numeric reading")
        index = code.reading_index
        total = self._settings().limits.sensor_reading_count
        expected = len(active.readings) + 1
        if index != expected or expected > total:
            raise RecordStateError(f"expected reading {expected} of {total}, got {index}")
        active.readings.append(float(value))
        return self._record(active, code, passed=None, value_num=float(value))

    def _operator_mark(self, active: _Active, code: CheckCode, ok: bool) -> CheckOutcome:
        total = self._settings().limits.sensor_reading_count
        if code is CheckCode.B2_SENSOR_OK and len(active.readings) < total:
            raise RecordStateError(f"take all {total} sensor readings first")
        if not self._satisfied(active, CheckCode.B1_COMM):
            raise RecordStateError("communication test must pass first")
        active.marks[code] = ok
        outcome = self._record(active, code, passed=ok, operator_marked=True)
        if not ok:
            return self._fail(
                active,
                outcome,
                "reject.reason.operator_marked_fail",
                {"check_key": code.label_key},
            )
        return outcome

    def _qr_read(self, active: _Active, value: CheckValue) -> CheckOutcome:
        if not isinstance(value, str) or not value.strip():
            raise InputError("C_QR_READ needs the decoded ID text")
        qr = value.strip()
        if not id_format_ok(qr, self._settings().camera.id_pattern):
            # A wrong label is not a device fault: record it and let the operator rescan.
            return self._record(
                active,
                CheckCode.C_QR_READ,
                passed=False,
                value_text=qr,
                retry_allowed=True,
                reason_key="identity.qr_bad_format",
                reason_params={"value": qr},
            )
        # A new scan starts identity over: an earlier match must not carry over to this QR.
        active.qr_id = qr
        active.identity = None
        active.outcomes.pop(CheckCode.C_ID_SYNC, None)
        if active.device_id != qr:
            active.device_id = None
        return self._record(active, CheckCode.C_QR_READ, passed=True, value_text=qr)

    # ================================================================== step flow
    def submit_and_next(self) -> StepResult:
        with self._lock:
            active = self._require_active()
            missing = self.missing_checks()
            if missing:
                raise RecordStateError(
                    "stage gate not satisfied", context={"missing": [c.value for c in missing]}
                )
            result, events = self._finish_sitting(active, park=False)
        for event in events:
            self._bus.publish(event)
        return result

    def _finish_sitting(self, active: _Active, *, park: bool) -> tuple[StepResult, list[Event]]:
        """Pass every step of the sitting, then continue with the board's next step on this
        bench (chosen and possible here, unless ``park``) or park it for that step's tray."""
        events: list[Event] = []
        row = active.device_row_id
        old_stage = active.stage
        sitting = active.segment
        for index, op in enumerate(sitting):
            self._record_ticks(active, op)
            if index + 1 < len(sitting):
                self._pass_and_claim(active, sitting[index + 1])
                active.segment = sitting[index + 1 :]
        last = active.op
        following = last.next
        if following is None:
            self._records.complete_device(row)
            self._records.record_transition(row, old_stage, Stage.COMPLETE)
            active.passed_ops.append(last)
            active.status = DeviceStatus.COMPLETE
            active.stage = Stage.COMPLETE
            active.segment = ()
            events += [
                StageChanged(row, old_stage, Stage.COMPLETE),
                DeviceCompleted(row, active.device_id),
            ]
            log.info("device row %d complete", row)
            return StepResult(stage=Stage.COMPLETE), events
        new_stage = following.stage
        if new_stage is not old_stage:
            check_transition(old_stage, new_stage)
            self._records.record_transition(row, old_stage, new_stage)
            events.append(StageChanged(row, old_stage, new_stage))
        if not park and following in self._selected and following in self._bench:
            self._pass_and_claim(active, following)
            active.stage = new_stage
            active.segment = self._segment(following)
            log.info("device row %d continues with %s", row, following.value)
            return StepResult(stage=new_stage, next_op=following), events
        self._records.pass_run()
        active.passed_ops.append(last)
        self._active = None
        events.append(DeviceParked(row, following))
        log.info("device row %d parked for %s", row, following.value)
        return StepResult(stage=new_stage, next_op=following, parked=True), events

    def _pass_and_claim(self, active: _Active, following: OpCode) -> None:
        """Pass the open step and claim ``following`` for the board that stays on the bench."""
        self._records.pass_run()
        active.passed_ops.append(active.op)
        by = IdentifyBy.MAC if active.identified_by is IdentifyBy.NEW else active.identified_by
        self._records.claim(active.device_row_id, following, by)
        active.op = following

    def _record_ticks(self, active: _Active, op: OpCode) -> None:
        """Checklist ticks are written when their step is passed (W8)."""
        for code in operation(op).checks:
            if code in CHECKLISTS:
                self._record(active, code, passed=True, operator_marked=True, publish=False)

    def reject(
        self,
        check_code: CheckCode,
        reason_key: str = "reject.reason.manual",
        **reason_params: object,
    ) -> RejectInstruction:
        with self._lock:
            active = self._require_active()
            if operation_for_check(check_code).code not in active.segment:
                raise RecordStateError(
                    f"cannot reject for {check_code.value} during {active.op.value}"
                )
            last = active.outcomes.get(check_code)
            if last is None or last.passed is not False:
                last = self._record(
                    active, check_code, passed=False, operator_marked=True, publish=False
                )
            params: dict[str, Any] = {"check_key": check_code.label_key, **reason_params}
            return self._do_reject(active, last, reason_key, params)

    def can_retry_programming(self) -> bool:
        with self._lock:
            active = self._on_bench()
            if active is None or active.op is not OpCode.A_PROGRAM:
                return False
            last = active.outcomes.get(CheckCode.A_UPLOAD)
            return (
                last is not None
                and last.passed is False
                and active.attempts.get(CheckCode.A_UPLOAD, 0)
                < self._policy().max_attempts(CheckCode.A_UPLOAD)
            )

    # ================================================================== testing
    def evaluate_measurement(self, measurement: Measurement) -> list[CheckOutcome]:
        with self._lock:
            active = self._require_active()
            if active.op is not OpCode.B_TEST:
                raise RecordStateError("measurement outside the testing step")
            total = self._settings().limits.sensor_reading_count
            if not (
                self._satisfied(active, CheckCode.B1_COMM)
                and len(active.readings) >= total
                and active.marks.get(CheckCode.B2_SENSOR_OK) is True
                and active.marks.get(CheckCode.B2_INDICATOR_OK) is True
            ):
                raise RecordStateError("finish B1 and B2 before measuring")
            settings = self._settings()
            policy = RetryPolicy(settings)
            ambient_reading = self._records.latest_ambient()
            ambient = ambient_reading.value_c if ambient_reading else None
            verdicts = measurement_verdicts(measurement, settings.limits, ambient)
            attempt = active.bump(CheckCode.B3_V_A)  # one counter for the whole measurement
            any_failed = any(not v.passed for v in verdicts)
            retry = any_failed and policy.retry_allowed(CheckCode.B3_V_A, attempt)
            outcomes: list[CheckOutcome] = []
            for verdict in verdicts:
                outcomes.append(
                    self._record(
                        active,
                        verdict.check_code,
                        passed=verdict.passed,
                        value_num=verdict.value,
                        value_text=verdict.detail,
                        limits=(verdict.low, verdict.high),
                        reason_key=verdict.reason_key,
                        reason_params=verdict.params,
                        attempt=attempt,
                        max_attempts=policy.max_attempts(CheckCode.B3_V_A),
                        retry_allowed=retry and not verdict.passed,
                    )
                )
            if measurement.t_amb_c is not None:
                self._record(
                    active,
                    CheckCode.B3_T_AMB,
                    passed=None,
                    value_num=float(quantize(measurement.t_amb_c, settings.limits.decimals)),
                )
            if any_failed and not retry:
                index, first = next((i, o) for i, o in enumerate(outcomes) if o.passed is False)
                verdict = verdicts[index]
                assert verdict.reason_key is not None
                outcomes[index] = self._fail(active, first, verdict.reason_key, verdict.params)
            return outcomes

    # ================================================================== labeling
    def reconcile_identity(
        self,
        qr_id: str,
        device_id: str | None,
        *,
        after_write: bool = False,
        method: IdEntryMethod = IdEntryMethod.CAMERA,
    ) -> IdentityOutcome:
        with self._lock:
            active = self._require_active()
            if active.op is not OpCode.C_CODE:
                raise RecordStateError("identity is reconciled in the code insertion step")
            qr = qr_id.strip()
            if active.qr_id is None or qr != active.qr_id:
                raise RecordStateError("read the QR code first")
            current = (device_id or "").strip()
            if not after_write:
                if ids_match(qr, current):
                    return self._identity_ok(active, qr, method, IdentityStatus.MATCH, "match")
                active.identity = IdentityStatus.WRITE_REQUIRED
                return IdentityOutcome(
                    status=IdentityStatus.WRITE_REQUIRED, qr_id=qr, device_id=current or None
                )
            if active.identity is not IdentityStatus.WRITE_REQUIRED:
                raise RecordStateError("no ID write was requested")
            if ids_match(qr, current):
                return self._identity_ok(active, qr, method, IdentityStatus.CONFIRMED, "written")
            active.identity = IdentityStatus.FAILED
            params = {"qr": qr, "device": current or "-"}
            outcome = self._record(
                active,
                CheckCode.C_ID_SYNC,
                passed=False,
                value_text=f"qr {qr} / device {current or '-'}",
                reason_key="reject.reason.id_sync_failed",
                reason_params=params,
            )
            rejected = self._fail(active, outcome, "reject.reason.id_sync_failed", params)
            return IdentityOutcome(
                status=IdentityStatus.FAILED,
                qr_id=qr,
                device_id=current or None,
                reject=rejected.reject,
            )

    def _identity_ok(
        self, active: _Active, qr: str, method: IdEntryMethod, status: IdentityStatus, word: str
    ) -> IdentityOutcome:
        self._records.set_device_id(active.device_row_id, qr, method)
        active.device_id = qr
        active.identity = status
        self._record(active, CheckCode.C_ID_SYNC, passed=True, value_text=f"{word} {qr}")
        return IdentityOutcome(status=status, qr_id=qr, device_id=qr)

    # ================================================================== internals
    def _on_bench(self) -> _Active | None:
        """The board being worked on (``None`` when idle or the board is finished)."""
        active = self._active
        return active if active is not None and active.status is DeviceStatus.IN_PROGRESS else None

    def _require_active(self) -> _Active:
        active = self._active
        if active is None:
            raise RecordStateError("no device on the bench")
        if active.status is not DeviceStatus.IN_PROGRESS:
            raise RecordStateError(f"device is already {active.status.value}")
        return active

    def _record(
        self,
        active: _Active,
        code: CheckCode,
        *,
        passed: bool | None,
        value_num: float | None = None,
        value_text: str | None = None,
        limits: tuple[float | None, float | None] | None = None,
        operator_marked: bool = False,
        attempt: int = 1,
        max_attempts: int = 1,
        retry_allowed: bool = False,
        reason_key: str | None = None,
        reason_params: dict[str, Any] | None = None,
        publish: bool = True,
    ) -> CheckOutcome:
        self._records.record_check(
            active.device_row_id,
            code.stage,
            code,
            value=value_num,
            value_text=value_text,
            limits=limits,
            passed=passed,
            operator_marked=operator_marked,
        )
        low, high = limits if limits is not None else (None, None)
        outcome = CheckOutcome(
            check_code=code,
            stage=code.stage,
            passed=passed,
            value_num=value_num,
            value_text=value_text,
            unit=code.meta.unit,
            limit_low=low,
            limit_high=high,
            reason_key=reason_key,
            reason_params=dict(reason_params or {}),
            retry_allowed=retry_allowed,
            attempt=attempt,
            max_attempts=max_attempts,
        )
        active.outcomes[code] = outcome
        if publish:
            self._bus.publish(CheckRecorded(active.device_row_id, outcome))
        return outcome

    def _fail(
        self, active: _Active, outcome: CheckOutcome, reason_key: str, params: dict[str, Any]
    ) -> CheckOutcome:
        full = {"check_key": outcome.check_code.label_key, **params}
        instruction = self._do_reject(active, outcome, reason_key, full)
        rejected = outcome.model_copy(
            update={"reject": instruction, "reason_key": reason_key, "reason_params": full}
        )
        active.outcomes[outcome.check_code] = rejected
        return rejected

    def _do_reject(
        self,
        active: _Active,
        outcome: CheckOutcome,
        reason_key: str,
        params: dict[str, Any],
    ) -> RejectInstruction:
        stage = active.stage
        check_transition(stage, Stage.REJECTED)
        code = outcome.check_code
        self._records.reject_device(active.device_row_id, stage, code, reason_key, params)
        self._records.record_transition(active.device_row_id, stage, Stage.REJECTED)
        instruction = RejectInstruction(
            device_row_id=active.device_row_id,
            stage=stage,
            check_code=code,
            reason_key=reason_key,
            reason_params=params,
            value_num=outcome.value_num,
            value_text=outcome.value_text,
            unit=outcome.unit,
            limit_low=outcome.limit_low,
            limit_high=outcome.limit_high,
        )
        active.status = DeviceStatus.REJECTED
        active.stage = Stage.REJECTED
        active.reject = instruction
        self._bus.publish(StageChanged(active.device_row_id, stage, Stage.REJECTED))
        self._bus.publish(DeviceRejected(active.device_row_id, instruction))
        log.info("device row %d rejected at %s (%s)", active.device_row_id, stage.value, code.value)
        return instruction

    def _snapshot(self) -> DeviceState | None:
        active = self._active
        if active is None:
            return None
        return DeviceState(
            device_row_id=active.device_row_id,
            mac_address=active.mac_address,
            device_id=active.device_id,
            qr_id=active.qr_id,
            stage=active.stage,
            status=active.status,
            started_at=active.started_at,
            upload_attempts=active.attempts.get(CheckCode.A_UPLOAD, 0),
            upload_failures=active.upload_failures,
            readings=list(active.readings),
            marks=dict(active.marks),
            outcomes=dict(active.outcomes),
            identity=active.identity,
            reject=active.reject,
            op=active.op if active.status is DeviceStatus.IN_PROGRESS else None,
            passed_ops=list(active.passed_ops),
            resumed=active.resumed,
        )


def _as_bool(value: CheckValue, code: CheckCode) -> bool:
    if not isinstance(value, bool):
        raise InputError(f"{code.value} needs True/False, got {value!r}")
    return value
