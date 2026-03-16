from __future__ import annotations

import io
import sqlite3
from pathlib import Path

from chessgpt.encoding.board_codec import starting_board
from chessgpt.pgn.ingest import ingest_game
from chessgpt.pgn.replay import read_games
from chessgpt.query.suggest import (
    find_position_id,
    suggest_moves,
    suggest_moves_for_position_id,
)


def init_test_db(conn: sqlite3.Connection) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    schema_dir = repo_root / "schema"

    for schema_file in ("001_init.sql", "002_views.sql"):
        sql = (schema_dir / schema_file).read_text(encoding="utf-8")
        conn.executescript(sql)


def make_test_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    init_test_db(conn)
    return conn


def parse_single_game(pgn_text: str):
    parsed_games = list(read_games(io.StringIO(pgn_text.strip())))
    assert len(parsed_games) == 1
    return parsed_games[0]


def test_find_position_id_returns_starting_position() -> None:
    conn = make_test_conn()
    try:
        parsed_game = parse_single_game(
            """
[Event "Test Game"]
[Site "Local"]
[Date "2026.03.15"]
[Round "1"]
[White "White"]
[Black "Black"]
[Result "1-0"]

1. e4 e5 2. Nf3 Nc6 1-0
"""
        )
        ingest_game(conn, parsed_game, "tests/sample.pgn")

        position_id = find_position_id(
            conn,
            board_blob=starting_board(),
            side_to_move=0,
            castling_rights=0b1111,
            ep_file=None,
        )

        assert position_id is not None
        assert isinstance(position_id, int)
    finally:
        conn.close()


def test_suggest_moves_returns_empty_for_unknown_position() -> None:
    conn = make_test_conn()
    try:
        moves = suggest_moves(
            conn,
            board_blob=starting_board(),
            side_to_move=0,
            castling_rights=0b1111,
            ep_file=None,
            limit=10,
        )
        assert moves == []
    finally:
        conn.close()


def test_suggest_moves_from_starting_position_returns_expected_first_moves() -> None:
    conn = make_test_conn()
    try:
        game1 = parse_single_game(
            """
[Event "Game 1"]
[Site "Local"]
[Date "2026.03.15"]
[Round "1"]
[White "White"]
[Black "Black"]
[Result "1-0"]

1. e4 e5 2. Nf3 Nc6 1-0
"""
        )
        game2 = parse_single_game(
            """
[Event "Game 2"]
[Site "Local"]
[Date "2026.03.15"]
[Round "2"]
[White "White"]
[Black "Black"]
[Result "0-1"]

1. d4 d5 2. c4 e6 0-1
"""
        )
        game3 = parse_single_game(
            """
[Event "Game 3"]
[Site "Local"]
[Date "2026.03.15"]
[Round "3"]
[White "White"]
[Black "Black"]
[Result "1/2-1/2"]

1. e4 c5 2. Nf3 d6 1/2-1/2
"""
        )

        ingest_game(conn, game1, "tests/g1.pgn")
        ingest_game(conn, game2, "tests/g2.pgn")
        ingest_game(conn, game3, "tests/g3.pgn")

        moves = suggest_moves(
            conn,
            board_blob=starting_board(),
            side_to_move=0,
            castling_rights=0b1111,
            ep_file=None,
            limit=10,
        )

        assert len(moves) == 2

        # e4 should come first because it was seen twice.
        assert moves[0].move_uci == "e2e4"
        assert moves[0].move_san == "e4"
        assert moves[0].frequency == 2
        assert moves[0].white_wins == 1
        assert moves[0].black_wins == 0
        assert moves[0].draws == 1
        assert moves[0].white_win_rate == 0.5
        assert moves[0].black_win_rate == 0.0
        assert moves[0].draw_rate == 0.5

        assert moves[1].move_uci == "d2d4"
        assert moves[1].move_san == "d4"
        assert moves[1].frequency == 1
        assert moves[1].white_wins == 0
        assert moves[1].black_wins == 1
        assert moves[1].draws == 0
        assert moves[1].white_win_rate == 0.0
        assert moves[1].black_win_rate == 1.0
        assert moves[1].draw_rate == 0.0

    finally:
        conn.close()


def test_suggest_moves_for_position_id_after_e4_returns_black_replies() -> None:
    conn = make_test_conn()
    try:
        game1 = parse_single_game(
            """
[Event "Game 1"]
[Site "Local"]
[Date "2026.03.15"]
[Round "1"]
[White "White"]
[Black "Black"]
[Result "1-0"]

1. e4 e5 2. Nf3 Nc6 1-0
"""
        )
        game2 = parse_single_game(
            """
[Event "Game 2"]
[Site "Local"]
[Date "2026.03.15"]
[Round "2"]
[White "White"]
[Black "Black"]
[Result "1/2-1/2"]

1. e4 c5 2. Nf3 d6 1/2-1/2
"""
        )

        ingest_game(conn, game1, "tests/g1.pgn")
        ingest_game(conn, game2, "tests/g2.pgn")

        # Position after 1.e4
        e4_position = conn.execute(
            """
            SELECT p.id
            FROM game_moves gm
            JOIN positions p ON p.id = gm.position_id
            JOIN edges e ON e.id = gm.edge_id
            WHERE gm.ply = 1
              AND e.move_uci = 'e2e4'
            LIMIT 1
            """
        ).fetchone()

        assert e4_position is not None

        moves = suggest_moves_for_position_id(conn, int(e4_position["id"]), limit=10)

        assert len(moves) == 2
        assert moves[0].move_uci == "e7e5"
        assert moves[0].move_san == "e5"
        assert moves[0].frequency == 1

        assert moves[1].move_uci == "c7c5"
        assert moves[1].move_san == "c5"
        assert moves[1].frequency == 1
    finally:
        conn.close()