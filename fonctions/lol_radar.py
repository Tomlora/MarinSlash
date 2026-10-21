"""Radar de compte : mesures versionnées, agrégation et rendu sans accès réseau."""
import json
import logging
import math
from io import BytesIO

log = logging.getLogger(__name__)
VERSION = 1
# Plafonds graphiques explicites, pas des percentiles ni des notes de performance.
AXES = (
    ("kda", "KDA", 10, ""), ("kp", "KP%", 100, "%"),
    ("vspm", "VSPM", 4, "/min"), ("fb", "FB%", 100, "%"),
    ("ka15", "K+A@15", 10, ""), ("kp15", "KP@15", 100, "%"),
    ("prox_adc", "Prox ADC", 100, "%"), ("prox_jg", "Prox JG", 100, "%"),
)
ROLES = {"TOP": "TOP", "JUNGLE": "JUNGLE", "MIDDLE": "MID", "MID": "MID",
         "BOTTOM": "ADC", "ADC": "ADC", "UTILITY": "SUPPORT", "SUPPORT": "SUPPORT"}
MODES = ("RANKED", "FLEX", "NORMAL", "SWIFTPLAY")


def number(value):
    if isinstance(value, bool):
        return None
    try:
        value = float(value)
        return value if math.isfinite(value) and value >= 0 else None
    except (TypeError, ValueError):
        return None


def object_data(value):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            return {}
    return value if isinstance(value, dict) else {}


def role(player):
    return ROLES.get(player.get("teamPosition") or player.get("individualPosition"))


def active_position(sample):
    if not isinstance(sample, dict):
        return None
    health = number((sample.get("championStats") or {}).get("health"))
    pos = sample.get("position") or {}
    x, y = number(pos.get("x")), number(pos.get("y"))
    if health is None or health <= 0 or x is None or y is None or x > 15000 or y > 15000:
        return None
    if any(math.dist((x, y), base) <= 2500 for base in ((0, 0), (15000, 15000))):
        return None
    return x, y


def build_snapshot(detail, timeline, puuid):
    """Un compte identifié par PUUID, y compris avec le DataFrame MatchLol."""
    info = detail.get("info", {}) if detail is not None else {}
    players = info.get("participants") or []
    if info.get("mapId") != 11 or len(players) != 10:
        return None
    if {p.get("participantId") for p in players} != set(range(1, 11)):
        return None
    if sorted(p.get("teamId", 0) for p in players) != [100] * 5 + [200] * 5:
        return None
    tracked = [p for p in players if puuid and p.get("puuid") == puuid]
    if len(tracked) != 1:
        return None
    p = tracked[0]
    pid, team = p["participantId"], p["teamId"]
    allies = [q for q in players if q["teamId"] == team]
    ally_ids = {q["participantId"] for q in allies}
    metrics = {key: None for key, *_ in AXES}
    k, a, d = (number(p.get(key)) for key in ("kills", "assists", "deaths"))
    team_kills = [number(q.get("kills")) for q in allies]
    if k is not None and a is not None:
        if d is not None:
            metrics["kda"] = (k + a) / max(1, d)
        if all(v is not None for v in team_kills) and sum(team_kills) > 0:
            metrics["kp"] = 100 * (k + a) / sum(team_kills)
    duration, vision = number(info.get("gameDuration")), number(p.get("visionScore"))
    if duration and vision is not None:
        metrics["vspm"] = vision * 60 / duration
    fbk, fba = p.get("firstBloodKill"), p.get("firstBloodAssist")
    if isinstance(fbk, bool) and isinstance(fba, bool):
        metrics["fb"] = 100.0 if fbk or fba else 0.0

    frames = timeline.get("info", {}).get("frames", []) if isinstance(timeline, dict) else []
    # Require a continuous prefix through 15:00 before interpreting absence of kills as zero.
    stamps = sorted({number(f.get("timestamp")) for f in frames} - {None})
    prefix = [t for t in stamps if t <= 901000]
    complete = (duration is not None and duration >= 900 and prefix and prefix[0] <= 1000
                and prefix[-1] >= 900000
                and all(b - a <= 61000 for a, b in zip(prefix, prefix[1:]))
                and all(isinstance(f.get("events"), list) for f in frames
                        if number(f.get("timestamp")) in prefix))
    if complete:
        seen, ka, tk = set(), 0, 0
        for frame in frames:
            for event in frame.get("events", []):
                stamp = number(event.get("timestamp"))
                if event.get("type") != "CHAMPION_KILL" or stamp is None or stamp > 900000:
                    continue
                key = (stamp, event.get("victimId"), event.get("killerId"))
                if key in seen:
                    continue
                seen.add(key)
                if event.get("killerId") in ally_ids:
                    tk += 1
                    ka += (event.get("killerId") == pid or pid in (event.get("assistingParticipantIds") or []))
        metrics["ka15"] = float(ka)
        metrics["kp15"] = 100 * ka / tk if tk else None

    samples = {number(f.get("timestamp")): f.get("participantFrames") or {} for f in frames
               if number(f.get("timestamp")) is not None and 120000 <= number(f.get("timestamp")) < 840000}
    coverage = {}
    for key, wanted in (("prox_jg", "JUNGLE"), ("prox_adc", "ADC")):
        targets = [q for q in allies if role(q) == wanted]
        if wanted == "JUNGLE" and not targets:
            targets = [q for q in allies if 11 in (q.get("summoner1Id"), q.get("summoner2Id"))]
        near = valid = 0
        if len(targets) == 1 and targets[0]["participantId"] != pid:
            target = targets[0]["participantId"]
            for sample in samples.values():
                xy, other = active_position(sample.get(str(pid))), active_position(sample.get(str(target)))
                if xy is not None and other is not None:
                    valid += 1
                    near += math.dist(xy, other) <= 2000
        coverage[key] = {"near": near, "valid": valid}
        metrics[key] = 100 * near / valid if valid else None
    return {"version": VERSION, "role": role(p), "metrics": metrics, "coverage": coverage}


