from __future__ import annotations

import io
import sqlite3
from pathlib import Path

import pytest

from chessgpt.control.apply import (
    AppliedMove,
    load_position_state,
    validate_and_apply_move,
)
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


def count_audit_rows(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COUNT(*) AS n FROM decision_audit").fetchone()
    return int(row["n"])


def test_load_position_state_returns_start_position() -> None:
    conn = make_test_conn()
    try:
        seed_opening_corpus(conn)
        state = load_position_state(conn, 1)

        assert state.position_id == 1
        assert state.side_to_move == 0
        assert state.castling_rights == 0b1111
        assert state.ep_file is None
        assert isinstance(state.board_blob, bytes)
        assert len(state.board_blob) == 32
    finally:
        conn.close()


def test_validate_and_apply_move_accepts_suggested_legal_move() -> None:
    conn = make_test_conn()
    try:
        seed_opening_corpus(conn)

        before = count_audit_rows(conn)
        applied = validate_and_apply_move(
            conn,
            position_id=1,
            move_uci="e2e4",
            actor="test",
            require_suggested=True,
            write_audit=True,
        )

        assert isinstance(applied, AppliedMove)
        assert applied.source_position_id == 1
        assert applied.move_uci == "e2e4"
        assert applied.move_san == "e4"
        assert applied.side_to_move == 1
        assert applied.castling_rights == 0b1111
        assert applied.ep_file == 4
        assert applied.resulting_position_id is not None

        after = count_audit_rows(conn)
        assert after == before + 1

        audit = conn.execute(
            """
            SELECT accepted, reason, actor, require_suggested, in_suggestions, resulting_position_id
            FROM decision_audit
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()

        assert audit["accepted"] == 1
        assert audit["reason"] == "accepted"
        assert audit["actor"] == "test"
        assert audit["require_suggested"] == 1
        assert audit["in_suggestions"] == 1
        assert audit["resulting_position_id"] == applied.resulting_position_id
    finally:
        conn.close()


def test_validate_and_apply_move_rejects_invalid_uci_syntax() -> None:
    conn = make_test_conn()
    try:
        seed_opening_corpus(conn)

        with pytest.raises(ValueError, match="invalid UCI move syntax"):
            validate_and_apply_move(
                conn,
                position_id=1,
                move_uci="e4",
                actor="test",
                require_suggested=True,
                write_audit=True,
            )

        audit = conn.execute(
            """
            SELECT accepted, reason, in_suggestions
            FROM decision_audit
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()

        assert audit["accepted"] == 0
        assert audit["reason"] == "invalid_uci_syntax"
        assert audit["in_suggestions"] is None
    finally:
        conn.close()


def test_validate_and_apply_move_rejects_legal_but_unsuggested_move_when_required() -> None:
    conn = make_test_conn()
    try:
        seed_opening_corpus(conn)

        with pytest.raises(ValueError, match="move not in suggested set"):
            validate_and_apply_move(
                conn,
                position_id=1,
                move_uci="b1c3",
                actor="test",
                require_suggested=True,
                write_audit=True,
            )

        audit = conn.execute(
            """
            SELECT accepted, reason, in_suggestions
            FROM decision_audit
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()

        assert audit["accepted"] == 0
        assert audit["reason"] == "move_not_in_suggestions"
        assert audit["in_suggestions"] == 0
    finally:
        conn.close()


def test_validate_and_apply_move_accepts_unsuggested_move_when_override_enabled() -> None:
    conn = make_test_conn()
    try:
        seed_opening_corpus(conn)

        applied = validate_and_apply_move(
            conn,
            position_id=1,
            move_uci="b1c3",
            actor="test",
            require_suggested=False,
            write_audit=True,
        )

        assert applied.move_uci == "b1c3"
        assert applied.move_san == "Nc3"
        assert applied.side_to_move == 1
        assert applied.ep_file is None

        audit = conn.execute(
            """
            SELECT accepted, reason, require_suggested, in_suggestions
            FROM decision_audit
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()

        assert audit["accepted"] == 1
        assert audit["reason"] == "accepted"
        assert audit["require_suggested"] == 0
        assert audit["in_suggestions"] == 0
    finally:
        conn.close()


def test_validate_and_apply_move_rejects_illegal_move() -> None:
    conn = make_test_conn()
    try:
        seed_opening_corpus(conn)

        with pytest.raises(ValueError, match="illegal move"):
            validate_and_apply_move(
                conn,
                position_id=1,
                move_uci="e2e5",
                actor="test",
                require_suggested=False,
                write_audit=True,
            )

        audit = conn.execute(
            """
            SELECT accepted, reason, in_suggestions
            FROM decision_audit
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()

        assert audit["accepted"] == 0
        assert audit["reason"] == "illegal_move"
        assert audit["in_suggestions"] == 0
    finally:
        conn.close()


def test_validate_and_apply_move_can_skip_audit() -> None:
    conn = make_test_conn()
    try:
        seed_opening_corpus(conn)

        before = count_audit_rows(conn)
        applied = validate_and_apply_move(
            conn,
            position_id=1,
            move_uci="e2e4",
            actor="test",
            require_suggested=True,
            write_audit=False,
        )
        after = count_audit_rows(conn)

        assert applied.move_uci == "e2e4"
        assert after == before
    finally:
        conn.close()
