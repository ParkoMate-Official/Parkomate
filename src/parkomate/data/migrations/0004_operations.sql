-- 0004_operations: boards flow through operations (multi-worker line, docs/MULTI_WORKER_PLAN.md).
-- A board is no longer owned by the session that started it: any session can continue it at
-- devices.next_op. Each sitting of one worker on one board for one operation is an
-- operation_runs row; check results and stage transitions point at the run that made them.

-- A session now leaves many boards in progress; "one board on a bench" moves to the run indexes.
DROP INDEX ux_devices_one_active;

-- The operation a board waits for. New boards start at A_PROGRAM; NULL once finished.
ALTER TABLE devices ADD COLUMN next_op TEXT DEFAULT 'A_PROGRAM'
    CHECK (next_op IN ('A_PROGRAM', 'B_TEST', 'C_CODE', 'C_CASING', 'C_BRANDING', 'D_PACK'));
UPDATE devices SET next_op = NULL WHERE status <> 'in_progress';
-- Boards in progress before this upgrade restart at the first operation of their last stage.
UPDATE devices SET next_op = CASE (
        SELECT t.to_stage FROM stage_transitions AS t
        WHERE t.device_row_id = devices.id ORDER BY t.id DESC LIMIT 1)
    WHEN 'testing' THEN 'B_TEST'
    WHEN 'labeling' THEN 'C_CODE'
    WHEN 'packaging' THEN 'D_PACK'
    ELSE 'A_PROGRAM'
END
WHERE status = 'in_progress';
CREATE INDEX ix_devices_queue ON devices (next_op, id) WHERE status = 'in_progress';

CREATE TABLE operation_runs (
    id            INTEGER PRIMARY KEY,
    device_row_id INTEGER NOT NULL REFERENCES devices (id),
    op_code       TEXT    NOT NULL
                  CHECK (op_code IN ('A_PROGRAM', 'B_TEST', 'C_CODE', 'C_CASING',
                                     'C_BRANDING', 'D_PACK')),
    session_id    INTEGER NOT NULL REFERENCES sessions (id),
    operator_id   INTEGER NOT NULL REFERENCES operators (id),
    station_id    TEXT    NOT NULL,
    identified_by TEXT    NOT NULL CHECK (identified_by IN ('new', 'mac', 'qr', 'manual')),
    started_at    TEXT    NOT NULL,
    finished_at   TEXT,
    outcome       TEXT CHECK (outcome IN ('passed', 'rejected', 'released', 'abandoned')),
    CHECK ((finished_at IS NULL) = (outcome IS NULL))
);
CREATE INDEX ix_runs_device ON operation_runs (device_row_id, id);
CREATE INDEX ix_runs_session ON operation_runs (session_id, id);
-- Nobody works on a board that is on another bench, and nobody holds two boards.
CREATE UNIQUE INDEX ux_runs_open_device ON operation_runs (device_row_id) WHERE finished_at IS NULL;
CREATE UNIQUE INDEX ux_runs_open_session ON operation_runs (session_id) WHERE finished_at IS NULL;

-- History: a run is never deleted, and the only change allowed is closing an open run once.
CREATE TRIGGER trg_runs_close_once BEFORE UPDATE ON operation_runs
WHEN OLD.finished_at IS NOT NULL
    OR NEW.id IS NOT OLD.id
    OR NEW.device_row_id IS NOT OLD.device_row_id
    OR NEW.op_code IS NOT OLD.op_code
    OR NEW.session_id IS NOT OLD.session_id
    OR NEW.operator_id IS NOT OLD.operator_id
    OR NEW.station_id IS NOT OLD.station_id
    OR NEW.identified_by IS NOT OLD.identified_by
    OR NEW.started_at IS NOT OLD.started_at
BEGIN SELECT RAISE(ABORT, 'operation_runs is append-only (an open run may be closed once)'); END;
CREATE TRIGGER trg_runs_no_delete BEFORE DELETE ON operation_runs
BEGIN SELECT RAISE(ABORT, 'operation_runs is append-only'); END;

-- Who did each check and stage move, where, and in which operation (NULL for older rows).
ALTER TABLE check_results ADD COLUMN run_id INTEGER REFERENCES operation_runs (id);
ALTER TABLE stage_transitions ADD COLUMN run_id INTEGER REFERENCES operation_runs (id);
CREATE INDEX ix_checks_run ON check_results (run_id);
