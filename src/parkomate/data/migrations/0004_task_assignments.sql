-- 0004_task_assignments: operator stage assignments and work queue for multi-user flow.

-- Each operator can be assigned specific stages. NULL means all stages (backward compatible).
ALTER TABLE operators ADD COLUMN assigned_stages TEXT;

-- Work queue: boards waiting to be picked up at a specific stage by the next operator.
CREATE TABLE work_queue (
    id              INTEGER PRIMARY KEY,
    device_row_id   INTEGER NOT NULL REFERENCES devices(id),
    mac_address     TEXT    NOT NULL,
    device_id       TEXT,
    current_stage   TEXT    NOT NULL CHECK (current_stage IN ('programming', 'testing', 'labeling', 'packaging')),
    ready_at        TEXT    NOT NULL,
    picked_by       INTEGER REFERENCES operators(id),
    picked_at       TEXT,
    completed_at    TEXT,
    source_session_id INTEGER REFERENCES sessions(id),
    target_session_id INTEGER REFERENCES sessions(id),
    status          TEXT    NOT NULL DEFAULT 'waiting'
                    CHECK (status IN ('waiting', 'in_progress', 'done', 'cancelled'))
);
CREATE INDEX ix_work_queue_stage ON work_queue (current_stage, status);
CREATE INDEX ix_work_queue_device ON work_queue (device_row_id);
CREATE INDEX ix_work_queue_picked ON work_queue (picked_by) WHERE status = 'in_progress';