def snapshot_for_match(match):
    try:
        return build_snapshot(getattr(match, "match_detail", None),
                              getattr(match, "data_timeline", {}), getattr(match, "puuid", None))
    except (TypeError, ValueError, AttributeError, KeyError):
        log.exception("Radar indisponible pour %s", getattr(match, "last_match", "?"))
        return None


def match_metrics(match, details):
    saved = object_data(object_data(details).get("radar"))
    if saved.get("version") == VERSION:
        return {key: number(object_data(saved.get("metrics")).get(key)) for key, *_ in AXES}
    result = {key: None for key, *_ in AXES}
    k, a, d, team = (number(match.get(key)) for key in ("kills", "assists", "deaths", "team_kills"))
    if k is not None and a is not None:
        result["kda"] = (k + a) / max(1, d) if d is not None else None
        result["kp"] = 100 * (k + a) / team if team else None
    # Legacy time is mm.ss, not decimal minutes; vision_min used that encoded value.
    encoded, vision = number(match.get("time")), number(match.get("vision_score"))
    if encoded is not None and vision is not None:
        minutes = int(encoded)
        seconds = round((encoded - minutes) * 100)
        duration = minutes * 60 + seconds
        if 0 <= seconds < 60 and duration > 0:
            result["vspm"] = vision * 60 / duration
    return result


def aggregate(rows):
    metrics = [match_metrics(object_data(r.get("match")), r.get("details")) for r in rows]
    result = {}
    for key, label, cap, unit in AXES:
        values = [m[key] for m in metrics if m[key] is not None]
        value = sum(values) / len(values) if values else None
        result[key] = {"value": value, "n": len(values),
                       "score": min(100, 100 * value / cap) if value is not None else None}
    return result


def radar_query(riot_id, riot_tag, guild_id, games=20, mode="RANKED", role_filter=None,
                champion=None, season=None, has_details=True):
    if isinstance(games, bool) or not isinstance(games, int) or not 1 <= games <= 100:
        raise ValueError("Choisis entre 1 et 100 parties.")
    if mode not in MODES or (role_filter and role_filter not in set(ROLES.values())):
        raise ValueError("Mode ou rôle non pris en charge.")
    params = {"riot_id": riot_id.lower().replace(" ", ""), "tag": riot_tag.strip().lstrip("#").upper(),
              "guild": int(guild_id), "mode": mode, "limit": games * 2}
    filters = ["t.riot_id = :riot_id", "t.riot_tagline = :tag", "t.server_id = :guild", "m.mode = :mode"]
    if role_filter:
        filters.append("m.role = :role")
        params["role"] = role_filter
    if champion:
        from fonctions.recap_filters import normalize_champion
        params["champion"] = normalize_champion(champion)
        if not params["champion"]:
            raise ValueError("Précise un nom de champion.")
        filters.append("REGEXP_REPLACE(LOWER(m.champion), '[^a-z0-9]', '', 'g') = :champion")
    if season is not None:
        filters.append("m.season = :season")
        params["season"] = season
    join = "LEFT JOIN match_recap_details d ON d.match_id = m.match_id AND d.joueur = m.joueur" if has_details else ""
    details = "d.data" if has_details else "NULL"
    sql = f"""WITH deduplicated AS (
        SELECT m.*, ROW_NUMBER() OVER (PARTITION BY m.match_id ORDER BY m.datetime DESC NULLS LAST, m.id DESC) AS rn
        FROM matchs m JOIN tracker t ON t.id_compte = m.joueur
        WHERE {' AND '.join(filters)}
    ), selected AS (
        SELECT * FROM deduplicated WHERE rn = 1
        ORDER BY datetime DESC NULLS LAST, id DESC LIMIT :limit
    ) SELECT to_jsonb(m) AS match, {details} AS details FROM selected m {join}
      ORDER BY m.datetime DESC NULLS LAST, m.id DESC"""
    return sql, params


