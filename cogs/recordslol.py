import numpy as np
import pandas as pd
from fonctions.gestion_bdd import lire_bdd, lire_bdd_perso
from fonctions.autocomplete import autocomplete_record
from fonctions.word import suggestion_word
import interactions
from interactions import SlashCommandChoice, SlashCommandOption, Extension, SlashContext, slash_command, AutocompleteContext
from interactions.ext.paginators import Paginator
from utils.params import Version, saison
from fonctions.match.riot_api import get_champ_list, get_version
from fonctions.match.records import trouver_records_multiples, get_stat_null_rules
from utils.emoji import emote_champ_discord
from aiohttp import ClientSession
import plotly.express as px
import asyncio
from fonctions.channels_discord import get_embed, mention
import difflib
from utils.emoji import emote_v2


def option_stats_records(name, params, description='type de recherche'):
    option = SlashCommandOption(
        name=name,
        description=description,
        type=interactions.OptionType.SUB_COMMAND,
        options=params)

    return option


def safe_round(series, decimals=2):
    """Arrondit une série en gérant les NaN et types mixtes."""
    try:
        return pd.to_numeric(series, errors='coerce').round(decimals)
    except Exception:
        return series


def safe_astype_int(series):
    """Convertit en int en gérant les NaN."""
    try:
        return pd.to_numeric(series, errors='coerce').fillna(0).astype(int)
    except Exception:
        return series.fillna(0)


def add_aggregated_data(df: pd.DataFrame, min_games: int = 3) -> pd.DataFrame:
    """
    Ajoute des lignes de statistiques moyennes/cumulées au DataFrame.
    
    Ces lignes agrégées sont ajoutées avec les colonnes originales mises à NaN
    pour éviter les conflits avec les records par match.
    
    Parameters
    ----------
    df : pd.DataFrame
        DataFrame des matchs individuels
    min_games : int
        Nombre minimum de parties pour être éligible aux records agrégés
        
    Returns
    -------
    pd.DataFrame
        DataFrame avec les lignes agrégées ajoutées
    """
    if df.empty:
        return df
    
    # Colonnes à moyenner
    cols_to_mean = [
        'kills', 'deaths', 'assists', 'kda', 'kp',
        'vision_score', 'vision_min',
        'cs', 'cs_jungle', 'cs_min',
        'dmg', 'dmg_min', 'dmg_tank', 'damageratio', 'tankratio',
        'gold', 'gold_min', 'gold_share',
        'heal_total', 'shield', 'dmg_reduit',
        'time', 'trade_efficience',
        'serie_kills'
    ]
    
    # Colonnes à sommer
    cols_to_sum = ['penta', 'quadra', 'triple', 'double', 'solokills']
    
    # Vérifier que les colonnes existent
    cols_mean = [c for c in cols_to_mean if c in df.columns]
    cols_sum = [c for c in cols_to_sum if c in df.columns]
    
    # Grouper par joueur ET champion (pour que les filtres par champion fonctionnent)
    groupby_cols = ['discord', 'riot_id', 'riot_tagline', 'champion']
    groupby_cols = [c for c in groupby_cols if c in df.columns]
    
    if not groupby_cols:
        return df
    
    # Convertir les colonnes numériques avant agrégation
    df_work = df.copy()
    for c in cols_mean + cols_sum:
        if c in df_work.columns:
            df_work[c] = pd.to_numeric(df_work[c], errors='coerce')
    
    if 'victoire' in df_work.columns:
        # Convertir victoire en 0/1
        df_work['victoire_num'] = df_work['victoire'].apply(lambda x: 1 if x == True or x == 1 else 0)
    
    # Construire le dictionnaire d'agrégation
    agg_dict = {
        'match_id': 'last',  # Dernier match pour avoir un lien valide
        'id_participant': 'last',
        'season': 'last',
    }
    
    # Ajouter les colonnes optionnelles si elles existent
    if 'server_id' in df_work.columns:
        agg_dict['server_id'] = 'last'
    if 'url' in df_work.columns:
        agg_dict['url'] = 'last'
    
    # Moyennes
    for c in cols_mean:
        agg_dict[c] = 'mean'
    
    # Sommes
    for c in cols_sum:
        if c not in agg_dict:  # Éviter les doublons (solokills est dans les deux)
            agg_dict[c] = 'sum'
    
    # Victoires pour winrate
    if 'victoire_num' in df_work.columns:
        agg_dict['victoire_num'] = 'sum'
    
    try:
        # Trier par match_id pour avoir le dernier match
        df_sorted = df_work.sort_values('match_id') if 'match_id' in df_work.columns else df_work
        
        # Agrégation
        df_agg = df_sorted.groupby(groupby_cols, as_index=False).agg(agg_dict)
        
        # Compter le nombre de games
        counts = df_work.groupby(groupby_cols, as_index=False)['match_id'].count()
        counts.columns = list(groupby_cols) + ['nb_games']
        df_agg = df_agg.merge(counts, on=groupby_cols)
        
        # Filtrer par nombre minimum de parties
        df_agg = df_agg[df_agg['nb_games'] >= min_games]
        
        if df_agg.empty:
            return df
        
        # =================================================================
        # CRÉATION DES NOUVELLES COLONNES DE RECORDS AGRÉGÉS
        # =================================================================
        
        # Moyennes (renommer pour éviter confusion avec les valeurs brutes)
        if 'kills' in cols_mean:
            df_agg['avg_kills'] = safe_round(df_agg['kills'], 2)
        if 'deaths' in cols_mean:
            df_agg['avg_deaths'] = safe_round(df_agg['deaths'], 2)
        if 'assists' in cols_mean:
            df_agg['avg_assists'] = safe_round(df_agg['assists'], 2)
        if 'kda' in cols_mean:
            df_agg['avg_kda'] = safe_round(df_agg['kda'], 2)
        if 'kp' in cols_mean:
            df_agg['avg_kp'] = safe_round(df_agg['kp'], 2)
        if 'vision_score' in cols_mean:
            df_agg['avg_vision'] = safe_round(df_agg['vision_score'], 2)
        if 'vision_min' in cols_mean:
            df_agg['avg_vision_min'] = safe_round(df_agg['vision_min'], 2)
        if 'cs' in cols_mean:
            df_agg['avg_cs'] = safe_round(df_agg['cs'], 2)
        if 'cs_min' in cols_mean:
            df_agg['avg_cs_min'] = safe_round(df_agg['cs_min'], 2)
        if 'dmg' in cols_mean:
            df_agg['avg_dmg'] = safe_round(df_agg['dmg'], 0)
        if 'dmg_min' in cols_mean:
            df_agg['avg_dmg_min'] = safe_round(df_agg['dmg_min'], 0)
        if 'dmg_tank' in cols_mean:
            df_agg['avg_dmg_tank'] = safe_round(df_agg['dmg_tank'], 0)
        if 'gold' in cols_mean:
            df_agg['avg_gold'] = safe_round(df_agg['gold'], 0)
        if 'gold_min' in cols_mean:
            df_agg['avg_gold_min'] = safe_round(df_agg['gold_min'], 2)
        if 'gold_share' in cols_mean:
            df_agg['avg_gold_share'] = safe_round(df_agg['gold_share'], 2)
        if 'damageratio' in cols_mean:
            df_agg['avg_damageratio'] = safe_round(df_agg['damageratio'], 2)
        if 'tankratio' in cols_mean:
            df_agg['avg_tankratio'] = safe_round(df_agg['tankratio'], 2)
        if 'heal_total' in cols_mean:
            df_agg['avg_heal'] = safe_round(df_agg['heal_total'], 0)
        if 'shield' in cols_mean:
            df_agg['avg_shield'] = safe_round(df_agg['shield'], 0)
        if 'dmg_reduit' in cols_mean:
            df_agg['avg_dmg_reduit'] = safe_round(df_agg['dmg_reduit'], 0)
        if 'trade_efficience' in cols_mean:
            df_agg['avg_trade_efficience'] = safe_round(df_agg['trade_efficience'], 2)
        # if 'solokills' in cols_mean:
        #     df_agg['avg_solokills'] = safe_round(df_agg['solokills'], 2)
        if 'time' in cols_mean:
            df_agg['avg_time'] = safe_round(df_agg['time'], 2)
        
        # Ratios par game (multikills)
        if 'penta' in df_agg.columns:
            df_agg['penta_game'] = safe_round(df_agg['penta'] / df_agg['nb_games'], 4)
            df_agg['total_penta'] = safe_astype_int(df_agg['penta'])
        if 'quadra' in df_agg.columns:
            df_agg['quadra_game'] = safe_round(df_agg['quadra'] / df_agg['nb_games'], 4)
            df_agg['total_quadra'] = safe_astype_int(df_agg['quadra'])
        if 'triple' in df_agg.columns:
            df_agg['triple_game'] = safe_round(df_agg['triple'] / df_agg['nb_games'], 4)
            df_agg['total_triple'] = safe_astype_int(df_agg['triple'])
        if 'double' in df_agg.columns:
            df_agg['double_game'] = safe_round(df_agg['double'] / df_agg['nb_games'], 4)
            df_agg['total_double'] = safe_astype_int(df_agg['double'])
        if 'solokills' in cols_sum:
            df_agg['avg_solokills'] = safe_round(df_agg['solokills'] / df_agg['nb_games'], 4)
            df_agg['total_solokills'] = safe_astype_int(df_agg['solokills'])
        
        # Winrate
        if 'victoire_num' in df_agg.columns:
            df_agg['winrate'] = safe_round((df_agg['victoire_num'] / df_agg['nb_games']) * 100, 2)
            df_agg['total_wins'] = safe_astype_int(df_agg['victoire_num'])
        
        # =================================================================
        # NETTOYAGE : Mettre les colonnes brutes à NaN pour éviter conflits
        # =================================================================
        
        # Liste de toutes les colonnes "par match" qui ne doivent pas être
        # considérées comme des records dans les lignes agrégées
        cols_to_nullify = [
            # Stats de base
            'kills', 'deaths', 'assists', 'kda', 'kp',
            'double', 'triple', 'quadra', 'penta', 'solokills',
            'team_kills', 'team_deaths', 'serie_kills',
            # DMG
            'dmg', 'dmg_ad', 'dmg_ap', 'dmg_true', 'dmg_min', 'damageratio',
            'crit_dmg', 'dmg_all', 'dmg_all_min', 'dmg/gold', 'dmg_par_kills',
            # Vision
            'vision_score', 'vision_pink', 'vision_wards', 'vision_wards_killed',
            'vision_min', 'vision_avantage',
            # Farming
            'cs', 'cs_jungle', 'cs_min', 'cs_dix_min', 'jgl_dix_min', 'cs_max_avantage',
            # Tank/Heal
            'dmg_tank', 'dmg_reduit', 'tankratio', 'shield', 'heal_total', 'heal_allies',
            # Gold
            'gold', 'gold_min', 'gold_share',
            # Objectifs
            'baron', 'drake', 'early_drake', 'early_baron', 'dmg_tower',
            'tower', 'inhib', 'fourth_dragon', 'first_elder', 'first_horde',
            # Timing
            'time', 'temps_dead', 'temps_vivant', 'temps_avant_premiere_mort',
            # Combat
            'skillshot_dodged', 'skillshot_hit', 'trade_efficience', 'temps_cc',
            'spells_used', 'buffs_voles', 'immobilisation', 'first_blood',
            # Stats max
            'abilityPower', 'armor', 'attackDamage', 'currentGold',
            'healthMax', 'magicResist', 'movementSpeed',
            # Ecarts
            'ecart_kills', 'ecart_deaths', 'ecart_assists', 'ecart_dmg',
            'ecart_gold_team', 'level_max_avantage', 'allie_feeder',
            # Autres
            'snowball', 'first_double', 'first_triple', 'first_quadra', 'first_penta',
            'kills_min', 'deaths_min', 'assists_min', 'longue_serie_kills',
            'killsratio', 'deathsratio', 'solokillsratio', 'kills+assists'
        ]
        
        for col in cols_to_nullify:
            if col in df_agg.columns:
                df_agg[col] = np.nan
        
        # Marquer les lignes comme agrégées (utile pour le debug ou filtrage)
        df_agg['is_aggregated'] = True
        if 'is_aggregated' not in df.columns:
            df['is_aggregated'] = False
        
        # =================================================================
        # FUSION AVEC LE DATAFRAME ORIGINAL
        # =================================================================
        
        result = pd.concat([df, df_agg], ignore_index=True)
        
        return result
        
    except Exception as e:
        print(f"Erreur dans add_aggregated_data: {e}")
        return df






