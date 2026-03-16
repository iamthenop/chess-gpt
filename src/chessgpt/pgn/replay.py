from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, TextIO

import chess
import chess.pgn

from chessgpt.encoding.board_codec import encode_board_from_rows


@dataclass(frozen=True)
class ReplaySnapshot:
    ply: int
    move_uci: str
    move_san: str
    board_blob: bytes
    side_to_move: int          # 0 = white, 1 = black
    castling_rights: int       # 1 = WL, 2 = WS, 4 = BL, 8 = BS
    ep_file: int | None        # 0..7 for a..h, None if unavailable


@dataclass(frozen=True)
class ParsedGame:
    headers: dict[str, str]
    game: chess.pgn.Game


def _piece_to_nibble(piece: chess.Piece) -> str:
    if piece.color == chess.WHITE:
        return {
            chess.PAWN: "1",
            chess.KNIGHT: "2",
            chess.BISHOP: "3",
            chess.ROOK: "4",
            chess.QUEEN: "5",
            chess.KING: "6",
        }[piece.piece_type]

    return {
        chess.PAWN: "F",
        chess.KNIGHT: "E",
        chess.BISHOP: "D",
        chess.ROOK: "C",
        chess.QUEEN: "B",
        chess.KING: "A",
    }[piece.piece_type]


def board_to_rows(board: chess.Board) -> list[str]:
    """
    Convert a python-chess board into the project's machine-oriented row format.

    Output rows are:
    - rows[0] = rank 1
    - rows[7] = rank 8
    - each row is 8 uppercase hex chars
    """
    rows: list[str] = []

    for rank_index in range(8):  # rank 1 to rank 8
        rank = rank_index
        chars: list[str] = []

        for file_index in range(8):  # a to h
            square = chess.square(file_index, rank)
            piece = board.piece_at(square)
            chars.append("0" if piece is None else _piece_to_nibble(piece))

        rows.append("".join(chars))

    return rows


def board_to_blob(board: chess.Board) -> bytes:
    return encode_board_from_rows(board_to_rows(board))


def side_to_move(board: chess.Board) -> int:
    return 0 if board.turn == chess.WHITE else 1


def castling_rights_mask(board: chess.Board) -> int:
    mask = 0

    if board.has_queenside_castling_rights(chess.WHITE):
        mask |= 0b0001  # WL
    if board.has_kingside_castling_rights(chess.WHITE):
        mask |= 0b0010  # WS
    if board.has_queenside_castling_rights(chess.BLACK):
        mask |= 0b0100  # BL
    if board.has_kingside_castling_rights(chess.BLACK):
        mask |= 0b1000  # BS

    return mask


def ep_file(board: chess.Board) -> int | None:
    """
    Return en passant file as 0..7 for a..h, or None if unavailable.
    """
    if board.ep_square is None:
        return None
    return chess.square_file(board.ep_square)


def replay_game(game: chess.pgn.Game) -> Iterator[ReplaySnapshot]:
    """
    Replay a parsed PGN game and yield one snapshot per ply.

    Each snapshot represents the resulting position after the move is applied.
    """
    board = game.board()
    node = game
    ply = 0

    while node.variations:
        next_node = node.variation(0)
        move = next_node.move

        move_san = board.san(move)
        move_uci = move.uci()

        board.push(move)
        ply += 1

        yield ReplaySnapshot(
            ply=ply,
            move_uci=move_uci,
            move_san=move_san,
            board_blob=board_to_blob(board),
            side_to_move=side_to_move(board),
            castling_rights=castling_rights_mask(board),
            ep_file=ep_file(board),
        )

        node = next_node


def read_games(handle: TextIO) -> Iterator[ParsedGame]:
    """
    Read all games from a PGN text stream.
    """
    while True:
        game = chess.pgn.read_game(handle)
        if game is None:
            break

        headers = {str(k): str(v) for k, v in game.headers.items()}
        yield ParsedGame(headers=headers, game=game)


def read_games_from_path(path: str | Path) -> Iterator[ParsedGame]:
    file_path = Path(path)
    with file_path.open("r", encoding="utf-8") as handle:
        yield from read_games(handle)
