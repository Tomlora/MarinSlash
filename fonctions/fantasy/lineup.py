"""Post-draft lineups. Every write and its history share one transaction."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import text

from .database import transaction
from .freshness import stale_competitions
from .locks import PARIS_TIMEZONE, ScheduledMatch, locked_competitions
from .models import Competition, PlayerAsset, PlayerRole, RosterEntry, RosterSlot, TeamAsset
from .roster import RosterValidationError, promote_bench_player
from .service import FantasyServiceError, _current_season_row, _league_row


@dataclass(frozen=True)
class LineupView:
    league_name: str
    season_name: str
    entries: tuple[RosterEntry, ...]
    locked: frozenset[Competition]
    unavailable_players: frozenset[int]
    stale: frozenset[Competition] = frozenset()


def _context(connection, league_id, guild_id, discord_user_id, *, editing=False):
    # Same league lock as draft/join: queued changes re-read committed slots.
    league = _league_row(connection, league_id, guild_id, for_update=editing)
    if editing and league.status != "active":
        raise FantasyServiceError("Les remplacements nécessitent une Fantasy active après la draft.")
    season = _current_season_row(connection, league_id)
    manager = connection.execute(text("""
        SELECT id FROM fantasy.manager
        WHERE league_id = :league_id AND discord_user_id = :discord_user_id
    """), {"league_id": league_id, "discord_user_id": discord_user_id}).first()
    if manager is None:
        raise FantasyServiceError("Tu n'es pas inscrit dans cette Fantasy.")
    return league, season, int(manager.id)


def _load_entries(connection, season_id, manager_id, now):
    rows = connection.execute(text("""
        SELECT r.slot, p.id AS player_id, p.handle, p.role, p.active,
               tenure.competition_code AS player_competition,
               tenure.current_team, t.id AS team_id, t.name AS team_name,
               t.competition_code AS team_competition
        FROM fantasy.roster_asset r
        LEFT JOIN fantasy.pro_player p ON p.id = r.player_id
        LEFT JOIN LATERAL (
            SELECT team.competition_code,
                   (team.active AND (h.valid_until IS NULL OR h.valid_until > :now)) AS current_team
            FROM fantasy.pro_player_team_history h
            JOIN fantasy.pro_team team ON team.id = h.team_id
            WHERE h.player_id = p.id AND h.valid_from <= :now
            ORDER BY h.valid_from DESC, h.id DESC LIMIT 1
        ) tenure ON TRUE
        LEFT JOIN fantasy.pro_team t ON t.id = r.team_id
        WHERE r.season_id = :season_id AND r.manager_id = :manager_id
        ORDER BY r.id
    """), {"season_id": season_id, "manager_id": manager_id, "now": now}).all()
    if not rows:
        raise FantasyServiceError("Ton roster sera disponible une fois la draft terminée.")
    entries, unavailable = [], set()
    for row in rows:
        if row.player_id is not None:
            if row.player_competition is None:
                raise FantasyServiceError(
                    f"Championnat inconnu pour {row.handle} : une synchronisation du pool est nécessaire."
                )
            if not row.active or not row.current_team:
                unavailable.add(int(row.player_id))
            entries.append(RosterEntry(RosterSlot(row.slot), player=PlayerAsset(
                int(row.player_id), row.handle, PlayerRole(row.role), Competition(row.player_competition)
            )))
        else:
            entries.append(RosterEntry(RosterSlot(row.slot), team=TeamAsset(
                int(row.team_id), row.team_name, Competition(row.team_competition)
            )))
    return entries, frozenset(unavailable)


def _locks(connection, now):
    paris = ZoneInfo(PARIS_TIMEZONE)
    day = now.astimezone(paris).date()
    start = datetime.combine(day, time.min, tzinfo=paris)
    end = datetime.combine(day + timedelta(days=1), time.min, tzinfo=paris)
    rows = connection.execute(text("""
        SELECT competition_code, scheduled_at_utc, status FROM fantasy.match_schedule
        WHERE scheduled_at_utc >= :start AND scheduled_at_utc < :end
    """), {"start": start, "end": end}).all()
    return frozenset(locked_competitions([
        ScheduledMatch(Competition(r.competition_code), r.scheduled_at_utc, r.status)
        for r in rows
    ], now=now))


def get_lineup(*, league_id: int, guild_id: int, discord_user_id: int) -> LineupView:
    with transaction() as connection:
        league, season, manager_id = _context(connection, league_id, guild_id, discord_user_id)
        now = connection.execute(text("SELECT clock_timestamp()")).scalar_one()
        entries, unavailable = _load_entries(connection, int(season.id), manager_id, now)
        return LineupView(league.name, season.name, tuple(entries), _locks(connection, now), unavailable,
                          stale_competitions(connection, now))


def set_starter(*, league_id: int, guild_id: int, discord_user_id: int, player_id: int) -> LineupView:
    with transaction() as connection:
        league, season, manager_id = _context(
            connection, league_id, guild_id, discord_user_id, editing=True
        )
        # Prevent pool/calendar sync from changing eligibility during validation.
        # SHARE also covers new schedule rows, which row locks cannot protect.
        connection.execute(text("""
            LOCK TABLE fantasy.pro_team, fantasy.pro_player,
                       fantasy.pro_player_team_history, fantasy.match_schedule,
                       fantasy.schedule_coverage IN SHARE MODE
        """))
        # Read the clock after lock waits, including waits across Paris midnight.
        now = connection.execute(text("SELECT clock_timestamp()")).scalar_one()
        entries, unavailable = _load_entries(connection, int(season.id), manager_id, now)
        if player_id in unavailable:
            raise FantasyServiceError("Ce joueur n'est plus actif dans le pool synchronisé.")
        locked = _locks(connection, now)
        stale = stale_competitions(connection, now)
        try:
            updated = promote_bench_player(entries, player_id, locked)
        except RosterValidationError as exc:
            raise FantasyServiceError(str(exc)) from exc
        changes = [(old, new) for old, new in zip(entries, updated) if old.slot != new.slot]
        if any(old.player.competition in stale for old, new in changes):
            raise FantasyServiceError(
                "Calendrier trop ancien ou non vérifié pour ce remplacement. "
                "Un administrateur doit lancer /fantasy_update_schedule."
            )
        # Free the starter slot before promoting the bench player (unique index).
        changes.sort(key=lambda pair: pair[1].slot != RosterSlot.BENCH)
        for old, new in changes:
            params = {"season_id": int(season.id), "manager_id": manager_id,
                      "player_id": new.player.player_id, "slot": new.slot.value,
                      "old_slot": old.slot.value, "now": now}
            result = connection.execute(text("""
                UPDATE fantasy.roster_history SET valid_until = :now
                WHERE season_id = :season_id AND manager_id = :manager_id
                  AND player_id = :player_id AND slot = :old_slot AND valid_until IS NULL
            """), params)
            if result.rowcount != 1:
                raise FantasyServiceError("Historique du roster incohérent : remplacement annulé.")
            connection.execute(text("""
                UPDATE fantasy.roster_asset SET slot = :slot
                WHERE season_id = :season_id AND manager_id = :manager_id AND player_id = :player_id
            """), params)
            connection.execute(text("""
                INSERT INTO fantasy.roster_history
                    (season_id, manager_id, player_id, slot, valid_from, reason)
                VALUES (:season_id, :manager_id, :player_id, :slot, :now, 'lineup')
            """), params)
        return LineupView(league.name, season.name, tuple(updated), locked, unavailable, stale)
