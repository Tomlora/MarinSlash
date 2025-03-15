import numpy as np
import pandas as pd
from fonctions.gestion_bdd import lire_bdd, lire_bdd_perso
from fonctions.word import suggestion_word
import interactions
from interactions import SlashCommandChoice, SlashCommandOption, Extension, SlashContext, slash_command, AutocompleteContext
from interactions.ext.paginators import Paginator
from fonctions.params import Version, saison
from fonctions.match import trouver_records, get_champ_list, get_version, trouver_records_multiples, emote_champ_discord
from aiohttp import ClientSession
import plotly.express as px
import asyncio
from fonctions.channels_discord import get_embed, mention
import difflib


def option_stats_records(name, params, description='type de recherche'):
    option = SlashCommandOption(
        name=name,
        description=description,
        type=interactions.OptionType.SUB_COMMAND,
        options=params)

    return option



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
    "skillshot_dodged" : ":wind_face:",
    "temps_cc" : ":timer:",
    'spells_used' : ':archery:',
    'buffs_voles' : ':spy:',
    'abilityHaste' : ':timer:',
    'abilityPower' : ':magic_wand:',
    'armor' : ':shield:',
    'attackDamage' : ':crossed_swords:',
    'currentGold' : ':euro:',
    'healthMax' : ':sparkling_heart:',
    'magicResist' : ':shield:',
    'movementSpeed' : ':wind_face:',
    'fourth_dragon' : ':dragon:',
    'first_elder' : ':dragon:',
    'first_horde' : ':space_invader:',
    'first_double' : ':two:',
    'first_triple' : ':three:',
    'first_quadra' : ':four:',
    'first_penta' : ':five:',
    'first_niveau_max' : ':star:',
    'first_blood' : ':dagger:',
    'kills_min' : ':dagger:',
    'deaths_min' : ':skull:',
    'assists_min' : ':crossed_swords:',
    'petales_sanglants' : ':rose:',
    'crit_dmg' : ':dart:',
    'immobilisation' : ':stop_sign:',
    'temps_CC_inflige' : ':timer:',
    'tower' : ':tokyo_tower:',
    'inhib' : ':tokyo_tower:',
    'dmg_true_all' : ':dart:',
    'dmg_true_all_min' : ':dart:',
    'dmg_ad_all' : ':dart:',
    'dmg_ad_all_min' : ':dart:',
    'dmg_ap_all' : ':dart:',
    'dmg_ap_all_min' : ':dart:',
    'dmg_all' : ':dart:',
    'dmg_all_min' : ':dart:',
    'longue_serie_kills' : ":crossed_swords:",
    'early_atakhan' : ':alien:',
    'ecart_kills' : ':crossed_swords:',
    'ecart_deaths' : ':skull:',
    'ecart_assists' : ':crossed_swords:',
    'ecart_dmg' : ':dart:',
}



