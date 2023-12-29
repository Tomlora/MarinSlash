import interactions
from interactions import Extension, SlashContext, SlashCommandChoice, SlashCommandOption, slash_command
import pandas as pd
import numpy as np
import aiohttp
import sys
import traceback


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


async def predict_match(ctx : SlashContext, match_id, match, champion, session : aiohttp.ClientSession):
    participants = match["participants"]
    msg = await ctx.send('Match trouvé')
    blueWinrates = []
    blueMasteries = []
    redWinrates = []
    redMasteries = []

    batch = 0
    totalBatches = 10
    # Get Masteries and Winrates
    for participant in participants:
        batch += 1
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
        else:
            blueMasteries.append(mastery)
            blueWinrates.append(winrate)

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
    
    await msg.delete()
    
    del model

    return prediction, proba



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
    prediction, proba = await predict_match(ctx, match_id, match, champions, session)


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

    return response


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
                                            name='match_id',
                                            description='EUW1_...',
                                            type=interactions.OptionType.STRING,
                                            required=True
                                        )])
    async def predict_probability(self,
                          ctx: SlashContext,
                          summonername: str,
                          match_id: str):
        
        session = aiohttp.ClientSession()
        
        await ctx.defer(ephemeral=False)

        try:
            data = await get_last_match_prediction(ctx, summonername, match_id, session)
            
            txt = f'Game **{match_id}** \n'
            txt += f'Ta team était : **{data["team"]}** \n'
            txt += f'Ton role était : **{data["role"]}** \n'
            txt += f'Ton champion était : **{data["champion"]}** \n'
            
            if data["won"]:
                result = 'une victoire'
            else:
                result = 'une défaite'
            txt += f'Le résultat de ta game était **{result}** \n'
            
            if data['correct']:
                prediction = 'correcte'
            else:
                prediction = 'incorrecte'
            
            probability = data['probability']
            
            if data['team'] == 'BLUE':
                txt += f'La prédiction était **{prediction}** -> Defaite : {np.round(probability[0][0]*100,0)}% | Victoire : {np.round(probability[0][1]*100,0)}% \n'
            else:
                txt += f'La prédiction était **{prediction}** -> Victoire : {np.round(probability[0][0]*100,0)}% | Défaite : {np.round(probability[0][1]*100,0)}% \n'
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
