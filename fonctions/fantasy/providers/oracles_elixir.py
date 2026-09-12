from __future__ import annotations

import asyncio
import csv
import os
import re
import tempfile
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Iterable, Sequence

import aiohttp

from ..models import Competition, PlayerRole
from .base import PlayerProvider, ProviderPlayer, ProviderTeam


OE_DATA_URL_TEMPLATE = (
    "https://oe-datasets.s3.us-west-2.amazonaws.com/LoL/"
    "{year}_LoL_esports_match_data_from_OraclesElixir.csv"
)

LEAGUE_MAP = {
    "LEC": Competition.LEC,
    "LCS": Competition.LCS,
    "LFL": Competition.LFL,
}

ROLE_MAP = {
    "top": PlayerRole.TOP,
    "jng": PlayerRole.JUNGLE,
    "jungle": PlayerRole.JUNGLE,
    "mid": PlayerRole.MID,
    "middle": PlayerRole.MID,
    "bot": PlayerRole.ADC,
    "adc": PlayerRole.ADC,
    "sup": PlayerRole.SUPPORT,
    "support": PlayerRole.SUPPORT,
}

# Oracle's Elixir is match data rather than an administrative roster registry.
# A team is therefore considered current if it played close to the latest match
# available for its league. A player is considered current if their latest game
# is recent relative to that team's latest game.
ACTIVE_TEAM_MAX_AGE_DAYS = 45
ACTIVE_PLAYER_MAX_AGE_DAYS = 28


class OracleElixirProviderError(RuntimeError):
    pass


