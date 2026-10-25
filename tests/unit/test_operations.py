"""Operation catalogue: every check in exactly one step, stages split in line order."""

from __future__ import annotations

from collections import Counter
from itertools import groupby

from parkomate.core.enums import (
    LABELING_CHECKLIST,
    LINE_ORDER,
    PRODUCTION_STAGES,
    BenchNeed,
    CheckCode,
    IdentifyBy,
    OpCode,
    Stage,
)
from parkomate.workflow.operations import (
    OPERATIONS,
    is_last_of_stage,
    next_operation,
    operation,
    operation_for_check,
    operations_of,
)


def test_catalogue_is_in_line_order() -> None:
    assert [op.code for op in OPERATIONS] == list(LINE_ORDER) == list(OpCode)


def test_every_check_belongs_to_exactly_one_operation() -> None:
    counts = Counter(check for op in OPERATIONS for check in op.checks)
    assert set(counts) == set(CheckCode)
    assert set(counts.values()) == {1}


def test_checks_belong_to_the_stage_of_their_operation() -> None:
    for op in OPERATIONS:
        assert op.stage is op.code.stage
        assert all(check.stage is op.stage for check in op.checks), op.code


def test_operations_of_a_stage_are_consecutive() -> None:
    stages = [stage for stage, _ in groupby(op.stage for op in OPERATIONS)]
    assert stages == list(PRODUCTION_STAGES)


def test_labeling_is_split_into_code_casing_branding() -> None:
    assert [op.code for op in operations_of(Stage.LABELING)] == [
        OpCode.C_CODE,
        OpCode.C_CASING,
        OpCode.C_BRANDING,
    ]
    labeling_checks = {check for op in operations_of(Stage.LABELING) for check in op.checks}
    assert labeling_checks == {*LABELING_CHECKLIST, CheckCode.C_QR_READ, CheckCode.C_ID_SYNC}
    assert operation_for_check(CheckCode.C4).code is OpCode.C_CODE  # QR sticker with the code
    assert operation_for_check(CheckCode.C1).code is OpCode.C_CASING
    assert operation_for_check(CheckCode.C3).code is OpCode.C_BRANDING


def test_terminal_stages_have_no_operations() -> None:
    assert operations_of(Stage.COMPLETE) == ()
    assert operations_of(Stage.REJECTED) == ()


def test_next_operation_walks_the_line() -> None:
    walked = [OpCode.A_PROGRAM]
    while (following := next_operation(walked[-1])) is not None:
        walked.append(following)
    assert walked == list(LINE_ORDER)
    assert next_operation(OpCode.D_PACK) is None


def test_last_operation_of_each_stage() -> None:
    last = {code for code in OpCode if is_last_of_stage(code)}
    assert last == {OpCode.A_PROGRAM, OpCode.B_TEST, OpCode.C_BRANDING, OpCode.D_PACK}


def test_every_reading_slot_is_recorded_in_testing() -> None:
    assert operation_for_check(CheckCode.reading(10)).code is OpCode.B_TEST
    assert operation_for_check(CheckCode.B3_T_AMB).code is OpCode.B_TEST


def test_identification_matches_the_bench() -> None:
    for op in OPERATIONS:
        assert op.identify_by in (IdentifyBy.MAC, IdentifyBy.QR), op.code
        if op.identify_by is IdentifyBy.MAC:
            assert BenchNeed.SERIAL in op.needs, op.code
        else:
            assert BenchNeed.CAMERA in op.needs, op.code


def test_bench_needs() -> None:
    assert operation(OpCode.A_PROGRAM).needs == {BenchNeed.SERIAL, BenchNeed.SERVER}
    assert BenchNeed.MEASUREMENT in operation(OpCode.B_TEST).needs
    assert operation(OpCode.D_PACK).needs == {BenchNeed.CAMERA}
    serial_free = {op.code for op in OPERATIONS if BenchNeed.SERIAL not in op.needs}
    assert serial_free == {OpCode.C_CASING, OpCode.C_BRANDING, OpCode.D_PACK}
