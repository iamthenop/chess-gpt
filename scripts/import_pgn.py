#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from chessgpt.pgn.ingest import ingest_pgn_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Import PGN games into the chess-gpt database")
    parser.add_argument("pgn", help="Path to PGN file")
    parser.add_argument(
        "--db",
        default="data/db/chessgpt.sqlite3",
        help="Path to SQLite database file",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    pgn_path = (repo_root / args.pgn).resolve() if not Path(args.pgn).is_absolute() else Path(args.pgn)
    db_path = (repo_root / args.db).resolve() if not Path(args.db).is_absolute() else Path(args.db)

    count = ingest_pgn_path(db_path, pgn_path)
    print(f"Imported {count} game(s) from {pgn_path} into {db_path}")


if __name__ == "__main__":
    main()