def load_radar(riot_id, riot_tag, guild_id, games=20, mode="RANKED", role_filter=None, champion=None, season=None):
    from fonctions.gestion_bdd import lire_bdd_perso
    exists = lire_bdd_perso("SELECT to_regclass('match_recap_details') AS relation", index_col=None).T
    has_details = not exists.empty and isinstance(exists.iloc[0]["relation"], str)
    sql, params = radar_query(riot_id, riot_tag, guild_id, games, mode, role_filter, champion, season, has_details)
    rows = lire_bdd_perso(sql, index_col=None, params=params).T.to_dict("records")
    current, previous = rows[:games], rows[games:]
    return {"current": aggregate(current), "previous": aggregate(previous),
            "games": len(current), "previous_games": len(previous)}


def render_radar(data, title, subtitle):
    """Pillow : rendu concurrent en mémoire, sans pyplot ni fichier partagé."""
    from PIL import Image, ImageDraw, ImageFont
    image = Image.new("RGB", (1400, 980), "#080d26")
    draw = ImageDraw.Draw(image)
    def font(size):
        for name in ("DejaVuSans.ttf", "C:/Windows/Fonts/arial.ttf"):
            try:
                return ImageFont.truetype(name, size)
            except OSError:
                pass
        return ImageFont.load_default()
    white, muted, cyan = "#eef3ff", "#a2b2cc", "#22e6ef"
    draw.text((48, 30), title[:65], font=font(34), fill=white)
    draw.text((48, 82), subtitle[:110], font=font(20), fill=muted)
    draw.text((48, 119), f"Récent : {data['games']} parties   •   Précédent : {data['previous_games']} parties", font=font(20), fill=muted)
    cx, cy, radius = 400, 480, 255
    def point(i, value):
        angle = -math.pi / 2 + i * math.tau / 8
        return cx + math.cos(angle) * radius * value / 100, cy + math.sin(angle) * radius * value / 100
    for level in (20, 40, 60, 80, 100):
        draw.ellipse((cx-radius*level/100, cy-radius*level/100, cx+radius*level/100, cy+radius*level/100), outline="#34405c", width=2)
        draw.text((cx+5, cy-radius*level/100+3), str(level), fill=muted, font=font(13))
    for i, (_, label, _, _) in enumerate(AXES):
        draw.line(((cx, cy), point(i, 100)), fill="#34405c", width=2)
        draw.text(point(i, 120), label, font=font(24), fill=white, anchor="mm")
    def polygon(series, color, dashed=False):
        points = [point(i, series[key]["score"]) if series[key]["score"] is not None else None
                  for i, (key, *_) in enumerate(AXES)]
        if not dashed and all(p is not None for p in points):
            overlay = Image.new("RGBA", image.size)
            ImageDraw.Draw(overlay).polygon(points, fill=(34, 230, 239, 55))
            image.paste(overlay, (0, 0), overlay)
        for a, b in zip(points, points[1:] + points[:1]):
            if a is None or b is None:
                continue
            if dashed:
                length = math.dist(a, b)
                for step in range(0, max(1, int(length)), 16):
                    start, end = step / max(1, length), min(1, (step+8)/max(1, length))
                    draw.line([(a[0]+(b[0]-a[0])*t, a[1]+(b[1]-a[1])*t) for t in (start, end)], fill=color, width=3)
            else:
                draw.line((a, b), fill=color, width=5)
        for p in points:
            if p is not None:
                draw.ellipse((p[0]-4, p[1]-4, p[0]+4, p[1]+4), fill=color)
    polygon(data["current"], cyan)
    polygon(data["previous"], white, True)
    draw.text((820, 211), "VALEURS MOYENNES", font=font(23), fill=white)
    draw.text((1000, 257), "Récent", font=font(18), fill=cyan)
    draw.text((1180, 257), "Précédent", font=font(18), fill=white)
    for i, (key, label, cap, unit) in enumerate(AXES):
        y = 300 + i * 53
        draw.text((820, y), label, font=font(21), fill=white)
        for x, name, color in ((1000, "current", cyan), (1180, "previous", white)):
            item = data[name][key]
            value = "N/D" if item["value"] is None else f"{item['value']:.2f}{unit}"
            draw.text((x, y), value, font=font(18), fill=color)
            draw.text((x, y+23), f"n={item['n']}", font=font(14), fill=muted)
    draw.text((48, 820), "Cyan : période récente   •   Pointillés : période précédente du même compte", font=font(21), fill=white)
    lines = ["Échelle 0–100 : valeur / plafond. KDA : 10 • VSPM : 4 • K+A@15 : 10 • Autres : 100%.",
             "Ce sont des repères graphiques, pas des percentiles ni une note globale. N/D : non disponible / non applicable.",
             "Proximités : relevés valides entre 2 et 14 min, distance ≤ 2 000. Une proximité élevée n'est pas toujours meilleure."]
    for i, line in enumerate(lines):
        draw.text((48, 866+i*28), line, font=font(17), fill=muted)
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()
