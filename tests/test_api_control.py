from __future__ import annotations

import io
import sqlite3
from pathlib import Path

import pytest

from chessgpt.api.control import apply_move_payload
from chessgpt.errors import IllegalMoveError, InvalidMoveSyntaxError, MoveNotSuggestedError
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


def test_apply_move_payload_for_valid_suggested_move() -> None:
    conn = make_test_conn()
    try:
        seed_opening_corpus(conn)

        payload = apply_move_payload(
            conn,
            position_id=1,
            move_uci="e2e4",
            actor="test",
            require_suggested=True,
            write_audit=True,
        )

        assert payload["format_version"] == 1
        assert payload["source_position_id"] == 1
        assert payload["move_uci"] == "e2e4"
        assert payload["move_san"] == "e4"
        assert payload["resulting_position_id"] is not None
        assert payload["side_to_move"] == "b"
        assert payload["castling"] == "1111"
        assert payload["ep_file"] == "e"
        assert payload["board_rows"] == [
            "42356324",
            "11110111",
            "00000000",
            "00001000",
            "00000000",
            "00000000",
            "FFFFFFFF",
            "CEDBADEC",
        ]
    finally:
        conn.close()


def test_apply_move_payload_rejects_invalid_syntax() -> None:
    conn = make_test_conn()
    try:
        seed_opening_corpus(conn)

        with pytest.raises(InvalidMoveSyntaxError, match="invalid UCI move syntax"):
            apply_move_payload(
                conn,
                position_id=1,
                move_uci="e4",
                actor="test",
                require_suggested=True,
                write_audit=True,
            )
    finally:
        conn.close()


def test_apply_move_payload_rejects_unsuggested_move_in_strict_mode() -> None:
    conn = make_test_conn()
    try:
        seed_opening_corpus(conn)

        with pytest.raises(MoveNotSuggestedError, match="move not in suggested set"):
            apply_move_payload(
                conn,
                position_id=1,
                move_uci="b1c3",
                actor="test",
                require_suggested=True,
                write_audit=True,
            )
    finally:
        conn.close()


def test_apply_move_payload_accepts_unsuggested_move_when_override_enabled() -> None:
    conn = make_test_conn()
    try:
        seed_opening_corpus(conn)

        payload = apply_move_payload(
            conn,
            position_id=1,
            move_uci="b1c3",
            actor="test",
            require_suggested=False,
            write_audit=True,
        )

        assert payload["move_uci"] == "b1c3"
        assert payload["move_san"] == "Nc3"
        assert payload["side_to_move"] == "b"
        assert payload["ep_file"] == "-"
    finally:
        conn.close()


def test_apply_move_payload_rejects_illegal_move() -> None:
    conn = make_test_conn()
    try:
        seed_opening_corpus(conn)

        with pytest.raises(IllegalMoveError, match="illegal move"):
            apply_move_payload(
                conn,
                position_id=1,
                move_uci="e2e5",
                actor="test",
                require_suggested=False,
                write_audit=True,
            )
    finally:
        conn.close()