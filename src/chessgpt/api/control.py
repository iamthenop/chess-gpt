from __future__ import annotations

import sqlite3
from pathlib import Path

from chessgpt.control.apply import validate_and_apply_move
from chessgpt.db.connection import connect
from chessgpt.encoding.board_codec import decode_board_to_rows


def _format_side_to_move(value: int) -> str:
    return "w" if value == 0 else "b"


def _format_castling(mask: int) -> str:
    return f"{mask:04b}"


def _format_ep_file(value: int | None) -> str:
    if value is None:
        return "-"
    return chr(ord("a") + value)


def applied_move_to_payload(applied) -> dict:
    return {
        "format_version": 1,
        "source_position_id": applied.source_position_id,
        "move_uci": applied.move_uci,
        "move_san": applied.move_san,
        "resulting_position_id": applied.resulting_position_id,
        "side_to_move": _format_side_to_move(applied.side_to_move),
        "castling": _format_castling(applied.castling_rights),
        "ep_file": _format_ep_file(applied.ep_file),
        "board_rows": decode_board_to_rows(applied.resulting_board_blob),
    }


def apply_move_payload(
    conn: sqlite3.Connection,
    *,
    position_id: int,
    move_uci: str,
    actor: str = "llm",
    require_suggested: bool = True,
    write_audit: bool = True,
) -> dict:
    applied = validate_and_apply_move(
        conn,
        position_id=position_id,
        move_uci=move_uci,
        actor=actor,
        require_suggested=require_suggested,
        write_audit=write_audit,
    )
    return applied_move_to_payload(applied)


def apply_move_payload_from_db(
    db_path: str | Path,
    *,
    position_id: int,
    move_uci: str,
    actor: str = "llm",
    require_suggested: bool = True,
    write_audit: bool = True,
    commit: bool = True,
) -> dict:
    conn = connect(db_path)
    try:
        payload = apply_move_payload(
            conn,
            position_id=position_id,
            move_uci=move_uci,
            actor=actor,
            require_suggested=require_suggested,
            write_audit=write_audit,
        )
        if commit:
            conn.commit()
        return payload
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()