#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from chessgpt.control.apply import validate_and_apply_move
from chessgpt.db.connection import connect
from chessgpt.encoding.board_codec import decode_board_to_rows
from chessgpt.query.suggest import suggest_moves_for_position_id

UCI_MOVE_RE = re.compile(r"^[a-h][1-8][a-h][1-8][qrbn]?$")


def format_side_to_move(value: int) -> str:
    return "w" if value == 0 else "b"


def format_castling(mask: int) -> str:
    return f"{mask:04b}"


def format_ep_file(value: int | None) -> str:
    if value is None:
        return "-"
    return chr(ord("a") + value)


def load_position(conn, position_id: int):
    row = conn.execute(
        """
        SELECT
            p.id AS position_id,
            b.board_blob,
            p.side_to_move,
            p.castling_rights,
            p.ep_file
        FROM positions p
        JOIN boards b
          ON b.id = p.board_id
        WHERE p.id = ?
        """,
        (position_id,),
    ).fetchone()

    if row is None:
        raise ValueError(f"position_id not found: {position_id}")

    return row


def build_prompt_payload(conn, position_id: int, min_frequency: int, limit: int) -> dict:
    row = load_position(conn, position_id)
    moves = suggest_moves_for_position_id(conn, position_id, limit=max(limit, 1000))
    moves = [m for m in moves if m.frequency >= min_frequency][:limit]

    return {
        "format_version": 1,
        "position": {
            "position_id": int(row["position_id"]),
            "side_to_move": format_side_to_move(int(row["side_to_move"])),
            "castling": format_castling(int(row["castling_rights"])),
            "ep_file": format_ep_file(row["ep_file"]),
            "board_rows": decode_board_to_rows(row["board_blob"]),
        },
        "candidate_moves": [
            {
                "move_uci": move.move_uci,
                "move_san": move.move_san,
                "frequency": move.frequency,
                "white_wins": move.white_wins,
                "black_wins": move.black_wins,
                "draws": move.draws,
                "white_win_rate": move.white_win_rate,
                "draw_rate": move.draw_rate,
                "black_win_rate": move.black_win_rate,
            }
            for move in moves
        ],
        "instructions": {
            "task": "Choose exactly one move.",
            "output_format": "Return exactly one UCI move and nothing else.",
            "strict_mode": True,
        },
    }


def parse_uci_only(text: str) -> str:
    stripped = text.strip()
    if not UCI_MOVE_RE.fullmatch(stripped):
        raise ValueError(
            "LLM response must be exactly one UCI move and nothing else. "
            f"Got: {text!r}"
        )
    return stripped


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare and apply one LLM chess turn")
    parser.add_argument("position_id", type=int, help="Source position ID")
    parser.add_argument(
        "--db",
        default="data/db/chessgpt.sqlite3",
        help="Path to SQLite database file",
    )
    parser.add_argument(
        "--min-frequency",
        type=int,
        default=5,
        help="Minimum suggestion frequency to include in the prompt payload",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of candidate moves to include in the prompt payload",
    )
    parser.add_argument(
        "--mode",
        choices=("prompt", "apply"),
        default="prompt",
        help="prompt = emit payload only, apply = read one UCI move from stdin and apply it",
    )
    parser.add_argument(
        "--actor",
        default="llm",
        help="Actor label for audit logging in apply mode",
    )
    parser.add_argument(
        "--allow-unsuggested",
        action="store_true",
        help="Allow legal moves not present in the suggested set",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    db_path = (repo_root / args.db).resolve() if not Path(args.db).is_absolute() else Path(args.db)

    conn = connect(db_path)
    try:
        if args.mode == "prompt":
            payload = build_prompt_payload(conn, args.position_id, args.min_frequency, args.limit)
            print(json.dumps(payload, indent=2))
            return

        llm_response = sys.stdin.read()
        move_uci = parse_uci_only(llm_response)

        applied = validate_and_apply_move(
            conn,
            position_id=args.position_id,
            move_uci=move_uci,
            actor=args.actor,
            require_suggested=not args.allow_unsuggested,
            write_audit=True,
        )
        conn.commit()

        result_payload = {
            "format_version": 1,
            "source_position_id": applied.source_position_id,
            "move_uci": applied.move_uci,
            "move_san": applied.move_san,
            "resulting_position_id": applied.resulting_position_id,
            "side_to_move": format_side_to_move(applied.side_to_move),
            "castling": format_castling(applied.castling_rights),
            "ep_file": format_ep_file(applied.ep_file),
            "board_rows": decode_board_to_rows(applied.resulting_board_blob),
        }
        print(json.dumps(result_payload, indent=2))

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()