import os
import sys
import aiohttp
import pandas as pd
import warnings
import interactions
from interactions import SlashCommandOption, Extension, SlashContext, SlashCommandChoice, listen, slash_command, Task, IntervalTrigger, TimeTrigger
from fonctions.params import Version, saison
from fonctions.channels_discord import identifier_role_by_name
from fonctions.match import trouver_records, get_version, emote_champ_discord, get_id_account_bdd
from fonctions.match import emote_rank_discord, emote_champ_discord, fix_temps
from fonctions.api_calls import getRankings
from cogs.recordslol import emote_v2
from fonctions.permissions import isOwner_slash
from fonctions.gestion_challenge import challengeslol
from datetime import datetime, timedelta
from dateutil import tz
from interactions.ext.paginators import Paginator
import traceback
import ast
import humanize
from asyncio import sleep

from fonctions.gestion_bdd import (lire_bdd,
                                   sauvegarde_bdd,
                                   get_data_bdd,
                                   requete_perso_bdd,
                                   lire_bdd_perso)

from fonctions.match import (matchlol,
                             get_summoner_by_puuid,
                             getId_with_puuid,
                             dict_rankid,
                             get_league_by_summoner,
                             trouver_records,
                             label_rank,
                             label_tier,
                             get_spectator_data
                             )
from fonctions.channels_discord import chan_discord, rgb_to_discord


warnings.simplefilter(action='ignore', category=FutureWarning)
pd.options.mode.chained_assignment = None  # default='warn'


def records_check2(fichier,
                   fichier_joueur=None,
                   fichier_champion=None,
                   category=None,
                   result_category_match=None,
                   methode='max') -> str:
    '''Cherche s'il y a un record :
    - Dans un premier temps, parmi tous les joueurs.
    - Dans un second temps, parmi les stats du joueur.
    None à la place du fichier pour désactiver un check.                                                                                                                                 
    '''
    embed = ''
    category_exclusion_egalite = ['baron', 'herald', 'drake', 'first_double', 'first_triple', 'first_quadra', 'first_penta', 'first_horde', 'first_niveau_max', 'first_blood']

    if result_category_match == 0:  # si le score est de 0, inutile
        return embed

    # Record sur tous les joueurs
    if fichier.shape[0] > 0:  # s'il y a des données, sinon first record
        joueur, champion, record, url = trouver_records(
            fichier, category, methode, identifiant='discord')

        if (
            methode == 'max'
            and float(record) < float(result_category_match)
            or methode != 'max'
            and float(record) > float(result_category_match)
        ):
            embed += f"\n ** :boom: Record - {emote_v2.get(category, ':star:')}__{category}__ : {result_category_match} ** (Ancien : {record} par {joueur} {emote_champ_discord.get(champion.capitalize(), 'inconnu')})"
        if (
            float(record) == float(result_category_match)
            and category not in category_exclusion_egalite
        ):  # si égalité
            embed += f"\n ** :medal: Egalisation record - {emote_v2.get(category, ':star:')}__{category}__ de {joueur} **"
    else:
        embed += f"\n ** :boom: Premier Record - {emote_v2.get(category, ':star:')}__{category}__ : {result_category_match} **"

    # Record sur ses stats personnels
    if isinstance(fichier_joueur, pd.DataFrame) and fichier_joueur.shape[0] > 0:
        joueur_perso, champion_perso, record_perso, url = trouver_records(
            fichier_joueur, category, methode)
    
        if (
            methode == 'max'
            and float(record_perso) < float(result_category_match)
            or methode != 'max'
            and float(record_perso) > float(result_category_match)
        ):
            embed += f"\n ** :military_medal: Record personnel - {emote_v2.get(category, ':star:')}__{category.lower()}__ : {result_category_match} ** (Ancien : {record_perso})"
        if (
            float(record_perso) == float(result_category_match)
            and category not in category_exclusion_egalite
        ):
            embed += f"\n ** :medal: Egalisation record personnel - {emote_v2.get(category, ':star:')}__{category}__ **"

    # Record sur les champions
    if isinstance(fichier_champion, pd.DataFrame) and fichier_champion.shape[0] > 0:
        joueur_champion, champion_champion, record_champion, url = trouver_records(
            fichier_champion, category, methode, identifiant='discord')
    
        if (
            methode == 'max'
            and float(record_champion) < float(result_category_match)
            or methode != 'max'
            and float(record_champion) > float(result_category_match)
        ):
            embed += f"\n ** :rocket: Record sur {emote_champ_discord.get(champion_champion.capitalize(), 'inconnu')} - {emote_v2.get(category, ':star:')}__{category.lower()}__ : {result_category_match} ** (Ancien : {record_champion} par {joueur_champion})"

    return embed


