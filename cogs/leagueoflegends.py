import os
import sys
import aiohttp
import pandas as pd
import warnings
import interactions
from interactions import SlashCommandOption, Extension, SlashContext, SlashCommandChoice, listen, slash_command, Task, IntervalTrigger, TimeTrigger
from fonctions.params import Version, saison
from fonctions.channels_discord import verif_module, identifier_role_by_name
from fonctions.match import emote_rank_discord, emote_champ_discord
from cogs.recordslol import emote_v2
from fonctions.permissions import isOwner_slash
from fonctions.gestion_challenge import challengeslol
import asyncio
from datetime import datetime, timedelta
from dateutil import tz
from interactions.ext.paginators import Paginator
import traceback


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
                        summonerName,
                        idgames: int,
                        sauvegarder: bool,
                        identifiant_game=None,
                        guild_id: int = 0,
                        me=None,
                        insights: bool = True,
                        affichage=1):

        match_info = matchlol(summonerName,
                              idgames,
                              identifiant_game=identifiant_game,
                              me=me)  # class

        await match_info.get_data_riot()


        if match_info.thisQId != 1700:  # urf
            await match_info.prepare_data()

        else:
            await match_info.prepare_data_arena()


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



        if sauvegarder and match_info.thisTime >= 10.0 and match_info.thisQ != 'ARENA 2v2' :
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
        except Exception:
            difLP = 0

        difLP = f'+{str(difLP)}' if difLP > 0 else str(difLP)
        if match_info.thisQ == "RANKED":  # si pas ranked, inutile car ça bougera pas

            suivi[summonerName.lower().replace(
                " ", "")]['wins'] = match_info.thisVictory
            suivi[summonerName.lower().replace(
                " ", "")]['losses'] = match_info.thisLoose
            suivi[summonerName.lower().replace(
                " ", "")]['LP'] = match_info.thisLP

        # on ne prend que les ranked > 20 min ou aram > 10 min
        if (match_info.thisQ in ['RANKED', 'FLEX'] and match_info.thisTime > 20) or (match_info.thisQ == "ARAM" and match_info.thisTime > 10):

            records = lire_bdd_perso(
                f'''SELECT index, "Score", "Champion", "Joueur", url from records where saison= {match_info.season} and mode= '{match_info.thisQ.lower()}' ''')
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
                             'gold_share': match_info.gold_share,
                             'ecart_gold_team': match_info.ecart_gold_team,
                             'kills+assists': match_info.thisKills + match_info.thisAssists,
                             'temps_avant_premiere_mort' : match_info.thisTimeLiving,
                             'dmg/gold' : match_info.DamageGoldRatio}

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
        elif match_info.thisQ == 'ARENA 2v2':
            embed = interactions.Embed(
                title=f"** {summonerName.upper()} ** vient de terminer ** {match_info.thisWin}ème ** en ARENA ", color=color)
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
        if match_info.thisQ != 'ARENA 2v2':
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
            if match_info.thisWinStreak == "True" and match_info.thisQ == "RANKED" and match_info.thisTime >= 15:
                # si égal à 0, le joueur commence une série avec 3 wins
                if suivi[summonerName.lower().replace(" ", "")]["serie"] == 0:
                    suivi[summonerName.lower().replace(" ", "")]["serie"] = 3
                else:  # si pas égal à 0, la série a déjà commencé
                    suivi[summonerName.lower().replace(
                        " ", "")]["serie"] = suivi[summonerName.lower().replace(" ", "")]["serie"] + 1

                serie_victoire = round(
                    suivi[summonerName.lower().replace(" ", "")]["serie"], 0)

                exploits = exploits + \
                        f"\n ** :fire: Série de victoire avec {serie_victoire} victoires**"

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

        time = 10 if match_info.thisQ == 'ARAM' else 15
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

            k = round(
                stats_joueur.loc[match_info.summonerName.lower(), 'kills'], 1)
            d = round(
                stats_joueur.loc[match_info.summonerName.lower(), 'deaths'], 1)
            a = round(
                stats_joueur.loc[match_info.summonerName.lower(), 'assists'], 1)
            kp = int(stats_joueur.loc[match_info.summonerName.lower(), 'kp'])
            mvp = round(
                stats_joueur.loc[match_info.summonerName.lower(), 'mvp'], 1)
            ratio_victoire = int((stats_joueur.loc[match_info.summonerName.lower(
            ), 'victoire'] / stats_joueur.loc[match_info.summonerName.lower(), 'nb_games'])*100)
            nb_games = int(
                stats_joueur.loc[match_info.summonerName.lower(), 'nb_games'])
            embed.add_field(
                name=f"{nb_games} P ({ratio_victoire}% V) | {mvp} MVP ", value=f"{k} / {d} / {a} ({kp}% KP)", inline=True)

        # on découpe le texte embed
        chunk_size = 1024
        max_len = 4000

        if exploits == '':  # si l'exploit est vide, il n'y a aucun exploit
            embed.add_field(
                name=f"Durée de la game : {str(int(match_info.thisTime))} minutes",
                value=f'Aucun exploit',
                inline=False,
            )

        elif len(exploits) <= chunk_size:
            exploits = exploits.replace('#', '').replace(' #', '')
            embed.add_field(
                name=f"Durée de la game : {str(int(match_info.thisTime))} minutes",
                value=exploits,
                inline=False,
            )

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
                field_name = (
                    f"Durée de la game : {str(int(match_info.thisTime))} minutes"
                    if i == 0
                    else f"Records {i + 1}"
                )
                field_value = exploits[i]
                # parfois la découpe renvoie un espace vide.
                if not field_value in ['', ' ']:
                    embed.add_field(name=field_name,
                                    value=field_value, inline=False)

        if match_info.thisQ != 'ARENA 2v2':
            if points >= 1:
                embed.add_field(name='Couronnes', value=couronnes_embed)

            if match_info.observations != '':
                embed.add_field(name='Insights', value=match_info.observations)

            # Gestion de l'image

            if affichage == 1:
                embed = await match_info.resume_general('resume', embed, difLP)

            elif affichage == 2:
                embed = await match_info.test('resume', embed, difLP)

        else:
            embed = await match_info.test_arena('resume', embed, difLP)

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

    async def updaterank(self,
                         key,
                         discord_server_id : chan_discord,
                         session: aiohttp.ClientSession,
                         me=None,
                         discord_id=None):

        suivirank = lire_bdd(f'suivi_s{saison}', 'dict')

        if me is None:
            me = await get_summoner_by_name(session, key)

        stats = await get_league_by_summoner(session, me)

        if len(stats) > 0:
   
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
                            await channel_tracklol.send(f'{emote_rank_discord[tier]} Le joueur **{key}** a démote du rank **{rank_old}** à **{rank}**')
                            await channel_tracklol.send(files=interactions.File('./img/notstonks.jpg'))
                        elif dict_rankid[rank_old] < dict_rankid[rank]:
                            await channel_tracklol.send(f'{emote_rank_discord[tier]}Le joueur **{key}** a été promu du rank **{rank_old}** à **{rank}**')
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
                       SlashCommandOption(name="summonername",
                                          description="Nom du joueur",
                                          type=interactions.OptionType.STRING, required=True),
                       SlashCommandOption(name="numerogame",
                                          description="Numero de la game, de 0 à 100",
                                          type=interactions.OptionType.INTEGER,
                                          required=True,
                                          min_value=0,
                                          max_value=100),
                       SlashCommandOption(name="sauvegarder",
                                          description="sauvegarder la game",
                                          type=interactions.OptionType.BOOLEAN,
                                          required=False),
                       SlashCommandOption(name="affichage",
                                          description="Mode d'affichage",
                                          type=interactions.OptionType.INTEGER,
                                          required=False,
                                          choices=[SlashCommandChoice(name="Affichage classique", value=1),
                                                   SlashCommandChoice(name="Affichage beta", value=2)]),
                       SlashCommandOption(name='identifiant_game',
                                          description="A ne pas utiliser",
                                          type=interactions.OptionType.STRING,
                                          required=False)])
    async def game(self,
                   ctx: SlashContext,
                   summonername: str,
                   numerogame: int,
                   sauvegarder: bool = False,
                   identifiant_game=None,
                   affichage=1):

        await ctx.defer(ephemeral=False)

        summonername = summonername.lower()

        embed, mode_de_jeu, resume = await self.printInfo(summonerName=summonername.lower(),
                                                          idgames=numerogame,
                                                          sauvegarder=sauvegarder,
                                                          identifiant_game=identifiant_game,
                                                          guild_id=int(
                                                              ctx.guild_id),
                                                          affichage=affichage)

        if embed != {}:
            await ctx.send(embeds=embed, files=resume)
            os.remove('resume.png')

    @slash_command(name="game_multi",
                   description="Voir les statistiques d'une games",
                   options=[SlashCommandOption(name="summonername",
                                               description="Nom du joueur",
                                               type=interactions.OptionType.STRING,
                                               required=True),
                            SlashCommandOption(name="debut",
                                               description="Numero de la game, de 0 à 100 (Game la plus recente)",
                                               type=interactions.OptionType.INTEGER,
                                               required=True),
                            SlashCommandOption(name="fin",
                                               description="Numero de la game, de 0 à 100 (Game la moins recente)",
                                               type=interactions.OptionType.INTEGER,
                                               required=True),
                            SlashCommandOption(name='sauvegarder',
                                               description='Sauvegarder les games',
                                               type=interactions.OptionType.BOOLEAN,
                                               required=False)])
    async def game_multi(self,
                         ctx: SlashContext,
                         summonername: str,
                         debut: int,
                         fin: int,
                         sauvegarder: bool = True):

        await ctx.defer(ephemeral=False)

        for i in range(fin, debut, -1):

            summonername = summonername.lower()

            embed, mode_de_jeu, resume = await self.printInfo(summonerName=summonername.lower(),
                                                              idgames=i,
                                                              sauvegarder=sauvegarder,
                                                              guild_id=int(ctx.guild_id))

            if embed != {}:
                await ctx.send(embeds=embed, files=resume)
            else:
                await ctx.send(f"La game {str(i)} n'a pas été comptabilisée")

            await asyncio.sleep(5)

    async def printLive(self,
                        summonername,
                        discord_server_id: chan_discord,
                        me=None,
                        identifiant_game=None,
                        tracker_challenges=False,
                        session=None,
                        insights=True,
                        nbchallenges=0,
                        affichage=1):

        summonername = summonername.lower()

        embed, mode_de_jeu, resume = await self.printInfo(summonerName=summonername,
                                                          idgames=0,
                                                          sauvegarder=True,
                                                          guild_id=discord_server_id.server_id,
                                                          identifiant_game=identifiant_game,
                                                          me=me,
                                                          insights=insights,
                                                          affichage=affichage)

        if tracker_challenges:
            chal = challengeslol(summonername.replace(
                ' ', ''), me['puuid'], session, nb_challenges=nbchallenges)
            await chal.preparation_data()
            await chal.comparaison()

            embed = await chal.embedding_discord(embed)

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

    @Task.create(IntervalTrigger(minutes=1))
    async def update(self):
        data = get_data_bdd(
            '''SELECT tracker.index, tracker.id, tracker.server_id, tracker.spec_tracker, tracker.spec_send, tracker.discord, tracker.puuid, tracker.challenges, tracker.insights, tracker.nb_challenges, tracker.affichage
                            from tracker 
                            INNER JOIN channels_module on tracker.server_id = channels_module.server_id
                            where tracker.activation = true and channels_module.league_ranked = true'''
        ).fetchall()
        timeout = aiohttp.ClientTimeout(total=20)
        session = aiohttp.ClientSession(timeout=timeout)

        for summonername, last_game, server_id, tracker_bool, tracker_send, discord_id, puuid, tracker_challenges, insights, nb_challenges, affichage in data:

            id_last_game = await getId_with_puuid(puuid, session)

            # value -> ID de dernière game enregistrée dans id_data != ID de la dernière game via l'API Rito / #key = pseudo // value = numéro de la game
            if str(last_game) != id_last_game:
                # update la bdd

                requete_perso_bdd(
                    'UPDATE tracker SET id = :id, spec_send = :spec WHERE index = :index',
                    {'id': id_last_game, 'index': summonername, 'spec': False},
                )

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
                                         insights=insights,
                                         nbchallenges=nb_challenges,
                                         affichage=affichage)

                    # update rank
                    await self.updaterank(summonername, discord_server_id, session, me, discord_id)
                except TypeError:
                    # on recommence dans 1 minute
                    requete_perso_bdd(
                        'UPDATE tracker SET id = :id WHERE index = :index',
                        {'id': last_game, 'index': summonername},
                    )
                    # joueur qui a posé pb
                    print(f"erreur TypeError {summonername}")
                    exc_type, exc_value, exc_traceback = sys.exc_info()
                    traceback_details = traceback.format_exception(exc_type, exc_value, exc_traceback)
                    traceback_msg = ''.join(traceback_details)
                    print(traceback_msg)
                    continue
                except Exception:
                    print(f"erreur {summonername}")  # joueur qui a posé pb
                    exc_type, exc_value, exc_traceback = sys.exc_info()
                    traceback_details = traceback.format_exception(exc_type, exc_value, exc_traceback)
                    traceback_msg = ''.join(traceback_details)
                    print(traceback_msg)
                    continue

            if tracker_bool and not tracker_send:
                try:
                    url, gamemode, id_game, champ_joueur, icon = await get_spectator_data(puuid, session)

                    url_opgg = f'https://www.op.gg/summoners/euw/{summonername}/ingame'

                    league_of_graph = f'https://porofessor.gg/fr/live/euw/{summonername}'

                    if url != None:

                        member = await self.bot.fetch_member(discord_id, server_id)

                        if id_last_game != str(id_game):
                            embed = interactions.Embed(
                                title=f'{summonername.upper()} : Analyse de la game prête !')

                            embed.add_field(name='Mode de jeu', value=gamemode)

                            embed.add_field(
                                name='OPGG', value=f"[General]({url_opgg}) | [Detail]({url}) ")
                            embed.add_field(
                                name='League of Graph', value=f"[{summonername.upper()}]({league_of_graph})")
                            embed.add_field(
                                name='Lolalytics', value=f'[{champ_joueur.capitalize()}](https://lolalytics.com/lol/{champ_joueur}/build/)')
                            embed.set_thumbnail(url=icon)

                            await member.send(embeds=embed)

                            requete_perso_bdd(
                                'UPDATE tracker SET spec_send = :spec WHERE index = :index',
                                {'spec': True, 'index': summonername},
                            )
                except TypeError:
                    continue
                except Exception:
                    continue
        await session.close()

    @slash_command(name='lol_compte', description='Gère ton compte League of Legends')
    async def lol_compte(self, ctx: SlashContext):
        pass

    @lol_compte.subcommand("add",
                           sub_cmd_description="Ajoute le joueur au suivi",
                           options=[
                               SlashCommandOption(name="summonername",
                                                  description="Nom du joueur",
                                                  type=interactions.OptionType.STRING,
                                                  required=True)])
    async def loladd(self,
                     ctx: SlashContext,
                     summonername):

        try:
            if verif_module('league_ranked', int(ctx.guild.id)):
                summonername = summonername.lower().replace(' ', '')
                session = aiohttp.ClientSession()
                me = await get_summoner_by_name(session, summonername)
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
                                  {'summonername': summonername.lower(), 'id': await getId_with_puuid(puuid, session), 'discord': int(ctx.author.id), 'guilde': int(ctx.guild.id), 'puuid': puuid})

                await ctx.send(f"{summonername} a été ajouté avec succès au live-feed!")
                await session.close()
            else:
                await ctx.send('Module désactivé pour ce serveur')
        except Exception:
            await ctx.send("Oops! Ce joueur n'existe pas.")

    @lol_compte.subcommand('mes_parametres',
                           sub_cmd_description='Affiche les paramètres du tracker pour mes comptes')
    async def tracker_mes_parametres(self,
                                     ctx: SlashContext):

        df = lire_bdd_perso(
            f'''SELECT index, activation, spec_tracker, challenges, insights, server_id, nb_challenges, affichage FROM tracker WHERE discord = '{int(ctx.author.id)}' ''').transpose()

        await ctx.defer(ephemeral=True)
        if df.empty:
            await ctx.send("Tu n'as pas encore ajouté de compte", ephemeral=True)
        else:
            txt = f'{df.shape[0]} comptes :'
            for joueur, data in df.iterrows():
                guild = await self.bot.fetch_guild(data['server_id'])

                if data['affichage'] == 1:
                    affichage = 'mode classique'
                elif data['affichage'] == 2:
                    affichage = 'mode beta'
                txt += f'\n**{joueur}** ({guild.name}): Tracking : **{data["activation"]}** ({affichage})  | Spectateur tracker : **{data["spec_tracker"]}** | Challenges : **{data["challenges"]}** (Affiché : {data["nb_challenges"]}) | Insights : **{data["insights"]}**'

            await ctx.send(txt, ephemeral=True)

        # Y a-t-il des challenges exclus ?

        df_exclusion = lire_bdd_perso(f'''SELECT challenge_exclusion.*, challenges.name from challenge_exclusion
                            INNER join tracker on challenge_exclusion.index = tracker.index
                            INNER join challenges on challenge_exclusion."challengeId" = challenges."challengeId"
                            WHERE tracker.discord = '{int(ctx.author.id)}' ''', index_col='id').transpose()

        if df_exclusion.empty:
            await ctx.send("Tu n'as aucun challenge exclu", ephemeral=True)
        else:
            df_exclusion.sort_values('index', inplace=True)
            txt_exclusion = ''.join(
                f'\n- {data["index"]} : **{data["name"]}** '
                for row, data in df_exclusion.iterrows()
            )
            await ctx.send(f'Challenges exclus : {txt_exclusion}', ephemeral=True)

    @lol_compte.subcommand('modifier_parametres',
                           sub_cmd_description='Activation/Désactivation du tracker',
                           options=[
                               SlashCommandOption(name='summonername',
                                                  description="nom ingame",
                                                  type=interactions.OptionType.STRING,
                                                  required=True),
                               SlashCommandOption(name="tracker_fin",
                                                  description="Tracker qui affiche le recap de la game en fin de partie",
                                                  type=interactions.OptionType.BOOLEAN,
                                                  required=False),
                               SlashCommandOption(name="tracker_debut",
                                                  description="Tracker en début de partie",
                                                  type=interactions.OptionType.BOOLEAN,
                                                  required=False),
                               SlashCommandOption(name="tracker_challenges",
                                                  description="Tracker challenges",
                                                  type=interactions.OptionType.BOOLEAN,
                                                  required=False),
                               SlashCommandOption(name="affichage",
                                                  description="Affichage du tracker",
                                                  type=interactions.OptionType.INTEGER,
                                                  required=False,
                                                  choices=[SlashCommandChoice(name="Mode classique", value=1),
                                                           SlashCommandChoice(name="Mode beta", value=2)]),
                               SlashCommandOption(name='nb_challenges',
                                                  description='Nombre de challenges à afficher dans le recap (entre 1 et 20)',
                                                  type=interactions.OptionType.INTEGER,
                                                  required=False,
                                                  min_value=1,
                                                  max_value=20),
                               SlashCommandOption(name="insights",
                                                  description="Insights dans le recap",
                                                  type=interactions.OptionType.BOOLEAN,
                                                  required=False)])
    async def tracker_config(self,
                             ctx: SlashContext,
                             summonername: str,
                             tracker_fin: bool = None,
                             tracker_debut: bool = None,
                             tracker_challenges: bool = None,
                             insights: bool = None,
                             nb_challenges: int = None,
                             affichage: int = None):

        summonername = summonername.lower().replace(' ', '')

        if tracker_fin != None:

            nb_row = requete_perso_bdd('UPDATE tracker SET activation = :activation WHERE index = :index', {
                'activation': tracker_fin, 'index': summonername}, get_row_affected=True)
            if nb_row > 0:
                if tracker_fin:
                    await ctx.send('Tracker fin de game activé !')
                else:
                    await ctx.send('Tracker fin de game désactivé !')
            else:
                await ctx.send('Joueur introuvable')

        if tracker_debut != None:

            nb_row = requete_perso_bdd('UPDATE tracker SET spec_tracker = :activation WHERE index = :index', {
                'activation': tracker_debut, 'index': summonername}, get_row_affected=True)
            if nb_row > 0:
                if tracker_debut:
                    await ctx.send('Tracker debut de game activé !')
                else:
                    await ctx.send('Tracker debut de game désactivé !')
            else:
                await ctx.send('Joueur introuvable')

        if tracker_challenges != None:

            nb_row = requete_perso_bdd('UPDATE tracker SET challenges = :activation WHERE index = :index', {
                'activation': tracker_challenges, 'index': summonername}, get_row_affected=True)
            if nb_row > 0:
                if tracker_challenges:
                    await ctx.send('Tracker challenges activé !')
                else:
                    await ctx.send('Tracker challenges désactivé !')
            else:
                await ctx.send('Joueur introuvable')

        if insights != None:

            nb_row = requete_perso_bdd('UPDATE tracker SET insights = :activation WHERE index = :index', {
                'activation': insights, 'index': summonername}, get_row_affected=True)
            if nb_row > 0:
                if insights:
                    await ctx.send('Insights activé !')
                else:
                    await ctx.send('Insights désactivé !')
            else:
                await ctx.send('Joueur introuvable')

        if affichage != None:

            nb_row = requete_perso_bdd('UPDATE tracker SET affichage = :activation WHERE index = :index', {
                'activation': affichage, 'index': summonername}, get_row_affected=True)
            if nb_row > 0:
                await ctx.send('Affichage modifié')
            else:
                await ctx.send('Joueur introuvable')

        if nb_challenges != None:

            nb_row = requete_perso_bdd('UPDATE tracker SET nb_challenges = :activation WHERE index = :index', {
                'activation': nb_challenges, 'index': summonername}, get_row_affected=True)

            if nb_row > 0:
                await ctx.send(f'Nombre de challenges affichés : ** {nb_challenges} ** !')

            else:
                await ctx.send('Joueur introuvable')

        if (
            tracker_fin is None
            and tracker_debut is None
            and tracker_challenges is None
            and insights is None
            and nb_challenges is None
            and affichage is None
        ):
            await ctx.send('Tu dois choisir une option !')

    @slash_command(name='lol_list',
                   description='Affiche la liste des joueurs suivis',
                   options=[SlashCommandOption(name='serveur_only',
                                      description='General ou serveur ?',
                                      type=interactions.OptionType.BOOLEAN,
                                      required=False)])
    async def lollist(self,
                      ctx: SlashContext,
                      serveur_only: bool = False):

        if serveur_only:
            df = lire_bdd_perso(f'''SELECT suivi.index, suivi.wins, suivi.losses, suivi."LP", suivi.tier, suivi.rank, tracker.server_id from suivi_s{saison} as suivi
                                        INNER join tracker ON tracker.index = suivi.index 
                                        where suivi.tier != 'Non-classe' and tracker.server_id = {int(ctx.guild.id)} ''')

        else:
            df = lire_bdd_perso(f'''SELECT suivi.index, suivi.wins, suivi.losses, suivi."LP", suivi.tier, suivi.rank, tracker.server_id from suivi_s{saison} as suivi
                                        INNER join tracker ON tracker.index = suivi.index 
                                        where suivi.tier != 'Non-classe' ''')
        df = df.transpose().reset_index()

        # Pour l'ordre de passage
        df['tier_pts'] = df['tier'].apply(label_tier)
        df['rank_pts'] = df['rank'].apply(label_rank)

        df['winrate'] = round(df['wins'].astype(int) / (df['wins'].astype(int) + df['losses'].astype(int)) * 100, 1)


        df.sort_values(by=['tier_pts', 'rank_pts', 'LP'],
                                    ascending=[False, False, False],
                                    inplace=True)

        response = ''.join(
            f'''{data['index']} : {emote_rank_discord[data['tier']]} {data['rank']} | {data['LP']} LP | {data['winrate']}% WR\n'''
            for lig, data in df.iterrows()
        )
        embed = interactions.Embed(
            title="Live feed list", description=response, color=interactions.Color.random())

        await ctx.send(embeds=embed)

    async def update_24h(self):
        data = get_data_bdd(
            '''SELECT DISTINCT tracker.server_id from tracker 
                    INNER JOIN channels_module on tracker.server_id = channels_module.server_id
                    where channels_module.league_ranked = true'''
        ).fetchall()

        for server_id in data:

            guild = await self.bot.fetch_guild(server_id[0])

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
                    title="Suivi LOL", description='Periode : 24h', color=interactions.Color.random())
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
                    classement_old = f"{tier_old} {rank_old}"

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
                        emote = ":arrow_up:"

                    elif dict_rankid[classement_old] == dict_rankid[classement_new]:
                        if difLP > 0:
                            emote = ":arrow_up:"
                        elif difLP < 0:
                            emote = ":arrow_down:"
                        elif difLP == 0:
                            emote = ":arrow_right:"

                    embed.add_field(
                        name=f"{str(key)} ( {emote_rank_discord[tier]} {rank} )",
                        value="V : "
                        + str(suivi[key]['wins'])
                        + "("
                        + str(difwins)
                        + ") | D : "
                        + str(suivi[key]['losses'])
                        + "("
                        + str(diflosses)
                        + ") | LP :  "
                        + str(suivi[key]['LP'])
                        + "("
                        + str(difLP)
                        + ")    "
                        + emote,
                        inline=False,
                    )

                    if (difwins + diflosses > 0):  # si supérieur à 0, le joueur a joué
                        sql += f'''UPDATE suivi_24h
                            SET wins = {suivi[key]['wins']},
                            losses = {suivi[key]['losses']},
                            "LP" = {suivi[key]['LP']},
                            tier = '{suivi[key]['tier']}',
                            rank = '{suivi[key]['rank']}'
                            where index = '{key}';'''

                channel_tracklol = await self.bot.fetch_channel(chan_discord_id.tracklol)

                embed.set_footer(text=f'Version {Version} by Tomlora')

                if sql != '':  # si vide, pas de requête
                    requete_perso_bdd(sql)

                if totalgames > 0:  # s'il n'y a pas de game, on ne va pas afficher le récap
                    await channel_tracklol.send(embeds=embed)
                    await channel_tracklol.send(f'Sur {totalgames} games -> {totalwin} victoires et {totaldef} défaites')

    @Task.create(TimeTrigger(hour=4))
    async def lolsuivi(self):

        await self.update_24h()

    @slash_command(name="force_update24h",
                   description="Réservé à Tomlora")
    async def force_update(self, ctx: SlashContext):

        await ctx.defer(ephemeral=False)

        if isOwner_slash(ctx):
            await self.update_24h()
            # await ctx.delete()

        else:
            await ctx.send("Tu n'as pas l'autorisation nécessaire")

    @lol_compte.subcommand("color",
                           sub_cmd_description="Modifier la couleur du recap",
                           options=[SlashCommandOption(name="summonername",
                                                       description="Nom du joueur",
                                                       type=interactions.OptionType.STRING,
                                                       required=True),
                                    SlashCommandOption(name="rouge",
                                                       description="R",
                                                       type=interactions.OptionType.INTEGER,
                                                       required=True),
                                    SlashCommandOption(name="vert",
                                                       description="G",
                                                       type=interactions.OptionType.INTEGER,
                                                       required=True),
                                    SlashCommandOption(name="bleu",
                                                       description="B",
                                                       type=interactions.OptionType.INTEGER,
                                                       required=True)])
    async def lolcolor(self,
                       ctx: SlashContext,
                       summonername: str,
                       rouge: int,
                       vert: int,
                       bleu: int):

        await ctx.defer(ephemeral=False)

        interactions.Role.color

        params = {'rouge': rouge, 'vert': vert,
                  'bleu': bleu, 'index': summonername.lower()}
        nb_row = requete_perso_bdd(
            'UPDATE tracker SET "R" = :rouge, "G" = :vert, "B" = :bleu WHERE index = :index',
            params,
            get_row_affected=True,
        )

        if nb_row > 0:
            await ctx.send(f' La couleur du joueur {summonername} a été modifiée.')
        else:
            await ctx.send(f" Le joueur {summonername} n'est pas dans la base de données.")

    @slash_command(name="abbedagge", description="Meilleur joueur de LoL")
    async def abbedagge(self, ctx):
        await ctx.send('https://clips.twitch.tv/ShakingCovertAuberginePanicVis-YDRK3JFk7Glm6nbB')

    @slash_command(name="closer", description="Meilleur joueur de LoL")
    async def closer(self, ctx):
        await ctx.send('https://clips.twitch.tv/EmpathicClumsyYogurtKippa-lmcFoGXm1U5Jx2bv')

    @slash_command(name="upset", description="Meilleur joueur de LoL")
    async def upset(self, ctx):
        await ctx.send('https://clips.twitch.tv/CuriousBenevolentMageHotPokket-8M0TX_zTaGW7P2g7')

    @lol_compte.subcommand('discord',
                           sub_cmd_description='Relie un compte discord et un compte league of legends',
                           options=[
                               SlashCommandOption(
                                   name='summonername',
                                   description='pseudo lol',
                                   type=interactions.OptionType.STRING,
                                   required=True),
                               SlashCommandOption(
                                   name='member',
                                   description='compte discord',
                                   type=interactions.OptionType.USER,
                                   required=True
                               )])
    async def link(self,
                   ctx: SlashContext,
                   summonername,
                   member: interactions.User):

        summonername = summonername.lower()
        nb_row = requete_perso_bdd('UPDATE tracker SET discord = :discord, server_id = :guild WHERE index = :summonername', {
            'discord': int(member.id), 'guild': int(ctx.guild.id), 'summonername': summonername}, get_row_affected=True)

        
        if nb_row > 0:
            await ctx.send(f'Le compte LoL {summonername} a été link avec <@{int(member.id)}>')
        else:
            await ctx.send(f"Le compte LoL {summonername} n'existe pas dans la base de donnée")

    @slash_command(name='recap_journalier',
                   description='Mon recap sur les 24 dernières heures',
                   options=[
                       SlashCommandOption(
                           name='summonername',
                           description='pseudo lol',
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
                       summonername: str,
                       mode: str = None,
                       observation: str = '24h'):

        summonername = summonername.lower()

        timezone = tz.gettz('Europe/Paris')

        dict_timedelta = {'24h': timedelta(days=1),
                          '48h': timedelta(days=2),
                          '72h': timedelta(days=3),
                          '96h': timedelta(days=4),
                          'Semaine': timedelta(days=7),
                          'Mois': timedelta(days=30)}

        await ctx.defer(ephemeral=False)

        if mode is None:
            df = (
                lire_bdd_perso(
                    f'''SELECT id, match_id, champion, id_participant, mvp, time, kills, deaths, assists, quadra, penta, tier, rank, mode, kp, kda, victoire, ecart_lp, ecart_gold, datetime from matchs
                                   where datetime >= :date
                                   and joueur='{summonername}' ''',
                    params={
                        'date': datetime.now(timezone)
                        - dict_timedelta.get(observation)
                    },
                    index_col='id',
                ).transpose()
                if observation != 'today'
                else lire_bdd_perso(
                    f'''SELECT id, match_id, id_participant, champion, mvp, time, kills, deaths, assists, quadra, penta, tier, rank, mode, kp, kda, victoire, ecart_lp, ecart_gold, datetime from matchs
                                where EXTRACT(DAY FROM datetime) = :jour
                                AND EXTRACT(MONTH FROM datetime) = :mois
                                AND EXTRACT(YEAR FROM datetime) = :annee
                                and joueur='{summonername}' ''',
                    params={
                        'jour': datetime.now(timezone).day,
                        'mois': datetime.now(timezone).month,
                        'annee': datetime.now(timezone).year,
                    },
                    index_col='id',
                ).transpose()
            )
        elif observation != 'today':
            df = lire_bdd_perso(f'''SELECT id, match_id, id_participant, champion, mvp, time, kills, deaths, assists, quadra, penta, tier, rank, mode, kp, victoire, kda, ecart_lp, ecart_gold, datetime from matchs
                                   where datetime >= :date
                                   and joueur='{summonername}'
                                   and mode = '{mode}' ''',
                                params={'date': datetime.now(
                                    timezone) - dict_timedelta.get(observation)},
                                index_col='id').transpose()

        else:

            df = lire_bdd_perso(f'''SELECT id, match_id, id_participant, champion, mvp, time, kills, deaths, assists, quadra, penta, tier, rank, mode, kp, victoire, kda, ecart_lp, ecart_gold, datetime from matchs
                                where EXTRACT(DAY FROM datetime) = :jour
                                AND EXTRACT(MONTH FROM datetime) = :mois
                                AND EXTRACT(YEAR FROM datetime) = :annee
                                and joueur='{summonername}'
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
                'SELECT "R", "G", "B" from tracker WHERE index= :index',
                {'index': summonername.lower()},
            ).fetchall()
            # color = rgb_to_discord(data[0][0], data[0][1], data[0][2])

            # On crée l'embed
            embed = interactions.Embed(
                title=f" Recap **{summonername.upper()} ** {observation.upper()}", color=interactions.Color.from_rgb(data[0][0], data[0][1], data[0][2]))

            txt = ''
            n = 1
            count = 0
            part = 1
            embeds = []
            
            emote_status_match = {'Victoire' : '<:valide:838833884442919002>', 'Défaite' : '<:invalide:838833882924843019>'}
            
           
            
            # On affiche les résultats des matchs
            
            for index, match in df.iterrows():
                rank_img = emote_rank_discord[match["tier"]]
                champ_img = emote_champ_discord.get(match["champion"].capitalize(), 'inconnu')
                txt += f'[{match["datetime"]}](https://www.leagueofgraphs.com/fr/match/euw/{str(match["match_id"])[5:]}#participant{int(match["id_participant"])+1}) {champ_img} [{match["mode"]} | {rank_img} {match["rank"]}] {emote_status_match[match["victoire"]]} | KDA : **{match["kills"]}**/**{match["deaths"]}**/**{match["assists"]}** ({match["kp"]}%) | LP : **{match["ecart_lp"]}** | G : {match["ecart_gold"]} \n'

                if embed.fields and len(txt) + sum(len(field.value) for field in embed.fields) > 4000:
                    embed.add_field(name='KDA', value=total_kda)
                    embed.add_field(name='Champions', value=txt_champ)
                    embed.add_field(
                        name='Ratio', value=f'{total_victoire} ({nb_victoire_total/(nb_victoire_total+nb_defaite_total)*100:.2f}%)')
                    embed.add_field(
                        name='Autres', value=f'Durée moyenne : **{duree_moyenne:.0f}**m | MVP : **{mvp_moyenne:.1f}**')
                
                    if (total_quadra + total_penta) > 0:
                        embed.add_field(
                            name='Série', value=f'Quadra : **{total_quadra}** | Penta : **{total_penta}**')
                
                    embeds.append(embed)
                    embed = interactions.Embed(
                        title=f" Recap **{summonername.upper()} ** {observation.upper()} Part {part}", color=interactions.Color.from_rgb(data[0][0], data[0][1], data[0][2]))
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
                    name='Ratio', value=f'{total_victoire} ({nb_victoire_total/(nb_victoire_total+nb_defaite_total)*100:.2f}%)')
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


def setup(bot):
    LeagueofLegends(bot)