async def load_data(ctx, view, saison, mode, time_mini):
    stat_null_rules = get_stat_null_rules()

    untouched_columns = [
        'max_data_timeline."abilityHaste"', 'max_data_timeline."abilityPower"', 'max_data_timeline."armor"',
        'max_data_timeline."attackDamage"', 'max_data_timeline."currentGold"', 'max_data_timeline."healthMax"',
        'max_data_timeline."magicResist"', 'max_data_timeline."movementSpeed"',
        'data_timeline_palier."ASSISTS_10"', 'data_timeline_palier."ASSISTS_20"', 'data_timeline_palier."ASSISTS_30"',
        'data_timeline_palier."BUILDING_KILL_10"', 'data_timeline_palier."BUILDING_KILL_20"', 'data_timeline_palier."BUILDING_KILL_30"',
        'data_timeline_palier."CHAMPION_KILL_10"', 'data_timeline_palier."CHAMPION_KILL_20"', 'data_timeline_palier."CHAMPION_KILL_30"',
        'data_timeline_palier."DEATHS_10"', 'data_timeline_palier."DEATHS_20"', 'data_timeline_palier."DEATHS_30"',
        'data_timeline_palier."ELITE_MONSTER_KILL_10"', 'data_timeline_palier."ELITE_MONSTER_KILL_20"', 'data_timeline_palier."ELITE_MONSTER_KILL_30"',
        'data_timeline_palier."ITEM_DESTROYED_10"', 'data_timeline_palier."ITEM_DESTROYED_20"', 'data_timeline_palier."ITEM_DESTROYED_30"',
        'data_timeline_palier."ITEM_PURCHASED_10"', 'data_timeline_palier."ITEM_PURCHASED_20"', 'data_timeline_palier."ITEM_PURCHASED_30"',
        'data_timeline_palier."ITEM_SOLD_10"', 'data_timeline_palier."ITEM_SOLD_20"', 'data_timeline_palier."ITEM_SOLD_30"',
        'data_timeline_palier."ITEM_UNDO_10"', 'data_timeline_palier."ITEM_UNDO_20"', 'data_timeline_palier."ITEM_UNDO_30"',
        'data_timeline_palier."LEVEL_UP_10"', 'data_timeline_palier."LEVEL_UP_20"', 'data_timeline_palier."LEVEL_UP_30"',
        'data_timeline_palier."SKILL_LEVEL_UP_10"', 'data_timeline_palier."SKILL_LEVEL_UP_20"', 'data_timeline_palier."SKILL_LEVEL_UP_30"',
        'data_timeline_palier."TURRET_PLATE_DESTROYED_10"', 'data_timeline_palier."TURRET_PLATE_DESTROYED_20"', 'data_timeline_palier."TURRET_PLATE_DESTROYED_30"',
        'data_timeline_palier."WARD_KILL_10"', 'data_timeline_palier."WARD_KILL_20"', 'data_timeline_palier."WARD_KILL_30"',
        'data_timeline_palier."WARD_PLACED_10"', 'data_timeline_palier."WARD_PLACED_20"', 'data_timeline_palier."WARD_PLACED_30"',
        'data_timeline_palier."CHAMPION_TRANSFORM_10"', 'data_timeline_palier."CHAMPION_TRANSFORM_20"', 'data_timeline_palier."CHAMPION_TRANSFORM_30"',
        'data_timeline_palier."TOTAL_CS_20"', 'data_timeline_palier."TOTAL_CS_30"', 'data_timeline_palier."TOTAL_GOLD_20"', 'data_timeline_palier."TOTAL_GOLD_30"',
        'data_timeline_palier."CS_20"', 'data_timeline_palier."CS_30"', 'data_timeline_palier."JGL_20"', 'data_timeline_palier."JGL_30"',
        'data_timeline_palier."TOTAL_DMG_10"', 'data_timeline_palier."TOTAL_DMG_20"', 'data_timeline_palier."TOTAL_DMG_30"',
        'data_timeline_palier."TOTAL_DMG_TAKEN_10"', 'data_timeline_palier."TOTAL_DMG_TAKEN_20"', 'data_timeline_palier."TOTAL_DMG_TAKEN_30"',
        'data_timeline_palier."TRADE_EFFICIENCE_10"', 'data_timeline_palier."TRADE_EFFICIENCE_20"', 'data_timeline_palier."TRADE_EFFICIENCE_30"',
        'records_loser."l_ecart_cs"', 'records_loser."l_ecart_gold"', 'records_loser."l_ecart_gold_min_durant_game"',
        'records_loser."l_ecart_gold_max_durant_game"', 'records_loser."l_kda"', 'records_loser."l_cs"', 'records_loser."l_cs_max_avantage"',
        'records_loser."l_level_max_avantage"', 'records_loser."l_ecart_gold_team"', 'records_loser."l_ecart_kills_team"',
        'records_loser."l_temps_avant_premiere_mort"', 'records_loser."l_ecart_kills"', 'records_loser."l_ecart_deaths"',
        'records_loser."l_ecart_assists"', 'records_loser."l_ecart_dmg"', 'records_loser."l_allie_feeder"',
        'records_loser."l_temps_vivant"', 'records_loser."l_time"', 'records_loser."l_solokills"',
    ]

    all_columns = [
        "matchs.*",
        "tracker.riot_id", "tracker.riot_tagline", "tracker.discord"
    ] + untouched_columns

    # Requête SQL allégée : uniquement les filtres liés aux JOINs et aux données essentielles
    base_query = f'''
        SELECT DISTINCT {', '.join(all_columns)}
        FROM matchs
        INNER JOIN tracker ON tracker.id_compte = matchs.joueur
        LEFT JOIN max_data_timeline ON matchs.joueur = max_data_timeline.riot_id AND matchs.match_id = max_data_timeline.match_id
        LEFT JOIN data_timeline_palier ON matchs.joueur = data_timeline_palier.riot_id AND matchs.match_id = data_timeline_palier.match_id
        LEFT JOIN records_loser ON matchs.joueur = records_loser.joueur AND matchs.match_id = records_loser.match_id
        WHERE tracker.banned = false
          AND tracker.save_records = true
          AND matchs.records = true
    '''

    fichier = lire_bdd_perso(base_query, index_col='id').transpose()

    # Filtres pandas (plus rapides que côté SQL pour des conditions simples sur des données déjà chargées)
    fichier = fichier[fichier['mode'] == mode]
    fichier = fichier[fichier['time'] >= time_mini[mode]]

    if saison != 0:
        fichier = fichier[fichier['season'] == saison]
    if view == 'serveur':
        fichier = fichier[fichier['server_id'] == int(ctx.guild_id)]

    # Règles d'annulation dynamiques
    if 'champion' in fichier.columns:
        for col, champions in stat_null_rules.items():
            if col in fichier.columns and col != 'champion':
                fichier.loc[fichier['champion'].isin(champions), col] = None

    fichier = add_aggregated_data(fichier, min_games=15)

    return fichier





        
