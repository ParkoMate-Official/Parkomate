-- 0003_repairs: repair tracking for rejected devices.
-- A rejected device can be opened as a repair case, repaired, retested, and either accepted or scrapped.

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

CREATE TRIGGER trg_repair_events_no_update BEFORE UPDATE ON repair_events
BEGIN SELECT RAISE(ABORT, 'repair_events is append-only'); END;
CREATE TRIGGER trg_repair_events_no_delete BEFORE DELETE ON repair_events
BEGIN SELECT RAISE(ABORT, 'repair_events is append-only'); END;

-- Link devices to their repair case (optional, set when a rejected device enters repair).
ALTER TABLE devices ADD COLUMN repair_case_id INTEGER REFERENCES repair_cases (id);
