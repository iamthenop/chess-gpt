from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass

import chess

from chessgpt.bridge.python_chess import (
    board_blob_to_board,
    board_to_position_parts,
)
from chessgpt.db.audit import record_decision_audit
from chessgpt.errors import (
    IllegalMoveError,
    InvalidMoveSyntaxError,
    MoveNotSuggestedError,
    PositionNotFoundError,
)
from chessgpt.query.suggest import suggest_moves_for_position_id

UCI_MOVE_RE = re.compile(r"^[a-h][1-8][a-h][1-8][qrbn]?$")


@dataclass(frozen=True)
class PositionState:
    position_id: int
    board_blob: bytes
    side_to_move: int          # 0 = white, 1 = black
    castling_rights: int       # 1 = WL, 2 = WS, 4 = BL, 8 = BS
    ep_file: int | None        # 0..7 or None


@dataclass(frozen=True)
class AppliedMove:
    source_position_id: int
    move_uci: str
    move_san: str
    resulting_board_blob: bytes
    side_to_move: int
    castling_rights: int
    ep_file: int | None
    resulting_position_id: int | None


def load_position_state(conn: sqlite3.Connection, position_id: int) -> PositionState:
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

    return PositionState(
        position_id=int(row["position_id"]),
        board_blob=row["board_blob"],
        side_to_move=int(row["side_to_move"]),
        castling_rights=int(row["castling_rights"]),
        ep_file=row["ep_file"],
    )


def _find_existing_position_id(
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


def validate_and_apply_move(
    conn: sqlite3.Connection,
    *,
    position_id: int,
    move_uci: str,
    actor: str = "llm",
    require_suggested: bool = True,
    write_audit: bool = True,
) -> AppliedMove:
    state = load_position_state(conn, position_id)

    move_uci = move_uci.strip().lower()
    if not UCI_MOVE_RE.fullmatch(move_uci):
        if write_audit:
            record_decision_audit(
                conn,
                position_id=position_id,
                chosen_move_uci=move_uci,
                chosen_move_san=None,
                accepted=0,
                reason="invalid_uci_syntax",
                actor=actor,
                require_suggested=require_suggested,
                in_suggestions=None,
                resulting_position_id=None,
            )
        raise InvalidMoveSyntaxError(f"invalid UCI move syntax: {move_uci}")

    suggested = suggest_moves_for_position_id(conn, position_id, limit=1000)
    suggested_uci = {m.move_uci for m in suggested}
    in_suggestions = move_uci in suggested_uci

    if require_suggested and not in_suggestions:
        if write_audit:
            record_decision_audit(
                conn,
                position_id=position_id,
                chosen_move_uci=move_uci,
                chosen_move_san=None,
                accepted=0,
                reason="move_not_in_suggestions",
                actor=actor,
                require_suggested=require_suggested,
                in_suggestions=0,
                resulting_position_id=None,
            )
        raise MoveNotSuggestedError(f"move not in suggested set: {move_uci}")

    board = board_blob_to_board(
        state.board_blob,
        side_to_move=state.side_to_move,
        castling_rights=state.castling_rights,
        ep_file_value=state.ep_file,
    )

    move = chess.Move.from_uci(move_uci)
    if move not in board.legal_moves:
        if write_audit:
            record_decision_audit(
                conn,
                position_id=position_id,
                chosen_move_uci=move_uci,
                chosen_move_san=None,
                accepted=0,
                reason="illegal_move",
                actor=actor,
                require_suggested=require_suggested,
                in_suggestions=1 if in_suggestions else 0,
                resulting_position_id=None,
            )
        raise IllegalMoveError(f"illegal move for position {position_id}: {move_uci}")

    move_san = board.san(move)
    board.push(move)

    resulting_board_blob, resulting_side, resulting_castling, resulting_ep = board_to_position_parts(board)

    resulting_position_id = _find_existing_position_id(
        conn,
        board_blob=resulting_board_blob,
        side_to_move=resulting_side,
        castling_rights=resulting_castling,
        ep_file=resulting_ep,
    )

    if write_audit:
        record_decision_audit(
            conn,
            position_id=position_id,
            chosen_move_uci=move_uci,
            chosen_move_san=move_san,
            accepted=1,
            reason="accepted",
            actor=actor,
            require_suggested=require_suggested,
            in_suggestions=1 if in_suggestions else 0,
            resulting_position_id=resulting_position_id,
        )

    return AppliedMove(
        source_position_id=position_id,
        move_uci=move_uci,
        move_san=move_san,
        resulting_board_blob=resulting_board_blob,
        side_to_move=resulting_side,
        castling_rights=resulting_castling,
        ep_file=resulting_ep,
        resulting_position_id=resulting_position_id,
    )