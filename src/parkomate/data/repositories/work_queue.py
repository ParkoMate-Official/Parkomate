"""Work queue: boards waiting between operators at different stages."""

from __future__ import annotations

import sqlite3

from parkomate.core.clock import Clock
from parkomate.core.enums import Stage
from parkomate.core.errors import NotFoundError
from parkomate.core.models import WorkQueueItem
from parkomate.data.db import Database
from parkomate.data.repositories._rows import iso, last_id, ts, ts_req

_COLUMNS = (
    "id, device_row_id, mac_address, device_id, current_stage, ready_at, "
    "picked_by, picked_at, completed_at, source_session_id, target_session_id, status"
)


def _to_model(row: sqlite3.Row) -> WorkQueueItem:
    return WorkQueueItem(
        id=row["id"],
        device_row_id=row["device_row_id"],
        mac_address=row["mac_address"],
        device_id=row["device_id"],
        current_stage=Stage(row["current_stage"]),
        ready_at=ts_req(row["ready_at"]),
        picked_by=row["picked_by"],
        picked_at=ts(row["picked_at"]),
        completed_at=ts(row["completed_at"]),
        source_session_id=row["source_session_id"],
        target_session_id=row["target_session_id"],
        status=row["status"],
    )


class WorkQueueRepo:
    def __init__(self, db: Database, clock: Clock) -> None:
        self._db = db
        self._clock = clock

    def enqueue(
        self,
        device_row_id: int,
        mac_address: str,
        device_id: str | None,
        stage: str,
        source_session_id: int,
    ) -> int:
        """Add a board to the queue for the given stage. Returns the queue item id."""
        with self._db.transaction() as conn:
            cursor = conn.execute(
                "INSERT INTO work_queue "
                "(device_row_id, mac_address, device_id, current_stage, ready_at, "
                " source_session_id, status) "
                "VALUES (?, ?, ?, ?, ?, ?, 'waiting')",
                (
                    device_row_id,
                    mac_address,
                    device_id,
                    stage,
                    iso(self._clock.now()),
                    source_session_id,
                ),
            )
            return last_id(cursor)

    def list_waiting(self, stage: str | None = None) -> list[WorkQueueItem]:
        """List all waiting items, optionally filtered by stage."""
        if stage is not None:
            rows = self._db.query(
                f"SELECT {_COLUMNS} FROM work_queue "
                "WHERE status = 'waiting' AND current_stage = ? ORDER BY ready_at",
                (stage,),
            )
        else:
            rows = self._db.query(
                f"SELECT {_COLUMNS} FROM work_queue "
                "WHERE status = 'waiting' ORDER BY ready_at",
            )
        return [_to_model(row) for row in rows]

    def list_for_operator(self, stages: tuple[str, ...]) -> list[WorkQueueItem]:
        """List waiting items for stages the operator handles."""
        if not stages:
            return []
        placeholders = ", ".join("?" for _ in stages)
        rows = self._db.query(
            f"SELECT {_COLUMNS} FROM work_queue "
            f"WHERE status = 'waiting' AND current_stage IN ({placeholders}) "
            "ORDER BY ready_at",
            tuple(stages),
        )
        return [_to_model(row) for row in rows]

    def get(self, queue_id: int) -> WorkQueueItem:
        """Get a single queue item by id."""
        row = self._db.query_one(
            f"SELECT {_COLUMNS} FROM work_queue WHERE id = ?", (queue_id,)
        )
        if row is None:
            raise NotFoundError(f"work queue item {queue_id} not found")
        return _to_model(row)

    def pick(self, queue_id: int, operator_id: int, session_id: int) -> WorkQueueItem:
        """Mark an item as picked by an operator. Returns updated item."""
        with self._db.transaction() as conn:
            conn.execute(
                "UPDATE work_queue SET picked_by = ?, picked_at = ?, "
                "target_session_id = ?, status = 'in_progress' "
                "WHERE id = ? AND status = 'waiting'",
                (operator_id, iso(self._clock.now()), session_id, queue_id),
            )
        return self.get(queue_id)

    def complete(self, queue_id: int) -> None:
        """Mark an item as done."""
        with self._db.transaction() as conn:
            conn.execute(
                "UPDATE work_queue SET completed_at = ?, status = 'done' WHERE id = ?",
                (iso(self._clock.now()), queue_id),
            )

    def cancel(self, queue_id: int) -> None:
        """Cancel a queue item."""
        with self._db.transaction() as conn:
            conn.execute(
                "UPDATE work_queue SET status = 'cancelled' WHERE id = ?",
                (queue_id,),
            )

    def count_waiting(self, stage: str | None = None) -> int:
        """Count waiting items."""
        if stage is not None:
            return int(
                self._db.scalar(
                    "SELECT COUNT(*) FROM work_queue "
                    "WHERE status = 'waiting' AND current_stage = ?",
                    (stage,),
                )
            )
        return int(
            self._db.scalar(
                "SELECT COUNT(*) FROM work_queue WHERE status = 'waiting'"
            )
        )

    def count_waiting_by_stage(self) -> dict[str, int]:
        """Count waiting items grouped by stage."""
        rows = self._db.query(
            "SELECT current_stage, COUNT(*) as cnt FROM work_queue "
            "WHERE status = 'waiting' GROUP BY current_stage"
        )
        return {row["current_stage"]: row["cnt"] for row in rows}
