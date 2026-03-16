from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from chessgpt.db.connection import connect


@dataclass(frozen=True)
class SuggestedMove:
    move_uci: str
    move_san: str | None
    frequency: int
    white_wins: int
    black_wins: int
    draws: int
    white_win_rate: float | None
    black_win_rate: float | None
    draw_rate: float | None


def _rates(frequency: int, white_wins: int, black_wins: int, draws: int) -> tuple[float | None, float | None, float | None]:
    if frequency <= 0:
        return None, None, None

    return (
        white_wins / frequency,
        black_wins / frequency,
        draws / frequency,
    )


def find_position_id(
    conn: sqlite3.Connection,
    *,
    board_blob: bytes,
    side_to_move: int,
    castling_rights: int,
    ep_file: int | None,
) -> int | None:
    row = conn.execute(
        """
        SELECT p.id
        FROM positions p
        JOIN boards b
          ON b.id = p.board_id
        WHERE b.board_blob = ?
          AND p.side_to_move = ?
          AND p.castling_rights = ?
          AND (
                (p.ep_file IS NULL AND ? IS NULL)
                OR p.ep_file = ?
          )
        """,
        (board_blob, side_to_move, castling_rights, ep_file, ep_file),
    ).fetchone()

    if row is None:
        return None
    return int(row["id"])


def suggest_moves_for_position_id(
    conn: sqlite3.Connection,
    position_id: int,
    *,
    limit: int = 10,
) -> list[SuggestedMove]:
    rows = conn.execute(
        """
        SELECT
            move_uci,
            move_san,
            frequency,
            white_wins,
            black_wins,
            draws
        FROM edges
        WHERE from_position_id = ?
        ORDER BY frequency DESC,
                 white_wins DESC,
                 black_wins DESC,
                 draws DESC,
                 move_uci ASC
        LIMIT ?
        """,
        (position_id, limit),
    ).fetchall()

    suggestions: list[SuggestedMove] = []
    for row in rows:
        frequency = int(row["frequency"])
        white_wins = int(row["white_wins"])
        black_wins = int(row["black_wins"])
        draws = int(row["draws"])
        white_rate, black_rate, draw_rate = _rates(
            frequency,
            white_wins,
            black_wins,
            draws,
        )

        suggestions.append(
            SuggestedMove(
                move_uci=str(row["move_uci"]),
                move_san=str(row["move_san"]) if row["move_san"] is not None else None,
                frequency=frequency,
                white_wins=white_wins,
                black_wins=black_wins,
                draws=draws,
                white_win_rate=white_rate,
                black_win_rate=black_rate,
                draw_rate=draw_rate,
            )
        )

    return suggestions


def suggest_moves(
    conn: sqlite3.Connection,
    *,
    board_blob: bytes,
    side_to_move: int,
    castling_rights: int,
    ep_file: int | None,
    limit: int = 10,
) -> list[SuggestedMove]:
    position_id = find_position_id(
        conn,
        board_blob=board_blob,
        side_to_move=side_to_move,
        castling_rights=castling_rights,
        ep_file=ep_file,
    )

    if position_id is None:
        return []

    return suggest_moves_for_position_id(conn, position_id, limit=limit)


def suggest_moves_from_db(
    db_path: str,
    *,
    board_blob: bytes,
    side_to_move: int,
    castling_rights: int,
    ep_file: int | None,
    limit: int = 10,
) -> list[SuggestedMove]:
    conn = connect(db_path)
    try:
        return suggest_moves(
            conn,
            board_blob=board_blob,
            side_to_move=side_to_move,
            castling_rights=castling_rights,
            ep_file=ep_file,
            limit=limit,
        )
    finally:
        conn.close()