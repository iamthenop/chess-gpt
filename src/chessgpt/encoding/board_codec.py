from __future__ import annotations

BOARD_SIZE = 64
BOARD_BYTES = 32
ENCODING_VERSION = 1

EMPTY = 0x0

WHITE_PAWN = 0x1
WHITE_KNIGHT = 0x2
WHITE_BISHOP = 0x3
WHITE_ROOK = 0x4
WHITE_QUEEN = 0x5
WHITE_KING = 0x6

BLACK_PAWN = 0xF
BLACK_KNIGHT = 0xE
BLACK_BISHOP = 0xD
BLACK_ROOK = 0xC
BLACK_QUEEN = 0xB
BLACK_KING = 0xA


def square_index(file_index: int, rank_index: int) -> int:
    """
    Internal layout:
    - a1 is address 0
    - row-major order
    - rank 1 first, rank 8 last
    """
    if not 0 <= file_index <= 7:
        raise ValueError(f"file_index out of range: {file_index}")
    if not 0 <= rank_index <= 7:
        raise ValueError(f"rank_index out of range: {rank_index}")
    return rank_index * 8 + file_index


def algebraic_to_index(square: str) -> int:
    if len(square) != 2:
        raise ValueError(f"invalid square: {square}")

    file_char = square[0].lower()
    rank_char = square[1]

    if not ("a" <= file_char <= "h"):
        raise ValueError(f"invalid file: {file_char}")
    if not ("1" <= rank_char <= "8"):
        raise ValueError(f"invalid rank: {rank_char}")

    return square_index(ord(file_char) - ord("a"), int(rank_char) - 1)


def index_to_algebraic(index: int) -> str:
    if not 0 <= index < BOARD_SIZE:
        raise ValueError(f"index out of range: {index}")

    file_index = index % 8
    rank_index = index // 8
    return f"{chr(ord('a') + file_index)}{rank_index + 1}"


def color_flip(nibble: int) -> int:
    """
    Flip piece color using 4-bit two's complement pairing.
    Empty remains empty.
    """
    if nibble == EMPTY:
        return EMPTY
    if not 0 <= nibble <= 0xF:
        raise ValueError(f"nibble out of range: {nibble}")
    return ((nibble ^ 0xF) + 1) & 0xF


def pack_nibbles(nibbles: list[int]) -> bytes:
    if len(nibbles) != BOARD_SIZE:
        raise ValueError(f"expected {BOARD_SIZE} nibbles, got {len(nibbles)}")

    out = bytearray(BOARD_BYTES)
    for i in range(0, BOARD_SIZE, 2):
        hi = nibbles[i]
        lo = nibbles[i + 1]

        if not 0 <= hi <= 0xF:
            raise ValueError(f"nibble out of range at index {i}: {hi}")
        if not 0 <= lo <= 0xF:
            raise ValueError(f"nibble out of range at index {i + 1}: {lo}")

        out[i // 2] = (hi << 4) | lo

    return bytes(out)


def unpack_nibbles(board_blob: bytes) -> list[int]:
    if len(board_blob) != BOARD_BYTES:
        raise ValueError(f"expected {BOARD_BYTES} bytes, got {len(board_blob)}")

    out: list[int] = []
    for byte in board_blob:
        out.append((byte >> 4) & 0xF)
        out.append(byte & 0xF)
    return out


def encode_board_from_hex(board_hex: str) -> bytes:
    cleaned = "".join(board_hex.split()).upper()

    if len(cleaned) != BOARD_SIZE:
        raise ValueError(f"expected {BOARD_SIZE} hex chars, got {len(cleaned)}")

    try:
        nibbles = [int(ch, 16) for ch in cleaned]
    except ValueError as exc:
        raise ValueError("board_hex contains non-hex characters") from exc

    return pack_nibbles(nibbles)


def decode_board_to_hex(board_blob: bytes) -> str:
    return "".join(f"{n:X}" for n in unpack_nibbles(board_blob))


def encode_board_from_rows(rows: list[str]) -> bytes:
    """
    rows[0] = rank 1
    rows[7] = rank 8
    each row = 8 hex chars
    """
    if len(rows) != 8:
        raise ValueError(f"expected 8 rows, got {len(rows)}")

    cleaned_rows: list[str] = []
    for i, row in enumerate(rows):
        cleaned = row.strip().upper()
        if len(cleaned) != 8:
            raise ValueError(f"row {i} must have 8 hex chars, got {len(cleaned)}")
        cleaned_rows.append(cleaned)

    return encode_board_from_hex("".join(cleaned_rows))


def decode_board_to_rows(board_blob: bytes) -> list[str]:
    board_hex = decode_board_to_hex(board_blob)
    return [board_hex[i:i + 8] for i in range(0, BOARD_SIZE, 8)]


def decode_board_to_text_rows(board_blob: bytes) -> str:
    return "\n".join(decode_board_to_rows(board_blob))


def get_square(board_blob: bytes, square: str) -> int:
    nibbles = unpack_nibbles(board_blob)
    return nibbles[algebraic_to_index(square)]


def set_square(board_blob: bytes, square: str, nibble: int) -> bytes:
    if not 0 <= nibble <= 0xF:
        raise ValueError(f"nibble out of range: {nibble}")

    nibbles = unpack_nibbles(board_blob)
    nibbles[algebraic_to_index(square)] = nibble
    return pack_nibbles(nibbles)


def starting_board() -> bytes:
    return encode_board_from_rows(
        [
            "42356324",
            "11111111",
            "00000000",
            "00000000",
            "00000000",
            "00000000",
            "FFFFFFFF",
            "CEDBADEC",
        ]
    )