async def load_data(ctx, view, saison, mode, time_mini):

        if saison != 0:
        
            if view == 'global':
                fichier = lire_bdd_perso(f'''SELECT distinct matchs.*, tracker.riot_id, tracker.riot_tagline, tracker.discord,
                                            max_data_timeline."abilityHaste" AS "abilityHaste",
                                            max_data_timeline."abilityPower" AS "abilityPower",
                                            max_data_timeline.armor AS armor,
                                            max_data_timeline."attackDamage" AS "attackDamage",
                                            max_data_timeline."currentGold" AS "currentGold",
                                            max_data_timeline."healthMax" AS "healthMax",
                                            max_data_timeline."magicResist" AS "magicResist",
                                            max_data_timeline."movementSpeed" AS "movementSpeed",
                                            "ASSISTS_10", "ASSISTS_20", "ASSISTS_30",
                                            "BUILDING_KILL_20", "BUILDING_KILL_30",
                                            "CHAMPION_KILL_10", "CHAMPION_KILL_20", "CHAMPION_KILL_30",
                                            "DEATHS_10", "DEATHS_20", "DEATHS_30",
                                            "ELITE_MONSTER_KILL_10", "ELITE_MONSTER_KILL_20", "ELITE_MONSTER_KILL_30",
                                            "LEVEL_UP_10", "LEVEL_UP_20", "LEVEL_UP_30",
                                            "TURRET_PLATE_DESTROYED_10",
                                            "WARD_KILL_10", "WARD_KILL_20", "WARD_KILL_30",
                                            "WARD_PLACED_10", "WARD_PLACED_20", "WARD_PLACED_30",
                                         "TOTAL_CS_20", "TOTAL_CS_30", "TOTAL_GOLD_20", "TOTAL_GOLD_30", "CS_20", "CS_30", "JGL_20", "JGL_30",
                                        "l_ecart_cs", "l_ecart_gold", "l_ecart_gold_min_durant_game", "l_ecart_gold_max_durant_game", "l_kda", "l_cs", "l_cs_max_avantage",
                                          "l_level_max_avantage", "l_ecart_gold_team", "l_ecart_kills_team", "l_temps_avant_premiere_mort",
                                         "l_ecart_kills", "l_ecart_deaths", "l_ecart_assists", "l_ecart_dmg", "l_allie_feeder", "l_temps_vivant","l_time", "l_solokills"     

                                        from matchs
                                        INNER JOIN tracker on tracker.id_compte = matchs.joueur
                                        LEFT JOIN max_data_timeline ON matchs.joueur = max_data_timeline.riot_id and matchs.match_id = max_data_timeline.match_id
                                        LEFT JOIN data_timeline_palier ON matchs.joueur = data_timeline_palier.riot_id and matchs.match_id = data_timeline_palier.match_id
                                        LEFT JOIN records_loser ON matchs.joueur = records_loser.joueur and matchs.match_id = records_loser.match_id 
                                        where season = {saison}
                                        and mode = '{mode}'
                                        and time >= {time_mini[mode]}
                                        and tracker.banned = false
                                        and tracker.save_records = true
                                        and matchs.records = true ''', index_col='id').transpose()
            elif view == 'serveur':
                fichier = lire_bdd_perso(f'''SELECT distinct matchs.*, tracker.riot_id, tracker.riot_tagline, tracker.discord,
                                            max_data_timeline."abilityHaste" AS "abilityHaste",
                                            max_data_timeline."abilityPower" AS "abilityPower",
                                            max_data_timeline.armor AS armor,
                                            max_data_timeline."attackDamage" AS "attackDamage",
                                            max_data_timeline."currentGold" AS "currentGold",
                                            max_data_timeline."healthMax" AS "healthMax",
                                            max_data_timeline."magicResist" AS "magicResist",
                                            max_data_timeline."movementSpeed" AS "movementSpeed",
                                            "ASSISTS_10", "ASSISTS_20", "ASSISTS_30",
                                            "BUILDING_KILL_20", "BUILDING_KILL_30",
                                            "CHAMPION_KILL_10", "CHAMPION_KILL_20", "CHAMPION_KILL_30",
                                            "DEATHS_10", "DEATHS_20", "DEATHS_30",
                                            "ELITE_MONSTER_KILL_10", "ELITE_MONSTER_KILL_20", "ELITE_MONSTER_KILL_30",
                                            "LEVEL_UP_10", "LEVEL_UP_20", "LEVEL_UP_30",
                                            "TURRET_PLATE_DESTROYED_10", 
                                            "WARD_KILL_10", "WARD_KILL_20", "WARD_KILL_30",
                                            "WARD_PLACED_10", "WARD_PLACED_20", "WARD_PLACED_30",
                                         "TOTAL_CS_20", "TOTAL_CS_30", "TOTAL_GOLD_20", "TOTAL_GOLD_30", "CS_20", "CS_30", "JGL_20", "JGL_30",
                                        "l_ecart_cs", "l_ecart_gold", "l_ecart_gold_min_durant_game", "l_ecart_gold_max_durant_game", "l_kda", "l_cs", "l_cs_max_avantage",
                                        "l_level_max_avantage", "l_ecart_gold_team", "l_ecart_kills_team", "l_temps_avant_premiere_mort",
                                          "l_ecart_kills", "l_ecart_deaths", "l_ecart_assists", "l_ecart_dmg", "l_allie_feeder", "l_temps_vivant","l_time", "l_solokills"  
                                                                                
                                        from matchs
                                        INNER JOIN tracker on tracker.id_compte = matchs.joueur
                                        LEFT JOIN max_data_timeline ON matchs.joueur = max_data_timeline.riot_id and matchs.match_id = max_data_timeline.match_id
                                        LEFT JOIN data_timeline_palier ON matchs.joueur = data_timeline_palier.riot_id and matchs.match_id = data_timeline_palier.match_id
                                        LEFT JOIN records_loser ON matchs.joueur = records_loser.joueur and matchs.match_id = records_loser.match_id 
                                        where season = {saison}
                                        and mode = '{mode}'
                                        and server_id = {int(ctx.guild_id)}
                                        and time >= {time_mini[mode]}
                                        and tracker.banned = false
                                        and tracker.save_records = true
                                        and matchs.records = true ''', index_col='id').transpose()

        else:
            if view == 'global':
                fichier = lire_bdd_perso(f'''SELECT distinct matchs.*, tracker.riot_id, tracker.riot_tagline, tracker.discord,
                                            max_data_timeline."abilityHaste" AS "abilityHaste",
                                            max_data_timeline."abilityPower" AS "abilityPower",
                                            max_data_timeline.armor AS armor,
                                            max_data_timeline."attackDamage" AS "attackDamage",
                                            max_data_timeline."currentGold" AS "currentGold",
                                            max_data_timeline."healthMax" AS "healthMax",
                                            max_data_timeline."magicResist" AS "magicResist",
                                            max_data_timeline."movementSpeed" AS "movementSpeed",
                                            "ASSISTS_10", "ASSISTS_20", "ASSISTS_30",
                                            "BUILDING_KILL_20", "BUILDING_KILL_30",
                                            "CHAMPION_KILL_10", "CHAMPION_KILL_20", "CHAMPION_KILL_30",
                                            "DEATHS_10", "DEATHS_20", "DEATHS_30",
                                            "ELITE_MONSTER_KILL_10", "ELITE_MONSTER_KILL_20", "ELITE_MONSTER_KILL_30",
                                            "LEVEL_UP_10", "LEVEL_UP_20", "LEVEL_UP_30",
                                            "TURRET_PLATE_DESTROYED_10",
                                            "WARD_KILL_10", "WARD_KILL_20", "WARD_KILL_30",
                                            "WARD_PLACED_10", "WARD_PLACED_20", "WARD_PLACED_30",
                                         "TOTAL_CS_20", "TOTAL_CS_30", "TOTAL_GOLD_20", "TOTAL_GOLD_30", "CS_20", "CS_30", "JGL_20", "JGL_30",
                                         "l_ecart_cs", "l_ecart_gold", "l_ecart_gold_min_durant_game", "l_ecart_gold_max_durant_game", "l_kda", "l_cs", "l_cs_max_avantage",
                                          "l_level_max_avantage", "l_ecart_gold_team", "l_ecart_kills_team", "l_temps_avant_premiere_mort",
                                          "l_ecart_kills", "l_ecart_deaths", "l_ecart_assists", "l_ecart_dmg", "l_allie_feeder", "l_temps_vivant","l_time", "l_solokills"   
                                                                                
                                        from matchs
                                        INNER JOIN tracker on tracker.id_compte = matchs.joueur
                                        LEFT JOIN max_data_timeline ON matchs.joueur = max_data_timeline.riot_id and matchs.match_id = max_data_timeline.match_id
                                        LEFT JOIN data_timeline_palier ON matchs.joueur = data_timeline_palier.riot_id and matchs.match_id = data_timeline_palier.match_id
                                        LEFT JOIN records_loser ON matchs.joueur = records_loser.joueur and matchs.match_id = records_loser.match_id 
                                        where mode = '{mode}'
                                        and time >= {time_mini[mode]}
                                        and tracker.banned = false
                                        and tracker.save_records = true
                                        and matchs.records = true ''', index_col='id').transpose()
            elif view == 'serveur':
                fichier = lire_bdd_perso(f'''SELECT distinct matchs.*, tracker.riot_id, tracker.riot_tagline, tracker.discord,
                                            max_data_timeline."abilityHaste" AS "abilityHaste",
                                            max_data_timeline."abilityPower" AS "abilityPower",
                                            max_data_timeline.armor AS armor,
                                            max_data_timeline."attackDamage" AS "attackDamage",
                                            max_data_timeline."currentGold" AS "currentGold",
                                            max_data_timeline."healthMax" AS "healthMax",
                                            max_data_timeline."magicResist" AS "magicResist",
                                            max_data_timeline."movementSpeed" AS "movementSpeed",
                                            "ASSISTS_10", "ASSISTS_20", "ASSISTS_30",
                                            "BUILDING_KILL_20", "BUILDING_KILL_30",
                                            "CHAMPION_KILL_10", "CHAMPION_KILL_20", "CHAMPION_KILL_30",
                                            "DEATHS_10", "DEATHS_20", "DEATHS_30",
                                            "ELITE_MONSTER_KILL_10", "ELITE_MONSTER_KILL_20", "ELITE_MONSTER_KILL_30",
                                            "LEVEL_UP_10", "LEVEL_UP_20", "LEVEL_UP_30",
                                            "TURRET_PLATE_DESTROYED_10", 
                                            "WARD_KILL_10", "WARD_KILL_20", "WARD_KILL_30",
                                            "WARD_PLACED_10", "WARD_PLACED_20", "WARD_PLACED_30",
                                         "TOTAL_CS_20", "TOTAL_CS_30", "TOTAL_GOLD_20", "TOTAL_GOLD_30", "CS_20", "CS_30", "JGL_20", "JGL_30",
                                         "l_ecart_cs", "l_ecart_gold", "l_ecart_gold_min_durant_game", "l_ecart_gold_max_durant_game", "l_kda", "l_cs", "l_cs_max_avantage",
                                          "l_level_max_avantage", "l_ecart_gold_team", "l_ecart_kills_team", "l_temps_avant_premiere_mort",
                                          "l_ecart_kills", "l_ecart_deaths", "l_ecart_assists", "l_ecart_dmg", "l_allie_feeder", "l_temps_vivant","l_time", "l_solokills"  
                                                                                
                                        from matchs
                                        INNER JOIN tracker on tracker.id_compte = matchs.joueur
                                        LEFT JOIN max_data_timeline ON matchs.joueur = max_data_timeline.riot_id and matchs.match_id = max_data_timeline.match_id
                                        LEFT JOIN data_timeline_palier ON matchs.joueur = data_timeline_palier.riot_id and matchs.match_id = data_timeline_palier.match_id
                                        LEFT JOIN records_loser ON matchs.joueur = records_loser.joueur and matchs.match_id = records_loser.match_id 
                                        where mode = '{mode}'
                                        and server_id = {int(ctx.guild_id)}
                                        and time >= {time_mini[mode]}
                                        and tracker.banned = false
                                        and tracker.save_records = true
                                        and matchs.records = true ''', index_col='id').transpose()

        return fichier


        
