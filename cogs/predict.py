import interactions
from interactions import Extension, SlashContext, SlashCommandChoice, SlashCommandOption, slash_command
import pandas as pd
import numpy as np
import aiohttp
import sys
import traceback
import humanize
from fonctions.match import emote_champ_discord


from fonctions.match import (get_version,
                             get_champ_list,
                             get_version,
                             get_champ_list)

import joblib
import fonctions.api_calls as api_calls
import numpy as np
import scipy.stats

  

async def add_stats(raw_data) -> list:
    processed_data = []

    # add 5 features to the
    processed_data += raw_data

    # Add average
    processed_data.append(np.average(raw_data))
    # Add median
    processed_data.append(np.median(raw_data))
    # Add coeficient of kurtosis
    processed_data.append(scipy.stats.kurtosis(raw_data, bias=False))
    # Add coeficient skewness
    processed_data.append(scipy.stats.skew(raw_data, bias=False))
    # Add standard_deviation
    processed_data.append(np.std(raw_data))
    # Add variance
    processed_data.append(np.var(raw_data))

    # return 11
    return processed_data


async def predict_match(match_id, match, champion, session : aiohttp.ClientSession, ctx : SlashContext = None):
    
    participants = match["participants"]
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
            
        championId = participant["championId"]
        team = participant["team"]
        summonerName = participant["summonerName"]
        
        winrate_list = await api_calls.get_winrates(summonerName, session=session)
        mastery_list = await api_calls.get_masteries(summonerName, champion, session)
        mastery = 0

        # Go over each element of the list
        for mastery_object in mastery_list:
            if championId == mastery_object["championId"]:
                mastery = mastery_object["mastery"]


        
        winrate = 0
        for winrate_object in winrate_list:
            if championId == winrate_object["championID"]:
                winrate = winrate_object["winrate"] / 100
                
        if team == "RED":
            redMasteries.append(mastery)
            redWinrates.append(winrate)
            redParticipant.append(participant['summonerName'])
            redChampion.append(champion[str(championId)])
        else:
            blueMasteries.append(mastery)
            blueWinrates.append(winrate)
            blueParticipant.append(participant['summonerName'])
            blueChampion.append(champion[str(championId)])

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
        
    for masteries, winrate, participant, champion in zip(redMasteries, redWinrates, redParticipant, redChampion):
        winrate = round(winrate*100,0)

        txt_rouge += f'{emote_champ_discord.get(champion.capitalize(), champion)} **{participant}**  : WR **{int(winrate)}%** | Pts : **{format_nombre(masteries)}** \n'
         
    for masteries, winrate, participant, champion in zip(blueMasteries, blueWinrates, blueParticipant, blueChampion):
        winrate = round(winrate*100,0)
        txt_bleu += f'**{emote_champ_discord.get(champion.capitalize(), champion)} {participant}**  : WR **{int(winrate)}%** | Pts : **{format_nombre(masteries)}** \n'
        
    txt_recap = {'redside' : txt_rouge, 'blueside' : txt_bleu}        
    # Process Data
    
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
    model = joblib.load("model/prediction_result.sav")
    prediction = model.predict([dataset])
    proba = model.predict_proba([dataset])
    
    if isinstance(ctx, SlashContext):
        await msg.delete()
    
    del model

    return prediction, proba, txt_recap



async def get_last_match_prediction(ctx : SlashContext, summonerName: str, match_id : str, session:aiohttp.ClientSession):
    
    async def charger_champion(session):
        version = await get_version(session)
        current_champ_list = await get_champ_list(session, version)
        return current_champ_list


    current_champ_list = await charger_champion(session)

    champions = {}
    for key in current_champ_list['data']:
        row = current_champ_list['data'][key]
        champions[row['key']] = row['id']
        
    # Get last match

    match_id = match_id[5:]
    match = await api_calls.get_past_matches(summonerName, match_id, session)
    prediction, proba, txt_recap = await predict_match(match_id, match, champions, session, ctx)


    teams_result = {
        match["teams"][0]["teamId"]: match["teams"][0]["result"],
        match["teams"][1]["teamId"]: match["teams"][1]["result"],
    }

    if teams_result["BLUE"] == "WON":
        result = 1
    else:
        result = 0

    response = {}

    your_championId = match["subject"]["championId"]
    your_team = match["subject"]["team"]
    your_role = match["subject"]["role"]

    response["team"] = your_team
    response["role"] = your_role
    response["champion"] = champions[str(your_championId)]
    response['probability'] = proba

    if (result == 1 and your_team == "BLUE") or (result == 0 and your_team == "RED"):
        response["won"] = True
    else:
        response["won"] = False

    if result == prediction:
        response["correct"] = True
    else:
        response["correct"] = False

    return response, txt_recap


