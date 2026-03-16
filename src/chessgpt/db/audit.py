from __future__ import annotations

import sqlite3


def record_decision_audit(
    conn: sqlite3.Connection,
    *,
    position_id: int,
    chosen_move_uci: str,
    chosen_move_san: str | None,
    accepted: int,
    reason: str,
    actor: str,
    require_suggested: bool,
    in_suggestions: int | None,
    resulting_position_id: int | None,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO decision_audit (
            position_id,
            chosen_move_uci,
            chosen_move_san,
            accepted,
            reason,
            actor,
            require_suggested,
            in_suggestions,
            resulting_position_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            position_id,
            chosen_move_uci,
            chosen_move_san,
            accepted,
            reason,
            actor,
            1 if require_suggested else 0,
            in_suggestions,
            resulting_position_id,
        ),
    )
    return int(cur.lastrowid)
