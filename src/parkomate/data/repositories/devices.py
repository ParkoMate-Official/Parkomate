"""Devices (one row per physical board that entered the line)."""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from parkomate.core.clock import Clock
from parkomate.core.enums import CheckCode, DeviceStatus, IdEntryMethod, OpCode, Stage
from parkomate.core.errors import NotFoundError
from parkomate.core.models import Device
from parkomate.data.db import Database
from parkomate.data.repositories._rows import dumps, iso, last_id, loads_dict, ts, ts_req

_COLUMNS = (
    "id, session_id, device_id, mac_address, firmware_version, started_at, finished_at, status, "
    "reject_stage, reject_check_code, reject_reason, reject_reason_key, reject_reason_params, "
    "programming_attempts, id_entry_method, next_op"
)
_WAITING = (
    "status = 'in_progress' AND NOT EXISTS (SELECT 1 FROM operation_runs r"
    " WHERE r.device_row_id = devices.id AND r.finished_at IS NULL)"
)
"""In progress and on nobody's bench: waiting in a tray for ``next_op``."""


def _to_model(row: sqlite3.Row) -> Device:
    return Device(
        id=row["id"],
        session_id=row["session_id"],
        device_id=row["device_id"],
        mac_address=row["mac_address"],
        firmware_version=row["firmware_version"],
        started_at=ts_req(row["started_at"]),
        finished_at=ts(row["finished_at"]),
        status=DeviceStatus(row["status"]),
        reject_stage=Stage(row["reject_stage"]) if row["reject_stage"] else None,
        reject_check_code=CheckCode(row["reject_check_code"]) if row["reject_check_code"] else None,
        reject_reason=row["reject_reason"],
        reject_reason_key=row["reject_reason_key"],
        reject_reason_params=loads_dict(row["reject_reason_params"]),
        programming_attempts=row["programming_attempts"],
        id_entry_method=IdEntryMethod(row["id_entry_method"]) if row["id_entry_method"] else None,
        next_op=OpCode(row["next_op"]) if row["next_op"] else None,
    )