async def format_value(joueur, champion, url, short=False):
            text = ''
            for j, c, u in zip(joueur, champion, url):
                if short:
                    text += f'**__ {j} __ {c} ** \n'
                else:
                    text += f'**__{j}__** [{c}]({u}) \n'
            return text

async def format_value_season(joueur, champion, url, liste_season, short=False):
            text = ''
            for j, c, u, s in zip(joueur, champion, url, liste_season):
                if short:
                    text += f'**__ {j} __ {c} S{s} ** \n'
                else:
                    text += f'**__{j}__** [{c}]({u}) S{s}\n'
            return text
        

async def creation_embed(fichier, column, methode_pseudo, embed, methode='max', saison=saison, rank=False):
                if rank:
                    joueur, champion, record, url, rank_joueur, season= trouver_records_multiples(fichier, column, methode, identifiant=methode_pseudo, rank=rank)
                else:
                    joueur, champion, record, url, season = trouver_records_multiples(fichier, column, methode, identifiant=methode_pseudo)
                # on montre l'image du champ uniquement quand le record appartient à une seule personne sinon on dépasse la limite de caractères
                
                if saison != 0:
                    value_text = await format_value(joueur, champion, url, short=False) if len(joueur) > 1 else f"**{joueur[0]}** {emote_champ_discord.get(champion[0].capitalize(), 'inconnu')} [G]({url[0]})\n"
                else:
                    value_text = await format_value_season(joueur, champion, url, season, short=False) if len(joueur) > 1 else f"**{joueur[0]}** {emote_champ_discord.get(champion[0].capitalize(), 'inconnu')} [G]({url[0]}) S{season[0]}\n"

                if rank:
                    embed.add_field(
                        name=f'{emote_v2.get(column, ":star:")}{column.upper()}',
                        value=f"Records : __{record}__ (#{rank_joueur}) \n {value_text}",
                        inline=True
                    )
                else:
                    embed.add_field(
                        name=f'{emote_v2.get(column, ":star:")}{column.upper()}',
                        value=f"Records : __ {record} __ \n {value_text}",
                        inline=True
                    )
                
                return embed

async def calcul_record(fichier, liste_records, records_min, title, title_personnalise, methode_pseudo, saison, rank:bool):
            embed = interactions.Embed(title=f'{title} {title_personnalise}', color=interactions.Color.random())

            for column in liste_records:
                methode = 'max'
                if column in records_min:
                    methode = 'min'

                embed = await creation_embed(fichier, column, methode_pseudo, embed, methode, saison=saison, rank=rank)
            
            return embed



