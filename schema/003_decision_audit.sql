BEGIN;

CREATE TABLE IF NOT EXISTS decision_audit (
    id                  INTEGER PRIMARY KEY,
    created_at          TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    position_id         INTEGER NOT NULL,
    chosen_move_uci     TEXT NOT NULL,
    chosen_move_san     TEXT,
    accepted            INTEGER NOT NULL CHECK (accepted IN (0, 1)),
    reason              TEXT NOT NULL,
    actor               TEXT NOT NULL DEFAULT 'llm',
    require_suggested   INTEGER NOT NULL DEFAULT 1 CHECK (require_suggested IN (0, 1)),
    in_suggestions      INTEGER CHECK (in_suggestions IS NULL OR in_suggestions IN (0, 1)),
    resulting_position_id INTEGER,
    FOREIGN KEY (position_id) REFERENCES positions(id) ON DELETE CASCADE,
    FOREIGN KEY (resulting_position_id) REFERENCES positions(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_decision_audit_position
    ON decision_audit(position_id, created_at);

CREATE INDEX IF NOT EXISTS idx_decision_audit_actor
    ON decision_audit(actor, created_at);

COMMIT;
