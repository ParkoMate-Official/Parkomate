"""The operation catalogue: how each stage is split into the steps one worker does on one
board in one sitting.

    A_PROGRAM → B_TEST → C_CODE → C_CASING → C_BRANDING → D_PACK
        A          B     └────────── C ──────────┘          D

Rules
* Every :class:`CheckCode` belongs to exactly one operation, of the same stage.
* The operations of a stage are consecutive in line order. A stage is complete when its last
  operation passes; that is when the stage transition is recorded.
* ``identify_by`` says how a board is recognised when it is picked up for the operation,
  ``needs`` what the bench must have to perform it.

The labeling split (code insertion, casing, branding) is the proposed default; the client still
has to confirm it (``docs/MULTI_WORKER_PLAN.md``, open question 2).
"""

from __future__ import annotations

from dataclasses import dataclass

from parkomate.core.enums import (
    LINE_ORDER,
    MAX_SENSOR_READINGS,
    BenchNeed,
    CheckCode,
    IdentifyBy,
    OpCode,
    Stage,
)


@dataclass(frozen=True, slots=True)
class Operation:
    code: OpCode
    checks: tuple[CheckCode, ...]
    """Every check recorded in this operation (all reading slots, not only the configured N)."""
    identify_by: IdentifyBy
    needs: frozenset[BenchNeed]

    @property
    def stage(self) -> Stage:
        return self.code.stage


_N = BenchNeed
OPERATIONS: tuple[Operation, ...] = (
    Operation(
        OpCode.A_PROGRAM,
        (CheckCode.A_WHITELIST, CheckCode.A_UPLOAD),
        IdentifyBy.MAC,
        frozenset({_N.SERIAL, _N.SERVER}),
    ),
    Operation(
        OpCode.B_TEST,
        (
            CheckCode.B1_COMM,
            *(CheckCode.reading(i) for i in range(1, MAX_SENSOR_READINGS + 1)),
            CheckCode.B2_SENSOR_OK,
            CheckCode.B2_INDICATOR_OK,
            CheckCode.B3_V_A,
            CheckCode.B3_V_B,
            CheckCode.B3_V_C,
            CheckCode.B3_T_REG,
            CheckCode.B3_T_AMB,
        ),
        IdentifyBy.MAC,
        frozenset({_N.SERIAL, _N.MEASUREMENT}),
    ),
    Operation(
        OpCode.C_CODE,
        (CheckCode.C_QR_READ, CheckCode.C_ID_SYNC, CheckCode.C4),
        IdentifyBy.MAC,
        frozenset({_N.SERIAL, _N.CAMERA}),
    ),
    Operation(
        OpCode.C_CASING,
        (CheckCode.C1, CheckCode.C2),
        IdentifyBy.QR,
        frozenset({_N.CAMERA}),
    ),
    Operation(
        OpCode.C_BRANDING,
        (CheckCode.C3,),
        IdentifyBy.QR,
        frozenset({_N.CAMERA}),
    ),
    Operation(
        OpCode.D_PACK,
        (CheckCode.D1, CheckCode.D2, CheckCode.D3, CheckCode.D4),
        IdentifyBy.QR,
        frozenset({_N.CAMERA}),
    ),
)

_BY_CODE: dict[OpCode, Operation] = {op.code: op for op in OPERATIONS}
_BY_CHECK: dict[CheckCode, Operation] = {check: op for op in OPERATIONS for check in op.checks}


def operation(code: OpCode) -> Operation:
    return _BY_CODE[code]


def operation_for_check(check: CheckCode) -> Operation:
    """The operation in which ``check`` is recorded."""
    return _BY_CHECK[check]


def operations_of(stage: Stage) -> tuple[Operation, ...]:
    """Operations of ``stage`` in line order (empty for COMPLETE / REJECTED)."""
    return tuple(op for op in OPERATIONS if op.stage is stage)


def next_operation(code: OpCode) -> OpCode | None:
    """The step after ``code``; ``None`` after the last one (the board is complete)."""
    index = LINE_ORDER.index(code) + 1
    return LINE_ORDER[index] if index < len(LINE_ORDER) else None


def is_last_of_stage(code: OpCode) -> bool:
    """True when passing ``code`` completes its stage."""
    following = next_operation(code)
    return following is None or following.stage is not code.stage
