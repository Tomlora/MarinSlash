"""Vues privées du match ; les anciens boutons Analyse / Progression restent compatibles."""
import json
import math
from datetime import datetime, timezone

import interactions

from fonctions.gestion_bdd import lire_bdd_perso
from fonctions.match.records_ui import _champion_icon

HISTORY_SIZE = 10


def _rows(sql, params):
    return lire_bdd_perso(sql, index_col=None, params=params).T.to_dict("records")


def _object(value):
    return json.loads(value) if isinstance(value, str) else dict(value)


def load_match(match_id, joueur):
    rows = _rows(
        """SELECT to_jsonb(m) AS data, t.riot_id, t.riot_tagline
           FROM matchs m JOIN tracker t ON t.id_compte = m.joueur
           WHERE m.match_id = :match_id AND m.joueur = :joueur LIMIT 1""",
        {"match_id": match_id, "joueur": int(joueur)},
    )
    if not rows:
        return None
    match = _object(rows[0]["data"])
    match["player_name"] = f"{rows[0]['riot_id']}#{rows[0]['riot_tagline']}"
    return match


def load_analysis(match_id, joueur):
    match = load_match(match_id, joueur)
    if match is None:
        return None
    # Cette table est optionnelle pour les installations sans historique TF.
    exists = _rows("SELECT to_regclass('public.match_teamfight_damage') AS table_name", {})
    if not exists or not exists[0]["table_name"]:
        return match, [], False
    fights = _rows(
        """SELECT to_jsonb(f) AS data FROM match_teamfight_damage f
           JOIN tracker t ON t.id_compte = :joueur
           WHERE f.match_id = :match_id AND f.analyzed_puuid = t.puuid
             AND f.puuid = t.puuid AND f.is_teamfight = TRUE
           ORDER BY f.start_ms, f.fight_id""",
        {"match_id": match_id, "joueur": int(joueur)},
    )
    return match, [_object(row["data"]) for row in fights], True


def load_progress(match_id, joueur):
    match = load_match(match_id, joueur)
    if match is None:
        return None
    if number(match.get("date")) is None:
        return match, []
    history = _rows(
        """SELECT to_jsonb(m) AS data FROM matchs m
           WHERE m.joueur = :joueur AND m.mode = :mode
             AND m.match_id <> :match_id AND m.date < :date
           ORDER BY m.date DESC, m.match_id DESC LIMIT 10""",
        {"joueur": int(joueur), "mode": match["mode"], "match_id": match_id, "date": match["date"]},
    )
    return match, [_object(row["data"]) for row in history]


def number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def fmt(value, digits=1):
    value = number(value)
    if value is None:
        return "—"
    return (f"{value:,.{digits}f}".rstrip("0").rstrip(".") if digits else f"{value:,.0f}").replace(",", " ")


