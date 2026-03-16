from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass

import chess

from chessgpt.db.audit import record_decision_audit
from chessgpt.encoding.board_codec import decode_board_to_rows
from chessgpt.pgn.replay import board_to_blob
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
        raise ValueError(f"position_id not found: {position_id}")

    return PositionState(
        position_id=int(row["position_id"]),
        board_blob=row["board_blob"],
        side_to_move=int(row["side_to_move"]),
        castling_rights=int(row["castling_rights"]),
        ep_file=row["ep_file"],
    )


def _castling_fen(mask: int) -> str:
    rights: list[str] = []
    if mask & 0b0010:
        rights.append("K")
    if mask & 0b0001:
        rights.append("Q")
    if mask & 0b1000:
        rights.append("k")
    if mask & 0b0100:
        rights.append("q")
    return "".join(rights) or "-"


def _rows_to_board(
    board_blob: bytes,
    side_to_move: int,
    castling_rights: int,
    ep_file: int | None,
) -> chess.Board:
    board = chess.Board(None)

    rows = decode_board_to_rows(board_blob)

    nibble_to_symbol = {
        "1": "P",
        "2": "N",
        "3": "B",
        "4": "R",
        "5": "Q",
        "6": "K",
        "F": "p",
        "E": "n",
        "D": "b",
        "C": "r",
        "B": "q",
        "A": "k",
    }

    for rank_index, row in enumerate(rows):      # rank 1 .. rank 8
        for file_index, ch in enumerate(row):    # a .. h
            if ch == "0":
                continue
            symbol = nibble_to_symbol[ch]
            piece = chess.Piece.from_symbol(symbol)
            square = chess.square(file_index, rank_index)
            board.set_piece_at(square, piece)

    board.turn = chess.WHITE if side_to_move == 0 else chess.BLACK
    board.set_castling_fen(_castling_fen(castling_rights))

    if ep_file is None:
        board.ep_square = None
    else:
        # If white to move, black just moved two squares -> ep target is rank 6.
        # If black to move, white just moved two squares -> ep target is rank 3.
        ep_rank = 5 if side_to_move == 0 else 2
        board.ep_square = chess.square(ep_file, ep_rank)

    return board


def _side_to_move(board: chess.Board) -> int:
    return 0 if board.turn == chess.WHITE else 1


def _castling_rights_mask(board: chess.Board) -> int:
    mask = 0
    if board.has_queenside_castling_rights(chess.WHITE):
        mask |= 0b0001
    if board.has_kingside_castling_rights(chess.WHITE):
        mask |= 0b0010
    if board.has_queenside_castling_rights(chess.BLACK):
        mask |= 0b0100
    if board.has_kingside_castling_rights(chess.BLACK):
        mask |= 0b1000
    return mask


def _ep_file(board: chess.Board) -> int | None:
    if board.ep_square is None:
        return None
    return chess.square_file(board.ep_square)


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
        raise ValueError(f"invalid UCI move syntax: {move_uci}")

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
        raise ValueError(f"move not in suggested set: {move_uci}")

    board = _rows_to_board(
        state.board_blob,
        state.side_to_move,
        state.castling_rights,
        state.ep_file,
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
        raise ValueError(f"illegal move for position {position_id}: {move_uci}")

    move_san = board.san(move)
    board.push(move)

    resulting_board_blob = board_to_blob(board)
    resulting_side = _side_to_move(board)
    resulting_castling = _castling_rights_mask(board)
    resulting_ep = _ep_file(board)

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
