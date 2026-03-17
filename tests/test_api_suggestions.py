from __future__ import annotations

import io
import sqlite3
from pathlib import Path

from chessgpt.api.suggestions import get_suggestions_payload
from chessgpt.pgn.ingest import ingest_game
from chessgpt.pgn.replay import read_games


def init_test_db(conn: sqlite3.Connection) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    schema_dir = repo_root / "schema"

    for schema_file in sorted(schema_dir.glob("*.sql")):
        sql = schema_file.read_text(encoding="utf-8")
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


def test_get_suggestions_payload_for_start_position() -> None:
    conn = make_test_conn()
    try:
        game1 = parse_single_game(
            """
[Event "Game 1"]
[Site "Local"]
[Date "2026.03.16"]
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
[Date "2026.03.16"]
[Round "2"]
[White "White"]
[Black "Black"]
[Result "1/2-1/2"]

1. e4 c5 2. Nf3 d6 1/2-1/2
"""
        )
        game3 = parse_single_game(
            """
[Event "Game 3"]
[Site "Local"]
[Date "2026.03.16"]
[Round "3"]
[White "White"]
[Black "Black"]
[Result "0-1"]

1. d4 d5 2. c4 e6 0-1
"""
        )

        ingest_game(conn, game1, "tests/g1.pgn")
        ingest_game(conn, game2, "tests/g2.pgn")
        ingest_game(conn, game3, "tests/g3.pgn")

        payload = get_suggestions_payload(conn, 1, min_frequency=1, limit=10)

        assert payload["format_version"] == 1
        assert payload["position_id"] == 1
        assert payload["min_frequency"] == 1
        assert len(payload["candidate_moves"]) == 2

        first = payload["candidate_moves"][0]
        second = payload["candidate_moves"][1]

        assert first["move_uci"] == "e2e4"
        assert first["move_san"] == "e4"
        assert first["frequency"] == 2
        assert first["white_wins"] == 1
        assert first["black_wins"] == 0
        assert first["draws"] == 1
        assert first["white_win_rate"] == 0.5
        assert first["draw_rate"] == 0.5
        assert first["black_win_rate"] == 0.0

        assert second["move_uci"] == "d2d4"
        assert second["move_san"] == "d4"
        assert second["frequency"] == 1
        assert second["white_wins"] == 0
        assert second["black_wins"] == 1
        assert second["draws"] == 0
        assert second["white_win_rate"] == 0.0
        assert second["draw_rate"] == 0.0
        assert second["black_win_rate"] == 1.0
    finally:
        conn.close()


def test_get_suggestions_payload_respects_min_frequency() -> None:
    conn = make_test_conn()
    try:
        game1 = parse_single_game(
            """
[Event "Game 1"]
[Site "Local"]
[Date "2026.03.16"]
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
[Date "2026.03.16"]
[Round "2"]
[White "White"]
[Black "Black"]
[Result "1/2-1/2"]

1. e4 c5 2. Nf3 d6 1/2-1/2
"""
        )
        game3 = parse_single_game(
            """
[Event "Game 3"]
[Site "Local"]
[Date "2026.03.16"]
[Round "3"]
[White "White"]
[Black "Black"]
[Result "0-1"]

1. d4 d5 2. c4 e6 0-1
"""
        )

        ingest_game(conn, game1, "tests/g1.pgn")
        ingest_game(conn, game2, "tests/g2.pgn")
        ingest_game(conn, game3, "tests/g3.pgn")

        payload = get_suggestions_payload(conn, 1, min_frequency=2, limit=10)

        assert len(payload["candidate_moves"]) == 1
        assert payload["candidate_moves"][0]["move_uci"] == "e2e4"
        assert payload["candidate_moves"][0]["frequency"] == 2
    finally:
        conn.close()


def test_get_suggestions_payload_for_unknown_position_returns_empty_list() -> None:
    conn = make_test_conn()
    try:
        payload = get_suggestions_payload(conn, 999, min_frequency=1, limit=10)

        assert payload == {
            "format_version": 1,
            "position_id": 999,
            "min_frequency": 1,
            "candidate_moves": [],
        }
    finally:
        conn.close()