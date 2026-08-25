"""
Module d'affichage des records - Regroupement par scope.

Ce module remplace les anciennes fonctions:
- summarize_medals()
- add_chunked_field() 
- records_check3() (ancienne version)

Usage:
    from fonctions.match.records_display import (
        RecordsCollector,
        records_check3,
        add_records_to_embed
    )
"""

import pandas as pd
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

from utils.emoji import emote_champ_discord, emote_v2, dict_place


# ============================================================================
# CONFIGURATION
# ============================================================================

MEDAL_EMOJIS: Dict[int, str] = dict_place

SCOPE_CONFIG: Dict[str, Dict[str, Any]] = {
    'alltime': {
        'icon': '🏛️',
        'label': 'All-Time',
        'header': '🏛️ **Records All-Time**',
        'order': 1,
    },
    'general': {
        'icon': '<:boss:1333120152983834726>',
        'label': 'Saison',
        'header': '<:boss:1333120152983834726> **Records Saison**',
        'order': 2,
    },
    'perso': {
        'icon': ':busts_in_silhouette:', 
        'label': 'Personnel',
        'header': ':busts_in_silhouette: **Records Perso**',
        'order': 3,
    },
}

RECORD_LABELS: Dict[str, str] = {
    'tf_takedowns_survived': 'KILLS + ASSISTS EN TF SANS MOURIR',
    'tf_teamfight_outnumbered_wins': 'TF GAGNÉS EN INFÉRIORITÉ',
    'tf_teamfights': 'COMBATS 3V3+ DISPUTÉS',
    'tf_clutches_won': 'COMBATS EN INFÉRIORITÉ GAGNÉS',
    'tf_damage_window': 'DMG MAX EN TEAMFIGHT',
    'tf_physical_damage_window': 'DMG AD MAX EN TEAMFIGHT',
    'tf_magic_damage_window': 'DMG AP MAX EN TEAMFIGHT',
    'tf_true_damage_window': 'DMG TRUE MAX EN TEAMFIGHT',
    'tf_damage_taken_window': 'DMG REÇUS MAX EN TEAMFIGHT',
    'tf_physical_damage_taken_window': 'DMG PHYSIQUES REÇUS MAX EN TEAMFIGHT',
    'tf_magic_damage_taken_window': 'DMG MAGIQUES REÇUS MAX EN TEAMFIGHT',
    'tf_true_damage_taken_window': 'DMG TRUE REÇUS MAX EN TEAMFIGHT',
    'tf_physical_dead_damage': 'DMG AD SUR CIBLES MORTES',
    'tf_magic_dead_damage': 'DMG AP SUR CIBLES MORTES',
    'tf_true_dead_damage': 'DMG TRUE SUR CIBLES MORTES',
    'tf_dead_damage_share_pct': '% DMG SUR CIBLES MORTES (5 ALLIÉS IMPLIQUÉS)',
    'tf_damage_window_share_pct': '% DMG ÉQUIPE EN TF (5 ALLIÉS IMPLIQUÉS)',
    'tf_duels': '1V1 DISPUTÉS',
    'tf_duels_won': '1V1 GAGNÉS',
    'tf_skirmishes': 'COMBATS 2V2 À 2V5 DISPUTÉS',
    'allie_feeder': "MORTS MAX D'UN COÉQUIPIER",
}

PERCENT_RECORDS = {
    'tf_dead_damage_share_pct',
    'tf_damage_window_share_pct',
}

# Catégories où l'égalisation n'est pas pertinente (objectifs binaires)
CATEGORY_EXCLUSION_EGALITE: List[str] = [
    'baron', 'herald', 'drake', 'first_double', 'first_triple', 'first_quadra',
    'first_penta', 'first_horde', 'first_niveau_max', 'first_blood',
    'tower', 'inhib', 'first_tower_time', 'LEVEL_UP_10'
]


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class RecordEntry:
    """Représente un record individuel."""
    scope: str          # 'general', 'perso', 'alltime'
    place: int          # Position dans le top
    category: str       # Nom de la stat
    value: float        # Valeur obtenue
    old_record: float   # Ancien record
    old_holder: str     # Détenteur précédent
    old_champion: str   # Champion utilisé par l'ancien détenteur
    is_tie: bool = False  # True si égalisation


