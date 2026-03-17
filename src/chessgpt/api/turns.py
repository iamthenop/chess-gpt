from __future__ import annotations

import sqlite3
from pathlib import Path

from chessgpt.api.positions import get_position_payload
from chessgpt.api.suggestions import get_suggestions_payload
from chessgpt.db.connection import connect
from chessgpt.policy.candidates import build_candidate_set


def get_turn_payload(
    conn: sqlite3.Connection,
    position_id: int,
    *,
    min_frequency: int = 5,
    limit: int = 10,
    strict_mode: bool = True,
) -> dict:
    position = get_position_payload(conn, position_id)
    suggestions = get_suggestions_payload(
        conn,
        position_id,
        min_frequency=min_frequency,
        limit=limit,
    )
    candidate_set = build_candidate_set(
        conn,
        position_id,
        min_frequency=min_frequency,
        limit=limit,
    )

    return {
        "format_version": 1,
        "position": position,
        "candidate_moves": suggestions["candidate_moves"],
        "candidate_policy": {
            "candidate_set_id": candidate_set.candidate_set_id,
            "candidate_binding_required": candidate_set.binding_required,
            "fallback_policy": candidate_set.fallback_policy,
            "candidate_moves": list(candidate_set.moves),
        },
        "instructions": {
            "task": "Choose exactly one move.",
            "output_format": "Return exactly one UCI move and nothing else.",
            "strict_mode": strict_mode,
        },
    }


def get_turn_payload_from_db(
    db_path: str | Path,
    position_id: int,
    *,
    min_frequency: int = 5,
    limit: int = 10,
    strict_mode: bool = True,
) -> dict:
    conn = connect(db_path)
    try:
        return get_turn_payload(
            conn,
            position_id,
            min_frequency=min_frequency,
            limit=limit,
            strict_mode=strict_mode,
        )
    finally:
        conn.close()