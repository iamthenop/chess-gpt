
-- =========================================
-- Writable interface layer
--
-- Public writes go through views and triggers.
-- Core tables remain compact and event-driven.
-- =========================================

-- =========================================
-- Boards
-- Insert-only by value. Boards are immutable once referenced.
-- =========================================
CREATE VIEW IF NOT EXISTS boards_write AS
SELECT
    b.id AS board_id,
    hex(b.board_blob) AS board_hex
FROM boards b;

CREATE TRIGGER IF NOT EXISTS boards_write_insert
INSTEAD OF INSERT ON boards_write
BEGIN
    SELECT CASE
        WHEN NEW.board_hex IS NULL OR length(NEW.board_hex) <> 64
            THEN RAISE(ABORT, 'board_hex must be 64 hex characters')
    END;

    SELECT CASE
        WHEN NEW.board_id IS NOT NULL
         AND EXISTS (
            SELECT 1
            FROM boards b
            WHERE b.id = NEW.board_id
              AND hex(b.board_blob) <> upper(NEW.board_hex)
         )
            THEN RAISE(ABORT, 'board_id already exists with different board_hex')
    END;

    INSERT OR IGNORE INTO boards (id, board_blob)
    SELECT NEW.board_id, unhex(NEW.board_hex)
    WHERE NEW.board_id IS NOT NULL;

    INSERT OR IGNORE INTO boards (board_blob)
    SELECT unhex(NEW.board_hex)
    WHERE NEW.board_id IS NULL;
END;

CREATE TRIGGER IF NOT EXISTS boards_write_update
INSTEAD OF UPDATE ON boards_write
BEGIN
    SELECT RAISE(ABORT, 'boards are immutable; insert a new board instead');
END;

-- =========================================
-- Moves
-- Insert-only aggregated board-to-board transitions.
-- from_board must already exist.
-- to_board may be supplied by id or hex; by hex it will be inserted if missing.
-- =========================================
CREATE VIEW IF NOT EXISTS moves_write AS
SELECT
    ml.move_id,
    ml.from_board_id,
    ml.from_board_hex,
    ml.to_board_id,
    ml.to_board_hex,
    ml.move_code,
    ml.flags,
    ml.move_uci,
    ml.is_capture,
    ml.is_check,
    ml.is_mate,
    ml.is_en_passant,
    ml.is_pawn_double_push,
    ml.is_short_castle,
    ml.is_long_castle,
    ml.is_new_game_marker
FROM move_lookup ml;

CREATE TRIGGER IF NOT EXISTS moves_write_insert
INSTEAD OF INSERT ON moves_write
BEGIN
    SELECT CASE
        WHEN NEW.move_code IS NULL OR NEW.move_code < 0 OR NEW.move_code > 65535
            THEN RAISE(ABORT, 'move_code must be between 0 and 65535')
        WHEN NEW.flags IS NULL OR NEW.flags < 0 OR NEW.flags > 65535
            THEN RAISE(ABORT, 'flags must be between 0 and 65535')
    END;

    -- Seed / resolve to_board by hex if needed.
    INSERT OR IGNORE INTO boards (board_blob)
    SELECT unhex(NEW.to_board_hex)
    WHERE NEW.to_board_id IS NULL
      AND NEW.to_board_hex IS NOT NULL;

    -- from_board must already exist.
    SELECT CASE
        WHEN COALESCE(
            NEW.from_board_id,
            (SELECT b.id FROM boards b WHERE hex(b.board_blob) = upper(NEW.from_board_hex))
        ) IS NULL
            THEN RAISE(ABORT, 'from_board does not exist')
    END;

    -- to_board must resolve either by id or by hex.
    SELECT CASE
        WHEN COALESCE(
            NEW.to_board_id,
            (SELECT b.id FROM boards b WHERE hex(b.board_blob) = upper(NEW.to_board_hex))
        ) IS NULL
            THEN RAISE(ABORT, 'to_board does not exist and could not be created')
    END;

    INSERT OR IGNORE INTO moves (
        id,
        from_board_id,
        to_board_id,
        move_code,
        flags
    )
    VALUES (
        NEW.move_id,
        COALESCE(
            NEW.from_board_id,
            (SELECT b.id FROM boards b WHERE hex(b.board_blob) = upper(NEW.from_board_hex))
        ),
        COALESCE(
            NEW.to_board_id,
            (SELECT b.id FROM boards b WHERE hex(b.board_blob) = upper(NEW.to_board_hex))
        ),
        NEW.move_code,
        NEW.flags
    );

    SELECT CASE
        WHEN NEW.move_id IS NOT NULL
         AND EXISTS (
            SELECT 1
            FROM moves m
            WHERE m.id = NEW.move_id
              AND (
                  m.from_board_id <> COALESCE(
                      NEW.from_board_id,
                      (SELECT b.id FROM boards b WHERE hex(b.board_blob) = upper(NEW.from_board_hex))
                  )
                  OR m.to_board_id <> COALESCE(
                      NEW.to_board_id,
                      (SELECT b.id FROM boards b WHERE hex(b.board_blob) = upper(NEW.to_board_hex))
                  )
                  OR m.move_code <> NEW.move_code
                  OR m.flags <> NEW.flags
              )
         )
            THEN RAISE(ABORT, 'move_id already exists with different values')
    END;
