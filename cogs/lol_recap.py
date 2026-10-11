import asyncio
import aiohttp
import pandas as pd
import warnings
import interactions
from interactions import SlashCommandOption, Extension, SlashContext, SlashCommandChoice, slash_command
from fonctions.match.riot_api import get_version
from utils.emoji import emote_champ_discord, emote_rank_discord
from fonctions.match.timeline import fix_temps
from fonctions.autocomplete import autocomplete_riotid
from fonctions.recap_filters import GAME_COUNTS, normalize_champion, recap_query
from interactions.ext.paginators import Paginator
import ast

from fonctions.gestion_bdd import get_data_bdd, lire_bdd_perso, get_tag

warnings.simplefilter(action='ignore', category=FutureWarning)
pd.options.mode.chained_assignment = None  # default='warn'


def recap_pages(title, color, description, fields):
    """Découper les champs et les pages sans dépasser les limites Discord."""
    pages = [interactions.Embed(title=title[:256], color=color, description=description)]
    for name, value in fields:
        while value:
            end = len(value)
            if end > 1024:
                end = value.rfind('\n', 0, 1024) + 1
                if end <= 0:
                    end = value.rfind(' | ', 0, 1024) + 3
                if end <= 2:
                    end = 1024
            chunk, value = value[:end], value[end:]
            page = pages[-1]
            if len(page.fields) >= 25 or len(page) + len(name) + len(chunk) > 5800:
                page = interactions.Embed(title=title[:256], color=color)
                pages.append(page)
            page.add_field(name=name, value=chunk)
    return pages




