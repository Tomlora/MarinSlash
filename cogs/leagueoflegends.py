import os
import sys
import aiohttp
import pandas as pd
import warnings
import interactions
from interactions import SlashCommandOption, Extension, SlashContext, listen, slash_command, Task, IntervalTrigger, TimeTrigger
from utils.params import Version, saison
from fonctions.channels_discord import identifier_role_by_name
from fonctions.match import get_id_account_bdd, get_stat_null_rules
from utils.emoji import emote_champ_discord, emote_rank_discord, emote_v2
from fonctions.match import emote_rank_discord, get_list_matchs_with_puuid
from fonctions.api_calls import getRankings
from fonctions.api_moba import test_mobalytics_api
from fonctions.permissions import isOwner_slash
from fonctions.gestion_challenge import challengeslol
from fonctions.autocomplete import autocomplete_riotid
from datetime import datetime
import traceback
import humanize
from asyncio import sleep
from collections import Counter, defaultdict
import re 
from utils.emoji import dict_place
import io 
from PIL import Image
import pickle

from fonctions.gestion_bdd import (lire_bdd,
                                   sauvegarde_bdd,
                                   get_data_bdd,
                                   requete_perso_bdd,
                                   lire_bdd_perso,
                                   get_tag)

from fonctions.match import (matchlol,
                             get_summoner_by_puuid,
                             getId_with_puuid,
                             get_league_by_puuid,
                             get_spectator_data,
                             top_records
                             )

from utils.lol import label_rank, label_tier, dict_rankid
from fonctions.channels_discord import chan_discord, rgb_to_discord


warnings.simplefilter(action='ignore', category=FutureWarning)
pd.options.mode.chained_assignment = None  # default='warn'

import re
from collections import defaultdict, OrderedDict


def summarize_medals(parts):
    """Résumé : groupé par (label, medal), total + noms de stats entre ()"""

    # 🔤 Ordre de priorité pour l'affichage
    CONTEXT_LABELS = OrderedDict([
        (":boom:", "Record"),
        ("<:boss:1333120152983834726>", "Record personnel"),
        ("<:world_emoji:1333120623613841489>", "Record All Time"),
        ("<:trophy_world:1333117173731819520>", "Record All Time Champion")
    ])

    label_order = {label: i for i, label in enumerate(CONTEXT_LABELS.values())}

    summary = defaultdict(lambda: {"count": 0, "stats": set()})

    for part in parts:
        lines = [line.strip() for line in part.split('\n') if line.strip()]
        for line in lines:
            # 🎯 Médaille
            medal_match = re.search(r'(<:medal\d+:\d+>)', line)
            if not medal_match:
                continue
            medal = medal_match.group(1)

            # 🎯 Contexte
            label = "Autre"
            for emote, name in CONTEXT_LABELS.items():
                if emote in line:
                    # label = name
                    label = f'{emote}{name}'
                    break

            # 🎯 Stat name (facultatif)
            stat_match = re.search(r'__(.+?)__', line)
            stat_name = f"__{stat_match.group(1)}__" if stat_match else "__?__"

            # 🔢 Ajout au résumé
            key = (label, medal)
            summary[key]["count"] += 1
            summary[key]["stats"].add(stat_name)

    # ✅ Format final du résumé, trié selon l’ordre du label puis nombre décroissant
    summary_lines = [
        f"{label} {medal} : {data['count']} ({', '.join(sorted(data['stats']))})"
        for (label, medal), data in sorted(
            summary.items(),
            key=lambda x: (
                label_order.get(x[0][0], 999),  # ordre du label
                -x[1]["count"]                  # puis nombre décroissant
            )
        )
    ]

    return "\n".join(summary_lines)


def add_chunked_field(embed, title, parts, max_len=1024, total_limit=4000):
    """Ajoute des champs à un embed Discord, ou un résumé si trop long."""

    total_content = "\n".join(parts).strip()

    if len(total_content) <= total_limit:
        # ✅ Mode normal : découpage en chunks
        current = ""
        index = 1

        for part in parts:
            part = part.strip()
            if not part:
                continue

            if len(part) > max_len:
                part = part[:max_len - 3] + '...'

            if len(current) + len(part) + 1 > max_len:
                embed.add_field(
                    name=title if index == 1 else f"{title} {index}",
                    value=current.strip(),
                    inline=False
                )
                current = ""
                index += 1

            current += part + "\n"

        if current.strip():
            embed.add_field(
                name=title if index == 1 else f"{title} {index}",
                value=current.strip(),
                inline=False
            )

    else:
        # ❗Trop long : résumé global, découpé en blocs de 1024 caractères
        summary = summarize_medals(parts)

        if not summary:
            embed.add_field(
                name=f"{title} (résumé)",
                value="Aucun record trouvé.",
                inline=False
            )
        else:
            lines = summary.split('\n')
            current = ""
            index = 1

            for line in lines:
                if len(current) + len(line) + 1 > max_len:
                    embed.add_field(
                        name=f"{title} (résumé {index})" if index > 1 else f"{title} (résumé)",
                        value=current.strip(),
                        inline=False
                    )
                    current = ""
                    index += 1
                current += line + "\n"

            if current.strip():
                embed.add_field(
                    name=f"{title} (résumé {index})" if index > 1 else f"{title} (résumé)",
                    value=current.strip(),
                    inline=False
                )

    return embed




def records_check3(fichier: pd.DataFrame,
                   fichier_joueur: pd.DataFrame = None,
                   fichier_all: pd.DataFrame = None,
                   category=None,
                   result_category_match=None,
                   methode='max') -> str:
    '''
    Vérifie si le score est dans le top 10 (général, perso, all-time), indique la position
    et le record battu ou égalisé si applicable.
    '''
    embed = ''
    category_exclusion_egalite = [
        'baron', 'herald', 'drake', 'first_double', 'first_triple', 'first_quadra',
        'first_penta', 'first_horde', 'first_niveau_max', 'first_blood',
        'tower', 'inhib', 'first_tower_time', 'LEVEL_UP_10'
    ]

    if result_category_match == 0:
        return embed

    def format_embed(scope_name, scope_name1, top_list):

        record_counts = Counter(str(record) for _, _, record, _ in top_list)


        for idx, (joueur, champion, record, url) in enumerate(top_list):
        # Ignorer si le record apparaît plus de 7 fois
            if record_counts[str(record)] >= 7:
                return ''
            place = idx + 1
            top_emoji = dict_place.get(place, f"TOP {place}")
            champ_emoji = emote_champ_discord.get(champion.capitalize(), 'inconnu')
            cat_emoji = emote_v2.get(category, ':star:')

            if float(result_category_match) == float(record):
                if category not in category_exclusion_egalite:
                    return (
                        f"\n **{scope_name} {top_emoji} {scope_name1} - {cat_emoji}__{category}__ : {result_category_match}**"
                        f" — :military_medal: Égalisation {joueur} {champ_emoji}"
                    )
                else:
                    return (
                        f"\n **{scope_name} {top_emoji} {scope_name1} - {cat_emoji}__{category}__ : {result_category_match}**"
                    )

            if (
                (methode == 'max' and float(result_category_match) > float(record)) or
                (methode == 'min' and float(result_category_match) < float(record))
            ):
                return (
                    f"\n **{scope_name} {top_emoji} {scope_name1} - {cat_emoji}__{category}__ : {result_category_match}**"
                    f" (Ancien : {record} par {joueur} {champ_emoji})"
                )
        return ''


    # TOP 10 Général
    if fichier is not None and fichier.shape[0] > 0:
        top_gen = top_records(fichier, category, methode, identifiant='discord', top_n=10)
        embed += format_embed(":boom:", "Général", top_gen)

    # TOP 10 Personnel
    if isinstance(fichier_joueur, pd.DataFrame) and fichier_joueur.shape[0] > 0:
        top_perso = top_records(fichier_joueur, category, methode, identifiant='riot_id', top_n=3)
        embed += format_embed("<:boss:1333120152983834726>",  "Perso", top_perso)

    # TOP 10 All Time
    if isinstance(fichier_all, pd.DataFrame) and fichier_all.shape[0] > 0 and len(fichier_all['season'].unique()) > 1:
        top_all = top_records(fichier_all, category, methode, identifiant='discord', top_n=10)
        embed += format_embed("<:world_emoji:1333120623613841489>", "All Time", top_all)

    return embed





