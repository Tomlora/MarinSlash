from __future__ import annotations

import asyncio
import logging
import re
from html.parser import HTMLParser
from typing import Iterable
from urllib.parse import urlparse

import pandas as pd
from aiohttp import ClientError, ClientSession, ClientTimeout

LOGGER = logging.getLogger(__name__)
LEAGUEPEDIA_API_URL = "https://lol.fandom.com/api.php"
ACCOUNT_COLUMNS = ("joueur", "compte", "region")
DEFAULT_HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
    )
}


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.nodes: list[str] = []

    def handle_data(self, data: str) -> None:
        value = " ".join(data.split())
        if value:
            self.nodes.append(value)


def _empty_accounts() -> pd.DataFrame:
    return pd.DataFrame(columns=ACCOUNT_COLUMNS)


def _cargo_escape(value: str) -> str:
    return value.replace("'", "''")


def _normalize_lolpros_url(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    url = str(value).strip()
    if not url:
        return None
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"}:
        return None
    if hostname != "lolpros.gg" and not hostname.endswith(".lolpros.gg"):
        return None
    return url


def parse_lolpros_accounts(
    html: str,
    player: str,
    *,
    region: str = "EUW",
) -> pd.DataFrame:
    """Extrait uniquement les Riot IDs actifs affichés en tête du profil.

    L'historique de renommage se trouve après ``Current Rank`` / ``Summoner Names``
    et n'est volontairement pas importé.
    """

    parser = _VisibleTextParser()
    parser.feed(html)

    stop_markers = ("Current Rank", "Summoner Names", "Rank History")
    riot_id = re.compile(r"^[^#\r\n]{1,32}#[A-Za-z0-9]{2,8}$")
    accounts: list[str] = []

    for node in parser.nodes:
        if any(marker in node for marker in stop_markers):
            break
        candidate = node.strip()
        if riot_id.fullmatch(candidate):
            accounts.append(candidate)

    accounts = list(dict.fromkeys(accounts))
    if not accounts:
        return _empty_accounts()

    return pd.DataFrame({"joueur": player, "compte": accounts, "region": region})


async def fetch_lolpros_urls(
    session: ClientSession,
    players: Iterable[str],
    *,
    timeout_seconds: int = 30,
    chunk_size: int = 50,
    strict: bool = False,
) -> pd.DataFrame:
    """Résout les URLs LoLPros via le champ ``Players.Lolpros`` de Leaguepedia."""

    unique_players = [
        player.strip()
        for player in dict.fromkeys(players)
        if isinstance(player, str) and player.strip()
    ]
    if not unique_players:
        return pd.DataFrame(columns=["plug", "Lolpros"])

    frames: list[pd.DataFrame] = []
    timeout = ClientTimeout(total=timeout_seconds)

    for start in range(0, len(unique_players), chunk_size):
        chunk = unique_players[start:start + chunk_size]
        quoted = ",".join(f"'{_cargo_escape(player)}'" for player in chunk)
        params = {
            "action": "cargoquery",
            "tables": "Players",
            "fields": "Players.Player,Players.Lolpros",
            "where": f"Players.Player IN ({quoted})",
            "format": "json",
            "limit": str(max(100, len(chunk) * 2)),
        }

        try:
            async with session.get(
                LEAGUEPEDIA_API_URL,
                params=params,
                timeout=timeout,
            ) as response:
                response.raise_for_status()
                payload = await response.json(content_type=None)

            rows = [entry["title"] for entry in payload.get("cargoquery", [])]
            if rows:
                frame = pd.DataFrame(rows).rename(
                    columns={"Player": "plug", "Lolpros": "Lolpros"}
                )
                frames.append(frame.reindex(columns=["plug", "Lolpros"]))
        except (ClientError, asyncio.TimeoutError, ValueError, KeyError) as exc:
            LOGGER.warning("Leaguepedia URLs LoLPros KO: %s", exc)
            if strict:
                raise

    if not frames:
        return pd.DataFrame(columns=["plug", "Lolpros"])

    result = pd.concat(frames, ignore_index=True)
    result["plug"] = result["plug"].astype("string").str.strip()
    result["Lolpros"] = result["Lolpros"].apply(_normalize_lolpros_url)
    result = result[result["plug"].notna() & result["Lolpros"].notna()]
    return result.drop_duplicates(subset="plug", keep="last").reset_index(drop=True)


async def fetch_lolpros_accounts(
    session: ClientSession,
    players: Iterable[str],
    *,
    timeout_seconds: int = 20,
    concurrency: int = 5,
    region: str = "EUW",
    strict: bool = False,
) -> pd.DataFrame:
    """Récupère les comptes LoLPros sans aucun appel à l'API Riot."""

    urls = await fetch_lolpros_urls(session, players, strict=strict)
    if urls.empty:
        return _empty_accounts()

    semaphore = asyncio.Semaphore(concurrency)
    timeout = ClientTimeout(total=timeout_seconds)

    async def fetch_one(player: str, url: str) -> pd.DataFrame:
        async with semaphore:
            try:
                async with session.get(
                    url,
                    timeout=timeout,
                    headers=DEFAULT_HTTP_HEADERS,
                ) as response:
                    response.raise_for_status()
                    html = await response.text()
                result = parse_lolpros_accounts(html, player, region=region)
                if result.empty:
                    LOGGER.warning("LoLPros: aucun compte actif détecté pour %s", player)
                return result
            except (ClientError, asyncio.TimeoutError, ValueError) as exc:
                LOGGER.warning("LoLPros comptes KO pour %s: %s", player, exc)
                if strict:
                    raise
                return _empty_accounts()

    frames = await asyncio.gather(*(
        fetch_one(row["plug"], row["Lolpros"])
        for _, row in urls.iterrows()
    ))
    frames = [frame for frame in frames if not frame.empty]
    if not frames:
        return _empty_accounts()
    return pd.concat(frames, ignore_index=True).drop_duplicates()


def merge_account_sources(*sources: pd.DataFrame) -> pd.DataFrame:
    """Fusionne LoLPros/TTP sans modifier le schéma historique de la table."""

    frames: list[pd.DataFrame] = []
    for source in sources:
        if source is None or source.empty:
            continue
        frame = source.copy().reindex(columns=ACCOUNT_COLUMNS)
        frame = frame[frame["joueur"].notna() & frame["compte"].notna()]
        frame["joueur"] = frame["joueur"].astype(str).str.strip()
        frame["compte"] = frame["compte"].astype(str).str.strip()
        frame["region"] = frame["region"].fillna("EUW").astype(str).str.strip().str.upper()
        frame = frame[frame["joueur"].ne("") & frame["compte"].ne("")]
        frames.append(frame)

    if not frames:
        return _empty_accounts()

    return (
        pd.concat(frames, ignore_index=True)
        .drop_duplicates(subset=list(ACCOUNT_COLUMNS), keep="first")
        .reset_index(drop=True)
    )
