
from fonctions.gestion_bdd import lire_bdd_perso


async def autocomplete_riotid(serverid,
                              input_txt):
    df = lire_bdd_perso(f'''select riot_id from tracker where server_id = '{serverid}' ''', index_col=None).T

    if df.empty:
        return []
    
    df['riot_id'] = df['riot_id'].str.lower()
    input_txt = input_txt.lower()

    df.sort_values(by='riot_id', inplace=True)

    liste_id = []
    for i in df['riot_id'].unique().tolist():
        if input_txt in i:
            liste_id.append({"name": f'{i}', "value": f'{i}'})
    
    return liste_id[:25]



async def autocomplete_record(record_id):

    liste_records = ['kills', 'assists', 'deaths', 'double', 'triple', 'quadra', 'penta', 'solokills', 'team_kills', 'team_deaths', 'kda', 'kp', 'kills+assists', 'serie_kills', 'first_double', 'first_triple', 'first_quadra', 'first_penta'] +\
    ['kills_min', 'deaths_min', 'assists_min', 'longue_serie_kills', 'ecart_kills', 'ecart_deaths', 'ecart_assists', 'killsratio', 'deathsratio', 'solokillsratio'] +\
    ['dmg', 'dmg_ad', 'dmg_ap', 'dmg_true', 'damageratio', 'dmg_min', 'dmg/gold', 'crit_dmg', 'dmg_true_all', 'dmg_true_all_min', 'dmg_ad_all', 'dmg_ad_all_min', 'dmg_ap_all', 'dmg_ap_all_min', 'dmg_all', 'dmg_all_min', 'ecart_dmg', 'dmg_par_kills'] +\
    ['vision_score', 'vision_pink', 'vision_wards', 'vision_wards_killed', 'vision_min', 'vision_avantage'] +\
    ['cs', 'cs_jungle', 'cs_min', 'cs_dix_min', 'jgl_dix_min', 'cs_max_avantage'] +\
    ['dmg_reduit', 'dmg_tank', 'tankratio', 'shield', 'heal_total', 'heal_allies'] +\
    ['baron', 'drake', 'early_drake', 'early_baron', 'dmg_tower', 'fourth_dragon', 'first_elder', 'first_horde', 'petales_sanglants', 'tower', 'inhib', 'early_atakhan'] +\
    ['time', 'gold', 'gold_min', 'gold_share', 'ecart_gold_team', 'level_max_avantage', 'temps_dead', 'temps_vivant', 'allie_feeder', 'temps_avant_premiere_mort', 'snowball',
    'skillshot_dodged', 'temps_cc', 'spells_used', 'buffs_voles', 'immobilisation', 'temps_cc_inflige', 'first_blood'] +\
    ['abilityHaste', 'abilityPower', 'armor', 'attackDamage', 'currentGold', 'healthMax', 'magicResist', 'movementSpeed', 'first_niveau_max'] +\
    ["ASSISTS_10", "ASSISTS_20", "ASSISTS_30",
                                        "BUILDING_KILL_20", "BUILDING_KILL_30",
                                        "CHAMPION_KILL_10", "CHAMPION_KILL_20", "CHAMPION_KILL_30",
                                        "DEATHS_10", "DEATHS_20", "DEATHS_30",
                                        "ELITE_MONSTER_KILL_10", "ELITE_MONSTER_KILL_20", "ELITE_MONSTER_KILL_30",
                                        "LEVEL_UP_10", "LEVEL_UP_20", "LEVEL_UP_30"] +\
    [ "TURRET_PLATE_DESTROYED_10", "WARD_KILL_10", "WARD_KILL_20", "WARD_KILL_30", "WARD_PLACED_10", "WARD_PLACED_20", "WARD_PLACED_30",
                                "TOTAL_CS_20", "TOTAL_CS_30", "TOTAL_GOLD_20", "TOTAL_GOLD_30", "CS_20", "CS_30", "JGL_20", "JGL_30"] +\
    ['l_ecart_cs', 'l_ecart_gold', 'l_ecart_gold_min_durant_game', 'l_ecart_gold_max_durant_game', 'l_kda', 'l_cs', 'l_cs_max_avantage', 'l_level_max_avantage', 'l_ecart_gold_team', 'l_ecart_kills_team', 'l_temps_avant_premiere_mort',
                      'l_ecart_kills', 'l_ecart_deaths', 'l_ecart_assists', 'l_ecart_dmg', 'l_allie_feeder', 'l_temps_vivant', 'l_time', 'l_solokills'] 

    liste_records.sort()

    liste_records = [i for i in liste_records if record_id in i]

    return liste_records[:25]