import interactions
import asyncio
import logging
from pathlib import Path
from interactions import Extension, SlashContext, SlashCommandChoice, SlashCommandOption, slash_command, listen, Task, IntervalTrigger, TimeTrigger
import pandas as pd
import numpy as np
import aiohttp
import sys
import traceback
import humanize
from utils.emoji import emote_champ_discord
from fonctions.match import (get_version,
                             get_champ_list,
                             get_version,
                             get_champ_list)
from fonctions.gestion_bdd import sauvegarde_bdd, get_data_bdd, lire_bdd_perso

import joblib
import fonctions.api_calls as api_calls
import numpy as np
import scipy.stats

logger = logging.getLogger(__name__)
MODEL_PATH = Path(__file__).resolve().parents[1] / 'model' / 'prediction_result.sav'

# U.GG est indisponible. Ne pas réactiver sans une source fiable et un budget
# d'appels explicite ; aucune collecte Riot de remplacement n'est lancée.
PREDICTIONS_ENABLED = False
PREDICTIONS_DISABLED_MESSAGE = (
    "Les nouvelles prédictions sont temporairement désactivées : U.GG est indisponible. "
    "Les anciennes prédictions restent consultables avec /predict_victory."
)


class PredictionDisabledError(RuntimeError):
    """Une nouvelle prédiction a été demandée alors que la collecte est arrêtée."""

async def add_stats(raw_data) -> list:
    if len(raw_data) != 5 or not np.isfinite(raw_data).all():
        raise ValueError("La prédiction exige cinq valeurs finies par équipe")
    processed_data = []

    # add 5 features to the
    processed_data += raw_data

    # Add average
    processed_data.append(np.average(raw_data))
    # Add median
    processed_data.append(np.median(raw_data))
    # Add coeficient of kurtosis
    constant = np.ptp(raw_data) == 0
    processed_data.append(0.0 if constant else scipy.stats.kurtosis(raw_data, bias=False))
    # Add coeficient skewness
    processed_data.append(0.0 if constant else scipy.stats.skew(raw_data, bias=False))
    # Add standard_deviation
    processed_data.append(np.std(raw_data))
    # Add variance
    processed_data.append(np.var(raw_data))

    # return 11
    return processed_data


