from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Iterable, Sequence

import aiohttp

from ..models import Competition
from .base import ProviderMatch, ScheduleProvider


LEAGUEPEDIA_API = "https://lol.fandom.com/api.php"
LOLESPORTS_API = "https://esports-api.lolesports.com/persisted/gw"

# Public frontend key used by the LoL Esports persisted API. It can be
# overridden without code changes if Riot rotates it.
DEFAULT_LOLESPORTS_API_KEY = "0TvQnueqKa5mxJntVWt0w4LpLfEkrV1Ta8rQBb9Z"

LEAGUEPEDIA_NAMES = {
    Competition.LEC: ("LoL EMEA Championship",),
    Competition.LCS: (
        "League Championship Series",
        "League of Legends Championship Series",
    ),
    Competition.LFL: ("La Ligue Française",),
}

RIOT_SLUGS = {
    Competition.LEC: "lec",
    Competition.LCS: "lcs",
    Competition.LFL: "lfl",
}


class ScheduleProviderError(RuntimeError):
    pass


def _normalise_competitions(
    competitions: Iterable[Competition],
) -> tuple[Competition, ...]:
    values = tuple(dict.fromkeys(Competition(value) for value in competitions))
    if not values:
        raise ScheduleProviderError("Aucun championnat demandé.")
    return values


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class LeaguepediaScheduleProvider(ScheduleProvider):
    """Fetch schedule in one Cargo request for all requested competitions."""

    def __init__(self, *, timeout_seconds: int = 30):
        self.timeout_seconds = timeout_seconds

    async def fetch_schedule(
        self,
        competitions: Iterable[Competition],
        start: datetime,
        end: datetime,
    ) -> Sequence[ProviderMatch]:
        requested = _normalise_competitions(competitions)
        if start.tzinfo is None or end.tzinfo is None:
            raise ScheduleProviderError("Les bornes du calendrier doivent être timezone-aware.")
        if end <= start:
            raise ScheduleProviderError("La fin du calendrier doit être après le début.")

        league_names = []
        reverse_names: dict[str, Competition] = {}
        for competition in requested:
            for name in LEAGUEPEDIA_NAMES.get(competition, ()):
                league_names.append("'" + name.replace("'", "''") + "'")
                reverse_names[name] = competition

        if not league_names:
            raise ScheduleProviderError("Aucun championnat Leaguepedia supporté.")

        start_utc = start.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        end_utc = end.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        params = {
            "action": "cargoquery",
            "format": "json",
            "tables": "MatchSchedule=MS,Tournaments=T",
            "fields": (
                "T.League=League,T.Name=Tournament,MS.MatchId=MatchId,"
                "MS.DateTime_UTC=DateTimeUTC,MS.Team1=Team1,MS.Team2=Team2,MS.Winner=Winner"
            ),
            "where": (
                f"MS.DateTime_UTC >= '{start_utc}' "
                f"AND MS.DateTime_UTC < '{end_utc}' "
                f"AND T.League IN ({','.join(league_names)})"
            ),
            "join_on": "MS.OverviewPage=T.OverviewPage",
            "order_by": "MS.DateTime_UTC ASC",
            "limit": "1000",
        }

        timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
        headers = {"User-Agent": "MarinSlash-Fantasy/1.0 (Leaguepedia schedule sync)"}
        try:
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                async with session.get(LEAGUEPEDIA_API, params=params) as response:
                    if response.status == 429:
                        raise ScheduleProviderError("Leaguepedia est rate-limitée (HTTP 429).")
                    if response.status >= 400:
                        raise ScheduleProviderError(
                            f"Leaguepedia a répondu HTTP {response.status}."
                        )
                    payload = await response.json(content_type=None)
        except aiohttp.ClientError as exc:
            raise ScheduleProviderError(
                f"Impossible de joindre Leaguepedia : {type(exc).__name__}."
            ) from exc

        if not isinstance(payload, dict):
            raise ScheduleProviderError("Réponse Leaguepedia invalide.")
        if "error" in payload:
            error = payload.get("error") or {}
            raise ScheduleProviderError(
                "Leaguepedia a refusé la requête "
                f"({error.get('code', 'unknown')}) : {error.get('info', '')}".strip()
            )

        raw_rows = payload.get("cargoquery")
        if not isinstance(raw_rows, list):
            raise ScheduleProviderError("Leaguepedia n'a pas retourné de résultat Cargo valide.")

        matches: list[ProviderMatch] = []
        for item in raw_rows:
            title = item.get("title", {}) if isinstance(item, dict) else {}
            if not isinstance(title, dict):
                continue
            competition = reverse_names.get(str(title.get("League") or ""))
            if competition is None:
                continue
            raw_date = str(title.get("DateTimeUTC") or "").strip()
            if not raw_date:
                continue
            try:
                scheduled_at = _parse_datetime(raw_date)
            except ValueError:
                continue
            team1 = str(title.get("Team1") or "").strip() or None
            team2 = str(title.get("Team2") or "").strip() or None
            match_id = str(title.get("MatchId") or "").strip()
            if not match_id:
                match_id = f"{competition.value}:{scheduled_at.isoformat()}:{team1}:{team2}"
            winner = str(title.get("Winner") or "").strip()
            matches.append(
                ProviderMatch(
                    external_id=f"leaguepedia:{match_id}",
                    competition=competition,
                    tournament=str(title.get("Tournament") or "").strip() or None,
                    scheduled_at_utc=scheduled_at,
                    team1_external_id=team1,
                    team2_external_id=team2,
                    status="completed" if winner else "scheduled",
                )
            )
        return matches


