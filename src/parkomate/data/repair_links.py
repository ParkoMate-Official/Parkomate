"""Keep repair cases in step with the device runs they belong to.

Called by the records service (and crash recovery) right after a device run ends, inside the
same transaction:

* a first run is **rejected** → a repair case opens (``waiting``);
* a retest **completes** → its case becomes ``passed`` (Accept is now possible);
* a retest is **rejected** → its case goes back to ``waiting`` (repair again or scrap);
* a retest is **abandoned** (cancelled, session ended, crash) → back to ``repaired``.
"""

from __future__ import annotations

import logging

from parkomate.core.enums import DeviceStatus, RepairEventKind, RepairStatus
from parkomate.core.models import Device
from parkomate.data import Repositories

log = logging.getLogger(__name__)


def link_finished_device(repos: Repositories, device: Device, operator_id: int | None) -> None:
    """Update (or open) the repair case of ``device`` after its run ended."""
    case_id = device.repair_case_id
    if case_id is None:
        if device.status is DeviceStatus.REJECTED:
            case = repos.repairs.open_case(device.id, device.mac_address)
            repos.repairs.add_event(
                case.id,
                RepairEventKind.OPENED,
                session_id=device.session_id,
                operator_id=operator_id,
                device_row_id=device.id,
                action=device.reject_check_code.value if device.reject_check_code else None,
            )
            log.info("repair case %d opened for device row %d", case.id, device.id)
        return
    transition = {
        DeviceStatus.COMPLETE: (RepairStatus.PASSED, RepairEventKind.RETEST_PASSED),
        DeviceStatus.REJECTED: (RepairStatus.WAITING, RepairEventKind.RETEST_FAILED),
        DeviceStatus.ABANDONED: (RepairStatus.REPAIRED, RepairEventKind.RETEST_CANCELLED),
    }.get(device.status)
    if transition is None:
        return
    status, event = transition
    repos.repairs.set_status(case_id, status, expected=(RepairStatus.RETESTING,))
    repos.repairs.add_event(
        case_id,
        event,
        session_id=device.session_id,
        operator_id=operator_id,
        device_row_id=device.id,
        action=device.reject_check_code.value if device.reject_check_code else None,
    )
    log.info("repair case %d: retest row %d -> %s", case_id, device.id, status.value)
