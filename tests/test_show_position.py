from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from chessgpt.pgn.ingest import ingest_pgn_path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def seed_db(db_path: Path, pgn_path: Path) -> None:
    ingest_pgn_path(db_path, pgn_path)


def run_show_position(*args: str) -> subprocess.CompletedProcess[str]:
    root = repo_root()
    env = {"PYTHONPATH": "src", **dict()}
    # Keep inherited environment minimal but usable.
    import os

    merged_env = os.environ.copy()
    merged_env.update(env)

    return subprocess.run(
        [sys.executable, "scripts/show_position.py", *args],
        cwd=root,
        env=merged_env,
        text=True,
        capture_output=True,
        check=True,
    )


def test_show_position_llm_output(tmp_path: Path) -> None:
    root = repo_root()
    db_path = tmp_path / "test.sqlite3"
    pgn_path = root / "data" / "samples" / "sample_game.pgn"

    # Initialize schema
    subprocess.run(
        [sys.executable, "scripts/init_db.py", "--db", str(db_path)],
        cwd=root,
        env={**__import__("os").environ, "PYTHONPATH": "src"},
        text=True,
        capture_output=True,
        check=True,
    )
    seed_db(db_path, pgn_path)

    result = run_show_position("1", "--db", str(db_path), "--format", "llm")
    assert result.stdout.strip() == "\n".join(
        [
            "side_to_move:w",
            "castling:1111",
            "ep_file:-",
            "board:",
            "42356324",
            "11111111",
            "00000000",
            "00000000",
            "00000000",
            "00000000",
            "FFFFFFFF",
            "CEDBADEC",
        ]
    )


def test_show_position_json_output(tmp_path: Path) -> None:
    root = repo_root()
    db_path = tmp_path / "test.sqlite3"
    pgn_path = root / "data" / "samples" / "sample_game.pgn"

    subprocess.run(
        [sys.executable, "scripts/init_db.py", "--db", str(db_path)],
        cwd=root,
        env={**__import__("os").environ, "PYTHONPATH": "src"},
        text=True,
        capture_output=True,
        check=True,
    )
    seed_db(db_path, pgn_path)

    result = run_show_position("1", "--db", str(db_path), "--format", "json")
    payload = json.loads(result.stdout)

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


def test_show_position_text_output_contains_expected_header(tmp_path: Path) -> None:
    root = repo_root()
    db_path = tmp_path / "test.sqlite3"
    pgn_path = root / "data" / "samples" / "sample_game.pgn"

    subprocess.run(
        [sys.executable, "scripts/init_db.py", "--db", str(db_path)],
        cwd=root,
        env={**__import__("os").environ, "PYTHONPATH": "src"},
        text=True,
        capture_output=True,
        check=True,
    )
    seed_db(db_path, pgn_path)

    result = run_show_position(
        "1",
        "--db",
        str(db_path),
        "--piece-set",
        "ascii",
        "--theme",
        "plain",
    )
    lines = result.stdout.splitlines()

    assert lines[0] == "position_id:1"
    assert lines[1] == "side_to_move:w"
    assert lines[2] == "castling:1111"
    assert lines[3] == "ep_file:-"
    assert "8 | r  | n  | b  | q  | k  | b  | n  | r  |" in result.stdout
    assert "1 | R  | N  | B  | Q  | K  | B  | N  | R  |" in result.stdout


def test_show_position_black_bottom_rotates_board(tmp_path: Path) -> None:
    root = repo_root()
    db_path = tmp_path / "test.sqlite3"
    pgn_path = root / "data" / "samples" / "sample_game.pgn"

    subprocess.run(
        [sys.executable, "scripts/init_db.py", "--db", str(db_path)],
        cwd=root,
        env={**__import__("os").environ, "PYTHONPATH": "src"},
        text=True,
        capture_output=True,
        check=True,
    )
    seed_db(db_path, pgn_path)

    result = run_show_position(
        "1",
        "--db",
        str(db_path),
        "--piece-set",
        "ascii",
        "--theme",
        "plain",
        "--black-bottom",
    )

    lines = result.stdout.splitlines()
    assert "1 | R  | N  | B  | K  | Q  | B  | N  | R  |" in lines
    assert lines[-1] == "    h   g   f   e   d   c   b   a"