async def get_current_match_prediction(ctx : SlashContext, summonerName: str, match_id : str, session:aiohttp.ClientSession):
    
    async def charger_champion(session):
        version = await get_version(session)
        current_champ_list = await get_champ_list(session, version)
        return current_champ_list


    current_champ_list = await charger_champion(session)

    champions = {}
    for key in current_champ_list['data']:
        row = current_champ_list['data'][key]
        champions[row['key']] = row['id']
        
    # Get last match

    match_id = match_id[5:]
    match = await api_calls.get_live_match(summonerName, session)
    if match == 'Aucun':
        return 'Aucun', 'Aucun'
    prediction, proba, txt_recap = await predict_match(match_id, match, champions, session, ctx)

    for participant in match['participants']:
        if participant["summonerName"].lower() == summonerName.lower():
            your_team = participant["team"]
            your_champion = champions[str(participant["championId"])]
            your_role = participant["currentRole"]        

    response = {}

    if (prediction == 1 and your_team == "BLUE") or (
        prediction == 0 and your_team == "RED"
    ):
        response["victory_predicted"] = True
    else:
        response["victory_predicted"] = False

    response["team"] = your_team
    response["champion"] = your_champion
    response["role"] = your_role
    response['probability'] = proba

    return response, txt_recap

class predict(Extension):
    def __init__(self, bot):
        self.bot: interactions.Client = bot

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
        
        session = aiohttp.ClientSession()
        
        await ctx.defer(ephemeral=False)
        
        summonername = summonername + '#' + tag

        try:
            data, txt_recap = await get_last_match_prediction(ctx, summonername, match_id, session)
            
            
            txt = f'Game **{match_id}** | **{data["team"]}** side | {emote_champ_discord.get(data["champion"].capitalize(), data["champion"])} **({data["role"]})** \n'
            
            if data["won"]:
                result = 'une victoire'
            else:
                result = 'une défaite'
            txt += f'Le résultat de ta game était **{result}** \n'
            
            if data['correct']:
                prediction = 'correcte'
            else:
                prediction = 'fausse'
            
            probability = data['probability']
            
            if data['team'] == 'BLUE':
                txt += f'La prédiction était **{prediction}** -> Defaite : {np.round(probability[0][0]*100,0)}% | Victoire : {np.round(probability[0][1]*100,0)}% \n'
            else:
                txt += f'La prédiction était **{prediction}** -> Victoire : {np.round(probability[0][0]*100,0)}% | Défaite : {np.round(probability[0][1]*100,0)}% \n'
            
            txt += f'\n{txt_recap["redside"]} \n{txt_recap["blueside"]}'  
            await ctx.send(txt)
            
            await session.close()
        
        except Exception:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback_details = traceback.format_exception(exc_type, exc_value, exc_traceback)
            traceback_msg = ''.join(traceback_details)
            print(traceback_msg)
            await ctx.send("Erreur. Si la game vient de se terminer, **merci d'attendre 5m**")
            await session.close()
            
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
        
        session = aiohttp.ClientSession()
        
        await ctx.defer(ephemeral=False)
        
        match_id = '      en cours'
        
        summonername = summonername + "#" + tagline

        try:
            data, txt_recap = await get_current_match_prediction(ctx, summonername, match_id, session)
            
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
            
            await session.close()
        
        except Exception:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback_details = traceback.format_exception(exc_type, exc_value, exc_traceback)
            traceback_msg = ''.join(traceback_details)
            print(traceback_msg)
            await ctx.send('Erreur')
            await session.close()


    

def setup(bot):
    predict(bot)
