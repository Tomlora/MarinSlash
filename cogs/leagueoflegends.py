import os
import sys
import aiohttp
import pandas as pd
import datetime
import numpy as np
import warnings
import interactions
from interactions import Option, Extension, CommandContext
from interactions.ext.tasks import IntervalTrigger, create_task
from interactions.ext.wait_for import wait_for_component, setup as stp
from fonctions.params import Version
from fonctions.channels_discord import verif_module

from fonctions.gestion_bdd import (lire_bdd,
                                   sauvegarde_bdd,
                                   get_data_bdd,
                                   requete_perso_bdd,
                                   lire_bdd_perso)

from fonctions.match import (matchlol,
                             getId,
                             dict_rankid,
                             get_league_by_summoner,
                             get_summoner_by_name,
                             trouver_records
                             )
from fonctions.channels_discord import chan_discord, rgb_to_discord

from time import sleep

warnings.simplefilter(action='ignore', category=FutureWarning)
pd.options.mode.chained_assignment = None  # default='warn'


def records_check2(fichier,
                   fichier_joueur,
                   category,
                   result_category_match,
                   embed,
                   methode='max'):
    '''Cherche s'il y a un record :
    - Dans un premier temps, parmi tous les joueurs.
    - Dans un second temps, parmi les stats du joueur.                                                                                                                                 
    '''

    # Record sur tous les joueurs
    if fichier.shape[0] > 0:  # s'il y a des données, sinon first record
        joueur, champion, record, url = trouver_records(
            fichier, category, methode)

        if methode == 'max':
            if float(record) < float(result_category_match):
                embed = embed + \
                    f"\n ** :boom: Record {category} battu avec {result_category_match} ** (Ancien : {record} par {joueur} ({champion}))"
        else:
            if float(record) > float(result_category_match):
                embed = embed + \
                    f"\n ** :boom: Record {category} battu avec {result_category_match} ** (Ancien : {record} par {joueur} ({champion}))"
    else:
        embed = embed + \
            f"\n ** :boom: Premier Record {category} avec {result_category_match} **"

    # Record sur ses stats
    if fichier_joueur.shape[0] > 0:  # s'il y a des données, sinon first record
        joueur_perso, champion_perso, record_perso, url = trouver_records(
            fichier_joueur, category, methode)

        if methode == 'max':
            if float(record_perso) < float(result_category_match):
                embed = embed + \
                    f"\n ** :military_medal: Tu as battu ton record personnel en {category.lower()} avec {result_category_match} ** (Anciennement : {record_perso})"
        else:
            if float(record_perso) > float(result_category_match):
                embed = embed + \
                    f"\n ** :military_medal: Tu as battu ton record personnel en {category.lower()} avec {result_category_match} ** (Anciennement : {record_perso})"
    else:
        embed = embed + \
            f"\n ** :military_medal: Premier Record personnel {category} avec {result_category_match} **"

    return embed


def records_check(fichier,
                  key_boucle,
                  key: str,
                  Score_check: float,
                  thisChampName,
                  summonerName,
                  embed,
                  url,
                  saison: int,
                  mode: str):
    mode = mode.lower()
    if str(key_boucle) == str(key):
        # ici on veut le plus faible et pas égale à 0
        if str(key) in ['EARLY_DRAKE', 'EARLY_BARON'] and Score_check > 0:
            if float(fichier[key]['Score']) > Score_check:
                ancien_score = fichier[key]['Score']
                detenteur_ancien_score = fichier[key]['Joueur']
                requete_perso_bdd('''UPDATE records
	            SET "Score"= :score, "Champion"= :champion, "Joueur"= :joueur, url= :url
	            WHERE index = :record and saison = :saison and mode = :mode;''', {'record': key, 'score': Score_check, 'champion': thisChampName, 'joueur': summonerName, 'url': url, 'saison': saison, 'mode': mode})
                # Annonce que le record a été battu :
                embed = embed + \
                    f"\n ** :boom: Record {str(key).lower()} battu avec {Score_check} ** (Ancien : {ancien_score} par {detenteur_ancien_score})"

        else:
            # si le record est battu, on fait les modifs nécessaires:
            if float(fichier[key]['Score']) < Score_check:
                ancien_score = fichier[key]['Score']
                detenteur_ancien_score = fichier[key]['Joueur']
                requete_perso_bdd('''UPDATE records
	            SET "Score"= :score, "Champion"= :champion, "Joueur"= :joueur, url= :url
	            WHERE index= :record and saison = :saison and mode =:mode;''', {'record': key, 'score': Score_check, 'champion': thisChampName, 'joueur': summonerName, 'url': url, 'saison': saison, 'mode': mode})

                embed = embed + \
                    f"\n ** :boom: Record {str(key).lower()} battu avec {Score_check} ** (Ancien : {ancien_score} par {detenteur_ancien_score})"

    return embed


