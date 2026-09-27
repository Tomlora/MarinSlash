"""Affichage compact, pagination et conservation des records d'une partie.

Le récap sélectionne trois statistiques puis présente leurs distinctions
par catégorie : All-Time, Saison et Personnel, comme l'ancien affichage.
Le snapshot évite de recalculer le classement lors d'un clic ultérieur.
"""
import json
import logging
from collections import defaultdict
from dataclasses import asdict

import interactions

from fonctions.gestion_bdd import lire_bdd_perso, requete_perso_bdd
from fonctions.match.records_display import (
    MEDAL_EMOJIS,
    RECORD_LABELS,
    SCOPE_CONFIG,
    RecordEntry,
    RecordsCollector,
    _format_value,
)
from utils.emoji import emote_champ_discord, emote_v2

log = logging.getLogger(__name__)

SCOPES = ("alltime", "general", "perso")
SCOPE_NAMES = {
    "alltime": "🏛️ All-Time",
    "general": "🏆 Saison",
    "perso": "👤 Personnel",
}
SCOPE_SHORT = {
    "alltime": "🏛️ Historique",
    "general": "🏆 Saison",
    "perso": "👤 Personnel",
}
PAGE_SIZE = 5
SCHEMA_READY = False

# Les records historiques absolus passent avant les records locaux.
# Une égalisation ne doit pas évincer un nouveau record.
SCOPE_PRIORITY = {"alltime": 0, "general": 1, "perso": 2}

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS match_records (
    match_id VARCHAR(40) NOT NULL,
    joueur BIGINT NOT NULL,
    data JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (match_id, joueur)
)
"""


def ensure_records_table():
    """Création automatique si le compte SQL a les droits nécessaires."""
    global SCHEMA_READY
    if not SCHEMA_READY:
        requete_perso_bdd(CREATE_TABLE_SQL)
        SCHEMA_READY = True


def save_record_snapshot(match_id, joueur, collector):
    """Enregistre aussi les parties sans record; retourne False en cas d'échec.

    Une erreur de migration ne doit jamais empêcher la publication du récap.
    """
    try:
        ensure_records_table()
        snapshot = {
            "version": 1,
            "entries": [
                asdict(entry)
                for scope in SCOPES
                for entry in collector.records.get(scope, [])
            ],
        }
        requete_perso_bdd(
            """
            INSERT INTO match_records (match_id, joueur, data)
            VALUES (:match_id, :joueur, CAST(:data AS JSONB))
            ON CONFLICT (match_id, joueur)
            DO UPDATE SET data = EXCLUDED.data, created_at = NOW()
            """,
            {
                "match_id": str(match_id),
                "joueur": int(joueur),
                "data": json.dumps(snapshot, ensure_ascii=False),
            },
        )
        return True
    except Exception:
        log.exception("Impossible d'enregistrer les records de %s / %s", match_id, joueur)
        return False


def load_record_snapshot(match_id, joueur):
    """Retourne None si aucune analyse enregistrée, y compris les anciennes parties."""
    ensure_records_table()
    rows = lire_bdd_perso(
        """
        SELECT data FROM match_records
        WHERE match_id = :match_id AND joueur = :joueur
        """,
        index_col=None,
        params={"match_id": str(match_id), "joueur": int(joueur)},
    ).T
    if rows.empty:
        return None
    data = rows.iloc[0]["data"]
    if isinstance(data, str):
        data = json.loads(data)
    collector = RecordsCollector()
    for raw in data.get("entries", []):
        if raw.get("scope") in SCOPES:
            collector.add(RecordEntry(**raw))
    return collector


def get_match_record_accounts(match_id):
    """Comptes dont le récap des records a été sauvegardé pour ce match."""
    ensure_records_table()
    return lire_bdd_perso(
        """
        SELECT mr.joueur, tracker.riot_id, tracker.riot_tagline
        FROM match_records mr
        LEFT JOIN tracker ON tracker.id_compte = mr.joueur
        WHERE mr.match_id = :match_id
        ORDER BY tracker.riot_id, mr.joueur
        """,
        index_col=None,
        params={"match_id": str(match_id)},
    ).T


def display_label(category):
    return RECORD_LABELS.get(category, category.replace("_", " ")).lower()


def _family(category):
    """Diversifier l'aperçu sans éliminer un record du détail."""
    if category.startswith("tf_"):
        return "teamfight"
    if category.startswith("vision") or "ward" in category:
        return "vision"
    if category.startswith(("dmg", "damage", "crit", "ecart_dmg")):
        return "dégâts"
    if category.startswith(("gold", "cs", "jgl_dix", "biggest_")):
        return "économie"
    if category.startswith(("early_", "first_", "drake", "baron", "herald", "tower", "objective")):
        return "objectifs"
    if category.startswith(("kill", "death", "assist", "kda", "penta", "quadra")):
        return "combat"
    return category


