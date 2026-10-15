-- 0003_repairs: faulty boards - repair, test again, then accept or scrap.
--
-- Every rejected board opens one repair case. A retest runs the board through the whole line
-- again as a NEW devices row that points to its case (devices.repair_case_id).
--
-- Case status:
--   waiting    rejected (or failed its retest) - needs repair
--   repaired   at least one repair written - ready for the retest
--   retesting  the board is on the line again (its retest device row is in progress)
--   passed     the retest completed every stage - waiting for Accept
--   accepted   closed: good board
--   scrapped   closed: thrown away

CREATE TABLE repair_cases (
    id            INTEGER PRIMARY KEY,
    device_row_id INTEGER NOT NULL UNIQUE REFERENCES devices (id),
    mac_address   TEXT    NOT NULL,
    status        TEXT    NOT NULL DEFAULT 'waiting'
                  CHECK (status IN ('waiting', 'repaired', 'retesting', 'passed',
                                    'accepted', 'scrapped')),
    opened_at     TEXT    NOT NULL,
    closed_at     TEXT,
    CHECK ((status IN ('accepted', 'scrapped')) = (closed_at IS NOT NULL))
);
CREATE INDEX ix_repair_cases_status ON repair_cases (status);
CREATE INDEX ix_repair_cases_mac ON repair_cases (mac_address);

-- What happened to a case, step by step (append-only). session_id / operator_id say who did
-- it, so each person's repair work is in their own session report.
CREATE TABLE repair_events (
    id            INTEGER PRIMARY KEY,
    case_id       INTEGER NOT NULL REFERENCES repair_cases (id),
    event         TEXT    NOT NULL
                  CHECK (event IN ('opened', 'repaired', 'retest_started', 'retest_passed',
                                   'retest_failed', 'retest_cancelled', 'accepted', 'scrapped')),
    session_id    INTEGER REFERENCES sessions (id),
    operator_id   INTEGER REFERENCES operators (id),
    device_row_id INTEGER REFERENCES devices (id),
    action        TEXT,
    note          TEXT,
    created_at    TEXT    NOT NULL
);
CREATE INDEX ix_repair_events_case ON repair_events (case_id, id);
CREATE INDEX ix_repair_events_session ON repair_events (session_id, id);

CREATE TRIGGER trg_repair_events_no_update BEFORE UPDATE ON repair_events
BEGIN SELECT RAISE(ABORT, 'repair_events is append-only'); END;
CREATE TRIGGER trg_repair_events_no_delete BEFORE DELETE ON repair_events
BEGIN SELECT RAISE(ABORT, 'repair_events is append-only'); END;

-- A retest device row belongs to its case.
ALTER TABLE devices ADD COLUMN repair_case_id INTEGER REFERENCES repair_cases (id);
CREATE INDEX ix_devices_repair_case ON devices (repair_case_id);

-- Boards rejected before this version get their case too.
INSERT INTO repair_cases (device_row_id, mac_address, status, opened_at)
SELECT id, mac_address, 'waiting', finished_at FROM devices WHERE status = 'rejected' ORDER BY id;
INSERT INTO repair_events (case_id, event, session_id, operator_id, device_row_id, created_at)
SELECT c.id, 'opened', d.session_id, s.operator_id, d.id, c.opened_at
FROM repair_cases c
JOIN devices d ON d.id = c.device_row_id
JOIN sessions s ON s.id = d.session_id
ORDER BY c.id;
