import numpy as np
import pandas as pd
from fonctions.gestion_bdd import lire_bdd, lire_bdd_perso
import interactions
from interactions import SlashCommandChoice, SlashCommandOption, Extension, SlashContext, slash_command
from interactions.ext.paginators import Paginator
from fonctions.params import Version, saison
from fonctions.match import trouver_records, get_champ_list, get_version, trouver_records_multiples
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
    "ecart_gold_team" : ":euro:"
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

    @slash_command(name="records_list_s12",
                                    description="Voir les records détenues par les joueurs (réservé s12)",
                                    options=[
                                        SlashCommandOption(
                                            name="mode",
                                            description="Quel mode de jeu ?",
                                            type=interactions.OptionType.STRING,
                                            required=True, choices=[
                                                SlashCommandChoice(name='ranked',
                                                       value='ranked'),
                                                SlashCommandChoice(name='aram', value='aram')])
                                    ])
    async def records_list_s12(self,
                           ctx: SlashContext,
                           mode: str = 'ranked'):

        await ctx.defer(ephemeral=False)

        saison = 12

        fichier = lire_bdd_perso(f'''SELECT index, "Score", "Champion", "Joueur", url from records where saison= {saison} AND mode='{mode}' ''').transpose()

        fichier1 = fichier.iloc[:22]
        fichier2 = fichier.iloc[22:]

        response = ""

        embed1 = interactions.Embed(
            title=f"Records {mode} S12 (Page 1/3) :bar_chart:", color=interactions.Color.random())

        for key, value in fichier1.iterrows():
            valeur = ""
            if key == "DEGATS_INFLIGES":
                valeur = "{:,}".format(value['Score']).replace(
                    ',', ' ').replace('.', ',')
            elif key == "DUREE_GAME":
                valeur = str(int(round(value['Score'], 0))).replace(".", "m")
            elif key in ["KP", "% DMG", "AVANTAGE_VISION", "AVANTAGE_VISION_SUPPORT"]:
                valeur = str(value['Score']) + "%"
            else:
                valeur = int(value['Score'])

            if value['url'] == "na":
                embed1.add_field(name=str(emote[key]) + "" + key,
                                 value=f"Records : __ {valeur} __ \n ** {value['Joueur']} ** ({value['Champion']})", inline=True)

            else:
                embed1.add_field(name=str(emote[key]) + "" + key,
                                 value=f"Records : __ [{valeur}]({value['url']}) __ \n ** {value['Joueur']} ** ({value['Champion']})", inline=True)

        embed1.set_footer(text=f'Version {Version} by Tomlora')

        embed2 = interactions.Embed(
            title=f"Records {mode} S12 (Page 2/3) :bar_chart:", color=interactions.Color.random())

        for key, value in fichier2.iterrows():
            valeur2 = ""
            if key in ["GOLDS_GAGNES", "DOMMAGES_TANK", 'DOMMAGES_REDUITS', "DOMMAGES_TOWER", "TOTAL_HEALS", "HEALS_SUR_ALLIES"]:
                valeur2 = "{:,}".format(value['Score']).replace(
                    ',', ' ').replace('.', ',')
            elif key == "DOMMAGES_TANK%":
                valeur2 = str(value['Score']) + "%"
            elif key == "EARLY_DRAKE" or key == "EARLY_BARON":
                valeur2 = str(value['Score']).replace(".", "m")
            else:
                valeur2 = int(value['Score'])

            if value['url'] == 'na':
                embed2.add_field(name=str(emote[key]) + "" + key,
                                 value=f"Records : __ {valeur2} __ \n ** {value['Joueur']} ** ({value['Champion']})", inline=True)

            else:
                embed2.add_field(name=str(emote[key]) + "" + key,
                                 value=f"Records : __ [{valeur2}]({value['url']}) __ \n ** {value['Joueur']} ** ({value['Champion']})", inline=True)

        embed2.set_footer(text=f'Version {Version} by Tomlora')

        embed3 = interactions.Embed(
            title=f"Records Cumul & Moyenne S12 (Page 3/3) :bar_chart: ")

        fichier3 = lire_bdd('records_cumul', 'dict')

        df = pd.DataFrame.from_dict(fichier3)
        df.fillna(0, inplace=True)
        df.index.name = "Joueurs"
        df.reset_index(inplace=True)

        if mode == 'ranked':
            col_games = 'NBGAMES'
            col_kills = 'KILLS'
            col_deaths = 'DEATHS'
            col_assists = 'ASSISTS'
            list_avg = ['WARDS_MOYENNE', 'KILLS_MOYENNE',
                        'DEATHS_MOYENNE', 'ASSISTS_MOYENNE']
            col_penta = 'PENTA'
            col_quadra = 'QUADRA'
            col_solokills = 'SOLOKILLS'

        elif mode == 'aram':
            col_games = 'NBGAMES_ARAM'
            col_kills = 'KILLS_ARAM'
            col_deaths = 'DEATHS_ARAM'
            col_assists = 'ASSISTS_ARAM'
            list_avg = ['KILLS_MOYENNE', 'DEATHS_MOYENNE', 'ASSISTS_MOYENNE']
            col_penta = 'PENTA_ARAM'
            col_quadra = 'QUADRA_ARAM'
            col_solokills = 'SOLOKILLS_ARAM'

        # Moyenne
        df['KILLS_MOYENNE'] = 0
        df['DEATHS_MOYENNE'] = 0
        df['ASSISTS_MOYENNE'] = 0
        df['WARDS_MOYENNE'] = 0

        df['KILLS_MOYENNE'] = np.where(
            df[col_games] > 0, df[col_kills] / df[col_games], 0)
        df['DEATHS_MOYENNE'] = np.where(
            df[col_games] > 0, df[col_deaths] / df[col_games], 0)
        df['ASSISTS_MOYENNE'] = np.where(
            df[col_games] > 0, df[col_assists] / df[col_games], 0)

        if mode == 'ARAM':
            df['WARDS_MOYENNE'] = np.where(
                df[col_games] > 0, df['WARDS_SCORE'] / df[col_games], 0)

        list_keys = []

        if mode == 'ranked':
            for key in fichier3.keys():
                if not "ARAM" in key.split('_'):
                    list_keys.append(key)
        elif mode == 'aram':
            for key in fichier3.keys():
                if "ARAM" in key.split('_'):
                    list_keys.append(key)

        def findrecord(df, key, asc):
            df = df[df[col_games] >= 10]
            if asc is True:
                df = df[df[key] > 1]

            df.sort_values(key, ascending=asc, inplace=True)

            value = df[key].iloc[0]
            joueur = df['Joueurs'].iloc[0]
            nbgames = int(df[col_games].iloc[0])

            return joueur, value, nbgames

        if df[col_games].max() >= 10:
            for key in list_keys:  # durée game bug donc on le retire

                joueur, value, nbgames = findrecord(df, key, False)

                if key == col_games or key == col_penta or key == col_quadra or key == col_solokills:
                    value = int(value)

                elif key in [col_kills, col_deaths, col_assists, 'WARDS_SCORE', 'WARDS_POSEES', 'WARDS_DETRUITES',
                             'WARDS_PINKS', 'CS']:
                    break

                embed3.add_field(name=str(emote[key]) + "" + str(key),
                                 value="Records : __ " + str(value) + " __ \n ** " + str(
                                     joueur) + "**", inline=True)

            for key in list_avg:
                joueur, value, nbgames = findrecord(df, key, False)
                value = round(float(value), 2)

                embed3.add_field(name=str(emote[key]) + "" + str(key) + " (ELEVEE)",
                                 value="Records : __ " + str(value) + " __ en " + str(nbgames) + " games \n ** " + str(
                                     joueur) + "**", inline=True)

            for key in ['KILLS_MOYENNE', 'DEATHS_MOYENNE', 'ASSISTS_MOYENNE']:
                joueur, value, nbgames = findrecord(df, key, True)
                value = round(float(value), 2)

                embed3.add_field(name=str(emote[key]) + "" + str(key) + " (BASSE)",
                                 value="Records : __ " + str(value) + " __ en " + str(nbgames) + " games \n ** " + str(
                                     joueur) + "**", inline=True)

        else:
            embed3.add_field(
                name="Indisponible", value="Aucun joueur n'a atteint le minimum requis : 10 games")

        embed3.set_footer(text=f'Version {Version} by Tomlora')

        paginator = Paginator.create_from_embeds(
            client=self.bot,
            embeds=[embed1, embed2, embed3])


    @slash_command(name="records_personnel_s12",
                                    description="Record personnel (réservé s12)",
                                    options=[
                                        SlashCommandOption(
                                            name="joueur",
                                            description="Pseudo LoL",
                                            type=interactions.OptionType.STRING,
                                            required=True)])
    async def records_personnel_s12(self,
                                ctx: SlashContext,
                                joueur: str):

        joueur = joueur.lower()

        df = lire_bdd('records_personnel')[joueur]

        await ctx.defer(ephemeral=False)

        df_part1 = df.iloc[:18]
        df_part2 = df.iloc[18:]

        embed1 = interactions.Embed(
            title=f"Records personnels {joueur} (1/3)", color=interactions.Color.random())
        embed2 = interactions.Embed(
            title=f"Records personnels {joueur} (2/3)", color=interactions.Color.random())
        embed3 = interactions.Embed(
            title=f"Records personnels ARAM {joueur} (3/3)", color=interactions.Color.random())

        for key, valeur in df_part1.iteritems():
            # format
            if key in ['DAMAGE_RATIO', 'DAMAGE_RATIO_ENCAISSE', 'KP', 'AVANTAGE_VISION']:
                valeur = str(valeur) + "%"
            elif key == "DUREE_GAME":
                valeur = str(valeur).replace(".", "m")
            else:
                if not 'url' in key.split('_'):
                    valeur = int(valeur)

            # si url alors c'est un lien, pas un record
            if not 'url' in key.split('_'):

                if df.loc[key + '_url'] == 'na':

                    embed1.add_field(name=str(emote[key]) + " " + key,
                                     value=f"Records : __ {valeur} __ ", inline=True)

                else:

                    embed1.add_field(name=str(emote[key]) + " " + key,
                                     value=f"Records : __ [{valeur}]({df.loc[key + '_url']}) __ ", inline=True)

        for key, valeur in df_part2.iteritems():

            if 'ARAM' in key.split('_'):
                embed_selected = embed3  # records perso aram
            else:
                embed_selected = embed2  # autre
            # format
            if key in ['DAMAGE_RATIO', 'DAMAGE_RATIO_ENCAISSE', 'KP', 'AVANTAGE_VISION']:
                valeur = str(valeur) + "%"
            elif key == "DUREE_GAME":
                valeur = str(valeur).replace(".", "m")
            else:
                if not 'url' in key.split('_'):
                    valeur = int(valeur)

            # si url alors c'est un lien, pas un record
            if not 'url' in key.split('_'):

                if df.loc[key + '_url'] == 'na':  # on cherche l'url associé

                    embed_selected.add_field(name=str(emote[key]) + " " + key,
                                             value=f"Records : __ {valeur} __ ", inline=True)

                else:

                    embed_selected.add_field(name=str(emote[key]) + " " + key,
                                             value=f"Records : __ [{valeur}]({df.loc[key + '_url']}) __ ", inline=True)

        embed1.set_footer(text=f'Version {Version} by Tomlora')
        embed2.set_footer(text=f'Version {Version} by Tomlora')
        embed3.set_footer(text=f'Version {Version} by Tomlora')

        paginator = Paginator.create_from_embeds(
            self.bot,
            embeds=[embed1, embed2, embed3])

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

    @slash_command(name="records_list",
                                    description="Voir les records détenues par les joueurs")
    async def records_list_v2(self, ctx:SlashContext):
        pass
    
    @records_list_v2.subcommand('general',
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
                                     where season = {saison} and mode = '{mode}' and time >= {self.time_mini[mode]}''', index_col='id').transpose()
        elif view == 'serveur':
            fichier = lire_bdd_perso(f'''SELECT distinct matchs.*, tracker.discord from matchs
                                     INNER JOIN tracker on tracker.index = matchs.joueur
                                     where season = {saison}
                                     and mode = '{mode}'
                                     and server_id = {int(ctx.guild_id)}
                                     and time >= {self.time_mini[mode]}''', index_col='id').transpose()
            
        if champion != None:
            
            champion = champion.capitalize()

            fichier = fichier[fichier['champion'] == champion] 
            
        if champion == None:
                title = f'Records {mode} S{saison}'
        else:
                title = f'Records {mode} S{saison} ({champion})'

        fichier_kills = ['kills', 'assists', 'deaths', 'double', 'triple', 'quadra', 'penta', 'solokills', 'team_kills', 'team_deaths', 'kda', 'kp', 'kills+assists', 'serie_kills'] 
        fichier_dmg = ['dmg', 'dmg_ad', 'dmg_ap', 'dmg_true', 'damageratio', 'dmg_min']
        fichier_vision = ['vision_score', 'vision_pink', 'vision_wards', 'vision_wards_killed', 'vision_min', 'vision_avantage']
        fichier_farming = ['cs', 'cs_jungle', 'cs_min', 'cs_dix_min', 'jgl_dix_min', 'cs_max_avantage']
        fichier_tank_heal = ['dmg_tank', 'dmg_reduit', 'dmg_tank', 'tankratio', 'shield', 'heal_total', 'heal_allies']
        fichier_objectif = ['baron', 'drake', 'herald', 'early_drake', 'early_baron', 'dmg_tower']
        fichier_divers = ['time', 'gold', 'gold_min', 'gold_share', 'ecart_gold_team', 'level_max_avantage', 'temps_dead', 'temps_vivant', 'allie_feeder', 'couronne', 'snowball']

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
            
                value_text = format_value(joueur, champion, url, short=False) if len(joueur) > 1 else f"** {joueur[0]} ** [{champion[0]}]({url[0]})\n"
                
                embed.add_field(
                    name=f'{emote_v2.get(column, ":star:")}{column.upper()}',
                    value=f"Records : __ {record} __ \n {value_text}",
                    inline=True
                )
                
                return embed
        
        embed1 = interactions.Embed(
            title=title + " Kills", color=interactions.Color.random())    

        for column in fichier_kills:
            
            embed1 = creation_embed(fichier, column, methode_pseudo, embed1)
          

        embed2 = interactions.Embed(
            title=title + " DMG", color=interactions.Color.random())

        for column in fichier_dmg:
            
            embed2 = creation_embed(fichier, column, methode_pseudo, embed2)

        embed5 = interactions.Embed(
            title=title + " Farming", color=interactions.Color.random())

        for column in fichier_farming:
            
            embed5 = creation_embed(fichier, column, methode_pseudo, embed5)

        embed6 = interactions.Embed(
            title=title + " Tank/Heal", color=interactions.Color.random())

        for column in fichier_tank_heal:
            
            embed6 = creation_embed(fichier, column, methode_pseudo, embed6)

        embed7 = interactions.Embed(
            title=title + " Divers", color=interactions.Color.random())

        for column in fichier_divers:
            
            embed7 = creation_embed(fichier, column, methode_pseudo, embed7)


        if mode != 'ARAM':
            
            embed3 = interactions.Embed(
            title=title + " Vision", color=interactions.Color.random())

            for column in fichier_vision:
                
                embed3 = creation_embed(fichier, column, methode_pseudo, embed3)

                
            embed4 = interactions.Embed(
                title=title + " Objectif", color=interactions.Color.random())
            
            for column in fichier_objectif:
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
            
        
    @records_list_v2.subcommand('personnel',
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
                                     where season = {saison} and mode = '{mode}' and time >= {self.time_mini[mode]}''', index_col='id').transpose()
        elif view == 'serveur':
            fichier = lire_bdd_perso(f'''SELECT distinct matchs.*, tracker.discord from matchs
                                     INNER JOIN tracker on tracker.index = matchs.joueur
                                     where season = {saison}
                                     and mode = '{mode}'
                                     and server_id = {int(ctx.guild_id)}
                                     and time >= {self.time_mini[mode]}''', index_col='id').transpose()
            

        if champion != None:
            
            champion = champion.capitalize()

            fichier = fichier[fichier['champion'] == champion]

            
        if joueur != None:
            
            joueur = joueur.lower()
                
            id_joueur = lire_bdd_perso('''SELECT tracker.index, tracker.discord from tracker''',
                                            format='dict', index_col='index')

            fichier = fichier[fichier['discord'] == id_joueur[joueur]['discord']]
                
              
        elif compte_discord != None:
                
            id_discord = str(compte_discord.id)
                               
            joueur = compte_discord.username
                
            fichier = fichier[fichier['discord'] == id_discord]
                
            
        elif joueur == None and compte_discord == None:
                
            fichier = fichier[fichier['discord'] == str(ctx.author.id)]
                
            joueur = ctx.author.name
                
        methode_pseudo = 'joueur'

        if champion == None:

                title = f'Records personnels {joueur} {mode} S{saison}'
        else:
                title = f'Records personnels {joueur} {mode} S{saison} ({champion})'

        
        fichier_kills = ['kills', 'assists', 'deaths', 'double', 'triple', 'quadra', 'penta', 'solokills', 'team_kills', 'team_deaths', 'kda', 'kp', 'kills+assists', 'serie_kills'] 
        fichier_dmg = ['dmg', 'dmg_ad', 'dmg_ap', 'dmg_true', 'damageratio', 'dmg_min']
        fichier_vision = ['vision_score', 'vision_pink', 'vision_wards', 'vision_wards_killed', 'vision_min', 'vision_avantage']
        fichier_farming = ['cs', 'cs_jungle', 'cs_min', 'cs_dix_min', 'jgl_dix_min', 'cs_max_avantage']
        fichier_tank_heal = ['dmg_tank', 'dmg_reduit', 'dmg_tank', 'tankratio', 'shield', 'heal_total', 'heal_allies']
        fichier_objectif = ['baron', 'drake', 'herald', 'early_drake', 'early_baron', 'dmg_tower']
        fichier_divers = ['time', 'gold', 'gold_min', 'gold_share', 'ecart_gold_team', 'level_max_avantage', 'temps_dead', 'temps_vivant', 'allie_feeder', 'couronne', 'snowball']

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
            
                value_text = format_value(joueur, champion, url, short=False) if len(joueur) > 1 else f"** {joueur[0]} ** [{champion[0]}]({url[0]})\n"
                
                embed.add_field(
                    name=f'{emote_v2.get(column, ":star:")}{column.upper()}',
                    value=f"Records : __ {record} __ \n {value_text}",
                    inline=True
                )
                
                return embed
        
        embed1 = interactions.Embed(
            title=title + " Kills", color=interactions.Color.random())    

        for column in fichier_kills:
            
            embed1 = creation_embed(fichier, column, methode_pseudo, embed1)
          

        embed2 = interactions.Embed(
            title=title + " DMG", color=interactions.Color.random())

        for column in fichier_dmg:
            
            embed2 = creation_embed(fichier, column, methode_pseudo, embed2)

        embed5 = interactions.Embed(
            title=title + " Farming", color=interactions.Color.random())

        for column in fichier_farming:
            
            embed5 = creation_embed(fichier, column, methode_pseudo, embed5)

        embed6 = interactions.Embed(
            title=title + " Tank/Heal", color=interactions.Color.random())

        for column in fichier_tank_heal:
            
            embed6 = creation_embed(fichier, column, methode_pseudo, embed6)

        embed7 = interactions.Embed(
            title=title + " Divers", color=interactions.Color.random())

        for column in fichier_divers:
            
            embed7 = creation_embed(fichier, column, methode_pseudo, embed7)


        if mode != 'ARAM':
            
            embed3 = interactions.Embed(
            title=title + " Vision", color=interactions.Color.random())

            for column in fichier_vision:
                
                embed3 = creation_embed(fichier, column, methode_pseudo, embed3)

                
            embed4 = interactions.Embed(
                title=title + " Objectif", color=interactions.Color.random())
            
            for column in fichier_objectif:
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

    @slash_command(name="records_count",
                                    description="Compte le nombre de records",
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
            fichier = lire_bdd_perso(f'''SELECT distinct matchs.*, tracker.discord from matchs, tracker where season = {saison} and mode = '{mode}' and time >= {self.time_mini[mode]}''', index_col='id').transpose()
        elif view == 'serveur':
            fichier = lire_bdd_perso(f'''SELECT distinct matchs.*, tracker.discord from matchs, tracker
                                     INNER JOIN tracker on tracker.index = matchs.joueur
                                     where season = {saison}
                                     and mode = '{mode}'
                                     and server_id = '{int(ctx.guild_id)}'
                                     and time >= {self.time_mini[mode]}''', index_col='id').transpose()

        # liste records

        liste_records = ['kills', 'assists', 'deaths', 'double', 'triple', 'quadra', 'penta', 'solokills', 'team_kills', 'team_deaths', 'kda', 'kp', 'serie_kills', 
        'dmg', 'dmg_ad', 'dmg_ap', 'dmg_true', 'damageratio', 'dmg_min', 'vision_score', 'vision_pink', 'vision_wards', 'vision_wards_killed', 'vision_min', 'vision_avantage',
        'cs', 'cs_jungle', 'cs_min', 'cs_dix_min', 'jgl_dix_min', 'cs_max_avantage',
        'dmg_tank', 'dmg_reduit', 'dmg_tank', 'tankratio', 'shield', 'heal_total', 'heal_allies',
        'baron', 'drake', 'herald', 'early_drake', 'early_baron', 'dmg_tower',
        'time', 'gold', 'gold_min', 'gold_share', 'ecart_gold_team', 'level_max_avantage', 'temps_dead', 'temps_vivant', 'allie_feeder', 'couronne', 'kills+assists']


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

            select = interactions.SelectMenu(
                options=[
                    interactions.SelectSlashCommandOption(
                        label="general", value="general", emoji=interactions.Emoji(name='1️⃣')),
                    interactions.SelectSlashCommandOption(
                        label="par champion", value="par champion", emoji=interactions.Emoji(name='2️⃣')),
                ],
                custom_id='selection',
                placeholder="Choix des records",
                min_values=1,
                max_values=1
            )

            await ctx.send("Quel type de record ?",
                           components=select)

            async def check(button_ctx):
                if int(button_ctx.author.user.id) == int(ctx.author.user.id):
                    return True
                await ctx.send("I wasn't asking you!", ephemeral=True)
                return False

            while True:
                try:
                    button_ctx: interactions.ComponentContext = await self.bot.wait_for_component(
                        components=select, check=check, timeout=30
                    )

                    if button_ctx.data.values[0] == 'general':
                        fig = px.histogram(counts_general,
                                           counts_general.index,
                                           counts_general.values,
                                           text_auto=True,
                                           color=counts_general.index,
                                           title=f'General ({mode})')

                    elif button_ctx.data.values[0] == 'par champion':
                        fig = px.histogram(counts_champion,
                                           counts_champion.index,
                                           counts_champion.values,
                                           text_auto=True,
                                           color=counts_champion.index,
                                           title=f'Par champion ({mode})')

                    fig.update_layout(showlegend=False)
                    embed, file = get_embed(fig, 'stats')
                    # On envoie

                    await ctx.edit(embeds=embed, files=file)

                except asyncio.TimeoutError:
                    # When it times out, edit the original message and remove the button(s)
                    return await ctx.edit(components=[])

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
            

    @slash_command(name="records_palmares",
                                    description="Classement pour un record donné",
                                    options=[
                                        SlashCommandOption(
                                            name='stat',
                                            description='Nom du record (voir records) ou écrire champion pour le nombre de champions joués',
                                            type=interactions.OptionType.STRING,
                                            required=True
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
                                     and time >= {self.time_mini[mode]}''',
                                     index_col='id').transpose()

        elif view == 'serveur':
            fichier = lire_bdd_perso(f'''SELECT distinct matchs.*, tracker.discord from matchs, tracker
                                         INNER JOIN tracker on tracker.index = matchs.joueur
                                         where season = {saison}
                                         and mode = '{mode}'
                                         and server_id = '{int(ctx.guild_id)}'
                                         and time >= {self.time_mini[mode]}''',
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
            fichier = fichier.groupby(['champion', 'discord']).count().sort_values(by='match_id', ascending=False).reset_index()
            nb_champion = len(fichier['champion'].unique())
            fichier = fichier.merge(count_game, on='discord', how='left')
            
            fichier['proportion'] = np.int8((fichier['match_id'] / fichier['count'])*100)
            
            
            fichier = fichier.head(top)   
            
            txt = ''
                
                
                
            for row, data in fichier.iterrows():
                    txt += f'**{data["match_id"]}** - {mention(data["discord"], "membre")} ({data["champion"]}) - **{data["proportion"]}% des games**\n'
                
            embed = interactions.Embed(title=f'Palmarès {stat} ({mode}) S{saison}', description=txt)
            embed.set_footer(text=f"{nb_row} matchs analysés | {nb_champion} champions différents")
            
            await ctx.send(embeds=embed)
            
        else:
            
            try:
                fichier = fichier[['match_id', 'id_participant', 'discord', 'champion', stat, 'datetime']]
                
                nb_row = fichier.shape[0]
                
                fichier.sort_values(by=stat, ascending=False, inplace=True)
                fichier = fichier.head(top)
                
                txt = ''
                
                
                
                for row, data in fichier.iterrows():
                    txt += f'**{data[stat]}** - {mention(data["discord"], "membre")} [{data["champion"]}](https://www.leagueofgraphs.com/fr/match/euw/{str(data["match_id"])[5:]}#participant{int(data["id_participant"])+1}) - {data["datetime"].day}/{data["datetime"].month}\n'
                
                embed = interactions.Embed(title=f'Palmarès {stat} ({mode}) S{saison}', description=txt)
                embed.set_footer(text=f"{nb_row} matchs analysés")
                
                
                await ctx.send(embeds=embed)
                
            except KeyError:
                await ctx.send("Ce record n'existe pas. Merci de regarder les records pour voir les noms disponibles.")
            


def setup(bot):
    Recordslol(bot)