class Recordslol(Extension):
    def __init__(self, bot):
        self.bot: interactions.Client = bot
        self.time_mini = {'RANKED' : 15, 'ARAM' : 10, 'FLEX' : 15, 'SWIFTPLAY' : 15} # minutes minimum pour compter dans les records
        
        self.fichiers = {
            'kills': ['kills', 'assists', 'deaths', 'double', 'triple', 'quadra', 'penta', 'solokills', 'team_kills', 'team_deaths', 'kda', 'kp', 'kills+assists', 'serie_kills', 'first_double', 'first_triple', 'first_quadra', 'first_penta'],
            'kills2': ['kills_min', 'deaths_min', 'assists_min', 'longue_serie_kills', 'ecart_kills', 'ecart_deaths', 'ecart_assists', 'killsratio', 'deathsratio', 'solokillsratio'],
            'dmg': ['dmg', 'dmg_ad', 'dmg_ap', 'dmg_true', 'damageratio', 'dmg_min', 'dmg/gold', 'crit_dmg', 'dmg_true_all', 'dmg_true_all_min', 'dmg_ad_all', 'dmg_ad_all_min', 'dmg_ap_all', 'dmg_ap_all_min', 'dmg_all', 'dmg_all_min', 'ecart_dmg', 'dmg_par_kills'],
            'vision': ['vision_score', 'vision_pink', 'vision_wards', 'vision_wards_killed', 'vision_min', 'vision_avantage'],
            'farming': ['cs', 'cs_jungle', 'cs_min', 'cs_dix_min', 'jgl_dix_min', 'cs_max_avantage'],
            'tank_heal': ['dmg_reduit', 'dmg_tank', 'tankratio', 'shield', 'heal_total', 'heal_allies'],
            'objectif': ['baron', 'drake', 'early_drake', 'early_baron', 'dmg_tower', 'fourth_dragon', 'first_elder', 'first_horde', 'petales_sanglants', 'tower', 'inhib', 'early_atakhan', 'first_tower_time'],
            'divers': ['time', 'gold', 'gold_min', 'gold_share', 'ecart_gold_team', 'level_max_avantage', 'temps_dead', 'temps_vivant', 'allie_feeder', 'temps_avant_premiere_mort', 'snowball'],
            'fight': ['skillshot_dodged', 'skillshot_hit', 'skillshots_dodge_min', 'skillshots_hit_min', 'trade_efficience', 'temps_cc', 'spells_used', 'buffs_voles', 'immobilisation', 'temps_cc_inflige', 'first_blood'],
            'stats': ['abilityPower', 'armor', 'attackDamage', 'currentGold', 'healthMax', 'magicResist', 'movementSpeed', 'first_niveau_max'],
            'timer': ["ASSISTS_10", "ASSISTS_20", "ASSISTS_30", "BUILDING_KILL_20", "BUILDING_KILL_30", "CHAMPION_KILL_10", "CHAMPION_KILL_20", "CHAMPION_KILL_30", "DEATHS_10", "DEATHS_20", "DEATHS_30", "ELITE_MONSTER_KILL_10", "ELITE_MONSTER_KILL_20", "ELITE_MONSTER_KILL_30", "LEVEL_UP_10", "LEVEL_UP_20", "LEVEL_UP_30"],
            'timer2': ["TURRET_PLATE_DESTROYED_10", "WARD_KILL_10", "WARD_KILL_20", "WARD_KILL_30", "WARD_PLACED_10", "WARD_PLACED_20", "WARD_PLACED_30", "TOTAL_CS_20", "TOTAL_CS_30", "TOTAL_GOLD_20", "TOTAL_GOLD_30", "CS_20", "CS_30", "JGL_20", "JGL_30"],
            'timer3' : ["TOTAL_DMG_10", "TOTAL_DMG_20", "TOTAL_DMG_30", "TOTAL_DMG_TAKEN_10", "TOTAL_DMG_TAKEN_20", "TOTAL_DMG_TAKEN_30", "TRADE_EFFICIENCE_10", "TRADE_EFFICIENCE_20", "TRADE_EFFICIENCE_30"],
            'loser': ['l_ecart_cs', 'l_ecart_gold', 'l_ecart_gold_min_durant_game', 'l_ecart_gold_max_durant_game', 'l_kda', 'l_cs', 'l_cs_max_avantage', 'l_level_max_avantage', 'l_ecart_gold_team', 'l_ecart_kills_team', 'l_temps_avant_premiere_mort', 'l_ecart_kills', 'l_ecart_deaths', 'l_ecart_assists', 'l_ecart_dmg', 'l_allie_feeder', 'l_temps_vivant', 'l_time', 'l_solokills'],
        # AJOUT DES NOUVELLES CATÉGORIES  <<<
        
        # Catégorie 1 : Moyennes de base (12 fields)
        'agreges_moyennes': [
            'avg_kills', 'avg_deaths', 'avg_assists', 'avg_kda', 'avg_kp',
            'avg_dmg', 'avg_dmg_min', 'avg_gold', 'avg_gold_min',
            'avg_cs', 'avg_cs_min', 'avg_time'
        ],
        
        # Catégorie 2 : Ratios et multikills (13 fields)
        'agreges_multikills': [
            'penta_game', 'quadra_game', 'triple_game', 'double_game',
            'total_penta', 'total_quadra', 'total_triple', 'total_double', 'total_solokills',
            'winrate', 'total_wins', 'avg_solokills'
        ],
        
        # Catégorie 3 : Tank/Support/Vision (11 fields) - pas pour ARAM
        'agreges_tank_vision': [
            'avg_vision', 'avg_vision_min',
            'avg_dmg_tank', 'avg_tankratio', 'avg_damageratio',
            'avg_heal', 'avg_shield', 'avg_dmg_reduit',
            'avg_gold_share', 'avg_trade_efficience'
        ],
        
        # Variante Tank/Support sans vision pour ARAM (8 fields)
        'agreges_tank_aram': [
            'avg_dmg_tank', 'avg_tankratio', 'avg_damageratio',
            'avg_heal', 'avg_shield', 'avg_dmg_reduit',
            'avg_gold_share', 'avg_trade_efficience'
        ],
    }

        

        self.liste_complete = [item for sublist in self.fichiers.values() for item in sublist]


        self.records_min = ['early_drake', 'early_baron', 'fourth_dragon', 'first_elder', 'first_horde', 'first_double', 'first_triple', 'first_quadra', 'first_penta', 'first_niveau_max', 'first_blood', 'early_atakhan', 'l_ecart_gold_min_durant_game', 'first_tower_time', 'avg_deaths']

        self.records_par_mode = {
            'RANKED': ['kills', 'kills2', 'dmg', 'vision', 'farming', 'tank_heal', 
                    'objectif', 'divers', 'fight', 'stats', 'timer', 'timer2', 'timer3', 'loser'],
            'FLEX': ['kills', 'kills2', 'dmg', 'vision', 'farming', 'tank_heal', 
                    'objectif', 'divers', 'fight', 'stats', 'timer', 'timer2', 'timer3', 'loser'],
            'SWIFTPLAY': ['kills', 'kills2', 'dmg', 'vision', 'farming', 'tank_heal', 
                        'objectif', 'divers', 'fight', 'stats', 'timer', 'timer2', 'timer3', 'loser'],
            'ARAM': ['kills', 'kills2', 'dmg', 'farming', 'tank_heal', 'divers', 'fight'],
        }        
    @slash_command(name='lol_records', description='records League of Legends')
    async def records_lol(self, ctx: SlashContext):
        pass


    parameters_communs = [
        SlashCommandOption(
            name="mode",
            description="Quel mode de jeu ?",
            type=interactions.OptionType.STRING,
            required=True, choices=[
                SlashCommandChoice(name='ranked',value='RANKED'),
                SlashCommandChoice(name='aram', value='ARAM'),
                SlashCommandChoice(name='swiftplay',value='SWIFTPLAY'),
                SlashCommandChoice(name='flex', value='FLEX')]),
        SlashCommandOption(
            name='saison',
            description='saison league of legends. Si 0 alors toutes les saisons',
            type=interactions.OptionType.INTEGER,
            required=False,
            min_value=0,
            max_value=saison),
        SlashCommandOption(
            name='champion',
            description='champion',
            type=interactions.OptionType.STRING,
            required=False),
        SlashCommandOption(
            name='view',
            description='global ou serveur ?',
            type=interactions.OptionType.STRING,
            required=False,
            choices=[
                SlashCommandChoice(name='global', value='global'),
                SlashCommandChoice(name='serveur', value='serveur')
            ]
        )]

    parameters_personnel = [
        SlashCommandOption(
            name="mode",
            description="Quel mode de jeu ?",
            type=interactions.OptionType.STRING,
            required=True, choices=[
                SlashCommandChoice(name='ranked',value='RANKED'),
                SlashCommandChoice(name='aram', value='ARAM'),
                SlashCommandChoice(name='swiftplay',value='SWIFTPLAY'),
                SlashCommandChoice(name='flex', value='FLEX')]),
        SlashCommandOption(
            name="joueur",
            description="Compte LoL (pas nécessaire si compte discord renseigné)",
            type=interactions.OptionType.STRING,
            required=False),
        SlashCommandOption(
            name="compte_discord",
            description='compte discord (pas nécessaire si compte lol renseigné)',
            type=interactions.OptionType.USER,
            required=False
        ),
        SlashCommandOption(
            name='saison',
            description='saison league of legends. Si 0 alors toutes les saisons. Si 0 alors toutes les saisons',
            type=interactions.OptionType.INTEGER,
            required=False,
            min_value=0,
            max_value=saison),
        SlashCommandOption(
            name='champion',
            description='champion',
            type=interactions.OptionType.STRING,
            required=False)]

    
    @records_lol.subcommand('general',
                                sub_cmd_description='Records tout confondus',
                                options=parameters_communs)
    async def records_list_general(self, ctx:SlashContext,
                                   saison:int=saison,
                                   mode:str = 'ranked',
                                   champion:str=None,
                                   view='global'):
        
        await ctx.defer(ephemeral=False)
        
        methode_pseudo = 'discord'

        fichier = await load_data(ctx, view, saison, mode, self.time_mini)

        if champion != None:
            
            champion = champion.capitalize()

            fichier = fichier[fichier['champion'] == champion] 
            
        if champion == None:
                title = f'Records {mode} S{saison}'
        else:
                title = f'Records {mode} S{saison} ({champion})'

        fichier_farming = self.fichiers['farming'].copy()
        fichier_divers = self.fichiers['divers'].copy()
        fichier_kills = self.fichiers['kills'].copy()
        fichier_kills2 = self.fichiers['kills2'].copy()
        fichier_timer = self.fichiers['timer'].copy()
        fichier_timer2 = self.fichiers['timer2'].copy()
        fichier_timer3 = self.fichiers['timer3'].copy()
        fichier_fight = self.fichiers['fight'].copy()

        # On adapte les éléments selon le mode
        if mode in ['RANKED', 'FLEX', 'SWIFTPLAY']:
            if 'snowball' in fichier_divers:
                fichier_divers.remove('snowball')

        if mode == 'ARAM':
            for item in ['cs_jungle', 'jgl_dix_min']:
                if item in fichier_farming:
                    fichier_farming.remove(item)

            for item in ['first_double', 'first_triple', 'first_quadra', 'first_penta']:
                if item in fichier_kills:
                    fichier_kills.remove(item)






        embed1 = await calcul_record(fichier, fichier_kills, self.records_min, title, 'Kills', methode_pseudo, saison, False)
        embed1_2 = await calcul_record(fichier, fichier_kills2, self.records_min, title, 'Kills2', methode_pseudo, saison, False)
        embed2 = await calcul_record(fichier, self.fichiers['dmg'], self.records_min, title, 'DMG', methode_pseudo, saison, False)
        embed5 = await calcul_record(fichier, fichier_farming, self.records_min, title, 'Farming', methode_pseudo, saison, False)
        embed6 = await calcul_record(fichier, self.fichiers['tank_heal'], self.records_min, title, 'Tank/Heal', methode_pseudo, saison, False)
        embed6_2 = await calcul_record(fichier, fichier_fight, self.records_min, title, 'Fight', methode_pseudo, saison, False)
        embed7 = await calcul_record(fichier, fichier_divers, self.records_min, title, 'Divers', methode_pseudo, saison, False)

        if mode != 'ARAM':
            embed3 = await calcul_record(fichier, self.fichiers['vision'], self.records_min, title, 'Vision', methode_pseudo, saison, False)
            embed4 = await calcul_record(fichier, self.fichiers['objectif'], self.records_min, title, 'Objectif', methode_pseudo, saison, False)
            embed8 = await calcul_record(fichier, self.fichiers['stats'], self.records_min, title, 'Stats', methode_pseudo, saison, False)
            embed9 = await calcul_record(fichier, fichier_timer, self.records_min, title, 'Timer', methode_pseudo, saison, False)
            embed10 = await calcul_record(fichier, fichier_timer2, self.records_min, title, 'Timer2', methode_pseudo, saison, False)
            embed10_2 = await calcul_record(fichier, fichier_timer3, self.records_min, title, 'Timer3', methode_pseudo, saison, False)
            embed11 = await calcul_record(fichier, self.fichiers['loser'], self.records_min, title, 'Loser', methode_pseudo, saison, False)


        
        # Page Moyennes de base
        embed_agreges_moy = await calcul_record(
            fichier, self.fichiers['agreges_moyennes'], self.records_min, 
            title, 'Moyennes', methode_pseudo, saison, False
        )
        embed_agreges_moy.set_footer(text=f'Min 15 games requises | Version {Version}')
        
        # Page Multikills/Ratios
        embed_agreges_multi = await calcul_record(
            fichier, self.fichiers['agreges_multikills'], self.records_min, 
            title, 'Multikills & Cumuls', methode_pseudo, saison, False
        )
        embed_agreges_multi.set_footer(text=f'Min 15 games requises | Version {Version}')
        
        # Page Tank/Vision (pas pour ARAM)
        if mode != 'ARAM':
            embed_agreges_tank = await calcul_record(
                fichier, self.fichiers['agreges_tank_vision'], self.records_min, 
                title, 'Tank/Vision Moyennés', methode_pseudo, saison, False
            )
        else:
            embed_agreges_tank = await calcul_record(
                fichier, self.fichiers['agreges_tank_aram'], self.records_min, 
                title, 'Tank Moyennés', methode_pseudo, saison, False
            )
        embed_agreges_tank.set_footer(text=f'Min 15 games requises | Version {Version}')
    
            
        for embed in [embed1, embed1_2, embed2, embed5, embed6, embed6_2, embed7]:
            embed.set_footer(text=f'Version {Version} by Tomlora')



        if mode != 'ARAM':
            for embed in [embed3, embed4, embed8, embed9, embed10, embed10_2, embed11]:
                embed.set_footer(text=f'Version {Version} by Tomlora')

            pages = [embed1, embed1_2, embed2, embed3, embed4, embed5, embed6, 
                    embed6_2, embed7, embed8, embed9, embed10, embed10_2, embed11,
                    embed_agreges_moy, embed_agreges_multi, embed_agreges_tank]

        else:
            pages = [embed1, embed1_2, embed2, embed5, embed6, embed6_2, embed7,
                    embed_agreges_moy, embed_agreges_multi, embed_agreges_tank]
        
        paginator = Paginator.create_from_embeds(
            self.bot,
            *pages
        )
        paginator.show_select_menu = True
        
        await paginator.send(ctx)   
            
        
    @records_lol.subcommand('personnel',
                                sub_cmd_description='Records personnels sur un joueur',
                                options=parameters_personnel)
    async def records_list_personnel(self,
                              ctx: SlashContext,
                              saison: int = saison,
                              mode: str = 'ranked',
                              joueur= None,
                              compte_discord : interactions.User = None,
                              champion : str =None,
                              view='global'):

        await ctx.defer(ephemeral=False)
        
        methode_pseudo = 'discord'
    
        fichier = await load_data(ctx, view, saison, mode, self.time_mini)

        
        fichier['early_drake'] = fichier['early_drake'].replace({0 : 999})    
        fichier['early_baron'] = fichier['early_baron'].replace({0 : 999}) 
        
        
        
        for column in self.liste_complete:
            
            try:
                fichier[f'{column}_rank_max'] = fichier[column].rank(method='min', ascending=False).astype(int)
                fichier[f'{column}_rank_min'] = fichier[column].rank(method='min', ascending=True).astype(int)
            except:
                try:
                    fichier[column].fillna(0, inplace=True)
                    fichier[f'{column}_rank_max'] = fichier[column].rank(method='min', ascending=False).astype(int)
                    fichier[f'{column}_rank_min'] = fichier[column].rank(method='min', ascending=True).astype(int)
                except:
                    print('erreur', column)
        
        nb_games = fichier.shape[0]    

        if champion != None:
            
            champion = champion.capitalize()

            fichier = fichier[fichier['champion'] == champion]

            
        if joueur != None:
            
            joueur = joueur.lower().replace(' ', '')
                
            id_joueur = lire_bdd_perso('''SELECT tracker.riot_id, tracker.discord from tracker where tracker.banned = false and tracker.save_records = true ''',
                                            format='dict', index_col='riot_id')
            try:
                fichier = fichier[fichier['riot_id'] == joueur]
            except KeyError:
                return await ctx.send('Joueur introuvable ou tu es banni')    
              
        elif compte_discord != None:
                
            id_discord = str(compte_discord.id)

                               
            joueur = compte_discord.global_name
            try:    
                fichier = fichier[fichier['discord'] == id_discord]
            except KeyError:
                return await ctx.send('Joueur introuvable ou tu es banni. ')    
                
            
        elif joueur == None and compte_discord == None:
                
            fichier = fichier[fichier['discord'] == str(ctx.author.id)]

            try:
                joueur = ctx.author.nick
            except AttributeError:
                try:
                    joueur = ctx.author.nickname
                except AttributeError:
                    joueur = ctx.user.global_name
            author_global = ctx.author.global_name
            if joueur == None:
                joueur = author_global                
            joueur = ctx.author.global_name
                
        methode_pseudo = 'riot_id'

        if champion == None:

                title = f'Records personnels {joueur} {mode} S{saison}'
        else:
                title = f'Records personnels {joueur} {mode} S{saison} ({champion})'

        
        # Copies locales des catégories modifiables
        fichier_farming = self.fichiers['farming'].copy()
        fichier_divers = self.fichiers['divers'].copy()
        fichier_timer = self.fichiers['timer'].copy()
        fichier_timer2 = self.fichiers['timer2'].copy()
        fichier_timer3 = self.fichiers['timer3'].copy()
        fichier_fight = self.fichiers['fight'].copy()

        # Ajustements selon le mode
        if mode in ['RANKED', 'FLEX', 'SWIFTPLAY']:
            if 'snowball' in fichier_divers:
                fichier_divers.remove('snowball')

        if mode == 'ARAM':
            for stat in ['cs_jungle', 'jgl_dix_min']:
                if stat in fichier_farming:
                    fichier_farming.remove(stat)

            to_remove_timer = [
                "WARD_KILL_10", "WARD_KILL_20", "WARD_KILL_30",
                "WARD_PLACED_10", "WARD_PLACED_20", "WARD_PLACED_30",
                "ELITE_MONSTER_KILL_10", "ELITE_MONSTER_KILL_20", "ELITE_MONSTER_KILL_30",
                "TURRET_PLATE_DESTROYED_10"
            ]
            for stat in to_remove_timer:
                if stat in fichier_timer:
                    fichier_timer.remove(stat)

        # Appels aux calculs
        embed1 = await calcul_record(fichier, self.fichiers['kills'], self.records_min, title, 'Kills', methode_pseudo, saison, True)
        embed1_2 = await calcul_record(fichier, self.fichiers['kills2'], self.records_min, title, 'Kills2', methode_pseudo, saison, True)
        embed2 = await calcul_record(fichier, self.fichiers['dmg'], self.records_min, title, 'DMG', methode_pseudo, saison, True)
        embed5 = await calcul_record(fichier, fichier_farming, self.records_min, title, 'Farming', methode_pseudo, saison, True)
        embed6 = await calcul_record(fichier, self.fichiers['tank_heal'], self.records_min, title, 'Tank/Heal', methode_pseudo, saison, True)
        embed6_2 = await calcul_record(fichier, fichier_fight, self.records_min, title, 'Fight', methode_pseudo, saison, True)
        embed7 = await calcul_record(fichier, fichier_divers, self.records_min, title, 'Divers', methode_pseudo, saison, True)

        if mode != 'ARAM':
            embed3 = await calcul_record(fichier, self.fichiers['vision'], self.records_min, title, 'Vision', methode_pseudo, saison, True)
            embed4 = await calcul_record(fichier, self.fichiers['objectif'], self.records_min, title, 'Objectif', methode_pseudo, saison, True)
            embed8 = await calcul_record(fichier, self.fichiers['stats'], self.records_min, title, 'Stats', methode_pseudo, saison, True)
            embed9 = await calcul_record(fichier, fichier_timer, self.records_min, title, 'Timer', methode_pseudo, saison, True)
            embed10 = await calcul_record(fichier, fichier_timer2, self.records_min, title, 'Timer2', methode_pseudo, saison, True)
            embed10_2 = await calcul_record(fichier, fichier_timer3, self.records_min, title, 'Timer3', methode_pseudo, saison, True)
            embed11 = await calcul_record(fichier, self.fichiers['loser'], self.records_min, title, 'Loser', methode_pseudo, saison, True)

            
    # Page Moyennes de base
        embed_agreges_moy = await calcul_record(
            fichier, self.fichiers['agreges_moyennes'], self.records_min, 
            title, 'Moyennes', methode_pseudo, saison, True
        )
        embed_agreges_moy.set_footer(text=f'Min 15 games requises | Version {Version} - {nb_games} parties')
        
        # Page Multikills/Ratios
        embed_agreges_multi = await calcul_record(
            fichier, self.fichiers['agreges_multikills'], self.records_min, 
            title, 'Multikills & Cumuls', methode_pseudo, saison, True
        )
        embed_agreges_multi.set_footer(text=f'Min 15 games requises | Version {Version} - {nb_games} parties')
        
        # Page Tank/Vision (adapté selon le mode)
        if mode != 'ARAM':
            embed_agreges_tank = await calcul_record(
                fichier, self.fichiers['agreges_tank_vision'], self.records_min, 
                title, 'Tank/Vision Moyennés', methode_pseudo, saison, True
            )
        else:
            embed_agreges_tank = await calcul_record(
                fichier, self.fichiers['agreges_tank_aram'], self.records_min, 
                title, 'Tank Moyennés', methode_pseudo, saison, True
            )
        embed_agreges_tank.set_footer(text=f'Min 15 games requises | Version {Version} - {nb_games} parties')


        for embed in [embed1, embed1_2, embed2, embed5, embed6, embed6_2, embed7]:
            embed.set_footer(text=f'Version {Version} by Tomlora - {nb_games} parties')


        if mode != 'ARAM':
            pages = [embed1, embed1_2, embed2, embed3, embed4, embed5, embed6, 
                    embed6_2, embed7, embed8, embed9, embed10, embed10_2, embed11,
                    embed_agreges_moy, embed_agreges_multi, embed_agreges_tank]
        else:
            pages = [embed1, embed1_2, embed2, embed5, embed6, embed6_2, embed7,
                    embed_agreges_moy, embed_agreges_multi, embed_agreges_tank]
            
        paginator = Paginator.create_from_embeds(
            self.bot,
            *pages,
        )
        
        paginator.show_select_menu = True
        await paginator.send(ctx)



    def get_liste_records(self, mode: str, inclure_agreges: bool = False) -> list:
        """
        Retourne la liste des records à utiliser selon le mode et les options.
        
        Parameters
        ----------
        mode : str
            Mode de jeu (RANKED, ARAM, FLEX, SWIFTPLAY)
        inclure_agreges : bool
            Inclure les records agrégés
            
        Returns
        -------
        list
            Liste des noms de colonnes de records
        """
        liste_records = []
        
        # Records standards pour ce mode
        categories = self.records_par_mode.get(mode, self.records_par_mode['RANKED'])
        for cat in categories:
            if cat in self.fichiers:
                liste_records.extend(self.fichiers[cat])
        
        # Ajout des records agrégés si demandé
        if inclure_agreges:
            categories_agreges = self.agreges_par_mode.get(mode, self.agreges_par_mode['RANKED'])
            for cat in categories_agreges:
                if cat in self.fichiers:
                    liste_records.extend(self.fichiers[cat])
        
        return liste_records


    # =============================================================================
    # 3. MÉTHODE HELPER POUR COMPTER LES RECORDS
    # =============================================================================

    def compter_records(self, fichier: pd.DataFrame, liste_records: list, 
                        list_champ: dict = None, par_champion: bool = False) -> pd.Series:
        """
        Compte le nombre de records par joueur.
        
        Parameters
        ----------
        fichier : pd.DataFrame
            DataFrame des matchs
        liste_records : list
            Liste des colonnes de records à compter
        list_champ : dict, optional
            Dictionnaire des champions (pour le comptage par champion)
        par_champion : bool
            Si True, compte les records par champion
            
        Returns
        -------
        pd.Series
            Comptage des records par joueur
        """
        liste_joueurs = []
        
        for record in liste_records:
            # Vérifier que la colonne existe
            if record not in fichier.columns:
                continue
                
            methode = 'min' if record in self.records_min else 'max'
            
            if par_champion and list_champ:
                # Comptage par champion
                for champ in list_champ.get('data', []):
                    try:
                        fichier_champ = fichier[fichier['champion'] == champ]
                        if fichier_champ.empty:
                            continue
                        joueur, *_ = trouver_records_multiples(fichier_champ, record, methode)
                        liste_joueurs.extend(joueur)
                    except Exception:
                        pass
            else:
                # Comptage général
                try:
                    joueur, *_ = trouver_records_multiples(fichier, record, methode)
                    liste_joueurs.extend(joueur)
                except Exception:
                    pass
        
        # Filtrer les "inconnu"
        liste_joueurs = [j for j in liste_joueurs if j != 'inconnu']
        
        return pd.Series(liste_joueurs).value_counts()


    # =============================================================================
    # 4. COMMANDE records_count SIMPLIFIÉE
    # =============================================================================

    @records_lol.subcommand("count",
                            sub_cmd_description="Compte le nombre de records",
                            options=[
                                SlashCommandOption(
                                    name="saison",
                                    description="Saison LoL (0 = toutes)",
                                    type=interactions.OptionType.INTEGER,
                                    required=False,
                                    min_value=0,
                                    max_value=saison),
                                SlashCommandOption(
                                    name='mode',
                                    description='Mode de jeu',
                                    type=interactions.OptionType.STRING,
                                    required=False,
                                    choices=[
                                        SlashCommandChoice(name='ranked', value='RANKED'),
                                        SlashCommandChoice(name='aram', value='ARAM'),
                                        SlashCommandChoice(name='flex', value='FLEX'),
                                        SlashCommandChoice(name='swiftplay', value='SWIFTPLAY'),
                                    ]
                                ),
                                SlashCommandOption(
                                    name='champion',
                                    description='Focus sur un champion',
                                    type=interactions.OptionType.STRING,
                                    required=False
                                ),
                                SlashCommandOption(
                                    name='view',
                                    description='Global ou serveur',
                                    type=interactions.OptionType.STRING,
                                    required=False,
                                    choices=[
                                        SlashCommandChoice(name='global', value='global'),
                                        SlashCommandChoice(name='serveur', value='serveur')
                                    ]
                                ),
                                SlashCommandOption(
                                    name='inclure_agreges',
                                    description='Inclure les records agrégés (moyennes, cumuls)',
                                    type=interactions.OptionType.BOOLEAN,
                                    required=False
                                )
                            ])
    async def records_count(self,
                            ctx: SlashContext,
                            saison: int = saison,
                            mode: str = 'RANKED',
                            champion: str = None,
                            view: str = 'global',
                            inclure_agreges: bool = False):

        await ctx.defer(ephemeral=False)

        # Charger les données
        fichier = await load_data(ctx, view, saison, mode, self.time_mini)
        
        # Obtenir la liste des records pour ce mode
        liste_records = self.get_liste_records(mode, inclure_agreges)
        
        # Suffixe pour les titres
        suffixe = " (avec agrégés)" if inclure_agreges else ""

        # Si champion spécifié, filtrer et afficher directement
        if champion:
            champion = champion.capitalize()
            fichier = fichier[fichier['champion'] == champion]
            
            counts = self.compter_records(fichier, liste_records)
            
            if counts.empty:
                return await ctx.send(f"Aucun record trouvé pour {champion}")
            
            fig = px.histogram(
                counts, counts.index, counts.values,
                text_auto=True, color=counts.index,
                title=f'Records {champion}{suffixe}'
            )
            fig.update_layout(showlegend=False)
            fig.write_image('image.png', width=1600, height=900)
            
            return await ctx.send(files=interactions.File('image.png'))

        # Sinon, proposer le choix général/par champion
        async with ClientSession() as session:
            version = await get_version(session)
            list_champ = await get_champ_list(session, version)

        # Pré-calculer les deux comptages
        counts_general = self.compter_records(fichier, liste_records)
        counts_champion = self.compter_records(fichier, liste_records, list_champ, par_champion=True)

        # Menu de sélection
        select = interactions.StringSelectMenu(
            interactions.StringSelectOption(label="Général", value="general", emoji="1️⃣"),
            interactions.StringSelectOption(label="Par champion", value="par_champion", emoji="2️⃣"),
            custom_id='selection_records_count',
            placeholder="Type de records",
        )

        message = await ctx.send(f"Quel type de record ?{suffixe}", components=select)

        def check(component):
            return int(component.ctx.author_id) == int(ctx.author.user.id)

        while True:
            try:
                component = await self.bot.wait_for_component(
                    components=select, check=check, timeout=120
                )

                choix = component.ctx.values[0]
                counts = counts_general if choix == "general" else counts_champion
                titre = "Général" if choix == "general" else "Par champion"

                fig = px.histogram(
                    counts, counts.index, counts.values,
                    text_auto=True, color=counts.index,
                    title=f'Records {titre}{suffixe}'
                )
                fig.update_layout(showlegend=False)
                fig.write_image('image.png', width=1600, height=900)
                
                await component.ctx.send(files=interactions.File('image.png'))

            except asyncio.TimeoutError:
                await message.edit(components=[])
                break



    @records_lol.subcommand("palmares",
                                    sub_cmd_description="Classement pour un record donné",
                                    options=[
                                        SlashCommandOption(
                                            name='stat',
                                            description='Nom du record (voir records) ou écrire champion pour le nombre de champions joués',
                                            type=interactions.OptionType.STRING,
                                            required=True,
                                            autocomplete=True
                                        ),
                                        SlashCommandOption(
                                            name="saison",
                                            description="saison lol ? Si 0 alors toutes les saisons",
                                            type=interactions.OptionType.INTEGER,
                                            required=False,
                                            min_value=0,
                                            max_value=saison),
                                        SlashCommandOption(
                                            name='mode',
                                            description='quel mode de jeu ?',
                                            type=interactions.OptionType.STRING,
                                            required=False,
                                            choices=[
                                                SlashCommandChoice(name='ranked', value='RANKED'),
                                                SlashCommandChoice(name='aram', value='ARAM'),
                                                SlashCommandChoice(name='swiftplay',value='SWIFTPLAY'),
                                                SlashCommandChoice(name='flex', value='FLEX')
                                            ]
                                        ),
                                        SlashCommandOption(
                                            name='champion',
                                            description='focus sur un champion ?',
                                            type=interactions.OptionType.STRING,
                                            required=False
                                        ),
                                        SlashCommandOption(
                                            name='joueur',
                                            description='focus sur un joueur ?',
                                            type=interactions.OptionType.STRING,
                                            required=False
                                        ),
                                        SlashCommandOption(
                                            name="compte_discord",
                                            description='focus sur un compte discord ?',
                                            type=interactions.OptionType.USER,
                                            required=False
                                        ),
                                        SlashCommandOption(
                                            name='view',
                                            description='Global ou serveur ?',
                                            type=interactions.OptionType.STRING,
                                            required=False,
                                            choices=[
                                                SlashCommandChoice(name='global', value='global'),
                                                SlashCommandChoice(name='serveur', value='serveur')
                                            ]
                                        ),
                                        SlashCommandOption(
                                            name='top',
                                            description='top à afficher',
                                            type=interactions.OptionType.INTEGER,
                                            required=False,
                                            min_value=10,
                                            max_value=25
                                        )
                                    ])
    async def palmares(self,
                        ctx: SlashContext,
                        stat : str,
                        saison: int = saison,
                        mode: str = 'RANKED',
                        champion: str = None,
                        joueur:str = None,
                        compte_discord: interactions.User = None,
                        view : str = 'global',
                        top : int = 10):


            # on récupère les champions

        await ctx.defer()

        stat = stat.lower()

        fichier = await load_data(ctx, view, saison, mode, self.time_mini)
        
        fichier.columns = [col.lower() for col in fichier.columns]
            
        if champion != None:
            fichier = fichier[fichier['champion'] == champion]
            
        if joueur != None:
            fichier = fichier[fichier['riot_id'] == joueur.replace(' ', '').lower()]
            
        if compte_discord != None:
            fichier = fichier[fichier['discord'] == str(compte_discord.id)]
            
            
            
        if stat == 'champion':
            fichier = fichier[['discord', 'champion', 'match_id']]
            nb_row = fichier.shape[0] 
            # on prépare le df count game
            count_game = fichier.groupby(['discord']).count().reset_index()
            count_game = count_game[['discord', 'champion']].rename(columns={'champion': 'count'})
            ascending=False
            # on prépare le fichier final
            
               
            fichier = fichier.groupby(['champion', 'discord']).count().sort_values(by='match_id', ascending=ascending).reset_index()
            nb_champion = len(fichier['champion'].unique())
            fichier = fichier.merge(count_game, on='discord', how='left')
            
            fichier['proportion'] = np.int8((fichier['match_id'] / fichier['count'])*100)
            
            
            fichier = fichier.head(top)   
            
            txt = ''
                
                
                
            for row, data in fichier.iterrows():
                champion = data['champion']
                txt += f'**{data["match_id"]}** - {mention(data["discord"], "membre")} {emote_champ_discord.get(champion.capitalize(), "inconnu")} - **{data["proportion"]}% des games**\n'
                
            embed = interactions.Embed(title=f'Palmarès {stat} ({mode}) S{saison}', description=txt)
            embed.set_footer(text=f"{nb_row} matchs analysés | {nb_champion} champions différents")
            
            await ctx.send(embeds=embed)
            
        else:
            
            try:
                fichier = fichier[['match_id', 'id_participant', 'discord', 'champion', stat, 'datetime', 'season']]
                
                nb_row = fichier.shape[0]
                
                                
                if stat in ['early_baron', 'early_drake', 'early_atakhan', 'l_ecart_gold_min_durant_game']:
                    ascending=True
                    fichier = fichier[fichier[stat] != 0]
                elif stat in ['fourth_dragon', 'first_elder', 'first_horde', 'first_double', 'first_triple', 'first_quadra', 'first_penta', 'first_niveau_max', 'first_blood', 'first_tower_time']:
                    ascending=True
                    fichier = fichier[fichier[stat] != 999]
                else:
                    ascending=False
                    fichier = fichier[fichier[stat] != 0]
                    
                fichier.sort_values(by=stat, ascending=ascending, inplace=True)
                fichier = fichier.head(top)
                
                txt = ''
                
                
                if saison != 0:
                    for row, data in fichier.iterrows():
                        champion = data['champion']
                        txt += f'[{data[stat]}](https://www.leagueofgraphs.com/fr/match/euw/{str(data["match_id"])[5:]}#participant{int(data["id_participant"])+1}) - {mention(data["discord"], "membre")} {emote_champ_discord.get(champion.capitalize(), "inconnu")} - {data["datetime"].day}/{data["datetime"].month} \n'
                else:
                    for row, data in fichier.iterrows():
                        champion = data['champion']
                        txt += f'[{data[stat]}](https://www.leagueofgraphs.com/fr/match/euw/{str(data["match_id"])[5:]}#participant{int(data["id_participant"])+1}) - {mention(data["discord"], "membre")} {emote_champ_discord.get(champion.capitalize(), "inconnu")} - {data["datetime"].day}/{data["datetime"].month} (S{data["season"]})\n'
                    
                embed = interactions.Embed(title=f'Palmarès {stat} ({mode}) S{saison}', description=txt)
                embed.set_footer(text=f"{nb_row} matchs analysés")
                
                
                await ctx.send(embeds=embed)
                
            except KeyError:              
                suggestion = suggestion_word(stat, fichier.columns.tolist())
                await ctx.send(f"Ce record n'existe pas. Souhaitais-tu dire : **{suggestion}** ?")
                

    @palmares.autocomplete("stat")

    async def autocomplete_game(self, ctx: interactions.AutocompleteContext):

        liste_choix = await autocomplete_record(ctx.input_text)

        await ctx.send(choices=liste_choix)

    @records_lol.subcommand("date_record",
                                    sub_cmd_description="Date des records",
                                    options=[
                                        SlashCommandOption(
                                            name="saison",
                                            description="saison lol",
                                            type=interactions.OptionType.INTEGER,
                                            required=False,
                                            min_value=13,
                                            max_value=saison),
                                        SlashCommandOption(
                                            name='mode',
                                            description='quel mode de jeu ?',
                                            type=interactions.OptionType.STRING,
                                            required=False,
                                            choices=[
                                                SlashCommandChoice(name='ranked', value='RANKED'),
                                                SlashCommandChoice(name='aram', value='ARAM'),
                                                SlashCommandChoice(name='swiftplay',value='SWIFTPLAY'),
                                                SlashCommandChoice(name='flex', value='FLEX')]),
                                        SlashCommandOption(
                                            name='view',
                                            description='Global ou serveur ?',
                                            type=interactions.OptionType.STRING,
                                            required=False,
                                            choices=[
                                                SlashCommandChoice(name='global', value='global'),
                                                SlashCommandChoice(name='serveur', value='serveur')
                                            ]
                                        )
                                    ]
    )
    async def date_record(self,
                        ctx: SlashContext,
                        saison: int = saison,
                        mode:str = 'RANKED',
                        view : str = 'global'):
        

        await ctx.defer()

        fichier = await load_data(ctx, view, saison, mode, self.time_mini) 
        
            
        # Sélection ciblée des colonnes
        base_cols = ['match_id', 'id_participant', 'riot_id', 'discord', 'champion', 'datetime']
        if saison == 0:
            base_cols.append('season')

        all_cols = base_cols + self.liste_complete
        fichier = fichier[all_cols]

        fichier.columns = [col.lower() for col in fichier.columns]

        # Typage optimisé
        fichier = fichier.astype({
            'match_id': 'string',
            'id_participant': 'int32',
            'riot_id': 'string',
            'discord': 'string',
            'champion': 'category',
            'datetime': 'datetime64[ns]',
            **{col.lower(): 'float32' for col in self.liste_complete if col.lower() not in ['datetime', 'champion']}
        })

        
       
        df_complet = []

        for stat in self.liste_complete:
            stat_lower = stat.lower()

            # Filtrage selon type de record
            if stat_lower in ['early_baron', 'early_drake', 'l_ecart_gold_min_durant_game']:
                fichier_filtre = fichier[fichier[stat_lower] != 0]
                top_row = fichier_filtre.nsmallest(1, stat_lower)
            elif stat_lower in ['fourth_dragon', 'first_elder', 'first_horde', 'first_double',
                                'first_triple', 'first_quadra', 'first_penta',
                                'first_niveau_max', 'first_blood', 'first_tower_time', 'early_atakhan']:
                fichier_filtre = fichier[fichier[stat_lower] != 999]
                top_row = fichier_filtre.nsmallest(1, stat_lower)
            else:
                fichier_filtre = fichier[fichier[stat_lower] != 0]
                top_row = fichier_filtre.nlargest(1, stat_lower)

            if not top_row.empty:
                top_row = top_row.copy()
                top_row['record'] = stat_lower
                df_complet.append(top_row)

        # Fusion + tri
        df_complet = (
            pd.concat(df_complet, ignore_index=True)
            .sort_values('datetime', ascending=False)
        )

        # Construction rapide du texte
        lines = []
        for _, data in df_complet.iterrows():
            record = data["record"]
            champ = emote_champ_discord.get(data["champion"].capitalize(), data["champion"])
            base = f'{emote_v2.get(record, ":star:")} **{record}** de **{data["riot_id"]}** le **{data["datetime"]}** avec {champ} : **{np.round(data[record],2)}**'
            if saison == 0:
                base += f' (S{data["season"]})'
            lines.append(base)

        txt = '\n'.join(lines)

        paginator = Paginator.create_from_string(self.bot, txt, page_size=2000, timeout=120)
        paginator.default_title = f'Date Records {mode}'
        await paginator.send(ctx)
        
                

def setup(bot):
    Recordslol(bot)