async def predict_match(match_id, match, champion, session : aiohttp.ClientSession, ctx : SlashContext = None):
    if not PREDICTIONS_ENABLED:
        raise PredictionDisabledError(PREDICTIONS_DISABLED_MESSAGE)
    
    participants = match["participants"]
    if (len(participants) != 10
            or sum(p.get('team') == 'BLUE' for p in participants) != 5
            or sum(p.get('team') == 'RED' for p in participants) != 5):
        raise ValueError("La prédiction est disponible uniquement pour les matchs 5 contre 5")
    if isinstance(ctx, SlashContext):
        msg = await ctx.send('Match trouvé')
        
    blueWinrates = []
    blueMasteries = []
    redWinrates = []
    redMasteries = []
    redParticipant = []
    redChampion = []
    blueParticipant = []
    blueChampion = []

    redLevel = []
    blueLevel = []

    try:
        humanize.activate('fr_FR', path='C:/Users/Kevin/PycharmProjects/bot_discord_aio/translations/')
    except FileNotFoundError:
        humanize.i18n.activate('fr_FR')    

    batch = 0
    totalBatches = 10
    # Get Masteries and Winrates
    for participant in participants:
        batch += 1
        if isinstance(ctx, SlashContext):
            await msg.edit(content=f"Game **EUW1_{match_id}** : Processing participant {batch} ({100*batch//totalBatches}%)")
            
        championId = int(participant["championId"])
        team = participant["team"]
        summonerName = participant["summonerName"]
        
        winrate_list = await api_calls.get_winrates(summonerName, session=session)
        mastery_list = await api_calls.get_masteries(summonerName, champion, session)
        mastery = 0
        level = 0

        # Go over each element of the list
        for mastery_object in mastery_list:
            if championId == int(mastery_object["championId"]):
                mastery = mastery_object["mastery"]
                level = mastery_object['level']
        winrate = 0
        try:
            for winrate_object in winrate_list:
                if championId == int(winrate_object["championID"]):
                    winrate = winrate_object["winrate"] / 100
        except TypeError:
            winrate = 0
                
        if team == "RED":
            redMasteries.append(mastery)
            redWinrates.append(winrate)
            redParticipant.append(participant['summonerName'])
            redChampion.append(champion[str(championId)])
            try:
                redLevel.append(level)
            except UnboundLocalError:
                redLevel.append(0)
        else:
            blueMasteries.append(mastery)
            blueWinrates.append(winrate)
            blueParticipant.append(participant['summonerName'])
            blueChampion.append(champion[str(championId)])
            try:
                blueLevel.append(level)
            except UnboundLocalError:
                blueLevel.append(0)

    txt_rouge = '**:red_circle: Team Red**\n'
    txt_bleu = '**:blue_circle: Team Blue **\n'
    
    def format_nombre(nombre):
        try:
            if len(str(int(nombre))) <= 6 :
                return humanize.intcomma(int(nombre)) # on met des espaces entre les milliers
            else:
                return humanize.intword(int(nombre)).replace('million', 'M') # on transforme le nombre en mots
        except ValueError:
            return 0
        
    for masteries, winrate, participant, champion, lev in zip(redMasteries, redWinrates, redParticipant, redChampion, redLevel):
        winrate = round(winrate*100,0)

        txt_rouge += f'{emote_champ_discord.get(champion.capitalize(), champion)} **{participant}**  : WR **{int(winrate)}%** | Pts : **{format_nombre(masteries)}** | Lvl : **{lev}** \n'
         
    for masteries, winrate, participant, champion, lev in zip(blueMasteries, blueWinrates, blueParticipant, blueChampion, blueLevel):
        winrate = round(winrate*100,0)
        txt_bleu += f'**{emote_champ_discord.get(champion.capitalize(), champion)} {participant}**  : WR **{int(winrate)}%** | Pts : **{format_nombre(masteries)}** | Lvl : **{lev}** \n'
        
    txt_recap = {'redside' : txt_rouge, 'blueside' : txt_bleu}        


    # Process Data pour envoi
    
    blueData = []
    redData = []

    blueData += await add_stats(blueMasteries)
    blueData += await add_stats(blueWinrates)
    redData += await add_stats(redMasteries)
    redData += await add_stats(redWinrates)

    final_data = []
    final_data += blueData
    final_data += redData

    dataset = final_data
    if len(dataset) != 44 or not np.isfinite(dataset).all():
        raise ValueError("Statistiques invalides pour la prédiction")
    model = joblib.load(MODEL_PATH)
    prediction = model.predict([dataset])
    proba = model.predict_proba([dataset])
    
    if isinstance(ctx, SlashContext):
        await msg.delete()
    
    del model

    return prediction, proba, txt_recap, dataset



# async def get_last_match_prediction(ctx : SlashContext, summonerName: str, match_id : str, session:aiohttp.ClientSession):
    
#     async def charger_champion(session):
#         version = await get_version(session)
#         current_champ_list = await get_champ_list(session, version)
#         return current_champ_list


#     current_champ_list = await charger_champion(session)

#     champions = {}
#     for key in current_champ_list['data']:
#         row = current_champ_list['data'][key]
#         champions[row['key']] = row['id']
        
#     # Get last match

#     match_id = match_id[5:]
#     match = await api_calls.get_past_matches(summonerName, match_id, session)
#     prediction, proba, txt_recap = await predict_match(match_id, match, champions, session, ctx)


#     teams_result = {
#         match["teams"][0]["teamId"]: match["teams"][0]["result"],
#         match["teams"][1]["teamId"]: match["teams"][1]["result"],
#     }

#     if teams_result["BLUE"] == "WON":
#         result = 1
#     else:
#         result = 0

#     response = {}

#     your_championId = match["subject"]["championId"]
#     your_team = match["subject"]["team"]
#     your_role = match["subject"]["role"]

#     response["team"] = your_team
#     response["role"] = your_role
#     response["champion"] = champions[str(your_championId)]
#     response['probability'] = proba

#     if (result == 1 and your_team == "BLUE") or (result == 0 and your_team == "RED"):
#         response["won"] = True
#     else:
#         response["won"] = False

#     if result == prediction:
#         response["correct"] = True
#     else:
#         response["correct"] = False

#     return response, txt_recap