END;

CREATE TRIGGER IF NOT EXISTS moves_write_update
INSTEAD OF UPDATE ON moves_write
BEGIN
    SELECT RAISE(ABORT, 'moves are immutable; insert a new move instead');
END;

-- =========================================
-- Games
-- Writable by player names and decoded labels.
-- =========================================
CREATE VIEW IF NOT EXISTS games_write AS
SELECT
    gl.game_id,
    gl.white_player,
    gl.black_player,
    gl.start_board_id,
    gl.start_board_hex,
    gl.result,
    gl.termination_reason,
    gl.site,
    gl.event,
    gl.round,
    gl.game_date,
    gl.time_control,
    gl.eco,
    gl.opening,
    gl.variation,
    gl.pgn_source
FROM game_labels gl;

CREATE TRIGGER IF NOT EXISTS games_write_insert
INSTEAD OF INSERT ON games_write
BEGIN
    SELECT CASE
        WHEN NEW.white_player IS NULL OR trim(NEW.white_player) = ''
            THEN RAISE(ABORT, 'white_player is required')
        WHEN NEW.black_player IS NULL OR trim(NEW.black_player) = ''
            THEN RAISE(ABORT, 'black_player is required')
    END;

    INSERT OR IGNORE INTO players (name) VALUES (trim(NEW.white_player));
    INSERT OR IGNORE INTO players (name) VALUES (trim(NEW.black_player));

    INSERT OR IGNORE INTO boards (board_blob)
    SELECT unhex(NEW.start_board_hex)
    WHERE NEW.start_board_id IS NULL
      AND NEW.start_board_hex IS NOT NULL;

    SELECT CASE
        WHEN COALESCE(
            NEW.start_board_id,
            (SELECT b.id FROM boards b WHERE hex(b.board_blob) = upper(NEW.start_board_hex))
        ) IS NULL
            THEN RAISE(ABORT, 'start board does not exist and could not be resolved')
    END;

    INSERT INTO games (
        id,
        white_player_id,
        black_player_id,
        start_board_id,
        result_code,
        termination_code,
        site,
        event,
        round,
        game_date,
        time_control,
        eco,
        opening,
        variation,
        pgn_source
    )
    VALUES (
        NEW.game_id,
        (SELECT p.id FROM players p WHERE p.name = trim(NEW.white_player)),
        (SELECT p.id FROM players p WHERE p.name = trim(NEW.black_player)),
        COALESCE(
            NEW.start_board_id,
            (SELECT b.id FROM boards b WHERE hex(b.board_blob) = upper(NEW.start_board_hex))
        ),
        CASE COALESCE(NEW.result, '*')
            WHEN '*' THEN 0
            WHEN '1-0' THEN 1
            WHEN '0-1' THEN 2
            WHEN '1/2-1/2' THEN 3
            ELSE RAISE(ABORT, 'invalid result')
        END,
        CASE COALESCE(NEW.termination_reason, 'unspecified')
            WHEN 'unspecified' THEN 0
            WHEN 'checkmate' THEN 1
            WHEN 'stalemate' THEN 2
            WHEN 'insufficient_material' THEN 3
            WHEN 'resignation' THEN 4
            WHEN 'draw_agreement' THEN 5
            WHEN 'repetition' THEN 6
            WHEN 'move_limit' THEN 7
            WHEN 'time_limit' THEN 8
            WHEN 'abandonment' THEN 9
            ELSE RAISE(ABORT, 'invalid termination_reason')
        END,
        NEW.site,
        NEW.event,
        NEW.round,
        NEW.game_date,
        NEW.time_control,
        NEW.eco,
        NEW.opening,
        NEW.variation,
        NEW.pgn_source
    );