async def format_value(joueur, champion, url, short=False):
            text = ''
            for j, c, u in zip(joueur, champion, url):
                if short:
                    text += f'**__ {j} __ {c} ** \n'
                else:
                    text += f'**__{j}__** [{c}]({u}) \n'
            return text

async def format_value_season(joueur, champion, url, liste_season, short=False):
            text = ''
            for j, c, u, s in zip(joueur, champion, url, liste_season):
                if short:
                    text += f'**__ {j} __ {c} S{s} ** \n'
                else:
                    text += f'**__{j}__** [{c}]({u}) S{s}\n'
            return text
        

async def creation_embed(fichier, column, methode_pseudo, embed, methode='max', saison=saison, rank=False):
                if rank:
                    joueur, champion, record, url, rank_joueur, season= trouver_records_multiples(fichier, column, methode, identifiant=methode_pseudo, rank=rank)
                else:
                    joueur, champion, record, url, season = trouver_records_multiples(fichier, column, methode, identifiant=methode_pseudo)
                # on montre l'image du champ uniquement quand le record appartient à une seule personne sinon on dépasse la limite de caractères
                
                if saison != 0:
                    value_text = await format_value(joueur, champion, url, short=False) if len(joueur) > 1 else f"**{joueur[0]}** {emote_champ_discord.get(champion[0].capitalize(), 'inconnu')} [G]({url[0]})\n"
                else:
                    value_text = await format_value_season(joueur, champion, url, season, short=False) if len(joueur) > 1 else f"**{joueur[0]}** {emote_champ_discord.get(champion[0].capitalize(), 'inconnu')} [G]({url[0]}) S{season[0]}\n"

                if rank:
                    embed.add_field(
                        name=f'{emote_v2.get(column, ":star:")}{column.upper()}',
                        value=f"Records : __{record}__ (#{rank_joueur}) \n {value_text}",
                        inline=True
                    )
                else:
                    embed.add_field(
                        name=f'{emote_v2.get(column, ":star:")}{column.upper()}',
                        value=f"Records : __ {record} __ \n {value_text}",
                        inline=True
                    )
                
                return embed

async def calcul_record(fichier, liste_records, records_min, title, title_personnalise, methode_pseudo, saison, rank:bool):
            embed = interactions.Embed(title=f'{title} {title_personnalise}', color=interactions.Color.random())

            for column in liste_records:
                methode = 'max'
                if column in records_min:
                    methode = 'min'

                embed = await creation_embed(fichier, column, methode_pseudo, embed, methode, saison=saison, rank=rank)
            
            return embed



# async def format_value_indiv(joueur, champion, url, short=False):
#             text = ''

#             for j, c, u in zip(joueur, champion, url):
#                 if short:
#                     text += f'**__ {j} __ {c} ** \n'
#                 else:
#                     text += f'**__{j}__** {emote_champ_discord.get(c.capitalize(), "inconnu")} [G]({u}) \n'
#             return text

# async def format_value_season_indiv(joueur, champion, url, liste_season, short=False):
#             text = ''

