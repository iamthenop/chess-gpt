PRAGMA foreign_keys = ON;

BEGIN;

-- =========================================
-- Boards
-- Pure board layout only.
-- 32-byte packed nibble representation.
-- =========================================
CREATE TABLE IF NOT EXISTS boards (
    id            INTEGER PRIMARY KEY,
    board_blob    BLOB NOT NULL CHECK (length(board_blob) = 32),
    UNIQUE(board_blob)
);

CREATE INDEX IF NOT EXISTS idx_boards_blob
    ON boards(board_blob);

-- =========================================
-- Positions
-- Board + minimal game-state metadata.
-- side_to_move: 0 = white, 1 = black
-- castling_rights bitmask:
--   1 = WL, 2 = WS, 4 = BL, 8 = BS
-- ep_file: 0..7 for a..h, NULL when unavailable
-- =========================================
CREATE TABLE IF NOT EXISTS positions (
    id                INTEGER PRIMARY KEY,
    board_id          INTEGER NOT NULL,
    side_to_move      INTEGER NOT NULL CHECK (side_to_move IN (0, 1)),
    castling_rights   INTEGER NOT NULL DEFAULT 0 CHECK (castling_rights BETWEEN 0 AND 15),
    ep_file           INTEGER CHECK (ep_file IS NULL OR ep_file BETWEEN 0 AND 7),
    pos_key           BLOB,
    FOREIGN KEY (board_id) REFERENCES boards(id) ON DELETE CASCADE,
    UNIQUE(board_id, side_to_move, castling_rights, ep_file)
);

CREATE INDEX IF NOT EXISTS idx_positions_board
    ON positions(board_id);

CREATE INDEX IF NOT EXISTS idx_positions_lookup
    ON positions(board_id, side_to_move, castling_rights, ep_file);

-- =========================================
-- Games
-- Raw provenance for imported PGNs.
-- =========================================
CREATE TABLE IF NOT EXISTS games (
    id               INTEGER PRIMARY KEY,
    site             TEXT,
    event            TEXT,
    round            TEXT,
    game_date        TEXT,
    white_player     TEXT,
    black_player     TEXT,
    result           TEXT NOT NULL CHECK (result IN ('1-0', '0-1', '1/2-1/2', '*')),
    time_control     TEXT,
    eco              TEXT,
    opening          TEXT,
    variation        TEXT,
    pgn_source       TEXT
);

CREATE INDEX IF NOT EXISTS idx_games_result
    ON games(result);

CREATE INDEX IF NOT EXISTS idx_games_players
    ON games(white_player, black_player);

-- =========================================
-- Edges
-- Move-labeled transitions between positions.
-- move_uci examples: e2e4, e7e8q, e1g1
-- move_san examples: e4, Qxd5+, O-O
-- =========================================
CREATE TABLE IF NOT EXISTS edges (
    id                   INTEGER PRIMARY KEY,
    from_position_id     INTEGER NOT NULL,
    to_position_id       INTEGER NOT NULL,
    move_uci             TEXT NOT NULL,
    move_san             TEXT,

    frequency            INTEGER NOT NULL DEFAULT 0 CHECK (frequency >= 0),
    white_wins           INTEGER NOT NULL DEFAULT 0 CHECK (white_wins >= 0),
    black_wins           INTEGER NOT NULL DEFAULT 0 CHECK (black_wins >= 0),
    draws                INTEGER NOT NULL DEFAULT 0 CHECK (draws >= 0),

    avg_elo              REAL,
    blitz_count          INTEGER NOT NULL DEFAULT 0 CHECK (blitz_count >= 0),
    rapid_count          INTEGER NOT NULL DEFAULT 0 CHECK (rapid_count >= 0),
    classical_count      INTEGER NOT NULL DEFAULT 0 CHECK (classical_count >= 0),

    FOREIGN KEY (from_position_id) REFERENCES positions(id) ON DELETE CASCADE,
    FOREIGN KEY (to_position_id)   REFERENCES positions(id) ON DELETE CASCADE,

    UNIQUE(from_position_id, move_uci, to_position_id)
);

CREATE INDEX IF NOT EXISTS idx_edges_from
    ON edges(from_position_id);

CREATE INDEX IF NOT EXISTS idx_edges_to
    ON edges(to_position_id);

CREATE INDEX IF NOT EXISTS idx_edges_from_freq
    ON edges(from_position_id, frequency DESC);

CREATE INDEX IF NOT EXISTS idx_edges_from_move
    ON edges(from_position_id, move_uci);

-- =========================================
-- Game path
-- One row per ply in an imported game.
-- position_id is the resulting position after the ply.
-- =========================================
CREATE TABLE IF NOT EXISTS game_moves (
    id                INTEGER PRIMARY KEY,
    game_id           INTEGER NOT NULL,
    ply               INTEGER NOT NULL CHECK (ply > 0),
    edge_id           INTEGER NOT NULL,
    position_id       INTEGER NOT NULL,
    FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE CASCADE,
    FOREIGN KEY (edge_id) REFERENCES edges(id) ON DELETE CASCADE,
    FOREIGN KEY (position_id) REFERENCES positions(id) ON DELETE CASCADE,
    UNIQUE(game_id, ply)
);

CREATE INDEX IF NOT EXISTS idx_game_moves_game
    ON game_moves(game_id, ply);

-- =========================================
-- Position tags
-- Optional structure labels for later similarity search.
-- Examples:
--   ('pawn_structure', 'iqp')
--   ('king_safety', 'opposite_castled')
-- =========================================
CREATE TABLE IF NOT EXISTS position_tags (
    position_id       INTEGER NOT NULL,
    tag               TEXT NOT NULL,
    value             TEXT,
    FOREIGN KEY (position_id) REFERENCES positions(id) ON DELETE CASCADE,
    PRIMARY KEY (position_id, tag)
);

CREATE INDEX IF NOT EXISTS idx_position_tags_tag
    ON position_tags(tag, value);

COMMIT;