@dataclass 
class RecordsCollector:
    """
    Collecteur de records groupés par scope.
    
    Accumule les records au fur et à mesure des vérifications
    puis les formate pour l'affichage.
    """
    records: Dict[str, List[RecordEntry]] = field(
        default_factory=lambda: defaultdict(list)
    )
    
    def add(self, entry: RecordEntry) -> None:
        """Ajoute un record au collecteur."""
        self.records[entry.scope].append(entry)
    
    def is_empty(self) -> bool:
        """Vérifie si le collecteur est vide."""
        return all(len(v) == 0 for v in self.records.values())
    
    def count(self) -> int:
        """Retourne le nombre total de records."""
        return sum(len(v) for v in self.records.values())
    
    def format_for_embed(self, max_per_scope: int = 10) -> List[str]:
        """
        Formate les records pour l'affichage Discord.
        
        Returns
        -------
        List[str]
            Liste de strings, une par scope (avec header).
        """
        parts = []
        
        sorted_scopes = sorted(
            self.records.keys(),
            key=lambda s: SCOPE_CONFIG.get(s, {}).get('order', 99)
        )
        
        for scope in sorted_scopes:
            entries = self.records[scope]
            if not entries:
                continue
            
            config = SCOPE_CONFIG.get(scope, {'header': f'**{scope.title()}**'})
            entries_sorted = sorted(
                entries, 
                key=lambda e: (e.place, e.category)
            )[:max_per_scope]
            
            lines = [config['header']]
            for entry in entries_sorted:
                lines.append(_format_record_line(entry))
            parts.append('\n'.join(lines))
        
        return parts
    
    def get_summary(self) -> str:
        summary_parts = []
        sorted_scopes = sorted(
            self.records.keys(),
            key=lambda s: SCOPE_CONFIG.get(s, {}).get('order', 99)
        )
        
        for scope in sorted_scopes:
            entries = self.records[scope]
            if not entries:
                continue
                
            config = SCOPE_CONFIG.get(scope, {'header': f'**{scope.title()}**'})
            by_medal: Dict[tuple, List[RecordEntry]] = defaultdict(list)
            for entry in entries:
                key = (entry.place, entry.is_tie)
                by_medal[key].append(entry)
            
            sorted_keys = sorted(by_medal.keys(), key=lambda k: (k[0], k[1]))
            lines = [config['header']]
            
            for (place, is_tie) in sorted_keys:
                medal = MEDAL_EMOJIS.get(place, f"#{place}")
                group_entries = by_medal[(place, is_tie)]
                count = len(group_entries)
                stats = sorted(RECORD_LABELS.get(e.category, e.category) for e in group_entries)
                max_display = 4
                if count <= max_display:
                    stats_display = ", ".join(stats)
                else:
                    stats_display = ", ".join(stats[:max_display]) + f"... (+{count - max_display})"
                tie_prefix = "🤝 " if is_tie else ""
                lines.append(f"{tie_prefix}{medal} x{count} : {stats_display}")
            
            summary_parts.append('\n'.join(lines))
        
        return '\n\n'.join(summary_parts)


def _format_value(value, category: str = None) -> str:
    if value is None:
        return "?"
    try:
        float_val = float(value)
        if float_val % 1 == 0:
            value_str = str(int(float_val))
        else:
            value_str = f"{float_val:.2f}" if category in PERCENT_RECORDS else f"{float_val:.1f}"
        return f"{value_str}%" if category in PERCENT_RECORDS else value_str
    except (ValueError, TypeError):
        return str(value)


def _fit_field(value: str, max_len: int = 950) -> str:
    if len(value) <= max_len:
        return value
    suffix = "\n..."
    return value[:max_len - len(suffix)].rstrip() + suffix


def _format_record_line(entry: RecordEntry) -> str:
    medal = MEDAL_EMOJIS.get(entry.place, f"`#{entry.place}`")
    cat_emoji = emote_v2.get(entry.category, '')
    category_label = RECORD_LABELS.get(entry.category, entry.category)
    champ_emoji = ''
    if entry.old_champion:
        champ_emoji = emote_champ_discord.get(
            entry.old_champion.capitalize(), ''
        )
    
    value_str = _format_value(entry.value, entry.category)
    base = f"{medal} {cat_emoji}**{category_label}** → `{value_str}`"
    
    if entry.is_tie:
        if entry.category not in CATEGORY_EXCLUSION_EGALITE:
            return f"{base} ・ Égalise {entry.old_holder} {champ_emoji}"
        return base
    else:
        old_str = _format_value(entry.old_record, entry.category)
        return f"{base} ・ ~~{old_str}~~ {entry.old_holder} {champ_emoji}"


