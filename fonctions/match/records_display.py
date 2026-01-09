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
        
        # Trier les scopes selon l'ordre défini
        sorted_scopes = sorted(
            self.records.keys(),
            key=lambda s: SCOPE_CONFIG.get(s, {}).get('order', 99)
        )
        
        for scope in sorted_scopes:
            entries = self.records[scope]
            if not entries:
                continue
            
            config = SCOPE_CONFIG.get(scope, {'header': f'**{scope.title()}**'})
            
            # Trier par place, puis par catégorie
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
        """
        Retourne un résumé compact des records, groupé par scope puis par médaille.
        
        Format:
            🏛️ **Records All-Time**
            🥇 x3 : kda, kills, dmg
            🥈 x2 : cs_min, gold
            
            👤 **Records Serveur**
            🥇 x5 : assists, deaths... (+2)
        """
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
            
            # Grouper par (place, is_tie)
            by_medal: Dict[tuple, List[RecordEntry]] = defaultdict(list)
            for entry in entries:
                key = (entry.place, entry.is_tie)
                by_medal[key].append(entry)
            
            # Trier : d'abord par place (1, 2, 3...), puis nouveaux records avant égalisations
            sorted_keys = sorted(by_medal.keys(), key=lambda k: (k[0], k[1]))
            
            lines = [config['header']]
            
            for (place, is_tie) in sorted_keys:
                medal = MEDAL_EMOJIS.get(place, f"#{place}")
                group_entries = by_medal[(place, is_tie)]
                count = len(group_entries)
                
                # Lister les noms de stats
                stats = sorted(e.category for e in group_entries)
                
                # Limiter l'affichage si trop nombreuses
                max_display = 4
                if count <= max_display:
                    stats_display = ", ".join(stats)
                else:
                    stats_display = ", ".join(stats[:max_display]) + f"... (+{count - max_display})"
                
                # Préfixe pour les égalisations
                tie_prefix = "🤝 " if is_tie else ""
                
                lines.append(f"{tie_prefix}{medal} x{count} : {stats_display}")
            
            summary_parts.append('\n'.join(lines))
        
        return '\n\n'.join(summary_parts)




# ============================================================================
# FONCTIONS DE FORMATAGE
# ============================================================================

def _format_value(value) -> str:
    """Formate une valeur numérique proprement."""
    if value is None:
        return "?"
    try:
        float_val = float(value)
        if float_val % 1 == 0:
            return str(int(float_val))
        return f"{float_val:.1f}"
    except (ValueError, TypeError):
        return str(value)


def _format_record_line(entry: RecordEntry) -> str:
    """
    Formate une ligne de record.
    
    Formats possibles:
    - Nouveau record : 🥇 ⚔️**kda** → `15.5` ・ ~~12.0~~ 🏆
    - Égalisation    : 🥇 ⚔️**kda** → `15.5` ・ Égalise @User 🏆
    """
    medal = MEDAL_EMOJIS.get(entry.place, f"`#{entry.place}`")
    cat_emoji = emote_v2.get(entry.category, '')
    
    # Emoji du champion (si disponible)
    champ_emoji = ''
    if entry.old_champion:
        champ_emoji = emote_champ_discord.get(
            entry.old_champion.capitalize(), ''
        )
    
    value_str = _format_value(entry.value)
    
    # Construction de la ligne de base
    base = f"{medal} {cat_emoji}**{entry.category}** → `{value_str}`"
    
    if entry.is_tie:
        # Égalisation
        if entry.category not in CATEGORY_EXCLUSION_EGALITE:
            return f"{base} ・ Égalise {entry.old_holder} {champ_emoji}"
        return base
    else:
        # Nouveau record - afficher l'ancien barré
        old_str = _format_value(entry.old_record)
        return f"{base} ・ ~~{old_str}~~ {entry.old_holder} {champ_emoji}"


# ============================================================================
# FONCTION PRINCIPALE DE VÉRIFICATION
# ============================================================================

