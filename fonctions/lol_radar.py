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
    end = next((t for t in stamps if t >= 900000), None)
    prefix = [t for t in stamps if end is not None and t <= end]
    complete = (duration is not None and duration >= 900 and prefix and prefix[0] <= 1000
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


def historical_proximity(snapshot, pid):
    """Les relevés du jungler et du laner décrivent la même distance."""
    result = {}
    team = snapshot.get("tracked_team")
    if snapshot.get("version") != 1 or team not in (100, 200):
        return result
    players = [p for p in snapshot.get("players") or [] if p.get("team") == team]
    adc_count = sum(p.get("role") == "ADC" for p in players)
    for player in players:
        own = object_data(player.get("own"))
        near, valid = number(own.get("near")), number(own.get("valid"))
        if not valid or near is None or near > valid:
            continue
        if player.get("id") == pid:
            result["prox_jg"] = 100 * near / valid
        elif own.get("jungler") == pid and player.get("role") == "ADC" and adc_count == 1:
            result["prox_adc"] = 100 * near / valid
    return result


def historical_kp15(match, deaths, pid, ka15):
    if ka15 is None or not isinstance(deaths, list) or pid not in range(1, 11):
        return None
    allies = range(1, 6) if pid <= 5 else range(6, 11)
    kills = [event for event in deaths if event.get("killer") in allies]
    if len(kills) != number(match.get("team_kills")):
        return None
    stamps = [number(event.get("t")) for event in kills]
    if None in stamps:
        return None
    team15 = sum(t <= 900000 for t in stamps)
    return 100 * ka15 / team15 if team15 and ka15 <= team15 else None


def match_metrics(match, details, events=None, first_blood=None):
    details = object_data(details)
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
    result["fb"] = 100 * first_blood if isinstance(first_blood, bool) else None
    pid_index = number(match.get("id_participant"))
    pid = int(pid_index) + 1 if pid_index in range(10) else None
    if pid is not None:
        result.update(historical_proximity(object_data(details.get("jungle_proximity")), pid))
    events = object_data(events)
    if encoded is not None and encoded >= 15 and k is not None and a is not None:
        # The saved event clock is rounded to the second. At 15:00 the side
        # of the cutoff is ambiguous. Also reject incomplete player histories.
        if k + a == 0:
            result["ka15"] = 0
        elif events.get("total") == k + a and events.get("boundary") is False:
            result["ka15"] = number(events.get("early"))
    saved = object_data(details.get("radar"))
    if saved.get("version") == VERSION:
        for key, value in object_data(saved.get("metrics")).items():
            numeric = number(value)
            if key in result and numeric is not None:
                result[key] = numeric
    if result["kp15"] is None:
        result["kp15"] = historical_kp15(match, details.get("deaths"), pid, result["ka15"])
    return result


def aggregate(rows):
    metrics = [match_metrics(object_data(r.get("match")), r.get("details"), r.get("events"),
                             r.get("first_blood")) for r in rows]
    result = {}
    for key, label, cap, unit in AXES:
        values = [m[key] for m in metrics if m[key] is not None]
        value = sum(values) / len(values) if values else None
        result[key] = {"value": value, "n": len(values),
                       "score": min(100, 100 * value / cap) if value is not None else None}
    return result


def radar_query(riot_id, riot_tag, guild_id, season, role_filter=None,
                champion=None, has_details=True, has_events=False, has_scoring=False):
    if isinstance(season, bool) or not isinstance(season, int) or season < 1:
        raise ValueError("Choisis un numéro de saison supérieur ou égal à 1.")
    if role_filter and role_filter not in set(ROLES.values()):
        raise ValueError("Rôle non pris en charge.")
    params = {"riot_id": riot_id.lower().replace(" ", ""), "tag": riot_tag.strip().lstrip("#").upper(),
              "guild": int(guild_id), "season": season, "previous_season": season - 1}
    filters = ["t.riot_id = :riot_id", "t.riot_tagline = :tag", "t.server_id = :guild",
               "m.mode = 'RANKED'", "m.season IN (:season, :previous_season)"]
    if role_filter:
        filters.append("m.role = :role")
        params["role"] = role_filter
    if champion:
        from fonctions.recap_filters import normalize_champion
        params["champion"] = normalize_champion(champion)
        if not params["champion"]:
            raise ValueError("Précise un nom de champion.")
        filters.append("REGEXP_REPLACE(LOWER(m.champion), '[^a-z0-9]', '', 'g') = :champion")
    join = "LEFT JOIN match_recap_details d ON d.match_id = m.match_id AND d.joueur = m.joueur" if has_details else ""
    details = """jsonb_build_object('radar', d.data->'radar', 'jungle_proximity', d.data->'jungle_proximity',
                                    'deaths', d.data#>'{map,deaths}')""" if has_details else "NULL"
    ctes = ""
    events = first_blood = "NULL"
    if has_events:
        # CHAMPION_KILL contains only the tracked player's takedowns in this
        # account-scoped table. Their own deaths are stored as DEATHS.
        ctes += """, takedowns AS (
            SELECT DISTINCT e.match_id, e.riot_id, e.timestamp, e."killerId", e."victimId"
            FROM data_timeline_events e JOIN selected m ON e.match_id = m.match_id AND e.riot_id = m.joueur
            WHERE e.type = 'CHAMPION_KILL' AND e."killerId" BETWEEN 1 AND 10
              AND e."victimId" BETWEEN 1 AND 10 AND e.timestamp >= 0
        ), event_counts AS (
            SELECT match_id, riot_id, count(*) AS total, count(*) FILTER (WHERE timestamp < 15) AS early,
                   bool_or(timestamp = 15) AS boundary FROM takedowns GROUP BY match_id, riot_id
        )"""
        join += " LEFT JOIN event_counts e ON e.match_id = m.match_id AND e.riot_id = m.joueur"
        events = "to_jsonb(e)"
    if has_scoring:
        # Old scoring rows can contain default false flags for a missing
        # timeline. Require a known first-blood killer in that match.
        ctes += """, fb_scores AS (
            SELECT s.match_id, CASE WHEN bool_or(s.has_first_blood) AND count(*) FILTER (WHERE
                lower(replace(s.riot_id, ' ', '')) = :riot_id AND upper(s.riot_tag) = :tag) = 1 THEN
                bool_or(s.has_first_blood OR s.has_first_blood_assist) FILTER (WHERE
                lower(replace(s.riot_id, ' ', '')) = :riot_id AND upper(s.riot_tag) = :tag) END AS participated
            FROM match_player_scoring_data s JOIN selected m ON m.match_id = s.match_id GROUP BY s.match_id
        )"""
        join += " LEFT JOIN fb_scores f ON f.match_id = m.match_id"
        first_blood = "f.participated"
    sql = f"""WITH deduplicated AS (
        SELECT m.*, ROW_NUMBER() OVER (PARTITION BY m.match_id ORDER BY m.datetime DESC NULLS LAST, m.id DESC) AS rn
        FROM matchs m JOIN tracker t ON t.id_compte = m.joueur
        WHERE {' AND '.join(filters)}
    ), selected AS (
        SELECT * FROM deduplicated WHERE rn = 1
    ){ctes} SELECT to_jsonb(m) AS match, {details} AS details, {events} AS events,
                   {first_blood} AS first_blood FROM selected m {join}
      ORDER BY m.datetime DESC NULLS LAST, m.id DESC"""
    return sql, params


def load_radar(riot_id, riot_tag, guild_id, season, role_filter=None, champion=None):
    from fonctions.gestion_bdd import lire_bdd_perso
    if season is None:
        from utils.params import saison
        season = saison
    if riot_tag is None:
        accounts = lire_bdd_perso(
            """SELECT DISTINCT riot_tagline FROM tracker WHERE server_id = :guild AND riot_id = :riot_id
               ORDER BY riot_tagline""", index_col=None,
            params={"guild": int(guild_id), "riot_id": riot_id.lower().replace(" ", "")}).T
        if accounts.empty:
            raise ValueError("Aucun compte suivi sous ce pseudo sur ce serveur.")
        if len(accounts) > 1:
            tags = ", ".join("#" + tag for tag in accounts["riot_tagline"])
            raise ValueError(f"Plusieurs comptes portent ce pseudo sur ce serveur. Précise riot_tag ({tags}).")
        riot_tag = accounts.iloc[0]["riot_tagline"]
    tables = lire_bdd_perso("""SELECT to_regclass('match_recap_details') IS NOT NULL AS has_details,
        to_regclass('data_timeline_events') IS NOT NULL AS has_events,
        to_regclass('match_player_scoring_data') IS NOT NULL AS has_scoring""", index_col=None).T
    sql, params = radar_query(riot_id, riot_tag, guild_id, season, role_filter, champion, **tables.iloc[0].to_dict())
    rows = lire_bdd_perso(sql, index_col=None, params=params).T.to_dict("records")
    current = [r for r in rows if number(object_data(r.get("match")).get("season")) == season]
    previous = [r for r in rows if number(object_data(r.get("match")).get("season")) == season - 1]
    return {"current": aggregate(current), "previous": aggregate(previous), "tag": params["tag"],
            "games": len(current), "previous_games": len(previous), "season": season, "previous_season": season - 1}


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
    current_label, previous_label = f"Saison {data['season']}", f"Saison {data['previous_season']}"
    draw.text((48, 119), f"{current_label} : {data['games']} parties   •   {previous_label} : {data['previous_games']} parties", font=font(20), fill=muted)
    axes = [axis for axis in AXES if data["current"][axis[0]]["n"] or data["previous"][axis[0]]["n"]]
    show_chart = len(axes) >= 3
    cx, cy, radius = 400, 480, 255
    def point(i, value):
        angle = -math.pi / 2 + i * math.tau / len(axes)
        return cx + math.cos(angle) * radius * value / 100, cy + math.sin(angle) * radius * value / 100
    for level in (20, 40, 60, 80, 100) if show_chart else ():
        draw.ellipse((cx-radius*level/100, cy-radius*level/100, cx+radius*level/100, cy+radius*level/100), outline="#34405c", width=2)
        draw.text((cx+5, cy-radius*level/100+3), str(level), fill=muted, font=font(13))
    for i, (_, label, _, _) in enumerate(axes if show_chart else []):
        draw.line(((cx, cy), point(i, 100)), fill="#34405c", width=2)
        draw.text(point(i, 120), label, font=font(24), fill=white, anchor="mm")
    def polygon(series, color, dashed=False):
        points = [point(i, series[key]["score"]) if series[key]["score"] is not None else None
                  for i, (key, *_) in enumerate(axes)]
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
    if show_chart:
        polygon(data["current"], cyan)
        polygon(data["previous"], white, True)
    table_x = 820 if show_chart else 48
    draw.text((table_x, 211), "VALEURS MOYENNES" if axes else "Aucune mesure disponible avec ces filtres.", font=font(23), fill=white)
    columns = [(table_x + 180, "current", cyan)]
    if data["previous_games"]:
        columns.append((table_x + 360, "previous", white))
    for x, name, color in columns:
        if axes:
            draw.text((x, 257), current_label if name == "current" else previous_label, font=font(18), fill=color)
    for i, (key, label, cap, unit) in enumerate(axes):
        y = 300 + i * 53
        draw.text((table_x, y), label, font=font(21), fill=white)
        for x, name, color in columns:
            item = data[name][key]
            value = "—" if item["value"] is None else f"{item['value']:.2f}{unit}"
            draw.text((x, y), value, font=font(18), fill=color)
            if item["n"]:
                draw.text((x, y+23), f"n={item['n']}", font=font(14), fill=muted)
    legend = f"Cyan · {current_label}"
    if data["previous_games"]:
        legend += f"     {'Pointillés' if show_chart else 'Blanc'} · {previous_label}"
    draw.text((48, 820), legend, font=font(21), fill=white)
    missing = [axis[1] for axis in AXES if axis not in axes]
    lines = ["Chaque moyenne porte sur les n parties renseignées. Un tiret indique une saison sans mesure."]
    if show_chart:
        lines.append("Échelle 0–100 selon le plafond de chaque axe · KDA et K+A@15  10  •  VSPM  4  •  Autres  100 %")
    if missing:
        lines.append("Sans mesure applicable sur les deux saisons · " + ", ".join(missing))
    else:
        lines.append("Proximité entre 2 et 14 minutes, à 2 000 unités ou moins.")
    for i, line in enumerate(lines):
        draw.text((48, 866+i*28), line, font=font(17), fill=muted)
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()
