#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from chessgpt.control.apply import validate_and_apply_move
from chessgpt.db.connection import connect
from chessgpt.encoding.board_codec import decode_board_to_rows
from chessgpt.encoding.render import render_llm_board, render_text_board


def format_side_to_move(value: int) -> str:
    return "w" if value == 0 else "b"


def format_castling(mask: int) -> str:
    return f"{mask:04b}"


def format_ep_file(value: int | None) -> str:
    if value is None:
        return "-"
    return chr(ord("a") + value)


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate and apply a move to a stored position")
    parser.add_argument("position_id", type=int, help="Source position ID")
    parser.add_argument("move_uci", help="Candidate move in UCI format, e.g. e2e4")
    parser.add_argument(
        "--db",
        default="data/db/chessgpt.sqlite3",
        help="Path to SQLite database file",
    )
    parser.add_argument(
        "--actor",
        default="human",
        help="Actor label for audit logging",
    )
    parser.add_argument(
        "--allow-unsuggested",
        action="store_true",
        help="Allow legal moves not present in the suggestion set",
    )
    parser.add_argument(
        "--format",
        choices=("text", "llm", "json"),
        default="text",
        help="Output format",
    )
    parser.add_argument(
        "--piece-set",
        choices=("unicode", "ascii"),
        default="unicode",
        help="Piece set for text rendering",
    )
    parser.add_argument(
        "--theme",
        choices=("dark", "light", "plain"),
        default="dark",
        help="Theme for text rendering",
    )
    parser.add_argument(
        "--black-bottom",
        action="store_true",
        help="Render with Black at the bottom in text mode",
    )
    parser.add_argument(
        "--no-coordinates",
        action="store_true",
        help="Hide coordinates in text mode",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    db_path = (repo_root / args.db).resolve() if not Path(args.db).is_absolute() else Path(args.db)

    conn = connect(db_path)
    try:
        applied = validate_and_apply_move(
            conn,
            position_id=args.position_id,
            move_uci=args.move_uci,
            actor=args.actor,
            require_suggested=not args.allow_unsuggested,
            write_audit=True,
        )
        conn.commit()

        side_to_move = format_side_to_move(applied.side_to_move)
        castling = format_castling(applied.castling_rights)
        ep_file = format_ep_file(applied.ep_file)

        if args.format == "json":
            payload = {
                "format_version": 1,
                "source_position_id": applied.source_position_id,
                "move_uci": applied.move_uci,
                "move_san": applied.move_san,
                "resulting_position_id": applied.resulting_position_id,
                "side_to_move": side_to_move,
                "castling": castling,
                "ep_file": ep_file,
                "board_rows": decode_board_to_rows(applied.resulting_board_blob),
            }
            print(json.dumps(payload, indent=2))
            return

        if args.format == "llm":
            print(f"source_position_id:{applied.source_position_id}")
            print(f"move_uci:{applied.move_uci}")
            print(f"move_san:{applied.move_san}")
            print(f"resulting_position_id:{applied.resulting_position_id or '-'}")
            print(
                render_llm_board(
                    applied.resulting_board_blob,
                    side_to_move=side_to_move,
                    castling=castling,
                    ep_file=ep_file,
                )
            )
            return

        header = [
            f"source_position_id:{applied.source_position_id}",
            f"move_uci:{applied.move_uci}",
            f"move_san:{applied.move_san}",
            f"resulting_position_id:{applied.resulting_position_id or '-'}",
            f"side_to_move:{side_to_move}",
            f"castling:{castling}",
            f"ep_file:{ep_file}",
            "",
        ]
        board_text = render_text_board(
            applied.resulting_board_blob,
            piece_set=args.piece_set,
            theme=args.theme,
            show_coordinates=not args.no_coordinates,
            white_at_bottom=not args.black_bottom,
        )
        print("\n".join(header) + board_text)

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()