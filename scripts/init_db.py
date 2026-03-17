#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from chessgpt.db.connection import connect


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize the chess-gpt database schema")
    parser.add_argument(
        "--db",
        default="data/db/chessgpt.sqlite3",
        help="Path to SQLite database file",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    db_path = (repo_root / args.db).resolve() if not Path(args.db).is_absolute() else Path(args.db)
    schema_dir = repo_root / "schema"

    conn = connect(db_path)
    try:
        for schema_file in sorted(schema_dir.glob("*.sql")):
            sql = schema_file.read_text(encoding="utf-8")
            conn.executescript(sql)
        conn.commit()
    finally:
        conn.close()

    print(f"Initialized database: {db_path}")


if __name__ == "__main__":
    main()