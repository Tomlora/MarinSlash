import numpy as np
import pandas as pd
from fonctions.gestion_bdd import lire_bdd, lire_bdd_perso
import interactions
from interactions import SlashCommandChoice, SlashCommandOption, Extension, SlashContext, slash_command, AutocompleteContext
from interactions.ext.paginators import Paginator
from fonctions.params import Version, saison
from fonctions.match import trouver_records, get_champ_list, get_version, trouver_records_multiples, emote_champ_discord
from aiohttp import ClientSession
import plotly.express as px
import asyncio
from fonctions.channels_discord import get_embed, mention

def option_stats_records(name, params, description='type de recherche'):
    option = SlashCommandOption(
        name=name,
        description=description,
        type=interactions.OptionType.SUB_COMMAND,
        options=params)

    return option


emote = {
    "KDA": ":star:",
    "KP": ":trophy:",
    "CS": ":ghost:",
    "CS/MIN": ":ghost:",
    "KILLS": ":dagger:",
    "DEATHS": ":skull:",
    "ASSISTS": ":crossed_swords:",
    'WARDS_SCORE': ":eye:",
    'WARDS_POSEES': ":eyes:",
    'WARDS_DETRUITES': ":mag:",
    'WARDS_PINKS': ":red_circle:",
    "AVANTAGE_VISION": ":eyes:",
    "AVANTAGE_VISION_SUPPORT": ":eyes:",
    "VISION/MIN": ":eyes:",
    'DEGATS_INFLIGES': ":dart:",
    'DAMAGE_RATIO': ":dart:",
    'DMG_TOTAL': ":dart:",
    "% DMG": ":magic_wand:",
    'DOUBLE': ":two:",
    'TRIPLE': ":three:",
    'QUADRA': ":four:",
    'PENTA': ":five:",
    'DUREE_GAME': ":timer:",
    'SPELLS_USED': ":gun:",
    'BUFFS_VOLEES': "<:PandaWow:732316840495415398>",
    'SPELLS_EVITES': ":white_check_mark:",
    'CS_AVANTAGE': ":ghost:",
    'CS_AVANTAGES': ":ghost:",
    'SOLOKILLS': ":karate_uniform:",
    'CS_APRES_10_MIN': ":ghost:",
    'CS/MIN': ":ghost:",
    'SERIES_DE_KILLS': ":crossed_swords:",
    'NB_SERIES_DE_KILLS': ":crossed_swords:",
    'DOMMAGES_TANK': ":shield:",
    'DOMMAGES_TANK%': ":shield:",
    'DOMMAGES_REDUITS': ":shield:",
    'DOMMAGES_TOWER': ":hook:",
    'DAMAGE_RATIO_ENCAISSE': ":shield:",
    'GOLDS_GAGNES': ":euro:",
    'TOTAL_HEALS': ":sparkling_heart:",
    'HEALS_SUR_ALLIES': ":two_hearts:",
    'NBGAMES': ":star:",
    "KILLS_MOYENNE": ":dagger:",
    "DEATHS_MOYENNE": ":skull:",
    "ASSISTS_MOYENNE": ":crossed_swords:",
    'WARDS_MOYENNE': ":eye:",
    "EARLY_DRAKE": ":timer:",
    "EARLY_BARON": ":timer:",
    "SKILLSHOTS_HIT": ":dart:",
    "SKILLSHOTS_DODGES": ":dash:",
    "TOWER_PLATES": ":ticket:",
    "ECART_LEVEL": ":wave:",
    "NB_COURONNE_1_GAME": ":crown:",
    "SERIE_VICTOIRE": ":fire:",
    "SHIELD": ":shield:",
    "ALLIE_FEEDER": ":monkey_face:",
    "KDA_ARAM": ":star:",
    "KP_ARAM": ":trophy:",
    "CS_ARAM": ":ghost:",
    "CS/MIN_ARAM": ":ghost:",
    "KILLS_ARAM": ":dagger:",
    "DEATHS_ARAM": ":skull:",
    "ASSISTS_ARAM": ":crossed_swords:",
    "AVANTAGE_VISION": ":eyes:",
    "AVANTAGE_VISION_SUPPORT": ":eyes:",
    "VISION/MIN": ":eyes:",
    "DEGATS_INFLIGES_ARAM": ":dart:",
    "DAMAGE_RATIO_ARAM": ":dart:",
    "DMG_TOTAL_ARAM": ":dart:",
    "% DMG_ARAM": ":magic_wand:",
    "DOUBLE_ARAM": ":two:",
    "TRIPLE_ARAM": ":three:",
    "QUADRA_ARAM": ":four:",
    "PENTA_ARAM": ":five:",
    "DUREE_GAME_ARAM": ":timer:",
    "SPELLS_USED_ARAM": ":gun:",
    "BUFFS_VOLEES_ARAM": "<:PandaWow:732316840495415398>",
    "SPELLS_EVITES_ARAM": ":white_check_mark:",
    "CS_AVANTAGE_ARAM": ":ghost:",
    "CS_AVANTAGES_ARAM": ":ghost:",
    "SOLOKILLS_ARAM": ":karate_uniform:",
    "CS_APRES_10_MIN_ARAM": ":ghost:",
    "CS/MIN_ARAM": ":ghost:",
    "SERIES_DE_KILLS_ARAM": ":crossed_swords:",
    "NB_SERIES_DE_KILLS_ARAM": ":crossed_swords:",
    "DOMMAGES_TANK_ARAM": ":shield:",
    "DOMMAGES_TANK%_ARAM": ":shield:",
    "DOMMAGES_REDUITS_ARAM": ":shield:",
    "DOMMAGES_TOWER_ARAM": ":hook:",
    "DAMAGE_RATIO_ENCAISSE_ARAM": ":shield:",
    "GOLDS_GAGNES_ARAM": ":euro:",
    "TOTAL_HEALS_ARAM": ":sparkling_heart:",
    "HEALS_SUR_ALLIES_ARAM": ":two_hearts:",
    "NBGAMES_ARAM": ":star:",
    "KILLS_MOYENNE_ARAM": ":dagger:",
    "DEATHS_MOYENNE_ARAM": ":skull:",
    "ASSISTS_MOYENNE_ARAM": ":crossed_swords:",
    "SKILLSHOTS_HIT_ARAM": ":dart:",
    "SKILLSHOTS_DODGES_ARAM": ":dash:",
    "NB_COURONNE_1_GAME_ARAM": ":crown:",
    "SHIELD_ARAM": ":shield:",
    "ALLIE_FEEDER_ARAM": ":monkey_face:"
}