END;

CREATE TRIGGER IF NOT EXISTS games_write_update
INSTEAD OF UPDATE ON games_write
BEGIN
    SELECT CASE
        WHEN NEW.game_id <> OLD.game_id
            THEN RAISE(ABORT, 'game_id is immutable')
        WHEN NEW.white_player IS NULL OR trim(NEW.white_player) = ''
            THEN RAISE(ABORT, 'white_player is required')
        WHEN NEW.black_player IS NULL OR trim(NEW.black_player) = ''
            THEN RAISE(ABORT, 'black_player is required')
    END;

    INSERT OR IGNORE INTO players (name) VALUES (trim(NEW.white_player));
    INSERT OR IGNORE INTO players (name) VALUES (trim(NEW.black_player));

    INSERT OR IGNORE INTO boards (board_blob)
    SELECT unhex(NEW.start_board_hex)
    WHERE NEW.start_board_id IS NULL
      AND NEW.start_board_hex IS NOT NULL;

    SELECT CASE
        WHEN COALESCE(
            NEW.start_board_id,
            (SELECT b.id FROM boards b WHERE hex(b.board_blob) = upper(NEW.start_board_hex))
        ) IS NULL
            THEN RAISE(ABORT, 'start board does not exist and could not be resolved')
    END;

    UPDATE games
    SET
        white_player_id = (SELECT p.id FROM players p WHERE p.name = trim(NEW.white_player)),
        black_player_id = (SELECT p.id FROM players p WHERE p.name = trim(NEW.black_player)),
        start_board_id = COALESCE(
            NEW.start_board_id,
            (SELECT b.id FROM boards b WHERE hex(b.board_blob) = upper(NEW.start_board_hex))
        ),
        result_code = CASE COALESCE(NEW.result, '*')
            WHEN '*' THEN 0
            WHEN '1-0' THEN 1
            WHEN '0-1' THEN 2
            WHEN '1/2-1/2' THEN 3
            ELSE RAISE(ABORT, 'invalid result')
        END,
        termination_code = CASE COALESCE(NEW.termination_reason, 'unspecified')
            WHEN 'unspecified' THEN 0
            WHEN 'checkmate' THEN 1
            WHEN 'stalemate' THEN 2
            WHEN 'insufficient_material' THEN 3
            WHEN 'resignation' THEN 4
            WHEN 'draw_agreement' THEN 5
            WHEN 'repetition' THEN 6
            WHEN 'move_limit' THEN 7
            WHEN 'time_limit' THEN 8
            WHEN 'abandonment' THEN 9
            ELSE RAISE(ABORT, 'invalid termination_reason')
        END,
        site = NEW.site,
        event = NEW.event,
        round = NEW.round,
        game_date = NEW.game_date,
        time_control = NEW.time_control,
        eco = NEW.eco,
        opening = NEW.opening,
        variation = NEW.variation,
        pgn_source = NEW.pgn_source
    WHERE id = OLD.game_id;
END;

-- =========================================
-- Game move stream
-- Ordered event stream by game / ply.
-- Accepts either move_id or natural move fields.
-- Enforces continuity against start_board and adjacent plies.
-- =========================================
CREATE VIEW IF NOT EXISTS game_moves_write AS
SELECT
    gm.game_id,
    gm.ply,
    ml.move_id,
    ml.from_board_id,
    ml.from_board_hex,
    ml.to_board_id,
    ml.to_board_hex,
    ml.move_code,
    ml.flags,
    ml.move_uci