class LeagueofLegends(Extension):
    def __init__(self, bot):
        self.bot: interactions.Client = bot

    @listen()
    async def on_startup(self):
        self.update.start()
        self.lolsuivi.start()
        self.compte_loading = set()


    async def printInfo(self,
                        id_compte,
                        riot_id,
                        riot_tag,
                        idgames: int,
                        sauvegarder: bool,
                        identifiant_game=None,
                        guild_id: int = 0,
                        me=None,
                        insights: bool = True,
                        affichage=1,
                        check_doublon: bool = True,
                        check_records : bool = True):

        match_info = matchlol(id_compte,
                              riot_id,
                              riot_tag,
                              idgames,
                              identifiant_game=identifiant_game,
                              me=me)  # class

        try:
            self.compte_loading.add(riot_id.lower())
            await match_info.get_data_riot()


            if match_info.thisQId not in [1700, 1820, 1830, 1840, 1900]:  # urf
                await match_info.prepare_data()
                await match_info.prepare_data_moba()
                if not match_info.moba_ok:
                    await match_info.prepare_data_ugg()
            
            # elif match_info.thisQId in [1820, 1830, 1840]:
            #     await match_info.prepare_data_swarm()
            else:
                pass




            def get_match_data(filters: str) -> pd.DataFrame:
                stat_null_rules = get_stat_null_rules()

                # Colonnes max_data_timeline à récupérer
                dynamic_stats = [
                    "abilityHaste", "abilityPower", "armor", "attackDamage", 
                    "currentGold", "healthMax", "magicResist", "movementSpeed"
                ]

                # Colonnes à récupérer
                columns = [
                    "matchs.*", "tracker.riot_id", "tracker.riot_tagline", "tracker.discord"
                ] + [f'max_data_timeline."{stat}"' for stat in dynamic_stats]

                columns += [
                    'data_timeline_palier."CS_20"',
                    'data_timeline_palier."CS_30"',
                    'data_timeline_palier."TOTAL_GOLD_20"',
                    'data_timeline_palier."TOTAL_GOLD_30"',
                    'data_timeline_palier."TOTAL_CS_20"',
                    'data_timeline_palier."TOTAL_CS_30"',
                    'data_timeline_palier."TOTAL_DMG_10"',
                    'data_timeline_palier."TOTAL_DMG_20"',
                    'data_timeline_palier."TOTAL_DMG_30"',
                    'data_timeline_palier."TOTAL_DMG_TAKEN_10"',
                    'data_timeline_palier."TOTAL_DMG_TAKEN_20"',
                    'data_timeline_palier."TOTAL_DMG_TAKEN_30"',
                    'data_timeline_palier."TRADE_EFFICIENCE_10"',
                    'data_timeline_palier."TRADE_EFFICIENCE_20"',
                    'data_timeline_palier."TRADE_EFFICIENCE_30"', 
                    'data_timeline_palier."ASSISTS_10"',
                    'data_timeline_palier."ASSISTS_20"',
                    'data_timeline_palier."ASSISTS_30"',
                    'data_timeline_palier."DEATHS_10"',
                    'data_timeline_palier."DEATHS_20"',
                    'data_timeline_palier."DEATHS_30"',
                    'data_timeline_palier."CHAMPION_KILL_10"',
                    'data_timeline_palier."CHAMPION_KILL_20"',
                    'data_timeline_palier."CHAMPION_KILL_30"',
                    'data_timeline_palier."LEVEL_UP_10"',
                    'data_timeline_palier."LEVEL_UP_20"',
                    'data_timeline_palier."LEVEL_UP_30"',
                    'data_timeline_palier."JGL_20"',
                    'data_timeline_palier."JGL_30"',
                    'data_timeline_palier."WARD_KILL_10"',
                    'data_timeline_palier."WARD_KILL_20"',
                    'data_timeline_palier."WARD_KILL_30"',
                    'data_timeline_palier."WARD_PLACED_10"',
                    'data_timeline_palier."WARD_PLACED_20"',
                    'data_timeline_palier."WARD_PLACED_30"',
                ]

                # Construction de la requête SQL finale (plus de CASE WHEN)
                base_query = f'''
                    SELECT DISTINCT {", ".join(columns)}
                    FROM matchs
                    INNER JOIN tracker ON tracker.id_compte = matchs.joueur
                    LEFT JOIN max_data_timeline 
                        ON matchs.joueur = max_data_timeline.riot_id 
                        AND matchs.match_id = max_data_timeline.match_id
                    LEFT JOIN data_timeline_palier 
                        ON matchs.joueur = data_timeline_palier.riot_id 
                        AND matchs.match_id = data_timeline_palier.match_id
                    WHERE mode = '{match_info.thisQ}'
                    AND server_id = {guild_id}
                    AND tracker.save_records = TRUE
                    AND matchs.records = TRUE
                    {filters}
                '''

                # Chargement des données
                df = lire_bdd_perso(base_query, index_col='id').transpose()

                # Application des règles d'annulation dynamiques
                if 'champion' in df.columns:
                    for col in df.columns:
                        if col == 'champion':
                            continue
                        if col in stat_null_rules:
                            champions = stat_null_rules[col]
                            df.loc[df['champion'].isin(champions), col] = None

                return df



            # Utilisations spécifiques
            fichier = get_match_data(f"AND season = {match_info.season}")
            fichier_all = get_match_data("")  # Pas de filtre saison
            fichier_joueur = get_match_data(f'''
                AND season = {match_info.season}
                AND discord = (SELECT tracker.discord FROM tracker WHERE tracker.id_compte = {id_compte})
            ''')
            # fichier_champion = get_match_data(f'''
            #     AND season = {match_info.season}
            #     AND champion = '{match_info.thisChampName}'
            # ''')
            # fichier_champion_all = get_match_data(f"AND champion = '{match_info.thisChampName}'")

            records_parts = []

            if check_doublon:
                df_doublon = lire_bdd_perso(f'''SELECT match_id, joueur from matchs
                            INNER JOIN tracker ON matchs.joueur = tracker.id_compte
                            WHERE matchs.joueur = (SELECT id_compte WHERE riot_id = '{riot_id.lower()}' and riot_tagline = '{riot_tag.upper()}')
                            AND match_id = '{match_info.last_match}' ''', index_col=None)
                
                if not df_doublon.empty:
                    return {}, 'Doublon', 0,


            if sauvegarder and match_info.thisTime >= 10.0 and match_info.thisQ != 'ARENA 2v2' and match_info.thisQ != 'SWARM' :
                await match_info.save_data()
            else:
                requete_perso_bdd(f'''DELETE from prev_lol WHERE riot_id = '{riot_id.lower()}' and riot_tag = '{riot_tag.upper()}' and match_id = '';
                                    DELETE from prev_lol_features WHERE riot_id = '{riot_id.lower()}' and riot_tag = '{riot_tag.upper()}' and match_id = '' ''')


            # if sauvegarder and match_info.thisQ == 'SWARM':
            #     await match_info.save_data_swarm()
                
            if match_info.thisQ in ['RANKED', 'FLEX', 'SWIFTPLAY'] and match_info.thisTime >= 15:
                await match_info.save_timeline()
                try:
                    await match_info.save_timeline_event()
                except:
                    print('Erreur save timeline event')

            if match_info.thisQId == 900:  # urf
                return {}, 'URF', 0,


            elif match_info.thisQId == 1300:  # urf
                return {}, 'NexusBlitz', 0,
            
            elif match_info.thisQId == 840:
                return {}, 'Bot', 0,   # bot game

            elif match_info.thisTime <= 3.0:
                return {}, 'Remake', 0,



            # Suivi

            suivi = lire_bdd(f'suivi_s{saison}', 'dict')

            try:
                if suivi[id_compte]['tier'] == match_info.thisTier and suivi[id_compte]['rank'] == match_info.thisRank:
                    difLP = int(match_info.thisLP) - \
                            int(suivi[id_compte]['LP'])
                else:
                    if int(match_info.thisLP) < int(suivi[id_compte]['LP']):
                        difLP = (100 - int(suivi[id_compte]['LP'])) + int(match_info.thisLP)
                    else:
                        difLP = (-100 - int(suivi[id_compte]['LP'])) + int(match_info.thisLP)

            except Exception:
                difLP = 0

            difLP = f'+{str(difLP)}' if difLP > 0 else str(difLP)
            if match_info.thisQ == "RANKED":  # si pas ranked, inutile car ça bougera pas

                suivi[id_compte]['wins'] = match_info.thisVictory
                suivi[id_compte]['losses'] = match_info.thisLoose
                suivi[id_compte]['LP'] = match_info.thisLP

            # on ne prend que les ranked > 20 min ou aram > 10 min + Ceux qui veulent checker les records
            if ((match_info.thisQ in ['RANKED', 'FLEX', 'SWIFTPLAY'] and match_info.thisTime >= 15) or (match_info.thisQ == "ARAM" and match_info.thisTime >= 10)) and check_records:

                # pour le nouveau système de records
                param_records = {'kda': match_info.thisKDA,
                                'kp': match_info.thisKP,
                                'cs': match_info.thisMinion,
                                'cs_min': match_info.thisMinionPerMin,
                                'kills': match_info.thisKills,
                                'deaths': match_info.thisDeaths,
                                'assists': match_info.thisAssists,
                                'double': match_info.thisDouble,
                                'triple': match_info.thisTriple,
                                'quadra': match_info.thisQuadra,
                                'penta': match_info.thisPenta,
                                'team_kills': match_info.thisTeamKills,
                                'team_deaths': match_info.thisTeamKillsOp,
                                'time': match_info.thisTime,
                                'dmg': match_info.thisDamageNoFormat,
                                'dmg_ad': match_info.thisDamageADNoFormat,
                                'dmg_ap': match_info.thisDamageAPNoFormat,
                                'dmg_true': match_info.thisDamageTrueNoFormat,
                                'gold': match_info.thisGoldNoFormat,
                                'gold_min': match_info.thisGoldPerMinute,
                                'dmg_min': match_info.thisDamagePerMinute,
                                'solokills': match_info.thisSoloKills,
                                'dmg_reduit': match_info.thisDamageSelfMitigated,
                                'heal_total': match_info.thisTotalHealed,
                                'heal_allies': match_info.thisTotalOnTeammates,
                                'serie_kills': match_info.thisKillingSprees,
                                'cs_dix_min': match_info.thisCSafter10min,
                                'cs_max_avantage': match_info.thisCSAdvantageOnLane,
                                'temps_dead': match_info.thisTimeSpendDead,
                                'damageratio': match_info.thisDamageRatio,
                                'tankratio': match_info.thisDamageTakenRatio,
                                'dmg_tank': match_info.thisDamageTakenNoFormat,
                                'shield': match_info.thisTotalShielded,
                                'allie_feeder': match_info.thisAllieFeeder,
                                'temps_vivant': match_info.thisTimeSpendAlive,
                                'dmg_tower': match_info.thisDamageTurrets,
                                'gold_share': match_info.gold_share,
                                'ecart_gold_team': match_info.ecart_gold_team,
                                'kills+assists': match_info.thisKills + match_info.thisAssists,
                                'temps_avant_premiere_mort' : match_info.thisTimeLiving,
                                'dmg/gold' : match_info.DamageGoldRatio,
                                'skillshot_dodged' : match_info.thisSkillshot_dodged,
                                'temps_cc' : match_info.time_CC,
                                'spells_used' : match_info.thisSpellUsed,
                                'kills_min' : match_info.kills_min,
                                'deaths_min' : match_info.deaths_min,
                                'assists_min' : match_info.assists_min,
                                'crit_dmg' : match_info.largest_crit,
                                'immobilisation' : match_info.enemy_immobilisation,
                                'temps_cc_inflige' : match_info.totaltimeCCdealt,
                                'dmg_true_all' : match_info.thisDamageTrueAllNoFormat,
                                'dmg_true_all_min' : match_info.thisDamageTrueAllPerMinute,
                                'dmg_ad_all' : match_info.thisDamageADAllNoFormat,
                                'dmg_ad_all_min' : match_info.thisDamageADAllPerMinute,
                                'dmg_ap_all' : match_info.thisDamageAPAllNoFormat,
                                'dmg_ap_all_min' : match_info.thisDamageAPAllPerMinute,
                                'dmg_all' : match_info.thisDamageAllNoFormat,
                                'dmg_all_min' : match_info.thisDamageAllPerMinute,
                                'longue_serie_kills' : match_info.thisKillsSeries,
                                'trade_efficience' : match_info.trade_efficience,
                                'skillshots_hit_min' : match_info.thisSkillshot_hit_per_min,
                                'skillshots_dodge_min' : match_info.thisSkillshot_dodged_per_min,
                                'dmg_par_kills' : match_info.damage_per_kills,
                                'killsratio' : match_info.killsratio,
                                'deathsratio' : match_info.deathsratio,
                                'solokillsratio' : match_info.solokillsratio}

                if match_info.thisQ in ['RANKED', 'FLEX', 'SWIFTPLAY']:
                    param_records_only_ranked = {'vision_score': match_info.thisVision,
                                                'vision_wards': match_info.thisWards,
                                                'vision_wards_killed': match_info.thisWardsKilled,
                                                'vision_pink': match_info.thisPink,
                                                'vision_min': match_info.thisVisionPerMin,
                                                'level_max_avantage': match_info.thisLevelAdvantage,
                                                'vision_avantage': match_info.thisVisionAdvantage,
                                                'early_drake': match_info.earliestDrake,
                                                'early_baron': match_info.earliestBaron,
                                                'jgl_dix_min': match_info.thisJUNGLEafter10min,
                                                'baron': match_info.thisBaronTeam,
                                                'drake': match_info.thisDragonTeam,
                                                'petales_sanglants' : match_info.petales_sanglants,
                                                'cs_jungle': match_info.thisJungleMonsterKilled,
                                                'buffs_voles' : match_info.thisbuffsVolees,
                                                'abilityHaste' : match_info.max_abilityHaste,
                                                'abilityPower' : match_info.max_ap,
                                                'armor' : match_info.max_armor,
                                                'attackDamage' : match_info.max_ad,
                                                'currentGold' : match_info.currentgold,
                                                'healthMax' : match_info.max_hp,
                                                'magicResist' : match_info.max_mr,
                                                'movementSpeed' : match_info.movement_speed,
                                                'fourth_dragon' : match_info.timestamp_fourth_dragon,
                                                'first_elder' : match_info.timestamp_first_elder,
                                                'first_horde' : match_info.timestamp_first_horde,
                                                'first_double' : match_info.timestamp_doublekill,
                                                'first_triple' : match_info.timestamp_triplekill,
                                                'first_quadra' : match_info.timestamp_quadrakill,
                                                'first_penta' : match_info.timestamp_pentakill,
                                                'first_niveau_max' : match_info.timestamp_niveau_max,
                                                'first_blood' : match_info.timestamp_first_blood,
                                                'tower' : match_info.thisTowerTeam,
                                                'inhib' : match_info.thisInhibTeam,
                                                'ecart_kills' : match_info.ecart_kills,
                                                'ecart_deaths' : match_info.ecart_morts,
                                                'ecart_assists' : match_info.ecart_assists,
                                                'ecart_dmg' : match_info.ecart_dmg, 
                                                'first_tower_time' : match_info.first_tower_time,
                                                'TOTAL_CS_20' : match_info.total_cs_20,
                                                'TOTAL_CS_30' : match_info.total_cs_30,
                                                'TOTAL_GOLD_20' : match_info.total_gold_20,
                                                'TOTAL_GOLD_30' : match_info.total_gold_30,
                                                'TOTAL_DMG_TAKEN_10' : match_info.totalDamageTaken_10,
                                                'TOTAL_DMG_TAKEN_20' : match_info.totalDamageTaken_20,
                                                'TOTAL_DMG_TAKEN_30' : match_info.totalDamageTaken_30,
                                                'TRADE_EFFICIENCE_10' : match_info.trade_efficience_10,
                                                'TRADE_EFFICIENCE_20' : match_info.trade_efficience_20,
                                                'TRADE_EFFICIENCE_30' : match_info.trade_efficience_30,
                                                'TOTAL_DMG_10' : match_info.totalDamageDone_10,
                                                'TOTAL_DMG_20' : match_info.totalDamageDone_20,
                                                'TOTAL_DMG_30' : match_info.totalDamageDone_30,
                                                'ASSISTS_10' : match_info.assists_10,
                                                'ASSISTS_20' : match_info.assists_20,
                                                'ASSISTS_30' : match_info.assists_30,
                                                'DEATHS_10' : match_info.deaths_10,
                                                'DEATHS_20' : match_info.deaths_20,
                                                'DEATHS_30' : match_info.deaths_30,
                                                'CHAMPION_KILL_10' : match_info.champion_kill_10,
                                                'CHAMPION_KILL_20' : match_info.champion_kill_20,
                                                'CHAMPION_KILL_30' : match_info.champion_kill_30,
                                                'LEVEL_UP_10' : match_info.level_10,
                                                'LEVEL_UP_20' : match_info.level_20,
                                                'LEVEL_UP_30' : match_info.level_30,
                                                'JGL_20' : match_info.jgl_20,
                                                'JGL_30' : match_info.jgl_30,
                                                'WARD_KILL_10' : match_info.WARD_KILL_10,
                                                'WARD_KILL_20' : match_info.WARD_KILL_20,
                                                'WARD_KILL_30' : match_info.WARD_KILL_30,
                                                'WARD_PLACED_10' : match_info.WARD_PLACED_10,
                                                'WARD_PLACED_20' : match_info.WARD_PLACED_20,
                                                'WARD_PLACED_30' : match_info.WARD_PLACED_30}
                else:
                    param_records_only_ranked = {}
                


                param_records_only_aram = {'snowball': match_info.snowball}


                

                for parameter, value in param_records.items():
                    methode = 'min' if parameter in [
                        'early_drake', 'early_baron', 'fourth_dragon', 'first_elder',
                        'first_horde', 'first_double', 'first_triple', 'first_quadra',
                        'first_penta', 'first_niveau_max', 'first_blood', 'first_tower_time'
                    ] else 'max'

                    if parameter == 'kda':
                        if int(match_info.thisDeaths) >= 1:
                            result = records_check3(fichier, fichier_joueur, fichier_all, 'kda', match_info.thisKDA, methode)
                        else:
                            kda_val = float(round((int(match_info.thisKills) + int(match_info.thisAssists)) / (int(match_info.thisDeaths) + 1), 2))
                            result = records_check3(fichier, fichier_joueur, fichier_all, 'kda', kda_val, methode)
                    else:
                        result = records_check3(fichier, fichier_joueur, fichier_all, parameter, value, methode)

                    if result:
                        records_parts.append(result)




                if match_info.thisQ in ['RANKED', 'FLEX', 'SWIFTPLAY']:
                    for parameter, value in param_records_only_ranked.items():
                        methode = 'min' if parameter in [
                            'early_drake', 'early_baron', 'fourth_dragon', 'first_elder',
                            'first_horde', 'first_double', 'first_triple', 'first_quadra',
                            'first_penta', 'first_niveau_max', 'first_blood', 'first_tower_time'
                        ] else 'max'
                        result = records_check3(fichier, fichier_joueur, fichier_all, parameter, value, methode)
                        if result:
                            records_parts.append(result)



                if match_info.thisQ in ['ARAM', 'CLASH ARAM']:
                    for parameter, value in param_records_only_aram.items():
                        methode = 'min' if parameter in [
                            'early_drake', 'early_baron', 'fourth_dragon', 'first_elder',
                            'first_horde', 'first_double', 'first_triple', 'first_quadra',
                            'first_penta', 'first_niveau_max', 'first_blood', 'first_tower_time'
                        ] else 'max'
                        result = records_check3(fichier, fichier_joueur, fichier_all, parameter, value, methode)
                        if result:
                            records_parts.append(result)


            del fichier, fichier_all, fichier_joueur


            try:
            # on le fait après sinon ça flingue les records
                match_info.thisDamageTurrets = "{:,}".format(match_info.thisDamageTurrets).replace(',', ' ').replace('.', ',')
            
            except AttributeError:
                match_info.thisDamageTurrets = 0

            # couleur de l'embed en fonction du pseudo

            data = get_data_bdd(f'SELECT "R", "G", "B" from tracker WHERE id_compte= :id_compte', {
                                'id_compte': id_compte}).fetchall()
            color = rgb_to_discord(data[0][0], data[0][1], data[0][2])

            # constructing the message

            match match_info.thisQ:
                case "OTHER":
                    embed = interactions.Embed(
                        title=f"** {match_info.riot_id.upper()} #{match_info.riot_tag} ** vient de ** {match_info.thisWin} ** une game ", color=color)
                case "PERSO":
                    embed = interactions.Embed(
                        title=f"** {match_info.riot_id.upper()} #{match_info.riot_tag} ** vient de ** {match_info.thisWin} ** une game perso", color=color)
                case "ARAM":
                    embed = interactions.Embed(
                        title=f"** {match_info.riot_id.upper()} #{match_info.riot_tag} ** vient de ** {match_info.thisWin} ** une ARAM ", color=color)
                case "CLASH ARAM":
                    embed = interactions.Embed(
                        title=f"** {match_info.riot_id.upper()} #{match_info.riot_tag} ** vient de ** {match_info.thisWin} ** un CLASH ARAM ", color=color)
                case 'ARENA 2v2':
                    embed = interactions.Embed(
                        title=f"** {match_info.riot_id.upper()} #{match_info.riot_tag} ** vient de terminer ** {match_info.thisWin}ème ** en ARENA ", color=color)
                case 'SWARM':
                    embed = interactions.Embed(
                        title=f"** {match_info.riot_id.upper()} #{match_info.riot_tag} ** vient de {match_info.thisWin} une  SWARM ", color=color)               
                case default:
                    embed = interactions.Embed(
                        title=f"** {match_info.riot_id.upper()} #{match_info.riot_tag} ** vient de ** {match_info.thisWin} ** une {match_info.thisQ} game ({match_info.thisPosition})", color=color)



            sauvegarde_bdd(suivi, f'suivi_s{saison}')  # achievements + suivi       

            # badges

            if insights and match_info.thisQ != 'ARENA 2v2' and match_info.thisQ != 'SWARM':
                await match_info.calcul_badges(sauvegarder)
            else:
                match_info.observations = ''
                
            

            # observations

            # ici, ça va de 1 à 10.. contrairement à Rito qui va de 1 à 9
            embed.add_field(
                name="Game", value=f"[Graph]({match_info.url_game}) | [OPGG](https://euw.op.gg/summoners/euw/{match_info.riot_id.replace(' ', '')}-{match_info.riot_tag}) ", inline=True)

            embed.add_field(
                name='Champion', value=f"[{match_info.thisChampName}](https://lolalytics.com/lol/{match_info.thisChampName.lower()}/build/)", inline=True)



            if not records_parts:
                embed.add_field(name="Exploits", value="Aucun exploit", inline=False)
            else:
                embed = add_chunked_field(embed, "Exploits", records_parts)



            if match_info.thisQ in ['RANKED', 'FLEX']:

                await match_info.traitement_objectif()
                name, txt = await match_info.show_objectifs() 

                if name != None:
                    embed.add_field(name=name, value=txt)

                # Detection joueurs pro 
                await match_info.detection_joueurs_pro()    
                            
                if match_info.observations_proplayers != '':
                    embed.add_field(name=':stadium: Joueurs Pro', value=match_info.observations_proplayers)
                    
                # Detection Smurf
                
                await match_info.detection_smurf()
                    
                if match_info.observations_smurf != '':
                    embed.add_field(name=':muscle: Bons joueurs', value=match_info.observations_smurf)


                # Detection mauvais joueur

                await match_info.detection_mauvais_joueur()

                if match_info.observations_mauvais_joueur != '':
                    embed.add_field(name=':thumbdown: Joueurs nuls', value=match_info.observations_mauvais_joueur) 

                # Detection First Time


                await match_info.detection_first_time()

                if match_info.first_time != '':
                    embed.add_field(name='<:worryschool:1307745643996905519> Débutant', value=match_info.first_time)       

                # OTP
                await match_info.detection_otp()

                if match_info.otp != '':
                    embed.add_field(name=':one: OTP', value=match_info.otp)  

                # Serie
                await match_info.detection_serie_victoire()

                if match_info.serie_victoire != '':
                    embed.add_field(name=':mag: Serie', value=match_info.serie_victoire)
                    
                await match_info.ecart_cs_by_role()
                
                if match_info.ecart_cs_txt != '':
                    embed.add_field(name=':ghost: Ecart CS', value=match_info.ecart_cs_txt )


                # Gap 

                # await match_info.detection_gap()
                # if match_info.txt_gap != '':
                #     embed.add_field(name=f':chart_with_upwards_trend: {match_info.txt_gap}', value=' ')


            if match_info.AFKTeamBool:
                embed.add_field(name=':sleeping: AFK', value=' ')

                # # Detection Participation jgl

                # if match_info.thisTime >= 15:
                #     text_jgl = ''
                #     kills_mini = 3 if match_info.thisPosition in ['TOP', 'MID'] else 4
                #     kills_jgl_early = getattr(match_info, 'kills_with_jgl_early', 0)
                #     morts_jgl_early = getattr(match_info, 'deaths_with_jgl_early', 0)

                #     if kills_jgl_early >= kills_mini:
                #         text_jgl += f':blue_circle: {kills_jgl_early} Kills avec son jgl en early\n'
                #     if morts_jgl_early >= 3:
                #         text_jgl += f':red_circle: {morts_jgl_early} morts par le jgl adverse en early'
                #     if text_jgl != '':
                #         embed.add_field(name=':evergreen_tree: Activité Jungle', value=text_jgl)
                # Insights



            if match_info.observations != '':
                    embed.add_field(name='Insights', value=match_info.observations)
                
            if match_info.observations2 != '':
                    embed.add_field(name='Insights 2', value=match_info.observations2)



                # Gestion de l'image


            embed = await match_info.resume_general('resume', embed, difLP)

        finally:
            self.compte_loading.discard(riot_id.lower())

        # on charge les img

        resume = interactions.File('resume.png')
        embed.set_image(url='attachment://resume.png')

        embed.set_footer(
                text=f'by Tomlora - Match {str(match_info.last_match)}')
        
        match_info.sauvegarde_embed(embed)
        
        return embed, match_info.thisQ, resume

    async def updaterank(self,
                         key,
                         riot_id,
                         riot_tag,
                         discord_server_id : chan_discord,
                         session: aiohttp.ClientSession,
                         puuid,
                         discord_id=None):

        suivirank = lire_bdd(f'suivi_s{saison}', 'dict')

        stats = await get_league_by_puuid(session, puuid)

        if len(stats) > 0: # s'il y a des stats
   
            for j in range(len(stats)):
                if stats[j]['queueType'] == 'RANKED_SOLO_5x5':
                    i = j
                    break

            try:
                tier_old = suivirank[key]['tier'].upper()
                tier = stats[i]['tier'].upper()
                rank_old = f"{suivirank[key]['tier']} {suivirank[key]['rank']}"
                rank = f"{stats[i]['tier']} {stats[i]['rank']}"

                if rank_old != rank:

                    try:
                        channel_tracklol = await self.bot.fetch_channel(discord_server_id.tracklol)
                        if dict_rankid[rank_old] > dict_rankid[rank]:  # 19 > 18
                            await channel_tracklol.send(f'{emote_rank_discord[tier]} Le joueur **{riot_id}** #{riot_tag} a démote du rank **{rank_old}** à **{rank}**')
                            await channel_tracklol.send(files=interactions.File('./img/notstonks.jpg'))
                        elif dict_rankid[rank_old] < dict_rankid[rank]:
                            await channel_tracklol.send(f'{emote_rank_discord[tier]}Le joueur **{riot_id}** #{riot_tag} a été promu du rank **{rank_old}** à **{rank}**')
                            await channel_tracklol.send(files=interactions.File('./img/stonks.jpg'))


                        # Role discord
                        if tier_old != tier:
                            member = await self.bot.fetch_member(discord_id, discord_server_id.server_id)
                            guild = await self.bot.fetch_guild(discord_server_id.server_id)
                            ancien_role = await identifier_role_by_name(guild, tier_old)
                            nouveau_role = await identifier_role_by_name(guild, tier)

                            if ancien_role in member.roles:
                                await member.remove_role(ancien_role)

                            if nouveau_role not in member.roles:
                                await member.add_role(nouveau_role)

                    except Exception:
                        print('Channel impossible')
                        print(sys.exc_info())

                    requete_perso_bdd(f'UPDATE suivi_s{saison} SET tier = :tier, rank = :rank where index = :joueur', {'tier': stats[i]['tier'],
                                                                                                                    'rank': stats[i]['rank'],
                                                                                                                    'joueur': key})
            except UnboundLocalError:
                pass

    @slash_command(name="game",
                   description="Voir les statistiques d'une games",
                   default_member_permissions=interactions.Permissions.MANAGE_GUILD,
                   options=[
                       SlashCommandOption(name="riot_id",
                                          description="Nom du joueur",
                                          type=interactions.OptionType.STRING,
                                            required=True,
                                            autocomplete=True),
                       SlashCommandOption(name="riot_tag",
                                          description="Tag",
                                          type=interactions.OptionType.STRING,
                                          required=False),
                       SlashCommandOption(name="numerogame",
                                          description="Numero de la game, de 0 à 100",
                                          type=interactions.OptionType.INTEGER,
                                          required=False,
                                          min_value=0,
                                          max_value=100),
                       SlashCommandOption(name='identifiant_game',
                                          description="A ne pas utiliser",
                                          type=interactions.OptionType.STRING,
                                          required=False),
                       SlashCommandOption(name='ce_channel',
                                          description='Poster dans ce channel ?',
                                          type=interactions.OptionType.BOOLEAN,
                                          required=False),
                       SlashCommandOption(name='check_doublon',
                                          description='Verifier si la game a déjà été enregistrée ?',
                                          type=interactions.OptionType.BOOLEAN,
                                          required=False)])
    async def game(self,
                   ctx: SlashContext,
                   riot_id: str,
                   riot_tag:str = None,
                   numerogame: int = 0,
                   identifiant_game=None,
                   ce_channel=False,
                   check_doublon=True):

        await ctx.defer(ephemeral=False)

        if riot_tag == None:
            try:
                riot_tag = get_tag(riot_id)
            except ValueError:
                return await ctx.send('Plusieurs comptes avec ce riot_id, merci de préciser le tag')
        
        server_id = int(ctx.guild_id)
        discord_server_id = chan_discord(int(server_id))

        discord_id = int(ctx.author.id)
        riot_id = riot_id.lower().replace(' ', '')
        riot_tag = riot_tag.upper()
        df_banned = lire_bdd_perso(f'''SELECT discord, banned from tracker WHERE discord = '{discord_id}' and banned = true''', index_col='discord')
        
        try:
            check_records = bool(lire_bdd_perso(f'''SELECT riot_id, save_records from tracker WHERE riot_id = '{riot_id}' and riot_tagline = '{riot_tag}' ''', 
                                                index_col='riot_id')\
                                                    .T\
                                                        .loc[riot_id]['save_records'])
            
            if check_records.empty: # cela veut dire que le compte n'a pas été trouvé
                check_records = False
        except:
            check_records = False
        
        if df_banned.empty:
            try:
                id_compte = get_id_account_bdd(riot_id, riot_tag)
            except IndexError:
                return await ctx.send("Ce compte n'existe pas ou n'est pas enregistré")
            embed, mode_de_jeu, resume = await self.printInfo(id_compte,
                                                            riot_id,
                                                            riot_tag,
                                                            idgames=numerogame,
                                                            sauvegarder=True,
                                                            identifiant_game=identifiant_game,
                                                            guild_id=int(ctx.guild_id),
                                                            affichage=1,
                                                            check_doublon=check_doublon,
                                                            check_records=check_records)
            
            if not ce_channel:
                if mode_de_jeu in ['RANKED', 'FLEX']:
                    tracklol = discord_server_id.tracklol
                
                elif mode_de_jeu == 'ARENA 2v2':
                    tracklol = discord_server_id.tft
                else:
                    tracklol = discord_server_id.lol_others

                channel_tracklol = await self.bot.fetch_channel(tracklol)
                
                await ctx.delete()
            else:
                channel_tracklol = ctx


            if embed != {}:                
                await channel_tracklol.send(embeds=embed, files=resume)
                os.remove('resume.png')
        else:
            await ctx.send("Tu n'as pas l'autorisation d'utiliser cette commande.")

    
    @game.autocomplete("riot_id")

    async def autocomplete_game(self, ctx: interactions.AutocompleteContext):

        liste_choix = await autocomplete_riotid(int(ctx.guild.id), ctx.input_text)

        await ctx.send(choices=liste_choix)


    @slash_command(name="game_rattrapage",
                   description="Rattrape les games oubliées",
                #    default_member_permissions=interactions.Permissions.MANAGE_GUILD,
                   options=[
                       SlashCommandOption(name="riot_id",
                                          description="Nom du joueur",
                                          type=interactions.OptionType.STRING,
                                            required=True,
                                            autocomplete=True),
                       SlashCommandOption(name="riot_tag",
                                          description="Tag",
                                          type=interactions.OptionType.STRING,
                                           required=False),
                       SlashCommandOption(name="attente",
                                          description="Attente entre 2 games",
                                          type=interactions.OptionType.INTEGER,
                                          required=False,
                                          min_value=45,
                                          max_value=100)])
    async def game_multi(self,
                   ctx: SlashContext,
                   riot_id: str,
                   riot_tag:str = None,
                   attente:int = 45):

        await ctx.defer(ephemeral=False)

        if riot_id.lower() in self.compte_loading:
            return await ctx.send("Une partie est déjà en cours de chargement pour ce joueur. Veuillez patienter.")
        
        if riot_tag == None:
            try:
                riot_tag = get_tag(riot_id)
            except ValueError:
                return await ctx.send('Plusieurs comptes avec ce riot_id, merci de préciser le tag')
                
        server_id = int(ctx.guild_id)
        discord_server_id = chan_discord(int(server_id))

        discord_id = int(ctx.author.id)
        riot_id = riot_id.lower().replace(' ', '')
        riot_tag = riot_tag.upper()
        df_banned = lire_bdd_perso(f'''SELECT discord, banned from tracker WHERE discord = '{discord_id}' and banned = true''', index_col='discord')
        data_joueur = lire_bdd_perso(f'''SELECT riot_id, puuid, id_compte from tracker WHERE riot_id = '{riot_id}' and riot_tagline = '{riot_tag}' ''', 
                                                index_col='riot_id')

        puuid = data_joueur.T.loc[riot_id]['puuid']
        id_compte = data_joueur.T.loc[riot_id]['id_compte']
        
        try:
            check_records = bool(lire_bdd_perso(f'''SELECT riot_id, save_records, from tracker WHERE riot_id = '{riot_id}' and riot_tagline = '{riot_tag}' ''', 
                                                index_col='riot_id')\
                                                    .T\
                                                        .loc[riot_id]['save_records'])
            
            if check_records.empty: # cela veut dire que le compte n'a pas été trouvé
                check_records = True
        except:
            check_records = True
        
        if df_banned.empty:
            try:
                id_compte = get_id_account_bdd(riot_id, riot_tag)
            except IndexError:
                return await ctx.send("Ce compte n'existe pas ou n'est pas enregistré")
            
            session = aiohttp.ClientSession()
            liste_matchs_riot : list = await get_list_matchs_with_puuid(session, puuid)
            await session.close()
            liste_matchs_save : pd.DataFrame = lire_bdd_perso(f'''SELECT distinct match_id from matchs where joueur = {id_compte}''', index_col=None).T

            matchs_manquants = pd.Series(liste_matchs_riot)[~pd.Series(liste_matchs_riot).isin(liste_matchs_save['match_id'].tolist())].tolist()


            if len(matchs_manquants) == 0:
                return await ctx.send("Aucune game à afficher")
            else:
                matchs_manquants.reverse() # ancienne à la plus récente
                msg = await ctx.send(f"Il y a {len(matchs_manquants)} games à charger : {matchs_manquants}.")

            
            for num, game in enumerate(matchs_manquants):

                await msg.edit(content=f"Il y a {len(matchs_manquants)} games à charger : {matchs_manquants} : Game {game} en cours... ({num+1}/{len(matchs_manquants)})")
                try:
                    embed, mode_de_jeu, resume = await self.printInfo(id_compte,
                                                                    riot_id,
                                                                    riot_tag,
                                                                    idgames=0,
                                                                    sauvegarder=True,
                                                                    identifiant_game=game,
                                                                    guild_id=int(ctx.guild_id),
                                                                    affichage=1,
                                                                    check_doublon=True,
                                                                    check_records=check_records)
                    

                    if mode_de_jeu in ['RANKED', 'FLEX']:
                        tracklol = discord_server_id.tracklol
                        
                    elif mode_de_jeu == 'ARENA 2v2':
                        tracklol = discord_server_id.tft
                    else:
                        tracklol = discord_server_id.lol_others

                    channel_tracklol = await self.bot.fetch_channel(tracklol)
                        
                        


                    if embed != {}:                
                        await channel_tracklol.send(embeds=embed, files=resume)
                        os.remove('resume.png')

                    

                except Exception:
                    print(f"erreur {riot_id}")  # joueur qui a posé pb
                    exc_type, exc_value, exc_traceback = sys.exc_info()
                    traceback_details = traceback.format_exception(exc_type, exc_value, exc_traceback)
                    traceback_msg = ''.join(traceback_details)
                    print(traceback_msg)
                    await ctx.send(f'Erreur game {game}')
                    continue

                await sleep(attente)
            
            await msg.delete()
            # await ctx.delete()

        else:
            await ctx.send("Tu n'as pas l'autorisation d'utiliser cette commande.")


    @game_multi.autocomplete("riot_id")
    async def autocomplete_multigame(self, ctx: interactions.AutocompleteContext):

        liste_choix = await autocomplete_riotid(int(ctx.guild.id), ctx.input_text)

        await ctx.send(choices=liste_choix)

    async def printLive(self,
                        id_compte,
                        riot_id,
                        riot_tag,
                        discord_server_id: chan_discord,
                        me=None,
                        identifiant_game=None,
                        tracker_challenges=False,
                        session=None,
                        insights=True,
                        nbchallenges=0,
                        banned=False,
                        check_records=True):


        embed, mode_de_jeu, resume = await self.printInfo(id_compte,
                                                          riot_id,
                                                          riot_tag,
                                                          idgames=0,
                                                          sauvegarder=True,
                                                          guild_id=discord_server_id.server_id,
                                                          identifiant_game=identifiant_game,
                                                          me=me,
                                                          insights=insights,
                                                          affichage=1,
                                                          check_records=check_records)

        if tracker_challenges:
            chal = challengeslol(id_compte, me['puuid'], session, nb_challenges=nbchallenges)
            await chal.preparation_data()
            await chal.comparaison()


            embed = await chal.embedding_discord(embed)

        if not banned:
            if mode_de_jeu in ['RANKED', 'FLEX']:
                tracklol = discord_server_id.tracklol
            
            elif mode_de_jeu == 'ARENA 2v2':
                tracklol = discord_server_id.tft
            else:
                tracklol = discord_server_id.lol_others

            channel_tracklol = await self.bot.fetch_channel(tracklol)

            if embed != {}:
                await channel_tracklol.send(embeds=embed, files=resume)
                os.remove('resume.png')

                if tracker_challenges:
                    await chal.sauvegarde()
        else:            
            try:
                os.remove('resume.png')
            except:
                pass
                
            

    @Task.create(IntervalTrigger(minutes=3))
    async def update(self):
        data = get_data_bdd(
            '''SELECT tracker.id_compte, tracker.riot_id, tracker.riot_tagline, tracker.id, tracker.server_id,
            tracker.spec_tracker, tracker.spec_send, tracker.discord, tracker.puuid, tracker.challenges,
            tracker.insights, tracker.nb_challenges, tracker.affichage,
            tracker.banned, tracker.riot_id, tracker.riot_tagline, tracker.save_records
                            from tracker 
                            INNER JOIN channels_module on tracker.server_id = channels_module.server_id
                            where tracker.activation = true
                            and channels_module.league_ranked = true'''
        ).fetchall()
        timeout = aiohttp.ClientTimeout(total=60*5)
        session = aiohttp.ClientSession(timeout=timeout)

        for id_compte, riot_id, riot_tag, last_game, server_id, tracker_bool, tracker_spec, discord_id, puuid, tracker_challenges, insights, nb_challenges, affichage, banned, riot_id, riot_tagline, check_records in data:

            id_last_game = await getId_with_puuid(puuid, session)

            if str(last_game) != id_last_game:
                # update la bdd

                requete_perso_bdd(
                    'UPDATE tracker SET id = :id, spec_send = :spec WHERE id_compte = :id_compte',
                    {'id': id_last_game, 'id_compte': id_compte, 'spec': False})

                try:
                    me = await get_summoner_by_puuid(puuid, session)
                        
                        # si maj pseudo ou tag
                    if riot_id != me['gameName'].replace(" ", "").lower() or riot_tag != me['tagLine']:
                        requete_perso_bdd(
                                'UPDATE tracker SET riot_id = :riot_id, riot_tagline = :riot_tag WHERE id_compte = :id_compte',
                                {'id_compte': id_compte, 'riot_id': me['gameName'].lower().replace(" ", ""), 'riot_tag': me['tagLine'].upper()},
                            )
                            
                        riot_id = me['gameName'].lower().replace(" ", "")
                        riot_tag = me['tagLine'].upper()

                except KeyError:
                    print(f'Erreur de maj de pseudo {riot_id}')
                    requete_perso_bdd(
                        'UPDATE tracker SET id = :id WHERE id_compte = :id_compte',
                        {'id': last_game, 'id_compte': id_compte})
                    continue             

                try:
                    # identification du channel
                    discord_server_id = chan_discord(int(server_id))

                    # résumé de game

                    await self.printLive(id_compte,
                                        riot_id,
                                         riot_tag,
                                         discord_server_id,
                                         me,
                                         identifiant_game=id_last_game,
                                         tracker_challenges=tracker_challenges,
                                         session=session,
                                         insights=insights,
                                         nbchallenges=nb_challenges,
                                         banned=banned,
                                         check_records=check_records)

                    # update rank
                    await self.updaterank(id_compte, riot_id, riot_tag,  discord_server_id, session, puuid, discord_id)
                except TypeError:
                    # on recommence dans 1 minute
                    requete_perso_bdd(
                        'UPDATE tracker SET id = :id WHERE id_compte = :id_compte',
                        {'id': last_game, 'id_compte': id_compte})
                    # joueur qui a posé pb
                    print(f"erreur TypeError {riot_id}")
                    exc_type, exc_value, exc_traceback = sys.exc_info()
                    traceback_details = traceback.format_exception(exc_type, exc_value, exc_traceback)
                    traceback_msg = ''.join(traceback_details)
                    print(traceback_msg)
                    continue
                except Exception:
                    print(f"erreur {riot_id}")  # joueur qui a posé pb
                    exc_type, exc_value, exc_traceback = sys.exc_info()
                    traceback_details = traceback.format_exception(exc_type, exc_value, exc_traceback)
                    traceback_msg = ''.join(traceback_details)
                    print(traceback_msg)
                    continue

            if tracker_bool and not tracker_spec:
                try:
                    url, gamemode, id_game, champ_joueur, icon = await get_spectator_data(puuid, session)

                    url_opgg = f'https://www.op.gg/summoners/euw/{riot_id.replace(" ", "")}-{riot_tagline}/ingame'

                    league_of_graph = f'https://porofessor.gg/fr/live/euw/{riot_id.replace(" ", "")}-{riot_tagline}'

                    if url != None:

                        member = await self.bot.fetch_member(discord_id, server_id)

                        if id_last_game != str(id_game):
                            embed = interactions.Embed(
                                title=f'{riot_id.upper()} : Analyse de la game prête !')

                            embed.add_field(name='Mode de jeu', value=gamemode)

                            embed.add_field(
                                name='OPGG', value=f"[General]({url_opgg}) | [Detail]({url}) ")
                            embed.add_field(
                                name='League of Graph', value=f"[{riot_id.upper()}]({league_of_graph})")
                            embed.add_field(
                                name='Lolalytics', value=f'[{champ_joueur.capitalize()}](https://lolalytics.com/lol/{champ_joueur}/build/)')
                            embed.set_thumbnail(url=icon)

                            await member.send(embeds=embed)

                            requete_perso_bdd(
                                'UPDATE tracker SET spec_send = :spec WHERE id_compte = :id_compte',
                                {'spec': True, 'id_compte': id_compte},
                            )
                except TypeError:
                    continue
                except Exception:
                    continue
        await session.close()


    


    async def update_24h(self):
        data = get_data_bdd(
            '''SELECT DISTINCT tracker.server_id from tracker 
                    INNER JOIN channels_module on tracker.server_id = channels_module.server_id
                    where channels_module.league_ranked = true and tracker.banned = false'''
        ).fetchall()

        params = lire_bdd_perso('select * from settings',
                                format='dict',
                                index_col='parametres')

        saison = int(params['saison']['value'])
        
        session = aiohttp.ClientSession()

        for server_id in data:

            guild = await self.bot.fetch_guild(server_id[0])

            chan_discord_id = chan_discord(int(guild.id))


            # le suivi est déjà maj par game/update... Pas besoin de le refaire ici..

            df = lire_bdd_perso(f'''SELECT tracker.id_compte, tracker.riot_id, tracker.riot_tagline, suivi.wins, suivi.losses, suivi."LP", suivi.tier, suivi.rank, suivi.wins_jour, suivi.losses_jour, suivi."LP_jour", suivi.tier_jour, suivi.rank_jour, suivi.classement_euw, suivi.classement_percent_euw, tracker.server_id from suivi_s{saison} as suivi
                                    INNER join tracker ON tracker.id_compte = suivi.index
                                    where suivi.tier != 'Non-classe'
                                    and tracker.server_id = {int(guild.id)}
                                    and tracker.banned = false
                                    and tracker.activation = true ''',
                                    index_col='id_compte')

            if df.shape[1] > 0:  # si pas de data, inutile de continuer

                df = df.transpose().reset_index()
                # df_24h = df_24h.transpose().reset_index()

                # Pour l'ordre de passage
                df['tier_pts'] = df['tier'].apply(label_tier)
                df['rank_pts'] = df['rank'].apply(label_rank)

                df['LP_pts'] = df['LP'].astype(int)

                df.sort_values(by=['tier_pts', 'rank_pts', 'LP_pts'],
                               ascending=[False, False, False],
                               inplace=True)
                


                sql = ''

                suivi = df.set_index(['id_compte']).transpose().to_dict()
                # suivi_24h = df_24h.set_index('index').transpose().to_dict()

                joueur = suivi.keys()

                embed = interactions.Embed(
                    title="Suivi LOL", description='Periode : 24h', color=interactions.Color.random())
                totalwin = 0
                totaldef = 0
                totalgames = 0
                
                for key in joueur:

                    # suivi est mis à jour par update et updaterank. On va donc prendre le comparer à suivi24h
                    wins = int(suivi[key]['wins_jour'])
                    losses = int(suivi[key]['losses_jour'])
                    nbgames = wins + losses
                    LP = int(suivi[key]['LP_jour'])
                    tier_old = str(suivi[key]['tier_jour'])
                    rank_old = str(suivi[key]['rank_jour'])
                    classement_old = f"{tier_old} {rank_old}"
                    
                    rank_euw_old = suivi[key]['classement_euw']
                    percent_rank_old = suivi[key]['classement_percent_euw']

                    # on veut les stats soloq

                    tier = str(suivi[key]['tier'])
                    rank = str(suivi[key]['rank'])
                    classement_new = f"{tier} {rank}"

                    difwins = int(suivi[key]['wins']) - wins
                    diflosses = int(suivi[key]['losses']) - losses
                    difLP = int(suivi[key]['LP']) - LP
                    totalwin = totalwin + difwins
                    totaldef = totaldef + diflosses
                    totalgames = totalwin + totaldef
                    
                    # Ranking EUW
                    # try:
                    #     success = await update_ugg(session, suivi[key]['riot_id'], suivi[key]['riot_tagline'])
                    # except:
                    #     pass
                    attempts = 0
                    try:
                        while attempts < 5: # max 5 tentatives
                            stats_rankings = await getRankings(session, suivi[key]['riot_id'], suivi[key]['riot_tagline'], 'euw1', saison, 420)
                        
                            if stats_rankings != 'Service indisponible':
                                break
                            else:
                                attempts += 1

                        if stats_rankings == 'Service indisponible': # si c'est toujours le cas...
                            rank_euw = rank_euw_old
                            percent_rank_euw = percent_rank_old
                        else:
                            rank_euw = stats_rankings['data']['overallRanking']['overallRanking']
                            percent_rank_euw = int(round(stats_rankings['data']['overallRanking']['overallRanking'] / stats_rankings['data']['overallRanking']['totalPlayerCount'] * 100,0))
                    except TypeError:
                        rank_euw = rank_euw_old
                        percent_rank_euw = percent_rank_old
                    
                    if rank_euw_old == 0:
                        rank_euw_old = rank_euw

                    diff_rank_euw = rank_euw - rank_euw_old
                    
                    if diff_rank_euw > 0:
                        diff_rank_euw = f"+{humanize.intcomma(int(diff_rank_euw)).replace(',', ' ')}"
                    else:
                        try:
                            diff_rank_euw = f"{humanize.intcomma(int(diff_rank_euw)).replace(',', ' ')}"
                        except ValueError:
                            diff_rank_euw = f"{0}"

                    try:    
                        rank_euw_format = humanize.intcomma(int(rank_euw)).replace(',', ' ')
                    except ValueError:
                        rank_euw_format = "0"
                        rank_euw = 0
                        percent_rank_euw = 0

                    # evolution

                    if dict_rankid[classement_old] > dict_rankid[classement_new]:  # 19-18
                        difrank = dict_rankid[classement_old] - dict_rankid[classement_new]
                        # si la personne vient de commencer ces classés, il n'a pas une multiple promotion
                        if classement_old == "Non-classe 0":
                            difrank = 0
                        if classement_old not in [
                            'MASTER I',
                            'GRANDMASTER I',
                            'CHALLENGER I',
                        ]: 
                            # il n'y a pas -100 lp pour ce type de démote
                            difLP = (100 * difrank) + LP - int(suivi[key]['LP'])
                        difLP = f"Démote (x{difrank}) / -{str(difLP)}  "
                        emote = ":arrow_down:"

                    elif dict_rankid[classement_old] < dict_rankid[classement_new]:
                        difrank = dict_rankid[classement_new] - dict_rankid[classement_old]

                        if classement_old not in [
                            'MASTER I',
                            'GRANDMASTER I',
                            'CHALLENGER I',
                        ]:


                            # si la personne vient de commencer ces classés, il n'a pas une multiple promotion
                            if classement_old == "Non-classe 0":
                                difrank = 0
                            difLP = (100 * difrank) - LP + int(suivi[key]['LP'])
                        difLP = f"Promotion (x{difrank}) / +{str(difLP)} "
                        emote = "<:frogUp:1205933878540238868>"

                    elif dict_rankid[classement_old] == dict_rankid[classement_new]:
                        if difLP > 0:
                            emote = "<:frogUp:1205933878540238868>"
                            difLP = f'+{difLP}'
                        elif difLP < 0:
                            emote = ":arrow_down:"
                        elif difLP == 0:
                            emote = ":arrow_right:"

                    embed.add_field(
                        name=f"{suivi[key]['riot_id']}#{suivi[key]['riot_tagline']} ( {emote_rank_discord[tier]} {rank} ) #{rank_euw_format}({diff_rank_euw}) | {percent_rank_euw}%",
                        value=f"V : {suivi[key]['wins']} ({difwins}) | D : {suivi[key]['losses']} ({diflosses}) | LP :  {suivi[key]['LP']} ({difLP})   {emote}", inline=False)
                    
                    if (difwins + diflosses > 0):  # si supérieur à 0, le joueur a joué
                        sql += f'''UPDATE suivi_s{saison}
                            SET wins_jour = {suivi[key]['wins']},
                            losses_jour = {suivi[key]['losses']},
                            "LP_jour" = {suivi[key]['LP']},
                            tier_jour = '{suivi[key]['tier']}',
                            rank_jour = '{suivi[key]['rank']}'
                            where index = '{key}';'''
                            
                    sql+= f'''UPDATE suivi_s{saison}
                            SET classement_euw = {rank_euw},
                            classement_percent_euw = {percent_rank_euw}
                            where index = '{key}';''' 

                channel_tracklol = await self.bot.fetch_channel(chan_discord_id.tracklol)

                embed.set_footer(text=f'Version {Version} by Tomlora')
                
                
                await session.close()

                if sql != '':  # si vide, pas de requête
                    requete_perso_bdd(sql)

                if totalgames > 0:  # s'il n'y a pas de game, on ne va pas afficher le récap
                    
                    attempts = 0 
                    
                    while attempts < 5:
                        try:
                            await channel_tracklol.send(content=f'Sur {totalgames} games -> {totalwin} victoires et {totaldef} défaites.', 
                                                        embeds=embed)
                            break
                        except:
                            attempts += 1
                            await sleep(5)


                
                df_journalier = lire_bdd_perso(f'''select index, wins, losses, "LP", tier, rank, classement_euw from suivi_s{saison} where tier != 'Non-classe' ''', index_col=None).T

                date = datetime.now()
                df_journalier['datetime'] = pd.to_datetime(f'{date.day}/{date.month}/{date.year}', format='%d/%m/%Y')
                df_journalier['classement_euw'] = df_journalier['classement_euw'].astype(int)
                df_journalier['saison'] = saison

                sauvegarde_bdd(df_journalier, 'suivi_rank', 'append', index=False)

                ### Faire graphique

    @Task.create(TimeTrigger(hour=6))
    async def lolsuivi(self):

        await self.update_24h()

    @slash_command(name="force_update24h",
                   default_member_permissions=interactions.Permissions.MANAGE_GUILD)
    async def force_update(self, ctx: SlashContext):

        await ctx.defer(ephemeral=False)

        if isOwner_slash(ctx):
            await self.update_24h()
            # await ctx.delete()

        else:
            await ctx.send("Tu n'as pas l'autorisation nécessaire")



    @slash_command(name="test_api_moba",
                                    description="Teste l'APi Mobalytics",
                                    default_member_permissions=interactions.Permissions.MANAGE_GUILD)
    async def test_api_m(self,
                        ctx: SlashContext):
        


        await ctx.defer(ephemeral=False)

        resp = await test_mobalytics_api()

        await ctx.send(f"{resp}")


    @slash_command(name='chargement_ancienne_game',
                   description='Charger des stats ancienne game')
    async def chargement_ancienne_game(self, ctx: SlashContext):  
        pass  

    @chargement_ancienne_game.subcommand('image',
                   sub_cmd_description="Charger le résumé d'une partie",
                   options=[
                       SlashCommandOption(name="match_id",
                                          description="Id du match EUW1...",
                                          type=interactions.OptionType.STRING,
                                            required=True)])
    async def load_resume(self, ctx: SlashContext, match_id):

        await ctx.defer()
        
        
        data = lire_bdd_perso(f'''SELECT * from match_images where match_id = '{match_id}' ''', index_col='match_id').T
        image_bytes = data['image'].values[0]
        image : Image.Image = Image.open(io.BytesIO(image_bytes))
        
        image.save('resume_save.png')
        
        await ctx.send(file='resume_save.png')
        
        os.remove('resume_save.png')

    @chargement_ancienne_game.subcommand('resume_complet',
                   sub_cmd_description="Charger le résumé d'une partie",
                   options=[
                       SlashCommandOption(name="match_id",
                                          description="Id du match EUW1...",
                                          type=interactions.OptionType.STRING,
                                            required=True)])
    async def load_embed(self, ctx: SlashContext, match_id):
        
        
        await ctx.defer()

        data = lire_bdd_perso(f'''SELECT match_embed.match_id, match_images.image, match_embed.joueur, match_embed.data from match_embed
                              inner join match_images on match_embed.match_id = match_images.match_id
                              where match_embed.match_id = '{match_id}' and match_images.match_id = '{match_id}' ''', index_col='match_id').T
        
        data_binary = data['data'].values[0]
        
        original_embed = pickle.loads(data_binary)
        
        image_bytes = data['image'].values[0]
        image : Image.Image = Image.open(io.BytesIO(image_bytes))
        
        image.save('resume_save.png')
        
        resume = interactions.File('resume_save.png')
        original_embed.set_image(url='attachment://resume_save.png')
        
        await ctx.send(embeds=original_embed, files=resume)
        os.remove('resume_save.png')
        

        
        

def setup(bot):
    LeagueofLegends(bot)
