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
    parse_lolpros_profile_metadata,
)

LOGGER = logging.getLogger(__name__)
LOLPROS_PLAYER_URL = "https://lolpros.gg/player/{slug}"
PROFILE_COLUMNS = ("joueur", "lolpros_url", "team_plug", "role", "Pays")

# Le job tourne de nuit : on privilégie la complétude et un rythme doux plutôt que
# la vitesse. Environ 2600 joueurs = ~26 lots, soit ~2 h avec ces valeurs hors
# latence réseau et éventuels backoffs 429.
DEFAULT_BATCH_SIZE = 100
DEFAULT_REQUEST_INTERVAL_SECONDS = 2.0
DEFAULT_BATCH_PAUSE_SECONDS = 60.0
DEFAULT_RATE_LIMIT_BACKOFF_SECONDS = 300.0
DEFAULT_MAX_RATE_LIMIT_COOLDOWNS = 5


class LolprosRateLimitError(RuntimeError):
    def __init__(self, retry_after: float | None = None):
        super().__init__("LoLPros HTTP 429 Too Many Requests")
        self.retry_after = retry_after


class LolprosRateLimitExhausted(RuntimeError):
    """Trop de périodes de rate-limit pendant un même run nocturne."""


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
    return re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")


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


def _profile_map(
    frame: pd.DataFrame | None,
    player_column: str,
    url_column: str,
) -> dict[str, str]:
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


def _unique_players(players: Iterable[str]) -> list[str]:
    """Déduplique les pseudos sans tenir compte de la casse."""

    result: list[str] = []
    seen: set[str] = set()
    for player in players:
        if not isinstance(player, str):
            continue
        value = player.strip()
        key = value.casefold()
        if not value or key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def _cache_age_order(cached_profiles: pd.DataFrame | None) -> list[str]:
    if cached_profiles is None or cached_profiles.empty or "joueur" not in cached_profiles.columns:
        return []

    frame = cached_profiles.copy()
    if "last_verified" in frame.columns:
        frame["last_verified"] = pd.to_datetime(frame["last_verified"], errors="coerce", utc=True)
        frame.sort_values("last_verified", na_position="first", inplace=True)

    return _unique_players(frame["joueur"].dropna().astype(str).tolist())


def _select_players_for_refresh(
    players: Iterable[str],
    *,
    leaguepedia_profiles: pd.DataFrame | None,
    cached_profiles: pd.DataFrame | None,
) -> list[str]:
    """Planifie TOUS les joueurs du run, avec les plus utiles en premier.

    Ordre :
    1. joueurs ayant une URL LoLPros fournie par Leaguepedia pendant ce run ;
    2. profils déjà validés en cache, les plus anciens d'abord ;
    3. tous les autres joueurs, dont le slug LoLPros sera deviné.

    Contrairement à l'ancienne version, aucun quota hebdomadaire ne laisse des
    milliers de joueurs pour les semaines suivantes : un run nocturne tente toute
    la base, simplement à un rythme contrôlé par lots.
    """

    unique_players = _unique_players(players)
    if not unique_players:
        return []

    by_key = {player.casefold(): player for player in unique_players}
    league_map = _profile_map(leaguepedia_profiles, "plug", "Lolpros")

    selected: list[str] = []
    selected_keys: set[str] = set()

    def add(player: str) -> None:
        key = player.casefold()
        if key in by_key and key not in selected_keys:
            selected.append(by_key[key])
            selected_keys.add(key)

    for player in unique_players:
        if player.casefold() in league_map:
            add(player)

    for cached_player in _cache_age_order(cached_profiles):
        add(cached_player)

    for player in unique_players:
        add(player)

    return selected


def _retry_after_seconds(response) -> float | None:
    raw_value = response.headers.get("Retry-After") if hasattr(response, "headers") else None
    if raw_value is None:
        return None
    try:
        return max(float(raw_value), 0.0)
    except (TypeError, ValueError):
        return None