FROM game_moves gm
JOIN move_lookup ml ON ml.move_id = gm.move_id;

CREATE TRIGGER IF NOT EXISTS game_moves_write_insert
INSTEAD OF INSERT ON game_moves_write
BEGIN
    SELECT CASE
        WHEN NOT EXISTS (SELECT 1 FROM games g WHERE g.id = NEW.game_id)
            THEN RAISE(ABORT, 'game_id does not exist')
        WHEN NEW.ply IS NULL OR NEW.ply <= 0
            THEN RAISE(ABORT, 'ply must be > 0')
        WHEN NEW.move_id IS NULL
         AND (NEW.move_code IS NULL OR NEW.flags IS NULL)
            THEN RAISE(ABORT, 'either move_id or move_code+flags must be provided')
    END;

    -- If natural move fields are supplied, resolve/create the move first.
    INSERT OR IGNORE INTO boards (board_blob)
    SELECT unhex(NEW.to_board_hex)
    WHERE NEW.move_id IS NULL
      AND NEW.to_board_id IS NULL
      AND NEW.to_board_hex IS NOT NULL;

    SELECT CASE
        WHEN NEW.move_id IS NULL
         AND COALESCE(
            NEW.from_board_id,
            (SELECT b.id FROM boards b WHERE hex(b.board_blob) = upper(NEW.from_board_hex))
         ) IS NULL
            THEN RAISE(ABORT, 'from_board does not exist')
        WHEN NEW.move_id IS NULL
         AND COALESCE(
            NEW.to_board_id,
            (SELECT b.id FROM boards b WHERE hex(b.board_blob) = upper(NEW.to_board_hex))
         ) IS NULL
            THEN RAISE(ABORT, 'to_board does not exist and could not be created')
    END;

    INSERT OR IGNORE INTO moves (
        from_board_id,
        to_board_id,
        move_code,
        flags
    )
    SELECT
        COALESCE(
            NEW.from_board_id,
            (SELECT b.id FROM boards b WHERE hex(b.board_blob) = upper(NEW.from_board_hex))
        ),
        COALESCE(
            NEW.to_board_id,
            (SELECT b.id FROM boards b WHERE hex(b.board_blob) = upper(NEW.to_board_hex))
        ),
        NEW.move_code,
        NEW.flags
    WHERE NEW.move_id IS NULL;

    -- Continuity against game start or adjacent plies.
    SELECT CASE
        WHEN NEW.ply = 1
         AND (
            SELECT m.from_board_id
            FROM moves m
            WHERE m.id = COALESCE(
                NEW.move_id,
                (SELECT m2.id
                 FROM moves m2
                 WHERE m2.from_board_id = COALESCE(
                           NEW.from_board_id,
                           (SELECT b.id FROM boards b WHERE hex(b.board_blob) = upper(NEW.from_board_hex))
                       )
                   AND m2.to_board_id = COALESCE(
                           NEW.to_board_id,
                           (SELECT b.id FROM boards b WHERE hex(b.board_blob) = upper(NEW.to_board_hex))
                       )
                   AND m2.move_code = NEW.move_code
                   AND m2.flags = NEW.flags)
            )
         ) <> (SELECT g.start_board_id FROM games g WHERE g.id = NEW.game_id)
            THEN RAISE(ABORT, 'first ply must begin from games.start_board_id')
        WHEN NEW.ply > 1
         AND NOT EXISTS (
            SELECT 1
            FROM game_moves gm_prev
            JOIN moves m_prev ON m_prev.id = gm_prev.move_id
            JOIN moves m_cur ON m_cur.id = COALESCE(
                NEW.move_id,
                (SELECT m2.id
                 FROM moves m2
                 WHERE m2.from_board_id = COALESCE(
                           NEW.from_board_id,
                           (SELECT b.id FROM boards b WHERE hex(b.board_blob) = upper(NEW.from_board_hex))
                       )
                   AND m2.to_board_id = COALESCE(
                           NEW.to_board_id,
                           (SELECT b.id FROM boards b WHERE hex(b.board_blob) = upper(NEW.to_board_hex))
                       )
                   AND m2.move_code = NEW.move_code
                   AND m2.flags = NEW.flags)
            )
            WHERE gm_prev.game_id = NEW.game_id
              AND gm_prev.ply = NEW.ply - 1
              AND m_prev.to_board_id = m_cur.from_board_id
         )
            THEN RAISE(ABORT, 'move does not continue from previous ply')
        WHEN EXISTS (
            SELECT 1
            FROM game_moves gm_next
            JOIN moves m_next ON m_next.id = gm_next.move_id
            JOIN moves m_cur ON m_cur.id = COALESCE(
                NEW.move_id,
                (SELECT m2.id
                 FROM moves m2
                 WHERE m2.from_board_id = COALESCE(
                           NEW.from_board_id,
                           (SELECT b.id FROM boards b WHERE hex(b.board_blob) = upper(NEW.from_board_hex))
                       )
                   AND m2.to_board_id = COALESCE(
                           NEW.to_board_id,
                           (SELECT b.id FROM boards b WHERE hex(b.board_blob) = upper(NEW.to_board_hex))
                       )
                   AND m2.move_code = NEW.move_code
                   AND m2.flags = NEW.flags)
            )
            WHERE gm_next.game_id = NEW.game_id
              AND gm_next.ply = NEW.ply + 1
              AND m_cur.to_board_id <> m_next.from_board_id
         )
            THEN RAISE(ABORT, 'move does not connect to next ply')
    END;

    INSERT OR REPLACE INTO game_moves (
        game_id,
        ply,
        move_id
    )
    VALUES (
        NEW.game_id,
        NEW.ply,
        COALESCE(
            NEW.move_id,
            (SELECT m.id
             FROM moves m
             WHERE m.from_board_id = COALESCE(
                       NEW.from_board_id,
                       (SELECT b.id FROM boards b WHERE hex(b.board_blob) = upper(NEW.from_board_hex))
                   )
               AND m.to_board_id = COALESCE(
                       NEW.to_board_id,
                       (SELECT b.id FROM boards b WHERE hex(b.board_blob) = upper(NEW.to_board_hex))
                   )
               AND m.move_code = NEW.move_code
               AND m.flags = NEW.flags)
        )
    );
