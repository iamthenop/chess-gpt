from __future__ import annotations

import sqlite3
from pathlib import Path

from chessgpt.db.connection import connect
from chessgpt.pgn.replay import ParsedGame, board_to_blob, read_games_from_path, replay_game


def get_or_create_board(conn: sqlite3.Connection, board_blob: bytes) -> int:
    row = conn.execute(
        """
        SELECT id
        FROM boards
        WHERE board_blob = ?
        """,
        (board_blob,),
    ).fetchone()

    if row is not None:
        return int(row["id"])

    cur = conn.execute(
        """
        INSERT INTO boards (board_blob)
        VALUES (?)
        """,
        (board_blob,),
    )
    return int(cur.lastrowid)


def get_or_create_position(
    conn: sqlite3.Connection,
    *,
    board_id: int,
    side_to_move: int,
    castling_rights: int,
    ep_file: int | None,
) -> int:
    row = conn.execute(
        """
        SELECT id
        FROM positions
        WHERE board_id = ?
          AND side_to_move = ?
          AND castling_rights = ?
          AND (
                (ep_file IS NULL AND ? IS NULL)
                OR ep_file = ?
          )
        """,
        (board_id, side_to_move, castling_rights, ep_file, ep_file),
    ).fetchone()

    if row is not None:
        return int(row["id"])

    cur = conn.execute(
        """
        INSERT INTO positions (board_id, side_to_move, castling_rights, ep_file)
        VALUES (?, ?, ?, ?)
        """,
        (board_id, side_to_move, castling_rights, ep_file),
    )
    return int(cur.lastrowid)


def get_or_create_game(conn: sqlite3.Connection, parsed_game: ParsedGame, pgn_source: str) -> int:
    headers = parsed_game.headers

    cur = conn.execute(
        """
        INSERT INTO games (
            site,
            event,
            round,
            game_date,
            white_player,
            black_player,
            result,
            time_control,
            eco,
            opening,
            variation,
            pgn_source
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            headers.get("Site"),
            headers.get("Event"),
            headers.get("Round"),
            headers.get("Date"),
            headers.get("White"),
            headers.get("Black"),
            headers.get("Result", "*"),
            headers.get("TimeControl"),
            headers.get("ECO"),
            headers.get("Opening"),
            headers.get("Variation"),
            pgn_source,
        ),
    )
    return int(cur.lastrowid)


def _result_counters(result: str) -> tuple[int, int, int]:
    if result == "1-0":
        return 1, 0, 0
    if result == "0-1":
        return 0, 1, 0
    if result == "1/2-1/2":
        return 0, 0, 1
    return 0, 0, 0


def _time_control_bucket(time_control: str | None) -> tuple[int, int, int]:
    """
    Very lightweight classification.

    Returns:
      (blitz_count, rapid_count, classical_count)

    Rules:
    - missing / "-" / weird values: all zero
    - base seconds < 600: blitz
    - base seconds < 3600: rapid
    - otherwise: classical

    This is intentionally simple for v1.
    """
    if not time_control or time_control in {"-", "?"}:
        return 0, 0, 0

    # PGN TimeControl examples:
    # "300+0", "600", "1800+20", "40/7200:3600"
    raw = time_control.strip()

    try:
        if "/" in raw or ":" in raw:
            return 0, 0, 0

        base = raw.split("+", 1)[0]
        base_seconds = int(base)

        if base_seconds < 600:
            return 1, 0, 0
        if base_seconds < 3600:
            return 0, 1, 0
        return 0, 0, 1
    except ValueError:
        return 0, 0, 0


def upsert_edge(
    conn: sqlite3.Connection,
    *,
    from_position_id: int,
    to_position_id: int,
    move_uci: str,
    move_san: str,
    result: str,
    white_elo: str | None,
    black_elo: str | None,
    time_control: str | None,
) -> int:
    row = conn.execute(
        """
        SELECT id, frequency, white_wins, black_wins, draws,
               avg_elo, blitz_count, rapid_count, classical_count
        FROM edges
        WHERE from_position_id = ?
          AND move_uci = ?
          AND to_position_id = ?
        """,
        (from_position_id, move_uci, to_position_id),
    ).fetchone()

    white_win_inc, black_win_inc, draw_inc = _result_counters(result)
    blitz_inc, rapid_inc, classical_inc = _time_control_bucket(time_control)

    elo_values: list[float] = []
    for value in (white_elo, black_elo):
        if value is None:
            continue
        try:
            elo_values.append(float(value))
        except ValueError:
            pass

    avg_elo_new_sample = sum(elo_values) / len(elo_values) if elo_values else None

    if row is not None:
        edge_id = int(row["id"])
        old_freq = int(row["frequency"])
        old_avg = row["avg_elo"]

        if avg_elo_new_sample is None:
            next_avg = old_avg
        elif old_avg is None:
            next_avg = avg_elo_new_sample
        else:
            next_avg = ((float(old_avg) * old_freq) + avg_elo_new_sample) / (old_freq + 1)

        conn.execute(
            """
            UPDATE edges
            SET move_san = ?,
                frequency = frequency + 1,
                white_wins = white_wins + ?,
                black_wins = black_wins + ?,
                draws = draws + ?,
                avg_elo = ?,
                blitz_count = blitz_count + ?,
                rapid_count = rapid_count + ?,
                classical_count = classical_count + ?
            WHERE id = ?
            """,
            (
                move_san,
                white_win_inc,
                black_win_inc,
                draw_inc,
                next_avg,
                blitz_inc,
                rapid_inc,
                classical_inc,
                edge_id,
            ),
        )
        return edge_id

    cur = conn.execute(
        """
        INSERT INTO edges (
            from_position_id,
            to_position_id,
            move_uci,
            move_san,
            frequency,
            white_wins,
            black_wins,
            draws,
            avg_elo,
            blitz_count,
            rapid_count,
            classical_count
        )
        VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            from_position_id,
            to_position_id,
            move_uci,
            move_san,
            white_win_inc,
            black_win_inc,
            draw_inc,
            avg_elo_new_sample,
            blitz_inc,
            rapid_inc,
            classical_inc,
        ),
    )
    return int(cur.lastrowid)


