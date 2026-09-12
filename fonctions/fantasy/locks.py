from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Set
from zoneinfo import ZoneInfo

from .models import Competition


PARIS_TIMEZONE = "Europe/Paris"
LOCKABLE_STATUSES = {"scheduled", "live", "completed"}


@dataclass(frozen=True)
class ScheduledMatch:
    competition: Competition
    scheduled_at: datetime
    status: str = "scheduled"


def locked_competitions(
    matches: Iterable[ScheduledMatch],
    now: datetime | None = None,
    timezone_name: str = PARIS_TIMEZONE,
) -> Set[Competition]:
    """Return competitions locked for the current local calendar day.

    A competition is locked for the entire Europe/Paris day when at least one
    non-cancelled match is scheduled on that local date.
    """
    timezone = ZoneInfo(timezone_name)
    now = now or datetime.now(timezone)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone)
    local_day = now.astimezone(timezone).date()

    result: Set[Competition] = set()
    for match in matches:
        if match.status not in LOCKABLE_STATUSES:
            continue
        if match.scheduled_at.tzinfo is None:
            raise ValueError("Match schedule timestamps must be timezone-aware")
        if match.scheduled_at.astimezone(timezone).date() == local_day:
            result.add(match.competition)
    return result


def ensure_competition_unlocked(
    competition: Competition,
    matches: Iterable[ScheduledMatch],
    now: datetime | None = None,
) -> None:
    if competition in locked_competitions(matches, now=now):
        raise ValueError(f"{competition.value} assets are locked for today")