END;

CREATE TRIGGER IF NOT EXISTS game_moves_write_update
INSTEAD OF UPDATE ON game_moves_write
BEGIN
    SELECT CASE
        WHEN NEW.game_id <> OLD.game_id OR NEW.ply <> OLD.ply
            THEN RAISE(ABORT, 'game_id and ply are immutable; delete/reinsert if you need to move a row')
        WHEN NEW.move_id IS NULL
         AND (NEW.move_code IS NULL OR NEW.flags IS NULL)
            THEN RAISE(ABORT, 'either move_id or move_code+flags must be provided')
    END;

    INSERT OR IGNORE INTO boards (board_blob)
    SELECT unhex(NEW.to_board_hex)
    WHERE NEW.move_id IS NULL
      AND NEW.to_board_id IS NULL
      AND NEW.to_board_hex IS NOT NULL;

    SELECT CASE
        WHEN NEW.move_id IS NULL
         AND COALESCE(
            NEW.from_board_id,
            (SELECT b.id FROM boards b WHERE hex(b.board_blob) = upper(NEW.from_board_hex))
         ) IS NULL
            THEN RAISE(ABORT, 'from_board does not exist')
        WHEN NEW.move_id IS NULL
         AND COALESCE(
            NEW.to_board_id,
            (SELECT b.id FROM boards b WHERE hex(b.board_blob) = upper(NEW.to_board_hex))
         ) IS NULL
            THEN RAISE(ABORT, 'to_board does not exist and could not be created')
    END;

    INSERT OR IGNORE INTO moves (
        from_board_id,
        to_board_id,
        move_code,
        flags
    )
    SELECT
        COALESCE(
            NEW.from_board_id,
            (SELECT b.id FROM boards b WHERE hex(b.board_blob) = upper(NEW.from_board_hex))
        ),
        COALESCE(
            NEW.to_board_id,
            (SELECT b.id FROM boards b WHERE hex(b.board_blob) = upper(NEW.to_board_hex))
        ),
        NEW.move_code,
        NEW.flags
    WHERE NEW.move_id IS NULL;

    SELECT CASE
        WHEN NEW.ply = 1
         AND (
            SELECT m.from_board_id
            FROM moves m
            WHERE m.id = COALESCE(
                NEW.move_id,
                (SELECT m2.id
                 FROM moves m2
                 WHERE m2.from_board_id = COALESCE(
                           NEW.from_board_id,
                           (SELECT b.id FROM boards b WHERE hex(b.board_blob) = upper(NEW.from_board_hex))
                       )
                   AND m2.to_board_id = COALESCE(
                           NEW.to_board_id,
                           (SELECT b.id FROM boards b WHERE hex(b.board_blob) = upper(NEW.to_board_hex))
                       )
                   AND m2.move_code = NEW.move_code
                   AND m2.flags = NEW.flags)
            )
         ) <> (SELECT g.start_board_id FROM games g WHERE g.id = NEW.game_id)
            THEN RAISE(ABORT, 'first ply must begin from games.start_board_id')
        WHEN NEW.ply > 1
         AND NOT EXISTS (
            SELECT 1
            FROM game_moves gm_prev
            JOIN moves m_prev ON m_prev.id = gm_prev.move_id
            JOIN moves m_cur ON m_cur.id = COALESCE(
                NEW.move_id,
                (SELECT m2.id
                 FROM moves m2
                 WHERE m2.from_board_id = COALESCE(
                           NEW.from_board_id,
                           (SELECT b.id FROM boards b WHERE hex(b.board_blob) = upper(NEW.from_board_hex))
                       )
                   AND m2.to_board_id = COALESCE(
                           NEW.to_board_id,
                           (SELECT b.id FROM boards b WHERE hex(b.board_blob) = upper(NEW.to_board_hex))
                       )
                   AND m2.move_code = NEW.move_code
                   AND m2.flags = NEW.flags)
            )
            WHERE gm_prev.game_id = NEW.game_id
              AND gm_prev.ply = NEW.ply - 1
              AND m_prev.to_board_id = m_cur.from_board_id
         )
            THEN RAISE(ABORT, 'move does not continue from previous ply')
        WHEN EXISTS (
            SELECT 1
            FROM game_moves gm_next
            JOIN moves m_next ON m_next.id = gm_next.move_id
            JOIN moves m_cur ON m_cur.id = COALESCE(
                NEW.move_id,
                (SELECT m2.id
                 FROM moves m2
                 WHERE m2.from_board_id = COALESCE(
                           NEW.from_board_id,
                           (SELECT b.id FROM boards b WHERE hex(b.board_blob) = upper(NEW.from_board_hex))
                       )
                   AND m2.to_board_id = COALESCE(
                           NEW.to_board_id,
                           (SELECT b.id FROM boards b WHERE hex(b.board_blob) = upper(NEW.to_board_hex))
                       )
                   AND m2.move_code = NEW.move_code
                   AND m2.flags = NEW.flags)
            )
            WHERE gm_next.game_id = NEW.game_id
              AND gm_next.ply = NEW.ply + 1
              AND m_cur.to_board_id <> m_next.from_board_id
         )
            THEN RAISE(ABORT, 'move does not connect to next ply')
    END;

    UPDATE game_moves
    SET move_id = COALESCE(
        NEW.move_id,
        (SELECT m.id
         FROM moves m
         WHERE m.from_board_id = COALESCE(
                   NEW.from_board_id,
                   (SELECT b.id FROM boards b WHERE hex(b.board_blob) = upper(NEW.from_board_hex))
               )
           AND m.to_board_id = COALESCE(
                   NEW.to_board_id,
                   (SELECT b.id FROM boards b WHERE hex(b.board_blob) = upper(NEW.to_board_hex))
               )
           AND m.move_code = NEW.move_code
           AND m.flags = NEW.flags)
    )
    WHERE game_id = OLD.game_id
      AND ply = OLD.ply;
END;
