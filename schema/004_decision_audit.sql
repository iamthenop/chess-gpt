BEGIN;

-- =========================================
-- Decision Audit
--
-- Audit records capture what an actor attempted to do,
-- not only what the substrate accepted.
--
-- Context may be supplied directly as a board_id, or
-- indirectly through (game_id, ply), where ply is the
-- move number the actor intended to play.
--
-- For game_id + ply:
--   context board = replayed board at ply-1
--
-- If game_id is supplied without ply:
--   context board = current/final replayed board for that game
-- =========================================
CREATE TABLE IF NOT EXISTS decision_audit (
    id                  INTEGER PRIMARY KEY,
    created_at          TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    context_mode        TEXT NOT NULL DEFAULT 'board'
                        CHECK (context_mode IN ('board', 'game', 'hybrid')),

    game_id             INTEGER,
    ply                 INTEGER CHECK (ply IS NULL OR ply > 0),
    board_id            INTEGER,

    chosen_move_id      INTEGER,
    chosen_move_code    INTEGER CHECK (chosen_move_code IS NULL OR chosen_move_code BETWEEN 0 AND 65535),
    chosen_flags        INTEGER CHECK (chosen_flags IS NULL OR chosen_flags BETWEEN 0 AND 65535),

    accepted            INTEGER NOT NULL CHECK (accepted IN (0, 1)),
    reason              TEXT NOT NULL,
    actor               TEXT NOT NULL DEFAULT 'llm',

    require_suggested   INTEGER NOT NULL DEFAULT 1 CHECK (require_suggested IN (0, 1)),
    notes               TEXT,

    CHECK (game_id IS NOT NULL OR board_id IS NOT NULL),
    CHECK (chosen_move_id IS NOT NULL OR chosen_move_code IS NOT NULL),

    FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE CASCADE,
    FOREIGN KEY (board_id) REFERENCES boards(id) ON DELETE CASCADE,
    FOREIGN KEY (chosen_move_id) REFERENCES moves(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_decision_audit_game_created
    ON decision_audit(game_id, created_at);

CREATE INDEX IF NOT EXISTS idx_decision_audit_board_created
    ON decision_audit(board_id, created_at);

CREATE INDEX IF NOT EXISTS idx_decision_audit_actor_created
    ON decision_audit(actor, created_at);

CREATE INDEX IF NOT EXISTS idx_decision_audit_mode_created
    ON decision_audit(context_mode, created_at);

-- =========================================
-- Resolved audit context
--
-- Resolves the board the actor was looking at, using:
--   1) explicit board_id, else
--   2) replayed board for (game_id, ply-1), else
--   3) current/final replayed board for game_id
-- =========================================
CREATE VIEW IF NOT EXISTS decision_audit_context AS
SELECT
    da.id AS audit_id,
    da.created_at,
    da.context_mode,
    da.game_id,
    da.ply,
    da.board_id AS explicit_board_id,
    da.chosen_move_id,
    da.chosen_move_code,
    da.chosen_flags,
    da.accepted,
    da.reason,
    da.actor,
    da.require_suggested,
    da.notes,

    COALESCE(
        da.board_id,
        p_prev.board_id,
        gfb.final_board_id
    ) AS context_board_id,

    COALESCE(
        hex(b_explicit.board_blob),
        p_prev.board_hex,
        gfb.final_board_hex
    ) AS context_board_hex

FROM decision_audit da
LEFT JOIN boards b_explicit
       ON b_explicit.id = da.board_id
LEFT JOIN positions p_prev
       ON p_prev.game_id = da.game_id
      AND da.ply IS NOT NULL
      AND p_prev.ply = da.ply - 1
LEFT JOIN game_final_board gfb
       ON gfb.game_id = da.game_id;

-- =========================================
-- Fully resolved audit entries
--
-- If chosen_move_id is missing, attempt to resolve it from:
--   context_board_id + chosen_move_code [+ chosen_flags]
--
-- Also joins the public move views so audit consumers do not
-- need to decode packed internals by hand.
-- =========================================
CREATE VIEW IF NOT EXISTS decision_audit_resolved AS
WITH resolved AS (
    SELECT
        dac.*,
        COALESCE(
            dac.chosen_move_id,
            (
                SELECT m.id
                FROM moves m
                WHERE m.from_board_id = dac.context_board_id
                  AND m.move_code = dac.chosen_move_code
                  AND (dac.chosen_flags IS NULL OR m.flags = dac.chosen_flags)
                ORDER BY m.id
                LIMIT 1
            )
        ) AS resolved_move_id
    FROM decision_audit_context dac
)
SELECT
    r.audit_id,
    r.created_at,
    r.context_mode,
    r.game_id,
    r.ply,
    r.explicit_board_id,
    r.context_board_id,
    r.context_board_hex,

    r.chosen_move_id,
    r.chosen_move_code,
    r.chosen_flags,
    r.resolved_move_id,

    ml.move_code AS resolved_move_code,
    ml.flags AS resolved_flags,
    ml.move_uci AS resolved_move_uci,
    ml.from_board_id,
    ml.from_board_hex,
    ml.to_board_id AS resulting_board_id,
    ml.to_board_hex AS resulting_board_hex,

    ml.is_capture,
    ml.is_check,
    ml.is_mate,
    ml.is_en_passant,
    ml.is_pawn_double_push,
    ml.is_short_castle,
    ml.is_long_castle,

    COALESCE(ml.frequency, 0) AS frequency,
    COALESCE(ml.white_wins, 0) AS white_wins,
    COALESCE(ml.black_wins, 0) AS black_wins,
    COALESCE(ml.draws, 0) AS draws,
    ml.white_win_rate,
    ml.black_win_rate,
    ml.draw_rate,

    CASE WHEN ml.move_id IS NULL THEN 0 ELSE 1 END AS resolved_to_known_move,
    CASE WHEN bms.move_id IS NULL THEN 0 ELSE 1 END AS in_suggestions,

    r.accepted,
    CASE
        WHEN r.require_suggested = 0
             THEN CASE WHEN ml.move_id IS NOT NULL THEN 1 ELSE 0 END
        ELSE CASE WHEN bms.move_id IS NOT NULL THEN 1 ELSE 0 END
    END AS satisfies_policy,
    r.reason,
    r.actor,
    r.require_suggested,
    r.notes

FROM resolved r
LEFT JOIN move_lookup ml
       ON ml.move_id = r.resolved_move_id
LEFT JOIN board_move_suggestions bms
       ON bms.board_id = r.context_board_id
      AND bms.move_id = r.resolved_move_id;

COMMIT;
