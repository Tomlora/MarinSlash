from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence


ROUNDS = 9
MIN_MANAGERS = 2
MAX_MANAGERS = 8


@dataclass(frozen=True)
class DraftTurn:
    overall_pick: int
    round_number: int
    position_in_round: int
    manager_id: int


def validate_manager_count(manager_ids: Sequence[int]) -> None:
    if not MIN_MANAGERS <= len(manager_ids) <= MAX_MANAGERS:
        raise ValueError("A Fantasy league must contain between 2 and 8 managers")
    if len(set(manager_ids)) != len(manager_ids):
        raise ValueError("Manager identifiers must be unique")


def snake_order(manager_ids: Sequence[int], rounds: int = ROUNDS) -> List[int]:
    """Return the complete snake draft order.

    Odd rounds use the declared draft order, even rounds use the reverse order.
    This works identically for even and odd manager counts.
    """
    validate_manager_count(manager_ids)
    if rounds <= 0:
        raise ValueError("rounds must be positive")

    forward = list(manager_ids)
    reverse = list(reversed(forward))
    result: List[int] = []
    for round_index in range(rounds):
        result.extend(forward if round_index % 2 == 0 else reverse)
    return result


def draft_turns(manager_ids: Sequence[int], rounds: int = ROUNDS) -> List[DraftTurn]:
    order = snake_order(manager_ids, rounds=rounds)
    manager_count = len(manager_ids)
    return [
        DraftTurn(
            overall_pick=index + 1,
            round_number=(index // manager_count) + 1,
            position_in_round=(index % manager_count) + 1,
            manager_id=manager_id,
        )
        for index, manager_id in enumerate(order)
    ]


def manager_for_pick(manager_ids: Sequence[int], overall_pick: int, rounds: int = ROUNDS) -> int:
    if overall_pick < 1:
        raise ValueError("overall_pick starts at 1")
    order = snake_order(manager_ids, rounds=rounds)
    if overall_pick > len(order):
        raise ValueError("overall_pick is outside the draft")
    return order[overall_pick - 1]


def remaining_picks_for_manager(
    manager_ids: Sequence[int], manager_id: int, completed_picks: int, rounds: int = ROUNDS
) -> int:
    """Count how many future picks a manager still owns."""
    order = snake_order(manager_ids, rounds=rounds)
    if manager_id not in manager_ids:
        raise ValueError("Unknown manager")
    completed_picks = max(0, min(completed_picks, len(order)))
    return sum(1 for pick_manager in order[completed_picks:] if pick_manager == manager_id)


def can_still_complete_roster(
    missing_required_slots: Iterable[str], remaining_picks: int
) -> bool:
    """Reject choices that make completion of mandatory roster slots impossible."""
    required = set(missing_required_slots)
    return len(required) <= remaining_picks
