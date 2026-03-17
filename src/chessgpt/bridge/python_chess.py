from __future__ import annotations

import chess

from chessgpt.encoding.board_codec import decode_board_to_rows, encode_board_from_rows

# Nibble/hex row encoding used by chess-gpt.
NIBBLE_TO_SYMBOL = {
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


def piece_to_nibble(piece: chess.Piece) -> str:
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
    Convert a python-chess board into chess-gpt machine-oriented row format.

    Output rows are:
    - rows[0] = rank 1
    - rows[7] = rank 8
    - each row is 8 uppercase hex chars
    """
    rows: list[str] = []

    for rank_index in range(8):  # rank 1 to rank 8
        chars: list[str] = []

        for file_index in range(8):  # a to h
            square = chess.square(file_index, rank_index)
            piece = board.piece_at(square)
            chars.append("0" if piece is None else piece_to_nibble(piece))

        rows.append("".join(chars))

    return rows


def board_to_blob(board: chess.Board) -> bytes:
    return encode_board_from_rows(board_to_rows(board))


def side_to_move_int(board: chess.Board) -> int:
    return 0 if board.turn == chess.WHITE else 1


def side_to_move_char(board: chess.Board) -> str:
    return "w" if board.turn == chess.WHITE else "b"


def castling_rights_mask(board: chess.Board) -> int:
    """
    Convert python-chess castling rights into chess-gpt bitmask form.

    Bit layout:
      1 = White long
      2 = White short
      4 = Black long
      8 = Black short
    """
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


def castling_rights_string(mask: int) -> str:
    return f"{mask:04b}"


def ep_file(board: chess.Board) -> int | None:
    """
    Return en passant file as 0..7 for a..h, or None if unavailable.
    """
    if board.ep_square is None:
        return None
    return chess.square_file(board.ep_square)


def ep_file_string(value: int | None) -> str:
    if value is None:
        return "-"
    return chr(ord("a") + value)


def castling_fen_from_mask(mask: int) -> str:
    """
    Convert chess-gpt castling mask into FEN castling rights string.
    """
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


def board_blob_to_board(
    board_blob: bytes,
    *,
    side_to_move: int,
    castling_rights: int,
    ep_file_value: int | None,
) -> chess.Board:
    """
    Reconstruct a python-chess Board from authoritative chess-gpt state.
    """
    board = chess.Board(None)

    rows = decode_board_to_rows(board_blob)

    # rows[0] = rank 1, rows[7] = rank 8
    for rank_index, row in enumerate(rows):
        for file_index, ch in enumerate(row):
            if ch == "0":
                continue

            symbol = NIBBLE_TO_SYMBOL[ch]
            piece = chess.Piece.from_symbol(symbol)
            square = chess.square(file_index, rank_index)
            board.set_piece_at(square, piece)

    board.turn = chess.WHITE if side_to_move == 0 else chess.BLACK
    board.set_castling_fen(castling_fen_from_mask(castling_rights))

    if ep_file_value is None:
        board.ep_square = None
    else:
        ep_rank = 5 if side_to_move == 0 else 2
        board.ep_square = chess.square(ep_file_value, ep_rank)

    return board


def board_to_position_parts(board: chess.Board) -> tuple[bytes, int, int, int | None]:
    """
    Convert a python-chess Board into chess-gpt authoritative position parts.

    Returns:
      (board_blob, side_to_move, castling_rights, ep_file)
    """
    return (
        board_to_blob(board),
        side_to_move_int(board),
        castling_rights_mask(board),
        ep_file(board),
    )


def board_to_position_payload(board: chess.Board) -> dict:
    """
    Convenience helper for JSON-ready state packaging.
    """
    board_blob, side, castling, ep = board_to_position_parts(board)
    return {
        "side_to_move": "w" if side == 0 else "b",
        "castling": castling_rights_string(castling),
        "ep_file": ep_file_string(ep),
        "board_rows": decode_board_to_rows(board_blob),
    }