from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, TextIO

import chess.pgn

from chessgpt.bridge.python_chess import (
    board_to_blob,
    board_to_rows,
    castling_rights_mask,
    ep_file,
    side_to_move_int,
)


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
            side_to_move=side_to_move_int(board),
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