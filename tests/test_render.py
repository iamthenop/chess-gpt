from __future__ import annotations

from chessgpt.encoding.board_codec import starting_board
from chessgpt.encoding.render import render_llm_board, render_text_board


def test_render_llm_board_starting_position_without_metadata() -> None:
    board_blob = starting_board()

    rendered = render_llm_board(board_blob)

    assert rendered == "\n".join(
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


def test_render_llm_board_starting_position_with_metadata() -> None:
    board_blob = starting_board()

    rendered = render_llm_board(
        board_blob,
        side_to_move="w",
        castling="1111",
        ep_file="-",
    )

    assert rendered == "\n".join(
        [
            "side_to_move:w",
            "castling:1111",
            "ep_file:-",
            "board:",
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


def test_render_text_board_unicode_dark_with_coordinates() -> None:
    board_blob = starting_board()

    rendered = render_text_board(
        board_blob,
        piece_set="unicode",
        theme="dark",
        show_coordinates=True,
        white_at_bottom=True,
    )

    expected = "\n".join(
        [
            "  +----+----+----+----+----+----+----+----+",
            "8 | ♜  | ♞  | ♝  | ♛  | ♚  | ♝  | ♞  | ♜  |",
            "  +----+----+----+----+----+----+----+----+",
            "7 | ♟  | ♟  | ♟  | ♟  | ♟  | ♟  | ♟  | ♟  |",
            "  +----+----+----+----+----+----+----+----+",
            "6 |    |░░░░|    |░░░░|    |░░░░|    |░░░░|",
            "  +----+----+----+----+----+----+----+----+",
            "5 |░░░░|    |░░░░|    |░░░░|    |░░░░|    |",
            "  +----+----+----+----+----+----+----+----+",
            "4 |    |░░░░|    |░░░░|    |░░░░|    |░░░░|",
            "  +----+----+----+----+----+----+----+----+",
            "3 |░░░░|    |░░░░|    |░░░░|    |░░░░|    |",
            "  +----+----+----+----+----+----+----+----+",
            "2 | ♙  | ♙  | ♙  | ♙  | ♙  | ♙  | ♙  | ♙  |",
            "  +----+----+----+----+----+----+----+----+",
            "1 | ♖  | ♘  | ♗  | ♕  | ♔  | ♗  | ♘  | ♖  |",
            "  +----+----+----+----+----+----+----+----+",
            "    a   b   c   d   e   f   g   h",
        ]
    )

    assert rendered == expected


def test_render_text_board_ascii_plain_with_coordinates() -> None:
    board_blob = starting_board()

    rendered = render_text_board(
        board_blob,
        piece_set="ascii",
        theme="plain",
        show_coordinates=True,
        white_at_bottom=True,
    )

    expected = "\n".join(
        [
            "  +----+----+----+----+----+----+----+----+",
            "8 | r  | n  | b  | q  | k  | b  | n  | r  |",
            "  +----+----+----+----+----+----+----+----+",
            "7 | p  | p  | p  | p  | p  | p  | p  | p  |",
            "  +----+----+----+----+----+----+----+----+",
            "6 |    |    |    |    |    |    |    |    |",
            "  +----+----+----+----+----+----+----+----+",
            "5 |    |    |    |    |    |    |    |    |",
            "  +----+----+----+----+----+----+----+----+",
            "4 |    |    |    |    |    |    |    |    |",
            "  +----+----+----+----+----+----+----+----+",
            "3 |    |    |    |    |    |    |    |    |",
            "  +----+----+----+----+----+----+----+----+",
            "2 | P  | P  | P  | P  | P  | P  | P  | P  |",
            "  +----+----+----+----+----+----+----+----+",
            "1 | R  | N  | B  | Q  | K  | B  | N  | R  |",
            "  +----+----+----+----+----+----+----+----+",
            "    a   b   c   d   e   f   g   h",
        ]
    )

    assert rendered == expected


def test_render_text_board_black_at_bottom_reverses_orientation() -> None:
    board_blob = starting_board()

    rendered = render_text_board(
        board_blob,
        piece_set="ascii",
        theme="plain",
        show_coordinates=True,
        white_at_bottom=False,
    )

    lines = rendered.splitlines()

    assert lines[1] == "1 | R  | N  | B  | K  | Q  | B  | N  | R  |"
    assert lines[-1] == "    h   g   f   e   d   c   b   a"