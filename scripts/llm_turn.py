#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from chessgpt.api.control import apply_move_payload
from chessgpt.api.turns import get_turn_payload
from chessgpt.db.connection import connect
from chessgpt.errors import InvalidMoveSyntaxError
from chessgpt.policy.candidates import CandidateSet, move_allowed


def candidate_set_from_turn_payload(payload: dict) -> CandidateSet:
    policy = payload["candidate_policy"]
    return CandidateSet(
        format_version=payload["format_version"],
        position_id=payload["position"]["position_id"],
        min_frequency=payload["position"].get("min_frequency", 0) if False else 0,
        moves=tuple(policy["candidate_moves"]),
        binding_required=bool(policy["candidate_binding_required"]),
        fallback_policy=str(policy["fallback_policy"]),
        candidate_set_id=str(policy["candidate_set_id"]),
    )


def parse_uci_only(text: str) -> str:
    stripped = text.strip().lower()
    import re

    if not re.fullmatch(r"^[a-h][1-8][a-h][1-8][qrbn]?$", stripped):
        raise InvalidMoveSyntaxError(
            "LLM response must be exactly one UCI move and nothing else. "
            f"Got: {text!r}"
        )
    return stripped


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare and apply one LLM chess turn")
    parser.add_argument("position_id", type=int, help="Source position ID")
    parser.add_argument(
        "--db",
        default="data/db/chessgpt.sqlite3",
        help="Path to SQLite database file",
    )
    parser.add_argument(
        "--min-frequency",
        type=int,
        default=5,
        help="Minimum suggestion frequency to include in the turn payload",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of candidate moves to include in the turn payload",
    )
    parser.add_argument(
        "--mode",
        choices=("prompt", "apply"),
        default="prompt",
        help="prompt = emit payload only, apply = read one UCI move from stdin and apply it",
    )
    parser.add_argument(
        "--actor",
        default="llm",
        help="Actor label for audit logging in apply mode",
    )
    parser.add_argument(
        "--allow-unsuggested",
        action="store_true",
        help="Allow legal moves not present in the issued candidate set",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    db_path = (repo_root / args.db).resolve() if not Path(args.db).is_absolute() else Path(args.db)

    conn = connect(db_path)
    try:
        strict_mode = not args.allow_unsuggested
        turn_payload = get_turn_payload(
            conn,
            args.position_id,
            min_frequency=args.min_frequency,
            limit=args.limit,
            strict_mode=strict_mode,
        )

        if args.mode == "prompt":
            print(json.dumps(turn_payload, indent=2))
            return

        llm_response = sys.stdin.read()
        move_uci = parse_uci_only(llm_response)

        issued_candidate_set = candidate_set_from_turn_payload(turn_payload)

        if strict_mode and not move_allowed(move_uci, issued_candidate_set):
            raise ValueError(
                f"move not allowed by issued candidate set: {move_uci} "
                f"(candidate_set_id={issued_candidate_set.candidate_set_id})"
            )

        result_payload = apply_move_payload(
            conn,
            position_id=args.position_id,
            move_uci=move_uci,
            actor=args.actor,
            require_suggested=False,
            write_audit=True,
        )
        conn.commit()
        print(json.dumps(result_payload, indent=2))

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()