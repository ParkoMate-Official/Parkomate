"""Enumerations shared by every layer (UI, data, workflow, hardware).

All enums are ``StrEnum`` so their values are stored verbatim in SQLite and TOML.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

MAX_SENSOR_READINGS = 10
"""Upper bound for ``limits.sensor_reading_count`` (one CheckCode exists per reading slot)."""


class Stage(StrEnum):
    """Production stages. The four production stages plus the two terminal states."""

    PROGRAMMING = "programming"
    TESTING = "testing"
    LABELING = "labeling"
    PACKAGING = "packaging"
    COMPLETE = "complete"
    REJECTED = "rejected"

    @property
    def letter(self) -> str:
        """Box / report letter: A-D for production stages, empty for terminal states."""
        return _STAGE_LETTERS.get(self, "")

    @property
    def label_key(self) -> str:
        """i18n key of the stage name."""
        return f"stage.{self.value}"

    @property
    def is_production(self) -> bool:
        return self in PRODUCTION_STAGES


_STAGE_LETTERS: dict[Stage, str] = {
    Stage.PROGRAMMING: "A",
    Stage.TESTING: "B",
    Stage.LABELING: "C",
    Stage.PACKAGING: "D",
}

PRODUCTION_STAGES: tuple[Stage, ...] = (
    Stage.PROGRAMMING,
    Stage.TESTING,
    Stage.LABELING,
    Stage.PACKAGING,
)


class DeviceStatus(StrEnum):
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"
    REJECTED = "rejected"
    ABANDONED = "abandoned"

    @property
    def label_key(self) -> str:
        return f"device_status.{self.value}"


class Role(StrEnum):
    OPERATOR = "operator"
    ADMIN = "admin"

    @property
    def label_key(self) -> str:
        return f"role.{self.value}"


class SessionEndReason(StrEnum):
    LOGOUT = "logout"
    CLOSE = "close"
    CRASH_RECOVERED = "crash_recovered"

    @property
    def label_key(self) -> str:
        return f"session_end.{self.value}"


class AmbientReason(StrEnum):
    SESSION_START = "session_start"
    REMEASURE = "remeasure"

    @property
    def label_key(self) -> str:
        return f"ambient_reason.{self.value}"


class CounterEvent(StrEnum):
    UPLOAD_SUCCESS = "upload_success"
    UPLOAD_FAILURE = "upload_failure"
    FAILURE_ADJUSTED = "failure_adjusted"
    RESET = "reset"


class IdEntryMethod(StrEnum):
    CAMERA = "camera"
    MANUAL = "manual"

    @property
    def label_key(self) -> str:
        return f"id_method.{self.value}"


class OutboxStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"

    @property
    def label_key(self) -> str:
        return f"outbox_status.{self.value}"


class Severity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class CheckKind(StrEnum):
    """How a check gets its result."""

    MEASURED = "measured"  # numeric value compared with limits by the workflow
    MARKED = "marked"  # operator marks success / failure (or ticks a checklist row)
    AUTOMATIC = "automatic"  # result produced by hardware/server (whitelist, upload, ping...)
    INFO = "info"  # value recorded for traceability only, no pass/fail


class CheckCode(StrEnum):
    """Every check the station can record. Stored verbatim in ``check_results.check_code``."""

    # A - Programming
    A_WHITELIST = "A_WHITELIST"
    A_UPLOAD = "A_UPLOAD"
    # B - Testing
    B1_COMM = "B1_COMM"
    B2_READING_1 = "B2_READING_1"
    B2_READING_2 = "B2_READING_2"
    B2_READING_3 = "B2_READING_3"
    B2_READING_4 = "B2_READING_4"
    B2_READING_5 = "B2_READING_5"
    B2_READING_6 = "B2_READING_6"
    B2_READING_7 = "B2_READING_7"
    B2_READING_8 = "B2_READING_8"
    B2_READING_9 = "B2_READING_9"
    B2_READING_10 = "B2_READING_10"
    B2_SENSOR_OK = "B2_SENSOR_OK"
    B2_INDICATOR_OK = "B2_INDICATOR_OK"
    B3_V_A = "B3_V_A"
    B3_V_B = "B3_V_B"
    B3_V_C = "B3_V_C"
    B3_T_REG = "B3_T_REG"
    B3_T_AMB = "B3_T_AMB"
    # C - Labeling
    C1 = "C1"
    C2 = "C2"
    C3 = "C3"
    C4 = "C4"
    C_QR_READ = "C_QR_READ"
    C_ID_SYNC = "C_ID_SYNC"
    # D - Packaging
    D1 = "D1"
    D2 = "D2"
    D3 = "D3"
    D4 = "D4"

    @property
    def meta(self) -> CheckMeta:
        return CHECK_META[self]

    @property
    def stage(self) -> Stage:
        return CHECK_META[self].stage

    @property
    def label_key(self) -> str:
        """i18n key of the check's human name (e.g. ``check.B3_V_C``)."""
        return f"check.{self.value}"

    @staticmethod
    def reading(index: int) -> CheckCode:
        """CheckCode for sensor reading ``index`` (1-based)."""
        if not 1 <= index <= MAX_SENSOR_READINGS:
            raise ValueError(f"reading index must be 1..{MAX_SENSOR_READINGS}, got {index}")
        return CheckCode(f"B2_READING_{index}")

    @property
    def reading_index(self) -> int | None:
        """1-based index if this is a sensor reading code, else None."""
        prefix = "B2_READING_"
        if self.value.startswith(prefix):
            return int(self.value[len(prefix) :])
        return None


@dataclass(frozen=True, slots=True)
class CheckMeta:
    stage: Stage
    kind: CheckKind
    unit: str | None = None


