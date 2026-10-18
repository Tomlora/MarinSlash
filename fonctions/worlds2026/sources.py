"""Connecteurs indépendants, délais/pagination bornés et résultats validés.

LoL Esports expose une API de site non contractuelle : la clé doit être fournie
par l'exploitant. Leaguepedia reste utilisable sans clé ; PandaScore est optionnel.
"""
import asyncio
from dataclasses import dataclass, field
import os
import re

import aiohttp

from .domain import Fixture, WorldsError, timestamp

HEADERS = {"User-Agent": "MarinSlash-Worlds2026/1.0 (https://github.com/Tomlora/MarinSlash)"}
CARGO_PAGE = "2026 Season World Championship"


class SourceError(RuntimeError):
    pass


@dataclass
class Snapshot:
    fixtures: list[Fixture] = field(default_factory=list)
    rejected: int = 0


async def get_json(session, url, params=None, headers=None):
    async with session.get(url, params=params, headers={**HEADERS, **(headers or {})},
                           timeout=aiohttp.ClientTimeout(total=20)) as response:
        if response.status != 200:
            # Ne pas exposer URL/requête/jeton dans les logs ou Discord.
            raise SourceError(f"HTTP {response.status}")
        data = await response.json(content_type=None)
        if isinstance(data, dict) and (data.get("error") or data.get("errors")):
            error = data.get("error")
            code = error.get("code", "unknown") if isinstance(error, dict) else "unknown"
            code = re.sub(r"[^a-zA-Z0-9_-]", "", str(code))[:50]
            raise SourceError(f"Erreur fournisseur JSON ({code})")
        return data


def _collect(rows, parser):
    result = Snapshot()
    for row in rows:
        try:
            fixture = parser(row)
            if fixture is not None:
                result.fixtures.append(fixture.normalized())
        except (KeyError, TypeError, ValueError, IndexError):
            result.rejected += 1
    return result


def parse_leaguepedia(row):
    overview = row["OverviewPage"]
    if overview != CARGO_PAGE and not overview.startswith(CARGO_PAGE + "/"):
        return None
    if str(row.get("HasTime", "0")) != "1":
        raise WorldsError("Horaire non confirmé")
    start = timestamp(str(row["DateTime UTC"]).replace(" ", "T") + "Z")
    winner = str(row.get("Winner") or "")
    s1, s2 = int(row.get("Team1Score") or 0), int(row.get("Team2Score") or 0)
    state = "scheduled"
    if str(row.get("IsNullified", "0")) == "1" or str(row.get("FF") or "0") not in ("0", ""):
        state = "cancelled"  # Aucun score exact attribué à un forfait.
    elif winner:
        if winner not in ("1", "2", row["Team1"], row["Team2"]):
            raise WorldsError("Gagnant inconnu")
        first_wins = winner in ("1", row["Team1"])
        if first_wins != (s1 > s2):
            raise WorldsError("Gagnant contradictoire")
        state = "finished"
    elif s1 or s2:
        state = "running"
    return Fixture("leaguepedia", str(row["MatchId"]), row["Team1"], row["Team2"],
                   start, int(row["BestOf"]), state, s1, s2,
                   str(row.get("Round") or overview.removeprefix(CARGO_PAGE)))


class Leaguepedia:
    name = "leaguepedia"

    async def fetch(self, session):
        rows = []
        for offset in range(0, 1000, 100):
            payload = await get_json(session, "https://lol.fandom.com/api.php", {
                "action": "cargoquery", "format": "json", "tables": "MatchSchedule",
                "fields": "MatchId,OverviewPage,Team1,Team2,DateTime_UTC,HasTime,BestOf,Team1Score,Team2Score,Winner,IsNullified,FF,Round",
                "where": f"OverviewPage='{CARGO_PAGE}' OR OverviewPage LIKE '{CARGO_PAGE}/%'",
                "order_by": "DateTime_UTC,MatchId", "limit": "100", "offset": str(offset),
            })
            page = [entry["title"] for entry in payload["cargoquery"]]
            rows.extend(page)
            if len(page) < 100:
                return _collect(rows, parse_leaguepedia)
        raise SourceError("Pagination Leaguepedia incomplète")


def parse_lolesports(event):
    if event.get("type") != "match":
        return None
    start = timestamp(event["startTime"])
    if not timestamp("2026-10-01T00:00:00Z") <= start < timestamp("2026-12-01T00:00:00Z"):
        return None
    match = event["match"]
    teams = match["teams"]
    if len(teams) != 2:
        raise WorldsError("Adversaires inconnus")
    state = {"unstarted": "scheduled", "inProgress": "running", "completed": "finished",
             "canceled": "cancelled", "cancelled": "cancelled"}[event["state"]]
    a, b = teams
    s1, s2 = (a.get("result") or {}).get("gameWins"), (b.get("result") or {}).get("gameWins")
    if state == "finished":
        if (a.get("result") or {}).get("outcome") != ("win" if s1 > s2 else "loss"):
            raise WorldsError("Gagnant incohérent")
    return Fixture("lolesports", str(match["id"]), a["name"], b["name"], start,
                   int(match["strategy"]["count"]), state, s1, s2,
                   str(event.get("blockName") or "Worlds 2026"))


