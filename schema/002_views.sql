-- =========================================
-- Read-only interface layer
--
-- Core storage is compact and event-driven.
-- These views decode packed values and expose
-- friendlier read surfaces for replay, audit,
-- and snapshot consumption.
-- =========================================

-- =========================================
-- Boards rendered as hex for inspection/debugging
-- =========================================
CREATE VIEW IF NOT EXISTS board_hex_view AS
SELECT
    b.id AS board_id,
    hex(b.board_blob) AS board_hex
FROM boards b;

-- =========================================
-- Game labels decoded from compact codes
-- =========================================
CREATE VIEW IF NOT EXISTS game_labels AS
SELECT
    g.id AS game_id,
    g.white_player_id,
    wp.name AS white_player,
    g.black_player_id,
    bp.name AS black_player,
    g.start_board_id,
    hex(sb.board_blob) AS start_board_hex,
    g.result_code,
    CASE g.result_code
        WHEN 0 THEN '*'
        WHEN 1 THEN '1-0'
        WHEN 2 THEN '0-1'
        WHEN 3 THEN '1/2-1/2'
    END AS result,
    g.termination_code,
    CASE g.termination_code
        WHEN 0 THEN 'unspecified'
        WHEN 1 THEN 'checkmate'
        WHEN 2 THEN 'stalemate'
        WHEN 3 THEN 'insufficient_material'
        WHEN 4 THEN 'resignation'
        WHEN 5 THEN 'draw_agreement'
        WHEN 6 THEN 'repetition'
        WHEN 7 THEN 'move_limit'
        WHEN 8 THEN 'time_limit'
        WHEN 9 THEN 'abandonment'
    END AS termination_reason,
    g.site,
    g.event,
    g.round,
    g.game_date,
    g.time_control,
    g.eco,
    g.opening,
    g.variation,
    g.pgn_source
FROM games g
JOIN players wp ON wp.id = g.white_player_id
JOIN players bp ON bp.id = g.black_player_id
JOIN boards sb ON sb.id = g.start_board_id;

-- =========================================
-- Decoded move identity and flags
--
-- move_code bit layout:
--   bits  0- 5 : from square  (0..63)
--   bits  6-11 : to square    (0..63)
--   bits 12-14 : promotion    (0 = none, 1 = knight,
--                              2 = bishop, 3 = rook, 4 = queen)
--   bit      15: reserved
--
-- flags bit layout:
--   bit  0 : capture
--   bit  1 : check
--   bit  2 : mate
--   bit  3 : en passant
--   bit  4 : pawn double push
--   bit  5 : short castle
--   bit  6 : long castle
--   bit 15 : new game marker
-- =========================================
CREATE VIEW IF NOT EXISTS move_decoded AS
WITH decoded AS (
    SELECT
        m.id AS move_id,
        m.from_board_id,
        m.to_board_id,
        m.move_code,
        m.flags,
        (m.move_code & 63) AS from_sq,
        ((m.move_code >> 6) & 63) AS to_sq,
        ((m.move_code >> 12) & 7) AS promotion_code
    FROM moves m
)
SELECT
    d.move_id,
    d.from_board_id,
    d.to_board_id,
    d.move_code,
    d.flags,
    d.from_sq,
    d.to_sq,
    char(unicode('a') + (d.from_sq % 8)) || char(unicode('1') + (d.from_sq / 8)) AS from_square,
    char(unicode('a') + (d.to_sq % 8)) || char(unicode('1') + (d.to_sq / 8)) AS to_square,
    d.promotion_code,
    CASE d.promotion_code
        WHEN 1 THEN 'n'
        WHEN 2 THEN 'b'
        WHEN 3 THEN 'r'
        WHEN 4 THEN 'q'
        ELSE ''
    END AS promotion_suffix,
    char(unicode('a') + (d.from_sq % 8)) || char(unicode('1') + (d.from_sq / 8)) ||
    char(unicode('a') + (d.to_sq % 8)) || char(unicode('1') + (d.to_sq / 8)) ||
    CASE d.promotion_code
        WHEN 1 THEN 'n'
        WHEN 2 THEN 'b'
        WHEN 3 THEN 'r'
        WHEN 4 THEN 'q'
        ELSE ''
    END AS move_uci,
    ((d.flags >> 0) & 1) != 0 AS is_capture,
    ((d.flags >> 1) & 1) != 0 AS is_check,
    ((d.flags >> 2) & 1) != 0 AS is_mate,
    ((d.flags >> 3) & 1) != 0 AS is_en_passant,
    ((d.flags >> 4) & 1) != 0 AS is_pawn_double_push,
    ((d.flags >> 5) & 1) != 0 AS is_short_castle,
    ((d.flags >> 6) & 1) != 0 AS is_long_castle,
    ((d.flags >> 15) & 1) != 0 AS is_new_game_marker
FROM decoded d;

-- =========================================
-- Aggregated move statistics, derived from game history
-- =========================================
CREATE VIEW IF NOT EXISTS move_stats AS
SELECT
    gm.move_id,
    COUNT(*) AS frequency,
    SUM(CASE WHEN g.result_code = 1 THEN 1 ELSE 0 END) AS white_wins,
    SUM(CASE WHEN g.result_code = 2 THEN 1 ELSE 0 END) AS black_wins,
    SUM(CASE WHEN g.result_code = 3 THEN 1 ELSE 0 END) AS draws,
    CASE
        WHEN COUNT(*) = 0 THEN NULL
        ELSE CAST(SUM(CASE WHEN g.result_code = 1 THEN 1 ELSE 0 END) AS REAL) / COUNT(*)
    END AS white_win_rate,
    CASE
        WHEN COUNT(*) = 0 THEN NULL
        ELSE CAST(SUM(CASE WHEN g.result_code = 2 THEN 1 ELSE 0 END) AS REAL) / COUNT(*)
    END AS black_win_rate,
    CASE
        WHEN COUNT(*) = 0 THEN NULL
        ELSE CAST(SUM(CASE WHEN g.result_code = 3 THEN 1 ELSE 0 END) AS REAL) / COUNT(*)
    END AS draw_rate
