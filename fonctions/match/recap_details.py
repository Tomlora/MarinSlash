"""Détail des scores et or par minute, depuis les données du récap sauvegardé."""
import json
import logging
from io import BytesIO
from threading import Lock
from .score_explanations import build_dimension_explanations, explanation_fields

from fonctions.gestion_bdd import lire_bdd_perso, requete_perso_bdd
from fonctions.match.match_views import (
    load_match, number, fmt, make_pages, _finish, _champion_icon, tracked_team, truth,
)

log = logging.getLogger(__name__)
PLOT_LOCK = Lock()  # Matplotlib n'est pas thread-safe.
SCHEMA = """CREATE TABLE IF NOT EXISTS match_recap_details (
    match_id TEXT NOT NULL, joueur BIGINT NOT NULL, data JSONB NOT NULL,
    PRIMARY KEY (match_id, joueur)
)"""
DIMENSIONS = (
    ("combat_value", "⚔️ Combat"), ("economic_efficiency", "💰 Économie"),
    ("objective_contribution", "🎯 Objectifs"), ("pace_rating", "⚡ Tempo"),
    ("win_impact", "👑 Impact"),
)


def rows(sql, params):
    return lire_bdd_perso(sql, index_col=None, params=params).T.to_dict("records")


def object_data(value):
    return json.loads(value) if isinstance(value, str) else dict(value)