class LoLEsports:
    name = "lolesports"
    base = "https://esports-api.lolesports.com/persisted/gw/"

    def __init__(self, key):
        self.key = key

    async def fetch(self, session):
        headers = {"x-api-key": self.key}
        payload = await get_json(session, self.base + "getLeagues", {"hl": "en-US"}, headers)
        leagues = [str(r["id"]) for r in payload["data"]["leagues"] if r.get("slug") == "worlds"]
        if len(leagues) != 1:
            raise SourceError("Ligue Worlds introuvable ou ambiguë")
        queue, seen, events = [None], set(), {}
        for _ in range(12):
            if not queue:
                return _collect(list(events.values()), parse_lolesports)
            token = queue.pop(0)
            if token in seen:
                continue
            seen.add(token)
            params = {"hl": "en-US", "leagueId": leagues[0]}
            if token is not None:
                params["pageToken"] = token
            payload = await get_json(session, self.base + "getSchedule", params, headers)
            schedule = payload["data"]["schedule"]
            for event in schedule["events"]:
                # Le filtre API est aussi vérifié dans la réponse.
                if event.get("league", {}).get("slug") == "worlds" and event.get("type") == "match":
                    events[str(event["match"]["id"])] = event
            for next_token in schedule.get("pages", {}).values():
                if next_token and next_token not in seen and next_token not in queue:
                    queue.append(next_token)
        if queue:
            raise SourceError("Pagination LoL Esports incomplète")
        return _collect(list(events.values()), parse_lolesports)


def parse_pandascore(row, series_ids):
    if int(row["serie"]["id"]) not in series_ids or int(row["serie"]["year"]) != 2026:
        return None
    if row.get("videogame", {}).get("slug") not in (None, "league-of-legends", "lol"):
        return None
    opponents = row["opponents"]
    if len(opponents) != 2:
        raise WorldsError("Adversaires inconnus")
    a, b = [v["opponent"] for v in opponents]
    results = {r["team_id"]: r["score"] for r in row.get("results", [])}
    state = {"not_started": "scheduled", "running": "running", "finished": "finished",
             "canceled": "cancelled", "postponed": "scheduled"}[row["status"]]
    if row.get("forfeit") or row.get("draw"):
        state = "cancelled"
    s1, s2 = results.get(a["id"]), results.get(b["id"])
    if state == "finished" and row.get("winner_id") != (a["id"] if s1 > s2 else b["id"]):
        raise WorldsError("Gagnant incohérent")
    return Fixture("pandascore", str(row["id"]), a["name"], b["name"],
                   timestamp(row.get("begin_at") or row["scheduled_at"]),
                   int(row["number_of_games"]), state, s1, s2,
                   str((row.get("tournament") or {}).get("name") or "Worlds 2026"))


class PandaScore:
    name = "pandascore"

    def __init__(self, token, series_ids):
        self.token, self.series_ids = token, series_ids

    async def fetch(self, session):
        if not self.series_ids:
            raise SourceError("Configurer WORLDS_PANDASCORE_SERIE_IDS pour les Worlds 2026")
        rows = []
        for page in range(1, 11):
            payload = await get_json(session, "https://api.pandascore.co/lol/matches", {
                "filter[serie_id]": ",".join(map(str, sorted(self.series_ids))),
                "sort": "begin_at,id", "page[size]": "100", "page[number]": str(page),
            }, {"Authorization": f"Bearer {self.token}"})
            if not isinstance(payload, list):
                raise SourceError("Réponse PandaScore invalide")
            rows.extend(payload)
            if len(payload) < 100:
                return _collect(rows, lambda row: parse_pandascore(row, self.series_ids))
        raise SourceError("Pagination PandaScore incomplète")


def configured_sources():
    sources = []
    if os.getenv("WORLDS_LOLESPORTS_API_KEY"):
        sources.append(LoLEsports(os.environ["WORLDS_LOLESPORTS_API_KEY"]))
    sources.append(Leaguepedia())
    if os.getenv("WORLDS_PANDASCORE_TOKEN"):
        try:
            ids = {int(i.strip()) for i in os.getenv("WORLDS_PANDASCORE_SERIE_IDS", "").split(",") if i.strip()}
        except ValueError:
            ids = set()
        sources.append(PandaScore(os.environ["WORLDS_PANDASCORE_TOKEN"], ids))
    return sources


async def fetch_safely(source, session):
    try:
        snapshot = await asyncio.wait_for(source.fetch(session), timeout=90)
        if not snapshot.fixtures:
            return None, f"Aucun match exploitable ({snapshot.rejected} lignes rejetées)"
        return snapshot, f"{len(snapshot.fixtures)} matchs ; {snapshot.rejected} lignes rejetées"
    except SourceError as exc:
        return None, str(exc)
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, KeyError, TypeError, IndexError) as exc:
        return None, f"Source indisponible ou schéma invalide ({type(exc).__name__})"