FROM game_moves gm
JOIN games g ON g.id = gm.game_id
GROUP BY gm.move_id;

-- =========================================
-- Enriched board-to-board move lookup
-- =========================================
CREATE VIEW IF NOT EXISTS move_lookup AS
SELECT
    md.move_id,
    md.move_code,
    md.flags,
    md.from_board_id,
    hex(fb.board_blob) AS from_board_hex,
    md.to_board_id,
    hex(tb.board_blob) AS to_board_hex,
    md.from_sq,
    md.to_sq,
    md.from_square,
    md.to_square,
    md.move_uci,
    md.promotion_code,
    md.promotion_suffix,
    md.is_capture,
    md.is_check,
    md.is_mate,
    md.is_en_passant,
    md.is_pawn_double_push,
    md.is_short_castle,
    md.is_long_castle,
    md.is_new_game_marker,
    COALESCE(ms.frequency, 0) AS frequency,
    COALESCE(ms.white_wins, 0) AS white_wins,
    COALESCE(ms.black_wins, 0) AS black_wins,
    COALESCE(ms.draws, 0) AS draws,
    ms.white_win_rate,
    ms.black_win_rate,
    ms.draw_rate
FROM move_decoded md
JOIN boards fb ON fb.id = md.from_board_id
JOIN boards tb ON tb.id = md.to_board_id
LEFT JOIN move_stats ms ON ms.move_id = md.move_id;

-- =========================================
-- Board-walk suggestions from a board snapshot
-- Excludes the synthetic new-game marker row.
-- =========================================
CREATE VIEW IF NOT EXISTS board_move_suggestions AS
SELECT
    ml.from_board_id AS board_id,
    ml.from_board_hex AS board_hex,
    ml.move_id,
    ml.move_uci,
    ml.to_board_id,
    ml.to_board_hex,
    ml.is_capture,
    ml.is_check,
    ml.is_mate,
    ml.is_en_passant,
    ml.is_pawn_double_push,
    ml.is_short_castle,
    ml.is_long_castle,
    ml.frequency,
    ml.white_wins,
    ml.black_wins,
    ml.draws,
    ml.white_win_rate,
    ml.black_win_rate,
    ml.draw_rate
FROM move_lookup ml
WHERE ml.is_new_game_marker = 0;

-- =========================================
-- Ordered move-event stream for each game
-- =========================================
CREATE VIEW IF NOT EXISTS game_replay AS
SELECT
    gm.game_id,
    gm.ply,
    gl.white_player,
    gl.black_player,
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
    gl.pgn_source,
    ml.move_id,
    ml.move_uci,
    ml.from_board_id,
    ml.from_board_hex,
    ml.to_board_id,
    ml.to_board_hex,
    ml.is_capture,
    ml.is_check,
    ml.is_mate,
    ml.is_en_passant,
    ml.is_pawn_double_push,
    ml.is_short_castle,
    ml.is_long_castle,
    ml.frequency,
    ml.white_wins,
    ml.black_wins,
    ml.draws
FROM game_moves gm
JOIN game_labels gl ON gl.game_id = gm.game_id
JOIN move_lookup ml ON ml.move_id = gm.move_id
ORDER BY gm.game_id, gm.ply;

-- =========================================
-- Replayed board snapshots by game/ply
--
-- ply = 0 is the game start board.
-- ply > 0 are the resulting boards after each move.
-- =========================================
CREATE VIEW IF NOT EXISTS positions AS
SELECT
    g.id AS game_id,
    0 AS ply,
    g.start_board_id AS board_id,
    hex(sb.board_blob) AS board_hex,
    NULL AS via_move_id,
    NULL AS via_move_code,
    NULL AS via_move_uci
FROM games g
JOIN boards sb ON sb.id = g.start_board_id
UNION ALL
SELECT
    gm.game_id,
    gm.ply,
    m.to_board_id AS board_id,
    hex(tb.board_blob) AS board_hex,
    gm.move_id AS via_move_id,
    m.move_code AS via_move_code,
    md.move_uci AS via_move_uci
FROM game_moves gm
JOIN moves m ON m.id = gm.move_id
JOIN move_decoded md ON md.move_id = gm.move_id
JOIN boards tb ON tb.id = m.to_board_id;

-- =========================================
-- Final board snapshot for each game
-- If a game has no recorded moves, the start board is the final board.
-- =========================================
CREATE VIEW IF NOT EXISTS game_final_board AS
WITH last_ply AS (
    SELECT
        gm.game_id,
        MAX(gm.ply) AS final_ply
    FROM game_moves gm
    GROUP BY gm.game_id
)
SELECT
    gl.game_id,
    gl.white_player,
    gl.black_player,
    gl.result,
    gl.termination_reason,
    COALESCE(lp.final_ply, 0) AS final_ply,
    COALESCE(m.to_board_id, gl.start_board_id) AS final_board_id,
    COALESCE(hex(tb.board_blob), gl.start_board_hex) AS final_board_hex
FROM game_labels gl
LEFT JOIN last_ply lp ON lp.game_id = gl.game_id
LEFT JOIN game_moves gm ON gm.game_id = lp.game_id AND gm.ply = lp.final_ply
LEFT JOIN moves m ON m.id = gm.move_id
LEFT JOIN boards tb ON tb.id = m.to_board_id;
