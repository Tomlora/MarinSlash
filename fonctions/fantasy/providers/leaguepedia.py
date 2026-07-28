from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, Sequence

import aiohttp

from ..models import Competition, PlayerRole
from .base import PlayerProvider, ProviderPlayer, ProviderTeam


LEAGUEPEDIA_API = "https://lol.fandom.com/api.php"

LEAGUE_NAMES = {
    Competition.LEC: "LoL EMEA Championship",
    Competition.LCS: "League Championship Series",
    Competition.LFL: "La Ligue Française",
}

ROLE_MAP = {
    "top": PlayerRole.TOP,
    "jungle": PlayerRole.JUNGLE,
    "jungler": PlayerRole.JUNGLE,
    "mid": PlayerRole.MID,
    "middle": PlayerRole.MID,
    "bot": PlayerRole.ADC,
    "adc": PlayerRole.ADC,
    "ad carry": PlayerRole.ADC,
    "support": PlayerRole.SUPPORT,
}


class LeaguepediaProviderError(RuntimeError):
    pass


class LeaguepediaPlayerProvider(PlayerProvider):
    """Fetch the current LEC/LCS/LFL player pool from Leaguepedia Cargo.

    One provider instance performs at most one HTTP request. ``fetch_teams`` and
    ``fetch_players`` share the parsed response so a database sync does not hit
    Fandom twice.
    """

    def __init__(self, *, timeout_seconds: int = 30):
        self.timeout_seconds = timeout_seconds
        self._cached_competitions: tuple[Competition, ...] | None = None
        self._cached_teams: tuple[ProviderTeam, ...] | None = None
        self._cached_players: tuple[ProviderPlayer, ...] | None = None

    @staticmethod
    def _normalise_competitions(
        competitions: Iterable[Competition],
    ) -> tuple[Competition, ...]:
        values = tuple(dict.fromkeys(Competition(value) for value in competitions))
        if not values:
            raise LeaguepediaProviderError("Aucun championnat demandé.")
        unsupported = [value for value in values if value not in LEAGUE_NAMES]
        if unsupported:
            raise LeaguepediaProviderError(
                "Championnat Leaguepedia non supporté : "
                + ", ".join(value.value for value in unsupported)
            )
        return values

    async def _load(
        self, competitions: Iterable[Competition]
    ) -> tuple[tuple[ProviderTeam, ...], tuple[ProviderPlayer, ...]]:
        requested = self._normalise_competitions(competitions)
        if (
            self._cached_competitions == requested
            and self._cached_teams is not None
            and self._cached_players is not None
        ):
            return self._cached_teams, self._cached_players

        league_values = ",".join(
            "'" + LEAGUE_NAMES[competition].replace("'", "''") + "'"
            for competition in requested
        )
        year = datetime.now(timezone.utc).year

        params = {
            "action": "cargoquery",
            "format": "json",
            "tables": "Tournaments=Tor,TournamentPlayers=TP,PlayerRedirects=PR,Players=P,Teams=Tm",
            "fields": (
                "Tor.League=League,Tor.DateStart=DateStart,"
                "TP.Team=TournamentTeam,TP.Player=TournamentPlayer,TP.Role=TournamentRole,"
                "P.Player=Player,P.OverviewPage=PlayerPage,P.Team=CurrentTeam,"
                "Tm.Short=TeamShort"
            ),
            "where": (
                f"Tor.League IN ({league_values}) "
                f"AND Tor.DateStart >= '{year}-01-01' "
                "AND TP.Role IN ('Top','Jungle','Mid','Bot','Support') "
                "AND P.Team=TP.Team"
            ),
            "join_on": (
                "Tor.OverviewPage=TP.OverviewPage,"
                "TP.Player=PR.AllName,"
                "PR.OverviewPage=P.OverviewPage,"
                "P.Team=Tm.OverviewPage"
            ),
            "order_by": "Tor.DateStart DESC",
            "limit": "1000",
        }

        timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
        headers = {
            "User-Agent": "MarinSlash-Fantasy/1.0 (Leaguepedia roster sync)"
        }
        try:
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                async with session.get(LEAGUEPEDIA_API, params=params) as response:
                    if response.status == 429:
                        raise LeaguepediaProviderError(
                            "Leaguepedia/Fandom refuse temporairement la requête (rate limit)."
                        )
                    if response.status >= 400:
                        raise LeaguepediaProviderError(
                            f"Leaguepedia a répondu HTTP {response.status}."
                        )
                    payload = await response.json(content_type=None)
        except aiohttp.ClientError as exc:
            raise LeaguepediaProviderError(
                f"Impossible de joindre Leaguepedia : {type(exc).__name__}."
            ) from exc

        if not isinstance(payload, dict):
            raise LeaguepediaProviderError("Réponse Leaguepedia invalide.")
        if "error" in payload:
            error = payload.get("error") or {}
            code = error.get("code", "unknown")
            info = error.get("info", "")
            raise LeaguepediaProviderError(
                f"Leaguepedia a refusé la requête ({code}) : {info}".strip()
            )

        raw_rows = payload.get("cargoquery")
        if not isinstance(raw_rows, list):
            raise LeaguepediaProviderError("Leaguepedia n'a retourné aucun résultat Cargo.")

        teams, players = self._parse_rows(raw_rows, requested)
        self._cached_competitions = requested
        self._cached_teams = teams
        self._cached_players = players
        return teams, players

    @staticmethod
    def _parse_rows(
        raw_rows: list[dict], requested: Sequence[Competition]
    ) -> tuple[tuple[ProviderTeam, ...], tuple[ProviderPlayer, ...]]:
        reverse_leagues = {name: competition for competition, name in LEAGUE_NAMES.items()}
        requested_set = set(requested)

        # Cargo rows are ordered newest tournament first. Keep the first valid
        # occurrence for a player so transfers/role swaps favour the newest event.
        teams: dict[tuple[Competition, str], ProviderTeam] = {}
        players: dict[str, ProviderPlayer] = {}

        for item in raw_rows:
            title = item.get("title", {}) if isinstance(item, dict) else {}
            if not isinstance(title, dict):
                continue

            competition = reverse_leagues.get(str(title.get("League") or ""))
            if competition not in requested_set:
                continue

            current_team = str(title.get("CurrentTeam") or "").strip()
            player_page = str(title.get("PlayerPage") or "").strip()
            handle = str(title.get("Player") or title.get("TournamentPlayer") or "").strip()
            role_text = str(title.get("TournamentRole") or "").strip().lower()
            role = ROLE_MAP.get(role_text)
            if not current_team or not player_page or not handle or role is None:
                continue

            team_key = (competition, current_team)
            if team_key not in teams:
                short_name = str(title.get("TeamShort") or "").strip() or None
                teams[team_key] = ProviderTeam(
                    external_id=current_team,
                    name=current_team,
                    short_name=short_name,
                    competition=competition,
                )

            if player_page not in players:
                players[player_page] = ProviderPlayer(
                    external_id=player_page,
                    handle=handle,
                    role=role,
                    team_external_id=current_team,
                    competition=competition,
                )

        return tuple(teams.values()), tuple(players.values())

    async def fetch_teams(
        self, competitions: Iterable[Competition]
    ) -> Sequence[ProviderTeam]:
        teams, _ = await self._load(competitions)
        return teams

    async def fetch_players(
        self, competitions: Iterable[Competition]
    ) -> Sequence[ProviderPlayer]:
        _, players = await self._load(competitions)
        return players