def records_check3(fichier: pd.DataFrame,
                   fichier_joueur: pd.DataFrame = None,
                   fichier_all: pd.DataFrame = None,
                   category: str = None,
                   result_category_match = None,
                   methode: str = 'max',
                   collector: RecordsCollector = None) -> RecordsCollector:
    from fonctions.match.records import top_records
    
    if collector is None:
        collector = RecordsCollector()
    
    if result_category_match is None or result_category_match == 0:
        return collector

    def check_scope(scope_key: str, df: pd.DataFrame, 
                    identifiant: str, top_n: int) -> None:
        if df is None or df.shape[0] == 0:
            return
        if scope_key == 'alltime':
            if 'season' not in df.columns or len(df['season'].unique()) <= 1:
                return
        try:
            top_list = top_records(
                df, category, methode, 
                identifiant=identifiant, 
                top_n=top_n
            )
        except Exception:
            return
        if not top_list:
            return
            
        record_counts = Counter(str(record) for _, _, record, _ in top_list)
        
        for idx, (joueur, champion, record, url) in enumerate(top_list):
            if record_counts[str(record)] >= 7:
                continue
            place = idx + 1
            try:
                result_float = float(result_category_match)
                record_float = float(record)
            except (ValueError, TypeError):
                continue
            if result_float == record_float:
                collector.add(RecordEntry(
                    scope=scope_key,
                    place=place,
                    category=category,
                    value=result_float,
                    old_record=record_float,
                    old_holder=str(joueur),
                    old_champion=str(champion) if champion else '',
                    is_tie=True
                ))
                break
            is_new_record = (
                (methode == 'max' and result_float > record_float) or
                (methode == 'min' and result_float < record_float)
            )
            if is_new_record:
                collector.add(RecordEntry(
                    scope=scope_key,
                    place=place,
                    category=category,
                    value=result_float,
                    old_record=record_float,
                    old_holder=str(joueur),
                    old_champion=str(champion) if champion else '',
                    is_tie=False
                ))
                break

    check_scope('general', fichier, 'discord', top_n=10)
    check_scope('perso', fichier_joueur, 'riot_id', top_n=3)
    check_scope('alltime', fichier_all, 'discord', top_n=10)
    return collector


def add_records_to_embed(embed, 
                         collector: RecordsCollector, 
                         title: str = "Exploits",
                         max_field_len: int = 950, 
                         total_limit: int = 3500,
                         max_fields: int = 5) -> Any:
    if collector.is_empty():
        embed.add_field(name=title, value="Aucun exploit", inline=False)
        return embed
    
    parts = collector.format_for_embed()
    total_content = '\n\n'.join(parts)
    
    if len(total_content) > total_limit:
        summary = collector.get_summary()
        if len(summary) <= max_field_len:
            embed.add_field(
                name=f"{title} (résumé)", 
                value=summary, 
                inline=False
            )
        else:
            _add_chunked_content(
                embed, 
                summary, 
                base_title=f"{title} (résumé)",
                max_len=max_field_len,
                max_fields=max_fields
            )
    else:
        all_lines = []
        for part in parts:
            all_lines.extend(part.strip().split('\n'))
            all_lines.append('')
        
        current = ""
        field_index = 1
        
        for line in all_lines:
            test_content = current + line + '\n' if current else line + '\n'
            if len(test_content) > max_field_len:
                if current.strip():
                    embed.add_field(
                        name=title if field_index == 1 else f"{title} ({field_index})",
                        value=_fit_field(current.strip(), max_field_len),
                        inline=False
                    )
                    field_index += 1
                    if field_index > max_fields:
                        remaining_lines = all_lines[all_lines.index(line):]
                        if remaining_lines:
                            embed.add_field(
                                name=f"{title} (suite)",
                                value=_fit_field(collector.get_summary(), max_field_len),
                                inline=False
                            )
                        return embed
                current = line + '\n'
            else:
                current = test_content
        
        if current.strip():
            embed.add_field(
                name=title if field_index == 1 else f"{title} ({field_index})",
                value=_fit_field(current.strip(), max_field_len),
                inline=False
            )
    
    return embed


def _add_chunked_content(embed, content: str, base_title: str, 
                         max_len: int = 950, max_fields: int = 5) -> None:
    lines = content.split('\n')
    current = ""
    index = 1
    
    for line in lines:
        if len(current) + len(line) + 1 > max_len:
            if index > max_fields:
                embed.add_field(
                    name=f"{base_title} {index}",
                    value=_fit_field(current.strip() + "\n...", max_len),
                    inline=False
                )
                return
            embed.add_field(
                name=base_title if index == 1 else f"{base_title} {index}",
                value=_fit_field(current.strip(), max_len),
                inline=False
            )
            current = ""
            index += 1
        current += line + "\n"
    
    if current.strip() and index <= max_fields:
        embed.add_field(
            name=base_title if index == 1 else f"{base_title} {index}",
            value=_fit_field(current.strip(), max_len),
            inline=False
        )
