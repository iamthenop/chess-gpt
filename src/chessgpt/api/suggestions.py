from __future__ import annotations

import sqlite3
from pathlib import Path

from chessgpt.db.connection import connect
from chessgpt.query.suggest import suggest_moves_for_position_id


def suggestion_to_payload(move) -> dict:
    return {
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


def get_suggestions_payload(
    conn: sqlite3.Connection,
    position_id: int,
    *,
    min_frequency: int = 1,
    limit: int = 10,
) -> dict:
    moves = suggest_moves_for_position_id(conn, position_id, limit=max(limit, 1000))
    moves = [move for move in moves if move.frequency >= min_frequency][:limit]

    return {
        "format_version": 1,
        "position_id": position_id,
        "min_frequency": min_frequency,
        "candidate_moves": [suggestion_to_payload(move) for move in moves],
    }


def get_suggestions_payload_from_db(
    db_path: str | Path,
    position_id: int,
    *,
    min_frequency: int = 1,
    limit: int = 10,
) -> dict:
    conn = connect(db_path)
    try:
        return get_suggestions_payload(
            conn,
            position_id,
            min_frequency=min_frequency,
            limit=limit,
        )
    finally:
        conn.close()