#             for j, c, u, s in zip(joueur, champion, url, liste_season):
#                 if short:
#                     text += f'**__ {j} __ {c} S{s} ** \n'
#                 else:
#                     text += f'**__{j}__** {emote_champ_discord.get(c.capitalize(), "inconnu")} [G]({u}) S{s} \n'
#             return text
        
# async def creation_embed_indiv(fichier, column, methode_pseudo, embed, methode='max', saison=saison):
#                 joueur, champion, record, url, rank, season = trouver_records_multiples(fichier, column, methode, identifiant=methode_pseudo, rank=True)

#                 if saison != 0:
#                     value_text = format_value_indiv(joueur, champion, url, short=False) if len(joueur) > 1 else f"** {joueur[0]} ** {emote_champ_discord.get(champion[0].capitalize(), 'inconnu')} [G]({url[0]})\n"
#                 else:
#                     value_text = format_value_season_indiv(joueur, champion, url, season, short=False) if len(joueur) > 1 else f"** {joueur[0]} ** {emote_champ_discord.get(champion[0].capitalize(), 'inconnu')} [G]({url[0]}) S{season[0]}\n"


#                 embed.add_field(
#                     name=f'{emote_v2.get(column, ":star:")}{column.upper()}',
#                     value=f"Records : __{record}__ (#{rank}) \n {value_text}",
#                     inline=True
#                 )
                
#                 return embed


# async def calcul_record_indiv(fichier, records_min, title, title_personnalise, methode_pseudo, saison):
#             embed = interactions.Embed(title=f'{title} {title_personnalise}', color=interactions.Color.random())

#             for column in fichier:
#                 methode = 'max'
#                 if column in records_min:
#                     methode = 'min'

#                 embed = await creation_embed_champ(fichier, column, methode_pseudo, embed, methode, saison=saison)
            
