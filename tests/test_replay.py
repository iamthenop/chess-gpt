from __future__ import annotations

import io

from chessgpt.encoding.board_codec import decode_board_to_rows
from chessgpt.pgn.replay import board_to_rows, read_games, replay_game


def test_board_to_rows_starting_position() -> None:
    import chess

    board = chess.Board()
    rows = board_to_rows(board)

    assert rows == [
        "42356324",
        "11111111",
        "00000000",
        "00000000",
        "00000000",
        "00000000",
        "FFFFFFFF",
        "CEDBADEC",
    ]


def test_replay_game_emits_expected_snapshots_for_short_opening() -> None:
    pgn = io.StringIO(
        """
[Event "Test Game"]
[Site "Local"]
[Date "2026.03.15"]
[Round "1"]
[White "White"]
[Black "Black"]
[Result "1-0"]

1. e4 e5 2. Nf3 Nc6 1-0
""".strip()
    )

    parsed_games = list(read_games(pgn))
    assert len(parsed_games) == 1

    parsed_game = parsed_games[0]
    snapshots = list(replay_game(parsed_game.game))

    assert len(snapshots) == 4

    s1, s2, s3, s4 = snapshots

    assert s1.ply == 1
    assert s1.move_san == "e4"
    assert s1.move_uci == "e2e4"
    assert s1.side_to_move == 1
    assert s1.castling_rights == 0b1111
    assert s1.ep_file == 4
    assert decode_board_to_rows(s1.board_blob) == [
        "42356324",
        "11110111",
        "00000000",
        "00001000",
        "00000000",
        "00000000",
        "FFFFFFFF",
        "CEDBADEC",
    ]

    assert s2.ply == 2
    assert s2.move_san == "e5"
    assert s2.move_uci == "e7e5"
    assert s2.side_to_move == 0
    assert s2.castling_rights == 0b1111
    assert s2.ep_file == 4
    assert decode_board_to_rows(s2.board_blob) == [
        "42356324",
        "11110111",
        "00000000",
        "00001000",
        "0000F000",
        "00000000",
        "FFFF0FFF",
        "CEDBADEC",
    ]

    assert s3.ply == 3
    assert s3.move_san == "Nf3"
    assert s3.move_uci == "g1f3"
    assert s3.side_to_move == 1
    assert s3.castling_rights == 0b1111
    assert s3.ep_file is None
    assert decode_board_to_rows(s3.board_blob) == [
        "42356304",
        "11110111",
        "00000200",
        "00001000",
        "0000F000",
        "00000000",
        "FFFF0FFF",
        "CEDBADEC",
    ]

    assert s4.ply == 4
    assert s4.move_san == "Nc6"
    assert s4.move_uci == "b8c6"
    assert s4.side_to_move == 0
    assert s4.castling_rights == 0b1111
    assert s4.ep_file is None
    assert decode_board_to_rows(s4.board_blob) == [
        "42356304",
        "11110111",
        "00000200",
        "00001000",
        "0000F000",
        "00E00000",
        "FFFF0FFF",
        "C0DBADEC",
    ]


def test_read_games_reads_multiple_games() -> None:
    pgn = io.StringIO(
        """
[Event "Game 1"]
[Site "Local"]
[Date "2026.03.15"]
[Round "1"]
[White "A"]
[Black "B"]
[Result "1-0"]

1. e4 e5 1-0

[Event "Game 2"]
[Site "Local"]
[Date "2026.03.15"]
[Round "2"]
[White "C"]
[Black "D"]
[Result "0-1"]

1. d4 d5 0-1
""".strip()
    )

    parsed_games = list(read_games(pgn))
    assert len(parsed_games) == 2
    assert parsed_games[0].headers["Event"] == "Game 1"
    assert parsed_games[1].headers["Event"] == "Game 2"