class LeagueofLegends(Extension):
    def __init__(self, bot):
        self.bot: interactions.Client = bot

    @listen()
    async def on_startup(self):
        self.update.start()
        self.lolsuivi.start()

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

        await match_info.get_data_riot()


        if match_info.thisQId not in [1700, 1820, 1830, 1840, 1900]:  # urf
            await match_info.prepare_data()
            await match_info.prepare_data_moba()
            await match_info.prepare_data_ugg()
        
        elif match_info.thisQId in [1820, 1830, 1840]:
            await match_info.prepare_data_swarm()
        else:
            pass


        # pour nouveau système de record
        fichier = lire_bdd_perso(f'''SELECT distinct matchs.*, tracker.riot_id, tracker.riot_tagline, tracker.discord, 
                                 max_data_timeline."abilityHaste" AS "abilityHaste",
                                max_data_timeline."abilityPower" AS "abilityPower",
                                max_data_timeline.armor AS armor,
                                max_data_timeline."attackDamage" AS "attackDamage",
                                max_data_timeline."currentGold" AS "currentGold",
                                max_data_timeline."healthMax" AS "healthMax",
                                max_data_timeline."magicResist" AS "magicResist",
                                max_data_timeline."movementSpeed" AS "movementSpeed"
                                 
                                 from matchs
                         INNER JOIN tracker ON tracker.id_compte = matchs.joueur
                         LEFT JOIN max_data_timeline ON matchs.joueur = max_data_timeline.riot_id and matchs.match_id = max_data_timeline.match_id
                         where season = {match_info.season}
                         and mode = '{match_info.thisQ}'
                         and server_id = {guild_id}
                         and tracker.save_records = True ''',
                                 index_col='id'
                                 ).transpose()

        fichier_joueur = lire_bdd_perso(f'''SELECT distinct matchs.*, tracker.riot_id, tracker.riot_tagline, tracker.discord,
                                        max_data_timeline."abilityHaste" AS "abilityHaste",
                                        max_data_timeline."abilityPower" AS "abilityPower",
                                        max_data_timeline.armor AS armor,
                                        max_data_timeline."attackDamage" AS "attackDamage",
                                        max_data_timeline."currentGold" AS "currentGold",
                                        max_data_timeline."healthMax" AS "healthMax",
                                        max_data_timeline."magicResist" AS "magicResist",
                                        max_data_timeline."movementSpeed" AS "movementSpeed"
                                        
                                        from matchs
                                        INNER JOIN tracker on tracker.id_compte = matchs.joueur
                                        LEFT JOIN max_data_timeline ON matchs.joueur = max_data_timeline.riot_id and matchs.match_id = max_data_timeline.match_id
                                        where season = {match_info.season}
                                        and mode = '{match_info.thisQ}'
                                        and discord = (SELECT tracker.discord from tracker WHERE tracker.id_compte = {id_compte})
                                        and server_id = {guild_id}
                                        and tracker.save_records = True ''',
                                        index_col='id',
                                        ).transpose()

        fichier_champion = lire_bdd_perso(f'''SELECT distinct matchs.*, tracker.riot_id, tracker.riot_tagline, tracker.discord,
                                        max_data_timeline."abilityHaste" AS "abilityHaste",
                                        max_data_timeline."abilityPower" AS "abilityPower",
                                        max_data_timeline.armor AS armor,
                                        max_data_timeline."attackDamage" AS "attackDamage",
                                        max_data_timeline."currentGold" AS "currentGold",
                                        max_data_timeline."healthMax" AS "healthMax",
                                        max_data_timeline."magicResist" AS "magicResist",
                                        max_data_timeline."movementSpeed" AS "movementSpeed"
                                        from matchs
                                          INNER JOIN tracker on tracker.id_compte = matchs.joueur
                                          LEFT JOIN max_data_timeline ON matchs.joueur = max_data_timeline.riot_id and matchs.match_id = max_data_timeline.match_id
                                        where season = {match_info.season}
                                        and mode = '{match_info.thisQ}'
                                        and champion = '{match_info.thisChampName}'
                                        and server_id = {guild_id}
                                        and tracker.save_records = True ''',
                                          index_col='id',
                                          ).transpose()


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
            requete_perso_bdd(f'''DELETE from prev_lol WHERE riot_id = '{riot_id.lower()}' and riot_tag = '{riot_tag.upper()}' and match_id = '' ''')


        if sauvegarder and match_info.thisQ == 'SWARM':
            await match_info.save_data_swarm()
            
        if match_info.thisQ in ['RANKED', 'FLEX'] and match_info.thisTime > 20:
            await match_info.save_timeline()
            await match_info.save_timeline_event()

        if match_info.thisQId == 900:  # urf
            return {}, 'URF', 0,


        elif match_info.thisQId == 1300:  # urf
            return {}, 'NexusBlitz', 0,
        
        elif match_info.thisQId == 840:
            return {}, 'Bot', 0,   # bot game

        elif match_info.thisTime <= 3.0:
            return {}, 'Remake', 0,



        exploits = ''

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
        if ((match_info.thisQ in ['RANKED', 'FLEX'] and match_info.thisTime > 20) or (match_info.thisQ == "ARAM" and match_info.thisTime > 10)) and check_records:

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
                             'assists_min' : match_info.assists_min}
            

            if match_info.thisQ in ['RANKED', 'FLEX']:
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
                                            # 'fourth_dragon' : match_info.timestamp_fourth_dragon,
                                            'first_elder' : match_info.timestamp_first_elder,
                                            'first_horde' : match_info.timestamp_first_horde,
                                            'first_double' : match_info.timestamp_doublekill,
                                            'first_triple' : match_info.timestamp_triplekill,
                                            'first_quadra' : match_info.timestamp_quadrakill,
                                            'first_penta' : match_info.timestamp_pentakill,
                                            'first_niveau_max' : match_info.timestamp_niveau_max,
                                            'first_blood' : match_info.timestamp_first_blood}
            else:
                param_records_only_ranked = {}
            


            param_records_only_aram = {'snowball': match_info.snowball}

            # nouveau système de records
            chunk = 1
            chunk_size = 700

            def check_chunk(exploits, chunk, chunk_size):
                '''Détection pour passer à l'embed suivant'''
                if len(exploits) >= chunk * chunk_size:
                    # Detection pour passer à l'embed suivant
                    chunk += 1
                    exploits += '#'
                return exploits, chunk

            for parameter, value in param_records.items():
                # on ajoute les conditions

                exploits, chunk = check_chunk(exploits, chunk, chunk_size)

                if parameter == 'kda':
                    # on ne peut pas comparer à un perfect kda
                    if int(match_info.thisDeaths) >= 1:
                        exploits += records_check2(fichier, fichier_joueur,
                                                   fichier_champion, 'kda', match_info.thisKDA)
                    else:
                        exploits += records_check2(fichier, fichier_joueur, fichier_champion, 'kda', float(
                            round((int(match_info.thisKills) + int(match_info.thisAssists)) / (int(match_info.thisDeaths) + 1), 2)))
                else:
                    exploits += records_check2(fichier, fichier_joueur,
                                               fichier_champion, parameter, value)

            if match_info.thisQ in ['RANKED', 'FLEX']:  # seulement en ranked
                for parameter, value in param_records_only_ranked.items():

                    exploits, chunk = check_chunk(exploits, chunk, chunk_size)

                    methode = 'max'

                    # si ce sont ces deux records, on veut le plus petit résultat
                    if parameter in ['early_drake', 'early_baron', 'fourth_dragon', 'first_elder', 'first_horde', 'first_double', 'first_triple', 'first_quadra', 'first_penta', 'first_niveau_max', 'first_blood']:
                        methode = 'min'

                    # on ne veut pas les records par champion sur ces stats.
                    if parameter in ['baron', 'drake', 'herald']:
                        exploits += records_check2(fichier, fichier_joueur,
                                                   None, parameter, value, methode)
                    else:
                        exploits += records_check2(fichier, fichier_joueur,
                                                   fichier_champion, parameter, value, methode)

            if match_info.thisQ in ['ARAM', 'CLASH ARAM']:  # seulement en aram
                for parameter, value in param_records_only_aram.items():

                    exploits, chunk = check_chunk(exploits, chunk, chunk_size)

                    methode = 'max'

                    exploits += records_check2(fichier, fichier_joueur,
                                               fichier_champion, parameter, value, methode)

        try:
        # on le fait après sinon ça flingue les records
            match_info.thisDamageTurrets = "{:,}".format(
                match_info.thisDamageTurrets).replace(',', ' ').replace('.', ',')
        
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


                if sauvegarder:
                # Série de victoire
                    if match_info.thisWinStreak == "True" and match_info.thisQ == "RANKED" and match_info.thisTime >= 15:
                        # si égal à 0, le joueur commence une série avec 3 wins
                        if suivi[id_compte]["serie"] == 0:
                            suivi[id_compte]["serie"] = 3
                        else:  # si pas égal à 0, la série a déjà commencé
                            suivi[id_compte]["serie"] = suivi[id_compte]["serie"] + 1

                        serie_victoire = round(
                            suivi[id_compte]["serie"], 0)

                        exploits = exploits + \
                                f"\n ** :fire: Série de victoire avec {serie_victoire} victoires**"

                    elif match_info.thisWinStreak == "False" and match_info.thisQ == "RANKED":  # si pas de série en soloq
                        suivi[id_compte]["serie"] = 0
                        serie_victoire = 0
                    else:
                        serie_victoire = 0

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

        # on va chercher les stats du joueur:

        time = 10 if match_info.thisQ == 'ARAM' else 15
        stats_joueur_saison = lire_bdd_perso(f'''SELECT tracker.id_compte, avg(kills) as kills, avg(deaths) as deaths, avg(assists) as assists, 
                    (count(victoire) filter (where victoire = True)) as victoire,
                    avg(kp) as kp,
                    count(victoire) as nb_games,
                    (avg(mvp) filter (where mvp != 0)) as mvp
                    from matchs
                    INNER JOIN tracker on matchs.joueur = tracker.id_compte
                    WHERE tracker.id_compte = {id_compte}
                    and champion = '{match_info.thisChampName}'
                    and season = {saison}
                    and mode = '{match_info.thisQ}'
                    and time > {time}
                    GROUP BY tracker.id_compte''', index_col='id_compte').transpose()
        
        stats_joueur_split = lire_bdd_perso(f'''SELECT tracker.id_compte, avg(kills) as kills, avg(deaths) as deaths, avg(assists) as assists, 
                    (count(victoire) filter (where victoire = True)) as victoire,
                    avg(kp) as kp,
                    count(victoire) as nb_games,
                    (avg(mvp) filter (where mvp != 0)) as mvp
                    from matchs
                    INNER JOIN tracker on matchs.joueur = tracker.id_compte
                    WHERE tracker.id_compte = {id_compte}
                    and champion = '{match_info.thisChampName}'
                    and season = {saison}
                    and mode = '{match_info.thisQ}'
                    and time > {time}
                    and split = {match_info.split}
                    GROUP BY tracker.id_compte''', index_col='id_compte').transpose()

        def stats_joueur(df, embed, id_compte, titre, inline=True):

            k = round(
                df.loc[id_compte, 'kills'], 1)
            d = round(
                df.loc[id_compte, 'deaths'], 1)
            a = round(
                df.loc[id_compte, 'assists'], 1)
            kp = int(df.loc[id_compte, 'kp'])
            
            try:
                mvp = round(
                    df.loc[id_compte, 'mvp'], 1)
            except TypeError:
                mvp = 0
            ratio_victoire = int((df.loc[id_compte, 'victoire'] / df.loc[id_compte, 'nb_games'])*100)
            nb_games = int(
                df.loc[id_compte, 'nb_games'])
            
            if mvp == 0:
                embed.add_field(
                    name=f"{titre} : {nb_games} P ({ratio_victoire}% V)", value=f"{k} / {d} / {a} ({kp}% KP)", inline=inline)
            else:
                embed.add_field(
                    name=f"{titre} : {nb_games} P ({ratio_victoire}% V) | {mvp} MVP ", value=f"{k} / {d} / {a} ({kp}% KP)", inline=inline)
                
            return embed 

        if not stats_joueur_saison.empty and match_info.split != 1:
            embed = stats_joueur(stats_joueur_saison, embed, id_compte, 'Saison', False)
        
        if not stats_joueur_split.empty:
            embed = stats_joueur(stats_joueur_split, embed, id_compte, 'Split')



        # on découpe le texte embed
        chunk_size = 1024
        max_len = 4000

        if exploits == '':  # si l'exploit est vide, il n'y a aucun exploit
            embed.add_field(
                name=f":timer: {str(int(match_info.thisTime))} minutes",
                value=f'Aucun exploit',
                inline=False,
            )

        elif len(exploits) <= chunk_size:
            exploits = exploits.replace('#', '').replace(' #', '')
            embed.add_field(
                name=f":timer: {str(int(match_info.thisTime))} minutes",
                value=exploits,
                inline=False,
            )

        elif len(exploits) > max_len or ((len(embed) + len(exploits)) > 5000):
            records_emoji = {':boom:': 0, ':medal:': 0,
                             ':military_medal:': 0, ':rocket:': 0}

            # on compte par emoji
            for emoji in records_emoji:
                records_emoji[emoji] = exploits.count(emoji)

            # on show
            exploits = ':star: __ Wow ! __ : \n'
            for emoji, count in records_emoji.items():
                if count > 0:
                    if emoji == ':rocket:':
                        exploits += f'{emoji} Tu as battu **{count}** records sur {match_info.thisChampName} \n'
                    elif emoji == ':medal:':
                        exploits += f'{emoji} Tu as égalé **{count}** records généraux ou personnels \n'
                    elif emoji == ':military_medal:':
                        exploits += f'{emoji} Tu as battu **{count}** records personnels \n'
                    else:
                        exploits += f'{emoji} Tu as battu **{count}** records \n'

            embed.add_field(
                name=f':timer: {int(match_info.thisTime)} minutes', value=exploits)

        else:  # si l'embed nécessite plusieurs fields, et est inférieur à la longueur max de l'embed
            exploits = exploits.split('#')  # on split sur notre mot clé

            for i in range(len(exploits)):
                field_name = (
                    f":timer: {str(int(match_info.thisTime))} minutes"
                    if i == 0
                    else f"Records {i + 1}"
                )
                field_value = exploits[i]
                # parfois la découpe renvoie un espace vide.
                if not field_value in ['', ' ']:
                    embed.add_field(name=field_name,
                                    value=field_value, inline=False)
         
        

        if match_info.thisQ != 'ARENA 2v2' and match_info.thisQ != 'SWARM':

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

            if match_info.thisQ != 'ARAM':
                await match_info.detection_first_time()

                if match_info.first_time != '':
                    embed.add_field(name='<:worryschool:1307745643996905519> Débutant', value=match_info.first_time)       

            # OTP
            await match_info.detection_otp()

            if match_info.otp != '':
                embed.add_field(name=':one: OTP', value=match_info.otp)         

            # Insights
            
            if match_info.observations != '':
                embed.add_field(name='Insights', value=match_info.observations)
            
            if match_info.observations2 != '':
                embed.add_field(name='Insights 2', value=match_info.observations2)

            # Gestion de l'image

            if affichage == 1:
                embed = await match_info.resume_general('resume', embed, difLP)


        elif match_info.thisQ == 'SWARM':
            embed.add_field(name='Augment', value=match_info.descriptionAugment)
            embed.add_field(name='Level', value=f'{match_info.thisLevel}')
            embed = await match_info.resume_swarm('resume', embed)

        else:
            pass

        # on charge les img

        resume = interactions.File('resume.png')
        embed.set_image(url='attachment://resume.png')

        embed.set_footer(
                text=f'by Tomlora - Match {str(match_info.last_match)}')
        
        return embed, match_info.thisQ, resume

    async def updaterank(self,
                         key,
                         riot_id,
                         riot_tag,
                         discord_server_id : chan_discord,
                         session: aiohttp.ClientSession,
                         me,
                         discord_id=None):

        suivirank = lire_bdd(f'suivi_s{saison}', 'dict')

        stats = await get_league_by_summoner(session, me)

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
                                          type=interactions.OptionType.STRING, required=True),
                       SlashCommandOption(name="riot_tag",
                                          description="Tag",
                                          type=interactions.OptionType.STRING, required=True),
                       SlashCommandOption(name="numerogame",
                                          description="Numero de la game, de 0 à 100",
                                          type=interactions.OptionType.INTEGER,
                                          required=True,
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
                   riot_tag:str,
                   numerogame: int,
                   identifiant_game=None,
                   ce_channel=False,
                   check_doublon=True):

        await ctx.defer(ephemeral=False)
        
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
                check_records = True
        except:
            check_records = True
        
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
                                                            guild_id=int(
                                                                ctx.guild_id),
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


    @slash_command(name="game_multi",
                   description="Voir les statistiques de plusieurs games",
                   default_member_permissions=interactions.Permissions.MANAGE_GUILD,
                   options=[
                       SlashCommandOption(name="riot_id",
                                          description="Nom du joueur",
                                          type=interactions.OptionType.STRING, required=True),
                       SlashCommandOption(name="riot_tag",
                                          description="Tag",
                                          type=interactions.OptionType.STRING, required=True),
                       SlashCommandOption(name="numero_avant",
                                          description="Numero de la game, de 0 à 100",
                                          type=interactions.OptionType.INTEGER,
                                          required=True,
                                          min_value=0,
                                          max_value=100),
                       SlashCommandOption(name="numero_apres",
                                          description="Numero de la game, de 0 à 100",
                                          type=interactions.OptionType.INTEGER,
                                          required=True,
                                          min_value=0,
                                          max_value=100),
                       SlashCommandOption(name="attente",
                                          description="Attente entre 2 games",
                                          type=interactions.OptionType.INTEGER,
                                          required=False,
                                          min_value=30,
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
    async def game_multi(self,
                   ctx: SlashContext,
                   riot_id: str,
                   riot_tag:str,
                   numero_avant: int,
                   numero_apres: int,
                   attente:int = 30,
                   identifiant_game=None,
                   ce_channel=False,
                   check_doublon=True):

        await ctx.defer(ephemeral=False)
        
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
                check_records = True
        except:
            check_records = True
        
        if df_banned.empty:
            try:
                id_compte = get_id_account_bdd(riot_id, riot_tag)
            except IndexError:
                return await ctx.send("Ce compte n'existe pas ou n'est pas enregistré")
            
            for numero in range(numero_avant, numero_apres):
                try:
                    embed, mode_de_jeu, resume = await self.printInfo(id_compte,
                                                                    riot_id,
                                                                    riot_tag,
                                                                    idgames=numero,
                                                                    sauvegarder=True,
                                                                    identifiant_game=identifiant_game,
                                                                    guild_id=int(
                                                                        ctx.guild_id),
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
                        
                        
                    else:
                        channel_tracklol = ctx


                    if embed != {}:                
                        await channel_tracklol.send(embeds=embed, files=resume)
                        os.remove('resume.png')
                
                except Exception:
                    print(f"erreur {riot_id}")  # joueur qui a posé pb
                    exc_type, exc_value, exc_traceback = sys.exc_info()
                    traceback_details = traceback.format_exception(exc_type, exc_value, exc_traceback)
                    traceback_msg = ''.join(traceback_details)
                    print(traceback_msg)
                    await ctx.send(f'Erreur game {numero}')
                    continue

                await sleep(attente)
            
            await ctx.delete()

        else:
            await ctx.send("Tu n'as pas l'autorisation d'utiliser cette commande.")



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
                
            

    @Task.create(IntervalTrigger(minutes=2))
    async def update(self):
        data = get_data_bdd(
            '''SELECT tracker.id_compte, tracker.riot_id, tracker.riot_tagline, tracker.id, tracker.server_id,
            tracker.spec_tracker, tracker.spec_send, tracker.discord, tracker.puuid, tracker.challenges,
            tracker.insights, tracker.nb_challenges, tracker.affichage,
            tracker.banned, tracker.riot_id, tracker.riot_tagline, tracker.id_league, tracker.save_records
                            from tracker 
                            INNER JOIN channels_module on tracker.server_id = channels_module.server_id
                            where tracker.activation = true
                            and channels_module.league_ranked = true'''
        ).fetchall()
        timeout = aiohttp.ClientTimeout(total=60*5)
        session = aiohttp.ClientSession(timeout=timeout)

        for id_compte, riot_id, riot_tag, last_game, server_id, tracker_bool, tracker_spec, discord_id, puuid, tracker_challenges, insights, nb_challenges, affichage, banned, riot_id, riot_tagline, id_league, check_records in data:

            id_last_game = await getId_with_puuid(puuid, session)

            if str(last_game) != id_last_game:
                # update la bdd

                requete_perso_bdd(
                    'UPDATE tracker SET id = :id, spec_send = :spec WHERE id_compte = :id_compte',
                    {'id': id_last_game, 'id_compte': id_compte, 'spec': False},
                )

                me = await get_summoner_by_puuid(puuid, session)
                
                # si maj pseudo ou tag
                if riot_id != me['gameName'].replace(" ", "").lower() or riot_tag != me['tagLine']:
                    requete_perso_bdd(
                        'UPDATE tracker SET riot_id = :riot_id, riot_tagline = :riot_tag WHERE id_compte = :id_compte',
                        {'id_compte': id_compte, 'riot_id': me['gameName'].lower().replace(" ", ""), 'riot_tag': me['tagLine'].upper()},
                    )
                    
                    riot_id = me['gameName'].lower().replace(" ", "")
                    riot_tag = me['tagLine'].upper()                    

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
                    await self.updaterank(id_compte, riot_id, riot_tag,  discord_server_id, session, id_league, discord_id)
                except TypeError:
                    # on recommence dans 1 minute
                    requete_perso_bdd(
                        'UPDATE tracker SET id = :id WHERE id_compte = :id_compte',
                        {'id': last_game, 'id_compte': id_compte},
                    )
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


    @slash_command(name='lol_list',
                   description='Affiche la liste des joueurs suivis',
                   options=[SlashCommandOption(name='season',
                                               description='14 pour le split en cours, 14_numero split pour un split terminé. Les splits commencent en S14',
                                               type=interactions.OptionType.STRING,
                                               required=False),
                       SlashCommandOption(name='serveur_only',
                                      description='General ou serveur ?',
                                      type=interactions.OptionType.BOOLEAN,
                                      required=False)])
    async def lollist(self,
                      ctx: SlashContext,
                      season : str = saison,
                      serveur_only: bool = False):

        if serveur_only:
            df = lire_bdd_perso(f'''SELECT tracker.riot_id, tracker.riot_tagline, suivi.wins, suivi.losses, suivi."LP", suivi.tier, suivi.rank, tracker.server_id from suivi_s{season} as suivi
                                        INNER join tracker ON tracker.id_compte = suivi.index
                                        where suivi.tier != 'Non-classe' and tracker.activation = true
                                        and tracker.server_id = {int(ctx.guild.id)}
                                        and tracker.banned = false ''', index_col='riot_id')

        else:
            df = lire_bdd_perso(f'''SELECT tracker.riot_id, tracker.riot_tagline, suivi.wins, suivi.losses, suivi."LP", suivi.tier, suivi.rank, tracker.server_id from suivi_s{season} as suivi
                                        INNER join tracker ON tracker.id_compte = suivi.index
                                        where suivi.tier != 'Non-classe' and tracker.activation = true 
                                        and tracker.banned = false ''', index_col='riot_id')
        df = df.transpose().reset_index()

        # Pour l'ordre de passage
        df['tier_pts'] = df['tier'].apply(label_tier)
        df['rank_pts'] = df['rank'].apply(label_rank)

        df['winrate'] = round(df['wins'].astype(int) / (df['wins'].astype(int) + df['losses'].astype(int)) * 100, 1)

        df['nb_games'] = df['wins'].astype(int) + df['losses'].astype(int)

        df.sort_values(by=['tier_pts', 'rank_pts', 'LP'],
                                    ascending=[False, False, False],
                                    inplace=True)

        response = ''.join(
            f'''**{data['riot_id']} #{data['riot_tagline']}** : {emote_rank_discord[data['tier']]} {data['rank']} | {data['LP']} LP | {data['winrate']}% WR\n'''
            for lig, data in df.iterrows())

        
        paginator = Paginator.create_from_string(self.bot, response, page_size=3000, timeout=60)

        paginator.default_title = f'Live feed list Split {season}'
        await paginator.send(ctx)
        # await ctx.send(embeds=embed)

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

                df.sort_values(by=['tier_pts', 'rank_pts', 'LP'],
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

                        
                    rank_euw_format = humanize.intcomma(int(rank_euw)).replace(',', ' ')

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
                        elif difLP < 0:
                            emote = ":arrow_down:"
                        elif difLP == 0:
                            emote = ":arrow_right:"

                    embed.add_field(
                        name=f"{suivi[key]['riot_id']} ( {emote_rank_discord[tier]} {rank} ) #{rank_euw_format}({diff_rank_euw}) | {percent_rank_euw}%",
                        value=f"V : {suivi[key]['wins']} ({difwins}) | D : {suivi[key]['losses']} ({diflosses}) | LP :  {suivi[key]['LP']}({difLP})   {emote}", inline=False)
                    
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
                    await channel_tracklol.send(embeds=embed)
                    await channel_tracklol.send(f'Sur {totalgames} games -> {totalwin} victoires et {totaldef} défaites.')

    @Task.create(TimeTrigger(hour=4))
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






    @slash_command(name='recap',
                   description='Mon recap sur un laps de temps',
                   options=[
                       SlashCommandOption(
                           name='riot_id',
                           description='pseudo lol',
                           type=interactions.OptionType.STRING,
                           required=True),
                       SlashCommandOption(
                           name='riot_tag',
                           description='tag',
                           type=interactions.OptionType.STRING,
                           required=True),
                       SlashCommandOption(
                           name='mode',
                           description='mode de jeu',
                           type=interactions.OptionType.STRING,
                           required=False,
                           choices=[
                               SlashCommandChoice(name='Ranked',
                                                  value='RANKED'),
                               SlashCommandChoice(name='Aram', value='ARAM')]
                       ),
                       SlashCommandOption(
                           name='observation',
                           description='Quelle vision ?',
                           type=interactions.OptionType.STRING,
                           required=False,
                           choices=[
                               SlashCommandChoice(
                                   name='24h', value='24h'),
                               SlashCommandChoice(
                                   name='48h', value='48h'),
                               SlashCommandChoice(
                                   name='72h', value='72h'),
                               SlashCommandChoice(
                                   name='96h', value='96h'),
                               SlashCommandChoice(
                                   name='Semaine', value='Semaine'),
                               SlashCommandChoice(
                                   name='Mois', value='Mois'),
                               SlashCommandChoice(
                                   name="Aujourd'hui", value='today')
                           ]
                       )])
    async def my_recap(self,
                       ctx: SlashContext,
                       riot_id: str,
                       riot_tag: str,
                       mode: str = None,
                       observation: str = '24h'):


        timezone = tz.gettz('Europe/Paris')

        dict_timedelta = {'24h': timedelta(days=1),
                          '48h': timedelta(days=2),
                          '72h': timedelta(days=3),
                          '96h': timedelta(days=4),
                          'Semaine': timedelta(days=7),
                          'Mois': timedelta(days=30)}

        await ctx.defer(ephemeral=False)
        
        riot_tag = riot_tag.upper()

        if mode is None:
            df = (
                lire_bdd_perso(
                    f'''SELECT matchs.id, match_id, champion, id_participant, mvp, time, kills, deaths, assists, quadra, penta, tier, rank, mode, kp, kda, victoire, ecart_lp, ecart_gold, datetime from matchs
                        INNER JOIN tracker on tracker.id_compte = matchs.joueur
                                   where datetime >= :date
                                   and tracker.riot_id ='{riot_id.lower().replace(" ", "")}' 
                                   and tracker.riot_tagline = '{riot_tag}' ''',
                    params={
                        'date': datetime.now(timezone)
                        - dict_timedelta.get(observation)
                    },
                    index_col='id',
                ).transpose()
                if observation != 'today'
                else lire_bdd_perso(
                    f'''SELECT matchs.id, match_id, id_participant, champion, mvp, time, kills, deaths, assists, quadra, penta, tier, rank, mode, kp, kda, victoire, ecart_lp, ecart_gold, datetime from matchs
                        INNER JOIN tracker on tracker.id_compte = matchs.joueur
                                where EXTRACT(DAY FROM datetime) = :jour
                                AND EXTRACT(MONTH FROM datetime) = :mois
                                AND EXTRACT(YEAR FROM datetime) = :annee
                                and tracker.riot_id ='{riot_id.lower().replace(" ", "")}' 
                                and tracker.riot_tagline = '{riot_tag}' ''',
                    params={
                        'jour': datetime.now(timezone).day,
                        'mois': datetime.now(timezone).month,
                        'annee': datetime.now(timezone).year,
                    },
                    index_col='id',
                ).transpose()
            )
        elif observation != 'today':
            df = lire_bdd_perso(f'''SELECT matchs.id, match_id, id_participant, champion, mvp, time, kills, deaths, assists, quadra, penta, tier, rank, mode, kp, victoire, kda, ecart_lp, ecart_gold, datetime from matchs
                                   INNER JOIN tracker on tracker.id_compte = matchs.joueur
                                   where datetime >= :date
                                and tracker.riot_id ='{riot_id.lower().replace(" ", "")}' 
                                and tracker.riot_tagline = '{riot_tag}'
                                   and mode = '{mode}' ''',
                                params={'date': datetime.now(
                                    timezone) - dict_timedelta.get(observation)},
                                index_col='id').transpose()

        else:

            df = lire_bdd_perso(f'''SELECT matchs.id, match_id, id_participant, champion, mvp, time, kills, deaths, assists, quadra, penta, tier, rank, mode, kp, victoire, kda, ecart_lp, ecart_gold, datetime from matchs
                                INNER JOIN tracker on tracker.id_compte = matchs.joueur
                                where EXTRACT(DAY FROM datetime) = :jour
                                AND EXTRACT(MONTH FROM datetime) = :mois
                                AND EXTRACT(YEAR FROM datetime) = :annee
                                and tracker.riot_id ='{riot_id.lower().replace(" ", "")}' 
                                and tracker.riot_tagline = '{riot_tag}'
                                and mode = '{mode}' ''',
                                params={'jour': datetime.now(timezone).day,
                                        'mois': datetime.now(timezone).month,
                                        'annee': datetime.now(timezone).year},
                                index_col='id').transpose()

        if df.shape[0] >= 1:

            # on convertit dans le bon fuseau horaire
            df['datetime'] = pd.to_datetime(
                df['datetime'], utc=True).dt.tz_convert('Europe/Paris')

            df.sort_values(by='datetime', ascending=False, inplace=True)

            df['datetime'] = df['datetime'].dt.strftime('%d/%m %H:%M')

            df['victoire'] = df['victoire'].map(
                {True: 'Victoire', False: 'Défaite'})

            # Total
            total_kda = f'Total : **{df["kills"].sum()}**/**{df["deaths"].sum()}**/**{df["assists"].sum()}**  | Moyenne : **{df["kills"].mean():.2f}**/**{df["deaths"].mean():.2f}**/**{df["assists"].mean():.1f}** (**{df["kda"].mean():.2f}**) | KP : **{df["kp"].mean():.2f}**% '
            total_lp = f'**{df["ecart_lp"].sum()}**'

            # Serie de kills
            total_quadra = df['quadra'].sum()
            total_penta = df['penta'].sum()

            # Moyenne
            duree_moyenne = df['time'].mean()
            mvp_moyenne = df['mvp'].mean()

            # Victoire
            nb_victoire_total = df['victoire'].value_counts().get(
                'Victoire', 0)
            nb_defaite_total = df['victoire'].value_counts().get('Défaite', 0)

            total_victoire = f'Victoire : **{nb_victoire_total}** | Défaite : **{nb_defaite_total}** '

            champion_counts = df['champion'].sort_values(
                ascending=False).value_counts()
            txt_champ = ''.join(
                f'{emote_champ_discord.get(champ.capitalize(), "inconnu")} : **{number}** | '
                for champ, number in champion_counts.items()
            )
            # On prépare l'embed
            data = get_data_bdd(
                'SELECT "R", "G", "B" from tracker WHERE riot_id = :riot_id and riot_tagline = :riot_tag',
                {'riot_id': riot_id.lower().replace(' ', ''), 'riot_tag' : riot_tag},
            ).fetchall()

            # On crée l'embed
            embed = interactions.Embed(
                title=f" Recap **{riot_id.upper()} # {riot_tag} ** {observation.upper()}", color=interactions.Color.from_rgb(data[0][0], data[0][1], data[0][2]))

            txt = ''
            n = 1
            count = 0
            part = 1
            embeds = []
            
            emote_status_match = {'Victoire' : ':green_circle:', 'Défaite' : ':red_circle:'}
            
           
            
            # On affiche les résultats des matchs
            
            for index, match in df.iterrows():
                rank_img = emote_rank_discord[match["tier"]]
                champ_img = emote_champ_discord.get(match["champion"].capitalize(), 'inconnu')
                txt += f'[{match["datetime"]}](https://www.leagueofgraphs.com/fr/match/euw/{str(match["match_id"])[5:]}#participant{int(match["id_participant"])+1}) {champ_img} [{match["mode"]} | {rank_img} {match["rank"]}] | {emote_status_match[match["victoire"]]} | MVP **{match["mvp"]}** | KDA : **{match["kills"]}**/**{match["deaths"]}**/**{match["assists"]}** ({match["kp"]}%) | **{match["ecart_lp"]}** | G : {match["ecart_gold"]} \n'

                if embed.fields and len(txt) + sum(len(field.value) for field in embed.fields) > 4000:
                    embed.add_field(name='KDA', value=total_kda)
                    embed.add_field(name='Champions', value=txt_champ)
                    embed.add_field(
                        name='Ratio', value=f'{total_victoire} ({nb_victoire_total/(nb_victoire_total+nb_defaite_total)*100:.2f}%) | LP {total_lp}')
                    embed.add_field(
                        name='Autres', value=f'Durée moyenne : **{duree_moyenne:.0f}**m | MVP : **{mvp_moyenne:.1f}**')
                
                    if (total_quadra + total_penta) > 0:
                        embed.add_field(
                            name='Série', value=f'Quadra : **{total_quadra}** | Penta : **{total_penta}**')
                
                    embeds.append(embed)
                    embed = interactions.Embed(
                        title=f" Recap **{riot_id.upper()} #{riot_tag} ** {observation.upper()} Part {part}", color=interactions.Color.from_rgb(data[0][0], data[0][1], data[0][2]))
                    part = part + 1

                # Vérifier si l'index est un multiple de 8
                if count % 3 == 0 and count != 0:

                    if n == 1:
                        embed.add_field(
                            name=f'Historique ({df.shape[0]} parties)', value=txt)
                    else:
                        embed.add_field(name='Historique (suite)', value=txt)
                    n = n+1
                    txt = ''

                count = count + 1

            # Vérifier si la variable txt contient des données non ajoutées
            if txt:
                embed.add_field(name='Historique (suite)', value=txt)

            # on ajoute les champs dans l'embed
            # embed.add_field(name=f'Historique ({df.shape[0]} parties)', value=txt)

            # On envoie l'embed
            if not embeds:  # si il n'y a qu'un seul embed, on l'envoie normalement
                # on ajoute ces champs dans le premier embed
                embed.add_field(name='KDA', value=total_kda)
                embed.add_field(name='Champions', value=txt_champ)
                embed.add_field(
                    name='Ratio', value=f'{total_victoire} ({nb_victoire_total/(nb_victoire_total+nb_defaite_total)*100:.2f}%) | LP {total_lp}')
                embed.add_field(
                    name='Autres', value=f'Durée moyenne : **{duree_moyenne:.0f}**m | MVP : {mvp_moyenne:.1f}')
                if (total_quadra + total_penta) > 0:
                    embed.add_field(
                        name='Série de kills', value=f'Quadra : **{total_quadra}** | Penta : **{total_penta}**')
                await ctx.send(embeds=embed)
            else:  # sinon on utilise le paginator
                embeds.append(embed)  # on ajoute le dernier embed

                paginator = Paginator.create_from_embeds(
                    self.bot,
                    *embeds)

                paginator.show_select_menu = True
                await paginator.send(ctx)

        else:
            await ctx.send('Pas de game enregistré sur les dernières 24h pour ce joueur')
            

    @slash_command(name="history_game",
                   description="Deroulement d'une game",
                   options=[
                       SlashCommandOption(name="riot_id",
                                          description="Nom du joueur",
                                          type=interactions.OptionType.STRING,
                                          required=True),
                       SlashCommandOption(name="riot_tag",
                                          description="Tag",
                                          type=interactions.OptionType.STRING,
                                          required=True),
                       SlashCommandOption(name="match_id",
                                          description="Id de la game avec EUW1",
                                          type=interactions.OptionType.STRING,
                                          required=True),
                       SlashCommandOption(name='action',
                                          description='filtrer sur un élément',
                                          type=interactions.OptionType.STRING,
                                          required=False,
                                          choices=[SlashCommandChoice(name='niveau', value='niveau'),
                                                   SlashCommandChoice(name='item', value='item'),
                                                   SlashCommandChoice(name='kda', value='kda'),
                                                   SlashCommandChoice(name='objectif', value='objectif'),
                                                   SlashCommandChoice(name='vision', value='vision')])])
    async def history(self,
                   ctx: SlashContext,
                   riot_id: str,
                   riot_tag:str,
                   match_id : str,
                   action = None):

        
        
        session = aiohttp.ClientSession()

        version = await get_version(session)
        
        await ctx.defer(ephemeral=False)
        
        async with session.get(f"https://ddragon.leagueoflegends.com/cdn/{version['n']['item']}/data/fr_FR/item.json") as itemlist:
            data_item = await itemlist.json()
            
        df = lire_bdd_perso(f'''SELECT * FROM data_timeline_events
        WHERE match_id = '{match_id}' 
        AND riot_id = (SELECT id_compte FROM tracker where riot_id = '{riot_id.lower().replace(' ', '')}' and riot_tagline = '{riot_tag.upper()}') ''', index_col=None).T
        
        limite_text = 1
        
        if df.empty:
            return await ctx.send('Game introuvable')
        
        df['timestamp'] = df['timestamp'].apply(fix_temps)
        
        
        if action != None:
            if action == 'niveau':
                df = df[df['type'].isin(['LEVEL_UP', 'SKILL_LEVEL_UP'])]
            elif action == 'item':
                df = df[df['type'].isin(['ITEM_PURCHASED', 'ITEM_DESTROYED'])]
            elif action == 'kda':
                df = df[df['type'].isin(['DEATHS', 'CHAMPION_KILL', 'CHAMPION_SPECIAL_KILL'])]
            elif action == 'objectif':
                df = df[df['type'].isin(['ELITE_MONSTER_KILL', 'BUILDING_KILL', 'TURRET_PLATE_DESTROYED'])]
            elif action == 'vision':
                df = df[df['type'].isin(['WARD_PLACED', 'WARD_KILL'])]
                
                
        txt = f'**Détail {match_id} ({riot_id}#{riot_tag})** \n\n'

        dict_pos = {1 : 'TOP',
                    2: 'JGL',
                    3: 'MID',
                    4 : 'ADC',
                    5 : 'SUPPORT',
                    6 : 'TOP',
                    7 : 'JGL',
                    8 : 'MID',
                    9 : 'ADC',
                    10 : 'SUPPORT'}
        
        dict_serie = {2 : 'DOUBLE',
                 3 : 'TRIPLE',
                 4 : 'QUADRA',
                 5 : 'PENTA'}

        df['timestamp'] = df['timestamp'].astype(str)

        for index, data in df.iterrows():
            
            txt += f"**{data['timestamp'].replace('.', 'm')} : **"
            match data['type']:
                case 'ITEM_PURCHASED':
                    item = data_item['data'][str(data['itemId'])[:-2]]['name']
                    txt += f"Acheté : **{item}**"
                case 'ITEM_DESTROYED':
                    item = data_item['data'][str(data['itemId'])[:-2]]['name']
                    txt += f'Detruit : **{item}**'
                case 'DEATHS':
                    killer = dict_pos[int(data['killerId'])]
                    assist = [dict_pos[int(x)] for x in list(ast.literal_eval(data['assistingParticipantIds']))]
                    txt += f"__Mort__ par le **{killer}** assistés par **{','.join(assist)}**"
                    
                case 'CHAMPION_KILL':
                    killer = dict_pos[int(data['victimId'])]
                    assist = [dict_pos[int(x)] for x in list(ast.literal_eval(data['assistingParticipantIds']))]
                    txt += f"__Kill__ sur **{killer}** assistés par **{','.join(assist)}**"
                    
                    if data['shutdownBounty'] != 0.0:
                        txt += f". Shutdown : **{int(data['shutdownBounty'])}** gold"
                        
                case 'CHAMPION_SPECIAL_KILL':
                    if data['killType'] == 'KILL_MULTI':
                        txt += f"Serie : **{dict_serie[int(data['multiKillLength'])]}**"
                    elif data['killType'] == 'KILL_FIRST_BLOOD':
                        killer = dict_pos[int(data['killerId'])]
                        txt += f'First Blood en tuant {killer}'
                        
                case 'TURRET_PLATE_DESTROYED':
                    txt += f"Plate en **{data['laneType']}**"
                case 'SKILL_LEVEL_UP':
                    txt += f"Up **spell {int(data['skillSlot'])}**"
                case 'WARD_PLACED':
                    txt += f"Utilisation : **{data['wardType']}**"
                case 'WARD_KILL':
                    txt += f"Destruction : **{data['wardType']}**"    
                case 'BUILDING_KILL':
                    txt += f"Prise : **{data['buildingType']}** ({data['towerType']}) en **{data['laneType']}**"
                case 'ELITE_MONSTER_KILL':
                    killer = dict_pos[int(data['killerId'])]
                    assist = [dict_pos[int(x)] for x in list(ast.literal_eval(data['assistingParticipantIds']))]
                    txt += f"Le {killer} a tué le {data['monsterType']} ({data['monsterSubType']}) avec l'aide de {','.join(assist)}"
                case 'LEVEL_UP':
                    txt += f"Up niveau **{int(data['level'])}**"
                    
            txt += '\n'
            
            if len(txt) >= 900 * limite_text:
                txt += '###'
                limite_text += 1
                
        liste_txt = txt.split('###')
        
        liste_embeds = []
        for i, texte in enumerate(liste_txt):
            embed = interactions.Embed(title=f'**Détail {match_id} ({riot_id}#{riot_tag})** (Partie {i})')
            embed.add_field('Description', texte)
            liste_embeds.append(embed)
        
        paginator = Paginator.create_from_embeds(
            self.bot,
            *liste_embeds)    

        paginator.show_select_menu = True
        
        await paginator.send(ctx)   

def setup(bot):
    LeagueofLegends(bot)
