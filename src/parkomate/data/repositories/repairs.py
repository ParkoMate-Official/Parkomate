"""Repair cases (one per rejected board) and their append-only event log."""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from datetime import datetime

from parkomate.core.clock import Clock
from parkomate.core.enums import RepairEventKind, RepairStatus
from parkomate.core.errors import NotFoundError, RecordStateError
from parkomate.core.models import RepairCase, RepairEventRecord
from parkomate.data.db import Database
from parkomate.data.repositories._rows import iso, last_id, ts, ts_req

_CASE_COLUMNS = "id, device_row_id, mac_address, status, opened_at, closed_at"
_EVENT_COLUMNS = (
    "id, case_id, event, session_id, operator_id, device_row_id, action, note, created_at"
)
OPEN_STATUSES = tuple(s.value for s in RepairStatus if s.is_open)


def _case(row: sqlite3.Row) -> RepairCase:
    return RepairCase(
        id=row["id"],
        device_row_id=row["device_row_id"],
        mac_address=row["mac_address"],
        status=RepairStatus(row["status"]),
        opened_at=ts_req(row["opened_at"]),
        closed_at=ts(row["closed_at"]),
    )


def _event(row: sqlite3.Row) -> RepairEventRecord:
    return RepairEventRecord(
        id=row["id"],
        case_id=row["case_id"],
        event=RepairEventKind(row["event"]),
        session_id=row["session_id"],
        operator_id=row["operator_id"],
        device_row_id=row["device_row_id"],
        action=row["action"],
        note=row["note"],
        created_at=ts_req(row["created_at"]),
    )


class RepairRepo:
    def __init__(self, db: Database, clock: Clock) -> None:
        self._db = db
        self._clock = clock

    # ------------------------------------------------------------------ cases
    def open_case(self, device_row_id: int, mac_address: str) -> RepairCase:
        with self._db.transaction() as conn:
            cursor = conn.execute(
                "INSERT INTO repair_cases (device_row_id, mac_address, status, opened_at)"
                " VALUES (?, ?, 'waiting', ?)",
                (device_row_id, mac_address, iso(self._clock.now())),
            )
            return self.require(last_id(cursor))

    def get(self, case_id: int) -> RepairCase | None:
        row = self._db.query_one(
            f"SELECT {_CASE_COLUMNS} FROM repair_cases WHERE id = ?", (case_id,)
        )
        return None if row is None else _case(row)

    def require(self, case_id: int) -> RepairCase:
        case = self.get(case_id)
        if case is None:
            raise NotFoundError(f"repair case {case_id} not found")
        return case

    def for_device(self, device_row_id: int) -> RepairCase | None:
        """The case opened by the reject of ``device_row_id``."""
        row = self._db.query_one(
            f"SELECT {_CASE_COLUMNS} FROM repair_cases WHERE device_row_id = ?",
            (device_row_id,),
        )
        return None if row is None else _case(row)

    def list_cases(
        self, *, open_only: bool | None = None, search: str = "", limit: int = 500
    ) -> list[RepairCase]:
        """Newest first. ``open_only``: True = open, False = closed, None = all. ``search``
        matches the MAC or the QR ID of any run of the board."""
        where: list[str] = []
        params: list[object] = []
        if open_only is not None:
            marks = ",".join("?" for _ in OPEN_STATUSES)
            where.append(f"c.status {'IN' if open_only else 'NOT IN'} ({marks})")
            params.extend(OPEN_STATUSES)
        text = search.strip()
        if text:
            where.append(
                "(c.mac_address LIKE ? OR EXISTS (SELECT 1 FROM devices d"
                " WHERE (d.id = c.device_row_id OR d.repair_case_id = c.id)"
                " AND d.device_id LIKE ?))"
            )
            params.extend([f"%{text}%", f"%{text}%"])
        clause = f" WHERE {' AND '.join(where)}" if where else ""
        rows = self._db.query(
            f"SELECT {', '.join('c.' + c for c in _CASE_COLUMNS.split(', '))}"
            f" FROM repair_cases c{clause} ORDER BY c.id DESC LIMIT ?",
            (*params, limit),
        )
        return [_case(row) for row in rows]

    def set_status(
        self,
        case_id: int,
        status: RepairStatus,
        *,
        expected: Sequence[RepairStatus],
        at: datetime | None = None,
    ) -> None:
        """Move the case to ``status`` - only from one of the ``expected`` states."""
        closed_at = iso(at or self._clock.now()) if not status.is_open else None
        marks = ",".join("?" for _ in expected)
        with self._db.transaction() as conn:
            cursor = conn.execute(
                f"UPDATE repair_cases SET status = ?, closed_at = ?"
                f" WHERE id = ? AND status IN ({marks})",
                (status.value, closed_at, case_id, *(s.value for s in expected)),
            )
            if cursor.rowcount != 1:
                current = self.require(case_id)
                raise RecordStateError(
                    f"repair case {case_id} is {current.status.value}, cannot become"
                    f" {status.value}",
                    context={"case_id": case_id, "status": current.status.value},
                )

    def counts(self) -> dict[RepairStatus, int]:
        totals = dict.fromkeys(RepairStatus, 0)
        for row in self._db.query("SELECT status, COUNT(*) AS n FROM repair_cases GROUP BY status"):
            totals[RepairStatus(row["status"])] = int(row["n"])
        return totals

    # ------------------------------------------------------------------ events
    def add_event(
        self,
        case_id: int,
        event: RepairEventKind,
        *,
        session_id: int | None,
        operator_id: int | None,
        device_row_id: int | None = None,
        action: str | None = None,
        note: str | None = None,
        at: datetime | None = None,
    ) -> RepairEventRecord:
        with self._db.transaction() as conn:
            cursor = conn.execute(
                "INSERT INTO repair_events (case_id, event, session_id, operator_id,"
                " device_row_id, action, note, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    case_id,
                    event.value,
                    session_id,
                    operator_id,
                    device_row_id,
                    action,
                    note,
                    iso(at or self._clock.now()),
                ),
            )
            row = conn.execute(
                f"SELECT {_EVENT_COLUMNS} FROM repair_events WHERE id = ?", (last_id(cursor),)
            ).fetchone()
        return _event(row)

    def events_for_case(self, case_id: int) -> list[RepairEventRecord]:
        rows = self._db.query(
            f"SELECT {_EVENT_COLUMNS} FROM repair_events WHERE case_id = ? ORDER BY id",
            (case_id,),
        )
        return [_event(row) for row in rows]

    def events_for_sessions(self, session_ids: Sequence[int]) -> list[RepairEventRecord]:
        if not session_ids:
            return []
        marks = ",".join("?" for _ in session_ids)
        rows = self._db.query(
            f"SELECT {_EVENT_COLUMNS} FROM repair_events WHERE session_id IN ({marks})"
            " ORDER BY session_id, id",
            tuple(session_ids),
        )
        return [_event(row) for row in rows]