async def _get_current_prediction(summoner_name, match_id, session, ctx=None):
    if not PREDICTIONS_ENABLED:
        raise PredictionDisabledError(PREDICTIONS_DISABLED_MESSAGE)
    # Éviter les appels Data Dragon et modèle quand aucune partie n'est active.
    match = await api_calls.get_live_match(summoner_name, session)
    if match == 'Aucun':
        return 'Aucun', 'Aucun', 'Aucun'

    normalize = lambda name: name.casefold().replace(' ', '')
    player = next(
        (p for p in match['participants']
         if normalize(p['summonerName']) == normalize(summoner_name)),
        None,
    )
    if player is None:
        raise ValueError("Le joueur demandé est absent de la partie retournée")

    version = await get_version(session)
    champion_data = await get_champ_list(session, version)
    champions = {row['key']: row['id'] for row in champion_data['data'].values()}
    prediction, proba, recap, dataset = await predict_match(
        match_id, match, champions, session, ctx
    )
    blue_wins = int(prediction[0]) == 1
    response = {
        'victory_predicted': blue_wins == (player['team'] == 'BLUE'),
        'team': player['team'],
        'champion': champions[str(player['championId'])],
        'role': 'aram' if match['gameType'] == 'normal_aram' else player.get('currentRole') or 'inconnu',
        'probability': proba,
        'summonerName': summoner_name,
    }
    return response, recap, dataset


async def get_current_match_prediction(ctx: SlashContext, summonerName: str,
                                       match_id: str, session: aiohttp.ClientSession):
    response, recap, _ = await _get_current_prediction(summonerName, match_id, session, ctx)
    return response, recap


async def get_current_match_prediction_auto(summonerName: str, match_id: str,
                                            session: aiohttp.ClientSession):
    return await _get_current_prediction(summonerName, match_id, session)

