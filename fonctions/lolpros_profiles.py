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

# LoLPros protège fortement ses pages contre les rafales de requêtes. Le job hebdo
# ne doit donc jamais essayer les ~2600 joueurs historiques d'un seul coup.
DEFAULT_MAX_PROFILES_PER_RUN = 500
DEFAULT_GUESSED_PROFILES_PER_RUN = 25
DEFAULT_REQUEST_INTERVAL_SECONDS = 1.0
DEFAULT_RATE_LIMIT_BACKOFF_SECONDS = 60.0


class LolprosRateLimitError(RuntimeError):
    def __init__(self, retry_after: float | None = None):
        super().__init__("LoLPros HTTP 429 Too Many Requests")
        self.retry_after = retry_after


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
    """Déduplique les pseudos sans tenir compte de la casse.

    La BDD historique contient par exemple CarioK/Cariok ou Hans-Sama/hans-sama.
    Les requêter deux fois ne fait qu'augmenter le risque de rate-limit.
    """

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
    max_profiles: int,
    guessed_profiles_limit: int,
) -> list[str]:
    """Sélectionne une quantité raisonnable de profils pour le run.

    Priorités :
    1. joueurs ayant une URL LoLPros fournie par Leaguepedia pendant ce run ;
    2. profils déjà validés en cache, les plus anciens d'abord ;
    3. un petit nombre de joueurs sans URL connue pour découvrir de nouveaux profils.

    Les comptes historiques déjà présents en BDD sont conservés par le caller : il
    n'est donc pas nécessaire de re-télécharger les ~2600 joueurs chaque semaine.
    """

    unique_players = _unique_players(players)
    if not unique_players or max_profiles <= 0:
        return []

    by_key = {player.casefold(): player for player in unique_players}
    league_map = _profile_map(leaguepedia_profiles, "plug", "Lolpros")
    cache_map = _profile_map(cached_profiles, "joueur", "lolpros_url")

    selected: list[str] = []
    selected_keys: set[str] = set()

    def add(player: str) -> None:
        key = player.casefold()
        if key in by_key and key not in selected_keys and len(selected) < max_profiles:
            selected.append(by_key[key])
            selected_keys.add(key)

    # Le roster courant doit toujours être prioritaire.
    for player in unique_players:
        if player.casefold() in league_map:
            add(player)

    # Ensuite on fait tourner les profils déjà connus, du plus vieux au plus récent.
    for cached_player in _cache_age_order(cached_profiles):
        if len(selected) >= max_profiles:
            break
        add(cached_player)

    # Enfin seulement, on devine quelques slugs supplémentaires.
    guessed = 0
    for player in unique_players:
        if len(selected) >= max_profiles or guessed >= guessed_profiles_limit:
            break
        key = player.casefold()
        if key in selected_keys or key in league_map or key in cache_map:
            continue
        add(player)
        guessed += 1

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
    max_profiles: int = DEFAULT_MAX_PROFILES_PER_RUN,
    guessed_profiles_limit: int = DEFAULT_GUESSED_PROFILES_PER_RUN,
    request_interval_seconds: float = DEFAULT_REQUEST_INTERVAL_SECONDS,
    rate_limit_backoff_seconds: float = DEFAULT_RATE_LIMIT_BACKOFF_SECONDS,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Récupère comptes SoloQ + métadonnées roster depuis LoLPros sans rafale HTTP.

    ``concurrency`` est conservé dans la signature pour compatibilité, mais les accès
    LoLPros sont volontairement sérialisés. Un premier HTTP 429 provoque une pause et
    un unique retry ; un second 429 ouvre le circuit et arrête immédiatement le reste
    du run afin de ne pas envoyer des milliers de requêtes inutiles.
    """

    del concurrency  # intentionnel : LoLPros ne doit plus être sollicité en parallèle.

    unique_players = _unique_players(players)
    if not unique_players:
        return _empty_accounts(), _empty_profiles()

    league_map = _profile_map(leaguepedia_profiles, "plug", "Lolpros")
    cache_map = _profile_map(cached_profiles, "joueur", "lolpros_url")
    selected_players = _select_players_for_refresh(
        unique_players,
        leaguepedia_profiles=leaguepedia_profiles,
        cached_profiles=cached_profiles,
        max_profiles=max_profiles,
        guessed_profiles_limit=guessed_profiles_limit,
    )

    LOGGER.info(
        "LoLPros: %s profils planifiés sur %s joueurs connus (budget=%s).",
        len(selected_players),
        len(unique_players),
        max_profiles,
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

    account_frames: list[pd.DataFrame] = []
    profiles: list[dict] = []
    rate_limit_retry_used = False

    for position, player in enumerate(selected_players, start=1):
        try:
            accounts, profile = await fetch_one(player)
        except LolprosRateLimitError as exc:
            if not rate_limit_retry_used:
                delay = exc.retry_after or rate_limit_backoff_seconds
                rate_limit_retry_used = True
                LOGGER.warning(
                    "LoLPros rate-limit 429 après %s/%s profils : pause %.0fs puis un seul retry.",
                    position - 1,
                    len(selected_players),
                    delay,
                )
                await asyncio.sleep(delay)
                try:
                    accounts, profile = await fetch_one(player)
                except LolprosRateLimitError as retry_exc:
                    LOGGER.warning(
                        "LoLPros toujours rate-limité après %.0fs : arrêt du run, %s profils non tentés.",
                        retry_exc.retry_after or delay,
                        len(selected_players) - position + 1,
                    )
                    break
            else:
                LOGGER.warning(
                    "LoLPros rate-limit 429 : circuit ouvert, %s profils non tentés.",
                    len(selected_players) - position + 1,
                )
                break

        if not accounts.empty:
            account_frames.append(accounts)
        if profile is not None:
            profiles.append(profile)

        if position < len(selected_players) and request_interval_seconds > 0:
            await asyncio.sleep(request_interval_seconds)

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
        "LoLPros terminé : %s profils résolus, %s Riot IDs récupérés.",
        len(resolved),
        len(accounts),
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