def _slug(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return value or "unknown"


def _parse_datetime(value: str) -> datetime | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        pass

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _team_external_id(competition: Competition, row: dict[str, str]) -> str:
    team_id = (row.get("teamid") or "").strip()
    if team_id:
        return team_id
    team_name = (row.get("teamname") or "").strip()
    return f"oe-team:{competition.value}:{_slug(team_name)}"


def _player_external_id(competition: Competition, row: dict[str, str]) -> str:
    player_id = (row.get("playerid") or "").strip()
    if player_id:
        return player_id
    player_name = (row.get("playername") or "").strip()
    return f"oe-player:{competition.value}:{_slug(player_name)}"


class OracleElixirPlayerProvider(PlayerProvider):
    """Build the active LEC/LCS/LFL pool from Oracle's Elixir match data.

    The provider downloads the current-year CSV once, keeps only player rows for
    the requested leagues, then derives the most recent team / role appearance.
    It intentionally favours players who actually appeared in recent games;
    announced transfers and unused substitutes cannot be inferred until they
    appear in Oracle's Elixir data.
    """

    def __init__(self, *, timeout_seconds: int = 120, data_url: str | None = None):
        year = datetime.now(timezone.utc).year
        self.data_url = (
            data_url
            or os.environ.get("FANTASY_OE_DATA_URL")
            or OE_DATA_URL_TEMPLATE.format(year=year)
        )
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
            raise OracleElixirProviderError("Aucun championnat demandé.")
        unsupported = [value for value in values if value.value not in LEAGUE_MAP]
        if unsupported:
            raise OracleElixirProviderError(
                "Championnat Oracle's Elixir non supporté : "
                + ", ".join(value.value for value in unsupported)
            )
        return values

    async def _download(self) -> str:
        timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
        headers = {"User-Agent": "MarinSlash-Fantasy/1.0 (OracleElixir roster sync)"}
        fd, path = tempfile.mkstemp(prefix="marinslash_oe_", suffix=".csv")
        os.close(fd)
        try:
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                async with session.get(self.data_url) as response:
                    if response.status >= 400:
                        raise OracleElixirProviderError(
                            f"Oracle's Elixir a répondu HTTP {response.status}."
                        )
                    with open(path, "wb") as output:
                        async for chunk in response.content.iter_chunked(1024 * 1024):
                            output.write(chunk)
            return path
        except aiohttp.ClientError as exc:
            try:
                os.remove(path)
            except OSError:
                pass
            raise OracleElixirProviderError(
                f"Impossible de télécharger Oracle's Elixir : {type(exc).__name__}."
            ) from exc

    @staticmethod
    def _parse_file(
        path: str, requested: tuple[Competition, ...]
    ) -> tuple[tuple[ProviderTeam, ...], tuple[ProviderPlayer, ...]]:
        requested_set = set(requested)
        league_latest: dict[Competition, datetime] = {}
        team_latest: dict[tuple[Competition, str], datetime] = {}
        team_names: dict[tuple[Competition, str], str] = {}
        latest_player_row: dict[str, tuple[datetime, Competition, str, str, PlayerRole]] = {}

        try:
            with open(path, "r", encoding="utf-8-sig", newline="") as source:
                reader = csv.DictReader(source)
                required = {"league", "date", "position", "playername", "teamname"}
                missing = required.difference(reader.fieldnames or [])
                if missing:
                    raise OracleElixirProviderError(
                        "Dataset Oracle's Elixir incompatible, colonnes manquantes : "
                        + ", ".join(sorted(missing))
                    )

                for row in reader:
                    competition = LEAGUE_MAP.get((row.get("league") or "").strip().upper())
                    if competition not in requested_set:
                        continue

                    role = ROLE_MAP.get((row.get("position") or "").strip().lower())
                    if role is None:
                        continue

                    handle = (row.get("playername") or "").strip()
                    team_name = (row.get("teamname") or "").strip()
                    played_at = _parse_datetime(row.get("date") or "")
                    if not handle or not team_name or played_at is None:
                        continue

                    team_external_id = _team_external_id(competition, row)
                    player_external_id = _player_external_id(competition, row)
                    team_key = (competition, team_external_id)

                    team_names[team_key] = team_name
                    if played_at > team_latest.get(team_key, datetime.min.replace(tzinfo=timezone.utc)):
                        team_latest[team_key] = played_at
                    if played_at > league_latest.get(
                        competition, datetime.min.replace(tzinfo=timezone.utc)
                    ):
                        league_latest[competition] = played_at

                    previous = latest_player_row.get(player_external_id)
                    if previous is None or played_at > previous[0]:
                        latest_player_row[player_external_id] = (
                            played_at,
                            competition,
                            team_external_id,
                            handle,
                            role,
                        )
        except UnicodeDecodeError as exc:
            raise OracleElixirProviderError(
                "Le dataset Oracle's Elixir téléchargé n'est pas un CSV UTF-8 valide."
            ) from exc

        active_teams: dict[tuple[Competition, str], ProviderTeam] = {}
        for team_key, last_game in team_latest.items():
            competition, external_id = team_key
            latest_for_league = league_latest.get(competition)
            if latest_for_league is None:
                continue
            if latest_for_league - last_game > timedelta(days=ACTIVE_TEAM_MAX_AGE_DAYS):
                continue
            active_teams[team_key] = ProviderTeam(
                external_id=external_id,
                name=team_names[team_key],
                short_name=None,
                competition=competition,
            )

        players: dict[str, ProviderPlayer] = {}
        for external_id, (
            last_game,
            competition,
            team_external_id,
            handle,
            role,
        ) in latest_player_row.items():
            team_key = (competition, team_external_id)
            latest_for_team = team_latest.get(team_key)
            if team_key not in active_teams or latest_for_team is None:
                continue
            if latest_for_team - last_game > timedelta(days=ACTIVE_PLAYER_MAX_AGE_DAYS):
                continue
            players[external_id] = ProviderPlayer(
                external_id=external_id,
                handle=handle,
                role=role,
                team_external_id=team_external_id,
                competition=competition,
            )

        return tuple(active_teams.values()), tuple(players.values())

    async def _load(
        self, competitions: Iterable[Competition]
    ) -> tuple[tuple[ProviderTeam, ...], tuple[ProviderPlayer, ...]]:
        requested = self._normalise_competitions(competitions)
        if (
            requested == self._cached_competitions
            and self._cached_teams is not None
            and self._cached_players is not None
        ):
            return self._cached_teams, self._cached_players

        path = await self._download()
        try:
            teams, players = await asyncio.to_thread(self._parse_file, path, requested)
        finally:
            try:
                os.remove(path)
            except OSError:
                pass

        if not teams or not players:
            raise OracleElixirProviderError(
                "Oracle's Elixir n'a produit aucun joueur/équipe exploitable."
            )

        self._cached_competitions = requested
        self._cached_teams = teams
        self._cached_players = players
        return teams, players

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
