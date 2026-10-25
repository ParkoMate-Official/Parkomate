"""Operation runs: one sitting of one worker on one board for one operation.

Append-only except that an open run is closed exactly once (DB trigger). At most one open run
per board and one per session (unique partial indexes).
"""

from __future__ import annotations

import sqlite3
from datetime import datetime

from parkomate.core.clock import Clock
from parkomate.core.enums import IdentifyBy, OpCode, RunOutcome
from parkomate.core.errors import NotFoundError
from parkomate.core.models import OperationRun
from parkomate.data.db import Database
from parkomate.data.repositories._rows import iso, last_id, ts, ts_req

_COLUMNS = (
    "id, device_row_id, op_code, session_id, operator_id, station_id, identified_by, "
    "started_at, finished_at, outcome"
)


def _to_model(row: sqlite3.Row) -> OperationRun:
    return OperationRun(
        id=row["id"],
        device_row_id=row["device_row_id"],
        op_code=OpCode(row["op_code"]),
        session_id=row["session_id"],
        operator_id=row["operator_id"],
        station_id=row["station_id"],
        identified_by=IdentifyBy(row["identified_by"]),
        started_at=ts_req(row["started_at"]),
        finished_at=ts(row["finished_at"]),
        outcome=RunOutcome(row["outcome"]) if row["outcome"] else None,
    )


class RunRepo:
    def __init__(self, db: Database, clock: Clock) -> None:
        self._db = db
        self._clock = clock

    def open(
        self,
        device_row_id: int,
        op: OpCode,
        *,
        session_id: int,
        operator_id: int,
        station_id: str,
        identified_by: IdentifyBy,
    ) -> OperationRun:
        with self._db.transaction() as conn:
            cursor = conn.execute(
                "INSERT INTO operation_runs (device_row_id, op_code, session_id, operator_id,"
                " station_id, identified_by, started_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    device_row_id,
                    op.value,
                    session_id,
                    operator_id,
                    station_id,
                    identified_by.value,
                    iso(self._clock.now()),
                ),
            )
            row = conn.execute(
                f"SELECT {_COLUMNS} FROM operation_runs WHERE id = ?", (last_id(cursor),)
            ).fetchone()
        return _to_model(row)

    def close(self, run_id: int, outcome: RunOutcome, finished_at: datetime) -> OperationRun:
        with self._db.transaction() as conn:
            cursor = conn.execute(
                "UPDATE operation_runs SET finished_at = ?, outcome = ?"
                " WHERE id = ? AND finished_at IS NULL",
                (iso(finished_at), outcome.value, run_id),
            )
            if cursor.rowcount != 1:
                raise NotFoundError(f"operation run {run_id} not found or already closed")
        return self.require(run_id)

    def get(self, run_id: int) -> OperationRun | None:
        row = self._db.query_one(f"SELECT {_COLUMNS} FROM operation_runs WHERE id = ?", (run_id,))
        return None if row is None else _to_model(row)

    def require(self, run_id: int) -> OperationRun:
        run = self.get(run_id)
        if run is None:
            raise NotFoundError(f"operation run {run_id} not found")
        return run

    def open_for_session(self, session_id: int) -> OperationRun | None:
        """The run of the board on this session's bench."""
        row = self._db.query_one(
            f"SELECT {_COLUMNS} FROM operation_runs WHERE session_id = ? AND finished_at IS NULL",
            (session_id,),
        )
        return None if row is None else _to_model(row)

    def open_for_device(self, device_row_id: int) -> OperationRun | None:
        """The run of whichever bench holds the board."""
        row = self._db.query_one(
            f"SELECT {_COLUMNS} FROM operation_runs"
            " WHERE device_row_id = ? AND finished_at IS NULL",
            (device_row_id,),
        )
        return None if row is None else _to_model(row)

    def latest_for_device(self, device_row_id: int) -> OperationRun | None:
        row = self._db.query_one(
            f"SELECT {_COLUMNS} FROM operation_runs WHERE device_row_id = ?"
            " ORDER BY id DESC LIMIT 1",
            (device_row_id,),
        )
        return None if row is None else _to_model(row)

    def list_for_device(self, device_row_id: int) -> list[OperationRun]:
        rows = self._db.query(
            f"SELECT {_COLUMNS} FROM operation_runs WHERE device_row_id = ? ORDER BY id",
            (device_row_id,),
        )
        return [_to_model(row) for row in rows]

    def list_for_session(self, session_id: int) -> list[OperationRun]:
        rows = self._db.query(
            f"SELECT {_COLUMNS} FROM operation_runs WHERE session_id = ? ORDER BY id",
            (session_id,),
        )
        return [_to_model(row) for row in rows]