async def fetch_lolpros_accounts_for_players(
    session: ClientSession,
    players: Iterable[str],
    *,
    leaguepedia_profiles: pd.DataFrame | None = None,
    cached_profiles: pd.DataFrame | None = None,
    timeout_seconds: int = 20,
    concurrency: int = 1,
    region: str = "EUW",
    strict: bool = False,
    batch_size: int = DEFAULT_BATCH_SIZE,
    request_interval_seconds: float = DEFAULT_REQUEST_INTERVAL_SECONDS,
    batch_pause_seconds: float = DEFAULT_BATCH_PAUSE_SECONDS,
    rate_limit_backoff_seconds: float = DEFAULT_RATE_LIMIT_BACKOFF_SECONDS,
    max_rate_limit_cooldowns: int = DEFAULT_MAX_RATE_LIMIT_COOLDOWNS,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Récupère comptes SoloQ + roster LoLPros pour tous les joueurs, par lots.

    Les requêtes sont volontairement sérialisées. Chaque joueur de la BDD est tenté
    pendant le run nocturne. Une pause est appliquée entre les profils et entre les
    lots. En cas de 429, le même joueur est retenté après ``Retry-After`` ou après un
    cooldown de 5 minutes. Après plusieurs cooldowns successifs, le run LoLPros est
    interrompu proprement pour ne pas marteler le service ; les résultats déjà
    obtenus restent utilisables par le caller.
    """

    del concurrency  # compatibilité de signature ; aucune rafale parallèle voulue.

    unique_players = _unique_players(players)
    if not unique_players:
        return _empty_accounts(), _empty_profiles()

    if batch_size <= 0:
        raise ValueError("batch_size doit être strictement positif")

    league_map = _profile_map(leaguepedia_profiles, "plug", "Lolpros")
    cache_map = _profile_map(cached_profiles, "joueur", "lolpros_url")
    selected_players = _select_players_for_refresh(
        unique_players,
        leaguepedia_profiles=leaguepedia_profiles,
        cached_profiles=cached_profiles,
    )

    total_batches = (len(selected_players) + batch_size - 1) // batch_size
    LOGGER.info(
        "LoLPros: %s profils planifiés sur %s joueurs connus, %s lots de %s max.",
        len(selected_players),
        len(unique_players),
        total_batches,
        batch_size,
    )

    timeout = ClientTimeout(total=timeout_seconds)

    async def fetch_one(player: str) -> tuple[pd.DataFrame, dict | None]:
        key = player.casefold()
        known_urls: list[str] = []
        if key in league_map:
            known_urls.append(league_map[key])
        if key in cache_map and cache_map[key] not in known_urls:
            known_urls.append(cache_map[key])

        urls = _candidate_urls(player, known_urls)
        if not urls:
            return _empty_accounts(), None

        last_error: Exception | None = None
        for url in urls:
            try:
                async with session.get(
                    url,
                    timeout=timeout,
                    headers=DEFAULT_HTTP_HEADERS,
                ) as response:
                    if response.status == 429:
                        raise LolprosRateLimitError(_retry_after_seconds(response))
                    if response.status == 404:
                        continue
                    response.raise_for_status()
                    html = await response.text()

                accounts = parse_lolpros_accounts(html, player, region=region)
                metadata = parse_lolpros_profile_metadata(html)
                profile = {
                    "joueur": player,
                    "lolpros_url": url,
                    "team_plug": metadata.get("team_plug"),
                    "role": metadata.get("role"),
                    "Pays": metadata.get("Pays"),
                }

                if not accounts.empty or any(metadata.values()):
                    return accounts, profile
            except LolprosRateLimitError:
                raise
            except (ClientError, asyncio.TimeoutError, ValueError) as exc:
                last_error = exc
                LOGGER.warning("LoLPros profil KO pour %s (%s): %s", player, url, exc)
                if strict:
                    raise

        if last_error is None:
            LOGGER.debug("LoLPros: aucun Riot ID ni metadata détecté pour %s", player)
        return _empty_accounts(), None

    async def fetch_with_backoff(
        player: str,
        *,
        processed: int,
    ) -> tuple[pd.DataFrame, dict | None, int]:
        cooldowns = 0
        while True:
            try:
                accounts, profile = await fetch_one(player)
                return accounts, profile, cooldowns
            except LolprosRateLimitError as exc:
                cooldowns += 1
                if cooldowns > max_rate_limit_cooldowns:
                    raise LolprosRateLimitExhausted(
                        f"LoLPros encore rate-limité après {max_rate_limit_cooldowns} cooldowns"
                    ) from exc

                delay = exc.retry_after or rate_limit_backoff_seconds
                LOGGER.warning(
                    "LoLPros 429 après %s profils : cooldown %s/%s de %.0fs, puis retry de %s.",
                    processed,
                    cooldowns,
                    max_rate_limit_cooldowns,
                    delay,
                    player,
                )
                await asyncio.sleep(delay)

    account_frames: list[pd.DataFrame] = []
    profiles: list[dict] = []
    processed = 0
    aborted = False

    for batch_number, start in enumerate(range(0, len(selected_players), batch_size), start=1):
        batch = selected_players[start:start + batch_size]
        LOGGER.info(
            "LoLPros lot %s/%s : %s profils (%s/%s déjà traités).",
            batch_number,
            total_batches,
            len(batch),
            processed,
            len(selected_players),
        )

        for index_in_batch, player in enumerate(batch, start=1):
            try:
                accounts, profile, _ = await fetch_with_backoff(
                    player,
                    processed=processed,
                )
            except LolprosRateLimitExhausted as exc:
                LOGGER.error(
                    "%s. Arrêt LoLPros après %s/%s profils ; les données déjà récupérées sont conservées.",
                    exc,
                    processed,
                    len(selected_players),
                )
                aborted = True
                break

            processed += 1
            if not accounts.empty:
                account_frames.append(accounts)
            if profile is not None:
                profiles.append(profile)

            if index_in_batch < len(batch) and request_interval_seconds > 0:
                await asyncio.sleep(request_interval_seconds)

        LOGGER.info(
            "LoLPros lot %s/%s terminé : %s/%s profils traités, %s profils résolus, %s Riot IDs cumulés.",
            batch_number,
            total_batches,
            processed,
            len(selected_players),
            len(profiles),
            sum(len(frame) for frame in account_frames),
        )

        if aborted:
            break

        if start + len(batch) < len(selected_players) and batch_pause_seconds > 0:
            LOGGER.info(
                "LoLPros pause inter-lot %.0fs avant le lot %s/%s.",
                batch_pause_seconds,
                batch_number + 1,
                total_batches,
            )
            await asyncio.sleep(batch_pause_seconds)

    if account_frames:
        accounts = pd.concat(account_frames, ignore_index=True).drop_duplicates()
    else:
        accounts = _empty_accounts()

    if profiles:
        resolved = (
            pd.DataFrame(profiles)
            .reindex(columns=PROFILE_COLUMNS)
            .drop_duplicates(subset="joueur", keep="last")
            .reset_index(drop=True)
        )
    else:
        resolved = _empty_profiles()

    LOGGER.info(
        "LoLPros terminé : %s/%s profils traités, %s profils résolus, %s Riot IDs récupérés%s.",
        processed,
        len(selected_players),
        len(resolved),
        len(accounts),
        " (arrêt sur rate-limit)" if aborted else "",
    )
    return accounts, resolved


async def fetch_lolpros_accounts_from_profiles(
    session: ClientSession,
    profiles: pd.DataFrame,
    *,
    timeout_seconds: int = 20,
    concurrency: int = 1,
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
