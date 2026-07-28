from __future__ import annotations

import asyncio
import logging
from typing import Iterable, Sequence

import pandas as pd
from aiohttp import ClientError, ClientSession, ClientTimeout

from fonctions.proplay_sources import DEFAULT_PRO_LEAGUES

LOGGER = logging.getLogger(__name__)

LEAGUEPEDIA_API_URL = "https://lol.fandom.com/api.php"
LEAGUEPEDIA_HEADERS = {
    "User-Agent": "MarinSlash/1.0 (https://github.com/Tomlora/MarinSlash)"
}
LEAGUEPEDIA_COLUMNS = (
    "plug",
    "Nom",
    "Pays",
    "Rôle",
    "Ligue",
    "team_plug",
    "Lolpros",
)


def _empty_players() -> pd.DataFrame:
    return pd.DataFrame(columns=LEAGUEPEDIA_COLUMNS)


def _cargo_escape(value: str) -> str:
    return value.replace("'", "''")


def _clean_result(frame: pd.DataFrame, *, league: str | None = None) -> pd.DataFrame:
    if frame.empty:
        return _empty_players()

    frame = frame.rename(
        columns={
            "Player": "plug",
            "Name": "Nom",
            "Country": "Pays",
            "Role": "Rôle",
            "League": "Ligue",
            "Team": "team_plug",
        }
    ).reindex(columns=LEAGUEPEDIA_COLUMNS)

    if league is not None:
        frame["Ligue"] = frame["Ligue"].fillna(league)

    frame["plug"] = (
        frame["plug"]
        .astype("string")
        .str.replace(r"\s*\(.*?\)", "", regex=True)
        .str.strip()
    )
    frame["Rôle"] = frame["Rôle"].replace({"Bot": "ADC"})
    frame = frame[frame["plug"].notna() & frame["plug"].ne("")]
    return frame.drop_duplicates(subset="plug", keep="first").reset_index(drop=True)


async def _cargo_query(
    session: ClientSession,
    params: dict[str, str],
    *,
    timeout_seconds: int,
) -> list[dict]:
    async with session.get(
        LEAGUEPEDIA_API_URL,
        params=params,
        timeout=ClientTimeout(total=timeout_seconds),
        headers=LEAGUEPEDIA_HEADERS,
    ) as response:
        response.raise_for_status()
        payload = await response.json(content_type=None)

    return [entry["title"] for entry in payload.get("cargoquery", [])]


async def fetch_leaguepedia_players(
    session: ClientSession,
    leagues: Sequence[str] = DEFAULT_PRO_LEAGUES,
    *,
    timeout_seconds: int = 30,
    strict: bool = False,
) -> pd.DataFrame:
    """Récupère les joueurs d'une liste de championnats Leaguepedia.

    La jointure suit celle utilisée actuellement par le module Leaguepedia
    TournamentPlayerInformation : TournamentPlayers.Link -> PlayerRedirects.AllName.
    Une panne sur un championnat n'empêche pas les autres de remonter.
    """

    frames: list[pd.DataFrame] = []

    for league in leagues:
        params = {
            "action": "cargoquery",
            "tables": "Tournaments,TournamentPlayers,PlayerRedirects,Players",
            "fields": (
                "Players.Player,Players.Name,Players.Country,Players.Role,"
                "Tournaments.League,Players.Team,Players.Lolpros"
            ),
            "where": (
                f"Tournaments.League in ('{_cargo_escape(league)}') "
                "and Players.Role in ('Top', 'Jungle', 'Mid', 'Bot', 'Support')"
            ),
            "join_on": (
                "Tournaments.OverviewPage=TournamentPlayers.OverviewPage,"
                "TournamentPlayers.Link=PlayerRedirects.AllName,"
                "PlayerRedirects.OverviewPage=Players.OverviewPage"
            ),
            "group_by": "Players.OverviewPage",
            "format": "json",
            "limit": "1000",
        }

        try:
            rows = await _cargo_query(
                session,
                params,
                timeout_seconds=timeout_seconds,
            )
            if not rows:
                LOGGER.warning("Leaguepedia: aucun joueur pour %s", league)
                continue
            frames.append(_clean_result(pd.DataFrame(rows), league=league))
        except (ClientError, asyncio.TimeoutError, ValueError, KeyError) as exc:
            LOGGER.warning("Leaguepedia KO pour %s: %s", league, exc)
            if strict:
                raise

    frames = [frame for frame in frames if not frame.empty]
    if not frames:
        return _empty_players()

    return (
        pd.concat(frames, ignore_index=True)
        .drop_duplicates(subset="plug", keep="first")
        .reset_index(drop=True)
    )


async def fetch_leaguepedia_players_by_name(
    session: ClientSession,
    players: Iterable[str],
    *,
    timeout_seconds: int = 30,
    strict: bool = False,
) -> pd.DataFrame:
    """Lookup Leaguepedia direct pour inspecter un ou plusieurs joueurs.

    Contrairement au lookup par championnat, ce chemin ne dépend pas de
    TournamentPlayers/Tournaments. Il accepte aussi un ancien alias grâce à
    PlayerRedirects et est donc adapté à ``scripts/test_proplay_sources.py
    --player ...``.
    """

    unique_players = [
        player.strip()
        for player in dict.fromkeys(players)
        if isinstance(player, str) and player.strip()
    ]
    if not unique_players:
        return _empty_players()

    frames: list[pd.DataFrame] = []

    for player in unique_players:
        escaped = _cargo_escape(player)
        params = {
            "action": "cargoquery",
            "tables": "PlayerRedirects,Players",
            "fields": (
                "Players.Player,Players.Name,Players.Country,Players.Role,"
                "Players.Team,Players.Lolpros"
            ),
            "where": (
                f"PlayerRedirects.AllName='{escaped}' "
                f"OR PlayerRedirects.ID='{escaped}'"
            ),
            "join_on": "PlayerRedirects.OverviewPage=Players.OverviewPage",
            "group_by": "Players.OverviewPage",
            "format": "json",
            "limit": "20",
        }

        try:
            rows = await _cargo_query(
                session,
                params,
                timeout_seconds=timeout_seconds,
            )
            if not rows:
                LOGGER.warning("Leaguepedia: joueur introuvable: %s", player)
                continue
            frames.append(_clean_result(pd.DataFrame(rows)))
        except (ClientError, asyncio.TimeoutError, ValueError, KeyError) as exc:
            LOGGER.warning("Leaguepedia lookup joueur KO pour %s: %s", player, exc)
            if strict:
                raise

    frames = [frame for frame in frames if not frame.empty]
    if not frames:
        return _empty_players()

    return (
        pd.concat(frames, ignore_index=True)
        .drop_duplicates(subset="plug", keep="first")
        .reset_index(drop=True)
    )
