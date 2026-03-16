"""
CLI entry points for chess-gpt.

This module is intentionally minimal for now.
Scripts in /scripts remain the primary user-facing interface.

Future work may consolidate script entry points here.
"""


def main() -> None:
    raise SystemExit(
        "chess-gpt CLI is not wired yet. "
        "Use scripts/init_db.py, scripts/import_pgn.py, "
        "scripts/show_position.py, or scripts/suggest_move.py."
    )
