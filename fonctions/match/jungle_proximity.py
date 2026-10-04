"""Proximité jungle observée sur les relevés Riot, sans interpolation."""
import logging
import math

from .map_view import finite, position

START_MS = 120_000
END_MS = 840_000
RADIUS = 2000
BASE_RADIUS = 2500
ROLES = {"TOP": "TOP", "MIDDLE": "MID", "MID": "MID", "BOTTOM": "ADC",
         "BOT": "ADC", "UTILITY": "SUPP", "SUPPORT": "SUPP", "JUNGLE": "JUNGLE"}
log = logging.getLogger(__name__)


def role(player):
    return ROLES.get(player.get("teamPosition") or player.get("individualPosition"), "?")


def jungler(players):
    candidates = [p for p in players if role(p) == "JUNGLE"]
    if not candidates:
        candidates = [p for p in players if 11 in (p.get("summoner1Id"), p.get("summoner2Id"))]
    return candidates[0]["participantId"] if len(candidates) == 1 else None


def active_position(sample):
    """Écarter morts, santé inconnue et présence dans l'une des deux bases."""
    if not isinstance(sample, dict):
        return None
    health = finite((sample.get("championStats") or {}).get("health"))
    xy = position(sample.get("position"))
    if health is None or health <= 0 or xy is None:
        return None
    if any(math.dist(xy, base) <= BASE_RADIUS for base in ((0, 0), (15000, 15000))):
        return None
    return xy


def build_snapshot(detail, timeline, puuid):
    info = detail.get("info", {}) if detail is not None else {}
    players = info.get("participants") or []
    if info.get("mapId") != 11 or len(players) != 10:
        return None
    if {p.get("participantId") for p in players} != set(range(1, 11)):
        return None
    if sorted(p.get("teamId", 0) for p in players) != [100] * 5 + [200] * 5:
        return None
    tracked = next((p["teamId"] for p in players if puuid and p.get("puuid") == puuid), None)
    junglers = {team: jungler([p for p in players if p["teamId"] == team]) for team in (100, 200)}
    frames = timeline.get("info", {}).get("frames", []) if isinstance(timeline, dict) else timeline
    # Un timestamp ne compte qu'une fois. Les trous ne sont jamais interpolés.
    samples = {}
    for frame in frames or []:
        stamp = finite(frame.get("timestamp"))
        if stamp is not None and START_MS <= stamp < END_MS:
            samples[stamp] = {int(pid): active_position(sample)
                              for pid, sample in (frame.get("participantFrames") or {}).items()
                              if str(pid) in {str(i) for i in range(1, 11)}}
    result = []
    for p in sorted(players, key=lambda p: (p["teamId"], p["participantId"])):
        pid, team = p["participantId"], p["teamId"]
        if pid in junglers.values() or role(p) == "JUNGLE":
            continue
        row = {"id": pid, "team": team, "role": role(p),
               "name": str(p.get("riotIdGameName") or p.get("summonerName") or "Joueur")[:60],
               "champion": str(p.get("championName") or "Champion inconnu")[:40]}
        for side, jungle_team in (("own", team), ("opponent", 300 - team)):
            jid = junglers[jungle_team]
            valid = near = 0
            for positions in samples.values():
                a, b = positions.get(pid), positions.get(jid)
                if a is not None and b is not None:
                    valid += 1
                    near += math.dist(a, b) <= RADIUS
            row[side] = {"jungler": jid, "near": near, "valid": valid,
                         "percent": round(100 * near / valid, 1) if valid else None}
        result.append(row)
    return {"version": 1, "tracked_team": tracked, "start_ms": START_MS, "end_ms": END_MS,
            "radius": RADIUS, "base_radius": BASE_RADIUS, "samples": len(samples), "players": result}


def snapshot_for_match(match):
    try:
        return build_snapshot(getattr(match, "match_detail", None),
                              getattr(match, "data_timeline", {}), getattr(match, "puuid", None))
    except (TypeError, ValueError, AttributeError, KeyError):
        log.exception("Proximité jungle indisponible pour %s", getattr(match, "last_match", "?"))
        return None