def _priority(entry):
    historical_first = entry.scope == "alltime" and entry.place == 1 and not entry.is_tie
    first = entry.place == 1 and not entry.is_tie
    return (
        0 if historical_first else 1 if first else 2 if not entry.is_tie else 3,
        SCOPE_PRIORITY.get(entry.scope, 9),
        entry.place,
        entry.category,
    )


def grouped_records(collector):
    """Une ligne par statistique, avec toutes ses distinctions conservées."""
    groups = defaultdict(list)
    for scope in SCOPES:
        for entry in collector.records.get(scope, []):
            groups[entry.category].append(entry)
    return dict(groups)


def featured_records(collector, max_items=3):
    """Sélectionner les lignes les plus parlantes, puis varier les familles."""
    groups = grouped_records(collector)
    ordered = sorted(groups.items(), key=lambda pair: _priority(min(pair[1], key=_priority)))
    selected = []
    families = set()

    # Les records historiques absolus sont examinés d'abord; le détail reste exhaustif.
    for category, entries in ordered:
        if len(selected) >= max_items:
            break
        best = min(entries, key=_priority)
        if best.scope == "alltime" and best.place == 1 and not best.is_tie:
            selected.append((category, entries))
            families.add(_family(category))

    for diversify in (True, False):
        for category, entries in ordered:
            if len(selected) >= max_items:
                break
            if any(category == chosen for chosen, _ in selected):
                continue
            family = _family(category)
            if diversify and family in families:
                continue
            selected.append((category, entries))
            families.add(family)
    return selected


def _safe_line(text, limit=180):
    value = str(text or "—").replace("\n", " ").replace("\r", " ")
    return value[:limit - 1] + "…" if len(value) > limit else value


def _champion_icon(champion):
    """Emoji du champion issu de data_champion, comme l'ancien récap."""
    if not champion:
        return ""
    name = str(champion).strip()
    # Les noms Riot peuvent comporter des majuscules internes (Kai'Sa, Lee Sin).
    for key in (name, name.capitalize(), name.title()):
        icon = emote_champ_discord.get(key)
        if icon:
            return str(icon)
    # Tolérer aussi les identifiants Riot sans espaces ni apostrophes.
    normalized = "".join(char for char in name.casefold() if char.isalnum())
    for key, icon in emote_champ_discord.items():
        if normalized == "".join(char for char in str(key).casefold() if char.isalnum()):
            return str(icon) if icon else ""
    return ""


def _former_holder(entry):
    """Conserver mention du joueur et icône du champion, sans texte entre parenthèses."""
    holder = _safe_line(entry.old_holder or "Détenteur inconnu", 48)
    icon = _champion_icon(entry.old_champion)
    return f"{holder} {icon}".rstrip()


def _featured_line(category, entries):
    """Présentation compacte de l'ancien embed avec scopes réunis proprement."""
    best = min(entries, key=_priority)
    medal = MEDAL_EMOJIS.get(best.place, f"#{best.place}")
    stat_icon = emote_v2.get(category, "")
    value = _format_value(best.value, best.category)
    prefix = "🤝 " if best.is_tie else ""
    headline = f"{prefix}{medal} {stat_icon}**{display_label(category)}** → `{value}`"
    lines = [headline]
    # Chaque scope peut avoir un détenteur et une valeur précédente différents.
    # Fusionner uniquement les scopes qui partagent le même ancien record.
    grouped = {}
    for entry in sorted(entries, key=lambda e: SCOPE_PRIORITY.get(e.scope, 99)):
        key = (entry.place, entry.old_record, entry.old_holder, entry.old_champion, entry.is_tie)
        grouped.setdefault(key, []).append(entry)
    for records in grouped.values():
        entry = records[0]
        scope_names = " · ".join(SCOPE_SHORT[e.scope] for e in records)
        previous = _format_value(entry.old_record, entry.category)
        result = f"Égalise {_former_holder(entry)}" if entry.is_tie else f"~~{previous}~~ {_former_holder(entry)}"
        if len(grouped) == 1:
            # Ancien style : score, précédent barré, détenteur et logo.
            lines = [f"{headline} ・ {result}", f"↳ {scope_names}"]
        else:
            scope_medal = MEDAL_EMOJIS.get(entry.place, f"#{entry.place}")
            lines.append(f"↳ {scope_names} · {scope_medal} {result}")
    return "\n".join(lines)


def _recap_sections(selected):
    """Une section par scope, avec les lignes complètes de l'ancien récap."""
    sections = []
    for scope in SCOPES:
        entries = sorted(
            (entry for _, records in selected for entry in records if entry.scope == scope),
            key=lambda entry: (entry.place, entry.is_tie, entry.category),
        )
        if not entries:
            continue
        lines = [SCOPE_CONFIG[scope]["header"]]
        for entry in entries:
            medal = MEDAL_EMOJIS.get(entry.place, f"#{entry.place}")
            icon = emote_v2.get(entry.category, "")
            label = display_label(entry.category)
            value = _format_value(entry.value, entry.category)
            previous = _format_value(entry.old_record, entry.category)
            comparison = (
                f"Égalise {_former_holder(entry)}" if entry.is_tie
                else f"~~{previous}~~ {_former_holder(entry)}"
            )
            lines.append(f"{medal} {icon}**{label}** → `{value}` ・ {comparison}")
        sections.append("\n".join(lines))
    return sections


