-- =========================================
-- Boards rendered as hex for inspection/debugging
-- =========================================
CREATE VIEW IF NOT EXISTS board_hex_view AS
SELECT
    id,
    hex(board_blob) AS board_hex
FROM boards;

-- =========================================
-- Edge statistics with computed rates
-- =========================================
CREATE VIEW IF NOT EXISTS edge_stats AS
SELECT
    e.id,
    e.from_position_id,
    e.to_position_id,
    e.move_uci,
    e.move_san,
    e.frequency,
    e.white_wins,
    e.black_wins,
    e.draws,
    CASE
        WHEN e.frequency = 0 THEN NULL
        ELSE CAST(e.white_wins AS REAL) / e.frequency
    END AS white_win_rate,
    CASE
        WHEN e.frequency = 0 THEN NULL
        ELSE CAST(e.black_wins AS REAL) / e.frequency
    END AS black_win_rate,
    CASE
        WHEN e.frequency = 0 THEN NULL
        ELSE CAST(e.draws AS REAL) / e.frequency
    END AS draw_rate,
    e.avg_elo,
    e.blitz_count,
    e.rapid_count,
    e.classical_count
FROM edges e;

-- =========================================
-- Position lookup view with board hex included
-- =========================================
CREATE VIEW IF NOT EXISTS position_lookup AS
SELECT
    p.id AS position_id,
    p.board_id,
    hex(b.board_blob) AS board_hex,
    p.side_to_move,
    p.castling_rights,
    p.ep_file,
    p.pos_key
FROM positions p
JOIN boards b
  ON b.id = p.board_id;

-- =========================================
-- Move suggestions from exact positions
-- =========================================
CREATE VIEW IF NOT EXISTS move_suggestions AS
SELECT
    p.id AS position_id,
    hex(b.board_blob) AS board_hex,
    p.side_to_move,
    p.castling_rights,
    p.ep_file,
    e.move_uci,
    e.move_san,
    e.frequency,
    e.white_wins,
    e.black_wins,
    e.draws,
    CASE
        WHEN e.frequency = 0 THEN NULL
        ELSE CAST(e.white_wins AS REAL) / e.frequency
    END AS white_win_rate,
    CASE
        WHEN e.frequency = 0 THEN NULL
        ELSE CAST(e.black_wins AS REAL) / e.frequency
    END AS black_win_rate,
    CASE
        WHEN e.frequency = 0 THEN NULL
        ELSE CAST(e.draws AS REAL) / e.frequency
    END AS draw_rate
FROM positions p
JOIN boards b
  ON b.id = p.board_id
JOIN edges e
  ON e.from_position_id = p.id;

-- =========================================
-- Game replay view
-- =========================================
CREATE VIEW IF NOT EXISTS game_replay AS
SELECT
    gm.game_id,
    gm.ply,
    g.white_player,
    g.black_player,
    g.result,
    e.move_uci,
    e.move_san,
    gm.position_id,
    hex(b.board_blob) AS board_hex,
    p.side_to_move,
    p.castling_rights,
    p.ep_file
FROM game_moves gm
JOIN games g
  ON g.id = gm.game_id
JOIN edges e
  ON e.id = gm.edge_id
JOIN positions p
  ON p.id = gm.position_id
JOIN boards b
  ON b.id = p.board_id
ORDER BY gm.game_id, gm.ply;
