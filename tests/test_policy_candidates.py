from __future__ import annotations

import io
import sqlite3
from pathlib import Path

from chessgpt.policy.candidates import build_candidate_set, move_allowed
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


def test_build_candidate_set_binds_when_candidates_exist() -> None:
    conn = make_test_conn()
    try:
        seed_opening_corpus(conn)

        cs = build_candidate_set(conn, 1, min_frequency=1, limit=10)

        assert cs.format_version == 1
        assert cs.position_id == 1
        assert cs.binding_required is True
        assert cs.moves == ("e2e4", "d2d4")
        assert len(cs.candidate_set_id) == 64
        assert move_allowed("e2e4", cs) is True
        assert move_allowed("b1c3", cs) is False
    finally:
        conn.close()


def test_build_candidate_set_allows_fallback_when_no_candidates() -> None:
    conn = make_test_conn()
    try:
        cs = build_candidate_set(conn, 999, min_frequency=1, limit=10)

        assert cs.binding_required is False
        assert cs.moves == ()
        assert move_allowed("b1c3", cs) is True
    finally:
        conn.close()