def add_featured_records(embed, collector, max_items=3):
    """Ancien affichage par scope, limité à trois statistiques marquantes."""
    if collector.is_empty():
        embed.add_field(
            name="Exploits",
            value="Aucun record pour cette partie.",
            inline=False,
        )
        return embed

    groups = grouped_records(collector)
    chosen = featured_records(collector, max_items=max_items)
    count = collector.count()
    footer = (
        f"{count} distinction{'s' if count > 1 else ''} · "
        f"{len(groups)} statistique{'s' if len(groups) > 1 else ''}"
    )

    def render(selected):
        sections = _recap_sections(selected)
        hidden = len(groups) - len(selected)
        if hidden:
            sections.append(f"**+{hidden} autre(s) statistique(s)** dans le détail.")
        sections.append(footer)
        return "\n\n".join(sections)

    # Conserver tous les scopes d'une statistique ou la laisser dans le détail.
    # Compter les titres, espaces et compteur dans le budget du champ Discord.
    selected = []
    for item in chosen:
        candidate = selected + [item]
        if len(render(candidate)) > 960:
            break
        selected = candidate
    embed.add_field(
        name="Exploits",
        value=render(selected),
        inline=False,
    )
    return embed


def _detail_field(entry):
    """Même style que l'ancien récap : emoji stat, score en code, ancien barré,
    ancien détenteur et emoji de champion natif du serveur.
    """
    medal = MEDAL_EMOJIS.get(entry.place, f"#{entry.place}")
    stat_icon = emote_v2.get(entry.category, "")
    category = display_label(entry.category)
    value = _format_value(entry.value, entry.category)
    previous = _format_value(entry.old_record, entry.category)
    status = "🤝 Égalisation" if entry.is_tie else ("Nouveau record" if entry.place == 1 else f"Top {entry.place}")
    old = f"Égalise {_former_holder(entry)}" if entry.is_tie else f"~~{previous}~~ {_former_holder(entry)}"
    return (
        _safe_line(f"{medal} {stat_icon}{category}", 256),
        f"→ `{value}` ・ {old}\n{status}",
    )


def build_record_pages(collector, match_id, player_name=None, demo=False):
    """Embeds Discord classiques : 5 lignes/page et jamais plus de 6 000 caractères."""
    prefix = "🧪 DÉMO · " if demo else ""
    suffix = f" · {_safe_line(player_name, 55)}" if player_name else ""
    subject = f"{prefix}Match {_safe_line(match_id, 55)}{suffix}"
    groups = grouped_records(collector)
    page_defs = []
    scope_counts = {
        scope: len(collector.records.get(scope, []))
        for scope in SCOPES
    }
    summary = interactions.Embed(
        title="🏅 Tous les records — Aperçu",
        description=(
            f"{subject}\n\n"
            f"**{collector.count()} distinction(s)** sur **{len(groups)} statistique(s)**.\n"
            f"🏛️ Historique : {scope_counts['alltime']}  ·  "
            f"🏆 Saison : {scope_counts['general']}  ·  "
            f"👤 Personnel : {scope_counts['perso']}"
        ),
        color=0x5865F2,
    )
    if collector.is_empty():
        summary.add_field(
            name="Aucun record",
            value="Aucune distinction n'a été obtenue dans ce scénario."
            if demo else "Aucune distinction enregistrée pour cette partie.",
            inline=False,
        )
    else:
        for category, entries in featured_records(collector, max_items=3):
            summary.add_field(
                name=_safe_line(display_label(category).title(), 256),
                value=_featured_line(category, entries)[:1024],
                inline=False,
            )
    page_defs.append(("aperçu", summary))

    for scope in SCOPES:
        entries = sorted(
            collector.records.get(scope, []),
            key=lambda entry: (entry.place, entry.is_tie, entry.category),
        )
        for start in range(0, len(entries), PAGE_SIZE):
            page = entries[start:start + PAGE_SIZE]
            embed = interactions.Embed(
                title=f"{prefix}{SCOPE_NAMES[scope]}",
                description=(
                    f"{subject}\n"
                    f"Distinctions {start + 1} à {start + len(page)} sur {len(entries)}."
                ),
                color=0x5865F2,
            )
            for entry in page:
                name, value = _detail_field(entry)
                embed.add_field(name=name, value=value[:1024], inline=False)
            page_defs.append((scope, embed))

    total = len(page_defs)
    for index, (scope, embed) in enumerate(page_defs):
        embed.set_footer(text=f"Page {index + 1}/{total} · {subject}")
    return page_defs


def make_open_button(match_id, joueur):
    """ID auto-suffisant pour retrouver le snapshot après redémarrage."""
    return interactions.Button(
        style=interactions.ButtonStyle.PRIMARY,
        label="🏆 Voir tous les records",
        custom_id=f"lolrec_open_{match_id}_{int(joueur)}",
    )
