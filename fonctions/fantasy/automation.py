"""Bounded Fantasy sync jobs, shared by admin commands and the background loop."""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import timedelta
from threading import Lock

from sqlalchemy import text

from .database import get_engine
from .freshness import stale_competitions
from .providers.leaguepedia import LeaguepediaPlayerProvider
from .providers.oracles_elixir import OracleElixirPlayerProvider
from .providers.schedule import FallbackScheduleProvider, LeaguepediaScheduleProvider, RiotEsportsScheduleProvider
from .schedule_sync import sync_schedule
from .sync import sync_player_pool

SYNC_LOCK_ID = 70612026
INTERVALS = {'pool': timedelta(hours=24), 'schedule': timedelta(hours=1)}
RETRIES = {'pool': timedelta(hours=6), 'schedule': timedelta(hours=1)}
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='fantasy-sync')
_busy = Lock()


class SyncBusyError(RuntimeError):
    pass


@dataclass(frozen=True)
class SyncOutcome:
    result: object
    source: str
    fallback: bool = False


def is_due(kind, row, now):
    if row is None or row.last_attempt_at is None:
        return True
    delay = RETRIES[kind] if row.last_error else INTERVALS[kind]
    return now - row.last_attempt_at >= delay


async def _fetch_and_sync(kind, source, now):
    if kind == 'pool':
        provider = LeaguepediaPlayerProvider() if source == 'leaguepedia' else OracleElixirPlayerProvider()
        result = await sync_player_pool(provider)
        return SyncOutcome(result, type(provider).__name__)
    provider = FallbackScheduleProvider(LeaguepediaScheduleProvider(), RiotEsportsScheduleProvider())
    result = await sync_schedule(provider, start=now - timedelta(days=2), end=now + timedelta(days=21))
    return SyncOutcome(result, provider.last_provider_name or 'unknown', bool(provider.errors))


def _run_job(kind, source, automatic):
    # Session lock covers HTTP + database writes, also across bot processes.
    with get_engine().connect().execution_options(isolation_level='AUTOCOMMIT') as connection:
        acquired = connection.execute(text('SELECT pg_try_advisory_lock(:key)'), {'key': SYNC_LOCK_ID}).scalar_one()
        if not acquired:
            raise SyncBusyError('Une synchronisation Fantasy est déjà en cours.')
        try:
            now = connection.execute(text('SELECT clock_timestamp()')).scalar_one()
            if automatic:
                active = connection.execute(text("SELECT EXISTS (SELECT 1 FROM fantasy.league WHERE status IN ('registration', 'draft', 'active'))")).scalar_one()
                if not active:
                    return None
                row = connection.execute(text('SELECT * FROM fantasy.sync_job WHERE kind = :kind'), {'kind': kind}).first()
                if not is_due(kind, row, now):
                    return None
            connection.execute(text('''
                INSERT INTO fantasy.sync_job (kind, last_attempt_at, last_error, source)
                VALUES (:kind, :now, 'interrupted', :source)
                ON CONFLICT (kind) DO UPDATE SET last_attempt_at = EXCLUDED.last_attempt_at,
                    last_error = EXCLUDED.last_error, source = EXCLUDED.source
            '''), {'kind': kind, 'now': now, 'source': source})
            try:
                # SQL and parsing also run here, never on the Discord loop.
                outcome = asyncio.run(asyncio.wait_for(_fetch_and_sync(kind, source, now), timeout=300))
            except Exception as exc:
                # Store only the exception type: provider URLs/credentials never enter status.
                connection.execute(text('UPDATE fantasy.sync_job SET last_error = :error WHERE kind = :kind'),
                                   {'kind': kind, 'error': type(exc).__name__})
                raise
            connection.execute(text('''
                UPDATE fantasy.sync_job SET last_success_at = clock_timestamp(),
                    last_error = NULL, source = :source WHERE kind = :kind
            '''), {'kind': kind, 'source': outcome.source})
            return outcome
        finally:
            # A failed unlock must not leave a locked session in the connection pool.
            try:
                connection.execute(text('SELECT pg_advisory_unlock(:key)'), {'key': SYNC_LOCK_ID})
            except BaseException:
                connection.invalidate()
                raise


def _guarded_job(kind, source, automatic):
    try:
        return _run_job(kind, source, automatic)
    finally:
        _busy.release()


async def run_sync(kind: str, *, source='oracle_elixir', automatic=False):
    if kind not in INTERVALS or source not in ('oracle_elixir', 'leaguepedia'):
        raise ValueError('Source ou synchronisation inconnue.')
    if not _busy.acquire(blocking=False):
        raise SyncBusyError('Une synchronisation Fantasy est déjà en cours.')
    try:
        future = asyncio.wrap_future(_executor.submit(_guarded_job, kind, source, automatic))
    except BaseException:
        _busy.release()
        raise
    # Cancelling a Discord interaction/unloading the cog must not release the gate
    # while its worker is still writing. Also consume any detached exception.
    future.add_done_callback(lambda done: done.exception() if not done.cancelled() else None)
    return await asyncio.shield(future)


def read_sync_status():
    with get_engine().connect() as connection:
        now = connection.execute(text('SELECT clock_timestamp()')).scalar_one()
        return {
            'jobs': [dict(row) for row in connection.execute(text('SELECT * FROM fantasy.sync_job ORDER BY kind')).mappings()],
            'stale': sorted(c.value for c in stale_competitions(connection, now)),
        }