emote_v2 = {
    "kda": ":star:",
    "kp": ":trophy:",
    "cs": ":ghost:",
    "cs_jungle": ":ghost:",
    "jgl_dix_min": ":ghost:",
    "cs_min": ":ghost:",
    "cs_dix_min": ":ghost:",
    "kills": ":dagger:",
    "kills+assists" : ":dagger:",
    "team_kills": ":dagger:",
    "deaths": ":skull:",
    "team_deaths": ":skull:",
    "assists": ":crossed_swords:",
    'vision_score': ":eye:",
    'vision_wards': ":eyes:",
    'vision_wards_killed': ":mag:",
    'vision_pink': ":red_circle:",
    "vision_avantage": ":eyes:",
    "vision_min": ":eyes:",
    'dmg': ":dart:",
    'dmg_ad': ":dart:",
    'dmg_ap': ":dart:",
    'dmg_true': ":dart:",
    'damageratio': ":dart:",
    'dmg_min': ":dart:",
    'dmg/gold' : ":dart:",
    "% DMG": ":magic_wand:",
    'double': ":two:",
    'triple': ":three:",
    'quadra': ":four:",
    'penta': ":five:",
    'time': ":timer:",
    'SPELLS_USED': ":gun:",
    'BUFFS_VOLEES': "<:PandaWow:732316840495415398>",
    'SPELLS_EVITES': ":white_check_mark:",
    'cs_max_avantage': ":ghost:",
    'solokills': ":karate_uniform:",
    'CS_APRES_10_MIN': ":ghost:",
    'CS/MIN': ":ghost:",
    'serie_kills': ":crossed_swords:",
    'NB_SERIES_DE_KILLS': ":crossed_swords:",
    'dmg_reduit': ":shield:",
    'tankratio': ":shield:",
    'dmg_tank': ":shield:",
    'gold': ":euro:",
    'gold_min': ":euro:",
    'drake': ":dragon:",
    'baron': ":space_invader:",
    'herald': ":space_invader:",
    'heal_total': ":sparkling_heart:",
    'heal_allies': ":two_hearts:",
    "early_drake": ":timer:",
    "early_baron": ":timer:",
    "temps_dead": ":timer:",
    "level_max_avantage": ":wave:",
    "couronne": ":crown:",
    "shield": ":shield:",
    "allie_feeder": ":monkey_face:",
    "snowball" : ":baseball:",
    "temps_vivant" : ":hourglass:",
    "dmg_tower" : ":tokyo_tower:",
    "gold_share" : ":dollar:",
    "ecart_gold_team" : ":euro:",
    "temps_avant_premiere_mort" : ":timer:",
}

choice_pantheon = [SlashCommandChoice(name="KDA", value="KDA"),
                   SlashCommandChoice(name='KDA moyenne', value='KDA moyenne'),
                   SlashCommandChoice(name='vision', value='VISION'),
                   SlashCommandChoice(name='vision moyenne', value='VISION moyenne'),
                   SlashCommandChoice(name='CS', value='CS'),
                   SlashCommandChoice(name='Solokills', value='SOLOKILLS'),
                   SlashCommandChoice(name='games', value='GAMES')]


