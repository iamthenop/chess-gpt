from __future__ import annotations

import io
import sqlite3
from pathlib import Path

from chessgpt.pgn.ingest import ingest_game
from chessgpt.pgn.replay import read_games


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


def test_ingest_game_inserts_expected_counts_for_short_game() -> None:
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
[TimeControl "300+0"]

1. e4 e5 2. Nf3 Nc6 1-0
"""
        )

        game_id = ingest_game(conn, parsed_game, "tests/sample.pgn")
        assert game_id == 1

        games_count = conn.execute("SELECT COUNT(*) AS n FROM games").fetchone()["n"]
        boards_count = conn.execute("SELECT COUNT(*) AS n FROM boards").fetchone()["n"]
        positions_count = conn.execute("SELECT COUNT(*) AS n FROM positions").fetchone()["n"]
        edges_count = conn.execute("SELECT COUNT(*) AS n FROM edges").fetchone()["n"]
        game_moves_count = conn.execute("SELECT COUNT(*) AS n FROM game_moves").fetchone()["n"]

        assert games_count == 1
        assert boards_count == 5          # initial + 4 resulting boards
        assert positions_count == 5       # initial + 4 resulting positions
        assert edges_count == 4           # one per ply
        assert game_moves_count == 4      # one per ply

        game_row = conn.execute(
            """
            SELECT white_player, black_player, result, time_control, pgn_source
            FROM games
            WHERE id = ?
            """,
            (game_id,),
        ).fetchone()

        assert game_row["white_player"] == "White"
        assert game_row["black_player"] == "Black"
        assert game_row["result"] == "1-0"
        assert game_row["time_control"] == "300+0"
        assert game_row["pgn_source"] == "tests/sample.pgn"

    finally:
        conn.close()


def test_ingest_game_aggregates_existing_edges_on_repeat_import() -> None:
    conn = make_test_conn()
    try:
        parsed_game = parse_single_game(
            """
[Event "Repeatable Game"]
[Site "Local"]
[Date "2026.03.15"]
[Round "1"]
[White "White"]
[Black "Black"]
[Result "1-0"]
[TimeControl "300+0"]

1. e4 e5 2. Nf3 Nc6 1-0
"""
        )

        ingest_game(conn, parsed_game, "tests/repeat.pgn")
        ingest_game(conn, parsed_game, "tests/repeat.pgn")

        games_count = conn.execute("SELECT COUNT(*) AS n FROM games").fetchone()["n"]
        boards_count = conn.execute("SELECT COUNT(*) AS n FROM boards").fetchone()["n"]
        positions_count = conn.execute("SELECT COUNT(*) AS n FROM positions").fetchone()["n"]
        edges_count = conn.execute("SELECT COUNT(*) AS n FROM edges").fetchone()["n"]
        game_moves_count = conn.execute("SELECT COUNT(*) AS n FROM game_moves").fetchone()["n"]

        # Provenance rows duplicate, graph rows should mostly reuse.
        assert games_count == 2
        assert boards_count == 5
        assert positions_count == 5
        assert edges_count == 4
        assert game_moves_count == 8

        edge = conn.execute(
            """
            SELECT frequency, white_wins, black_wins, draws, blitz_count, rapid_count, classical_count
            FROM edges
            WHERE move_uci = 'e2e4'
            """
        ).fetchone()

        assert edge["frequency"] == 2
        assert edge["white_wins"] == 2
        assert edge["black_wins"] == 0
        assert edge["draws"] == 0
        assert edge["blitz_count"] == 2
        assert edge["rapid_count"] == 0
        assert edge["classical_count"] == 0

    finally:
        conn.close()


def test_ingest_game_stores_ordered_game_path() -> None:
    conn = make_test_conn()
    try:
        parsed_game = parse_single_game(
            """
[Event "Path Test"]
[Site "Local"]
[Date "2026.03.15"]
[Round "1"]
[White "White"]
[Black "Black"]
[Result "0-1"]

1. d4 d5 2. c4 e6 0-1
"""
        )

        game_id = ingest_game(conn, parsed_game, "tests/path.pgn")

        rows = conn.execute(
            """
            SELECT gm.ply, e.move_san, e.move_uci
            FROM game_moves gm
            JOIN edges e ON e.id = gm.edge_id
            WHERE gm.game_id = ?
            ORDER BY gm.ply
            """,
            (game_id,),
        ).fetchall()

        assert [(row["ply"], row["move_san"], row["move_uci"]) for row in rows] == [
            (1, "d4", "d2d4"),
            (2, "d5", "d7d5"),
            (3, "c4", "c2c4"),
            (4, "e6", "e7e6"),
        ]

    finally:
        conn.close()


def test_ingest_game_preserves_position_metadata() -> None:
    conn = make_test_conn()
    try:
        parsed_game = parse_single_game(
            """
[Event "Metadata Test"]
[Site "Local"]
[Date "2026.03.15"]
[Round "1"]
[White "White"]
[Black "Black"]
[Result "1/2-1/2"]

1. e4 e5 2. Nf3 Nc6 1/2-1/2
"""
        )

        ingest_game(conn, parsed_game, "tests/meta.pgn")

        rows = conn.execute(
            """
            SELECT gm.ply, p.side_to_move, p.castling_rights, p.ep_file
            FROM game_moves gm
            JOIN positions p ON p.id = gm.position_id
            ORDER BY gm.ply
            """
        ).fetchall()

        # After 1.e4 -> black to move, ep on e-file
        assert rows[0]["ply"] == 1
        assert rows[0]["side_to_move"] == 1
        assert rows[0]["castling_rights"] == 0b1111
        assert rows[0]["ep_file"] == 4

        # After 1...e5 -> white to move, ep on e-file
        assert rows[1]["ply"] == 2
        assert rows[1]["side_to_move"] == 0
        assert rows[1]["castling_rights"] == 0b1111
        assert rows[1]["ep_file"] == 4

        # After 2.Nf3 -> black to move, no ep
        assert rows[2]["ply"] == 3
        assert rows[2]["side_to_move"] == 1
        assert rows[2]["castling_rights"] == 0b1111
        assert rows[2]["ep_file"] is None

        # After 2...Nc6 -> white to move, no ep
        assert rows[3]["ply"] == 4
        assert rows[3]["side_to_move"] == 0
        assert rows[3]["castling_rights"] == 0b1111
        assert rows[3]["ep_file"] is None

    finally:
        conn.close()