#             return embed


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
        self.time_mini = {'RANKED' : 15, 'ARAM' : 10, 'FLEX' : 15, 'SWIFTPLAY' : 15} # minutes minimum pour compter dans les records
        
        self.fichier_kills = ['kills', 'assists', 'deaths', 'double', 'triple', 'quadra', 'penta', 'solokills', 'team_kills', 'team_deaths', 'kda', 'kp', 'kills+assists', 'serie_kills', 'first_double', 'first_triple', 'first_quadra', 'first_penta',  'kills_min', 'deaths_min', 'assists_min', 'longue_serie_kills', 'ecart_kills', 'ecart_deaths', 'ecart_assists'] 
        self.fichier_dmg = ['dmg', 'dmg_ad', 'dmg_ap', 'dmg_true', 'damageratio', 'dmg_min', 'dmg/gold', 'crit_dmg', 'dmg_true_all', 'dmg_true_all_min', 'dmg_ad_all', 'dmg_ad_all_min', 'dmg_ap_all', 'dmg_ap_all_min', 'dmg_all', 'dmg_all_min', 'ecart_dmg']
        self.fichier_vision = ['vision_score', 'vision_pink', 'vision_wards', 'vision_wards_killed', 'vision_min', 'vision_avantage']
        self.fichier_farming = ['cs', 'cs_jungle', 'cs_min', 'cs_dix_min', 'jgl_dix_min', 'cs_max_avantage']
        self.fichier_tank_heal = ['dmg_reduit', 'dmg_tank', 'tankratio', 'shield', 'heal_total', 'heal_allies']
        self.fichier_objectif = ['baron', 'drake', 'early_drake', 'early_baron', 'dmg_tower', 'fourth_dragon', 'first_elder', 'first_horde', 'petales_sanglants', 'tower', 'inhib', 'early_atakhan']
        self.fichier_divers = ['time', 'gold', 'gold_min', 'gold_share', 'ecart_gold_team', 'level_max_avantage', 'temps_dead', 'temps_vivant', 'allie_feeder', 'temps_avant_premiere_mort', 'snowball', 'skillshot_dodged', 'temps_cc', 'spells_used', 'buffs_voles', 'immobilisation', 'temps_cc_inflige', 'first_blood']
        self.fichier_stats = ['abilityHaste', 'abilityPower', 'armor', 'attackDamage', 'currentGold', 'healthMax', 'magicResist', 'movementSpeed', 'first_niveau_max']
        self.fichier_timer = ["ASSISTS_10", "ASSISTS_20", "ASSISTS_30",
                                        "BUILDING_KILL_20", "BUILDING_KILL_30",
                                        "CHAMPION_KILL_10", "CHAMPION_KILL_20", "CHAMPION_KILL_30",
                                        "DEATHS_10", "DEATHS_20", "DEATHS_30",
                                        "ELITE_MONSTER_KILL_10", "ELITE_MONSTER_KILL_20", "ELITE_MONSTER_KILL_30",
                                        "LEVEL_UP_10", "LEVEL_UP_20", "LEVEL_UP_30",
                                        "TURRET_PLATE_DESTROYED_10",
                                        "WARD_KILL_10", "WARD_KILL_20", "WARD_KILL_30",
                                        "WARD_PLACED_10", "WARD_PLACED_20", "WARD_PLACED_30"]
        
        self.fichier_timer2 = ["TOTAL_CS_20", "TOTAL_CS_30", "TOTAL_GOLD_20", "TOTAL_GOLD_30", "CS_20", "CS_30", "JGL_20", "JGL_30"]


        self.loser = ['l_ecart_cs', 'l_ecart_gold', 'l_ecart_gold_min_durant_game', 'l_ecart_gold_max_durant_game', 'l_kda', 'l_cs', 'l_cs_max_avantage', 'l_level_max_avantage', 'l_ecart_gold_team', 'l_ecart_kills_team', 'l_temps_avant_premiere_mort',
                      'l_ecart_kills', 'l_ecart_deaths', 'l_ecart_assists', 'l_ecart_dmg', 'l_allie_feeder', 'l_temps_vivant', 'l_time', 'l_solokills']

        self.liste_complete = self.fichier_kills + self.fichier_dmg + self.fichier_vision + self.fichier_farming + self.fichier_tank_heal + self.fichier_objectif + self.fichier_divers + self.fichier_stats + self.fichier_timer + self.fichier_timer2 + self.loser


        self.records_min = ['early_drake', 'early_baron', 'fourth_dragon', 'first_elder', 'first_horde', 'first_double', 'first_triple', 'first_quadra', 'first_penta', 'first_niveau_max', 'first_blood', 'early_atakhan', 'l_ecart_gold_min_durant_game']
        
    @slash_command(name='lol_records', description='records League of Legends')
    async def records_lol(self, ctx: SlashContext):
        pass


    parameters_communs = [
        SlashCommandOption(
            name="mode",
            description="Quel mode de jeu ?",
            type=interactions.OptionType.STRING,
            required=True, choices=[
                SlashCommandChoice(name='ranked',value='RANKED'),
                SlashCommandChoice(name='aram', value='ARAM'),
                SlashCommandChoice(name='swiftplay',value='SWIFTPLAY'),
                SlashCommandChoice(name='flex', value='FLEX')]),
        SlashCommandOption(
            name='saison',
            description='saison league of legends. Si 0 alors toutes les saisons',
            type=interactions.OptionType.INTEGER,
            required=False,
            min_value=0,
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
                SlashCommandChoice(name='ranked',value='RANKED'),
                SlashCommandChoice(name='aram', value='ARAM'),
                SlashCommandChoice(name='swiftplay',value='SWIFTPLAY'),
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
            description='saison league of legends. Si 0 alors toutes les saisons. Si 0 alors toutes les saisons',
            type=interactions.OptionType.INTEGER,
            required=False,
            min_value=0,
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
                                   champion:str=None,
                                   view='global'):
        
        await ctx.defer(ephemeral=False)
        
        methode_pseudo = 'discord'

        fichier = await load_data(ctx, view, saison, mode, self.time_mini)

        if champion != None:
            
            champion = champion.capitalize()

            fichier = fichier[fichier['champion'] == champion] 
            
        if champion == None:
                title = f'Records {mode} S{saison}'
        else:
                title = f'Records {mode} S{saison} ({champion})'

        fichier_farming = self.fichier_farming.copy()
        fichier_divers = self.fichier_divers.copy()
        fichier_kills = self.fichier_kills.copy()
        fichier_timer = self.fichier_timer.copy()
        fichier_timer2 = self.fichier_timer2.copy()

        # on rajoute quelques éléments sur d'autres pages...

        
        if mode in ['RANKED', 'FLEX', 'SWIFTPLAY']:
            fichier_divers.remove('snowball')

        if mode == 'ARAM':  # on vire les records qui ne doivent pas être comptés en aram

            fichier_farming.remove('cs_jungle')
            fichier_farming.remove('jgl_dix_min')
            fichier_kills.remove('first_double')
            fichier_kills.remove('first_triple')
            fichier_kills.remove('first_quadra')
            fichier_kills.remove('first_penta')
            fichier_kills.remove('first_blood')






        embed1 = await calcul_record(fichier, fichier_kills, self.records_min, title, 'Kills', methode_pseudo, saison, False)
        embed2 = await calcul_record(fichier, self.fichier_dmg, self.records_min, title, 'DMG', methode_pseudo, saison, False)
        embed5 = await calcul_record(fichier, fichier_farming, self.records_min, title, 'Farming', methode_pseudo, saison, False)
        embed6 = await calcul_record(fichier, self.fichier_tank_heal, self.records_min, title, 'Tank/Heal', methode_pseudo, saison, False)
        embed7 = await calcul_record(fichier, fichier_divers, self.records_min, title, 'Divers', methode_pseudo, saison, False)

        
            

        if mode != 'ARAM':

            embed3 = await calcul_record(fichier, self.fichier_vision, self.records_min, title, 'Vision', methode_pseudo, saison, False)
            embed4 = await calcul_record(fichier, self.fichier_objectif, self.records_min, title, 'Objectif', methode_pseudo, saison, False)
            embed8 = await calcul_record(fichier, self.fichier_stats, self.records_min, title, 'Stats', methode_pseudo, saison, False)
            embed9 = await calcul_record(fichier, fichier_timer, self.records_min, title, 'Timer', methode_pseudo, saison, False)
            embed10 = await calcul_record(fichier, fichier_timer2, self.records_min, title, 'Timer2', methode_pseudo, saison, False)
            embed11 = await calcul_record(fichier, self.loser, self.records_min, title, 'Loser', methode_pseudo, saison, False)

            
        for embed in [embed1, embed2, embed5, embed6, embed7]:
            embed.set_footer(text=f'Version {Version} by Tomlora')

        if mode != 'ARAM':
            for embed in [embed3, embed4, embed8, embed9, embed10, embed11]:
                embed.set_footer(text=f'Version {Version} by Tomlora')

            pages=[embed1, embed2, embed3, embed4, embed5, embed6, embed7, embed8, embed9, embed10, embed11]

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
    
        fichier = await load_data(ctx, view, saison, mode, self.time_mini)

        
        fichier['early_drake'] = fichier['early_drake'].replace({0 : 999})    
        fichier['early_baron'] = fichier['early_baron'].replace({0 : 999}) 
        
        
        
        for column in self.liste_complete:
            
            try:
                fichier[f'{column}_rank_max'] = fichier[column].rank(method='min', ascending=False).astype(int)
                fichier[f'{column}_rank_min'] = fichier[column].rank(method='min', ascending=True).astype(int)
            except:
                try:
                    fichier[column].fillna(0, inplace=True)
                    fichier[f'{column}_rank_max'] = fichier[column].rank(method='min', ascending=False).astype(int)
                    fichier[f'{column}_rank_min'] = fichier[column].rank(method='min', ascending=True).astype(int)
                except:
                    print('erreur', column)
        
        nb_games = fichier.shape[0]    

        if champion != None:
            
            champion = champion.capitalize()

            fichier = fichier[fichier['champion'] == champion]

            
        if joueur != None:
            
            joueur = joueur.lower().replace(' ', '')
                
            id_joueur = lire_bdd_perso('''SELECT tracker.riot_id, tracker.discord from tracker where tracker.banned = false and tracker.save_records = true ''',
                                            format='dict', index_col='riot_id')
            try:
                fichier = fichier[fichier['riot_id'] == joueur]
            except KeyError:
                return await ctx.send('Joueur introuvable ou tu es banni')    
              
        elif compte_discord != None:
                
            id_discord = str(compte_discord.id)

                               
            joueur = compte_discord.global_name
            try:    
                fichier = fichier[fichier['discord'] == id_discord]
            except KeyError:
                return await ctx.send('Joueur introuvable ou tu es banni. ')    
                
            
        elif joueur == None and compte_discord == None:
                
            fichier = fichier[fichier['discord'] == str(ctx.author.id)]

            try:
                joueur = ctx.author.nick
            except AttributeError:
                try:
                    joueur = ctx.author.nickname
                except AttributeError:
                    joueur = ctx.user.global_name
            author_global = ctx.author.global_name
            if joueur == None:
                joueur = author_global                
            joueur = ctx.author.global_name
                
        methode_pseudo = 'riot_id'

        if champion == None:

                title = f'Records personnels {joueur} {mode} S{saison}'
        else:
                title = f'Records personnels {joueur} {mode} S{saison} ({champion})'

        
        fichier_farming = self.fichier_farming.copy()
        fichier_divers = self.fichier_divers.copy()
        fichier_timer = self.fichier_timer.copy()
        fichier_timer2 = self.fichier_timer2.copy()

        # on rajoute quelques éléments sur d'autres pages...

        
        if mode in ['RANKED', 'FLEX', 'SWIFTPLAY']:
            fichier_divers.remove('snowball')

        if mode == 'ARAM':  # on vire les records qui ne doivent pas être comptés en aram

            fichier_farming.remove('cs_jungle')
            fichier_farming.remove('jgl_dix_min')
            
            for stat in ["WARD_KILL_10", "WARD_KILL_20", "WARD_KILL_30", "WARD_PLACED_10", "WARD_PLACED_20", "WARD_PLACED_30", "ELITE_MONSTER_KILL_10", "ELITE_MONSTER_KILL_20", "ELITE_MONSTER_KILL_30", "TURRET_PLATE_DESTROYED_10"]:
                fichier_timer.remove(stat)




        embed1 = await calcul_record(fichier, self.fichier_kills, self.records_min, title, 'Kills', methode_pseudo, saison, True)
        embed2 = await calcul_record(fichier, self.fichier_dmg, self.records_min, title, 'DMG', methode_pseudo, saison, True)
        embed5 = await calcul_record(fichier, fichier_farming, self.records_min, title, 'Farming', methode_pseudo, saison, True)
        embed6 = await calcul_record(fichier, self.fichier_tank_heal, self.records_min, title, 'Tank/Heal', methode_pseudo, saison, True)
        embed7 = await calcul_record(fichier, fichier_divers, self.records_min, title, 'Divers', methode_pseudo, saison, True)
        
            

        if mode != 'ARAM':
            
            embed3 = await calcul_record(fichier, self.fichier_vision, self.records_min, title, 'Vision', methode_pseudo, saison, True)
            embed4 = await calcul_record(fichier, self.fichier_objectif, self.records_min, title, 'Objectif', methode_pseudo, saison, True)
            embed8 = await calcul_record(fichier, self.fichier_stats, self.records_min, title, 'Stats', methode_pseudo, saison, True)
            embed9 = await calcul_record(fichier, fichier_timer, self.records_min, title, 'Timer', methode_pseudo, saison, True)
            embed10 = await calcul_record(fichier, fichier_timer2, self.records_min, title, 'Timer2', methode_pseudo, saison, True)
            embed11 = await calcul_record(fichier, self.loser, self.records_min, title, 'Loser', methode_pseudo, saison, True)

        for embed in [embed1, embed2, embed5, embed6, embed7]:
            embed.set_footer(text=f'Version {Version} by Tomlora - {nb_games} parties')


        if mode != 'ARAM':
            for embed in [embed3, embed4, embed8, embed9, embed10, embed11]:
                embed.set_footer(text=f'Version {Version} by Tomlora - {nb_games} parties')

            pages=[embed1, embed2, embed3, embed4, embed5, embed6, embed7, embed8, embed9, embed10, embed11]

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
                                            description="saison lol ? Si 0 toutes les saisons",
                                            type=interactions.OptionType.INTEGER,
                                            required=False,
                                            min_value=0,
                                            max_value=saison),
                                        SlashCommandOption(
                                            name='mode',
                                            description='quel mode de jeu ?',
                                            type=interactions.OptionType.STRING,
                                            required=False,
                                            choices=[
                                                SlashCommandChoice(name='ranked', value='RANKED'),
                                                SlashCommandChoice(name='aram', value='ARAM'),
                                                SlashCommandChoice(name='flex', value='FLEX'),
                                                SlashCommandChoice(name='swiftplay',value='SWIFTPLAY'),
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

        fichier = await load_data(ctx, view, saison, mode, self.time_mini)

        # liste records

        if mode in ['RANKED', 'FLEX', 'SWIFTPLAY']:
            liste_records = ['kills', 'assists', 'deaths', 'double', 'triple', 'quadra', 'penta', 'solokills', 'team_kills', 'team_deaths', 'kda', 'kp', 'serie_kills', 
            'dmg', 'dmg_ad', 'dmg_ap', 'dmg_true', 'damageratio', 'dmg_min', 'vision_score', 'vision_pink', 'vision_wards', 'vision_wards_killed', 'vision_min', 'vision_avantage',
            'cs', 'cs_jungle', 'cs_min', 'cs_dix_min', 'jgl_dix_min', 'cs_max_avantage', 'kills_min', 'deaths_min', 'assists_min', 'dmg_all', 'dmg_all_min', 'longue_serie_kills',
            'dmg_tank', 'dmg_reduit', 'dmg_tank', 'tankratio', 'shield', 'heal_total', 'heal_allies',
            'baron', 'drake', 'early_drake', 'early_baron', 'dmg_tower', 'petales_sanglants',
            'time', 'gold', 'gold_min', 'gold_share', 'ecart_gold_team', 'level_max_avantage', 'temps_dead', 'temps_vivant', 'allie_feeder', 'kills+assists', 'temps_avant_premiere_mort', 'dmg/gold', 
            'skillshot_dodged', 'temps_cc', 'spells_used', 'buffs_voles', 'crit_dmg', 'immobilisation', 'dmg_true_all', 'dmg_true_all_min', 'dmg_ad_all', 'dmg_ad_all_min', 'dmg_ap_all', 'dmg_ap_all_min',
            'abilityHaste', 'abilityPower', 'armor', 'attackDamage', 'currentGold', 'healthMax', 'magicResist', 'movementSpeed', 'fourth_dragon',
            'first_elder', 'first_horde', 'first_double', 'first_triple', 'first_quadra', 'first_penta', 'first_niveau_max', 'first_blood', 'tower', 'inhib', 'temps_cc_inflige', 'ecart_kills', 'ecart_deaths', 'ecart_assists', 'ecart_dmg',
            "ASSISTS_10", "ASSISTS_20", "ASSISTS_30",
                                        "BUILDING_KILL_20", "BUILDING_KILL_30",
                                        "CHAMPION_KILL_10", "CHAMPION_KILL_20", "CHAMPION_KILL_30",
                                        "DEATHS_10", "DEATHS_20", "DEATHS_30",
                                        "ELITE_MONSTER_KILL_10", "ELITE_MONSTER_KILL_20", "ELITE_MONSTER_KILL_30",
                                        "LEVEL_UP_10", "LEVEL_UP_20", "LEVEL_UP_30",
                                        "TURRET_PLATE_DESTROYED_10", 
                                        "WARD_KILL_10", "WARD_KILL_20", "WARD_KILL_30",
                                        "WARD_PLACED_10", "WARD_PLACED_20", "WARD_PLACED_30", "TOTAL_CS_20", "TOTAL_CS_30", "TOTAL_GOLD_20", "TOTAL_GOLD_30", "CS_20", "CS_30", "JGL_20", "JGL_30",
                                        'l_ecart_cs', 'l_ecart_gold', 'l_ecart_gold_min_durant_game', 'l_ecart_gold_max_durant_game', 'l_kda', 'l_cs', 'l_cs_max_avantage', 'l_level_max_avantage', 'l_ecart_gold_team', 'l_ecart_kills_team', 'l_temps_avant_premiere_mort',
                      "l_ecart_kills", "l_ecart_deaths", "l_ecart_assists", "l_ecart_dmg", "l_allie_feeder", "l_temps_vivant","l_time", "l_solokills"]


        if mode == 'ARAM':
            liste_records = ['kills', 'assists', 'deaths', 'double', 'triple', 'quadra', 'penta', 'solokills', 'team_kills', 'team_deaths', 'kda', 'kp', 'serie_kills', 
            'dmg', 'dmg_ad', 'dmg_ap', 'dmg_true', 'damageratio', 'dmg_min', 'longue_serie_kills',
            'cs', 'cs_min', 'cs_dix_min', 'cs_max_avantage', 'kills_min', 'deaths_min', 'assists_min',
            'dmg_tank', 'dmg_reduit', 'dmg_tank', 'tankratio', 'shield', 'heal_total', 'heal_allies', 'dmg_ad_all', 'dmg_ad_all_min', 'dmg_ap_all', 'dmg_ap_all_min', 'dmg_all', 'dmg_all_min',
            'baron', 'drake', 'dmg_tower', 'crit_dmg', 'immobilisation', 'temps_cc_inflige', 'dmg_true_all', 'dmg_true_all_min',
            'time', 'gold', 'gold_min', 'gold_share', 'ecart_gold_team', 'level_max_avantage', 'temps_dead', 'temps_vivant', 'allie_feeder', 'kills+assists', 'temps_avant_premiere_mort',
            'dmg/gold', 'skillshot_dodged', 'temps_cc', 'spells_used']

        if champion == None:
            # Initialisation des listes
            liste_joueurs_general = []
            liste_joueurs_champion = []

            # Parcours des enregistrements dans liste_records
            for records in liste_records:
                methode = 'max'
                if records in self.records_min:
                    methode = 'min'

                # Appel de la fonction trouver_records_multiples
                joueur, champion, record, url_game, saison = trouver_records_multiples(
                    fichier, records, methode)
                
                # Ajout des joueurs dans la liste_joueurs_general
                liste_joueurs_general.extend(joueur)

                # Parcours des champions dans la liste list_champ['data']
                for champion in list_champ['data']:
                    try:
                        # Filtre le fichier par champion
                        fichier_champion = fichier[fichier['champion'] == champion]

                        # Appel de la fonction trouver_records_multiples
                        joueur, champion, record, url_game, saison = trouver_records_multiples(
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
                if record in self.records_min:
                    methode = 'min'

                # Appel de la fonction trouver_records_multiples
                joueur, champion, record, url_game, saison = trouver_records_multiples(
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
                                            description="saison lol ? Si 0 alors toutes les saisons",
                                            type=interactions.OptionType.INTEGER,
                                            required=False,
                                            min_value=0,
                                            max_value=saison),
                                        SlashCommandOption(
                                            name='mode',
                                            description='quel mode de jeu ?',
                                            type=interactions.OptionType.STRING,
                                            required=False,
                                            choices=[
                                                SlashCommandChoice(name='ranked', value='RANKED'),
                                                SlashCommandChoice(name='aram', value='ARAM'),
                                                SlashCommandChoice(name='swiftplay',value='SWIFTPLAY'),
                                                SlashCommandChoice(name='flex', value='FLEX')
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

        await ctx.defer()

        stat = stat.lower()

        fichier = await load_data(ctx, view, saison, mode, self.time_mini)
        
        fichier.columns = [col.lower() for col in fichier.columns]
            
        if champion != None:
            fichier = fichier[fichier['champion'] == champion]
            
        if joueur != None:
            fichier = fichier[fichier['riot_id'] == joueur.replace(' ', '').lower()]
            
        if compte_discord != None:
            fichier = fichier[fichier['discord'] == str(compte_discord.id)]
            
            
            
        if stat == 'champion':
            fichier = fichier[['discord', 'champion', 'match_id']]
            nb_row = fichier.shape[0] 
            # on prépare le df count game
            count_game = fichier.groupby(['discord']).count().reset_index()
            count_game = count_game[['discord', 'champion']].rename(columns={'champion': 'count'})
            ascending=False
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
                fichier = fichier[['match_id', 'id_participant', 'discord', 'champion', stat, 'datetime', 'season']]
                
                nb_row = fichier.shape[0]
                
                                
                if stat in ['early_baron', 'early_drake', 'early_atakhan', 'l_ecart_gold_min_durant_game']:
                    ascending=True
                    fichier = fichier[fichier[stat] != 0]
                elif stat in ['fourth_dragon', 'first_elder', 'first_horde', 'first_double', 'first_triple', 'first_quadra', 'first_penta', 'first_niveau_max', 'first_blood']:
                    ascending=True
                    fichier = fichier[fichier[stat] != 999]
                else:
                    ascending=False
                    fichier = fichier[fichier[stat] != 0]
                    
                fichier.sort_values(by=stat, ascending=ascending, inplace=True)
                fichier = fichier.head(top)
                
                txt = ''
                
                
                if saison != 0:
                    for row, data in fichier.iterrows():
                        champion = data['champion']
                        txt += f'[{data[stat]}](https://www.leagueofgraphs.com/fr/match/euw/{str(data["match_id"])[5:]}#participant{int(data["id_participant"])+1}) - {mention(data["discord"], "membre")} {emote_champ_discord.get(champion.capitalize(), "inconnu")} - {data["datetime"].day}/{data["datetime"].month} \n'
                else:
                    for row, data in fichier.iterrows():
                        champion = data['champion']
                        txt += f'[{data[stat]}](https://www.leagueofgraphs.com/fr/match/euw/{str(data["match_id"])[5:]}#participant{int(data["id_participant"])+1}) - {mention(data["discord"], "membre")} {emote_champ_discord.get(champion.capitalize(), "inconnu")} - {data["datetime"].day}/{data["datetime"].month} (S{data["season"]})\n'
                    
                embed = interactions.Embed(title=f'Palmarès {stat} ({mode}) S{saison}', description=txt)
                embed.set_footer(text=f"{nb_row} matchs analysés")
                
                
                await ctx.send(embeds=embed)
                
            except KeyError:              
                suggestion = suggestion_word(stat, fichier.columns.tolist())
                await ctx.send(f"Ce record n'existe pas. Souhaitais-tu dire : **{suggestion}** ?")
                

    @records_lol.subcommand("date_record",
                                    sub_cmd_description="Date des records",
                                    options=[
                                        SlashCommandOption(
                                            name="saison",
                                            description="saison lol",
                                            type=interactions.OptionType.INTEGER,
                                            required=False,
                                            min_value=13,
                                            max_value=saison),
                                        SlashCommandOption(
                                            name='mode',
                                            description='quel mode de jeu ?',
                                            type=interactions.OptionType.STRING,
                                            required=False,
                                            choices=[
                                                SlashCommandChoice(name='ranked', value='RANKED'),
                                                SlashCommandChoice(name='aram', value='ARAM'),
                                                SlashCommandChoice(name='swiftplay',value='SWIFTPLAY'),
                                                SlashCommandChoice(name='flex', value='FLEX')]),
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
                                    ]
    )
    async def date_record(self,
                        ctx: SlashContext,
                        saison: int = saison,
                        mode:str = 'RANKED',
                        view : str = 'global'):
        

        await ctx.defer()

        fichier = await load_data(ctx, view, saison, mode, self.time_mini) 
        
            
        if saison != 0:
            fichier = fichier[['match_id', 'id_participant', 'riot_id', 'discord', 'champion','datetime'] + self.liste_complete]
        else:
            fichier = fichier[['match_id', 'id_participant', 'riot_id', 'discord', 'champion','datetime', 'season'] + self.liste_complete]
        

        fichier.columns = [col.lower() for col in fichier.columns]
        
        df_complet = []
       
        for stat in self.liste_complete: 
            stat_lower = stat.lower()                       
            if stat_lower in ['early_baron', 'early_drake', 'l_ecart_gold_min_durant_game']:
                ascending=True
                fichier_filtre = fichier[fichier[stat_lower] != 0]
            elif stat_lower in ['fourth_dragon', 'first_elder', 'first_horde', 'first_double', 'first_triple', 'first_quadra', 'first_penta', 'first_niveau_max', 'first_blood']:
                ascending=True
                fichier_filtre = fichier[fichier[stat_lower] != 999]
            else:
                ascending=False
                fichier_filtre = fichier[fichier[stat_lower] != 0]
                        
            fichier_filtre.sort_values(by=stat_lower, ascending=ascending, inplace=True)
            fichier_filtre = fichier_filtre.head(1)
            fichier_filtre['record'] = stat_lower
            df_complet.append(fichier_filtre)
            
        df_complet = pd.concat(df_complet)    
        
        
        df_complet.sort_values('datetime', ascending=False, inplace=True)
        
        txt = ''

        if saison != 0:
            for id, data in df_complet.iterrows():
                record = data["record"]
                txt += f'{emote_v2.get(record, ":star:")} **{record}** de **{data["riot_id"]}** le **{data["datetime"]}** avec {emote_champ_discord.get(data["champion"].capitalize(), data["champion"]) } : **{data[record]}** \n'
        else:
            for id, data in df_complet.iterrows():
                record = data["record"]
                txt += f'{emote_v2.get(record, ":star:")} **{record}** de **{data["riot_id"]}** le **{data["datetime"]}** avec {emote_champ_discord.get(data["champion"].capitalize(), data["champion"]) } : **{data[record]}** (S{data["season"]}) \n'
        
        paginator = Paginator.create_from_string(self.bot, txt, page_size=2000, timeout=120)

        paginator.default_title = f'Date Records {mode}'
        await paginator.send(ctx)            
                

def setup(bot):
    Recordslol(bot)
