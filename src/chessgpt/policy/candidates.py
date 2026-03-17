from __future__ import annotations

import hashlib
from dataclasses import dataclass

from chessgpt.api.suggestions import get_suggestions_payload


@dataclass(frozen=True)
class CandidateSet:
    format_version: int
    position_id: int
    min_frequency: int
    moves: tuple[str, ...]
    binding_required: bool
    fallback_policy: str
    candidate_set_id: str

    def to_payload(self) -> dict:
        return {
            "format_version": self.format_version,
            "position_id": self.position_id,
            "min_frequency": self.min_frequency,
            "candidate_moves": list(self.moves),
            "candidate_binding_required": self.binding_required,
            "fallback_policy": self.fallback_policy,
            "candidate_set_id": self.candidate_set_id,
        }


def _candidate_set_id(
    *,
    position_id: int,
    min_frequency: int,
    moves: tuple[str, ...],
    binding_required: bool,
    fallback_policy: str,
) -> str:
    material = "|".join(
        [
            "v1",
            str(position_id),
            str(min_frequency),
            "1" if binding_required else "0",
            fallback_policy,
            ",".join(moves),
        ]
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def build_candidate_set(
    conn,
    position_id: int,
    *,
    min_frequency: int = 5,
    limit: int = 10,
    fallback_policy: str = "allow_any_legal_move_if_no_candidates",
) -> CandidateSet:
    suggestions = get_suggestions_payload(
        conn,
        position_id,
        min_frequency=min_frequency,
        limit=limit,
    )

    moves = tuple(move["move_uci"] for move in suggestions["candidate_moves"])
    binding_required = len(moves) > 0

    return CandidateSet(
        format_version=1,
        position_id=position_id,
        min_frequency=min_frequency,
        moves=moves,
        binding_required=binding_required,
        fallback_policy=fallback_policy,
        candidate_set_id=_candidate_set_id(
            position_id=position_id,
            min_frequency=min_frequency,
            moves=moves,
            binding_required=binding_required,
            fallback_policy=fallback_policy,
        ),
    )


def move_allowed(
    move_uci: str,
    candidate_set: CandidateSet,
) -> bool:
    if candidate_set.binding_required:
        return move_uci in candidate_set.moves

    if candidate_set.fallback_policy == "allow_any_legal_move_if_no_candidates":
        return True

    return False