_M = CheckMeta
CHECK_META: dict[CheckCode, CheckMeta] = {
    CheckCode.A_WHITELIST: _M(Stage.PROGRAMMING, CheckKind.AUTOMATIC),
    CheckCode.A_UPLOAD: _M(Stage.PROGRAMMING, CheckKind.AUTOMATIC),
    CheckCode.B1_COMM: _M(Stage.TESTING, CheckKind.AUTOMATIC),
    **{
        CheckCode.reading(i): _M(Stage.TESTING, CheckKind.INFO)
        for i in range(1, MAX_SENSOR_READINGS + 1)
    },
    CheckCode.B2_SENSOR_OK: _M(Stage.TESTING, CheckKind.MARKED),
    CheckCode.B2_INDICATOR_OK: _M(Stage.TESTING, CheckKind.MARKED),
    CheckCode.B3_V_A: _M(Stage.TESTING, CheckKind.MEASURED, "V"),
    CheckCode.B3_V_B: _M(Stage.TESTING, CheckKind.MEASURED, "V"),
    CheckCode.B3_V_C: _M(Stage.TESTING, CheckKind.MEASURED, "V"),
    CheckCode.B3_T_REG: _M(Stage.TESTING, CheckKind.MEASURED, "°C"),
    CheckCode.B3_T_AMB: _M(Stage.TESTING, CheckKind.INFO, "°C"),
    CheckCode.C1: _M(Stage.LABELING, CheckKind.MARKED),
    CheckCode.C2: _M(Stage.LABELING, CheckKind.MARKED),
    CheckCode.C3: _M(Stage.LABELING, CheckKind.MARKED),
    CheckCode.C4: _M(Stage.LABELING, CheckKind.MARKED),
    CheckCode.C_QR_READ: _M(Stage.LABELING, CheckKind.AUTOMATIC),
    CheckCode.C_ID_SYNC: _M(Stage.LABELING, CheckKind.AUTOMATIC),
    CheckCode.D1: _M(Stage.PACKAGING, CheckKind.MARKED),
    CheckCode.D2: _M(Stage.PACKAGING, CheckKind.MARKED),
    CheckCode.D3: _M(Stage.PACKAGING, CheckKind.MARKED),
    CheckCode.D4: _M(Stage.PACKAGING, CheckKind.MARKED),
}

LABELING_CHECKLIST: tuple[CheckCode, ...] = (CheckCode.C1, CheckCode.C2, CheckCode.C3, CheckCode.C4)
PACKAGING_CHECKLIST: tuple[CheckCode, ...] = (
    CheckCode.D1,
    CheckCode.D2,
    CheckCode.D3,
    CheckCode.D4,
)
VOLTAGE_CHECKS: tuple[CheckCode, ...] = (CheckCode.B3_V_A, CheckCode.B3_V_B, CheckCode.B3_V_C)


class OpCode(StrEnum):
    """Operations: the steps one worker does on one board in one sitting, in line order.

    Every stage is split into one or more operations (catalogue: ``workflow/operations.py``).
    Stored verbatim in ``operation_runs.op_code`` and ``devices.next_op``.
    """

    A_PROGRAM = "A_PROGRAM"
    B_TEST = "B_TEST"
    C_CODE = "C_CODE"
    C_CASING = "C_CASING"
    C_BRANDING = "C_BRANDING"
    D_PACK = "D_PACK"

    @property
    def stage(self) -> Stage:
        return _OP_STAGES[self]

    @property
    def label_key(self) -> str:
        """i18n key of the step name (e.g. ``op.C_CODE`` = "C-1 Code insertion")."""
        return f"op.{self.value}"

    @property
    def next(self) -> OpCode | None:
        """The step after this one; ``None`` after the last (the board is complete)."""
        index = LINE_ORDER.index(self) + 1
        return LINE_ORDER[index] if index < len(LINE_ORDER) else None


_OP_STAGES: dict[OpCode, Stage] = {
    OpCode.A_PROGRAM: Stage.PROGRAMMING,
    OpCode.B_TEST: Stage.TESTING,
    OpCode.C_CODE: Stage.LABELING,
    OpCode.C_CASING: Stage.LABELING,
    OpCode.C_BRANDING: Stage.LABELING,
    OpCode.D_PACK: Stage.PACKAGING,
}

LINE_ORDER: tuple[OpCode, ...] = tuple(OpCode)
"""Operations in the order every board passes them."""


class IdentifyBy(StrEnum):
    """How a board is recognised when it is picked up (``operation_runs.identified_by``)."""

    NEW = "new"  # MAC not in progress anywhere: a new board, starts at A_PROGRAM
    MAC = "mac"  # read over the serial port
    QR = "qr"  # QR code scanned by the camera
    MANUAL = "manual"  # ID typed twice (camera.allow_manual_entry)


class RunOutcome(StrEnum):
    """How an operation run ended (``operation_runs.outcome``)."""

    PASSED = "passed"
    REJECTED = "rejected"
    RELEASED = "released"  # Finish later, logout or crash: the board waits for this step again
    ABANDONED = "abandoned"  # an admin wrote the board off


class BenchNeed(StrEnum):
    """Equipment a bench must have to perform an operation."""

    SERIAL = "serial"
    SERVER = "server"
    MEASUREMENT = "measurement"
    CAMERA = "camera"


class IdentityStatus(StrEnum):
    """Result of comparing the QR ID with the ID stored in the device."""

    MATCH = "match"  # IDs already equal
    WRITE_REQUIRED = "write_required"  # differ: caller must write QR ID and read back
    CONFIRMED = "confirmed"  # written and read back equal
    FAILED = "failed"  # write or read-back failed -> device rejected

    @property
    def label_key(self) -> str:
        return f"identity.{self.value}"
