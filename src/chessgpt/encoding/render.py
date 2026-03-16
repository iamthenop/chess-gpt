from __future__ import annotations

from dataclasses import dataclass

from .board_codec import (
    BLACK_BISHOP,
    BLACK_KING,
    BLACK_KNIGHT,
    BLACK_PAWN,
    BLACK_QUEEN,
    BLACK_ROOK,
    WHITE_BISHOP,
    WHITE_KING,
    WHITE_KNIGHT,
    WHITE_PAWN,
    WHITE_QUEEN,
    WHITE_ROOK,
    decode_board_to_rows,
)

UNICODE_PIECES = {
    WHITE_PAWN: "♙",
    WHITE_KNIGHT: "♘",
    WHITE_BISHOP: "♗",
    WHITE_ROOK: "♖",
    WHITE_QUEEN: "♕",
    WHITE_KING: "♔",
    BLACK_PAWN: "♟",
    BLACK_KNIGHT: "♞",
    BLACK_BISHOP: "♝",
    BLACK_ROOK: "♜",
    BLACK_QUEEN: "♛",
    BLACK_KING: "♚",
}

ASCII_PIECES = {
    WHITE_PAWN: "P",
    WHITE_KNIGHT: "N",
    WHITE_BISHOP: "B",
    WHITE_ROOK: "R",
    WHITE_QUEEN: "Q",
    WHITE_KING: "K",
    BLACK_PAWN: "p",
    BLACK_KNIGHT: "n",
    BLACK_BISHOP: "b",
    BLACK_ROOK: "r",
    BLACK_QUEEN: "q",
    BLACK_KING: "k",
}


@dataclass(frozen=True)
class RenderOptions:
    piece_set: str = "unicode"   # unicode | ascii
    theme: str = "dark"          # dark | light | plain
    show_coordinates: bool = True
    white_at_bottom: bool = True


def _nibble_to_piece_char(nibble: int, piece_set: str) -> str:
    if piece_set == "unicode":
        return UNICODE_PIECES.get(nibble, " ")
    if piece_set == "ascii":
        return ASCII_PIECES.get(nibble, " ")
    raise ValueError(f"unknown piece_set: {piece_set}")


def _is_dark_square(file_index: int, rank_index: int) -> bool:
    # a1 is dark
    return (file_index + rank_index) % 2 == 0


def _empty_square_fill(dark_square: bool, theme: str) -> str:
    if theme == "plain":
        return " "
    if theme == "dark":
        return "░" if dark_square else " "
    if theme == "light":
        return "▒" if dark_square else " "
    raise ValueError(f"unknown theme: {theme}")


def _cell_text(nibble: int, file_index: int, rank_index: int, options: RenderOptions) -> str:
    piece = _nibble_to_piece_char(nibble, options.piece_set)
    if piece != " ":
        return f" {piece}  "

    dark = _is_dark_square(file_index, rank_index)
    fill = _empty_square_fill(dark, options.theme)
    return fill * 4


def render_text_board(
    board_blob: bytes,
    *,
    piece_set: str = "unicode",
    theme: str = "dark",
    show_coordinates: bool = True,
    white_at_bottom: bool = True,
) -> str:
    options = RenderOptions(
        piece_set=piece_set,
        theme=theme,
        show_coordinates=show_coordinates,
        white_at_bottom=white_at_bottom,
    )

    machine_rows = decode_board_to_rows(board_blob)
    rows = [list(row) for row in machine_rows]

    if white_at_bottom:
        display_rank_indices = list(range(7, -1, -1))
        file_labels = list("abcdefgh")
    else:
        display_rank_indices = list(range(8))
        file_labels = list("hgfedcba")

    horizontal = "  +" + "+".join(["----"] * 8) + "+"

    lines: list[str] = [horizontal]

    for rank_index in display_rank_indices:
        display_rank = rank_index + 1
        row = rows[rank_index]

        if white_at_bottom:
            display_files = list(range(8))
        else:
            display_files = list(range(7, -1, -1))

        cells = []
        for file_index in display_files:
            nibble = int(row[file_index], 16)
            cells.append(_cell_text(nibble, file_index, rank_index, options))

        lines.append(f"{display_rank} |" + "|".join(cells) + "|")
        lines.append(horizontal)

    if show_coordinates:
        coord_line = "    " + "   ".join(file_labels)
        lines.append(coord_line)

    return "\n".join(lines)


def render_llm_board(
    board_blob: bytes,
    *,
    side_to_move: str | None = None,
    castling: str | None = None,
    ep_file: str | None = None,
) -> str:
    rows = decode_board_to_rows(board_blob)

    lines: list[str] = []
    if side_to_move is not None:
        lines.append(f"side_to_move:{side_to_move}")
    if castling is not None:
        lines.append(f"castling:{castling}")
    if ep_file is not None:
        lines.append(f"ep_file:{ep_file}")
    if lines:
        lines.append("board:")

    lines.extend(rows)
    return "\n".join(lines)
