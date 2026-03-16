#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from chessgpt.db.connection import connect
from chessgpt.query.suggest import suggest_moves_for_position_id


def format_rate(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.3f}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Suggest moves for a stored position")
    parser.add_argument("position_id", type=int, help="Position ID to query")
    parser.add_argument(
        "--db",
        default="data/db/chessgpt.sqlite3",
        help="Path to SQLite database file",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of candidate moves to return",
    )
    parser.add_argument(
        "--min-frequency",
        type=int,
        default=1,
        help="Minimum edge frequency required to include a move",
    )
    parser.add_argument(
        "--format",
        choices=("text", "llm"),
        default="text",
        help="Output format",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    db_path = (repo_root / args.db).resolve() if not Path(args.db).is_absolute() else Path(args.db)

    conn = connect(db_path)
    try:
        moves = suggest_moves_for_position_id(conn, args.position_id, limit=max(args.limit, 1000))
    finally:
        conn.close()

    moves = [move for move in moves if move.frequency >= args.min_frequency][: args.limit]

    if args.format == "llm":
        print(f"position_id:{args.position_id}")
        print(f"min_frequency:{args.min_frequency}")
        print("candidate_moves:")
        for move in moves:
            print(
                f"- move_uci:{move.move_uci} "
                f"move_san:{move.move_san or '-'} "
                f"frequency:{move.frequency} "
                f"white_win_rate:{format_rate(move.white_win_rate)} "
                f"draw_rate:{format_rate(move.draw_rate)} "
                f"black_win_rate:{format_rate(move.black_win_rate)}"
            )
        return

    print(f"position_id:{args.position_id}")
    print(f"min_frequency:{args.min_frequency}")
    if not moves:
        print("no candidate moves found")
        return

    for i, move in enumerate(moves, start=1):
        print(
            f"{i:>2}. "
            f"{(move.move_san or '-'):6} "
            f"({move.move_uci})  "
            f"freq={move.frequency:<5} "
            f"W={format_rate(move.white_win_rate)} "
            f"D={format_rate(move.draw_rate)} "
            f"B={format_rate(move.black_win_rate)}"
        )


if __name__ == "__main__":
    main()