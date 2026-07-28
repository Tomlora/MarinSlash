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


class LeaguepediaCargoError(RuntimeError):
    """Erreur fonctionnelle renvoyée par l'API MediaWiki/Cargo."""


def _empty_players() -> pd.DataFrame:
    return pd.DataFrame(columns=LEAGUEPEDIA_COLUMNS)


def _cargo_escape(value: str) -> str:
    return value.replace("'", "''")


def _quoted_values(values: Iterable[str]) -> str:
    return ",".join(f"'{_cargo_escape(value)}'" for value in values)


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
    return frame.reset_index(drop=True)


def _raise_for_cargo_error(payload: dict) -> None:
    """Transforme les erreurs JSON MediaWiki en vraie exception.

    Fandom peut répondre HTTP 200 avec ``{"error": {"code": "ratelimited", ...}}``.
    Sans ce contrôle, le job interprétait cette réponse comme un roster vide.
    """

    error = payload.get("error")
    if not error:
        return
    code = error.get("code", "unknown")
    info = error.get("info", "Erreur MediaWiki/Cargo sans détail")
    raise LeaguepediaCargoError(f"{code}: {info}")


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

    _raise_for_cargo_error(payload)
    return [entry["title"] for entry in payload.get("cargoquery", [])]


async def fetch_leaguepedia_players(
    session: ClientSession,
    leagues: Sequence[str] = DEFAULT_PRO_LEAGUES,
    *,
    timeout_seconds: int = 45,
    strict: bool = False,
) -> pd.DataFrame:
    """Récupère les rosters demandés avec UNE seule requête Cargo.

    Fandom applique actuellement un rate-limit très agressif aux requêtes Cargo
    non authentifiées. L'ancienne version faisait une requête par championnat ;
    celle-ci regroupe toute la liste dans un seul ``IN (...)``.
    """

    unique_leagues = [
        league.strip()
        for league in dict.fromkeys(leagues)
        if isinstance(league, str) and league.strip()
    ]
    if not unique_leagues:
        return _empty_players()

    params = {
        "action": "cargoquery",
        "tables": "Tournaments,TournamentPlayers,PlayerRedirects,Players",
        "fields": (
            "Players.Player,Players.Name,Players.Country,Players.Role,"
            "Tournaments.League,Players.Team,Players.Lolpros"
        ),
        "where": (
            f"Tournaments.League IN ({_quoted_values(unique_leagues)}) "
            "AND Players.Role IN ('Top', 'Jungle', 'Mid', 'Bot', 'Support')"
        ),
        "join_on": (
            "Tournaments.OverviewPage=TournamentPlayers.OverviewPage,"
            "TournamentPlayers.Link=PlayerRedirects.AllName,"
            "PlayerRedirects.OverviewPage=Players.OverviewPage"
        ),
        "group_by": "Players.OverviewPage,Tournaments.League",
        "format": "json",
        "limit": "5000",
    }

    try:
        rows = await _cargo_query(session, params, timeout_seconds=timeout_seconds)
    except (
        ClientError,
        asyncio.TimeoutError,
        ValueError,
        KeyError,
        LeaguepediaCargoError,
    ) as exc:
        LOGGER.warning("Leaguepedia roster KO: %s", exc)
        if strict:
            raise
        return _empty_players()

    if not rows:
        LOGGER.warning("Leaguepedia: aucun joueur pour les championnats demandés")
        return _empty_players()

    return (
        _clean_result(pd.DataFrame(rows))
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
    """Lookup direct de noms canoniques dans ``Players`` en UNE requête Cargo.

    Ce chemin ne dépend ni de Tournaments ni de TournamentPlayers et convient au
    diagnostic ``--player Caps`` / ``--player Markoon``. Il privilégie la
    robustesse et ne tente pas de résoudre les anciens alias, ce qui nécessiterait
    une requête supplémentaire et consommerait le rate-limit Fandom.
    """

    unique_players = [
        player.strip()
        for player in dict.fromkeys(players)
        if isinstance(player, str) and player.strip()
    ]
    if not unique_players:
        return _empty_players()

    params = {
        "action": "cargoquery",
        "tables": "Players",
        "fields": (
            "Players.Player,Players.Name,Players.Country,Players.Role,"
            "Players.Team,Players.Lolpros"
        ),
        "where": f"Players.Player IN ({_quoted_values(unique_players)})",
        "format": "json",
        "limit": str(max(20, len(unique_players) * 2)),
    }

    try:
        rows = await _cargo_query(session, params, timeout_seconds=timeout_seconds)
    except (
        ClientError,
        asyncio.TimeoutError,
        ValueError,
        KeyError,
        LeaguepediaCargoError,
    ) as exc:
        LOGGER.warning("Leaguepedia lookup joueur KO: %s", exc)
        if strict:
            raise
        return _empty_players()

    if not rows:
        LOGGER.warning("Leaguepedia: joueur(s) introuvable(s): %s", ", ".join(unique_players))
        return _empty_players()

    return (
        _clean_result(pd.DataFrame(rows))
        .drop_duplicates(subset="plug", keep="first")
        .reset_index(drop=True)
    )
