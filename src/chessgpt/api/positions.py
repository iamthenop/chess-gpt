from __future__ import annotations

import sqlite3
from pathlib import Path

from chessgpt.db.connection import connect
from chessgpt.errors import PositionNotFoundError
from chessgpt.encoding.board_codec import decode_board_to_rows


def _format_side_to_move(value: int) -> str:
    return "w" if value == 0 else "b"


def _format_castling(mask: int) -> str:
    return f"{mask:04b}"


def _format_ep_file(value: int | None) -> str:
    if value is None:
        return "-"
    return chr(ord("a") + value)


def load_position_row(conn: sqlite3.Connection, position_id: int) -> sqlite3.Row:
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
        raise PositionNotFoundError(f"position_id not found: {position_id}")

    return row


def get_position_payload(conn: sqlite3.Connection, position_id: int) -> dict:
    row = load_position_row(conn, position_id)

    board_blob = row["board_blob"]
    return {
        "format_version": 1,
        "position_id": int(row["position_id"]),
        "side_to_move": _format_side_to_move(int(row["side_to_move"])),
        "castling": _format_castling(int(row["castling_rights"])),
        "ep_file": _format_ep_file(row["ep_file"]),
        "board_rows": decode_board_to_rows(board_blob),
    }


def get_position_payload_from_db(db_path: str | Path, position_id: int) -> dict:
    conn = connect(db_path)
    try:
        return get_position_payload(conn, position_id)
    finally:
        conn.close()