class RiotEsportsScheduleProvider(ScheduleProvider):
    """Fallback using Riot's LoL Esports persisted frontend API."""

    def __init__(self, *, timeout_seconds: int = 30, api_key: str | None = None):
        self.timeout_seconds = timeout_seconds
        self.api_key = (
            api_key
            or os.environ.get("FANTASY_LOLESPORTS_API_KEY")
            or DEFAULT_LOLESPORTS_API_KEY
        )

    async def _get_json(self, session: aiohttp.ClientSession, endpoint: str, params):
        async with session.get(f"{LOLESPORTS_API}/{endpoint}", params=params) as response:
            if response.status == 429:
                raise ScheduleProviderError("LoL Esports est rate-limitée (HTTP 429).")
            if response.status >= 400:
                raise ScheduleProviderError(
                    f"LoL Esports a répondu HTTP {response.status} sur {endpoint}."
                )
            return await response.json(content_type=None)

    async def fetch_schedule(
        self,
        competitions: Iterable[Competition],
        start: datetime,
        end: datetime,
    ) -> Sequence[ProviderMatch]:
        requested = _normalise_competitions(competitions)
        if start.tzinfo is None or end.tzinfo is None:
            raise ScheduleProviderError("Les bornes du calendrier doivent être timezone-aware.")
        if end <= start:
            raise ScheduleProviderError("La fin du calendrier doit être après le début.")

        timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
        headers = {
            "User-Agent": "MarinSlash-Fantasy/1.0 (LoL Esports schedule fallback)",
            "x-api-key": self.api_key,
        }
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            leagues_payload = await self._get_json(session, "getLeagues", {"hl": "en-US"})
            leagues = ((leagues_payload or {}).get("data") or {}).get("leagues") or []
            slug_to_league = {
                str(league.get("slug") or "").lower(): league
                for league in leagues
                if isinstance(league, dict)
            }

            league_ids: list[str] = []
            id_to_competition: dict[str, Competition] = {}
            missing: list[str] = []
            for competition in requested:
                slug = RIOT_SLUGS.get(competition)
                league = slug_to_league.get(slug or "")
                if not league or not league.get("id"):
                    missing.append(competition.value)
                    continue
                league_id = str(league["id"])
                league_ids.append(league_id)
                id_to_competition[league_id] = competition

            if missing:
                raise ScheduleProviderError(
                    "LoL Esports ne fournit pas les ligues demandées : " + ", ".join(missing)
                )

            base_params: list[tuple[str, str]] = [("hl", "en-US")]
            base_params.extend(("leagueId", league_id) for league_id in league_ids)

            events_by_id: dict[str, dict] = {}
            page_token: str | None = None
            # The initial page is generally centred around the current schedule.
            # Follow a few newer pages so a 21-day Fantasy window is not silently
            # truncated when several leagues are requested together.
            for _ in range(6):
                params = list(base_params)
                if page_token:
                    params.append(("pageToken", page_token))
                payload = await self._get_json(session, "getSchedule", params)
                schedule = ((payload or {}).get("data") or {}).get("schedule") or {}
                events = schedule.get("events") or []
                page_max: datetime | None = None
                for event in events:
                    if not isinstance(event, dict):
                        continue
                    event_id = str(event.get("id") or (event.get("match") or {}).get("id") or "")
                    if event_id:
                        events_by_id[event_id] = event
                    raw_start = event.get("startTime")
                    if raw_start:
                        try:
                            event_time = _parse_datetime(str(raw_start))
                        except ValueError:
                            event_time = None
                        if event_time is not None and (page_max is None or event_time > page_max):
                            page_max = event_time

                if page_max is not None and page_max >= end.astimezone(timezone.utc):
                    break
                newer = (schedule.get("pages") or {}).get("newer")
                newer = str(newer or "").strip()
                if not newer or newer == page_token:
                    break
                page_token = newer

        matches: list[ProviderMatch] = []
        for event in events_by_id.values():
            if event.get("type") != "match":
                continue
            raw_start = event.get("startTime")
            if not raw_start:
                continue
            try:
                scheduled_at = _parse_datetime(str(raw_start))
            except ValueError:
                continue
            if scheduled_at < start.astimezone(timezone.utc) or scheduled_at >= end.astimezone(timezone.utc):
                continue

            league = event.get("league") or {}
            league_id = str(league.get("id") or "")
            competition = id_to_competition.get(league_id)
            if competition is None:
                slug = str(league.get("slug") or "").lower()
                competition = next(
                    (comp for comp, expected_slug in RIOT_SLUGS.items() if expected_slug == slug),
                    None,
                )
            if competition not in requested:
                continue

            match = event.get("match") or {}
            raw_teams = match.get("teams") or []
            team_names = [
                str(team.get("name") or team.get("code") or team.get("slug") or "").strip()
                for team in raw_teams
                if isinstance(team, dict)
            ]
            team1 = team_names[0] if len(team_names) > 0 and team_names[0] else None
            team2 = team_names[1] if len(team_names) > 1 and team_names[1] else None
            state = str(event.get("state") or "").lower()
            status = {
                "completed": "completed",
                "inprogress": "live",
                "in_progress": "live",
                "unstarted": "scheduled",
            }.get(state, "scheduled")
            event_id = str(event.get("id") or match.get("id") or "").strip()
            if not event_id:
                event_id = f"{competition.value}:{scheduled_at.isoformat()}:{team1}:{team2}"

            matches.append(
                ProviderMatch(
                    external_id=f"lolesports:{event_id}",
                    competition=competition,
                    tournament=str(event.get("blockName") or "").strip() or None,
                    scheduled_at_utc=scheduled_at,
                    team1_external_id=team1,
                    team2_external_id=team2,
                    status=status,
                )
            )
        return matches


class FallbackScheduleProvider(ScheduleProvider):
    """Try providers in order; useful for Cargo -> LoL Esports failover."""

    def __init__(self, *providers: ScheduleProvider):
        if not providers:
            raise ValueError("Au moins un provider calendrier est requis.")
        self.providers = providers
        self.last_provider_name: str | None = None
        self.errors: tuple[str, ...] = ()

    async def fetch_schedule(
        self,
        competitions: Iterable[Competition],
        start: datetime,
        end: datetime,
    ) -> Sequence[ProviderMatch]:
        requested = tuple(competitions)
        errors: list[str] = []
        for provider in self.providers:
            try:
                matches = await provider.fetch_schedule(requested, start, end)
                self.last_provider_name = type(provider).__name__
                self.errors = tuple(errors)
                return matches
            except Exception as exc:
                errors.append(f"{type(provider).__name__}: {exc}")

        self.errors = tuple(errors)
        raise ScheduleProviderError(
            "Tous les providers calendrier ont échoué : " + " | ".join(errors)
        )
