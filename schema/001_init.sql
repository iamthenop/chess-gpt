PRAGMA foreign_keys = ON;

BEGIN;

-- =========================================
-- Boards
-- Pure board geometry only.
-- 32-byte packed nibble representation.
--
-- board id 0 = empty board sentinel
-- board id 1 = standard start position
--
-- UNIQUE(board_blob) already creates the hot lookup index,
-- so no separate secondary index is needed here.
-- =========================================
CREATE TABLE IF NOT EXISTS boards (
    id          INTEGER PRIMARY KEY,
    board_blob  BLOB NOT NULL CHECK (length(board_blob) = 32),
    UNIQUE(board_blob)
);

INSERT OR IGNORE INTO boards (id, board_blob) VALUES
    (0, X'0000000000000000000000000000000000000000000000000000000000000000');

INSERT OR IGNORE INTO boards (id, board_blob) VALUES
    (1, X'423562341111111100000000000000000000000000000000ffffffffcedabdec');

-- =========================================
-- Moves
-- Aggregated board-to-board transitions.
--
-- move_code bit layout (16-bit unsigned integer):
--   bits  0- 5 : from square  (0..63)
--   bits  6-11 : to square    (0..63)
--   bits 12-14 : promotion    (0 = none, 1 = knight, 2 = bishop,
--                              3 = rook, 4 = queen)
--   bit      15: reserved
--
-- flags bit layout (16-bit unsigned integer):
--   bit  0 : capture
--   bit  1 : check
--   bit  2 : mate
--   bit  3 : en passant
--   bit  4 : pawn double push
--   bit  5 : short castle
--   bit  6 : long castle
--   bits 7-14 : reserved
--   bit 15 : new game marker
--
-- The sentinel move id 0 is reserved for a synthetic game-start edge:
--   empty board -> start board
-- This keeps game streams anchorable without inventing a missing from-board.
-- =========================================
CREATE TABLE IF NOT EXISTS moves (
    id              INTEGER PRIMARY KEY,
    from_board_id   INTEGER NOT NULL,
    to_board_id     INTEGER NOT NULL,
    move_code       INTEGER NOT NULL DEFAULT 0
                    CHECK (move_code BETWEEN 0 AND 65535),
    flags           INTEGER NOT NULL DEFAULT 0
                    CHECK (flags BETWEEN 0 AND 65535),

    FOREIGN KEY (from_board_id) REFERENCES boards(id) ON DELETE CASCADE,
    FOREIGN KEY (to_board_id)   REFERENCES boards(id) ON DELETE CASCADE,

    CHECK (from_board_id <> to_board_id),
    CHECK (
        ((flags >> 15) & 1) = 0
        OR (from_board_id = 0 AND to_board_id = 1 AND move_code = 0)
    ),

    UNIQUE(from_board_id, move_code, to_board_id)
);

-- UNIQUE(from_board_id, move_code, to_board_id) already covers the hot path
-- for lookups starting from a board and specific move code.
CREATE INDEX IF NOT EXISTS idx_moves_to_board
    ON moves(to_board_id);

INSERT OR IGNORE INTO moves (id, from_board_id, to_board_id, move_code, flags) VALUES
    (0, 0, 1, 0, 1 << 15);

-- =========================================
-- Players
-- Player identity is normalized to reduce duplication across games.
-- =========================================
CREATE TABLE IF NOT EXISTS players (
    id      INTEGER PRIMARY KEY,
    name    TEXT NOT NULL,
    UNIQUE(name)
);

-- =========================================
-- Games
-- One row per recorded game / puzzle / study line.
--
-- result_code:
--   0 = * / unknown / in-progress
--   1 = 1-0
--   2 = 0-1
--   3 = 1/2-1/2
--
-- termination_code:
--   0 = unspecified
--   1 = checkmate
--   2 = stalemate
--   3 = insufficient_material
--   4 = resignation
--   5 = draw_agreement
--   6 = repetition
--   7 = move_limit
--   8 = time_limit
--   9 = abandonment
--
-- start_board_id allows standard games, puzzles, studies,
-- and non-standard starting positions.
-- =========================================
CREATE TABLE IF NOT EXISTS games (
    id                INTEGER PRIMARY KEY,
    white_player_id   INTEGER NOT NULL,
    black_player_id   INTEGER NOT NULL,
    start_board_id    INTEGER NOT NULL DEFAULT 1,

    result_code       INTEGER NOT NULL DEFAULT 0
                      CHECK (result_code BETWEEN 0 AND 3),
    termination_code  INTEGER NOT NULL DEFAULT 0
                      CHECK (termination_code BETWEEN 0 AND 9),

    site              TEXT,
    event             TEXT,
    round             TEXT,
    game_date         TEXT,
    time_control      TEXT,
    eco               TEXT,
    opening           TEXT,
    variation         TEXT,
    pgn_source        TEXT,

    FOREIGN KEY (white_player_id) REFERENCES players(id) ON DELETE RESTRICT,
    FOREIGN KEY (black_player_id) REFERENCES players(id) ON DELETE RESTRICT,
    FOREIGN KEY (start_board_id)  REFERENCES boards(id)  ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_games_players
    ON games(white_player_id, black_player_id);

CREATE INDEX IF NOT EXISTS idx_games_result_code
    ON games(result_code, termination_code);

CREATE INDEX IF NOT EXISTS idx_games_start_board
    ON games(start_board_id);

-- =========================================
-- Game Moves
-- Ordered move-event stream for each game.
--
-- The first real move in a game must begin from games.start_board_id.
-- That invariant is best enforced at the write layer through views/triggers.
--
-- WITHOUT ROWID keeps the primary key compact for a very large table.
-- =========================================
CREATE TABLE IF NOT EXISTS game_moves (
    game_id      INTEGER NOT NULL,
    ply          INTEGER NOT NULL CHECK (ply > 0),
    move_id      INTEGER NOT NULL,

    PRIMARY KEY (game_id, ply),
    FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE CASCADE,
    FOREIGN KEY (move_id) REFERENCES moves(id) ON DELETE RESTRICT
) WITHOUT ROWID;

CREATE INDEX IF NOT EXISTS idx_game_moves_move_id
    ON game_moves(move_id);

COMMIT;