class DeviceRepo:
    def __init__(self, db: Database, clock: Clock) -> None:
        self._db = db
        self._clock = clock

    def create(
        self, session_id: int, mac_address: str, firmware_version: str | None = None
    ) -> Device:
        with self._db.transaction() as conn:
            cursor = conn.execute(
                "INSERT INTO devices (session_id, mac_address, firmware_version, started_at)"
                " VALUES (?, ?, ?, ?)",
                (session_id, mac_address, firmware_version, iso(self._clock.now())),
            )
            return self.require(last_id(cursor))

    def get(self, device_row_id: int) -> Device | None:
        row = self._db.query_one(f"SELECT {_COLUMNS} FROM devices WHERE id = ?", (device_row_id,))
        return None if row is None else _to_model(row)

    def require(self, device_row_id: int) -> Device:
        device = self.get(device_row_id)
        if device is None:
            raise NotFoundError(f"device row {device_row_id} not found")
        return device

    def list_for_session(self, session_id: int) -> list[Device]:
        rows = self._db.query(
            f"SELECT {_COLUMNS} FROM devices WHERE session_id = ? ORDER BY id",
            (session_id,),
        )
        return [_to_model(row) for row in rows]

    def list_for_sessions(self, session_ids: Sequence[int]) -> list[Device]:
        if not session_ids:
            return []
        marks = ",".join("?" for _ in session_ids)
        rows = self._db.query(
            f"SELECT {_COLUMNS} FROM devices WHERE session_id IN ({marks}) ORDER BY session_id, id",
            tuple(session_ids),
        )
        return [_to_model(row) for row in rows]

    def active_for_session(self, session_id: int) -> Device | None:
        row = self._db.query_one(
            f"SELECT {_COLUMNS} FROM devices WHERE session_id = ? AND status = 'in_progress'",
            (session_id,),
        )
        return None if row is None else _to_model(row)

    def search(self, text: str, limit: int = 100) -> list[Device]:
        """Devices whose QR ID or MAC contains ``text`` (case-insensitive), newest first."""
        pattern = f"%{text.strip()}%"
        rows = self._db.query(
            f"SELECT {_COLUMNS} FROM devices"
            " WHERE device_id LIKE ? OR mac_address LIKE ? ORDER BY id DESC LIMIT ?",
            (pattern, pattern, limit),
        )
        return [_to_model(row) for row in rows]

    def set_device_id(self, device_row_id: int, device_id: str, method: IdEntryMethod) -> None:
        self._update(device_row_id, "device_id = ?, id_entry_method = ?", (device_id, method.value))

    def set_firmware_version(self, device_row_id: int, version: str) -> None:
        self._update(device_row_id, "firmware_version = ?", (version,))

    def increment_programming_attempts(self, device_row_id: int) -> None:
        self._update(device_row_id, "programming_attempts = programming_attempts + 1", ())

    def set_next_op(self, device_row_id: int, op: OpCode) -> None:
        self._update(device_row_id, "next_op = ?", (op.value,), only_in_progress=True)

    def find(self, *, mac: str | None = None, device_id: str | None = None) -> Device | None:
        """The board with this MAC (or QR ID): its in-progress row, else its newest row."""
        column, value = ("mac_address", mac) if mac is not None else ("device_id", device_id)
        row = self._db.query_one(
            f"SELECT {_COLUMNS} FROM devices WHERE {column} = ?"
            " ORDER BY status = 'in_progress' DESC, id DESC LIMIT 1",
            (value,),
        )
        return None if row is None else _to_model(row)

    def queue(self, op: OpCode) -> list[Device]:
        """Boards waiting for ``op``, oldest first."""
        rows = self._db.query(
            f"SELECT {_COLUMNS} FROM devices WHERE next_op = ? AND {_WAITING} ORDER BY id",
            (op.value,),
        )
        return [_to_model(row) for row in rows]

    def queue_counts(self) -> dict[OpCode, int]:
        """Number of boards waiting for each operation."""
        counts = dict.fromkeys(OpCode, 0)
        for row in self._db.query(
            f"SELECT next_op, COUNT(*) AS n FROM devices WHERE {_WAITING} GROUP BY next_op"
        ):
            counts[OpCode(row["next_op"])] = int(row["n"])
        return counts

    def finish(self, device_row_id: int, status: DeviceStatus, finished_at: datetime) -> None:
        """Set a terminal non-reject status (complete / abandoned)."""
        if status not in (DeviceStatus.COMPLETE, DeviceStatus.ABANDONED):
            raise ValueError(f"use reject() for status {status}")
        self._update(
            device_row_id,
            "status = ?, finished_at = ?, next_op = NULL",
            (status.value, iso(finished_at)),
            only_in_progress=True,
        )

    def reject(
        self,
        device_row_id: int,
        *,
        stage: Stage,
        check_code: CheckCode,
        reason: str,
        reason_key: str,
        reason_params: dict[str, Any],
        finished_at: datetime,
    ) -> None:
        self._update(
            device_row_id,
            "status = 'rejected', finished_at = ?, reject_stage = ?, reject_check_code = ?,"
            " reject_reason = ?, reject_reason_key = ?, reject_reason_params = ?, next_op = NULL",
            (
                iso(finished_at),
                stage.value,
                check_code.value,
                reason,
                reason_key,
                dumps(reason_params),
            ),
            only_in_progress=True,
        )

    def _update(
        self,
        device_row_id: int,
        assignments: str,
        params: tuple[object, ...],
        *,
        only_in_progress: bool = False,
    ) -> None:
        guard = " AND status = 'in_progress'" if only_in_progress else ""
        with self._db.transaction() as conn:
            cursor = conn.execute(
                f"UPDATE devices SET {assignments} WHERE id = ?{guard}",
                (*params, device_row_id),
            )
            if cursor.rowcount != 1:
                raise NotFoundError(f"device row {device_row_id} not found or already finished")