def ingest_game(conn: sqlite3.Connection, parsed_game: ParsedGame, pgn_source: str) -> int:
    headers = parsed_game.headers
    game_id = get_or_create_game(conn, parsed_game, pgn_source)

    # Initial position from python-chess default start state.
    # White to move, both sides keep both castling rights, no ep.
    initial_board = parsed_game.game.board()
    from_board_id = get_or_create_board(conn, board_to_blob(initial_board))
    from_position_id = get_or_create_position(
        conn,
        board_id=from_board_id,
        side_to_move=0 if initial_board.turn else 1,
        castling_rights=0b1111,
        ep_file=None,
    )

    white_elo = headers.get("WhiteElo")
    black_elo = headers.get("BlackElo")
    result = headers.get("Result", "*")
    time_control = headers.get("TimeControl")

    for snapshot in replay_game(parsed_game.game):
        to_board_id = get_or_create_board(conn, snapshot.board_blob)
        to_position_id = get_or_create_position(
            conn,
            board_id=to_board_id,
            side_to_move=snapshot.side_to_move,
            castling_rights=snapshot.castling_rights,
            ep_file=snapshot.ep_file,
        )

        edge_id = upsert_edge(
            conn,
            from_position_id=from_position_id,
            to_position_id=to_position_id,
            move_uci=snapshot.move_uci,
            move_san=snapshot.move_san,
            result=result,
            white_elo=white_elo,
            black_elo=black_elo,
            time_control=time_control,
        )

        conn.execute(
            """
            INSERT INTO game_moves (game_id, ply, edge_id, position_id)
            VALUES (?, ?, ?, ?)
            """,
            (game_id, snapshot.ply, edge_id, to_position_id),
        )

        from_position_id = to_position_id

    return game_id


def ingest_pgn_file(conn: sqlite3.Connection, pgn_path: str | Path) -> int:
    path = Path(pgn_path)
    count = 0

    for parsed_game in read_games_from_path(path):
        ingest_game(conn, parsed_game, str(path))
        count += 1

    return count


def ingest_pgn_path(db_path: str | Path, pgn_path: str | Path) -> int:
    conn = connect(db_path)
    try:
        count = ingest_pgn_file(conn, pgn_path)
        conn.commit()
        return count
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
