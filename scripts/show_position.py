#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from chessgpt.db.connection import connect
from chessgpt.encoding.render import render_llm_board, render_text_board


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


def format_side_to_move(value: int) -> str:
    return "w" if value == 0 else "b"


def format_castling(mask: int) -> str:
    return f"{mask:04b}"


def format_ep_file(value: int | None) -> str:
    if value is None:
        return "-"
    return chr(ord("a") + value)


def main() -> None:
    parser = argparse.ArgumentParser(description="Show a stored chess position")
    parser.add_argument("position_id", type=int, help="Position ID to display")
    parser.add_argument(
        "--db",
        default="data/db/chessgpt.sqlite3",
        help="Path to SQLite database file",
    )
    parser.add_argument(
        "--format",
        choices=("llm", "text"),
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
        row = load_position(conn, args.position_id)

        board_blob = row["board_blob"]
        side_to_move = format_side_to_move(int(row["side_to_move"]))
        castling = format_castling(int(row["castling_rights"]))
        ep_file = format_ep_file(row["ep_file"])

        if args.format == "llm":
            output = render_llm_board(
                board_blob,
                side_to_move=side_to_move,
                castling=castling,
                ep_file=ep_file,
            )
        else:
            header = [
                f"position_id:{int(row['position_id'])}",
                f"side_to_move:{side_to_move}",
                f"castling:{castling}",
                f"ep_file:{ep_file}",
                "",
            ]
            board_text = render_text_board(
                board_blob,
                piece_set=args.piece_set,
                theme=args.theme,
                show_coordinates=not args.no_coordinates,
                white_at_bottom=not args.black_bottom,
            )
            output = "\n".join(header) + board_text

        print(output)

    finally:
        conn.close()


if __name__ == "__main__":
    main()