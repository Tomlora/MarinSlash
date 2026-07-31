from __future__ import annotations

import asyncio
import logging
import re
import unicodedata
from typing import Iterable
from urllib.parse import quote, urlparse

import pandas as pd
from aiohttp import ClientError, ClientSession, ClientTimeout

from fonctions.lolpros import (
    ACCOUNT_COLUMNS,
    DEFAULT_HTTP_HEADERS,
    parse_lolpros_accounts,
)

LOGGER = logging.getLogger(__name__)
LOLPROS_PLAYER_URL = "https://lolpros.gg/player/{slug}"
PROFILE_COLUMNS = ("joueur", "lolpros_url")


def _empty_accounts() -> pd.DataFrame:
    return pd.DataFrame(columns=ACCOUNT_COLUMNS)


def _empty_profiles() -> pd.DataFrame:
    return pd.DataFrame(columns=PROFILE_COLUMNS)


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


def _slugify_player(player: str) -> str:
    normalized = unicodedata.normalize("NFKD", player)
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")
    return slug


def _candidate_urls(player: str, known_urls: Iterable[str]) -> list[str]:
    candidates: list[str] = []

    for value in known_urls:
        url = _normalize_lolpros_url(value)
        if url and url not in candidates:
            candidates.append(url)

    slug = _slugify_player(player)
    if slug:
        guessed = LOLPROS_PLAYER_URL.format(slug=quote(slug))
        if guessed not in candidates:
            candidates.append(guessed)

    compact = re.sub(r"[^a-z0-9]+", "", slug)
    if compact and compact != slug:
        guessed = LOLPROS_PLAYER_URL.format(slug=quote(compact))
        if guessed not in candidates:
            candidates.append(guessed)

    return candidates


def _profile_map(frame: pd.DataFrame | None, player_column: str, url_column: str) -> dict[str, str]:
    if frame is None or frame.empty:
        return {}
    if player_column not in frame.columns or url_column not in frame.columns:
        return {}

    mapping: dict[str, str] = {}
    for _, row in frame.iterrows():
        player = row.get(player_column)
        url = _normalize_lolpros_url(row.get(url_column))
        if pd.isna(player) or not url:
            continue
        key = str(player).strip().casefold()
        if key:
            mapping[key] = url
    return mapping


async def fetch_lolpros_accounts_for_players(
    session: ClientSession,
    players: Iterable[str],
    *,
    leaguepedia_profiles: pd.DataFrame | None = None,
    cached_profiles: pd.DataFrame | None = None,
    timeout_seconds: int = 20,
    concurrency: int = 5,
    region: str = "EUW",
    strict: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Récupère les comptes LoLPros sans dépendre de Leaguepedia.

    Ordre des URLs candidates pour chaque joueur :
    1. URL fournie par Leaguepedia pendant ce run, si disponible ;
    2. URL LoLPros validée et mise en cache lors d'un run précédent ;
    3. URL déduite directement du nom pro (``/player/<slug>``).

    Cela permet de continuer à rafraîchir les comptes des joueurs déjà présents
    en BDD même quand Cargo/Leaguepedia est ratelimited ou indisponible.

    Retourne ``(accounts, resolved_profiles)`` ; le deuxième DataFrame sert à
    persister les URLs qui ont réellement répondu avec au moins un Riot ID attribué
    au joueur (compte courant ou nom historique).
    """

    unique_players = [
        player.strip()
        for player in dict.fromkeys(players)
        if isinstance(player, str) and player.strip()
    ]
    if not unique_players:
        return _empty_accounts(), _empty_profiles()

    league_map = _profile_map(leaguepedia_profiles, "plug", "Lolpros")
    cache_map = _profile_map(cached_profiles, "joueur", "lolpros_url")

    semaphore = asyncio.Semaphore(concurrency)
    timeout = ClientTimeout(total=timeout_seconds)

    async def fetch_one(player: str) -> tuple[pd.DataFrame, dict | None]:
        key = player.casefold()
        known_urls = []
        if key in league_map:
            known_urls.append(league_map[key])
        if key in cache_map and cache_map[key] not in known_urls:
            known_urls.append(cache_map[key])

        urls = _candidate_urls(player, known_urls)
        if not urls:
            return _empty_accounts(), None

        async with semaphore:
            last_error: Exception | None = None
            for url in urls:
                try:
                    async with session.get(
                        url,
                        timeout=timeout,
                        headers=DEFAULT_HTTP_HEADERS,
                    ) as response:
                        if response.status == 404:
                            continue
                        response.raise_for_status()
                        html = await response.text()

                    result = parse_lolpros_accounts(html, player, region=region)
                    if not result.empty:
                        return result, {"joueur": player, "lolpros_url": url}
                except (ClientError, asyncio.TimeoutError, ValueError) as exc:
                    last_error = exc
                    LOGGER.warning("LoLPros profil KO pour %s (%s): %s", player, url, exc)
                    if strict:
                        raise

            if last_error is None:
                LOGGER.warning("LoLPros: aucun Riot ID détecté pour %s", player)
            return _empty_accounts(), None

    results = await asyncio.gather(*(fetch_one(player) for player in unique_players))

    account_frames = [accounts for accounts, _ in results if not accounts.empty]
    profiles = [profile for _, profile in results if profile is not None]

    if account_frames:
        accounts = pd.concat(account_frames, ignore_index=True).drop_duplicates()
    else:
        accounts = _empty_accounts()

    if profiles:
        resolved = (
            pd.DataFrame(profiles)
            .drop_duplicates(subset="joueur", keep="last")
            .reset_index(drop=True)
        )
    else:
        resolved = _empty_profiles()

    return accounts, resolved


async def fetch_lolpros_accounts_from_profiles(
    session: ClientSession,
    profiles: pd.DataFrame,
    *,
    timeout_seconds: int = 20,
    concurrency: int = 5,
    region: str = "EUW",
    strict: bool = False,
) -> pd.DataFrame:
    """Compatibilité : récupère les comptes depuis un DataFrame Leaguepedia."""

    if profiles is None or profiles.empty or "plug" not in profiles.columns:
        return _empty_accounts()

    accounts, _ = await fetch_lolpros_accounts_for_players(
        session,
        profiles["plug"].dropna().astype(str).tolist(),
        leaguepedia_profiles=profiles,
        timeout_seconds=timeout_seconds,
        concurrency=concurrency,
        region=region,
        strict=strict,
    )
    return accounts
