from __future__ import annotations

import io
import sqlite3
from pathlib import Path

from chessgpt.api.turns import get_turn_payload
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


def seed_opening_corpus(conn: sqlite3.Connection) -> None:
    games = [
        """
[Event "Game 1"]
[Site "Local"]
[Date "2026.03.16"]
[Round "1"]
[White "White"]
[Black "Black"]
[Result "1-0"]

1. e4 e5 2. Nf3 Nc6 1-0
""",
        """
[Event "Game 2"]
[Site "Local"]
[Date "2026.03.16"]
[Round "2"]
[White "White"]
[Black "Black"]
[Result "1/2-1/2"]

1. e4 c5 2. Nf3 d6 1/2-1/2
""",
        """
[Event "Game 3"]
[Site "Local"]
[Date "2026.03.16"]
[Round "3"]
[White "White"]
[Black "Black"]
[Result "0-1"]

1. d4 d5 2. c4 e6 0-1
""",
    ]

    for i, pgn_text in enumerate(games, start=1):
        ingest_game(conn, parse_single_game(pgn_text), f"tests/seed_{i}.pgn")


def test_get_turn_payload_for_start_position() -> None:
    conn = make_test_conn()
    try:
        seed_opening_corpus(conn)

        payload = get_turn_payload(conn, 1, min_frequency=1, limit=10, strict_mode=True)

        assert payload["format_version"] == 1
        assert payload["position"] == {
            "format_version": 1,
            "position_id": 1,
            "side_to_move": "w",
            "castling": "1111",
            "ep_file": "-",
            "board_rows": [
                "42356324",
                "11111111",
                "00000000",
                "00000000",
                "00000000",
                "00000000",
                "FFFFFFFF",
                "CEDBADEC",
            ],
        }

        assert payload["instructions"] == {
            "task": "Choose exactly one move.",
            "output_format": "Return exactly one UCI move and nothing else.",
            "strict_mode": True,
        }

        assert len(payload["candidate_moves"]) == 2
        assert payload["candidate_moves"][0]["move_uci"] == "e2e4"
        assert payload["candidate_moves"][1]["move_uci"] == "d2d4"

        policy = payload["candidate_policy"]
        assert policy["candidate_binding_required"] is True
        assert policy["fallback_policy"] == "allow_any_legal_move_if_no_candidates"
        assert policy["candidate_moves"] == ["e2e4", "d2d4"]
        assert len(policy["candidate_set_id"]) == 64
    finally:
        conn.close()


def test_get_turn_payload_respects_min_frequency() -> None:
    conn = make_test_conn()
    try:
        seed_opening_corpus(conn)

        payload = get_turn_payload(conn, 1, min_frequency=2, limit=10, strict_mode=True)

        assert len(payload["candidate_moves"]) == 1
        assert payload["candidate_moves"][0]["move_uci"] == "e2e4"
        assert payload["candidate_moves"][0]["frequency"] == 2

        policy = payload["candidate_policy"]
        assert policy["candidate_binding_required"] is True
        assert policy["candidate_moves"] == ["e2e4"]
    finally:
        conn.close()


def test_get_turn_payload_can_set_non_strict_mode() -> None:
    conn = make_test_conn()
    try:
        seed_opening_corpus(conn)

        payload = get_turn_payload(conn, 1, min_frequency=1, limit=10, strict_mode=False)

        assert payload["instructions"]["strict_mode"] is False
    finally:
        conn.close()