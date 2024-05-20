
from interactions import SlashCommandOption, Extension, SlashContext, SlashCommandChoice, Task, IntervalTrigger, slash_command
import interactions
import pandas as pd
from fonctions.gestion_bdd import lire_bdd_perso
from fonctions.match import emote_champ_discord
import numpy as np
from interactions.ext.paginators import Paginator
import dataframe_image as dfi
import os

saison = int(lire_bdd_perso('select * from settings', format='dict', index_col='parametres')['saison']['value'])

async def export_as_image(df, ctx : SlashContext, content=None):
    dfi.export(df, 'image.png', max_cols=-1,
                       max_rows=-1, table_conversion="matplotlib")

    if content == None:
        await ctx.send(files=interactions.File('image.png'))
    
    else:
        await ctx.send(content=content, files=interactions.File('image.png'))
    

    os.remove('image.png')

class AnalyseLoLSeason(Extension):
    def __init__(self, bot):
        self.bot: interactions.Client = bot
        


    @slash_command(name='lol_analyse_season', description='Stats sur sa saison')
    async def lol_analyse_season(self, ctx: SlashContext):
        pass


    @lol_analyse_season.subcommand("champion",
                            sub_cmd_description="Permet d'afficher des statistiques sur les champions rencontrés dans la saison",
                            options=[
                                SlashCommandOption(
                                    name="riot_id",
                                    description="Nom du joueur",
                                    type=interactions.OptionType.STRING,
                                    required=True),
                                SlashCommandOption(
                                    name="riot_tag",
                                    description="Nom du joueur",
                                    type=interactions.OptionType.STRING,
                                    required=True),
                                SlashCommandOption(
                                    name="mode",
                                    description="Mode de jeu",
                                    type=interactions.OptionType.STRING,
                                    required=True,
                                    choices=[SlashCommandChoice(name='RANKED', value='RANKED'),
                                             SlashCommandChoice(name='ARAM', value='ARAM')]),
                                SlashCommandOption(
                                    name="saison",
                                    description="Quelle saison?",
                                    type=interactions.OptionType.INTEGER,
                                    required=False),
                                SlashCommandOption(
                                    name="champion",
                                    description="Champion joué",
                                    type=interactions.OptionType.STRING,
                                    required=False),
                                SlashCommandOption(
                                    name="role",
                                    description="role",
                                    type=interactions.OptionType.STRING,
                                    required=False,
                                    choices=[
                                        SlashCommandChoice(name='top', value='TOP'),
                                        SlashCommandChoice(name='jungle', value='JUNGLE'),
                                        SlashCommandChoice(name='mid', value='MID'),
                                        SlashCommandChoice(name='adc', value='ADC'),
                                        SlashCommandChoice(name='support', value='SUPPORT')])
                                ])
    async def analyse_champion(self,
                      ctx: SlashContext,
                      riot_id: str,
                      riot_tag:str,
                      mode:str,
                      saison = saison,
                      champion = None,
                      role = None):
        
        riot_id = riot_id.lower().replace(' ', '')
        riot_tag = riot_tag.upper() 
        
        await ctx.defer(ephemeral=False)     
        
        df = lire_bdd_perso(f'''SELECT matchs_joueur.*, matchs.champion, matchs.role, matchs.victoire from tracker
        INNER JOIN matchs ON tracker.id_compte = matchs.joueur
        INNER JOIN matchs_joueur ON matchs.match_id = matchs_joueur.match_id
        WHERE tracker.riot_id = '{riot_id}'
        AND tracker.riot_tagline = '{riot_tag}'
        AND matchs.season = {saison}
        AND matchs.mode = '{mode}' ''', index_col='match_id').T
        
        if champion != None:
            df = df[df['champion'] == champion.replace(' ', '').capitalize()]
        
        if role != None:
            df = df[df['role'] == role]
        
        nbgames = df.shape[0]
        
        
        dict_allie = {}
        dict_ennemi = {}

        dict_allie = {}
        dict_ennemi = {}
        victory = []

        for match_id, data in df.iterrows():
            for i in range(1,6):
                name_allie = data[f'allie{i}'].lower()
                name_ennemi = data[f'ennemi{i}'].lower()
                champ_allie = data[f'champ{i}']
                champ_ennemi = data[f'champ{i+5}']
                victory.append(data['victoire'])
                
                if name_allie in dict_allie.keys():
                    name_allie = f'{name_allie} + {match_id}'
                dict_allie[name_allie] = champ_allie
                if name_ennemi in dict_ennemi:
                    name_ennemi = f'{name_ennemi} + {match_id}'
                dict_ennemi[name_ennemi] = champ_ennemi

        def count_champion(dict):
            df_champion = pd.DataFrame.from_dict(dict, orient='index', columns=['champion'])
            df_champion['victoire'] = victory
            df_champion['victoire'] = df_champion['victoire'].astype(int)
            df_champion = df_champion[~df_champion.index.str.contains(f'{riot_id}#{riot_tag.lower()}')]
            df_count = df_champion.groupby('champion').agg(count=('champion', 'count'),
                                                        victory=('victoire', 'sum'))
            df_count.sort_values('count', ascending=False, inplace=True)
            df_count.index = df_count.index.str.capitalize()
            df_count['%'] = np.int8((df_count['count'] / df_count['count'].sum())*100)
            df_count['%_victoire'] = np.int8(df_count['victory'] / df_count['count'] * 100)
            
            # return df_champion
            
            return df_count          
        
        df_allie = count_champion(dict_allie)
        df_ennemi = count_champion(dict_ennemi)    
        
        def embedding(df, title, part):
            embed = interactions.Embed(f'{title} ({nbgames} games)')
            txt = ''
            for champion, data in df.iterrows():
                count = data['count']
                pick_percent = data['%']
                victory_percent = data['%_victoire']
                txt += f'{emote_champ_discord.get(champion, champion)} Pick **{count}** fois ({pick_percent}%) -> WR : **{victory_percent}%** \n'
            
            embed.add_field(name=f'{mode} PARTIE {part}', value=txt)    
            
            return embed
        
        
        embed_allie_top10 = embedding(df_allie.iloc[:10], 'ALLIE', 1)
        embed_allie_top20 = embedding(df_allie.iloc[10:20], 'ALLIE', 2)
        embed_allie_top30 = embedding(df_allie.iloc[20:30], 'ALLIE', 3)
        embed_ennemi_top10 = embedding(df_ennemi.iloc[:10], 'ENNEMI', 1)
        embed_ennemi_top20 = embedding(df_ennemi.iloc[10:20], 'ENNEMI', 2)
        embed_ennemi_top30 = embedding(df_ennemi.iloc[20:30], 'ENNEMI', 3)
        
        embeds = [embed_allie_top10, embed_allie_top20, embed_allie_top30, embed_ennemi_top10, embed_ennemi_top20, embed_ennemi_top30]
    

        paginator = Paginator.create_from_embeds(
                    self.bot,
                    *embeds)

        paginator.show_select_menu = True
        await paginator.send(ctx)

    @lol_analyse_season.subcommand("ecart_stats",
                            sub_cmd_description="Permet d'afficher des statistiques sur des écarts durant la saison",
                            options=[
                                SlashCommandOption(
                                    name="methode",
                                    description="Methode",
                                    type=interactions.OptionType.STRING,
                                    required=False,
                                    choices=[
                                        SlashCommandChoice(name='gold_individuel', value='ecart_gold'),
                                        SlashCommandChoice(name='gold_team', value='ecart_gold_team'),
                                        SlashCommandChoice(name='kills', value='kills'),
                                        SlashCommandChoice(name='morts', value='deaths'),
                                        SlashCommandChoice(name='assists', value='assists'),
                                        SlashCommandChoice(name='dmg', value='dmg'),
                                        SlashCommandChoice(name='tank', value='dmg_tank'),
                                        SlashCommandChoice(name='cs', value='cs'),
                                        SlashCommandChoice(name='vision', value='vision_score'),
                                        SlashCommandChoice(name='afk', value='afk'),
                                        SlashCommandChoice(name='duree', value='time')]),
                                SlashCommandOption(
                                    name="saison",
                                    description="Quelle saison?",
                                    type=interactions.OptionType.INTEGER,
                                    required=False),
                                SlashCommandOption(
                                    name="champion",
                                    description="Quelle champion?",
                                    type=interactions.OptionType.INTEGER,
                                    required=False),
                                SlashCommandOption(
                                    name="calcul",
                                    description="Calcul",
                                    type=interactions.OptionType.STRING,
                                    required=False,
                                    choices=[
                                        SlashCommandChoice(name='Somme', value='sum'),
                                        SlashCommandChoice(name='Moyenne', value='mean')]),
                                SlashCommandOption(
                                    name="minmax",
                                    description="Inclure min et max?",
                                    type=interactions.OptionType.BOOLEAN,
                                    required=False),
                                SlashCommandOption(
                                    name="role",
                                    description="role",
                                    type=interactions.OptionType.STRING,
                                    required=False,
                                    choices=[
                                        SlashCommandChoice(name='top', value='TOP'),
                                        SlashCommandChoice(name='jungle', value='JUNGLE'),
                                        SlashCommandChoice(name='mid', value='MID'),
                                        SlashCommandChoice(name='adc', value='ADC'),
                                        SlashCommandChoice(name='support', value='SUPPORT')])
                                ])
    async def analyse_gold(self,
                      ctx: SlashContext,
                      methode = 'ecart_gold',
                      saison = 0,
                      champion = None,
                      calcul = 'sum',
                      minmax = False,
                      role = None):
        
        
        await ctx.defer(ephemeral=False)     
        
        df = lire_bdd_perso(f'''SELECT tracker.riot_id, matchs.champion, matchs.role, matchs.victoire, matchs.{methode}, matchs.tier, matchs.season from tracker
        INNER JOIN matchs ON tracker.id_compte = matchs.joueur
        AND matchs.mode = 'RANKED'
        and server_id = {int(ctx.guild_id)} ''', index_col=None).T

        if minmax:
            aggfunc = [calcul, 'count', 'min', 'max']
        else:
            aggfunc = [calcul, 'count']

        if champion != None:
            df = df[df['champion'] == champion.replace(' ', '').capitalize()]
        
        if role != None:
            df = df[df['role'] == role]
        
        if saison != 0:
            df = df[df['season'] == saison]

        df['victoire'].replace({False : 'Défaite', True : 'Victoire'}, inplace=True )

        df_pivot = df.pivot_table(index='riot_id',
                                columns=['victoire'],
                                values=methode,
                                aggfunc=aggfunc,
                                fill_value=0)
        
        df_pivot = df_pivot.astype(int)

        df_pivot['Ecart'] = df_pivot[(calcul, 'Défaite')] + df_pivot[(calcul, 'Victoire')]
        df_pivot.sort_values('Ecart', ascending=False, inplace=True)
        
        await export_as_image(df_pivot, ctx)
        
  
                
def setup(bot):
    AnalyseLoLSeason(bot)


   