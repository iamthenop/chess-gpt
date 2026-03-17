from __future__ import annotations

import io
import sqlite3
from pathlib import Path

import pytest

from chessgpt.api.positions import get_position_payload
from chessgpt.errors import PositionNotFoundError
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


def test_get_position_payload_for_start_position() -> None:
    conn = make_test_conn()
    try:
        parsed_game = parse_single_game(
            """
[Event "Test Game"]
[Site "Local"]
[Date "2026.03.16"]
[Round "1"]
[White "White"]
[Black "Black"]
[Result "1-0"]

1. e4 e5 2. Nf3 Nc6 1-0
"""
        )
        ingest_game(conn, parsed_game, "tests/sample.pgn")

        payload = get_position_payload(conn, 1)

        assert payload == {
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
    finally:
        conn.close()


def test_get_position_payload_raises_for_unknown_position() -> None:
    conn = make_test_conn()
    try:
        with pytest.raises(PositionNotFoundError, match="position_id not found"):
            get_position_payload(conn, 999)
    finally:
        conn.close()