class LoLRecap(Extension):
    def __init__(self, bot):
        self.bot: interactions.Client = bot

    @slash_command(name='recap',
                   description='Mon récap par durée ou nombre de parties, avec filtre champion',
                   options=[
                       SlashCommandOption(
                           name='riot_id',
                           description='pseudo lol',
                           type=interactions.OptionType.STRING,
                           required=True,
                           autocomplete=True),
                       SlashCommandOption(
                           name='riot_tag',
                           description='tag',
                           type=interactions.OptionType.STRING,
                           required=False),
                       SlashCommandOption(
                           name='mode',
                           description='mode de jeu',
                           type=interactions.OptionType.STRING,
                           required=False,
                           choices=[
                               SlashCommandChoice(name='Normal', value='NORMAL'),
                               SlashCommandChoice(name='Ranked', value='RANKED'),
                               SlashCommandChoice(name='Aram', value='ARAM'),
                               SlashCommandChoice(name='Swiftplay', value='SWIFTPLAY')]
                       ),
                       SlashCommandOption(
                           name='observation',
                           description='Observation (Durée), 24h par défaut. Incompatible avec observation_parties.',
                           type=interactions.OptionType.STRING,
                           required=False,
                           choices=[
                               SlashCommandChoice(name='24h', value='24h'),
                               SlashCommandChoice(name='48h', value='48h'),
                               SlashCommandChoice(name='72h', value='72h'),
                               SlashCommandChoice(name='96h', value='96h'),
                               SlashCommandChoice(name='Semaine', value='Semaine'),
                               SlashCommandChoice(name='Mois', value='Mois'),
                               SlashCommandChoice(name="Aujourd'hui", value='today')
                                
                           ]
                       ),
                       SlashCommandOption(
                           name='observation_parties',
                           description='Observation (Nombre de parties). Incompatible avec observation (Durée).',
                           type=interactions.OptionType.INTEGER,
                           required=False,
                           choices=[SlashCommandChoice(name=f'{count} parties', value=count)
                                    for count in GAME_COUNTS]),
                       SlashCommandOption(
                           name='champion',
                           description='Limiter le récap aux parties jouées avec ce champion',
                           type=interactions.OptionType.STRING,
                           required=False,
                           autocomplete=True)
                   ])
    async def my_recap(self,
                       ctx: SlashContext,
                       riot_id: str,
                       riot_tag: str = None,
                       mode: str = None,
                       observation: str = None,
                       observation_parties: int = None,
                       champion: str = None):
        await ctx.defer(ephemeral=False)

        # Valider les options avant toute lecture de la base.
        try:
            sql, params, observation_label = recap_query(
                riot_id, riot_tag or '', mode, observation, observation_parties, champion)
        except ValueError as error:
            return await ctx.send(str(error))

        if riot_tag is None:
            try:
                riot_tag = await asyncio.to_thread(get_tag, riot_id)
            except ValueError:
                return await ctx.send('Plusieurs comptes avec ce riot_id, merci de préciser le tag')
        riot_tag = riot_tag.upper()
        params['riot_tag'] = riot_tag
        df = (await asyncio.to_thread(
            lire_bdd_perso, sql, params=params, index_col='id')).transpose()

        if df.shape[0] >= 1:


            df.drop_duplicates(subset='match_id', inplace=True)

            # on convertit dans le bon fuseau horaire
            df['datetime'] = pd.to_datetime(
                df['datetime'], utc=True).dt.tz_convert('Europe/Paris')

            df.sort_values(by='datetime', ascending=False, kind='stable', inplace=True)

            df['datetime'] = df['datetime'].dt.strftime('%d/%m %H:%M')

            df['victoire'] = df['victoire'].map(
                {True: 'Victoire', False: 'Défaite'})

            df['victory_predicted'] = df['victory_predicted'].map(
                {True: 'Victoire', False: 'Défaite'})

            # Total
            total_kda = f'**{df["kills"].sum()}**/**{df["deaths"].sum()}**/**{df["assists"].sum()}**  | Moyenne : **{df["kills"].mean():.2f}**/**{df["deaths"].mean():.2f}**/**{df["assists"].mean():.1f}** (**{df["kda"].mean():.2f}**) | KP : **{df["kp"].mean():.2f}**% '
            total_lp = f'**{df["ecart_lp"].sum()}**'

            gold_moyen = f'**{df["ecart_gold"].mean():.0f}**'
            gold_moyen_v = f'**{df[df["victoire"] == "Victoire"]["ecart_gold"].mean():.0f}**'
            gold_moyen_d = f'**{df[df["victoire"] == "Défaite"]["ecart_gold"].mean():.0f}**'

            gold_moyen_v = f'**0**' if gold_moyen_v == '**nan**' else gold_moyen_v
            gold_moyen_d = f'**0**' if gold_moyen_d == '**nan**' else gold_moyen_d

            # Serie de kills
            total_quadra = df['quadra'].sum()
            total_penta = df['penta'].sum()

            solokills = df['solokills'].sum()

            # Moyenne
            duree_moyenne = df['time'].mean()
            mvp_moyenne = df['mvp'].mean()



            # Victoire
            nb_victoire_total = df['victoire'].value_counts().get(
                'Victoire', 0)
            nb_defaite_total = df['victoire'].value_counts().get('Défaite', 0)


            total_victoire = f'Victoire : **{nb_victoire_total}** | Défaite : **{nb_defaite_total}** ({nb_victoire_total/(nb_victoire_total+nb_defaite_total)*100:.2f}%) | LP {total_lp}' 

            # Victoire (model)
            nb_victoire_total_model = df['victory_predicted'].value_counts().get(
                'Victoire', 0)
            nb_defaite_total_model = df['victory_predicted'].value_counts().get('Défaite', 0)

            # Ajouter une phrase dans total_victoire s'il y a des données

            if (nb_victoire_total_model + nb_defaite_total_model) > 0:
                total_victoire += f'\n __Prediction__ Victoire : **{nb_victoire_total_model}** | Défaite : **{nb_defaite_total_model}** '

                if df['victory_predicted'].isna().sum() > 0:
                    total_victoire += f' | NA : **{df["victory_predicted"].isna().sum()}**'



            df['champion'] = df['champion'].str.capitalize()
            champion_counts = df['champion'].sort_values(
                ascending=False).value_counts()
            
            champion_lp = df.groupby('champion')[['ecart_lp']].sum()
            

            txt_champ = ''.join(
                f'{emote_champ_discord.get(champ, "inconnu")} : **{number}**'
                + (f' ({lp} LP)' if (lp := champion_lp.loc[champ].values[0]) != 0 else '')
                + ' | '
                for champ, number in champion_counts.items()
            )

            
            # On prépare l'embed
            data = get_data_bdd(
                'SELECT "R", "G", "B" from tracker WHERE riot_id = :riot_id and riot_tagline = :riot_tag',
                {'riot_id': riot_id.lower().replace(' ', ''), 'riot_tag' : riot_tag},
            ).fetchall()

            title = f"Recap **{riot_id.upper()} #{riot_tag}** {observation_label}"
            color = interactions.Color.from_rgb(data[0][0], data[0][1], data[0][2])
            description = (f'{len(df)} parties disponibles sur {observation_parties} demandées.'
                           if observation_parties is not None else None)
            fields = [
                ('KDA', total_kda),
                ('Gold', f'Moyenne : {gold_moyen} (V : {gold_moyen_v} | D : {gold_moyen_d})'),
                ('Champions', txt_champ),
                ('Ratio', total_victoire),
                ('Autres', f'Durée moyenne : **{duree_moyenne:.0f}**m | MVP : **{mvp_moyenne:.1f}**'
                 + (f' | Solo kills : **{solokills}**' if solokills > 0 else '')),
            ]
            if total_quadra + total_penta > 0:
                fields.append(('Série de kills', f'Quadra : **{total_quadra}** | Penta : **{total_penta}**'))
            txt = ''

            emote_status_match = {'Victoire' : ':green_circle:', 'Défaite' : ':red_circle:'}

            df['mode'] = df['mode'].replace({'ARAM': 'A',
                                             'RANKED': 'R',
                                             'SWIFTPLAY': 'S'})
            
            df['proba1'] = df['proba1'].fillna(-1)
            df['proba2'] = df['proba2'].fillna(-1)
            df['team'] = df['team'].fillna('BLUE')

            df['proba_win'] = df.apply(lambda x : x['proba2'] if x['team'] == 'BLUE' else x['proba1'], axis=1)
           
            
            # On affiche les résultats des matchs
            
            for index, match in df.iterrows():
                rank_img = emote_rank_discord[match["tier"]]
                champ_img = emote_champ_discord.get(match["champion"].capitalize(), 'inconnu')
                url_game = f'https://www.leagueofgraphs.com/fr/match/euw/{str(match["match_id"])[5:]}#participant{int(match["id_participant"])+1}'
                kda = f'**{match["kills"]}**/**{match["deaths"]}**/**{match["assists"]}** ({match["kp"]}%)'
                mode = match['mode']

                if mode in ['NORMAL', 'S']:
                    if match['proba_win'] == -1:
                        txt += f'[{match["datetime"]}]({url_game}) {champ_img} [{mode}] | {emote_status_match[match["victoire"]]} | MVP **{match["mvp"]}** | {kda} | **{match["ecart_lp"]}** | G : {match["ecart_gold"]} \n'
                    else:
                        txt += f'[{match["datetime"]}]({url_game}) {champ_img} [{mode}] | {emote_status_match[match["victoire"]]} | MVP **{match["mvp"]}** | {kda} | **{match["ecart_lp"]}** | G : {match["ecart_gold"]} | P : {match["proba_win"]}% \n'
                else:
                    if match['proba_win'] == -1:
                        txt += f'[{match["datetime"]}]({url_game}) {champ_img} [{mode}] | {rank_img} {match["rank"]}] | {emote_status_match[match["victoire"]]} | MVP **{match["mvp"]}** | {kda} | **{match["ecart_lp"]}** | G : {match["ecart_gold"]} \n'
                    else:
                        txt += f'[{match["datetime"]}]({url_game}) {champ_img} [{mode}] | {rank_img} {match["rank"]}] | {emote_status_match[match["victoire"]]} | MVP **{match["mvp"]}** | {kda} | **{match["ecart_lp"]}** | G : {match["ecart_gold"]} | P : {match["proba_win"]}% \n'

            fields.append((f'Historique ({len(df)} parties)', txt))
            embeds = recap_pages(title, color, description, fields)
            if len(embeds) == 1:
                await ctx.send(embeds=embeds[0])
            else:
                paginator = Paginator.create_from_embeds(self.bot, *embeds)
                # Discord limite les menus de sélection à 25 choix.
                paginator.show_select_menu = len(embeds) <= 25
                await paginator.send(ctx)

        else:
            await ctx.send(f'Aucune partie enregistrée pour {riot_id}#{riot_tag} — {observation_label}.')


    @my_recap.autocomplete('champion')
    async def autocomplete_recap_champion(self, ctx: interactions.AutocompleteContext):
        search = normalize_champion(ctx.input_text)
        choices = [
            {'name': name, 'value': name}
            for name in sorted(emote_champ_discord)
            if search in normalize_champion(name)
        ]
        await ctx.send(choices=choices[:25])

    @my_recap.autocomplete('riot_id')

    async def autocomplete_recap(self, ctx: interactions.AutocompleteContext):

        liste_choix = await autocomplete_riotid(int(ctx.guild.id), ctx.input_text)

        await ctx.send(choices=liste_choix)

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
