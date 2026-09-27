"""Collecte des challenges : cache du catalogue, délais bornés, isolation du récap."""
import asyncio
import logging
import time
import weakref
from datetime import datetime, timezone

import aiohttp

from fonctions import challenge_store as store
from fonctions.challenge_progress import normalize

log = logging.getLogger(__name__)
_locks = weakref.WeakValueDictionary()
_catalog = None
_catalog_until = 0
_catalog_lock = asyncio.Lock()


def account_lock(joueur):
    key = int(joueur)
    lock = _locks.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _locks[key] = lock
    return lock


async def request(session, path):
    from utils.params import api_key_lol, my_region
    url = f'https://{my_region}.api.riotgames.com/lol/challenges/v1/{path}'
    async with session.get(url, headers={'X-Riot-Token': api_key_lol},
                           timeout=aiohttp.ClientTimeout(total=12)) as response:
        if response.status != 200:
            raise RuntimeError(f'Challenges Riot indisponibles (HTTP {response.status})')
        return await response.json()


async def catalog(session):
    global _catalog, _catalog_until
    async with _catalog_lock:
        if _catalog is None or time.monotonic() >= _catalog_until:
            result = await request(session, 'challenges/config')
            if not isinstance(result, list) or not result:
                raise ValueError('Catalogue Riot vide ou invalide')
            _catalog, _catalog_until = result, time.monotonic() + 6 * 3600
        return _catalog


async def observe(joueur, puuid, match_id=None, initialize_only=False):
    async with account_lock(joueur):
        if match_id:
            existing = await asyncio.to_thread(store.load_match, match_id, joueur)
            if existing is not None:
                return existing
        previous, _ = await asyncio.to_thread(store.profile, joueur)
        if initialize_only and previous:
            return previous
        async with aiohttp.ClientSession() as session:
            config = await catalog(session)
            player = await request(session, f'player-data/{puuid}')
        current = normalize(player, config, datetime.now(timezone.utc).isoformat())
        if previous and previous['entries'] and not current['entries']:
            raise ValueError('Relevé vide inattendu : référence conservée')
        return await asyncio.to_thread(store.save_observation, joueur, current, match_id)


async def recap_snapshot(joueur, puuid, match_id, capture=False):
    """Un rejeu consulte le snapshot; il ne compare jamais le présent à un vieux match."""
    try:
        if capture:
            return await asyncio.wait_for(observe(joueur, puuid, match_id), timeout=35)
        return await asyncio.wait_for(asyncio.to_thread(store.load_match, match_id, joueur), timeout=10)
    except Exception:
        log.exception('Challenges non disponibles pour %s / %s', match_id, joueur)
        return None
