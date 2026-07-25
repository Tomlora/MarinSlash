from __future__ import annotations

from collections import Counter
from typing import Iterable, Sequence

from .models import PlayerRole, RosterEntry, RosterSlot, STARTER_SLOTS


EXPECTED_PLAYER_COUNT = 8
EXPECTED_BENCH_COUNT = 3


class RosterValidationError(ValueError):
    pass


def _expected_role(slot: RosterSlot) -> PlayerRole:
    return PlayerRole(slot.value)


def validate_lineup(entries: Iterable[RosterEntry]) -> None:
    """Validate the five starters and the mandatory two-competition rule."""
    entries = list(entries)
    starters = [entry for entry in entries if entry.slot in STARTER_SLOTS]

    slot_counts = Counter(entry.slot for entry in starters)
    missing = [slot.value for slot in STARTER_SLOTS if slot_counts[slot] != 1]
    if missing:
        raise RosterValidationError(
            "Lineup must contain exactly one starter for each role: " + ", ".join(missing)
        )

    for entry in starters:
        if entry.player is None:
            raise RosterValidationError("Starter slots require player assets")
        if entry.player.role != _expected_role(entry.slot):
            raise RosterValidationError(
                f"{entry.player.handle} cannot start at {entry.slot.value}: "
                f"player role is {entry.player.role.value}"
            )

    competitions = {entry.player.competition for entry in starters if entry.player is not None}
    if len(competitions) < 2:
        raise RosterValidationError(
            "The five starters must represent at least two competitions"
        )


def validate_final_roster(entries: Sequence[RosterEntry]) -> None:
    """Validate the complete 5 starters + team + 3 bench roster."""
    if len(entries) != 9:
        raise RosterValidationError("A completed roster must contain exactly 9 assets")

    players = [entry.player for entry in entries if entry.player is not None]
    teams = [entry.team for entry in entries if entry.team is not None]
    benches = [entry for entry in entries if entry.slot == RosterSlot.BENCH]

    if len(players) != EXPECTED_PLAYER_COUNT:
        raise RosterValidationError("A completed roster must contain exactly 8 players")
    if len(teams) != 1:
        raise RosterValidationError("A completed roster must contain exactly 1 team")
    if len(benches) != EXPECTED_BENCH_COUNT:
        raise RosterValidationError("A completed roster must contain exactly 3 bench players")

    player_ids = [player.player_id for player in players]
    if len(set(player_ids)) != len(player_ids):
        raise RosterValidationError("A player cannot appear twice in the same roster")

    validate_lineup(entries)


def required_slots_remaining(entries: Iterable[RosterEntry]) -> set[str]:
    """Return mandatory slots that still need to be filled during the draft."""
    entries = list(entries)
    occupied_starters = {entry.slot for entry in entries if entry.slot in STARTER_SLOTS}
    missing = {slot.value for slot in STARTER_SLOTS if slot not in occupied_starters}

    if not any(entry.slot == RosterSlot.TEAM for entry in entries):
        missing.add(RosterSlot.TEAM.value)

    bench_count = sum(entry.slot == RosterSlot.BENCH for entry in entries)
    for bench_index in range(bench_count, EXPECTED_BENCH_COUNT):
        missing.add(f"BENCH_{bench_index + 1}")

    return missing