def records_check3(fichier: pd.DataFrame,
                   fichier_joueur: pd.DataFrame = None,
                   fichier_all: pd.DataFrame = None,
                   category: str = None,
                   result_category_match = None,
                   methode: str = 'max',
                   collector: RecordsCollector = None) -> RecordsCollector:
    '''
    Vérifie si le score est dans le top (général, perso, all-time).
    
    Parameters
    ----------
    fichier : pd.DataFrame
        Données de la saison courante (records serveur)
    fichier_joueur : pd.DataFrame, optional
        Données du joueur uniquement (records perso)
    fichier_all : pd.DataFrame, optional
        Données toutes saisons (records all-time)
    category : str
        Nom de la statistique
    result_category_match : float/int
        Valeur obtenue dans la partie
    methode : str
        'max' ou 'min' selon si on cherche le plus haut ou plus bas
    collector : RecordsCollector, optional
        Collecteur existant à enrichir (créé si None)
        
    Returns
    -------
    RecordsCollector
        Le collecteur enrichi avec les nouveaux records
    '''
    from fonctions.match.records import top_records
    
    if collector is None:
        collector = RecordsCollector()
    
    # Valeurs invalides
    if result_category_match is None or result_category_match == 0:
        return collector


    def check_scope(scope_key: str, df: pd.DataFrame, 
                    identifiant: str, top_n: int) -> None:
        """Vérifie les records pour un scope donné."""
        if df is None or df.shape[0] == 0:
            return
        
        # Pour all-time, vérifier qu'il y a plusieurs saisons
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
            
        # Vérifier si trop d'égalités (évite le spam)
        record_counts = Counter(str(record) for _, _, record, _ in top_list)
        
        for idx, (joueur, champion, record, url) in enumerate(top_list):
            # Trop d'égalités = pas intéressant
            if record_counts[str(record)] >= 7:
                continue
                
            place = idx + 1
            
            try:
                result_float = float(result_category_match)
                record_float = float(record)
            except (ValueError, TypeError):
                continue
            
            # Égalisation
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
                break  # Un seul record par scope
            
            # Nouveau record
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
                break  # Un seul record par scope

    # Vérifier chaque scope
    check_scope('general', fichier, 'discord', top_n=10)
    check_scope('perso', fichier_joueur, 'riot_id', top_n=3)
    check_scope('alltime', fichier_all, 'discord', top_n=10)
    
    return collector


# ============================================================================
# FONCTION D'AJOUT À L'EMBED
# ============================================================================

def add_records_to_embed(embed, 
                         collector: RecordsCollector, 
                         title: str = "Exploits",
                         max_field_len: int = 1024, 
                         total_limit: int = 3500) -> Any:
    """
    Ajoute les records à un embed Discord, groupés par scope.
    
    Parameters
    ----------
    embed : interactions.Embed
        L'embed à enrichir
    collector : RecordsCollector
        Le collecteur de records
    title : str
        Titre du champ
    max_field_len : int
        Longueur max par champ Discord (limite API: 1024)
    total_limit : int
        Limite totale avant de passer en mode résumé
        
    Returns
    -------
    interactions.Embed
        L'embed enrichi
    """
    # Aucun record
    if collector.is_empty():
        embed.add_field(name=title, value="Aucun exploit", inline=False)
        return embed
    
    parts = collector.format_for_embed()
    total_content = '\n\n'.join(parts)
    
    # Contenu trop long → afficher un résumé
    if len(total_content) > total_limit:
        summary = collector.get_summary()
        
        if len(summary) <= max_field_len:
            embed.add_field(
                name=f"{title} (résumé)", 
                value=summary, 
                inline=False
            )
        else:
            # Même le résumé est trop long, découper
            _add_chunked_content(
                embed, 
                summary, 
                base_title=f"{title} (résumé)",
                max_len=max_field_len
            )
    else:
        # Affichage normal groupé par scope
        current = ""
        field_index = 1
        
        for part in parts:
            part = part.strip()
            
            # Tronquer si une partie est trop longue
            if len(part) > max_field_len:
                part = part[:max_field_len - 3] + '...'
            
            # Si ajouter cette partie dépasse la limite, créer un nouveau champ
            separator = "\n\n" if current else ""
            if current and len(current) + len(separator) + len(part) > max_field_len:
                embed.add_field(
                    name=title if field_index == 1 else f"{title} ({field_index})",
                    value=current.strip(),
                    inline=False
                )
                current = ""
                field_index += 1
            
            current += separator + part
        
        # Ajouter le dernier champ
        if current.strip():
            embed.add_field(
                name=title if field_index == 1 else f"{title} ({field_index})",
                value=current.strip(),
                inline=False
            )
    
    return embed


def _add_chunked_content(embed, content: str, base_title: str, 
                         max_len: int = 1024) -> None:
    """Ajoute du contenu découpé en plusieurs champs si nécessaire."""
    lines = content.split('\n')
    current = ""
    index = 1
    
    for line in lines:
        if len(current) + len(line) + 1 > max_len:
            embed.add_field(
                name=base_title if index == 1 else f"{base_title} {index}",
                value=current.strip(),
                inline=False
            )
            current = ""
            index += 1
        current += line + "\n"
    
    if current.strip():
        embed.add_field(
            name=base_title if index == 1 else f"{base_title} {index}",
            value=current.strip(),
            inline=False
        )