def minute_gold(timeline, participants):
    """Totaux des dix joueurs aux minutes entières ; aucun remplissage des trous."""
    teams = {str(p.get("participantId")): p.get("teamId") for p in participants}
    if len(teams) != 10 or list(teams.values()).count(100) != 5 or list(teams.values()).count(200) != 5:
        return []
    frames = timeline.get("info", {}).get("frames", []) if isinstance(timeline, dict) else []
    points = {}
    for frame in frames:
        stamp = number(frame.get("timestamp"))
        if stamp is None or stamp < 0:
            continue
        minute = int(stamp // 60000)
        drift = stamp - minute * 60000
        # Les frames Riot peuvent dériver légèrement. La frame finale partielle
        # ne doit pas remplacer celle de la minute précédente.
        if drift > 1000:
            continue
        players = frame.get("participantFrames") or {}
        totals = {100: 0, 200: 0}
        valid = True
        for pid, team in teams.items():
            gold = number(players.get(pid, {}).get("totalGold"))
            if gold is None or gold < 0:
                valid = False
                break
            totals[team] += gold
        if valid and (minute not in points or drift < points[minute][0]):
            points[minute] = (drift, {"minute": minute, "blue": totals[100], "red": totals[200]})
    return [points[m][1] for m in sorted(points)]


def snapshot(match_info):
    participants = getattr(match_info, "match_detail", {}).get("info", {}).get("participants", [])
    teams = {p.get("puuid"): p.get("teamId") for p in participants if p.get("puuid")}
    puuids = getattr(match_info, "thisPuuidListe", [])
    scores = []
    for summary in match_info.get_all_players_performance_summary():
        if not summary:
            continue
        index = summary["index"]
        if not 0 <= index < len(puuids):
            continue
        def at(name):
            values = getattr(match_info, name, [])
            return values[index] if index < len(values) else ""
        scores.append({
            "player_index": index, "riot_id": at("thisRiotIdListe"), "riot_tag": at("thisRiotTagListe"),
            "champion": at("thisChampNameListe"), "role": summary.get("role"),
            "scoring_version": summary.get("scoring_version", "legacy"),
            "scoring_supported": summary.get("scoring_supported", True),
            **{key: number(summary.get(key)) for key in ("statistical_score", "contribution_score", "utility_score")},
            "timeline_available": summary.get("timeline_available"),
            "scoring_inputs": summary.get("scoring_inputs", {}),
            "team": teams.get(puuids[index]), "tracked": puuids[index] == match_info.puuid,
            **{key: number(summary.get(key)) for key in ("score", "rank")},
            **{key: truth(summary.get(key)) for key in ("is_mvp", "is_ace")},
            **{key: number((summary.get("breakdown") or {}).get(key)) for key, _ in DIMENSIONS},
        })
        if puuids[index] == match_info.puuid:
            metrics = getattr(match_info, 'player_metrics_liste', [])
            if index < len(metrics):
                explanations = build_dimension_explanations(metrics[index])
                if explanations:
                    scores[-1]['dimension_explanations'] = explanations
    return {"scores": scores, "gold": minute_gold(getattr(match_info, "data_timeline", {}), participants)}


def save_recap_details(match_info):
    """Un échec de cette sauvegarde optionnelle ne bloque jamais le récap."""
    try:
        data = snapshot(match_info)
        if not data["scores"] and not data["gold"]:
            return False
        requete_perso_bdd(SCHEMA)
        requete_perso_bdd(
            """INSERT INTO match_recap_details (match_id, joueur, data)
               VALUES (:match_id, :joueur, CAST(:data AS JSONB))
               ON CONFLICT (match_id, joueur) DO UPDATE SET data = EXCLUDED.data""",
            {"match_id": match_info.last_match, "joueur": int(match_info.id_compte),
             "data": json.dumps(data, ensure_ascii=False, allow_nan=False)},
        )
        return True
    except Exception:
        log.exception("Sauvegarde des détails du récap impossible pour %s", match_info.last_match)
        return False


def load_details(match_id, joueur):
    match = load_match(match_id, joueur)
    if match is None:
        return None
    tables = rows(
        """SELECT to_regclass('public.match_recap_details') AS details,
                  to_regclass('public.match_scoring') AS scoring,
                  to_regclass('public.matchs_timestamp_gold') AS gold""", {},
    )[0]
    data = {}
    params = {"match_id": match_id, "joueur": int(joueur)}
    if tables["details"]:
        found = rows("SELECT data FROM match_recap_details WHERE match_id = :match_id AND joueur = :joueur", params)
        if found:
            data = object_data(found[0]["data"])
    return match, data, tables


def load_score(match_id, joueur):
    loaded = load_details(match_id, joueur)
    if loaded is None:
        return None
    match, data, tables = loaded
    scores = data.get("scores") or []
    if not scores and tables["scoring"]:
        # L'index de scoring est réordonné et peut venir d'un autre compte suivi.
        # Identifier par Riot ID + tag, jamais par matchs.id_participant.
        scores = [object_data(r["data"]) for r in rows(
            "SELECT to_jsonb(s) AS data FROM match_scoring s WHERE s.match_id = :match_id ORDER BY s.player_index",
            {"match_id": match_id},
        )]
        normalized = lambda v: str(v or "").replace(" ", "").casefold()
        for score in scores:
            score["tracked"] = normalized(f"{score.get('riot_id')}#{score.get('riot_tag')}") == normalized(match["player_name"])
    return match, scores


def player_label(player):
    champ = str(player.get("champion") or "?")[:40]
    name = str(player.get("riot_id") or "Joueur")[:40]
    tag = str(player.get("riot_tag") or "")[:10]
    return f"{_champion_icon(champ)} **{name}#{tag}** · {champ}"


def score_order(player):
    score = number(player.get("score"))
    return -(score if score is not None else -1), number(player.get("player_index")) or 0


def build_score_pages(match, scores):
    def pages(title, fields):
        return make_pages("📊 Détail du score · " + title, match, fields,
                          "Scores sauvegardés pour cette partie · Dimensions sur 10.", 0x9B59B6)
    tracked = [p for p in scores if truth(p.get("tracked"))]
    if len(tracked) != 1:
        return _finish(pages("Données indisponibles", [
            ("Score du compte", "Le détail du score n'est pas enregistré ou le compte ne peut pas être identifié dans ces anciennes données.")
        ]))
    player = tracked[0]
    known = [(label, number(player.get(key))) for key, label in DIMENSIONS if number(player.get(key)) is not None]
    dimensions = "\n".join(f"{label} : **{fmt(player.get(key))}/10**" for key, label in DIMENSIONS)
    fields = [
        ("Performance", f"{player_label(player)} · {str(player.get('role') or '?')[:20]}\n"
         f"Note **{fmt(player.get('score'))}/10** · Rang **{fmt(player.get('rank'), 0)}/{len(scores)}**"),
        ("Dimensions", dimensions),
    ]
    if player.get("scoring_version") in ("3.0", "4.0"):
        fields.append(("Calcul de la note", f"70 % statistiques ({fmt(player.get('statistical_score'))})"
                       f" + 30 % contribution ({fmt(player.get('contribution_score'))}) · v{player['scoring_version']}"))
        if player.get("timeline_available") is False:
            fields.append(("Données manquantes", "Timeline indisponible : composantes temporelles neutralisées."))
    if known:
        best, weak = max(known, key=lambda p: p[1]), min(known, key=lambda p: p[1])
        fields += [("💪 Point fort", f"{best[0]} · **{fmt(best[1])}/10**"),
                   ("📉 Axe de progression", f"{weak[0]} · **{fmt(weak[1])}/10**")]
    explanation = player.get('dimension_explanations') or {}
    details = explanation.get('dimensions', []) if explanation.get('version') in (1, 2) else []
    if not details:
        fields.append(("Pourquoi ces notes ?", "Les valeurs et barèmes nécessaires à cette explication n'ont pas été sauvegardés "
                       "avec ce récap. Les notes restent consultables ; un nouveau récap calculé avec cette fonctionnalité "
                       "inclura leur explication. Aucun détail n'est déduit des seules notes."))
    if player.get('scoring_supported') is False:
        fields.append(("Mode ou rôle non évalué", "Les références ne couvrent pas ce mode ou ce rôle inconnu : valeurs neutres, sans jugement de performance."))
    result = pages("Ta performance", fields)
    for detail in details:
        note = (f"{player_label(player)} · **{fmt(detail['score'])}/10**\n"
                "Les pourcentages indiquent ce qui compte le plus dans cette dimension. "
                "Chaque critère reste entre 0 et 10. "
                "Barèmes du bot appliqués lors de cette partie, adaptés au rôle et au profil du champion. "
                "Ces dimensions expliquent la partie « contribution » de la note globale (30 %).")
        if explanation.get('version') == 2:
            note += f" Durée : {fmt(explanation['duration_minutes'])} min. Repères provisoires : une valeur attendue vaut 5/10."
        dimension_pages = make_pages("📊 Pourquoi cette note · " + detail['title'], match,
                                     explanation_fields(detail), note, 0x9B59B6)
        if len(dimension_pages) > 1:
            for part, page in enumerate(dimension_pages, 1):
                page.title += f" · {part}/{len(dimension_pages)}"
        result += dimension_pages
    others = [p for p in scores if p is not player and number(p.get("score")) is not None]
    candidates = [p for p in others if truth(p.get("is_mvp"))]
    if not candidates:
        candidates = [p for p in others if p.get("team") == player.get("team")] or others
    if candidates:
        other = sorted(candidates, key=score_order)[0]
        comparisons = []
        for key, label in DIMENSIONS:
            current, reference = number(player.get(key)), number(other.get(key))
            delta = f"{current - reference:+.1f} pt" if current is not None and reference is not None else "—"
            comparisons.append((label, f"Toi **{fmt(current)}** · Comparé **{fmt(reference)}** · Écart **{delta}**"))
        result += make_pages("📊 Détail du score · Comparaison", match, comparisons,
                             f"Face à {player_label(other)} · {fmt(other.get('score'))}/10\n"
                             "Les rôles et champions peuvent différer.", 0x9B59B6)
    ranking = []
    for p in sorted(scores, key=score_order):
        badge = " 🏆 MVP" if truth(p.get("is_mvp")) else " ⭐ ACE" if truth(p.get("is_ace")) else ""
        team = ("Équipe du joueur" if p.get("team") == player.get("team") else "Équipe adverse") if p.get("team") is not None else "Équipe inconnue"
        ranking.append((f"#{fmt(p.get('rank'), 0)} · {fmt(p.get('score'))}/10{badge}",
                        f"{'▶ ' if truth(p.get('tracked')) else ''}{player_label(p)}\n"
                        f"{team} · {str(p.get('role') or '?')[:20]}"))
    result += pages("Classement du match", ranking)
    return _finish(result)


def load_gold(match_id, joueur):
    loaded = load_details(match_id, joueur)
    if loaded is None:
        return None
    match, data, tables = loaded
    gold = data.get("gold") or []
    if not gold and tables["gold"] and tracked_team(match) is not None:
        # Ancienne table : totaux alliés/adverses et timestamp en minutes.
        old = rows(
            """SELECT to_jsonb(g) AS data FROM matchs_timestamp_gold g
               WHERE g.match_id = :match_id AND g.riot_id = :joueur ORDER BY g.timestamp""",
            {"match_id": match_id, "joueur": int(joueur)},
        )
        for row in old:
            point = object_data(row["data"])
            minute = number(point.get("timestamp"))
            ally, enemy = number(point.get("gold_allie")), number(point.get("gold_adv"))
            if minute is None or minute < 0 or minute != int(minute) or ally is None or enemy is None:
                continue
            blue, red = (ally, enemy) if tracked_team(match) == 100 else (enemy, ally)
            gold.append({"minute": int(minute), "blue": blue, "red": red})
    valid = {}
    for p in gold:
        minute, blue, red = (number(p.get(k)) for k in ("minute", "blue", "red"))
        if minute is not None and minute >= 0 and minute == int(minute) and blue is not None and red is not None and min(blue, red) >= 0:
            valid[int(minute)] = {"minute": int(minute), "blue": blue, "red": red}
    return match, [valid[m] for m in sorted(valid)]


def gold_series(match, points):
    """Une seule série alliés - adversaires, du point de vue du compte du récap."""
    team = tracked_team(match)
    if team is None:
        return []
    sign = 1 if team == 100 else -1
    return [(p["minute"], sign * (p["blue"] - p["red"]) or 0) for p in points]


GOLD_POSITIVE = "#2563eb"
GOLD_NEGATIVE = "#dc2626"
GOLD_ZERO = "#64748b"


def gold_segments(series):
    """Couper au passage par zéro et ne jamais relier deux minutes non consécutives."""
    segments, colors = [], []
    for (x1, y1), (x2, y2) in zip(series, series[1:]):
        if x2 - x1 != 1:
            continue
        spans = [((x1, y1), (x2, y2))]
        if y1 * y2 < 0:
            zero = (x1 + (x2 - x1) * abs(y1) / (abs(y1) + abs(y2)), 0)
            spans = [((x1, y1), zero), (zero, (x2, y2))]
        for start, end in spans:
            value = (start[1] + end[1]) / 2
            segments.append([start, end])
            colors.append(GOLD_POSITIVE if value > 0 else GOLD_NEGATIVE if value < 0 else GOLD_ZERO)
    return segments, colors


def gold_embed(match, points):
    series = gold_series(match, points)
    if not points:
        fields = [("Données indisponibles", "Les totaux d'or par minute ne sont pas enregistrés pour cette partie. "
                   "Ils seront conservés dans les nouveaux récaps disposant d'une timeline.")]
    elif not series:
        fields = [("Équipe inconnue", "L'équipe du compte suivi n'est pas enregistrée pour ce match.")]
    else:
        minute, last = series[-1]
        ally_lead = max(value for _, value in series)
        enemy_lead = max(-value for _, value in series)
        fields = [
            ("Lecture", "Or de ton équipe − or de l'équipe adverse.\n"
             "🔵 Au-dessus de zéro : avantage allié · 🔴 En dessous : avantage adverse."),
            ("Dernière minute mesurée", f"**{minute}:00** · Différentiel **{last:+,.0f}** or".replace(",", " ")),
            ("Avantage maximal observé", f"Alliés **{fmt(max(0, ally_lead), 0)}** or"
             f" · Adversaires **{fmt(max(0, enemy_lead), 0)}** or"),
        ]
    embed = _finish(make_pages("💰 Différentiel d'or", match, fields,
                              "Un point par minute entière · Les minutes absentes restent des interruptions.", 0xF1C40F))[0]
    if series:
        embed.set_image(url="attachment://gold_diff.png")
    return embed


def render_gold(match, points):
    """Courbe gold_team : segments bleus/rouges et valeur affichée à chaque minute."""
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.collections import LineCollection
    from matplotlib.lines import Line2D
    from matplotlib.ticker import MultipleLocator, FuncFormatter

    series = gold_series(match, points)
    if not series:
        return None
    with PLOT_LOCK:
        first, last = series[0][0], series[-1][0]
        # Garder les valeurs de chaque minute lisibles, même sur une longue partie.
        width = max(12, min(36, (last - first + 1) * 0.3))
        fig = Figure(figsize=(width, 5.5), dpi=120, facecolor="white")
        FigureCanvasAgg(fig)
        ax = fig.subplots()
        ax.set_facecolor("white")
        segments, colors = gold_segments(series)
        ax.add_collection(LineCollection(segments, colors=colors, linewidths=2))
        for minute, value in series:
            color = GOLD_POSITIVE if value > 0 else GOLD_NEGATIVE if value < 0 else GOLD_ZERO
            ax.scatter([minute], [value], color=color, s=14, zorder=3)
            ax.annotate(f"{value:+,.0f}".replace(",", " "), (minute, value),
                        xytext=(0, 8 if value >= 0 else -12), textcoords="offset points",
                        ha="center", va="bottom" if value >= 0 else "top",
                        fontsize=7, rotation=45, color=color)
        ax.axhline(0, color=GOLD_ZERO, linewidth=1)
        peak = max(abs(value) for _, value in series)
        ax.set_ylim(-max(500, peak * 1.3), max(500, peak * 1.3))
        ax.set_xlim(first - 0.75, last + 0.75)
        ax.xaxis.set_major_locator(MultipleLocator(1))
        ax.yaxis.set_major_formatter(FuncFormatter(lambda value, pos: f"{value:+,.0f}".replace(",", " ") if value else "0"))
        ax.set_xlabel("Minute de jeu", color="#334155")
        ax.set_ylabel("Or allié − or adverse", color="#334155")
        ax.set_title(f"Écart d'or · {str(match.get('player_name') or 'Compte suivi')[:65]}",
                     color="#0f172a", fontsize=16, pad=18)
        ax.tick_params(colors="#475569", axis="both", labelsize=8)
        ax.grid(True, color="#cbd5e1", alpha=0.5)
        for spine in ax.spines.values():
            spine.set_color("#cbd5e1")
        ax.legend(handles=[
            Line2D([0], [0], color=GOLD_POSITIVE, label="Avantage allié", linewidth=2),
            Line2D([0], [0], color=GOLD_NEGATIVE, label="Avantage adverse", linewidth=2),
        ], loc="upper left")
        fig.tight_layout()
        output = BytesIO()
        fig.savefig(output, format="png", facecolor=fig.get_facecolor())
        return output.getvalue()


def gold_response(match_id, joueur):
    data = load_gold(match_id, joueur)
    if data is None:
        return None
    match, points = data
    return gold_embed(match, points), render_gold(match, points) if points else None