class LeagueofLegends(Extension):
    def __init__(self, bot):
        self.bot: interactions.Client = bot
        stp(self.bot)

    @interactions.extension_listener
    async def on_start(self):

        self.task1 = create_task(IntervalTrigger(60))(self.update)
        self.task1.start()

        self.task2 = create_task(IntervalTrigger(60*60))(self.lolsuivi)
        self.task2.start()

    async def printInfo(self,
                        summonerName,
                        idgames: int,
                        succes,
                        sauvegarder: bool,
                        identifiant_game=None):

        match_info = matchlol(summonerName,
                              idgames,
                              identifiant_game=identifiant_game)  # class

        await match_info.get_data_riot()
        await match_info.prepare_data()

        # pour nouveau système de record
        fichier = lire_bdd_perso('SELECT distinct * from matchs where season = %(saison)s and mode = %(mode)s', index_col='id', params={'saison': match_info.season,
                                                                                                                                        'mode': match_info.thisQ}).transpose()

        fichier_joueur = lire_bdd_perso('SELECT distinct * from matchs where season = %(saison)s and mode = %(mode)s and joueur = %(joueur)s', index_col='id', params={'saison': match_info.season,
                                                                                                                                                                       'joueur': summonerName.lower(),
                                                                                                                                                                       'mode': match_info.thisQ}).transpose()
        if sauvegarder:
            await match_info.save_data()

        if match_info.thisQId == 900:  # urf
            return {}, 'URF'

        if match_info.thisQId == 840:
            return {}, 'Bot'  # bot game

        url_game = f'https://www.leagueofgraphs.com/fr/match/euw/{str(match_info.last_match)[5:]}#participant{int(match_info.thisId)+1}'

        exploits = "Observations :"

        # Suivi

        suivi = lire_bdd('suivi', 'dict')

        try:
            if suivi[summonerName.lower().replace(" ", "")]['tier'] == match_info.thisTier and suivi[summonerName.lower().replace(" ", "")]['rank'] == match_info.thisRank:
                difLP = int(match_info.thisLP) - \
                    int(suivi[summonerName.lower().replace(" ", "")]['LP'])
            else:
                difLP = 0
        except:
            difLP = 0

        if difLP > 0:
            difLP = '+' + str(difLP)
        else:
            difLP = str(difLP)

        if match_info.thisQ == "RANKED":  # si pas ranked, inutile car ça bougera pas

            suivi[summonerName.lower().replace(
                " ", "")]['wins'] = match_info.thisVictory
            suivi[summonerName.lower().replace(
                " ", "")]['losses'] = match_info.thisLoose
            suivi[summonerName.lower().replace(
                " ", "")]['LP'] = match_info.thisLP

        # on ne prend que les ranked > 20 min ou aram > 10 min
        if (match_info.thisQ == "RANKED" and match_info.thisTime > 20) or (match_info.thisQ == "ARAM" and match_info.thisTime > 10):

            records = lire_bdd_perso('SELECT index, "Score", "Champion", "Joueur", url from records where saison= %(saison)s and mode=%(mode)s', params={'saison': match_info.season,
                                                                                                                                                         'mode': match_info.thisQ.lower()})
            records = records.to_dict()

            # nouveau système de records
            # if int(match_info.thisDeaths) >= 1: # on ne peut pas comparer à un perfect kda
            #     exploits = records_check2(fichier, fichier_joueur, 'kda', match_info.thisKDA, exploits)
            # else:
            #     exploits = records_check2(fichier, fichier_joueur, 'kda', float(
            #                                      round((int(match_info.thisKills) + int(match_info.thisAssists)) / (int(match_info.thisDeaths) + 1),2)), exploits)
            # exploits = records_check2(fichier, fichier_joueur, 'kp', match_info.thisKP, exploits)
            # exploits = records_check2(fichier, fichier_joueur, 'cs', match_info.thisMinion, exploits)
            # exploits = records_check2(fichier, fichier_joueur, 'cs_min', match_info.thisMinionPerMin, exploits)
            # exploits = records_check2(fichier, fichier_joueur, 'kills', match_info.thisKills, exploits)
            # exploits = records_check2(fichier, fichier_joueur, 'deaths', match_info.thisDeaths, exploits)
            # exploits = records_check2(fichier, fichier_joueur, 'assists', match_info.thisAssists, exploits)
            # exploits = records_check2(fichier, fichier_joueur, 'double', match_info.thisDouble, exploits)
            # exploits = records_check2(fichier, fichier_joueur, 'triple', match_info.thisTriple, exploits)
            # exploits = records_check2(fichier, fichier_joueur, 'quadra', match_info.thisQuadra, exploits)
            # exploits = records_check2(fichier, fichier_joueur, 'penta', match_info.thisPenta, exploits)
            # exploits = records_check2(fichier, fichier_joueur, 'team_kills', match_info.thisTeamKills, exploits)
            # exploits = records_check2(fichier, fichier_joueur, 'team_deaths', match_info.thisTeamKillsOp, exploits)
            # exploits = records_check2(fichier, fichier_joueur, 'time', match_info.thisTime, exploits)
            # exploits = records_check2(fichier, fichier_joueur, 'dmg', match_info.thisDamageNoFormat, exploits)
            # exploits = records_check2(fichier, fichier_joueur, 'dmg_ad', match_info.thisDamageADNoFormat, exploits)
            # exploits = records_check2(fichier, fichier_joueur, 'dmg_ap', match_info.thisDamageAPNoFormat, exploits)
            # exploits = records_check2(fichier, fichier_joueur, 'dmg_true', match_info.thisDamageTrueNoFormat, exploits)
            # exploits = records_check2(fichier, fichier_joueur, 'gold', match_info.thisGoldNoFormat, exploits)
            # exploits = records_check2(fichier, fichier_joueur, 'gold_min', match_info.thisGoldPerMinute, exploits)
            # exploits = records_check2(fichier, fichier_joueur, 'dmg_min', match_info.thisDamagePerMinute, exploits)
            # exploits = records_check2(fichier, fichier_joueur, 'solokills', match_info.thisSoloKills, exploits)
            # exploits = records_check2(fichier, fichier_joueur, 'dmg_reduit', match_info.thisDamageSelfMitigated, exploits)
            # exploits = records_check2(fichier, fichier_joueur, 'heal_total', match_info.thisTotalHealed, exploits)
            # exploits = records_check2(fichier, fichier_joueur, 'heal_allies', match_info.thisTotalOnTeammates, exploits)
            # exploits = records_check2(fichier, fichier_joueur, 'serie_kills', match_info.thisKillingSprees, exploits)
            # exploits = records_check2(fichier, fichier_joueur, 'cs_dix_min', match_info.thisCSafter10min, exploits)
            # exploits = records_check2(fichier, fichier_joueur, 'cs_max_avantage', match_info.thisCSAdvantageOnLane, exploits)
            # exploits = records_check2(fichier, fichier_joueur, 'temps_dead', match_info.thisTimeSpendDead, exploits)
            # exploits = records_check2(fichier, fichier_joueur, 'damageratio', match_info.thisDamageRatio, exploits)
            # exploits = records_check2(fichier, fichier_joueur, 'tankratio', match_info.thisDamageTakenRatio, exploits)
            # exploits = records_check2(fichier, fichier_joueur, 'dmg_tank', match_info.thisDamageTakenNoFormat, exploits)
            # exploits = records_check2(fichier, fichier_joueur, 'shield', match_info.thisTotalShielded, exploits)
            # exploits = records_check2(fichier, fichier_joueur, 'allie_feeder', match_info.thisAllieFeeder, exploits)

            # if match_info.thisQ == 'RANKED': # seulement en ranked
            #     exploits = records_check2(fichier, fichier_joueur, 'vision_score', match_info.thisVision, exploits)
            #     exploits = records_check2(fichier, fichier_joueur, 'vision_wards', match_info.thisWards, exploits)
            #     exploits = records_check2(fichier, fichier_joueur, 'vision_wards_killed', match_info.thisWardsKilled, exploits)
            #     exploits = records_check2(fichier, fichier_joueur, 'vision_pink', match_info.thisPink, exploits)
            #     exploits = records_check2(fichier, fichier_joueur, 'vision_min', match_info.thisVisionPerMin, exploits)
            #     exploits = records_check2(fichier, fichier_joueur, 'level_max_avantage', match_info.thisLevelAdvantage, exploits)
            #     exploits = records_check2(fichier, fichier_joueur, 'vision_avantage', match_info.thisVisionAdvantage, exploits)
            #     exploits = records_check2(fichier, fichier_joueur, 'early_drake', match_info.earliestDrake, exploits)
            #     exploits = records_check2(fichier, fichier_joueur, 'early_baron', match_info.earliestBaron, exploits)
            #     exploits = records_check2(fichier, fichier_joueur, 'jgl_dix_min', match_info.thisJUNGLEafter10min, exploits)
            #     exploits = records_check2(fichier, fichier_joueur, 'baron', match_info.thisBaronTeam, exploits)
            #     exploits = records_check2(fichier, fichier_joueur, 'drake', match_info.thisDragonTeam, exploits)
            #     exploits = records_check2(fichier, fichier_joueur, 'herald', match_info.thisHeraldTeam, exploits)
            #     exploits = records_check2(fichier, fichier_joueur, 'cs_jungle', match_info.thisJungleMonsterKilled, exploits)

            for key, value in records.items():
                if int(match_info.thisDeaths) >= 1:

                    exploits = records_check(records, key, 'KDA',
                                             float(match_info.thisKDA),
                                             match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)
                else:
                    exploits = records_check(records, key, 'KDA',
                                             float(
                                                 round((int(match_info.thisKills) + int(match_info.thisAssists)) / (int(match_info.thisDeaths) + 1), 2)),
                                             match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)

                exploits = records_check(records, key, 'KP', match_info.thisKP,
                                         match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)
                exploits = records_check(records, key, 'CS', match_info.thisMinion,
                                         match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)
                exploits = records_check(records, key, 'CS/MIN', match_info.thisMinionPerMin,
                                         match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)
                exploits = records_check(records, key, 'KILLS', match_info.thisKills,
                                         match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)
                exploits = records_check(records, key, 'DEATHS', match_info.thisDeaths,
                                         match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)
                exploits = records_check(records, key, 'ASSISTS', match_info.thisAssists,
                                         match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)

                if match_info.thisQ == "RANKED":
                    exploits = records_check(records, key, 'WARDS_SCORE', match_info.thisVision,
                                             match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)
                    exploits = records_check(records, key, 'WARDS_POSEES', match_info.thisWards,
                                             match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)
                    exploits = records_check(records, key, 'WARDS_DETRUITES', match_info.thisWardsKilled,
                                             match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)
                    exploits = records_check(records, key, 'WARDS_PINKS', match_info.thisPink,
                                             match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)
                    exploits = records_check(records, key, 'BUFFS_VOLEES', match_info.thisbuffsVolees,
                                             match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)
                    exploits = records_check(records, key, 'TOWER_PLATES', match_info.thisTurretPlatesTaken,
                                             match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)
                    exploits = records_check(records, key, 'ECART_LEVEL', match_info.thisLevelAdvantage,
                                             match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)
                    exploits = records_check(records, key, 'EARLY_DRAKE', match_info.earliestDrake,
                                             match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)
                    exploits = records_check(records, key, 'EARLY_BARON', match_info.earliestBaron,
                                             match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)
                    exploits = records_check(records, key, 'CS_AVANTAGES', match_info.thisCSAdvantageOnLane,
                                             match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)
                    exploits = records_check(records, key, 'CS_APRES_10_MIN', match_info.thisCSafter10min,
                                             match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)

                    if match_info.thisPosition == "SUPPORT":
                        exploits = records_check(records, key, 'AVANTAGE_VISION_SUPPORT', float(match_info.thisVisionAdvantage),
                                                 match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)

                    else:
                        exploits = records_check(records, key, 'AVANTAGE_VISION', float(match_info.thisVisionAdvantage),
                                                 match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)

                exploits = records_check(records, key, 'DEGATS_INFLIGES',
                                         match_info.match_detail_participants['totalDamageDealtToChampions'],
                                         match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)
                exploits = records_check(records, key, '% DMG', match_info.thisDamageRatio,
                                         match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)
                exploits = records_check(records, key, 'DOUBLE', match_info.thisDouble,
                                         match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)
                exploits = records_check(records, key, 'TRIPLE', match_info.thisTriple,
                                         match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)
                exploits = records_check(records, key, 'QUADRA', match_info.thisQuadra,
                                         match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)
                exploits = records_check(records, key, 'PENTA', match_info.thisPenta,
                                         match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)
                exploits = records_check(records, key, 'DUREE_GAME', match_info.thisTime,
                                         match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)
                exploits = records_check(records, key, 'ALLIE_FEEDER', match_info.thisAllieFeeder,
                                         match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)

                # on supprime Zeri de ce record qui est impossible à égaler avec d'autres champions
                if match_info.thisChampName != "Zeri":
                    exploits = records_check(records, key, 'SPELLS_USED',
                                             match_info.thisSpellUsed,
                                             match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)

                exploits = records_check(records, key, 'SPELLS_EVITES', match_info.thisSpellsDodged,
                                         match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)

                exploits = records_check(records, key, 'SOLOKILLS', match_info.thisSoloKills,
                                         match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)

                exploits = records_check(records, key, 'NB_SERIES_DE_KILLS', match_info.thisKillingSprees,
                                         match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)
                exploits = records_check(records, key, 'DOMMAGES_TANK',
                                         int(
                                             match_info.match_detail_participants['totalDamageTaken']),
                                         match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)
                exploits = records_check(records, key, 'DOMMAGES_TANK%', match_info.thisDamageTakenRatio,
                                         match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)
                exploits = records_check(records, key, 'DOMMAGES_REDUITS', match_info.thisDamageSelfMitigated,
                                         match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)
                exploits = records_check(records, key, 'DOMMAGES_TOWER', match_info.thisDamageTurrets,
                                         match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)
                exploits = records_check(records, key, 'GOLDS_GAGNES', match_info.thisGoldEarned,
                                         match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)
                exploits = records_check(records, key, 'SERIES_DE_KILLS', match_info.thisKillsSeries,
                                         match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)
                exploits = records_check(records, key, 'TOTAL_HEALS',
                                         match_info.thisTotalHealed,
                                         match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)
                exploits = records_check(records, key, 'HEALS_SUR_ALLIES', match_info.thisTotalOnTeammates,
                                         match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)

                if match_info.thisChampName != "Zeri":  # champion désactivé pour ce record
                    exploits = records_check(records, key, 'SKILLSHOTS_HIT', match_info.thisSkillshot_hit,
                                             match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)

                exploits = records_check(records, key, 'SKILLSHOTS_DODGES', match_info.thisSkillshot_dodged,
                                         match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)

                exploits = records_check(records, key, 'SHIELD', match_info.thisTotalShielded,
                                         match_info.thisChampName, summonerName, exploits, url_game, match_info.season, match_info.thisQ)

        # on le fait après sinon ça flingue les records
        match_info.thisDamageTurrets = "{:,}".format(
            match_info.thisDamageTurrets).replace(',', ' ').replace('.', ',')

        # couleur de l'embed en fonction du pseudo

        pseudo = str(summonerName).lower()

        data = get_data_bdd(f'SELECT "R", "G", "B" from tracker WHERE index= :index', {
                            'index': pseudo}).fetchall()
        color = rgb_to_discord(data[0][0], data[0][1], data[0][2])

        # constructing the message

        if match_info.thisQ == "OTHER":
            embed = interactions.Embed(
                title=f"** {summonerName.upper()} ** vient de ** {match_info.thisWin} ** une game ", color=color)
        elif match_info.thisQ == "ARAM":
            embed = interactions.Embed(
                title=f"** {summonerName.upper()} ** vient de ** {match_info.thisWin} ** une ARAM ", color=color)
        else:
            embed = interactions.Embed(
                title=f"** {summonerName.upper()} ** vient de ** {match_info.thisWin} ** une {match_info.thisQ} game ({match_info.thisPosition})", color=color)

        # annonce
        points = 0

        if match_info.thisQ == 'ARAM':
                # couronnes pour aram
            settings = lire_bdd_perso(
                f'SELECT index, score_aram as score from achievements_settings')
        else: # couronnes si autre mode de jeu
            settings = lire_bdd_perso(
                f'SELECT index, score as score from achievements_settings')

        settings = settings.to_dict()

        
        ## Couronnes 
        
        if match_info.thisQ == 'RANKED': # pour only ranked 
            if int(match_info.thisLevelAdvantage) >= settings['Ecart_Level']['score']:
                exploits = exploits + \
                    f"\n ** :crown: :wave: Tu as au moins {match_info.thisLevelAdvantage} niveaux d'avance sur ton adversaire durant la game**"
                points = points + 1

            if (float(match_info.thisVisionAdvantage) >= settings['Avantage_vision(support)']['score'] and str(match_info.thisPosition) == "SUPPORT") or (float(match_info.thisVisionAdvantage) >= settings['Avantage_vision(autres)']['score'] and str(match_info.thisPosition) != "SUPPORT"):
                exploits = exploits + \
                    f"\n ** :crown: :eye: Ce joueur a un gros avantage de vision sur son adversaire avec {match_info.thisVisionAdvantage}% **"
                points = points + 1

            if (float(match_info.thisDragonTeam) >= settings['Dragon']['score']):
                exploits = exploits + f"\n ** :crown: :dragon: Tu as obtenu l'âme du dragon **"
                points = points + 1

            if (int(match_info.thisDanceHerald) >= 1):
                exploits = exploits + f"\n ** :crown: :dancer: A dansé avec l'Herald **"
                points = points + 1

            if (int(match_info.thisPerfectGame) >= 1):
                exploits = exploits + f"\n :crown: :crown: :sunny: Perfect Game"
                points = points + 2

            if int(match_info.thisDeaths) == int(settings['Ne_pas_mourir']['score']):
                exploits = exploits + "\n ** :crown: :heart: Ce joueur n'est pas mort de la game ** \n ** :crown: :star: Ce joueur a un PERFECT KDA **"
                points = points + 2

            if float(match_info.thisVisionPerMin) >= settings['Vision/min(support)']['score'] and str(match_info.thisPosition) == "SUPPORT":
                exploits = exploits + \
                    f"\n ** :crown: :eye: Ce joueur a un gros score de vision avec {match_info.thisVisionPerMin} / min **"
                points = points + 1

            if int(match_info.thisVisionPerMin) >= settings['Vision/min(autres)']['score'] and str(match_info.thisPosition) != "SUPPORT":
                exploits = exploits + \
                    f"\n ** :crown: :eye: Ce joueur a un gros score de vision avec {match_info.thisVisionPerMin} / min **"
                points = points + 1

            if int(match_info.thisSoloKills) >= settings['Solokills']['score']:
                exploits = exploits + \
                    f"\n ** :crown: :muscle: Ce joueur a réalisé {match_info.thisSoloKills} solokills **"
                points = points + 1

            if int(match_info.thisCSAdvantageOnLane) >= settings['CSAvantage']['score']:
                exploits = exploits + \
                    f"\n ** :crown: :ghost: Tu as plus de {match_info.thisCSAdvantageOnLane} CS d'avance sur ton adversaire durant la game**"
                points = points + 1
                
        ## pour tous les modes
        if float(match_info.thisKDA) >= settings['KDA']['score']:
            exploits = exploits + \
                f"\n ** :crown: :star: Ce joueur a un bon KDA avec un KDA de {match_info.thisKDA} **"
            points = points + 1

        if int(match_info.thisKP) >= settings['KP']['score']:
            exploits = exploits + \
                f"\n ** :crown: :dagger: Ce joueur a participé à énormément de kills dans son équipe avec {match_info.thisKP} % **"
            points = points + 1

        if int(match_info.thisPenta) >= settings['Pentakill']['score']:
            exploits = exploits + \
                f"\n ** :crown: :five: Ce joueur a pentakill ** {match_info.thisPenta} fois"
            points = points + (1 * int(match_info.thisPenta))

        if int(match_info.thisQuadra) >= settings['Quadrakill']['score']:
            exploits = exploits + \
                f"\n ** :crown: :four: Ce joueur a quadrakill ** {match_info.thisQuadra} fois"
            points = points + (1 * int(match_info.thisQuadra))

        if int(match_info.thisMinionPerMin) >= settings['CS/min']['score']:
            exploits = exploits + \
                f"\n ** :crown: :ghost: Ce joueur a bien farm avec {match_info.thisMinionPerMin} CS / min **"
            points = points + 1

        if int(match_info.thisDamageRatio) >= settings['%_dmg_équipe']['score']:
            exploits = exploits + \
                f"\n ** :crown: :dart: Ce joueur a infligé beaucoup de dmg avec {match_info.thisDamageRatio}%  pour son équipe **"
            points = points + 1

        if int(match_info.thisDamageTakenRatio) >= settings['%_dmg_tank']['score']:
            exploits = exploits + \
                f"\n ** :crown: :shield: Ce joueur a bien tank pour son équipe avec {match_info.thisDamageTakenRatio}% **"
            points = points + 1

        if int(match_info.thisTotalOnTeammates) >= settings['Total_Heals_sur_alliés']['score']:
            exploits = exploits + \
                f"\n ** :crown: :heart: Ce joueur a heal plus de {match_info.thisTotalOnTeammatesFormat} sur ses alliés **"
            points = points + 1

        if (int(match_info.thisTotalShielded) >= settings['Shield']['score']):
            exploits = exploits + \
                f"\n ** :crown: :shield: Tu as shield {match_info.thisTotalShielded} **"
            points = points + 1

        if (match_info.thisQ == "RANKED" and match_info.thisTime > 20 and succes is True) or\
                (match_info.thisQ == "ARAM" and match_info.thisTime > 10):
            # on add les couronnes si ranked (> 20 min) ou aram (> 10 min))
            exploits = records_check2(
                fichier, fichier_joueur, 'couronne', points, exploits)
            
            await match_info.add_couronnes(points)

        # Présence d'afk
        if match_info.AFKTeam >= 1:
            exploits = exploits + \
                "\n ** :tired_face: Tu as eu un afk dans ton équipe :'( **"

        # Série de victoire
        if match_info.thisWinStreak == "True" and match_info.thisQ == "RANKED" and succes is True and match_info.thisTime > 20:
            # si égal à 0, le joueur commence une série avec 3 wins
            if suivi[summonerName.lower().replace(" ", "")]["serie"] == 0:
                suivi[summonerName.lower().replace(" ", "")]["serie"] = 3
            else:  # si pas égal à 0, la série a déjà commencé
                suivi[summonerName.lower().replace(
                    " ", "")]["serie"] = suivi[summonerName.lower().replace(" ", "")]["serie"] + 1

            serie_victoire = round(
                suivi[summonerName.lower().replace(" ", "")]["serie"], 0)

            exploits = exploits + \
                f"\n ** :fire: Ce joueur est en série de victoire avec {serie_victoire} victoires**"

        elif match_info.thisWinStreak == "False" and match_info.thisQ == "RANKED":  # si pas de série en soloq
            suivi[summonerName.lower().replace(" ", "")]["serie"] = 0
            serie_victoire = 0
        else:
            serie_victoire = 0

        # TODO : records personnel

        # Achievements
        # TODO : à supprimer dès s13
        if match_info.thisQ == "RANKED" and match_info.thisTime > 20 and succes is True:
            suivi[summonerName.lower().replace(" ", "")]['Achievements'] = \
                suivi[summonerName.lower().replace(" ", "")][
                'Achievements'] + points

            suivi[summonerName.lower().replace(" ", "")]['games'] = suivi[summonerName.lower().replace(" ", "")][
                'games'] + 1

        if match_info.thisQ == "ARAM" and match_info.thisTime > 10:
            suivi[summonerName.lower().replace(" ", "")]['Achievements_aram'] = \
                suivi[summonerName.lower().replace(" ", "")][
                'Achievements_aram'] + points

            suivi[summonerName.lower().replace(" ", "")]['games_aram'] = suivi[summonerName.lower().replace(" ", "")][
                'games_aram'] + 1

        sauvegarde_bdd(suivi, 'suivi')  # achievements + suivi

        # observations

        # ici, ça va de 1 à 10.. contrairement à Rito qui va de 1 à 9
        embed.add_field(name="Game", value=f"[LeagueofGraph]({url_game})")
        embed.add_field(
            name="OPGG", value=f"[Profil](https://euw.op.gg/summoners/euw/{summonerName})")
        embed.add_field(
            name="Stats", value=f"[{match_info.thisChampName}](https://lolalytics.com/lol/{match_info.thisChampName.lower()}/build/)")

        if len(exploits) <= 1024:
            embed.add_field(name="Durée de la game : " + str(int(match_info.thisTime)) + " minutes",
                            value=exploits, inline=False)

        else:
            embed.add_field(name="Durée de la game : " + str(int(match_info.thisTime)) + " minutes",
                            value=exploits[:1024], inline=False)
            embed.add_field(
                name="Records 2",
                value=exploits[1023:2047], inline=False)
            if len(exploits) >= 2047:
                embed.add_field(
                    name="Records 3",
                    value=exploits[2047:3071], inline=False)
            if len(exploits) >= 3071:
                embed.add_field(
                    name="Records 4",
                    value=exploits[3071:4095], inline=False)
            if len(exploits) >= 4095:
                embed.add_field(
                    name="Records 5",
                    value=exploits[4095:])

        # # Objectifs
        if match_info.thisQ != "ARAM":
            embed.add_field(name="Team :", value=f"\nEcart top - Vision : **{match_info.ecart_top_vision}** | CS : **{match_info.ecart_top_cs}** \n"
                            + f"Ecart jgl - Vision: **{match_info.ecart_jgl_vision}** | CS : **{match_info.ecart_jgl_cs}** \n"
                            + f"Ecart mid - Vision : **{match_info.ecart_mid_vision}** | CS : **{match_info.ecart_mid_cs}** \n"
                            + f"Ecart adc - Vision : **{match_info.ecart_adc_vision}** | CS : **{match_info.ecart_adc_cs}** \n"
                            + f"Ecart supp - Vision : **{match_info.ecart_supp_vision}** | CS : **{match_info.ecart_supp_cs}**", inline=False)

       # Gestion de l'image 1

        embed = await match_info.resume_personnel('resume_perso', embed, difLP)

        # Gestion de l'image 2

        await match_info.resume_general('resume')

        # on charge les img

        resume = interactions.File('resume_perso.png')
        embed.set_image(url='attachment://resume_perso.png')

        embed2 = interactions.Embed(color=color)
        resume2 = interactions.File('resume.png')
        embed2.set_image(url='attachment://resume.png')

        if sauvegarder:
            embed.set_footer(
                text=f'Version {Version} by Tomlora - Match {str(match_info.last_match)} - Sauvegardé')
        else:
            embed.set_footer(
                text=f'Version {Version} by Tomlora - Match {str(match_info.last_match)}')
        return embed, match_info.thisQ, resume, embed2, resume2

    async def updaterank(self, key, discord_server_id, session: aiohttp.ClientSession):

        suivirank = lire_bdd('suivi', 'dict')

        me = await get_summoner_by_name(session, key)

        stats = await get_league_by_summoner(session, me)

        if len(stats) > 0:
            if str(stats[0]['queueType']) == 'RANKED_SOLO_5x5':
                i = 0
            else:
                i = 1

            tier = str(stats[i]['tier'])
            rank = str(stats[i]['rank'])
            level = tier + " " + rank

            if str(suivirank[key]['tier']) + " " + str(suivirank[key]['rank']) != level:
                rank_old = str(suivirank[key]['tier']) + \
                    " " + str(suivirank[key]['rank'])

                try:
                    channel_tracklol = await interactions.get(client=self.bot,
                                                              obj=interactions.Channel,
                                                              object_id=discord_server_id.tracklol)
                    if dict_rankid[rank_old] > dict_rankid[level]:  # 19 > 18
                        await channel_tracklol.send(f' Le joueur **{key}** a démote du rank **{rank_old}** à **{level}**')
                        await channel_tracklol.send(files=interactions.File('./img/notstonks.jpg'))
                    elif dict_rankid[rank_old] < dict_rankid[level]:
                        await channel_tracklol.send(f' Le joueur **{key}** a été promu du rank **{rank_old}** à **{level}**')
                        await channel_tracklol.send(files=interactions.File('./img/stonks.jpg'))

                except:
                    print('Channel impossible')
                    print(sys.exc_info())

                requete_perso_bdd('UPDATE suivi SET tier = :tier, rank = :rank where index = :joueur', {'tier': tier,
                                                                                                        'rank': rank,
                                                                                                        'joueur': key})

    @interactions.extension_command(name="game",
                                    description="Voir les statistiques d'une games",
                                    options=[
                                        Option(name="summonername",
                                                    description="Nom du joueur",
                                                    type=interactions.OptionType.STRING, required=True),
                                        Option(name="numerogame",
                                                    description="Numero de la game, de 0 à 100",
                                                    type=interactions.OptionType.INTEGER,
                                                    required=True,
                                                    min_value=0,
                                                    max_value=100),
                                        Option(name="succes",
                                                    description="Faut-il la compter dans les records/achievements ? True = Oui / False = Non",
                                                    type=interactions.OptionType.BOOLEAN,
                                                    required=True),
                                        Option(name="sauvegarder",
                                                    description="sauvegarder la game",
                                                    type=interactions.OptionType.BOOLEAN,
                                                    required=False),
                                        Option(name='identifiant_game',
                                                    description="A ne pas utiliser",
                                                    type=interactions.OptionType.STRING,
                                                    required=False)])
    async def game(self,
                   ctx: CommandContext,
                   summonername: str,
                   numerogame: int,
                   succes: bool,
                   sauvegarder: bool = True,
                   identifiant_game=None):

        await ctx.defer(ephemeral=False)

        summonername = summonername.lower()

        embed, mode_de_jeu, resume, embed2, resume2 = await self.printInfo(summonerName=summonername.lower(),
                                                                           idgames=int(
                                                                               numerogame),
                                                                           succes=succes,
                                                                           sauvegarder=sauvegarder,
                                                                           identifiant_game=identifiant_game)

        if embed != {}:
            await ctx.send(embeds=embed, files=resume)
            await ctx.send(embeds=embed2, files=resume2)
            os.remove('resume.png')
            os.remove('resume_perso.png')

    @interactions.extension_command(name="game_multi",
                                    description="Voir les statistiques d'une games",
                                    options=[Option(name="summonername",
                                                    description="Nom du joueur",
                                                    type=interactions.OptionType.STRING,
                                                    required=True),
                                             Option(name="debut",
                                                    description="Numero de la game, de 0 à 100",
                                                    type=interactions.OptionType.INTEGER,
                                                    required=True),
                                             Option(name="fin",
                                                    description="Numero de la game, de 0 à 100",
                                                    type=interactions.OptionType.INTEGER,
                                                    required=True),
                                             Option(name="succes",
                                                    description="Faut-il la compter dans les records/achievements ? True = Oui / False = Non",
                                                    type=interactions.OptionType.BOOLEAN,
                                                    required=True),
                                             Option(name='sauvegarder',
                                                    description='Sauvegarder les games',
                                                    type=interactions.OptionType.BOOLEAN,
                                                    required=False)])
    async def game_multi(self,
                         ctx: CommandContext,
                         summonername: str,
                         debut: int,
                         fin: int,
                         succes: bool,
                         sauvegarder: bool = True):

        await ctx.defer(ephemeral=False)

        for i in range(fin, debut, -1):

            summonername = summonername.lower()

            embed, mode_de_jeu, resume, embed2, resume2 = await self.printInfo(summonerName=summonername.lower(), idgames=int(i), succes=succes, sauvegarder=sauvegarder)

            if embed != {}:
                await ctx.send(embeds=embed, files=resume)
                await ctx.send(embeds=embed2, files=resume2)
            else:
                await ctx.send(f"La game {str(i)} n'a pas été comptabilisée")

            sleep(5)

    async def printLive(self, summonername, discord_server_id: chan_discord):

        summonername = summonername.lower()

        embed, mode_de_jeu, resume, embed2, resume2 = await self.printInfo(summonerName=summonername, idgames=0, succes=True, sauvegarder=True)

        if mode_de_jeu in ['RANKED', 'FLEX']:

            channel_tracklol = await interactions.get(client=self.bot,
                                                      obj=interactions.Channel,
                                                      object_id=discord_server_id.tracklol)
        else:
            channel_tracklol = await interactions.get(client=self.bot,
                                                      obj=interactions.Channel,
                                                      object_id=discord_server_id.lol_others)

        if embed != {}:
            await channel_tracklol.send(embeds=embed, files=resume)
            await channel_tracklol.send(embeds=embed2, files=resume2)

            os.remove('resume.png')
            os.remove('resume_perso.png')

    async def update(self):

        data = get_data_bdd(f'''SELECT tracker.index, tracker.id, tracker.server_id from tracker 
                    INNER JOIN channels_module on tracker.server_id = channels_module.server_id
                    where tracker.activation = true and channels_module.league_ranked = true''').fetchall()
        timeout = aiohttp.ClientTimeout(total=20)
        session = aiohttp.ClientSession(timeout=timeout)

        for key, value, server_id in data:

            id_last_game = await getId(key, session)

            if str(value) != id_last_game:  # value -> ID de dernière game enregistrée dans id_data != ID de la dernière game via l'API Rito / #key = pseudo // value = numéro de la game
                # update la bdd

                requete_perso_bdd(f'UPDATE tracker SET id = :id WHERE index = :index', {
                                  'id': id_last_game, 'index': key})
                try:

                    # identification du channel
                    discord_server_id = chan_discord(int(server_id))

                    # résumé de game

                    await self.printLive(key, discord_server_id)

                    # update rank
                    await self.updaterank(key, discord_server_id, session)

                except:
                    print(f"erreur {key}")  # joueur qui a posé pb
                    print(sys.exc_info())  # erreur
                    continue

         # update la bdd
        await session.close()

    @interactions.extension_command(name="loladd",
                                    description="Ajoute le joueur au suivi",
                                    options=[
                                        Option(name="summonername",
                                                    description="Nom du joueur",
                                                    type=interactions.OptionType.STRING,
                                                    required=True)])
    async def loladd(self,
                     ctx: CommandContext,
                     summonername):
        try:
            if verif_module('league_ranked', int(ctx.guild.id)):
                summonername = summonername.lower()
                session = aiohttp.ClientSession()
                requete_perso_bdd(f'''INSERT INTO tracker(index, id, discord, server_id) VALUES (:summonername, :id, :discord, :guilde);
                                
                                INSERT INTO suivi(
                                index, wins, losses, "LP", tier, rank, "Achievements", games, serie)
                                VALUES (:summonername, 0, 0, 0, 'Non-classe', 0, 0, 0, 0);
                            
                                INSERT INTO suivi_24h(
                                index, wins, losses, "LP", tier, rank, "Achievements", games, serie)
                                VALUES (:summonername, 0, 0, 0, 'Non-classe', 0, 0, 0, 0);
                            
                                INSERT INTO ranked_aram(
                                index, wins, losses, lp, games, k, d, a, activation, rank)
                                VALUES (:summonername, 0, 0, 0, 0, 0, 0, 0, True, 'IRON');
                            
                                INSERT INTO ranked_aram_24h(
                                index, wins, losses, lp, games, k, d, a, activation, rank)
                                VALUES (:summonername, 0, 0, 0, 0, 0, 0, 0, True, 'IRON');''',
                                  {'summonername': summonername.lower(), 'id': await getId(summonername, session), 'discord': int(ctx.author.id), 'guilde': int(ctx.guild.id)})

                await ctx.send(f"{summonername} a été ajouté avec succès au live-feed!")
                await session.close()
            else:
                await ctx.send('Module désactivé pour ce serveur')
        except:
            await ctx.send("Oops! Ce joueur n'existe pas.")

    @interactions.extension_command(name='lolremove', description='Activation/Désactivation du tracker',
                                    options=[
                                        Option(name='summonername',
                                                    description="nom ingame",
                                                    type=interactions.OptionType.STRING,
                                                    required=True),
                                        Option(name="activation",
                                                    description="True : Activé / False : Désactivé",
                                                    type=interactions.OptionType.BOOLEAN,
                                                    required=True)])
    async def lolremove(self,
                        ctx: CommandContext,
                        summonername: str,
                        activation: bool):

        summonername = summonername.lower()

        try:
            requete_perso_bdd('UPDATE tracker SET activation = :activation WHERE index = :index', {
                              'activation': activation, 'index': summonername})
            if activation:
                await ctx.send('Tracker activé !')
            else:
                await ctx.send('Tracker désactivé !')
        except KeyError:
            await ctx.send('Joueur introuvable')

    @interactions.extension_command(name='lollist',
                                    description='Affiche la liste des joueurs suivis')
    async def lollist(self, ctx: CommandContext):

        data = get_data_bdd(f'''SELECT index from tracker 
                    where server_id = :server_id''', {'server_id': int(ctx.guild.id)}).fetchall()

        response = ""

        for key in data:
            response += key[0].upper() + ", "

        response = response[:-2]
        embed = interactions.Embed(
            title="Live feed list", description=response, color=interactions.Color.blurple())

        await ctx.send(embeds=embed)

    async def lolsuivi(self):

        currentHour = str(datetime.datetime.now().hour)

        if currentHour == str(2):

            data = get_data_bdd(f'''SELECT DISTINCT tracker.server_id from tracker 
                    INNER JOIN channels_module on tracker.server_id = channels_module.server_id
                    where channels_module.league_ranked = true''').fetchall()

            for server_id in data:

                guild = await interactions.get(client=self.bot,
                                               obj=interactions.Guild,
                                               object_id=server_id[0])

                chan_discord_id = chan_discord(int(guild.id))

            # le suivi est déjà maj par game/update... Pas besoin de le refaire ici..

                df = lire_bdd_perso(f'''SELECT suivi.index, suivi.wins, suivi.losses, suivi."LP", suivi.tier, suivi.rank, tracker.server_id from suivi 
                                    INNER join tracker ON tracker.index = suivi.index 
                                    where suivi.tier != 'Non-classe' and tracker.server_id = {int(guild.id)} ''')
                df_24h = lire_bdd_perso(f'''SELECT suivi.index, suivi.wins, suivi.losses, suivi."LP", suivi.tier, suivi.rank, tracker.server_id from suivi_24h as suivi
                                    INNER join tracker ON tracker.index = suivi.index 
                                    where suivi.tier != 'Non-classe' and tracker.server_id = {int(guild.id)} ''')

                if df.shape[1] > 0:  # si pas de data, inutile de continuer

                    df = df.transpose().reset_index()
                    df_24h = df_24h.transpose().reset_index()

                    def changement_tier(x):
                        dict_chg_tier = {'IRON': 1,
                                         'BRONZE': 1,
                                         'SILVER': 2,
                                         'GOLD': 3,
                                         'PLATINUM': 4,
                                         'DIAMOND': 5,
                                         'MASTER': 6}
                        return dict_chg_tier[x]

                    def changement_rank(x):
                        dict_chg_rank = {'IV': 1,
                                         'III': 2,
                                         'II': 3,
                                         'I': 4}
                        return dict_chg_rank[x]

                    # Pour l'ordre de passage
                    df['tier_pts'] = df['tier'].apply(changement_tier)
                    df['rank_pts'] = df['rank'].apply(changement_rank)

                    df.sort_values(by=['tier_pts', 'rank_pts', 'LP'], ascending=[
                                   False, False, False], inplace=True)

                    sql = ''

                    suivi = df.set_index('index').transpose().to_dict()
                    suivi_24h = df_24h.set_index('index').transpose().to_dict()

                    joueur = suivi.keys()

                    embed = interactions.Embed(
                        title="Suivi LOL", description='Periode : 24h', color=interactions.Color.blurple())
                    totalwin = 0
                    totaldef = 0
                    totalgames = 0

                    for key in joueur:

                        # suivi est mis à jour par update et updaterank. On va donc prendre le comparer à suivi24h
                        wins = int(suivi_24h[key]['wins'])
                        losses = int(suivi_24h[key]['losses'])
                        nbgames = wins + losses
                        LP = int(suivi_24h[key]['LP'])
                        tier_old = str(suivi_24h[key]['tier'])
                        rank_old = str(suivi_24h[key]['rank'])
                        classement_old = tier_old + " " + rank_old

                        # on veut les stats soloq

                        tier = str(suivi[key]['tier'])
                        rank = str(suivi[key]['rank'])
                        classement_new = tier + " " + rank

                        difwins = int(suivi[key]['wins']) - wins
                        diflosses = int(suivi[key]['losses']) - losses
                        difLP = int(suivi[key]['LP']) - LP
                        totalwin = totalwin + difwins
                        totaldef = totaldef + diflosses
                        totalgames = totalwin + totaldef

                        # evolution

                        if dict_rankid[classement_old] > dict_rankid[classement_new]:  # 19-18
                            difLP = 100 + LP - int(suivi[key]['LP'])
                            difLP = "Démote / -" + str(difLP)
                            emote = ":arrow_down:"

                        elif dict_rankid[classement_old] < dict_rankid[classement_new]:
                            difLP = 100 - LP + int(suivi[key]['LP'])
                            difLP = "Promotion / +" + str(difLP)
                            emote = ":arrow_up:"

                        elif dict_rankid[classement_old] == dict_rankid[classement_new]:
                            if difLP > 0:
                                emote = ":arrow_up:"
                            elif difLP < 0:
                                emote = ":arrow_down:"
                            elif difLP == 0:
                                emote = ":arrow_right:"

                        embed.add_field(name=str(key) + " ( " + tier + " " + rank + " )",
                                        value="V : " +
                                        str(suivi[key]['wins']) +
                                        "(" + str(difwins) + ") | D : "
                                        + str(suivi[key]['losses']) +
                                        "(" + str(diflosses) + ") | LP :  "
                                        + str(suivi[key]['LP']) + "(" + str(difLP) + ")    " + emote, inline=False)

                        if difwins + diflosses > 0:  # si supérieur à 0, le joueur a joué
                            sql += f'''UPDATE suivi_24h SET wins = {suivi[key]['wins']}, losses = {suivi[key]['losses']}, "LP" = {suivi[key]['LP']}, tier = '{suivi[key]['tier']}', rank = '{suivi[key]['rank']}' where index = '{key}';'''

                    channel_tracklol = await interactions.get(client=self.bot,
                                                              obj=interactions.Channel,
                                                              object_id=chan_discord_id.tracklol)

                    embed.set_footer(text=f'Version {Version} by Tomlora')

                    if sql != '':  # si vide, pas de requête
                        requete_perso_bdd(sql)

                    if totalgames > 0:  # s'il n'y a pas de game, on ne va pas afficher le récap
                        await channel_tracklol.send(embeds=embed)
                        await channel_tracklol.send(f'Sur {totalgames} games -> {totalwin} victoires et {totaldef} défaites')

    @interactions.extension_command(name="color_recap",
                                    description="Modifier la couleur du recap",
                                    options=[Option(name="summonername",
                                                    description="Nom du joueur",
                                                    type=interactions.OptionType.STRING,
                                                    required=True),
                                             Option(name="rouge",
                                                    description="R",
                                                    type=interactions.OptionType.INTEGER,
                                                    required=True),
                                             Option(name="vert",
                                                    description="G",
                                                    type=interactions.OptionType.INTEGER,
                                                    required=True),
                                             Option(name="bleu",
                                                    description="B",
                                                    type=interactions.OptionType.INTEGER,
                                                    required=True)])
    async def color_recap(self,
                          ctx: CommandContext,
                          summonername: str,
                          rouge: int,
                          vert: int,
                          bleu: int):

        await ctx.defer(ephemeral=False)

        params = {'rouge': rouge, 'vert': vert,
                  'bleu': bleu, 'index': summonername.lower()}
        requete_perso_bdd(
            f'UPDATE tracker SET "R" = :rouge, "G" = :vert, "B" = :bleu WHERE index = :index', params)

        await ctx.send(f' La couleur du joueur {summonername} a été modifiée.')

    @interactions.extension_command(name="abbedagge", description="Meilleur joueur de LoL")
    async def abbedagge(self, ctx):
        await ctx.send('https://clips.twitch.tv/ShakingCovertAuberginePanicVis-YDRK3JFk7Glm6nbB')

    @interactions.extension_command(name="closer", description="Meilleur joueur de LoL")
    async def closer(self, ctx):
        await ctx.send('https://clips.twitch.tv/EmpathicClumsyYogurtKippa-lmcFoGXm1U5Jx2bv')

    @interactions.extension_command(name="upset", description="Meilleur joueur de LoL")
    async def upset(self, ctx):
        await ctx.send('https://clips.twitch.tv/CuriousBenevolentMageHotPokket-8M0TX_zTaGW7P2g7')

    @interactions.extension_command(name='lol_discord',
                                    description='Link discord et lol',
                                    options=[
                                        Option(
                                            name='summonername',
                                            description='pseudo lol',
                                            type=interactions.OptionType.STRING,
                                            required=True),
                                        Option(
                                            name='member',
                                            description='compte discord',
                                            type=interactions.OptionType.USER,
                                            required=True
                                        )])
    async def link(self,
                   ctx: CommandContext,
                   summonername,
                   member: interactions.User):

        summonername = summonername.lower()
        requete_perso_bdd('UPDATE tracker SET discord = :discord, server_id = :guild WHERE index = :summonername', {
                          'discord': int(member.id), 'server_id': int(ctx.guild.id), 'summonername': summonername})
        await ctx.send(f'Le compte LoL {summonername} a été link avec <@{int(member.id)}>')


def setup(bot):
    LeagueofLegends(bot)
