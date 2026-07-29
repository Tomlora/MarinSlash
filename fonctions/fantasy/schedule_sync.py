from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.engine import Connection

from .database import transaction
from .models import Competition
from .providers.base import ProviderMatch, ScheduleProvider


class FantasyScheduleSyncError(RuntimeError):
    pass


@dataclass(frozen=True)
class ScheduleSyncResult:
    matches_seen: int
    competitions_updated: tuple[Competition, ...]
    teams_resolved: int
    teams_unresolved: int


def _slug(value: str | None) -> str:
    if not value:
        return "unknown"
    result = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return result or "unknown"


def _canonical_external_id(match: ProviderMatch) -> str:
    scheduled = match.scheduled_at_utc.astimezone(timezone.utc).replace(second=0, microsecond=0)
    return (
        f"fantasy:{match.competition.value}:{scheduled.isoformat()}:"
        f"{_slug(match.team1_external_id)}:{_slug(match.team2_external_id)}"
    )


def _resolve_team_id(
    connection: Connection, competition: Competition, external_or_name: str | None
) -> int | None:
    value = (external_or_name or "").strip()
    if not value:
        return None
    row = connection.execute(
        text(
            """
            SELECT id
            FROM fantasy.pro_team
            WHERE competition_code = :competition
              AND active = TRUE
              AND (
                    external_id = :value
                 OR LOWER(name) = LOWER(:value)
                 OR LOWER(COALESCE(short_name, '')) = LOWER(:value)
              )
            ORDER BY
                CASE
                    WHEN external_id = :value THEN 0
                    WHEN LOWER(name) = LOWER(:value) THEN 1
                    ELSE 2
                END,
                id
            LIMIT 1
            """
        ),
        {"competition": competition.value, "value": value},
    ).first()
    return int(row.id) if row is not None else None


async def sync_schedule(
    provider: ScheduleProvider,
    *,
    start: datetime,
    end: datetime,
    competitions: tuple[Competition, ...] = (
        Competition.LEC,
        Competition.LCS,
        Competition.LFL,
    ),
) -> ScheduleSyncResult:
    if start.tzinfo is None or end.tzinfo is None:
        raise FantasyScheduleSyncError("Les bornes du calendrier doivent être timezone-aware.")
    if end <= start:
        raise FantasyScheduleSyncError("La fin du calendrier doit être après le début.")

    matches = list(await provider.fetch_schedule(competitions, start, end))
    if not matches:
        raise FantasyScheduleSyncError(
            "Aucun match retourné dans la fenêtre demandée ; calendrier laissé inchangé."
        )

    valid_competitions = set(competitions)
    matches = [match for match in matches if match.competition in valid_competitions]
    if not matches:
        raise FantasyScheduleSyncError("Le provider n'a retourné aucun championnat supporté.")

    competitions_updated = tuple(sorted({match.competition for match in matches}, key=lambda c: c.value))
    teams_resolved = 0
    teams_unresolved = 0

    with transaction() as connection:
        # Replace only mutable rows for competitions for which the provider gave
        # us actual data. Completed rows are preserved for history/scoring.
        connection.execute(
            text(
                """
                DELETE FROM fantasy.match_schedule
                WHERE competition_code = ANY(:competitions)
                  AND scheduled_at_utc >= :start
                  AND scheduled_at_utc < :end
                  AND status <> 'completed'
                """
            ),
            {
                "competitions": [competition.value for competition in competitions_updated],
                "start": start.astimezone(timezone.utc),
                "end": end.astimezone(timezone.utc),
            },
        )

        for match in matches:
            team1_id = _resolve_team_id(
                connection, match.competition, match.team1_external_id
            )
            team2_id = _resolve_team_id(
                connection, match.competition, match.team2_external_id
            )
            for source_value, resolved_id in (
                (match.team1_external_id, team1_id),
                (match.team2_external_id, team2_id),
            ):
                if not source_value:
                    continue
                if resolved_id is None:
                    teams_unresolved += 1
                else:
                    teams_resolved += 1

            connection.execute(
                text(
                    """
                    INSERT INTO fantasy.match_schedule
                        (external_id, competition_code, tournament, scheduled_at_utc,
                         team1_id, team2_id, status, updated_at)
                    VALUES
                        (:external_id, :competition_code, :tournament, :scheduled_at_utc,
                         :team1_id, :team2_id, :status, NOW())
                    ON CONFLICT (external_id) DO UPDATE
                    SET
                        competition_code = EXCLUDED.competition_code,
                        tournament = EXCLUDED.tournament,
                        scheduled_at_utc = EXCLUDED.scheduled_at_utc,
                        team1_id = COALESCE(EXCLUDED.team1_id, fantasy.match_schedule.team1_id),
                        team2_id = COALESCE(EXCLUDED.team2_id, fantasy.match_schedule.team2_id),
                        status = EXCLUDED.status,
                        updated_at = NOW()
                    """
                ),
                {
                    "external_id": _canonical_external_id(match),
                    "competition_code": match.competition.value,
                    "tournament": match.tournament,
                    "scheduled_at_utc": match.scheduled_at_utc.astimezone(timezone.utc),
                    "team1_id": team1_id,
                    "team2_id": team2_id,
                    "status": match.status,
                },
            )

    return ScheduleSyncResult(
        matches_seen=len(matches),
        competitions_updated=competitions_updated,
        teams_resolved=teams_resolved,
        teams_unresolved=teams_unresolved,
    )