class predict(Extension):
    def __init__(self, bot):
        self.bot: interactions.Client = bot


    @listen()
    async def on_startup(self):
        if PREDICTIONS_ENABLED:
            self.update_predict.start()
        else:
            logger.info("Collecte des prédictions désactivée : U.GG indisponible")

    # @slash_command(name='predict_victory',
    #                                 description='Predit le resultat de la game',
    #                                 options=[
    #                                     SlashCommandOption(
    #                                         name='summonername',
    #                                         description='SummonerName',
    #                                         type=interactions.OptionType.STRING,
    #                                         required=True),
    #                                     SlashCommandOption(
    #                                         name='tag',
    #                                         description='Tag',
    #                                         type=interactions.OptionType.STRING,
    #                                         required=True),
    #                                     SlashCommandOption(
    #                                         name='match_id',
    #                                         description='EUW1_...',
    #                                         type=interactions.OptionType.STRING,
    #                                         required=True
    #                                     )])
    # async def predict_probability(self,
    #                       ctx: SlashContext,
    #                       summonername: str,
    #                       tag: str,
    #                       match_id: str):
        
    #     session = aiohttp.ClientSession()
        
    #     await ctx.defer(ephemeral=False)
        
    #     summonername = summonername + '#' + tag

    #     try:
    #         data, txt_recap = await get_last_match_prediction(ctx, summonername, match_id, session)
            
            
    #         txt = f'Game **{match_id}** | **{data["team"]}** side | {emote_champ_discord.get(data["champion"].capitalize(), data["champion"])} **({data["role"]})** \n'
            
    #         if data["won"]:
    #             result = 'une victoire'
    #         else:
    #             result = 'une défaite'
    #         txt += f'Le résultat de ta game était **{result}** \n'
            
    #         if data['correct']:
    #             prediction = 'correcte'
    #         else:
    #             prediction = 'fausse'
            
    #         probability = data['probability']
            
    #         if data['team'] == 'BLUE':
    #             txt += f'La prédiction était **{prediction}** -> Defaite : {np.round(probability[0][0]*100,0)}% | Victoire : {np.round(probability[0][1]*100,0)}% \n'
    #         else:
    #             txt += f'La prédiction était **{prediction}** -> Victoire : {np.round(probability[0][0]*100,0)}% | Défaite : {np.round(probability[0][1]*100,0)}% \n'
            
    #         txt += f'\n{txt_recap["redside"]} \n{txt_recap["blueside"]}'  
    #         await ctx.send(txt)
            
    #         await session.close()
        
    #     except Exception:
    #         exc_type, exc_value, exc_traceback = sys.exc_info()
    #         traceback_details = traceback.format_exception(exc_type, exc_value, exc_traceback)
    #         traceback_msg = ''.join(traceback_details)
    #         print(traceback_msg)
    #         await ctx.send("Erreur. Si la game vient de se terminer, **merci d'attendre 5m**")
    #         await session.close()

    @slash_command(name='predict_victory',
                                    description='Predit le resultat de la game',
                                    options=[
                                        SlashCommandOption(
                                            name='summonername',
                                            description='SummonerName',
                                            type=interactions.OptionType.STRING,
                                            required=True),
                                        SlashCommandOption(
                                            name='tag',
                                            description='Tag',
                                            type=interactions.OptionType.STRING,
                                            required=True),
                                        SlashCommandOption(
                                            name='match_id',
                                            description='EUW1_...',
                                            type=interactions.OptionType.STRING,
                                            required=True
                                        )])
    async def predict_probability(self,
                          ctx: SlashContext,
                          summonername: str,
                          tag: str,
                          match_id: str):
        
        
        await ctx.defer(ephemeral=False)

        summonername = summonername.lower()
        tag = tag.upper()

        try:
            df = lire_bdd_perso('''select prev_lol.*, matchs.victoire from prev_lol
            INNER JOIN matchs ON matchs.match_id = prev_lol.match_id
            INNER JOIN tracker ON tracker.id_compte = matchs.joueur
            WHERE prev_lol.match_id = :match_id
            AND prev_lol.riot_id = :riot_id AND prev_lol.riot_tag = :riot_tag
            AND tracker.riot_id = :riot_id AND tracker.riot_tagline = :riot_tag''',
                index_col=None,
                params={'match_id': match_id, 'riot_id': summonername, 'riot_tag': tag},
            ).T

            if df.empty:
                return await ctx.send("Aucune prédiction enregistrée pour ce joueur et cette partie.")

            df['pred_correct'] = df['victory_predicted'] == df['victoire']

            df = df.iloc[0]

            txt_result = df['text']

            if df['victoire']:
                txt_result += '\n\nLe résultat de ta game était une **victoire**'
            else:
                txt_result += '\n\nLe résultat de ta game était une **défaite**'

            if df['pred_correct']:
                txt_result += '\nLa prédiction était **correcte**'
            else:
                txt_result += '\nLa prédiction était **fausse**'

            
            await ctx.send(txt_result)

        
        except Exception:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback_details = traceback.format_exception(exc_type, exc_value, exc_traceback)
            traceback_msg = ''.join(traceback_details)
            print(traceback_msg)
            await ctx.send("Erreur. Si la game vient de se terminer, **merci d'attendre 5m**")

    @Task.create(IntervalTrigger(minutes=5))
    async def update_predict(self):
        if not PREDICTIONS_ENABLED:
            return

        data_joueur = get_data_bdd(
            '''SELECT DISTINCT tracker.riot_id, tracker.riot_tagline
               FROM tracker
               INNER JOIN channels_module ON tracker.server_id = channels_module.server_id
               WHERE tracker.activation = true AND channels_module.league_ranked = true'''
        ).fetchall()
        data_empty = lire_bdd_perso(
            "SELECT riot_id, riot_tag FROM prev_lol WHERE match_id = ''",
            index_col=None,
        ).T
        pending = {
            (str(row.riot_id).lower(), str(row.riot_tag).upper())
            for row in data_empty.itertuples()
        }
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            for riot_id, riot_tag in data_joueur:
                account = (riot_id.lower(), riot_tag.upper())
                if account in pending:
                    continue
                try:
                    await asyncio.wait_for(
                        self.predict_probability_auto(session, *account), timeout=180
                    )
                except Exception:
                    # Une API indisponible pour un compte ne doit pas arrêter
                    # la tâche périodique ni les prédictions des autres joueurs.
                    logger.exception("Prédiction indisponible pour %s#%s", *account)
                else:
                    pending.add(account)

    @slash_command(name='predict_victory_en_cours',
                                    description='Predit le resultat de la game',
                                    options=[
                                        SlashCommandOption(
                                            name='summonername',
                                            description='SummonerName',
                                            type=interactions.OptionType.STRING,
                                            required=True),
                                        SlashCommandOption(
                                            name='tagline',
                                            description='tag',
                                            type=interactions.OptionType.STRING,
                                            required=True
                                        )])



    async def predict_probability_direct(self,
                          ctx: SlashContext,
                          summonername: str,
                          tagline: str):
        if not PREDICTIONS_ENABLED:
            return await ctx.send(PREDICTIONS_DISABLED_MESSAGE, ephemeral=True)
        
        await ctx.defer(ephemeral=False)
        
        match_id = '      en cours'
        
        summonername = summonername + "#" + tagline

        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                data, txt_recap = await asyncio.wait_for(
                    get_current_match_prediction(ctx, summonername, match_id, session),
                    timeout=180,
                )
            
            if data == "Aucun":
                return await ctx.send('Pas de game en cours')
            
            txt = f'Game **{match_id}** | **{data["team"]}** side | {emote_champ_discord.get(data["champion"].capitalize(), data["champion"])} **({data["role"]})** \n'
            
            if data['victory_predicted']:
                prediction = 'une victoire'
            else:
                prediction = 'une defaite'
            
            probability = data['probability']
            
            if data['team'] == 'BLUE':
                txt += f'La prédiction est **{prediction}** -> Defaite : {np.round(probability[0][0]*100,0)}% | Victoire : {np.round(probability[0][1]*100,0)}% \n'
            else:
                txt += f'La prédiction est **{prediction}** -> Victoire : {np.round(probability[0][0]*100,0)}% | Défaite : {np.round(probability[0][1]*100,0)}% \n'
                
            txt += f'\n{txt_recap["redside"]} \n{txt_recap["blueside"]}'    
            await ctx.send(txt)
            
        
        except Exception:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback_details = traceback.format_exception(exc_type, exc_value, exc_traceback)
            traceback_msg = ''.join(traceback_details)
            print(traceback_msg)
            await ctx.send('Erreur')



    async def predict_probability_auto(self,
                                       session : aiohttp.ClientSession,
                                       riot_id,
                                       riot_tag,
                                       match_id = '      en cours'):
        if not PREDICTIONS_ENABLED:
            return



        data, txt_recap, dataset = await get_current_match_prediction_auto(f'{riot_id.lower()}#{riot_tag.lower()}', match_id, session)

        if data != 'Aucun':

            # Convention historique consommée par lol_recap : win=P(RED),
            # lose=P(BLUE). Ne pas inverser ces colonnes sans migration.
            data['win'] = np.round(data['probability'][0][0]*100)
            data['lose'] = np.round(data['probability'][0][1]*100)

            txt = f'**{data["team"]}** side | {emote_champ_discord.get(data["champion"].capitalize(), data["champion"])} **({data["role"]})** \n'
                        
            if data['victory_predicted']:
                prediction = 'une victoire'
            else:
                prediction = 'une defaite'
                        
            probability = data['probability']
                        
            if data['team'] == 'BLUE':
                txt += f'La prédiction est **{prediction}** -> Defaite : {np.round(probability[0][0]*100,0)}% | Victoire : {np.round(probability[0][1]*100,0)}% \n'
            else:
                txt += f'La prédiction est **{prediction}** -> Victoire : {np.round(probability[0][0]*100,0)}% | Défaite : {np.round(probability[0][1]*100,0)}% \n'
                            
            txt += f'\n{txt_recap["redside"]} \n{txt_recap["blueside"]}' 

            data['text'] = txt

            data['match_id'] = ''

            data['summonerName'] = data['summonerName'].lower()


            df = pd.DataFrame.from_dict(data, orient='index').T
            df.drop(columns='probability', inplace=True)

            df[['riot_id', 'riot_tag']] = df['summonerName'].str.split('#', expand=True)
            df['riot_tag'] = df['riot_tag'].str.upper()

            sauvegarde_bdd(df, 'prev_lol', 'append', index=False)

            df_features = pd.DataFrame([dataset])

            df_features.columns = ["blue_masteries_0", "blue_masteries_1", "blue_masteries_2", "blue_masteries_3", "blue_masteries_4", "blue_masteries_moyenne",  "blue_masteries_mediane", "blue_masteries_kurt", "blue_masteries_skew", "blue_masteries_ecart_type", "blue_masteries_variance",
                "blue_wr_0", "blue_wr_1", "blue_wr_2", "blue_wr_3", "blue_wr_4", "blue_wr_moyenne",  "blue_wr_mediane", "blue_wr_kurt", "blue_wr_skew", "blue_wr_ecart_type", "blue_wr_variance",
            "red_masteries_0", "red_maste0ries_1", "red_masteries_2", "red_masteries_3", "red_masteries_4", "red_masteries_moyenne",  "red_masteries_mediane", "red_masteries_kurt", "red_masteries_skew", "red_masteries_ecart_type", "red_masteries_variance",
                "red_wr_0", "red_wr_1", "red_wr_2", "red_wr_3", "red_wr_4", "red_wr_moyenne",  "red_wr_mediane", "red_wr_kurt", "red_wr_skew", "red_wr_ecart_type", "red_wr_variance"]

            df_features['match_id'] = ''
            df_features['summonerName'] = data['summonerName'].lower()
            df_features[['riot_id', 'riot_tag']] = df_features['summonerName'].str.split('#', expand=True)
            df_features['riot_tag'] = df_features['riot_tag'].str.upper()
            df_features.drop(columns='summonerName', inplace=True)

            sauvegarde_bdd(df_features, 'prev_lol_features', 'append', index=False)



    

def setup(bot):
    predict(bot)