def clock_ms(value):
    value = number(value)
    if value is None:
        return "—"
    seconds = max(0, int(value) // 1000)
    return f"{seconds // 60}:{seconds % 60:02d}"


def duration(value):
    # matchs.time conserve la représentation MM.SS du bot.
    value = number(value)
    return f"{value:.2f}".replace(".", ":") if value is not None else "—"


def outcome(value):
    if value is True or value == 1 or str(value).lower() in ("true", "victoire"):
        return "Victoire"
    if value is False or value == 0 or str(value).lower() in ("false", "défaite"):
        return "Défaite"
    return "Résultat inconnu"


def subject(match):
    name = str(match.get("player_name") or "Compte suivi")[:65]
    return f"**{name}** · {str(match.get('mode') or 'Mode inconnu')[:30]}\n{match['match_id']}"


def make_pages(title, match, fields, note="", color=0x5865F2, *, fields_per_page=5):
    pages = []
    fields = fields or [("Aucune donnée", "Les données de cette section ne sont pas disponibles.")]
    for start in range(0, len(fields), fields_per_page):
        page = interactions.Embed(
            title=title, description=subject(match) + ("\n" + note if note else ""), color=color,
        )
        for name, value in fields[start:start + fields_per_page]:
            page.add_field(name=str(name)[:256], value=str(value)[:900] or "—", inline=False)
        pages.append(page)
    return pages


def _finish(pages):
    for index, page in enumerate(pages):
        page.set_footer(text=f"Page {index + 1}/{len(pages)} · Données sauvegardées du compte du récap")
    return pages


def build_analysis_pages(match, fights, fights_available=True):
    champion = str(match.get("champion") or "Inconnu")[:50]
    pages = make_pages("📊 Analyse · Vue d'ensemble", match, [
        ("Partie", f"{outcome(match.get('victoire'))} · {duration(match.get('time'))} min\n"
         f"{_champion_icon(champion)} {champion} · {str(match.get('role') or 'Rôle inconnu')[:40]}"),
        ("Combat", f"**{fmt(match.get('kills'), 0)}/{fmt(match.get('deaths'), 0)}/{fmt(match.get('assists'), 0)}**"
         f" · KDA {fmt(match.get('kda'))}\nParticipation aux kills : {fmt(match.get('kp'))} %"),
        ("Dégâts", f"**{fmt(match.get('dmg'), 0)}** aux champions · {fmt(match.get('dmg_min'))}/min"),
        ("Économie", f"{fmt(match.get('cs_min'))} sbires/min · {fmt(match.get('gold_min'))} or/min"),
        ("Vision", f"Score **{fmt(match.get('vision_score'), 0)}** · {fmt(match.get('vision_min'))}/min"),
    ])
    pages += make_pages("🎯 Analyse · Objectifs", match, [
        ("Objectifs de l'équipe", f"Dragons : {fmt(match.get('drake'), 0)} · Barons : {fmt(match.get('baron'), 0)}\n"
         f"Tours : {fmt(match.get('tower'), 0)} · Inhibiteurs : {fmt(match.get('inhib'), 0)}"),
        ("Contribution individuelle", f"Dégâts aux tours : **{fmt(match.get('dmg_tower'), 0)}**\n"
         f"Plaques : {fmt(match.get('turret_plates_taken_total'), 0)}"),
        ("Premiers objectifs de l'équipe", f"Dragon : {duration(match.get('early_drake'))} · "
         f"Baron : {duration(match.get('early_baron'))}\n0:00 indique qu'aucun timing n'a été enregistré."),
    ])
    if not fights:
        message = ("Aucun combat enregistré pour ce joueur sur ce match."
                   if fights_available else "L'historique des teamfights n'est pas disponible sur cette installation.")
        pages += make_pages("⚔️ Analyse · Teamfights", match, [("Données disponibles", message)])
    else:
        # Chaque ligne porte le point de vue du joueur suivi, pas celui des autres participants.
        highlights = sorted(fights, key=lambda f: number(f.get("damage_window_estimated")) or 0, reverse=True)[:3]
        pages += make_pages("✨ Analyse · Combats marquants", match, [
            (f"{clock_ms(f.get('start_ms'))} — {clock_ms(f.get('end_ms'))}",
             f"**{fmt(f.get('damage_window_estimated'), 0)}** dégâts estimés\n"
             f"{fmt(f.get('fight_kills'), 0)}/{fmt(f.get('fight_deaths'), 0)}/{fmt(f.get('fight_assists'), 0)} · "
             f"Éliminations alliées/ennemies : {fmt(f.get('allied_kills'), 0)}/{fmt(f.get('enemy_kills'), 0)}")
            for f in highlights
        ], "Les trois combats avec le plus de dégâts estimés. Les fenêtres de mesure peuvent se chevaucher.")
        pages += make_pages("⚔️ Analyse · Chronologie des teamfights", match, [
            (f"{clock_ms(f.get('start_ms'))} — {clock_ms(f.get('end_ms'))}",
             f"**{fmt(f.get('fight_kills'), 0)}/{fmt(f.get('fight_deaths'), 0)}/{fmt(f.get('fight_assists'), 0)}**"
             f" · {fmt(f.get('damage_window_estimated'), 0)} dégâts estimés\n"
             f"Éliminations alliées/ennemies : {fmt(f.get('allied_kills'), 0)}/{fmt(f.get('enemy_kills'), 0)}")
            for f in fights
        ])
    return _finish(pages)


PROGRESS_METRICS = (
    ("⚔️ Progression · Combat", (("dmg_min", "Dégâts/min"), ("kp", "Participation aux kills (%)"), ("kda", "KDA"), ("deaths", "Morts"))),
    ("💰 Progression · Économie", (("cs_min", "Sbires/min"), ("gold_min", "Or/min"))),
    ("👁️ Progression · Vision", (("vision_score", "Score de vision"), ("vision_min", "Vision/min"))),
)


def comparison(current, history, key):
    value = number(current.get(key))
    samples = [number(row.get(key)) for row in history]
    samples = [sample for sample in samples if sample is not None]
    if value is None:
        return "Valeur non enregistrée pour ce match."
    if not samples:
        return f"Ce match : **{fmt(value)}**\nAucune valeur antérieure disponible."
    mean = sum(samples) / len(samples)
    delta = value - mean
    sign = "+" if delta > 0 else ""
    relative = f" ({sign}{fmt(delta / mean * 100)} %)" if mean else ""
    return (f"Ce match : **{fmt(value)}** · Moyenne : {fmt(mean)}\n"
            f"Écart : **{sign}{fmt(delta)}**{relative} · {len(samples)} match(s) renseigné(s)")


def build_progress_pages(match, history):
    # Même compte et même mode ; la requête exclut le match courant et tous les matchs postérieurs.
    note = f"Comparaison aux {len(history)} parties précédentes du même compte et du même mode (maximum 10)."
    if len(history) < 3:
        note += " Échantillon limité."
    results = [outcome(row.get("victoire")) for row in history]
    known = [value for value in results if value != "Résultat inconnu"]
    wins = known.count("Victoire")
    winrate = f"{wins}/{len(known)} · {fmt(wins / len(known) * 100)} %" if known else "Aucun résultat antérieur disponible."
    pages = make_pages("📈 Ma progression", match, [
        ("Référence", note),
        ("Victoires précédentes", winrate),
        ("Lecture des écarts", "Les écarts décrivent ce match face à ta moyenne. "
         "Une hausse n'est pas toujours meilleure, notamment pour les morts. "
         "Les champions et rôles peuvent varier entre ces parties."),
    ])
    for title, metrics in PROGRESS_METRICS:
        pages += make_pages(title, match, [
            (label, comparison(match, history, key)) for key, label in metrics
        ], note)
    history_fields = []
    for row in history:
        stamp = number(row.get("date"))
        try:
            day = datetime.fromtimestamp(stamp, timezone.utc).strftime("%d/%m/%Y") if stamp else "Date inconnue"
        except (ValueError, OverflowError, OSError):
            day = "Date inconnue"
        champ = str(row.get("champion") or "?")[:50]
        history_fields.append((
            f"{day} · {champ} · {outcome(row.get('victoire'))}",
            f"{row['match_id']}\n{fmt(row.get('kills'), 0)}/{fmt(row.get('deaths'), 0)}/{fmt(row.get('assists'), 0)}"
            f" · {fmt(row.get('dmg_min'))} dégâts/min · {fmt(row.get('cs_min'))} sbires/min",
        ))
    if history_fields:
        pages += make_pages("🕘 Progression · Parties de référence", match, history_fields)
    return _finish(pages)


def make_match_buttons(match_id, joueur, records_button=None):
    buttons = [records_button] if records_button is not None else []
    for kind, label, style in (("teamfight", "⚔️ Teamfight", interactions.ButtonStyle.DANGER),
                               ("ganks", "🌿 Ganks", interactions.ButtonStyle.SUCCESS),
                               ("score", "📊 Détail du score", interactions.ButtonStyle.PRIMARY),
                               ("gold", "💰 Différentiel d’or", interactions.ButtonStyle.SECONDARY)):
        buttons.append(interactions.Button(
            style=style, label=label,
            custom_id=f"lolview_open_{kind}_{match_id}_{int(joueur)}",
        ))
    buttons.append(interactions.Button(
        style=interactions.ButtonStyle.SECONDARY, label="👥 Caractéristiques des joueurs",
        custom_id=f"lolview_open_players_{match_id}_{int(joueur)}",
    ))
    return [interactions.ActionRow(*buttons[i:i + 5]) for i in range(0, len(buttons), 5)]


# Les anciennes vues restent accessibles depuis les messages déjà publiés.
# Les nouveaux récaps exposent uniquement Teamfight et Ganks.
TEAMFIGHT_COLOR = 0xE74C3C
GANKS_COLOR = 0x2ECC71
GANK_END_MS = 14 * 60 * 1000
GANK_MODES = {"RANKED", "FLEX", "SWIFTPLAY"}


def truth(value):
    return value is True or str(value).lower() in {"true", "t", "1"}


def load_teamfights(match_id, joueur):
    match = load_match(match_id, joueur)
    if match is None:
        return None
    exists = _rows("SELECT to_regclass('public.match_teamfight_damage') AS table_name", {})
    if not exists or not exists[0]["table_name"]:
        return match, [], False
    # Tous les participants du point de vue sauvegardé sont nécessaires au % équipe.
    rows = _rows(
        """SELECT to_jsonb(f) AS data, f.puuid = t.puuid AS tracked
           FROM match_teamfight_damage f JOIN tracker t ON t.id_compte = :joueur
           WHERE f.match_id = :match_id AND f.analyzed_puuid = t.puuid
           ORDER BY f.start_ms, f.fight_id""",
        {"match_id": match_id, "joueur": int(joueur)},
    )
    return match, [{**_object(row["data"]), "tracked": row["tracked"]} for row in rows], True


def tracked_team(match):
    # id_participant est l'index Riot original, de 0 à 9.
    participant = number(match.get("id_participant"))
    if participant is None or participant != int(participant) or not 0 <= participant <= 9:
        return None
    return 100 if participant < 5 else 200


def load_ganks(match_id, joueur):
    match = load_match(match_id, joueur)
    if match is None:
        return None
    team = tracked_team(match)
    if str(match.get("mode")).upper() not in GANK_MODES or team is None:
        return match, {}, [], False
    tables = _rows(
        """SELECT to_regclass('public.match_gank_summary') AS summary_table,
                  to_regclass('public.match_gank_events') AS events_table""", {},
    )[0]
    summary = {}
    if tables["summary_table"]:
        rows = _rows(
            """SELECT to_jsonb(s) AS data FROM match_gank_summary s
               WHERE s.match_id = :match_id AND s.team_id = :team_id LIMIT 1""",
            {"match_id": match_id, "team_id": team},
        )
        summary = _object(rows[0]["data"]) if rows else {}
    if not tables["events_table"]:
        return match, summary, [], False
    # to_jsonb permet de lire aussi les anciens schémas sans colonnes hybrides.
    rows = _rows(
        """SELECT to_jsonb(e) AS data FROM match_gank_events e
           WHERE e.match_id = :match_id AND e.timestamp_ms >= 0
             AND e.timestamp_ms < :gank_end
           ORDER BY e.timestamp_ms, e.team_id""",
        {"match_id": match_id, "gank_end": GANK_END_MS},
    )
    events = [_object(row["data"]) for row in rows]
    return match, summary, events, bool(summary or events)


def fight_result(fight):
    winner, team = number(fight.get("winner")), number(fight.get("team"))
    if winner not in (100, 200) or team not in (100, 200):
        return "⚪ Égalité / résultat inconnu"
    return "🟢 Gagné" if winner == team else "🔴 Perdu"


def fight_details(fight, participants):
    team = number(fight.get("team"))
    damages = [number(p.get("damage_frame_window")) for p in participants
               if number(p.get("team")) == team and team is not None]
    dealt = number(fight.get("damage_frame_window"))
    total = sum(max(0, damage) for damage in damages if damage is not None)
    share = (f"{fmt(100 * max(0, dealt) / total)} % équipe"
             if dealt is not None and total > 0 and all(d is not None for d in damages) else "part équipe —")
    label = str(fight.get("fight_type") or fight.get("fight_category") or "Combat")[:60]
    proximity = fight.get("fight_type_with_proximity")
    if proximity and proximity != fight.get("fight_type"):
        label += f" · proximité {str(proximity)[:40]}"
    kda = "/".join(fmt(fight.get("fight_" + key), 0) for key in ("kills", "deaths", "assists"))
    return (
        f"{fight_result(fight)} · **{label}** · K/D/A **{kda}**\n"
        f"🎯 **{fmt(dealt, 0)}** infligés · {share}\n"
        f"🛡️ **{fmt(fight.get('damage_taken_frame_window'), 0)}** reçus (toutes sources)"
    )


def build_teamfight_pages(match, rows, available=True):
    note = "🎯 Dégâts champions sur la fenêtre du combat · 🛡️ Reçus toutes sources · — non renseigné."
    def pages(title, fields):
        return make_pages("⚔️ Teamfight · " + title, match, fields, note, TEAMFIGHT_COLOR)
    grouped = {}
    for row in rows:
        grouped.setdefault(row.get("fight_id"), []).append(row)
    fights = [(row, grouped[row.get("fight_id")]) for row in rows if truth(row.get("tracked"))]
    fights.sort(key=lambda item: number(item[0].get("start_ms")) or 0)
    if not fights:
        message = ("Aucun combat enregistré pour ce joueur sur cette partie." if available
                   else "Les données de teamfight ne sont pas disponibles pour cette partie.")
        return _finish(pages("Résumé", [("Combats", message)]))
    teamfights = [(f, ps) for f, ps in fights if truth(f.get("is_teamfight"))]
    wins = sum(fight_result(f).startswith("🟢") for f, _ in teamfights)
    losses = sum(fight_result(f).startswith("🔴") for f, _ in teamfights)
    duels = [f for f, _ in fights if f.get("fight_category") == "duel" and truth(f.get("is_core_participant"))]
    skirmishes = sum(f.get("fight_category") == "skirmish" for f, _ in fights)
    outnumbered = sum(truth(f.get("won_while_outnumbered")) and
                       number(f.get("team")) in (100, 200) and
                       number(f.get("team")) == number(f.get("outnumbered_team")) for f, _ in fights)
    champion = str(match.get("champion") or "?")[:50]
    fields = [("Bilan des combats",
               f"{_champion_icon(champion)} **{champion}**\n"
               f"**{len(teamfights)}** teamfights · **{wins}** gagnés · **{losses}** perdus"
               f" · **{len(teamfights) - wins - losses}** égalités / inconnus\n"
               f"**{skirmishes}** escarmouches · **{len(duels)}** duels"
               f" dont **{sum(fight_result(f).startswith('🟢') for f in duels)}** gagnés\n"
               f"🔥 **{outnumbered}** combats gagnés en infériorité")]
    for key, title in (("damage_frame_window", "🎯 Meilleur teamfight en dégâts infligés"),
                       ("damage_taken_frame_window", "🛡️ Plus de dégâts reçus en teamfight")):
        known = [(f, ps) for f, ps in teamfights if number(f.get(key)) is not None]
        if known:
            fight, participants = max(known, key=lambda pair: number(pair[0][key]))
            fields.append((title, f"**#{fight.get('fight_id')}** · {clock_ms(fight.get('start_ms'))}"
                           f" → {clock_ms(fight.get('end_ms'))}\n{fight_details(fight, participants)}"))
    result = pages("Résumé", fields)
    result += pages("Chronologie des combats", [
        (f"#{fight.get('fight_id')} · {clock_ms(fight.get('start_ms'))} → {clock_ms(fight.get('end_ms'))}",
         fight_details(fight, participants)) for fight, participants in fights
    ])
    return _finish(result)


GANK_OUTCOMES = {
    "success": "✅ Succès", "trade": "🟡 Échange de kills",
    "failed": "⚪ Raté", "jungler_death": "❌ Mort du jungler",
}


def gank_outcome(event):
    # L'ancien booléen successful incluait les trades : ne pas inventer un succès strict.
    return GANK_OUTCOMES.get(event.get("outcome"), "Issue non renseignée")


def build_gank_pages(match, summary, events, available=True):
    note = "Ganks entre **0:00 et 13:59** · Succès strict = kill sans échange retour."
    def pages(title, fields):
        return make_pages("🌿 Ganks · " + title, match, fields, note, GANKS_COLOR)
    if str(match.get("mode")).upper() not in GANK_MODES:
        return _finish(pages("Résumé", [("Mode non pris en charge", "Disponible en Ranked, Flex et Swiftplay.")]))
    team = tracked_team(match)
    if team is None:
        return _finish(pages("Résumé", [("Équipe inconnue", "L'équipe du compte suivi n'est pas enregistrée pour ce match.")]))
    if not available:
        return _finish(pages("Résumé", [("Données indisponibles", "Aucune analyse de ganks exploitable n'est enregistrée pour cette partie.")]))
    # Même filtre à l'affichage pour les appels directs et les données historiques.
    events = [e for e in events if number(e.get("timestamp_ms")) is not None
              and 0 <= number(e["timestamp_ms"]) < GANK_END_MS and number(e.get("team_id")) in (100, 200)]
    events.sort(key=lambda e: (number(e["timestamp_ms"]), number(e["team_id"])))
    sides = [
        ("🔵 Jungle alliée", [e for e in events if number(e.get("team_id")) == team], "ally"),
        ("🔴 Jungle ennemie", [e for e in events if number(e.get("team_id")) != team], "enemy"),
    ]
    fields, lanes = [], []
    for label, rows, side in sides:
        champion = str(summary.get(side + "_jungler_champion") or
                       (rows[0].get("jungler_champion") if rows else "") or "Jungler")[:50]
        success = sum(e.get("outcome") == "success" for e in rows)
        trades = sum(e.get("outcome") == "trade" for e in rows)
        failed = sum(e.get("outcome") in ("failed", "jungler_death") for e in rows)
        unknown = len(rows) - success - trades - failed
        first = f"{clock_ms(rows[0]['timestamp_ms'])} {str(rows[0].get('lane') or '?').upper()}" if rows else "—"
        rate = f"{fmt(100 * success / len(rows), 0)} %" if rows and not unknown else "—"
        fields.append((f"{label} · {_champion_icon(champion)} {champion}",
                       f"**{len(rows)}** tentatives · **{success}** succès stricts ({rate})\n"
                       f"**{trades}** échanges · **{failed}** ratées / mort du jungler"
                       + (f" · **{unknown}** issues inconnues" if unknown else "")
                       + f"\nPremier gank : **{first}**"))
        lanes.append(label + " : " + " · ".join(
            f"**{lane.upper()} {sum(str(e.get('lane')).lower() == lane for e in rows)}**"
            for lane in ("top", "mid", "bot")))
    fields.append(("🗺️ Répartition des appuis", "\n".join(lanes)))
    ally = sides[0][1]
    exact = sum(e.get("detection_source") == "exact_event" for e in ally)
    inferred = sum(e.get("detection_source") in ("sampled_combat", "inferred_combat") for e in ally)
    high = sum((number(e.get("confidence")) or 0) >= 0.8 for e in ally)
    counters = sum(truth(e.get("is_counter_gank")) for e in ally)
    fields.append(("🔬 Lecture de l'activité",
                   f"Différentiel **{len(ally) - len(sides[1][1]):+d}** · Counter-ganks alliés **{counters}**\n"
                   f"Jungle alliée : **{exact}** exactes · **{inferred}** inférées · **{high}** haute confiance\n"
                   "La conversion est observée : les passages sans kill ni signal de dégâts sont moins bien détectés."))
    result = pages("Résumé", fields)
    details = []
    for event in events:
        side = "🔵" if number(event.get("team_id")) == team else "🔴"
        champion = str(event.get("jungler_champion") or "?")[:50]
        source = {"exact_event": "Exact", "sampled_combat": "Frame",
                  "inferred_combat": "Inféré"}.get(event.get("detection_source"), "Source inconnue")
        confidence = number(event.get("confidence"))
        confidence_text = f"{fmt(confidence * 100, 0)} %" if confidence is not None else "—"
        kda = "/".join(fmt(event.get("jungler_" + key), 0) for key in ("kills", "deaths", "assists"))
        counter = " · 🔁 Counter-gank" if truth(event.get("is_counter_gank")) else ""
        details.append((f"{side} {clock_ms(event['timestamp_ms'])} · {str(event.get('lane') or '?').upper()[:30]}",
                        f"{_champion_icon(champion)} **{champion}** · {gank_outcome(event)}{counter}\n"
                        f"K/D/A jungler **{kda}** · {source} · Confiance **{confidence_text}**"))
    if details:
        result += pages("Chronologie", details)
    return _finish(result)
