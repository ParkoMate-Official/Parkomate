"""Crash recovery, run once at start-up before anybody logs in.

Only one station process runs per PC (the UI enforces a single instance), so any session
still open at start-up belongs to a run that crashed or lost power. For each one:

* a board still on its bench is released (its run closed at the last recorded activity): it
  waits for the same operation again, for any session to continue;
* the session is closed with ``end_reason = 'crash_recovered'``;
* an audit entry is written.

The caller then queues the session report for e-mail (see ``parkomate.mail.reporting``).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from parkomate.core.enums import RunOutcome, SessionEndReason
from parkomate.data import Repositories

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RecoveryResult:
    session_ids: list[int] = field(default_factory=list)
    released_device_ids: list[int] = field(default_factory=list)

    @property
    def recovered(self) -> bool:
        return bool(self.session_ids)


def recover_unclosed_sessions(repos: Repositories) -> RecoveryResult:
    sessions: list[int] = []
    devices: list[int] = []
    for session in repos.sessions.open_sessions():
        ended_at = repos.sessions.last_activity(session.id) or repos.clock.now()
        released: list[int] = []
        with repos.db.transaction():
            run = repos.runs.open_for_session(session.id)
            if run is not None:
                repos.runs.close(run.id, RunOutcome.RELEASED, ended_at)
                released.append(run.device_row_id)
            repos.sessions.close(session.id, SessionEndReason.CRASH_RECOVERED, ended_at)
            repos.audit.record(
                None,
                "session.crash_recovered",
                {"session_id": session.id, "released_devices": released},
            )
        log.warning(
            "recovered unclosed session %d (released devices: %s)", session.id, released or "none"
        )
        sessions.append(session.id)
        devices.extend(released)
    return RecoveryResult(sessions, devices)