class Recordslol(Extension):
    def __init__(self, bot):
        self.bot: interactions.Client = bot
        self.time_mini = {'RANKED' : 20, 'ARAM' : 10, 'FLEX' : 20} # minutes minimum pour compter dans les records
        
        self.fichier_kills = ['kills', 'assists', 'deaths', 'double', 'triple', 'quadra', 'penta', 'solokills', 'team_kills', 'team_deaths', 'kda', 'kp', 'kills+assists', 'serie_kills'] 
        self.fichier_dmg = ['dmg', 'dmg_ad', 'dmg_ap', 'dmg_true', 'damageratio', 'dmg_min', 'dmg/gold']
        self.fichier_vision = ['vision_score', 'vision_pink', 'vision_wards', 'vision_wards_killed', 'vision_min', 'vision_avantage']
        self.fichier_farming = ['cs', 'cs_jungle', 'cs_min', 'cs_dix_min', 'jgl_dix_min', 'cs_max_avantage']
        self.fichier_tank_heal = ['dmg_tank', 'dmg_reduit', 'dmg_tank', 'tankratio', 'shield', 'heal_total', 'heal_allies']
        self.fichier_objectif = ['baron', 'drake', 'herald', 'early_drake', 'early_baron', 'dmg_tower']
        self.fichier_divers = ['time', 'gold', 'gold_min', 'gold_share', 'ecart_gold_team', 'level_max_avantage', 'temps_dead', 'temps_vivant', 'allie_feeder', 'temps_avant_premiere_mort', 'couronne', 'snowball']

        self.liste_complete = self.fichier_kills + self.fichier_dmg + self.fichier_vision + self.fichier_farming + self.fichier_tank_heal + self.fichier_objectif + self.fichier_divers

    @slash_command(name='lol_records', description='records League of Legends')
    async def records_lol(self, ctx: SlashContext):
        pass


    parameters_communs = [
        SlashCommandOption(
            name="mode",
            description="Quel mode de jeu ?",
            type=interactions.OptionType.STRING,
            required=True, choices=[
                SlashCommandChoice(name='ranked',
                       value='RANKED'),
                SlashCommandChoice(name='aram', value='ARAM'),
                SlashCommandChoice(name='flex', value='FLEX')]),
        SlashCommandOption(
            name='saison',
            description='saison league of legends',
            type=interactions.OptionType.INTEGER,
            required=False,
            min_value=12,
            max_value=saison),
        SlashCommandOption(
            name='champion',
            description='champion',
            type=interactions.OptionType.STRING,
            required=False),
        SlashCommandOption(
            name='view',
            description='global ou serveur ?',
            type=interactions.OptionType.STRING,
            required=False,
            choices=[
                SlashCommandChoice(name='global', value='global'),
                SlashCommandChoice(name='serveur', value='serveur')
            ]
        )]

    parameters_personnel = [
        SlashCommandOption(
            name="mode",
            description="Quel mode de jeu ?",
            type=interactions.OptionType.STRING,
            required=True, choices=[
                SlashCommandChoice(name='ranked',
                       value='RANKED'),
                SlashCommandChoice(name='aram', value='ARAM'),
                SlashCommandChoice(name='flex', value='FLEX')]),
        SlashCommandOption(
            name="joueur",
            description="Compte LoL (pas nécessaire si compte discord renseigné)",
            type=interactions.OptionType.STRING,
            required=False),
        SlashCommandOption(
            name="compte_discord",
            description='compte discord (pas nécessaire si compte lol renseigné)',
            type=interactions.OptionType.USER,
            required=False
        ),
        SlashCommandOption(
            name='saison',
            description='saison league of legends',
            type=interactions.OptionType.INTEGER,
            required=False,
            min_value=12,
            max_value=saison),
        SlashCommandOption(
            name='champion',
            description='champion',
            type=interactions.OptionType.STRING,
            required=False)]

    
    @records_lol.subcommand('general',
                                sub_cmd_description='Records tout confondus',
                                options=parameters_communs)
    async def records_list_general(self, ctx:SlashContext,
                                   saison:int=saison,
                                   mode:str = 'ranked',
                                   joueur=None,
                                   compte_discord:interactions.User=None,
                                   champion:str=None,
                                   view='global'):
        
        await ctx.defer(ephemeral=False)
        
        methode_pseudo = 'discord'
        
        if view == 'global':
            fichier = lire_bdd_perso(f'''SELECT distinct matchs.*, tracker.discord from matchs
                                     INNER JOIN tracker on tracker.index = matchs.joueur
                                     where season = {saison}
                                     and mode = '{mode}'
                                     and time >= {self.time_mini[mode]}
                                     and tracker.banned = false ''', index_col='id').transpose()
        elif view == 'serveur':
            fichier = lire_bdd_perso(f'''SELECT distinct matchs.*, tracker.discord from matchs
                                     INNER JOIN tracker on tracker.index = matchs.joueur
                                     where season = {saison}
                                     and mode = '{mode}'
                                     and server_id = {int(ctx.guild_id)}
                                     and time >= {self.time_mini[mode]}
                                     and tracker.banned = false ''', index_col='id').transpose()
            
        if champion != None:
            
            champion = champion.capitalize()

            fichier = fichier[fichier['champion'] == champion] 
            
        if champion == None:
                title = f'Records {mode} S{saison}'
        else:
                title = f'Records {mode} S{saison} ({champion})'

        fichier_farming = self.fichier_farming.copy()
        fichier_divers = self.fichier_divers.copy()

        # on rajoute quelques éléments sur d'autres pages...

        
        if mode == 'RANKED':
            fichier_divers.remove('snowball')

        if mode == 'ARAM':  # on vire les records qui ne doivent pas être comptés en aram

            fichier_farming.remove('cs_jungle')
            fichier_farming.remove('jgl_dix_min')


        def format_value(joueur, champion, url, short=False):
            text = ''
            for j, c, u in zip(joueur, champion, url):
                if short:
                    text += f'**__ {j} __ {c} ** \n'
                else:
                    text += f'**__{j}__** [{c}]({u}) \n'
            return text
        
        def creation_embed(fichier, column, methode_pseudo, embed, methode='max'):
                joueur, champion, record, url = trouver_records_multiples(fichier, column, methode, identifiant=methode_pseudo)
                # on montre l'image du champ uniquement quand le record appartient à une seule personne sinon on dépasse la limite de caractères
                
                value_text = format_value(joueur, champion, url, short=False) if len(joueur) > 1 else f"**{joueur[0]}** {emote_champ_discord.get(champion[0].capitalize(), 'inconnu')} [G]({url[0]})\n"
                # value_text = format_value(joueur, champion, url, short=False) if len(joueur) > 1 else f"**{joueur[0]}** [{champion[0]}]({url[0]})\n"
                
                embed.add_field(
                    name=f'{emote_v2.get(column, ":star:")}{column.upper()}',
                    value=f"Records : __ {record} __ \n {value_text}",
                    inline=True
                )
                
                return embed
        
        embed1 = interactions.Embed(
            title=title + " Kills", color=interactions.Color.random())    

        for column in self.fichier_kills:
            
            embed1 = creation_embed(fichier, column, methode_pseudo, embed1)
          

        embed2 = interactions.Embed(
            title=title + " DMG", color=interactions.Color.random())

        for column in self.fichier_dmg:
            
            embed2 = creation_embed(fichier, column, methode_pseudo, embed2)

        embed5 = interactions.Embed(
            title=title + " Farming", color=interactions.Color.random())

        for column in fichier_farming:
            
            embed5 = creation_embed(fichier, column, methode_pseudo, embed5)

        embed6 = interactions.Embed(
            title=title + " Tank/Heal", color=interactions.Color.random())

        for column in self.fichier_tank_heal:
            
            embed6 = creation_embed(fichier, column, methode_pseudo, embed6)

        embed7 = interactions.Embed(
            title=title + " Divers", color=interactions.Color.random())

        for column in fichier_divers:
            
            embed7 = creation_embed(fichier, column, methode_pseudo, embed7)


        if mode != 'ARAM':
            
            embed3 = interactions.Embed(
            title=title + " Vision", color=interactions.Color.random())

            for column in self.fichier_vision:
                
                embed3 = creation_embed(fichier, column, methode_pseudo, embed3)

                
            embed4 = interactions.Embed(
                title=title + " Objectif", color=interactions.Color.random())
            
            for column in self.fichier_objectif:
                methode = 'max'
                if column in ['early_drake', 'early_baron']:
                    methode = 'min'
                
                embed4 = creation_embed(fichier, column, methode_pseudo, embed4, methode)

        embed1.set_footer(text=f'Version {Version} by Tomlora')
        embed2.set_footer(text=f'Version {Version} by Tomlora')
        embed5.set_footer(text=f'Version {Version} by Tomlora')
        embed6.set_footer(text=f'Version {Version} by Tomlora')
        embed7.set_footer(text=f'Version {Version} by Tomlora')

        if mode != 'ARAM':
            embed3.set_footer(text=f'Version {Version} by Tomlora')
            embed4.set_footer(text=f'Version {Version} by Tomlora')
            pages=[embed1, embed2, embed3, embed4, embed5, embed6, embed7]

        else:
            pages=[embed1, embed2, embed5, embed6, embed7]
            
        paginator = Paginator.create_from_embeds(
            self.bot,
            *pages
        )
        paginator.show_select_menu = True
        
        await paginator.send(ctx)   
            
        
    @records_lol.subcommand('personnel',
                                sub_cmd_description='Records personnels sur un joueur',
                                options=parameters_personnel)
    async def records_list_personnel(self,
                              ctx: SlashContext,
                              saison: int = saison,
                              mode: str = 'ranked',
                              joueur= None,
                              compte_discord : interactions.User = None,
                              champion : str =None,
                              view='global'):

        await ctx.defer(ephemeral=False)
        
        methode_pseudo = 'discord'
        
        if view == 'global':
            fichier = lire_bdd_perso(f'''SELECT distinct matchs.*, tracker.discord from matchs
                                     INNER JOIN tracker on tracker.index = matchs.joueur
                                     where season = {saison} and mode = '{mode}' and time >= {self.time_mini[mode]} and tracker.banned = false''', index_col='id').transpose()
        elif view == 'serveur':
            fichier = lire_bdd_perso(f'''SELECT distinct matchs.*, tracker.discord from matchs
                                     INNER JOIN tracker on tracker.index = matchs.joueur
                                     where season = {saison}
                                     and mode = '{mode}'
                                     and server_id = {int(ctx.guild_id)}
                                     and time >= {self.time_mini[mode]}
                                     and tracker.banned = false''', index_col='id').transpose()
            
        fichier['early_drake'] = fichier['early_drake'].replace({0 : 999})    
        fichier['early_baron'] = fichier['early_baron'].replace({0 : 999}) 
        for column in self.liste_complete:
            
            fichier[f'{column}_rank_max'] = fichier[column].rank(method='min', ascending=False).astype(int)
            fichier[f'{column}_rank_min'] = fichier[column].rank(method='min', ascending=True).astype(int)
            

        if champion != None:
            
            champion = champion.capitalize()

            fichier = fichier[fichier['champion'] == champion]

            
        if joueur != None:
            
            joueur = joueur.lower()
                
            id_joueur = lire_bdd_perso('''SELECT tracker.index, tracker.discord from tracker where tracker.banned = false''',
                                            format='dict', index_col='index')
            try:
                fichier = fichier[fichier['discord'] == id_joueur[joueur]['discord']]
            except KeyError:
                return await ctx.send('Joueur introuvable ou tu es banni')    
              
        elif compte_discord != None:
                
            id_discord = str(compte_discord.id)
                               
            joueur = compte_discord.username
            try:    
                fichier = fichier[fichier['discord'] == id_discord]
            except KeyError:
                return await ctx.send('Joueur introuvable ou tu es banni')    
                
            
        elif joueur == None and compte_discord == None:
                
            fichier = fichier[fichier['discord'] == str(ctx.author.id)]
                
            joueur = ctx.author.name
                
        methode_pseudo = 'joueur'

        if champion == None:

                title = f'Records personnels {joueur} {mode} S{saison}'
        else:
                title = f'Records personnels {joueur} {mode} S{saison} ({champion})'

        
        fichier_farming = self.fichier_farming.copy()
        fichier_divers = self.fichier_divers.copy()

        # on rajoute quelques éléments sur d'autres pages...

        
        if mode == 'RANKED':
            fichier_divers.remove('snowball')

        if mode == 'ARAM':  # on vire les records qui ne doivent pas être comptés en aram

            fichier_farming.remove('cs_jungle')
            fichier_farming.remove('jgl_dix_min')


        def format_value(joueur, champion, url, short=False):
            text = ''
            for j, c, u in zip(joueur, champion, url):
                if short:
                    text += f'**__ {j} __ {c} ** \n'
                else:
                    text += f'**__{j}__** {emote_champ_discord.get(c.capitalize(), "inconnu")} [G]({u}) \n'
            return text
        
        def creation_embed(fichier, column, methode_pseudo, embed, methode='max'):
                joueur, champion, record, url, rank = trouver_records_multiples(fichier, column, methode, identifiant=methode_pseudo, rank=True)
            
                value_text = format_value(joueur, champion, url, short=False) if len(joueur) > 1 else f"** {joueur[0]} ** {emote_champ_discord.get(champion[0].capitalize(), 'inconnu')} [G]({url[0]})\n"
                
                embed.add_field(
                    name=f'{emote_v2.get(column, ":star:")}{column.upper()}',
                    value=f"Records : __{record}__ (#{rank}) \n {value_text}",
                    inline=True
                )
                
                return embed
        
        embed1 = interactions.Embed(
            title=title + " Kills", color=interactions.Color.random())    

        for column in self.fichier_kills:
            
            embed1 = creation_embed(fichier, column, methode_pseudo, embed1)
          

        embed2 = interactions.Embed(
            title=title + " DMG", color=interactions.Color.random())

        for column in self.fichier_dmg:
            
            embed2 = creation_embed(fichier, column, methode_pseudo, embed2)

        embed5 = interactions.Embed(
            title=title + " Farming", color=interactions.Color.random())

        for column in fichier_farming:
            
            embed5 = creation_embed(fichier, column, methode_pseudo, embed5)

        embed6 = interactions.Embed(
            title=title + " Tank/Heal", color=interactions.Color.random())

        for column in self.fichier_tank_heal:
            
            embed6 = creation_embed(fichier, column, methode_pseudo, embed6)

        embed7 = interactions.Embed(
            title=title + " Divers", color=interactions.Color.random())

        for column in fichier_divers:
            
            embed7 = creation_embed(fichier, column, methode_pseudo, embed7)


        if mode != 'ARAM':
            
            embed3 = interactions.Embed(
            title=title + " Vision", color=interactions.Color.random())

            for column in self.fichier_vision:
                
                embed3 = creation_embed(fichier, column, methode_pseudo, embed3)

                
            embed4 = interactions.Embed(
                title=title + " Objectif", color=interactions.Color.random())
            
            for column in self.fichier_objectif:
                methode = 'max'
                if column in ['early_drake', 'early_baron']:
                    methode = 'min'
                
                embed4 = creation_embed(fichier, column, methode_pseudo, embed4, methode)

        embed1.set_footer(text=f'Version {Version} by Tomlora')
        embed2.set_footer(text=f'Version {Version} by Tomlora')
        embed5.set_footer(text=f'Version {Version} by Tomlora')
        embed6.set_footer(text=f'Version {Version} by Tomlora')
        embed7.set_footer(text=f'Version {Version} by Tomlora')

        if mode != 'ARAM':
            embed3.set_footer(text=f'Version {Version} by Tomlora')
            embed4.set_footer(text=f'Version {Version} by Tomlora')
            pages=[embed1, embed2, embed3, embed4, embed5, embed6, embed7]

        else:
            pages=[embed1, embed2, embed5, embed6, embed7]
            
        paginator = Paginator.create_from_embeds(
            self.bot,
            *pages,
        )
        
        paginator.show_select_menu = True
        await paginator.send(ctx)

    @records_lol.subcommand("count",
                                    sub_cmd_description="Compte le nombre de records",
                                    options=[
                                        SlashCommandOption(
                                            name="saison",
                                            description="saison lol ?",
                                            type=interactions.OptionType.INTEGER,
                                            required=False,
                                            min_value=12,
                                            max_value=saison),
                                        SlashCommandOption(
                                            name='mode',
                                            description='quel mode de jeu ?',
                                            type=interactions.OptionType.STRING,
                                            required=False,
                                            choices=[
                                                SlashCommandChoice(name='ranked',
                                                       value='RANKED'),
                                                SlashCommandChoice(name='aram',
                                                       value='ARAM'),
                                                SlashCommandChoice(name='flex',
                                                       value='FLEX')
                                            ]
                                        ),
                                        SlashCommandOption(
                                            name='champion',
                                            description='focus sur un champion ?',
                                            type=interactions.OptionType.STRING,
                                            required=False
                                        ),
                                        SlashCommandOption(
                                            name='view',
                                            description='Global ou serveur ?',
                                            type=interactions.OptionType.STRING,
                                            required=False,
                                            choices=[
                                                SlashCommandChoice(name='global', value='global'),
                                                SlashCommandChoice(name='serveur', value='serveur')
                                            ]
                                        )
                                    ])
    async def records_count(self,
                            ctx: SlashContext,
                            saison: int = saison,
                            mode: str = 'RANKED',
                            champion: str = None,
                            view : str = 'global'):

        await ctx.defer(ephemeral=False)

        # on récupère la version du jeu
        session = ClientSession()
        version = await get_version(session)

        # on récupère les champions

        list_champ = await get_champ_list(session, version)

        await session.close()

        # data
        if view == 'global':
            fichier = lire_bdd_perso(f'''SELECT distinct matchs.*, tracker.discord from matchs where season = {saison} and mode = '{mode}' and time >= {self.time_mini[mode]} and tracker.banned = false''', index_col='id').transpose()
        elif view == 'serveur':
            fichier = lire_bdd_perso(f'''SELECT distinct matchs.*, tracker.discord from matchs
                                     INNER JOIN tracker on tracker.index = matchs.joueur
                                     where season = {saison}
                                     and mode = '{mode}'
                                     and server_id = '{int(ctx.guild_id)}'
                                     and time >= {self.time_mini[mode]}
                                     and tracker.banned = false''', index_col='id').transpose()

        # liste records

        liste_records = ['kills', 'assists', 'deaths', 'double', 'triple', 'quadra', 'penta', 'solokills', 'team_kills', 'team_deaths', 'kda', 'kp', 'serie_kills', 
        'dmg', 'dmg_ad', 'dmg_ap', 'dmg_true', 'damageratio', 'dmg_min', 'vision_score', 'vision_pink', 'vision_wards', 'vision_wards_killed', 'vision_min', 'vision_avantage',
        'cs', 'cs_jungle', 'cs_min', 'cs_dix_min', 'jgl_dix_min', 'cs_max_avantage',
        'dmg_tank', 'dmg_reduit', 'dmg_tank', 'tankratio', 'shield', 'heal_total', 'heal_allies',
        'baron', 'drake', 'herald', 'early_drake', 'early_baron', 'dmg_tower',
        'time', 'gold', 'gold_min', 'gold_share', 'ecart_gold_team', 'level_max_avantage', 'temps_dead', 'temps_vivant', 'allie_feeder', 'couronne', 'kills+assists', 'temps_avant_premiere_mort', 'dmg/gold']


        if mode == 'ARAM':
            liste_records.append('snowball')
            liste_records.remove('cs_jungle')
            liste_records.remove('jgl_dix_min')

        if champion == None:
            # Initialisation des listes
            liste_joueurs_general = []
            liste_joueurs_champion = []

            # Parcours des enregistrements dans liste_records
            for records in liste_records:
                methode = 'max'
                if records in ['early_drake', 'early_baron']:
                    methode = 'min'

                # Appel de la fonction trouver_records_multiples
                joueur, champion, record, url_game = trouver_records_multiples(
                    fichier, records, methode)
                
                # Ajout des joueurs dans la liste_joueurs_general
                liste_joueurs_general.extend(joueur)

                # Parcours des champions dans la liste list_champ['data']
                for champion in list_champ['data']:
                    try:
                        # Filtre le fichier par champion
                        fichier_champion = fichier[fichier['champion'] == champion]

                        # Appel de la fonction trouver_records_multiples
                        joueur, champion, record, url_game = trouver_records_multiples(
                            fichier_champion, records, methode)

                        # Ajout des joueurs dans la liste_joueurs_champion
                        liste_joueurs_champion.extend(joueur)

                    except:  # personne a le record
                        pass
                    

            counts_general = pd.Series(liste_joueurs_general).value_counts()
            counts_champion = pd.Series(liste_joueurs_champion).value_counts()
            
            options=[
                    interactions.StringSelectOption(
                        label="general", value="general", emoji=interactions.PartialEmoji(name='1️⃣')),
                    interactions.StringSelectOption(
                        label="par champion", value="par champion", emoji=interactions.PartialEmoji(name='2️⃣')),
                ],

            select = interactions.StringSelectMenu(
                *options,
                custom_id='selection',
                placeholder="Choix des records",
                min_values=1,
                max_values=1
            )

            message = await ctx.send("Quel type de record ?",
                           components=select)

            async def check(button_ctx : interactions.api.events.internal.Component):
                
                if int(button_ctx.ctx.author_id) == int(ctx.author.user.id):
                    return True
                await ctx.send("I wasn't asking you!", ephemeral=True)
                return False

            while True:
                try:
                    button_ctx: interactions.api.events.internal.Component  = await self.bot.wait_for_component(
                        components=select, check=check, timeout=120
                    )

                    if button_ctx.ctx.values[0] == 'general':
                        fig = px.histogram(counts_general,
                                           counts_general.index,
                                           counts_general.values,
                                           text_auto=True,
                                           color=counts_general.index,
                                           title=f'General ({mode})')

                    elif button_ctx.ctx.values[0] == 'par champion':
                        fig = px.histogram(counts_champion,
                                           counts_champion.index,
                                           counts_champion.values,
                                           text_auto=True,
                                           color=counts_champion.index,
                                           title=f'Par champion ({mode})')

                    fig.update_layout(showlegend=False)
                    embed, file = get_embed(fig, 'stats')
                    # On envoie

                    await message.edit(embeds=embed, files=file)

                except asyncio.TimeoutError:
                    # When it times out, edit the original message and remove the button(s)
                    return await message.edit(components=[])

        elif champion != None:  # si un champion en particulier
            fichier = fichier[fichier['champion'] == champion]

            # Initialisation de la liste
            liste_joueurs_champion = []

            # Parcours des enregistrements dans liste_records
            for records in liste_records:
                methode = 'max'
                if record in ['early_drake', 'early_baron']:
                    methode = 'min'

                # Appel de la fonction trouver_records_multiples
                joueur, champion, record, url_game = trouver_records_multiples(
                    fichier, records, methode)

                # Ajout des joueurs dans la liste_joueurs_champion
                liste_joueurs_champion.extend(joueur)

            # Comptage des occurrences des joueurs dans la liste
            counts_champion = pd.Series(liste_joueurs_champion).value_counts()

            fig = px.histogram(counts_champion,
                               counts_champion.index,
                               counts_champion.values,
                               text_auto=True,
                               color=counts_champion.index,
                               title=f'Record {champion} ({mode}) ')
            
            embed, file = get_embed(fig, 'stats')
            
            await ctx.send(embeds=embed, files=file)
            

    @records_lol.subcommand("palmares",
                                    sub_cmd_description="Classement pour un record donné",
                                    options=[
                                        SlashCommandOption(
                                            name='stat',
                                            description='Nom du record (voir records) ou écrire champion pour le nombre de champions joués',
                                            type=interactions.OptionType.STRING,
                                            required=True,
                                        ),
                                        SlashCommandOption(
                                            name="saison",
                                            description="saison lol ?",
                                            type=interactions.OptionType.INTEGER,
                                            required=False,
                                            min_value=12,
                                            max_value=saison),
                                        SlashCommandOption(
                                            name='mode',
                                            description='quel mode de jeu ?',
                                            type=interactions.OptionType.STRING,
                                            required=False,
                                            choices=[
                                                SlashCommandChoice(name='ranked',
                                                       value='RANKED'),
                                                SlashCommandChoice(name='aram',
                                                       value='ARAM'),
                                                SlashCommandChoice(name='flex',
                                                       value='FLEX')
                                            ]
                                        ),
                                        SlashCommandOption(
                                            name='champion',
                                            description='focus sur un champion ?',
                                            type=interactions.OptionType.STRING,
                                            required=False
                                        ),
                                        SlashCommandOption(
                                            name='joueur',
                                            description='focus sur un joueur ?',
                                            type=interactions.OptionType.STRING,
                                            required=False
                                        ),
                                        SlashCommandOption(
                                            name="compte_discord",
                                            description='focus sur un compte discord ?',
                                            type=interactions.OptionType.USER,
                                            required=False
                                        ),
                                        SlashCommandOption(
                                            name='view',
                                            description='Global ou serveur ?',
                                            type=interactions.OptionType.STRING,
                                            required=False,
                                            choices=[
                                                SlashCommandChoice(name='global', value='global'),
                                                SlashCommandChoice(name='serveur', value='serveur')
                                            ]
                                        ),
                                        SlashCommandOption(
                                            name='top',
                                            description='top à afficher',
                                            type=interactions.OptionType.INTEGER,
                                            required=False,
                                            min_value=10,
                                            max_value=25
                                        )
                                    ])
    async def palmares(self,
                        ctx: SlashContext,
                        stat : str,
                        saison: int = saison,
                        mode: str = 'RANKED',
                        champion: str = None,
                        joueur:str = None,
                        compte_discord: interactions.User = None,
                        view : str = 'global',
                        top : int = 10):


            # on récupère les champions


        stat = stat.lower()
        # data
        if view == 'global':
            fichier = lire_bdd_perso(f'''SELECT distinct matchs.*, tracker.discord from matchs
                                     INNER JOIN tracker on tracker.index = matchs.joueur
                                     where season = {saison}
                                     and mode = '{mode}'
                                     and time >= {self.time_mini[mode]}
                                     and tracker.banned = false''',
                                     index_col='id').transpose()

        elif view == 'serveur':
            fichier = lire_bdd_perso(f'''SELECT distinct matchs.*, tracker.discord from matchs, tracker
                                         INNER JOIN tracker on tracker.index = matchs.joueur
                                         where season = {saison}
                                         and mode = '{mode}'
                                         and server_id = '{int(ctx.guild_id)}'
                                         and time >= {self.time_mini[mode]}
                                         and tracker.banned = false''',
                                         index_col='id').transpose()
            
        if champion != None:
            fichier = fichier[fichier['champion'] == champion]
            
        if joueur != None:
            fichier = fichier[fichier['joueur'] == joueur.lower()]
            
        if compte_discord != None:
            fichier = fichier[fichier['discord'] == str(compte_discord.id)]
            
            
            
        if stat == 'champion':
            fichier = fichier[['discord', 'champion', 'match_id']]
            nb_row = fichier.shape[0] 
            # on prépare le df count game
            count_game = fichier.groupby(['discord']).count().reset_index()
            count_game = count_game[['discord', 'champion']].rename(columns={'champion': 'count'})
            
            # on prépare le fichier final
            
               
            fichier = fichier.groupby(['champion', 'discord']).count().sort_values(by='match_id', ascending=ascending).reset_index()
            nb_champion = len(fichier['champion'].unique())
            fichier = fichier.merge(count_game, on='discord', how='left')
            
            fichier['proportion'] = np.int8((fichier['match_id'] / fichier['count'])*100)
            
            
            fichier = fichier.head(top)   
            
            txt = ''
                
                
                
            for row, data in fichier.iterrows():
                champion = data['champion']
                txt += f'**{data["match_id"]}** - {mention(data["discord"], "membre")} {emote_champ_discord.get(champion.capitalize(), "inconnu")} - **{data["proportion"]}% des games**\n'
                
            embed = interactions.Embed(title=f'Palmarès {stat} ({mode}) S{saison}', description=txt)
            embed.set_footer(text=f"{nb_row} matchs analysés | {nb_champion} champions différents")
            
            await ctx.send(embeds=embed)
            
        else:
            
            try:
                fichier = fichier[['match_id', 'id_participant', 'discord', 'champion', stat, 'datetime']]
                
                nb_row = fichier.shape[0]
                
                                
                if stat in ['early_baron', 'early_drake']:
                    ascending=True
                    fichier = fichier[fichier[stat] != 0]
                else:
                    ascending=False
                    
                fichier.sort_values(by=stat, ascending=ascending, inplace=True)
                fichier = fichier.head(top)
                
                txt = ''
                
                
                
                for row, data in fichier.iterrows():
                    champion = data['champion']
                    txt += f'[{data[stat]}](https://www.leagueofgraphs.com/fr/match/euw/{str(data["match_id"])[5:]}#participant{int(data["id_participant"])+1}) - {mention(data["discord"], "membre")} {emote_champ_discord.get(champion.capitalize(), "inconnu")} - {data["datetime"].day}/{data["datetime"].month}\n'
                
                embed = interactions.Embed(title=f'Palmarès {stat} ({mode}) S{saison}', description=txt)
                embed.set_footer(text=f"{nb_row} matchs analysés")
                
                
                await ctx.send(embeds=embed)
                
            except KeyError:
                await ctx.send("Ce record n'existe pas. Merci de regarder les records pour voir les noms disponibles.")
                
                
    # @palmares.autocomplete('stat')
    # async def palmares_autocomplete(self, ctx: AutocompleteContext):
    #     string_option_input = ctx.input_text
        
    #     await ctx.send(
    #         choices=[
    #             {'name' : f'kda', f'value' : f'kda'},
    #             {'name' : f'kp', f'value' : f'kp'},
    #             {'name' : f'cs', f'value' : f'cs'},
    #             {'name' : f'cs_min', f'value' : f'cs_min'},
    #             {'name' : f'kills', f'value' : f'kills'},
    #             {'name' : f'deaths', f'value' : f'deaths'},
    #             {'name' : f'assists', f'value' : f'assists'},
    #             {'name' : f'double', f'value' : f'double'},
    #             {'name' : f'triple', f'value' : f'triple'},
    #             {'name' : f'quadra', f'value' : f'quadra'},
    #             {'name' : f'penta', f'value' : f'penta'},
    #             {'name' : f'team_kills', f'value' : f'team_kills'},
    #             {'name' : f'team_deaths', f'value' : f'team_deaths'},
    #             {'name' : f'time', f'value' : f'time'},
    #             {'name' : f'dmg', f'value' : f'dmg'},
    #             {'name' : f'dmg_ad', f'value' : f'dmg_ad'},
    #             {'name' : f'dmg_ap', f'value' : f'dmg_ap'},
    #             {'name' : f'dmg_true', f'value' : f'dmg_true'},
    #             {'name' : f'gold', f'value' : f'gold'},
    #             {'name' : f'gold_min', f'value' : f'gold_min'},
    #             {'name' : f'dmg_min', f'value' : f'dmg_min'},
    #             {'name' : f'solokills', f'value' : f'solokills'},
    #             {'name' : f'dmg_reduit', f'value' : f'dmg_reduit'},
    #             {'name' : f'heal_total', f'value' : f'heal_total'},
    #             {'name' : f'heal_allies', f'value' : f'heal_allies'},
    #             {'name' : f'serie_kills', f'value' : f'serie_kills'},
    #             {'name' : f'cs_dix_min', f'value' : f'cs_dix_min'},
    #             {'name' : f'cs_max_avantage', f'value' : f'cs_max_avantage'},
    #             {'name' : f'temps_dead', f'value' : f'temps_dead'},
    #             {'name' : f'damageratio', f'value' : f'damageratio'},
    #             {'name' : f'tankratio', f'value' : f'tankratio'},
    #             {'name' : f'dmg_tank', f'value' : f'dmg_tank'},
    #             {'name' : f'shield', f'value' : f'shield'},
    #             {'name' : f'allie_feeder', f'value' : f'allie_feeder'},
    #             {'name' : f'temps_vivant', f'value' : f'temps_vivant'},
    #             {'name' : f'dmg_tower', f'value' : f'dmg_tower'},
    #             {'name' : f'gold_share', f'value' : f'gold_share'},
    #             {'name' : f'ecart_gold_team', f'value' : f'ecart_gold_team'},
    #             {'name' : f'kills+assists', f'value' : f'kills+assists'},
    #             {'name' : f'vision_score', f'value' : f'vision_score'},
    #             {'name' : f'vision_wards', f'value' : f'vision_wards'},
    #             {'name' : f'vision_wards_killed', f'value' : f'vision_wards_killed'},
    #             {'name' : f'vision_pink', f'value' : f'vision_pink'},
    #             {'name' : f'vision_min', f'value' : f'vision_min'},
    #             {'name' : f'level_max_avantage', f'value' : f'level_max_avantage'},
    #             {'name' : f'vision_avantage', f'value' : f'vision_avantage'},
    #             {'name' : f'early_drake', f'value' : f'early_drake'},
    #             {'name' : f'early_baron', f'value' : f'early_baron'},
    #             {'name' : f'jgl_dix_min', f'value' : f'jgl_dix_min'},
    #             {'name' : f'baron', f'value' : f'baron'},
    #             {'name' : f'drake', f'value' : f'drake'},
    #             {'name' : f'herald', f'value' : f'herald'},
    #             {'name' : f'cs_jungle', f'value' : f'cs_jungle'},
    #             {'name' : f'snowball', f'value' : f'snowball'},
                #   {'name' : 'temps_avant_premiere_mort', 'value' : 'temps_avant_premiere_mort'},
    #             {'name' : f'champion', 'value' : f'champion'},

    #         ]
    #     )
              
def setup(bot):
    Recordslol(bot)
