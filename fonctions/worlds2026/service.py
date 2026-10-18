"""Une seule collecte pour tous les serveurs, aucune opération SQL sur la boucle Discord."""
import asyncio
import logging
import time

import aiohttp

from .domain import utcnow, timestamp
from .sources import configured_sources, fetch_safely

log = logging.getLogger(__name__)


class Synchronizer:
    def __init__(self, store, sources=None):
        self.store = store
        self.sources = configured_sources() if sources is None else sources
        self.lock = asyncio.Lock()
        self.next_attempt = {}
        self.failures = {}
        self.last_report = "Aucune synchronisation effectuée."

    async def run(self):
        async with self.lock:
            guilds = await asyncio.to_thread(self.store.enabled_guilds)
            if not guilds:
                return "Aucun serveur activé."
            reports = []
            async with aiohttp.ClientSession() as session:
                for source in self.sources:
                    if time.monotonic() < self.next_attempt.get(source.name, 0):
                        reports.append(f"{source.name} : délai entre collectes en cours.")
                        continue
                    snapshot, message = await fetch_safely(source, session)
                    failure_count = 0 if snapshot else self.failures.get(source.name, 0) + 1
                    self.failures[source.name] = failure_count
                    delay = min(3600, 600 * 2 ** min(failure_count, 3))
                    self.next_attempt[source.name] = time.monotonic() + delay
                    await asyncio.to_thread(self.store.record_health, source.name, message, snapshot is not None)
                    reports.append(f"{source.name} : {message}")
                    if snapshot:
                        for guild in guilds:
                            try:
                                report = await asyncio.to_thread(self.store.ingest, guild, snapshot.fixtures)
                                if report["errors"]:
                                    reports.append(f"Serveur {guild} : {len(report['errors'])} anomalies (voir /worlds_admin statut).")
                            except Exception:
                                # Une panne d'un serveur ne supprime pas les données ni les autres collectes.
                                log.exception("Worlds 2026 : échec d'import du serveur %s", guild)
                                reports.append(f"Serveur {guild} : échec de l'enregistrement.")
            self.last_report = "\n".join(reports)
            return self.last_report

    async def automatic(self):
        # Après novembre, le classement reste consultable sans polling perpétuel.
        if timestamp("2026-10-01T00:00:00Z") <= utcnow() < timestamp("2026-12-01T00:00:00Z"):
            return await self.run()
