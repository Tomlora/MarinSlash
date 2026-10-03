from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence

from .draft import validate_manager_count


@dataclass(frozen=True)
class Matchup:
    round_number: int
    manager1_id: Optional[int]
    manager2_id: Optional[int]

    @property
    def is_bye(self) -> bool:
        return self.manager1_id is None or self.manager2_id is None

    @property
    def bye_manager_id(self) -> Optional[int]:
        if not self.is_bye:
            return None
        return self.manager2_id if self.manager1_id is None else self.manager1_id


def round_robin(manager_ids: Sequence[int]) -> List[List[Matchup]]:
    """Generate one complete round-robin cycle.

    With an odd number of managers a virtual BYE participant is inserted. Each
    real manager therefore receives exactly one BYE during a complete cycle.
    """
    validate_manager_count(manager_ids)
    participants: List[Optional[int]] = list(manager_ids)
    if len(participants) % 2:
        participants.append(None)

    rounds: List[List[Matchup]] = []
    participant_count = len(participants)

    for round_index in range(participant_count - 1):
        matchups: List[Matchup] = []
        for pair_index in range(participant_count // 2):
            left = participants[pair_index]
            right = participants[-(pair_index + 1)]
            matchups.append(
                Matchup(
                    round_number=round_index + 1,
                    manager1_id=left,
                    manager2_id=right,
                )
            )
        rounds.append(matchups)

        participants = [participants[0], participants[-1], *participants[1:-1]]

    return rounds
