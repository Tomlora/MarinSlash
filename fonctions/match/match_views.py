"""Pages d'analyse et de progression construites depuis les données déjà sauvegardées."""
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


def make_pages(title, match, fields, note=""):
    pages = []
    fields = fields or [("Aucune donnée", "Les données de cette section ne sont pas disponibles.")]
    for start in range(0, len(fields), 5):
        page = interactions.Embed(
            title=title, description=subject(match) + ("\n" + note if note else ""), color=0x5865F2,
        )
        for name, value in fields[start:start + 5]:
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
    for kind, label in (("analysis", "📊 Analyse du match"), ("progress", "📈 Ma progression")):
        buttons.append(interactions.Button(
            style=interactions.ButtonStyle.SECONDARY, label=label,
            custom_id=f"lolview_open_{kind}_{match_id}_{int(joueur)}",
        ))
    return [interactions.ActionRow(*buttons)]
