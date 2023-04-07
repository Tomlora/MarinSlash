import os
import sys
import aiohttp
import pandas as pd
import datetime
import warnings
import interactions
from interactions import Option, Extension, CommandContext
from interactions.ext.tasks import IntervalTrigger, create_task
from interactions.ext.wait_for import wait_for_component, setup as stp
from fonctions.params import Version, saison, heure_lolsuivi
from fonctions.channels_discord import verif_module
from cogs.recordslol import emote_v2
from fonctions.permissions import isOwner_slash
from fonctions.gestion_challenge import challengeslol



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
                             get_summoner_by_name,
                             trouver_records,
                             label_rank,
                             label_tier,
                             get_spectator_data
                             )
from fonctions.channels_discord import chan_discord, rgb_to_discord

from time import sleep

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
    category_exclusion_egalite = ['baron', 'herald', 'drake']

    if result_category_match == 0:  # si le score est de 0, inutile
        return embed

    # Record sur tous les joueurs
    if fichier.shape[0] > 0:  # s'il y a des données, sinon first record
        joueur, champion, record, url = trouver_records(
            fichier, category, methode, identifiant='discord')

        if methode == 'max':
            if float(record) < float(result_category_match):
                embed += f"\n ** :boom: Record - {emote_v2.get(category, ':star:')}__{category}__ : {result_category_match} ** (Ancien : {record} par {joueur} ({champion}))"
        else:
            if float(record) > float(result_category_match):
                embed += f"\n ** :boom: Record - {emote_v2.get(category, ':star:')}__{category}__ : {result_category_match} ** (Ancien : {record} par {joueur} ({champion}))"

        if float(record) == float(result_category_match) and not category in category_exclusion_egalite:  # si égalité
            embed += f"\n ** :medal: Egalisation record - {emote_v2.get(category, ':star:')}__{category}__ de {joueur} **"
    else:
        embed += f"\n ** :boom: Premier Record - {emote_v2.get(category, ':star:')}__{category}__ : {result_category_match} **"

    # Record sur ses stats personnels
    if isinstance(fichier_joueur, pd.DataFrame):
        # s'il y a des données, sinon first record
        if fichier_joueur.shape[0] > 0:
            joueur_perso, champion_perso, record_perso, url = trouver_records(
                fichier_joueur, category, methode)

            if methode == 'max':
                if float(record_perso) < float(result_category_match):
                    embed += f"\n ** :military_medal: Record personnel - {emote_v2.get(category, ':star:')}__{category.lower()}__ : {result_category_match} ** (Ancien : {record_perso})"
            else:
                if float(record_perso) > float(result_category_match):
                    embed += f"\n ** :military_medal: Record personnel - {emote_v2.get(category, ':star:')}__{category.lower()}__ : {result_category_match} ** (Ancien : {record_perso})"


            if float(record_perso) == float(result_category_match) and not category in category_exclusion_egalite:
                embed += f"\n ** :medal: Egalisation record personnel - {emote_v2.get(category, ':star:')}__{category}__ **"

        # else:
        #     embed += f"\n ** :military_medal: Premier Record personnel - {emote_v2.get(category, ':star:')}__{category}__ : {result_category_match} **"

    # Record sur les champions
    if isinstance(fichier_champion, pd.DataFrame):
        # s'il y a des données, sinon first record
        if fichier_champion.shape[0] > 0:
            joueur_champion, champion_champion, record_champion, url = trouver_records(
                fichier_champion, category, methode, identifiant='discord')

            if methode == 'max':
                if float(record_champion) < float(result_category_match):
                    embed += f"\n ** :rocket: Record sur {champion_champion} - {emote_v2.get(category, ':star:')}__{category.lower()}__ : {result_category_match} ** (Ancien : {record_champion} par {joueur_champion})"
            else:
                if float(record_champion) > float(result_category_match):
                    embed += f"\n ** :rocket: Record sur {champion_champion} - {emote_v2.get(category, ':star:')}__{category.lower()}__ : {result_category_match} ** (Ancien : {record_champion} par {joueur_champion})"
        # else:
        #     embed += f"\n ** :rocket: Premier Record sur le champion - {emote_v2.get(category, ':star:')}__{category}__ : {result_category_match} **"

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
                        sauvegarder: bool,
                        identifiant_game=None,
                        guild_id: int = 0,
                        me=None,
                        insights:bool=True):

        match_info = matchlol(summonerName,
                              idgames,
                              identifiant_game=identifiant_game,
                              me=me)  # class

        await match_info.get_data_riot()
        await match_info.prepare_data()

        # pour nouveau système de record
        fichier = lire_bdd_perso(f'''SELECT distinct matchs.*, tracker.discord from matchs
                         INNER JOIN tracker ON tracker.index = matchs.joueur
                         where season = {match_info.season}
                         and mode = '{match_info.thisQ}'
                         and server_id = {guild_id}''',
                         index_col='id'
                         ).transpose()

        fichier_joueur = lire_bdd_perso(f'''SELECT distinct matchs.*, tracker.discord from matchs
                                        INNER JOIN tracker on tracker.index = matchs.joueur
                                        where season = {match_info.season}
                                        and mode = '{match_info.thisQ}'
                                        and discord = (SELECT tracker.discord from tracker WHERE tracker.index = '{summonerName.lower()}')
                                        and server_id = {guild_id}''',
                                        index_col='id',
                                        ).transpose()

        fichier_champion = lire_bdd_perso(f'''SELECT distinct matchs.*, tracker.discord from matchs
                                          INNER JOIN tracker on tracker.index = matchs.joueur
                                        where season = {match_info.season}
                                        and mode = '{match_info.thisQ}'
                                        and champion = '{match_info.thisChampName}'
                                        and server_id = {guild_id}''',
                                          index_col='id',
                                        ).transpose()

        if sauvegarder and match_info.thisTime >= 10.0:
            await match_info.save_data()

        if match_info.thisQId == 900:  # urf
            return {}, 'URF', 0, 

        if match_info.thisQId == 840:
            return {}, 'Bot', 0,   # bot game

        if match_info.thisTime <= 3.0:
            return {}, 'Remake', 0, 

        

        exploits = ''

        # Suivi

        suivi = lire_bdd(f'suivi_s{saison}', 'dict')

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
        if (match_info.thisQ in ['RANKED', 'FLEX'] and match_info.thisTime > 20) or (match_info.thisQ == "ARAM" and match_info.thisTime > 10):

            records = lire_bdd_perso(f'''SELECT index, "Score", "Champion", "Joueur", url from records where saison= {match_info.season} and mode= '{match_info.thisQ.lower()}' ''')
            records = records.to_dict()

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
                             'gold_share' : match_info.gold_share,
                             'ecart_gold_team' : match_info.ecart_gold_team,
                             'kills+assists' : match_info.thisKills + match_info.thisAssists}

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
                                         'herald': match_info.thisHeraldTeam,
                                         'cs_jungle': match_info.thisJungleMonsterKilled}

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
                    if parameter in ['early_drake', 'early_baron']:
                        methode = 'min'

                    # on ne veut pas les records par champion sur ces stats.
                    if parameter in ['baron', 'drake', 'herald']:
                        exploits += records_check2(fichier, fichier_joueur,
                                                   None, parameter, value, methode)
                    else:
                        exploits += records_check2(fichier, fichier_joueur,
                                                   fichier_champion, parameter, value, methode)

            if match_info.thisQ == 'ARAM':  # seulement en aram
                for parameter, value in param_records_only_aram.items():

                    exploits, chunk = check_chunk(exploits, chunk, chunk_size)

                    methode = 'max'

                    exploits += records_check2(fichier, fichier_joueur,
                                               fichier_champion, parameter, value, methode)



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
        else:  # couronnes si autre mode de jeu
            settings = lire_bdd_perso(
                f'SELECT index, score as score from achievements_settings')

        settings = settings.to_dict()

        # Couronnes

        couronnes_embed = ''

        # pour only ranked/normal game
        if match_info.thisQ in ['RANKED', 'NORMAL', 'FLEX']:
            if int(match_info.thisLevelAdvantage) >= settings['Ecart_Level']['score']:
                couronnes_embed +=\
                    f"\n ** :crown: :wave: {match_info.thisLevelAdvantage} niveaux d'avance sur ton adversaire durant la game**"
                points += 1

            if (float(match_info.thisVisionAdvantage) >= settings['Avantage_vision(support)']['score'] and str(match_info.thisPosition) == "SUPPORT") or (float(match_info.thisVisionAdvantage) >= settings['Avantage_vision(autres)']['score'] and str(match_info.thisPosition) != "SUPPORT"):
                couronnes_embed +=\
                    f"\n ** :crown: :eye: Avantage de vision sur son adversaire avec {match_info.thisVisionAdvantage}% **"
                points += 1

            if (float(match_info.thisDragonTeam) >= settings['Dragon']['score']):
                couronnes_embed += f"\n ** :crown: :dragon: Âme du dragon **"
                points += 1

            if (int(match_info.thisDanceHerald) >= 1):
                couronnes_embed += f"\n ** :crown: :dancer: Danse avec l'Herald **"
                points += 1

            if (int(match_info.thisPerfectGame) >= 1):
                couronnes_embed += f"\n :crown: :crown: :sunny: Perfect Game"
                points += 2

            if int(match_info.thisDeaths) == int(settings['Ne_pas_mourir']['score']):
                couronnes_embed += "\n ** :crown: :heart: N'est pas mort de la game ** \n ** :crown: :star: PERFECT KDA **"
                points += 2

            if float(match_info.thisVisionPerMin) >= settings['Vision/min(support)']['score'] and str(match_info.thisPosition) == "SUPPORT":
                couronnes_embed +=\
                    f"\n ** :crown: :eye: Gros score de vision avec {match_info.thisVisionPerMin} / min **"
                points += 1

            if int(match_info.thisVisionPerMin) >= settings['Vision/min(autres)']['score'] and str(match_info.thisPosition) != "SUPPORT":
                couronnes_embed +=\
                    f"\n ** :crown: :eye: Gros score de vision avec {match_info.thisVisionPerMin} / min **"
                points += 1

            if int(match_info.thisSoloKills) >= settings['Solokills']['score']:
                couronnes_embed +=\
                    f"\n ** :crown: :muscle: {match_info.thisSoloKills} solokills **"
                points += 1

            if int(match_info.thisCSAdvantageOnLane) >= settings['CSAvantage']['score']:
                couronnes_embed +=\
                    f"\n ** :crown: :ghost: {match_info.thisCSAdvantageOnLane} CS d'avance sur ton adversaire durant la game**"
                points += 1

        # pour tous les modes
        if float(match_info.thisKDA) >= settings['KDA']['score']:
            couronnes_embed +=\
                f"\n ** :crown: :star: Bon KDA : {match_info.thisKDA} **"
            points += 1

        if int(match_info.thisKP) >= settings['KP']['score']:
            couronnes_embed +=\
                f"\n ** :crown: :dagger: Participation à beaucoup de kills : {match_info.thisKP} % **"
            points += 1

        if int(match_info.thisPenta) >= settings['Pentakill']['score']:
            couronnes_embed +=\
                f"\n ** :crown: :five: Pentakill ** {match_info.thisPenta} fois"
            points += (1 * int(match_info.thisPenta))

        if int(match_info.thisQuadra) >= settings['Quadrakill']['score']:
            couronnes_embed +=\
                f"\n ** :crown: :four: Quadrakill ** {match_info.thisQuadra} fois"
            points += (1 * int(match_info.thisQuadra))

        if int(match_info.thisMinionPerMin) >= settings['CS/min']['score']:
            couronnes_embed +=\
                f"\n ** :crown: :ghost: {match_info.thisMinionPerMin} CS / min **"
            points += 1

        if int(match_info.thisDamageRatio) >= settings['%_dmg_équipe']['score']:
            couronnes_embed +=\
                f"\n ** :crown: :dart: Beaucoup de dmg avec {match_info.thisDamageRatio}% **"
            points += 1

        if int(match_info.thisDamageTakenRatio) >= settings['%_dmg_tank']['score']:
            couronnes_embed +=\
                f"\n ** :crown: :shield: Bon tanking : {match_info.thisDamageTakenRatio}% **"
            points += 1

        if int(match_info.thisTotalOnTeammates) >= settings['Total_Heals_sur_alliés']['score']:
            couronnes_embed +=\
                f"\n ** :crown: :heart: Heal plus de {match_info.thisTotalOnTeammatesFormat} sur ses alliés **"
            points += 1

        if (int(match_info.thisTotalShielded) >= settings['Shield']['score']):
            couronnes_embed +=\
                f"\n ** :crown: :shield: Shield : {match_info.thisTotalShielded} **"
            points += 1
            

        if (match_info.thisQ == 'RANKED' and match_info.thisTime > 20) or\
                (match_info.thisQ == "ARAM" and match_info.thisTime > 10):
            # Le record de couronne n'est disponible qu'en ranked / aram
            exploits += records_check2(
                fichier, fichier_joueur, fichier_champion, 'couronne', points, exploits)

        if (match_info.thisQ in ['RANKED', 'NORMAL', 'FLEX'] and match_info.thisTime > 20) or\
                (match_info.thisQ == "ARAM" and match_info.thisTime > 10):
            # on ajoute les couronnes pour les modes ranked, normal, aram
            await match_info.add_couronnes(points)

        # Présence d'afk
        if match_info.AFKTeam >= 1:
            exploits = exploits + \
                "\n ** :tired_face: Tu as eu un afk dans ton équipe :'( **"

        # Série de victoire
        if match_info.thisWinStreak == "True" and match_info.thisQ == "RANKED" and match_info.thisTime > 20:
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

        sauvegarde_bdd(suivi, f'suivi_s{saison}')  # achievements + suivi
        
        # badges
        
        if insights:
            await match_info.calcul_badges()
        else:
            match_info.observations = ''

        # observations

        # ici, ça va de 1 à 10.. contrairement à Rito qui va de 1 à 9
        embed.add_field(
            name="Game", value=f"[Graph]({match_info.url_game}) | [OPGG](https://euw.op.gg/summoners/euw/{summonerName}) ", inline=True)
    
        embed.add_field(
            name='Champ', value=f"[{match_info.thisChampName}](https://lolalytics.com/lol/{match_info.thisChampName.lower()}/build/)", inline=True)
        
        # on va chercher les stats du joueur:
        
        if match_info.thisQ == 'ARAM':
            time = 10
        else:
            time = 15
        
        stats_joueur = lire_bdd_perso(f'''SELECT joueur, avg(kills) as kills, avg(deaths) as deaths, avg(assists) as assists, 
                    (count(victoire) filter (where victoire = True)) as victoire,
                    avg(kp) as kp,
                    count(victoire) as nb_games,
                    (avg(mvp) filter (where mvp != 0)) as mvp
                    from matchs WHERE joueur = '{match_info.summonerName.lower()}'
                    and champion = '{match_info.thisChampName}'
                    and season = {saison}
                    and mode = '{match_info.thisQ}'
                    and time > {time}
                    GROUP BY joueur''', index_col='joueur').transpose()
        

        if not stats_joueur.empty:

            k = round(stats_joueur.loc[match_info.summonerName.lower(), 'kills'],1)
            d = round(stats_joueur.loc[match_info.summonerName.lower(), 'deaths'],1)
            a = round(stats_joueur.loc[match_info.summonerName.lower(), 'assists'],1)
            kp = int(stats_joueur.loc[match_info.summonerName.lower(), 'kp'])
            mvp = round(stats_joueur.loc[match_info.summonerName.lower(), 'mvp'],1)
            ratio_victoire = int((stats_joueur.loc[match_info.summonerName.lower(), 'victoire'] / stats_joueur.loc[match_info.summonerName.lower(), 'nb_games'])*100)
            nb_games = int(stats_joueur.loc[match_info.summonerName.lower(), 'nb_games'])
            embed.add_field(
                name=f"{nb_games} P ({ratio_victoire}% V) | {mvp} MVP ", value=f"{k} / {d} / {a} ({kp}% KP)", inline=True)
            
        
        # on découpe le texte embed
        chunk_size = 1024
        max_len = 4000

        if exploits == '':  # si l'exploit est vide, il n'y a aucun exploit
            embed.add_field(name="Durée de la game : " + str(int(match_info.thisTime)) + " minutes",
                            value=f'Aucun exploit', inline=False)

        elif len(exploits) <= chunk_size:
            exploits = exploits.replace('#', '').replace(' #', '')
            embed.add_field(name="Durée de la game : " + str(int(match_info.thisTime)) + " minutes",
                            value=exploits, inline=False)

        # si l'exploit est trop grand pour l'embed à partir de 6000... mais déjà 4000, c'est peu lisible :
        elif len(exploits) > max_len:
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
                name=f'Durée de la game : {int(match_info.thisTime)} minutes', value=exploits)

        else:  # si l'embed nécessite plusieurs fields, et est inférieur à la longueur max de l'embed
            exploits = exploits.split('#')  # on split sur notre mot clé

            for i in range(len(exploits)):
                if i == 0:
                    field_name = "Durée de la game : " + \
                        str(int(match_info.thisTime)) + " minutes"
                else:
                    field_name = f"Records {i + 1}"
                field_value = exploits[i]
                # parfois la découpe renvoie un espace vide.
                if not field_value in ['', ' ']:
                    embed.add_field(name=field_name,
                                    value=field_value, inline=False)

        if points >= 1:
            embed.add_field(name='Couronnes', value=couronnes_embed)
            
        if match_info.observations != '':
            embed.add_field(name='Insights', value=match_info.observations)
            
        # Gestion de l'image 

        embed = await match_info.resume_general('resume', embed, difLP)

        # on charge les img

        resume = interactions.File('resume.png')
        embed.set_image(url='attachment://resume.png')

        if sauvegarder:
            embed.set_footer(
                text=f'Version {Version} by Tomlora - Match {str(match_info.last_match)} - Sauvegardé')
        else:
            embed.set_footer(
                text=f'Version {Version} by Tomlora - Match {str(match_info.last_match)}')
        return embed, match_info.thisQ, resume

    async def updaterank(self, key, discord_server_id, session: aiohttp.ClientSession, me=None):

        suivirank = lire_bdd(f'suivi_s{saison}', 'dict')

        if me == None:
            me = await get_summoner_by_name(session, key)

        stats = await get_league_by_summoner(session, me)

        if len(stats) > 0:
            i = 0 if stats[0]['queueType'] == 'RANKED_SOLO_5x5' else 1

            rank_old = f"{suivirank[key]['tier']} {suivirank[key]['rank']}"
            rank = f"{stats[i]['tier']} {stats[i]['rank']}"
            if rank_old != rank:

                try:
                    channel_tracklol = await interactions.get(client=self.bot,
                                                              obj=interactions.Channel,
                                                              object_id=discord_server_id.tracklol)
                    if dict_rankid[rank_old] > dict_rankid[rank]:  # 19 > 18
                        await channel_tracklol.send(f' Le joueur **{key}** a démote du rank **{rank_old}** à **{rank}**')
                        await channel_tracklol.send(files=interactions.File('./img/notstonks.jpg'))
                    elif dict_rankid[rank_old] < dict_rankid[rank]:
                        await channel_tracklol.send(f' Le joueur **{key}** a été promu du rank **{rank_old}** à **{rank}**')
                        await channel_tracklol.send(files=interactions.File('./img/stonks.jpg'))

                except:
                    print('Channel impossible')
                    print(sys.exc_info())

                requete_perso_bdd(f'UPDATE suivi_s{saison} SET tier = :tier, rank = :rank where index = :joueur', {'tier': stats[i]['tier'],
                                                                                                                   'rank': stats[i]['rank'],
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
                   sauvegarder: bool = True,
                   identifiant_game=None):

        await ctx.defer(ephemeral=False)

        summonername = summonername.lower()
        

        embed, mode_de_jeu, resume= await self.printInfo(summonerName=summonername.lower(),
                                                                           idgames=numerogame,
                                                                           sauvegarder=sauvegarder,
                                                                           identifiant_game=identifiant_game,
                                                                           guild_id=int(ctx.guild_id))

        if embed != {}:
            await ctx.send(embeds=embed, files=resume)
            os.remove('resume.png')


    @interactions.extension_command(name="game_multi",
                                    description="Voir les statistiques d'une games",
                                    options=[Option(name="summonername",
                                                    description="Nom du joueur",
                                                    type=interactions.OptionType.STRING,
                                                    required=True),
                                             Option(name="debut",
                                                    description="Numero de la game, de 0 à 100 (Game la plus recente)",
                                                    type=interactions.OptionType.INTEGER,
                                                    required=True),
                                             Option(name="fin",
                                                    description="Numero de la game, de 0 à 100 (Game la moins recente)",
                                                    type=interactions.OptionType.INTEGER,
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
                         sauvegarder: bool = True):

        await ctx.defer(ephemeral=False)

        for i in range(fin, debut, -1):

            summonername = summonername.lower()

            embed, mode_de_jeu, resume= await self.printInfo(summonerName=summonername.lower(),
                                                                               idgames=i,
                                                                               sauvegarder=sauvegarder,
                                                                               guild_id=int(ctx.guild_id))

            if embed != {}:
                await ctx.send(embeds=embed, files=resume)
            else:
                await ctx.send(f"La game {str(i)} n'a pas été comptabilisée")

            sleep(5)

    async def printLive(self,
                        summonername,
                        discord_server_id: chan_discord,
                        me=None,
                        identifiant_game=None,
                        tracker_challenges=False,
                        session=None,
                        insights=True):

        summonername = summonername.lower()

        embed, mode_de_jeu, resume= await self.printInfo(summonerName=summonername,
                                                                           idgames=0,
                                                                           sauvegarder=True,
                                                                           guild_id=discord_server_id.server_id,
                                                                           identifiant_game=identifiant_game,
                                                                           me=me,
                                                                           insights=insights)
        
        if tracker_challenges:
            chal = challengeslol(summonername.replace(' ', ''), me['puuid'], session)
            await chal.preparation_data()
            await chal.comparaison()
            
            embed = await chal.embedding_discord(embed)
            await chal.sauvegarde()
        

        if mode_de_jeu in ['RANKED', 'FLEX']:
            tracklol = discord_server_id.tracklol
        else:
            tracklol = discord_server_id.lol_others

        channel_tracklol = await interactions.get(client=self.bot,
                                                      obj=interactions.Channel,
                                                      object_id=tracklol)

        if embed != {}:
            await channel_tracklol.send(embeds=embed, files=resume)
            os.remove('resume.png')


    async def update(self):

        data = get_data_bdd(f'''SELECT tracker.index, tracker.id, tracker.server_id, tracker.spec_tracker, tracker.spec_send, tracker.discord, tracker.puuid, tracker.challenges, tracker.insights
                            from tracker 
                            INNER JOIN channels_module on tracker.server_id = channels_module.server_id
                            where tracker.activation = true and channels_module.league_ranked = true''').fetchall()
        timeout = aiohttp.ClientTimeout(total=20)
        session = aiohttp.ClientSession(timeout=timeout)

        for summonername, last_game, server_id, tracker_bool, tracker_send, discord_id, puuid, tracker_challenges, insights in data:

            id_last_game = await getId_with_puuid(puuid, session)
            
            if str(last_game) != id_last_game:  # value -> ID de dernière game enregistrée dans id_data != ID de la dernière game via l'API Rito / #key = pseudo // value = numéro de la game
                # update la bdd

                requete_perso_bdd(f'UPDATE tracker SET id = :id, spec_send = :spec WHERE index = :index', {
                                  'id': id_last_game, 'index': summonername, 'spec': False})
                
                
                
                me = await get_summoner_by_puuid(puuid, session)
                
                name_actuelle = me['name'].lower().replace(' ', '')
                
                # Changement de pseudo ?
                if name_actuelle != summonername:
                    requete_perso_bdd(f'''UPDATE tracker set index = :nouveau where index = :ancien;
                                
                                UPDATE suivi_s{saison} set index = :nouveau where index = :ancien;
                                
                                UPDATE suivi_s{saison-1} set index = :nouveau where index = :ancien;
                            
                                UPDATE suivi_24h set index = :nouveau where index = :ancien;
                            
                                UPDATE ranked_aram_s{saison} set index = :nouveau where index = :ancien;
                                
                                UPDATE ranked_aram_s{saison-1} set index = :nouveau where index = :ancien;
                            
                                UPDATE ranked_aram_24h set index = :nouveau where index = :ancien;
                                
                                UPDATE matchs set joueur = :nouveau where joueur = :ancien;''',
                              {'ancien': summonername, 'nouveau': name_actuelle})
                    
                    summonername = name_actuelle
                try:

                    # identification du channel
                    discord_server_id = chan_discord(int(server_id))

                    # résumé de game

                    await self.printLive(summonername,
                                         discord_server_id,
                                         me,
                                         identifiant_game=id_last_game,
                                         tracker_challenges=tracker_challenges,
                                         session=session,
                                         insights=insights)

                    # update rank
                    await self.updaterank(summonername, discord_server_id, session, me)
                except TypeError:
                    # on recommence dans 1 minute
                    requete_perso_bdd(f'UPDATE tracker SET id = :id WHERE index = :index', {
                                  'id': last_game, 'index': summonername})
                    print(f"erreur TypeError {summonername}")  # joueur qui a posé pb
                    print(sys.exc_info())  # erreur
                    continue
                except:
                    print(f"erreur {summonername}")  # joueur qui a posé pb
                    print(sys.exc_info())  # erreur
                    continue
                
            if tracker_bool and not tracker_send:
                try:
                    url, gamemode, id_game, champ_joueur, icon = await get_spectator_data(puuid, session)
                    
                    url_opgg = f'https://www.op.gg/summoners/euw/{summonername}/ingame'
                    
                    league_of_graph = f'https://porofessor.gg/fr/live/euw/{summonername}'
                    
                    if url != None:
                        member : interactions.Member = await interactions.get(self.bot,
                                                        interactions.Member,
                                                        object_id = discord_id,
                                                        parent_id = server_id)
                        
                        if id_last_game != str(id_game):
                            embed = interactions.Embed(title=f'{summonername.upper()} : Analyse de la game prête !')
                            
                            embed.add_field(name='Mode de jeu', value=gamemode)
                            
                            embed.add_field(name='OPGG', value=f"[General]({url_opgg}) | [Detail]({url}) ")
                            embed.add_field(name='League of Graph', value=f"[{summonername.upper()}]({league_of_graph})")
                            embed.add_field(name='Lolalytics', value=f'[{champ_joueur.capitalize()}](https://lolalytics.com/lol/{champ_joueur}/build/)')
                            embed.set_thumbnail(url=icon)
                            
                            await member.send(embeds=embed)
                        
                            requete_perso_bdd(f'UPDATE tracker SET spec_send = :spec WHERE index = :index', {
                                        'spec': True, 'index': summonername})
                except TypeError:
                    continue
                except:
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
                summonername = summonername.lower().replace(' ', '')
                session = aiohttp.ClientSession()
                me = await get_summoner_by_name(summonername, session)
                puuid = me['puuid']
                requete_perso_bdd(f'''
                                  
                                INSERT INTO tracker(index, id, discord, server_id, puuid) VALUES (:summonername, :id, :discord, :guilde, :puuid);
                                
                                INSERT INTO suivi_s{saison}(
                                index, wins, losses, "LP", tier, rank, serie)
                                VALUES (:summonername, 0, 0, 0, 'Non-classe', 0, 0);
                            
                                INSERT INTO suivi_24h(
                                index, wins, losses, "LP", tier, rank, serie)
                                VALUES (:summonername, 0, 0, 0, 'Non-classe', 0, 0);
                            
                                INSERT INTO ranked_aram_s{saison}(
                                index, wins, losses, lp, games, k, d, a, activation, rank)
                                VALUES (:summonername, 0, 0, 0, 0, 0, 0, 0, True, 'IRON');
                            
                                INSERT INTO ranked_aram_24h(
                                index, wins, losses, lp, games, k, d, a, activation, rank)
                                VALUES (:summonername, 0, 0, 0, 0, 0, 0, 0, True, 'IRON');''',
                                  {'summonername': summonername.lower(), 'id': await getId_with_puuid(puuid, session), 'discord': int(ctx.author.id), 'guilde': int(ctx.guild.id), 'puuid' : puuid})

                await ctx.send(f"{summonername} a été ajouté avec succès au live-feed!")
                await session.close()
            else:
                await ctx.send('Module désactivé pour ce serveur')
        except:
            await ctx.send("Oops! Ce joueur n'existe pas.")
            
            

    @interactions.extension_command(name='tracker', description='Activation/Désactivation du tracker',
                                    options=[
                                        Option(name='summonername',
                                                    description="nom ingame",
                                                    type=interactions.OptionType.STRING,
                                                    required=True),
                                        Option(name="tracker_fin",
                                                    description="Tracker qui affiche le recap de la game en fin de partie",
                                                    type=interactions.OptionType.BOOLEAN,
                                                    required=False),
                                        Option(name="tracker_debut",
                                                    description="Tracker en début de partie",
                                                    type=interactions.OptionType.BOOLEAN,
                                                    required=False),
                                        Option(name="tracker_challenges",
                                                    description="Tracker challenges",
                                                    type=interactions.OptionType.BOOLEAN,
                                                    required=False),
                                        Option(name="insights",
                                                    description="Insights dans le recap",
                                                    type=interactions.OptionType.BOOLEAN,
                                                    required=False)])
    async def lolremove(self,
                        ctx: CommandContext,
                        summonername: str,
                        tracker_fin: bool=None,
                        tracker_debut: bool=None,
                        tracker_challenges: bool=None,
                        insights: bool=None):

        summonername = summonername.lower()

        if tracker_fin != None:
            try:
                requete_perso_bdd('UPDATE tracker SET activation = :activation WHERE index = :index', {
                                'activation': tracker_fin, 'index': summonername})
                if tracker_fin:
                    await ctx.send('Tracker fin de game activé !')
                else:
                    await ctx.send('Tracker fin de game désactivé !')
            except KeyError:
                await ctx.send('Joueur introuvable')

        if tracker_debut != None:
            try:
                requete_perso_bdd('UPDATE tracker SET spec_tracker = :activation WHERE index = :index', {
                                'activation': tracker_debut, 'index': summonername})
                if tracker_debut:
                    await ctx.send('Tracker debut de game activé !')
                else:
                    await ctx.send('Tracker debut de game désactivé !')
            except KeyError:
                await ctx.send('Joueur introuvable')
                
        if tracker_challenges != None:
            try:
                requete_perso_bdd('UPDATE tracker SET challenges = :activation WHERE index = :index', {
                                'activation': tracker_challenges, 'index': summonername})
                if tracker_challenges:
                    await ctx.send('Tracker challenges activé !')
                else:
                    await ctx.send('Tracker challenges désactivé !')
            except KeyError:
                await ctx.send('Joueur introuvable')
        
        if insights != None:
            try:
                requete_perso_bdd('UPDATE tracker SET insights = :activation WHERE index = :index', {
                                'activation': insights, 'index': summonername})
                if insights:
                    await ctx.send('Insights activé !')
                else:
                    await ctx.send('Insights désactivé !')
            except KeyError:
                await ctx.send('Joueur introuvable')
        
        if tracker_fin == None and tracker_debut == None and tracker_challenges == None and insights == None:
            await ctx.send('Tu dois choisir une option !')


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
            title="Live feed list", description=response, color=interactions.Color.BLURPLE)

        await ctx.send(embeds=embed)
        


        
        
    async def update_24h(self):
        data = get_data_bdd(f'''SELECT DISTINCT tracker.server_id from tracker 
                    INNER JOIN channels_module on tracker.server_id = channels_module.server_id
                    where channels_module.league_ranked = true''').fetchall()

        for server_id in data:

            guild = await interactions.get(client=self.bot,
                                               obj=interactions.Guild,
                                               object_id=server_id[0])

            chan_discord_id = chan_discord(int(guild.id))

            # le suivi est déjà maj par game/update... Pas besoin de le refaire ici..

            df = lire_bdd_perso(f'''SELECT suivi.index, suivi.wins, suivi.losses, suivi."LP", suivi.tier, suivi.rank, tracker.server_id from suivi_s{saison} as suivi
                                    INNER join tracker ON tracker.index = suivi.index 
                                    where suivi.tier != 'Non-classe' and tracker.server_id = {int(guild.id)} ''')
            df_24h = lire_bdd_perso(f'''SELECT suivi.index, suivi.wins, suivi.losses, suivi."LP", suivi.tier, suivi.rank, tracker.server_id from suivi_24h as suivi
                                    INNER join tracker ON tracker.index = suivi.index 
                                    and tracker.server_id = {int(guild.id)} ''')

            if df.shape[1] > 0:  # si pas de data, inutile de continuer

                df = df.transpose().reset_index()
                df_24h = df_24h.transpose().reset_index()



                    # Pour l'ordre de passage
                df['tier_pts'] = df['tier'].apply(label_tier)
                df['rank_pts'] = df['rank'].apply(label_rank)

                df.sort_values(by=['tier_pts', 'rank_pts', 'LP'],
                                   ascending=[False, False, False],
                                   inplace=True)

                sql = ''

                suivi = df.set_index('index').transpose().to_dict()
                suivi_24h = df_24h.set_index('index').transpose().to_dict()

                joueur = suivi.keys()

                embed = interactions.Embed(
                        title="Suivi LOL", description='Periode : 24h', color=interactions.Color.BLURPLE)
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
                        if not classement_old in ['MASTER I', 'GRANDMASTER I', 'CHALLENGER I']:
                            difLP = 100 + LP - int(suivi[key]['LP']) # il n'y a pas -100 lp pour ce type de démote
                        difLP = "Démote / -" + str(difLP)
                        emote = ":arrow_down:"

                    elif dict_rankid[classement_old] < dict_rankid[classement_new]:
                        if not classement_old in ['MASTER I', 'GRANDMASTER I', 'CHALLENGER I']:
                            difLP = 100 - LP + int(suivi[key]['LP']) # il n'y a pas +100 lp pour ce type de démote
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
                            sql += f'''UPDATE suivi_24h
                            SET wins = {suivi[key]['wins']},
                            losses = {suivi[key]['losses']},
                            "LP" = {suivi[key]['LP']},
                            tier = '{suivi[key]['tier']}',
                            rank = '{suivi[key]['rank']}'
                            where index = '{key}';'''

                channel_tracklol = await interactions.get(client=self.bot,
                                                              obj=interactions.Channel,
                                                              object_id=chan_discord_id.tracklol)

                embed.set_footer(text=f'Version {Version} by Tomlora')

                if sql != '':  # si vide, pas de requête
                    requete_perso_bdd(sql)

                if totalgames > 0:  # s'il n'y a pas de game, on ne va pas afficher le récap
                    await channel_tracklol.send(embeds=embed)
                    await channel_tracklol.send(f'Sur {totalgames} games -> {totalwin} victoires et {totaldef} défaites')

    async def lolsuivi(self):

        currentHour = str(datetime.datetime.now().hour)

        if currentHour == str(heure_lolsuivi):
            await self.update_24h()
            

    @interactions.extension_command(name="force_update24h",
                                    description="Réservé à Tomlora")
    async def force_update(self, ctx: CommandContext):


        await ctx.defer(ephemeral=False)
        
        if isOwner_slash(ctx):
            await self.update_24h()
        
        else:
            await ctx.send("Tu n'as pas l'autorisation nécessaire")
            

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
                                    description='Relie un compte discord et un compte league of legends',
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
                          'discord': int(member.id), 'guild': int(ctx.guild.id), 'summonername': summonername})
        await ctx.send(f'Le compte LoL {summonername} a été link avec <@{int(member.id)}>')


def setup(bot):
    LeagueofLegends(bot)
