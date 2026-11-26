"""Diagnostic réseau sans écrire en BDD ni envoyer de message Discord.

Depuis la racine : python -m scripts.check_worlds2026_sources
Les clés optionnelles sont lues dans l'environnement ; elles ne sont pas affichées.
"""
import asyncio
import json

import aiohttp

from fonctions.worlds2026.sources import configured_sources, fetch_safely


async def main():
    async with aiohttp.ClientSession() as session:
        for source in configured_sources():
            snapshot, message = await fetch_safely(source, session)
            print(json.dumps({"source": source.name, "ok": snapshot is not None, "detail": message}, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
