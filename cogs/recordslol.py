import numpy as np
import pandas as pd
from fonctions.gestion_bdd import lire_bdd, lire_bdd_perso
import interactions
from interactions import Choice, Option, Extension, CommandContext
from interactions.ext.paginator import Page, Paginator
from fonctions.params import Version
from fonctions.match import trouver_records, get_champ_list, get_version
from aiohttp import ClientSession
import plotly.express as px
import asyncio
from fonctions.channels_discord import get_embed


def option_stats_records(name, params, description='type de recherche'):
    option = Option(
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
    'spell1': ":magic_wand:",
    'spell2': ":magic_wand:",
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
}

choice_pantheon = [Choice(name="KDA", value="KDA"),
                   Choice(name='KDA moyenne', value='KDA moyenne'),
                   Choice(name='vision', value='VISION'),
                   Choice(name='vision moyenne', value='VISION moyenne'),
                   Choice(name='CS', value='CS'),
                   Choice(name='Solokills', value='SOLOKILLS'),
                   Choice(name='games', value='GAMES')]


class Recordslol(Extension):
    def __init__(self, bot):
        self.bot: interactions.Client = bot

    @interactions.extension_command(name="records_list_s12",
                                    description="Voir les records détenues par les joueurs (réservé s12)",
                                    options=[
                                        Option(
                                            name="mode",
                                            description="Quel mode de jeu ?",
                                            type=interactions.OptionType.STRING,
                                            required=True, choices=[
                                                Choice(name='ranked',
                                                       value='ranked'),
                                                Choice(name='aram', value='aram')])
                                    ])
    async def records_list(self,
                           ctx: CommandContext,
                           mode: str = 'ranked'):

        await ctx.defer(ephemeral=False)

        current = 0
        saison = 12

        fichier = lire_bdd_perso('SELECT index, "Score", "Champion", "Joueur", url from records where saison= %(saison)s AND mode=%(mode)s', params={'saison': saison,
                                                                                                                                                     'mode': mode}).transpose()

        fichier1 = fichier.iloc[:22]
        fichier2 = fichier.iloc[22:]

        response = ""

        embed1 = interactions.Embed(
            title=f"Records {mode} S{saison} (Page 1/3) :bar_chart:", color=interactions.Color.blurple())

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
            title=f"Records {mode} S{saison} (Page 2/3) :bar_chart:", color=interactions.Color.blurple())

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
            title=f"Records Cumul & Moyenne S{saison} (Page 3/3) :bar_chart: ")

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

        await Paginator(
            client=self.bot,
            ctx=ctx,
            pages=[
                Page(embed1.title, embed1),
                Page(embed2.title, embed2),
                Page(embed3.title, embed3)
            ]
        ).run()

    @interactions.extension_command(name="records_personnel_s12",
                                    description="Record personnel (réservé s12)",
                                    options=[
                                        Option(
                                            name="joueur",
                                            description="Pseudo LoL",
                                            type=interactions.OptionType.STRING,
                                            required=True)])
    async def records_personnel(self,
                                ctx: CommandContext,
                                joueur: str):

        joueur = joueur.lower()

        df = lire_bdd('records_personnel')[joueur]

        await ctx.defer(ephemeral=False)

        df_part1 = df.iloc[:18]
        df_part2 = df.iloc[18:]

        embed1 = interactions.Embed(
            title=f"Records personnels {joueur} (1/3)", color=interactions.Color.blurple())
        embed2 = interactions.Embed(
            title=f"Records personnels {joueur} (2/3)", color=interactions.Color.blurple())
        embed3 = interactions.Embed(
            title=f"Records personnels ARAM {joueur} (3/3)", color=interactions.Color.blurple())

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

        await Paginator(
            client=self.bot,
            ctx=ctx,
            pages=[
                Page(embed1.title, embed1),
                Page(embed2.title, embed2),
                Page(embed3.title, embed3)
            ]
        ).run()

    parameters_communs = [
        Option(
            name="mode",
            description="Quel mode de jeu ?",
            type=interactions.OptionType.STRING,
            required=True, choices=[
                Choice(name='ranked',
                       value='RANKED'),
                Choice(name='aram', value='ARAM')]),
        Option(
            name='saison',
            description='saison league of legends',
            type=interactions.OptionType.INTEGER,
            required=False),
        Option(
            name='champion',
            description='champion',
            type=interactions.OptionType.STRING,
            required=False),
        Option(
            name='view',
            description='global ou serveur ?',
            type=interactions.OptionType.STRING,
            required=False,
            choices=[
                Choice(name='global', value='global'),
                Choice(name='serveur', value='serveur')
            ]
        )]

    parameters_personnel = [
        Option(
            name="mode",
            description="Quel mode de jeu ?",
            type=interactions.OptionType.STRING,
            required=True, choices=[
                Choice(name='ranked',
                       value='RANKED'),
                Choice(name='aram', value='ARAM')]),
        Option(
            name="joueur",
            description="Quel joueur ?",
            type=interactions.OptionType.STRING,
            required=True),
        Option(
            name='saison',
            description='saison league of legends',
            type=interactions.OptionType.INTEGER,
            required=False),
        Option(
            name='champion',
            description='champion',
            type=interactions.OptionType.STRING,
            required=False)]

    @interactions.extension_command(name="records_list_v2",
                                    description="Voir les records détenues par les joueurs",
                                    options=[
                                        option_stats_records(name='general',
                                                                  params=parameters_communs, description='Records tout confondu'),
                                        option_stats_records(
                                            name='personnel', params=parameters_personnel, description='Record sur un joueur')
                                    ])
    async def records_list_v2(self,
                              ctx: CommandContext,
                              sub_command: str,
                              saison: int = 12,
                              mode: str = 'ranked',
                              joueur=None,
                              champion=None,
                              view='global'):

        await ctx.defer(ephemeral=False)
        
        
        if view == 'global':
            fichier = lire_bdd_perso('SELECT distinct * from matchs where season = %(saison)s and mode = %(mode)s', index_col='id', params={'saison': saison,
                                                                                                                                        'mode': mode}).transpose()
        elif view == 'serveur':
            fichier = lire_bdd_perso('''SELECT distinct matchs.* from matchs
                                     INNER JOIN tracker on tracker.index = matchs.joueur
                                     where season = %(saison)s and mode = %(mode)s
                                     and server_id = %(guild_id)s''', index_col='id', params={'saison': saison,
                                                                                              'mode': mode,
                                                                                              'guild_id' : int(ctx.guild_id)}).transpose()
            

        if champion != None:

            fichier = fichier[fichier['champion'] == champion]

        if sub_command == 'personnel':

            joueur = joueur.lower()

            fichier = fichier[fichier['joueur'] == joueur]

            if champion != None:

                title = f'Records personnels {joueur} {mode} S{saison}'
            else:
                title = f'Records personnels {joueur} {mode} S{saison} ({champion})'

        else:

            if champion == None:
                title = f'Records {mode} S{saison}'
            else:
                title = f'Records {mode} S{saison} ({champion})'

        fichier1 = fichier.columns[3:22].drop(['champion', 'victoire'])
        fichier2 = fichier.columns[22:45].drop(['team'])
        fichier3 = fichier.columns[45:].drop(['afk', 'season', 'date', 'mode', 'rank', 'tier', 'kda', 'kp', 'damageratio',
                                             'lp', 'id_participant', 'item1', 'item2', 'item3', 'item4', 'item5', 'item6'])

        # on rajoute quelques éléments sur d'autres pages...

        fichier1 = np.append(fichier1, ['kda', 'kp', 'damageratio'])

        fichier1 = fichier1.tolist()

        if mode == 'ARAM':  # on vire les records qui ne doivent pas être comptés en aram

            fichier1.remove('cs_jungle')
            fichier1.remove('vision_score')
            fichier2 = fichier2.drop(['vision_pink', 'vision_wards', 'vision_wards_killed',
                                      'jgl_dix_min', 'baron', 'drake', 'herald',
                                      'vision_min', 'level_max_avantage'])
            fichier3 = fichier3.drop(
                ['vision_avantage', 'early_drake', 'early_baron'])

        embed1 = interactions.Embed(
            title=title + " (Page 1/3) :bar_chart:", color=interactions.Color.blurple())

        for column in fichier1:
            joueur, champion, record, url = trouver_records(fichier, column)

            embed1.add_field(name=f'{emote_v2.get(column, ":star:")}{column.upper()}',
                             value=f"Records : __ [{record}]({url}) __ \n ** {joueur} ** ({champion})", inline=True)

        embed2 = interactions.Embed(
            title=title + " (Page 2/3) :bar_chart:", color=interactions.Color.blurple())

        for column in fichier2:
            joueur, champion, record, url = trouver_records(fichier, column)
            embed2.add_field(name=f'{emote_v2.get(column, ":star:")}{column.upper()}',
                             value=f"Records : __ [{record}]({url}) __ \n ** {joueur} ** ({champion})", inline=True)

        embed3 = interactions.Embed(
            title=title + " (Page 3/3) :bar_chart:", color=interactions.Color.blurple())

        for column in fichier3:
            methode = 'max'
            if column in ['early_drake', 'early_baron']:
                methode = 'min'
            joueur, champion, record, url = trouver_records(
                fichier, column, methode)
            embed3.add_field(name=f'{emote_v2.get(column, ":star:")}{column.upper()}',
                             value=f"Records : __ [{record}]({url}) __ \n ** {joueur} ** ({champion})", inline=True)

        embed1.set_footer(text=f'Version {Version} by Tomlora')
        embed2.set_footer(text=f'Version {Version} by Tomlora')
        embed3.set_footer(text=f'Version {Version} by Tomlora')

        await Paginator(
            client=self.bot,
            ctx=ctx,
            pages=[
                Page(embed1.title, embed1),
                Page(embed2.title, embed2),
                Page(embed3.title, embed3)
            ]
        ).run()

    @interactions.extension_command(name="records_count",
                                    description="Compte le nombre de records",
                                    options=[
                                        Option(
                                            name="saison",
                                            description="saison lol ?",
                                            type=interactions.OptionType.INTEGER,
                                            required=False),
                                        Option(
                                            name='mode',
                                            description='quel mode de jeu ?',
                                            type=interactions.OptionType.STRING,
                                            required=False,
                                            choices=[
                                                Choice(name='ranked',
                                                       value='RANKED'),
                                                Choice(name='aram',
                                                       value='ARAM')
                                            ]
                                        ),
                                        Option(
                                            name='champion',
                                            description='focus sur un champion ?',
                                            type=interactions.OptionType.STRING,
                                            required=False
                                        ),
                                        Option(
                                            name='view',
                                            description='Global ou serveur ?',
                                            type=interactions.OptionType.STRING,
                                            required=False,
                                            choices=[
                                                Choice(name='global', value='global'),
                                                Choice(name='serveur', value='serveur')
                                            ]
                                        )
                                    ])
    async def records_count(self,
                            ctx: CommandContext,
                            saison: int = 12,
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
            fichier = lire_bdd_perso('SELECT distinct * from matchs where season = %(saison)s and mode = %(mode)s', index_col='id', params={'saison': saison,
                                                                                                                                        'mode': mode}).transpose()
        elif view == 'serveur':
            fichier = lire_bdd_perso('''SELECT distinct matchs.* from matchs
                                     INNER JOIN tracker on tracker.index = matchs.joueur
                                     where season = %(saison)s
                                     and mode = %(mode)s
                                     and server_id = %(guild_id)s''', index_col='id', params={'saison': saison,
                                                                                                'mode': mode,
                                                                                                'guild_id' : int(ctx.guild_id)}).transpose()

        # liste records

        liste_records = ['kda', 'kp', 'cs', 'cs_min', 'deaths', 'assists', 'double', 'triple', 'quadra', 'penta', 'team_kills',
                         'team_deaths', 'time', 'dmg', 'dmg_ad', 'dmg_ap', 'dmg_true', 'gold', 'gold_min', 'dmg_min', 'solokills', 'dmg_reduit', 'heal_total', 'heal_allies',
                         'serie_kills', 'cs_dix_min', 'cs_max_avantage', 'temps_dead', 'damageratio', 'tankratio', 'dmg_tank', 'shield', 'allie_feeder',
                         'vision_score', 'vision_wards', 'vision_wards_killed', 'vision_pink', 'vision_min', 'level_max_avantage', 'vision_avantage', 'early_drake', 'early_baron',
                         'jgl_dix_min', 'baron', 'drake', 'herald', 'cs_jungle']

        if champion == None:
            liste_joueurs_general = []
            liste_joueurs_champion = []
            for records in liste_records:
                methode = 'max'
                if records in ['early_drake', 'early_baron']:
                    methode = 'min'
                joueur, champion, record, url_game = trouver_records(
                    fichier, records, methode)
                liste_joueurs_general.append(joueur)

                for champion in list_champ['data']:
                    try:
                        fichier_champion = fichier[fichier['champion']
                                                   == champion]
                        joueur, champion, record, url_game = trouver_records(
                            fichier_champion, records, methode)
                        liste_joueurs_champion.append(joueur)
                    except:  # personne a le record
                        pass

            counts_general = pd.Series(liste_joueurs_general).value_counts()
            counts_champion = pd.Series(liste_joueurs_champion).value_counts()

            select = interactions.SelectMenu(
                options=[
                    interactions.SelectOption(
                        label="general", value="general", emoji=interactions.Emoji(name='1️⃣')),
                    interactions.SelectOption(
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

            liste_joueurs_champion = []

            for records in liste_records:
                methode = 'max'
                if records in ['early_drake', 'early_baron']:
                    methode = 'min'
                joueur, champion, record, url_game = trouver_records(
                    fichier, records, methode)
                liste_joueurs_champion.append(joueur)

            counts_champion = pd.Series(liste_joueurs_champion).value_counts()

            fig = px.histogram(counts_champion,
                               counts_champion.index,
                               counts_champion.values,
                               text_auto=True,
                               color=counts_champion.index,
                               title=f'Record {champion} ({mode}) ')
            
            embed, file = get_embed(fig, 'stats')
            
            await ctx.send(embeds=embed, files=file)
            


def setup(bot):
    Recordslol(bot)
