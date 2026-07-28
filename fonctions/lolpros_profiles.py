from __future__ import annotations

import asyncio
import logging
from urllib.parse import urlparse

import pandas as pd
from aiohttp import ClientError, ClientSession, ClientTimeout

from fonctions.lolpros import (
    ACCOUNT_COLUMNS,
    DEFAULT_HTTP_HEADERS,
    parse_lolpros_accounts,
)

LOGGER = logging.getLogger(__name__)


def _empty_accounts() -> pd.DataFrame:
    return pd.DataFrame(columns=ACCOUNT_COLUMNS)


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


async def fetch_lolpros_accounts_from_profiles(
    session: ClientSession,
    profiles: pd.DataFrame,
    *,
    timeout_seconds: int = 20,
    concurrency: int = 5,
    region: str = "EUW",
    strict: bool = False,
) -> pd.DataFrame:
    """Récupère les comptes via les URLs LoLPros déjà fournies par Leaguepedia.

    Aucun nouvel appel Cargo n'est effectué ici : cela évite de consommer une
    deuxième requête Fandom juste après la collecte du roster.
    """

    if profiles is None or profiles.empty:
        return _empty_accounts()
    if "plug" not in profiles.columns or "Lolpros" not in profiles.columns:
        return _empty_accounts()

    targets = profiles[["plug", "Lolpros"]].copy()
    targets["plug"] = targets["plug"].astype("string").str.strip()
    targets["Lolpros"] = targets["Lolpros"].apply(_normalize_lolpros_url)
    targets = targets[targets["plug"].notna() & targets["Lolpros"].notna()]
    targets = targets.drop_duplicates(subset="plug", keep="last")
    if targets.empty:
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
        fetch_one(str(row["plug"]), str(row["Lolpros"]))
        for _, row in targets.iterrows()
    ))
    frames = [frame for frame in frames if not frame.empty]
    if not frames:
        return _empty_accounts()
    return pd.concat(frames, ignore_index=True).drop_duplicates()
