"""Run the legacy match pipeline away from Discord's event loop.

Only data and coroutine factories cross this boundary. HTTP sessions must be
created and closed inside the job; Discord clients/contexts must stay outside.
Jobs are serial because the legacy pipeline replaces shared season tables.
"""
import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
from weakref import WeakKeyDictionary


log = logging.getLogger(__name__)
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="matchlol")
_gates = WeakKeyDictionary()


def _execute(factory, args, kwargs):
    started = perf_counter()

    async def build():
        with TemporaryDirectory(prefix="matchlol-") as directory:
            return await factory(*args, image_path=str(Path(directory) / "resume"), **kwargs)

    try:
        # The job owns this loop, including its aiohttp sessions and executor.
        return asyncio.run(build())
    finally:
        log.info("MatchLoL generation finished in %.2fs", perf_counter() - started)


async def run_match_job(factory, *args, **kwargs):
    """Keep at most one submitted job per caller loop, even after cancellation.

    A running SQL/Pillow call cannot be killed safely. Cancelling the waiter
    leaves the worker finishing its cleanup before the next job can start.
    """
    loop = asyncio.get_running_loop()
    gate = _gates.setdefault(loop, asyncio.Semaphore(1))
    await gate.acquire()
    try:
        future = loop.run_in_executor(_executor, _execute, factory, args, kwargs)
    except BaseException:
        gate.release()
        raise

    def finished(result):
        gate.release()
        if not result.cancelled():
            result.exception()  # Retrieve failures even if the waiter was cancelled.

    future.add_done_callback(finished)
    return await asyncio.shield(future)


def fetch_rows(query, params=None):
    """Execute and materialize SQL rows in the same worker and connection scope."""
    from sqlalchemy import text
    from fonctions.gestion_bdd import engine

    with engine.connect() as connection:
        return connection.execute(text(query), params or {}).fetchall()
