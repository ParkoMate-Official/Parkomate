"""Session summary computation (shared by the summary card, e-mail and reports)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from parkomate.core.enums import (
    PRODUCTION_STAGES,
    CounterEvent,
    DeviceStatus,
    RepairEventKind,
    Stage,
)
from parkomate.core.models import SessionSummary

if TYPE_CHECKING:
    from parkomate.data import Repositories


def build_session_summary(repos: Repositories, session_id: int) -> SessionSummary:
    """Totals for the whole session (counter resets do not affect the summary)."""
    session = repos.sessions.require(session_id)
    operator = repos.operators.get(session.operator_id)
    devices = repos.devices.list_for_session(session_id)
    events = repos.counters.list_for_session(session_id)

    totals = dict.fromkeys(CounterEvent, 0)
    failed_devices: set[int] = set()
    for event in events:
        totals[event.event] += 1
        if event.event is CounterEvent.UPLOAD_FAILURE and event.device_row_id is not None:
            failed_devices.add(event.device_row_id)

    rejected_by_stage: dict[Stage, int] = dict.fromkeys(PRODUCTION_STAGES, 0)
    complete = abandoned = in_progress = first_pass = first_finished = 0
    retests = retests_passed = 0
    for device in devices:
        if device.is_retest:
            retests += 1
            retests_passed += device.status is DeviceStatus.COMPLETE
        elif device.status in (DeviceStatus.COMPLETE, DeviceStatus.REJECTED):
            first_finished += 1
        if device.status is DeviceStatus.COMPLETE:
            complete += 1
            if device.id not in failed_devices and not device.is_retest:
                first_pass += 1
        elif device.status is DeviceStatus.REJECTED and device.reject_stage is not None:
            rejected_by_stage[device.reject_stage] += 1
        elif device.status is DeviceStatus.ABANDONED:
            abandoned += 1
        elif device.status is DeviceStatus.IN_PROGRESS:
            in_progress += 1
    repair_steps = dict.fromkeys(RepairEventKind, 0)
    for step in repos.repairs.events_for_sessions([session_id]):
        repair_steps[step.event] += 1

    return SessionSummary(
        session=session,
        operator_code=operator.operator_code if operator else "",
        operator_name=operator.full_name if operator else "",
        ambient_readings=repos.sessions.ambient_readings(session_id),
        total_devices=len(devices),
        complete=complete,
        rejected_by_stage=rejected_by_stage,
        abandoned=abandoned,
        in_progress=in_progress,
        upload_success=totals[CounterEvent.UPLOAD_SUCCESS],
        upload_failure=totals[CounterEvent.UPLOAD_FAILURE],
        failures_adjusted=totals[CounterEvent.FAILURE_ADJUSTED],
        counter_resets=totals[CounterEvent.RESET],
        first_pass_complete=first_pass,
        first_pass_finished=first_finished,
        retests=retests,
        retests_passed=retests_passed,
        repairs_written=repair_steps[RepairEventKind.REPAIRED],
        repairs_accepted=repair_steps[RepairEventKind.ACCEPTED],
        repairs_scrapped=repair_steps[RepairEventKind.SCRAPPED],
    )
