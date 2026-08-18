from fonctions.gestion_bdd import lire_bdd_perso


RECORD_AUTOCOMPLETE_LABELS = {
    'tf_takedowns_survived': 'KILLS + ASSISTS EN TF SANS MOURIR',
    'tf_teamfight_outnumbered_wins': 'TF GAGNÉS EN INFÉRIORITÉ',
    'tf_teamfights': 'COMBATS 3V3+ DISPUTÉS',
    'tf_clutches_won': 'COMBATS EN INFÉRIORITÉ GAGNÉS',
    'tf_damage_window': 'DMG MAX EN TEAMFIGHT',
    'tf_physical_damage_window': 'DMG AD MAX EN TEAMFIGHT',
    'tf_magic_damage_window': 'DMG AP MAX EN TEAMFIGHT',
    'tf_true_damage_window': 'DMG TRUE MAX EN TEAMFIGHT',
    'tf_physical_dead_damage': 'DMG AD SUR CIBLES MORTES',
    'tf_magic_dead_damage': 'DMG AP SUR CIBLES MORTES',
    'tf_true_dead_damage': 'DMG TRUE SUR CIBLES MORTES',
    'tf_dead_damage_share_pct': '% DMG SUR CIBLES MORTES (5 ALLIÉS IMPLIQUÉS)',
    'tf_damage_window_share_pct': '% DMG ÉQUIPE EN TF (5 ALLIÉS IMPLIQUÉS)',
    'tf_duels': '1V1 DISPUTÉS',
    'tf_duels_won': '1V1 GAGNÉS',
    'tf_skirmishes': 'COMBATS 2V2 À 2V5 DISPUTÉS',
    'allie_feeder': "MORTS MAX D'UN COÉQUIPIER",
}


async def autocomplete_riotid(serverid, input_txt):
    df = lire_bdd_perso(
        f'''select riot_id from tracker where server_id = '{serverid}' ''',
        index_col=None
    ).T

    if df.empty:
        return []

    df['riot_id'] = df['riot_id'].str.lower()
    input_txt = input_txt.lower()
    df.sort_values(by='riot_id', inplace=True)

    liste_id = []
    for riot_id in df['riot_id'].unique().tolist():
        if input_txt in riot_id:
            liste_id.append({'name': riot_id, 'value': riot_id})

    return liste_id[:25]


async def autocomplete_record(record_id):
    liste_records = [
        'kills', 'assists', 'deaths', 'double', 'triple', 'quadra', 'penta',
        'solokills', 'team_kills', 'team_deaths', 'kda', 'kp', 'kills+assists',
        'serie_kills', 'first_double', 'first_triple', 'first_quadra', 'first_penta',
        'kills_min', 'deaths_min', 'assists_min', 'longue_serie_kills',
        'ecart_kills', 'ecart_deaths', 'ecart_assists', 'killsratio', 'deathsratio',
        'solokillsratio',
        'dmg', 'dmg_ad', 'dmg_ap', 'dmg_true', 'damageratio', 'dmg_min', 'dmg/gold',
        'crit_dmg', 'dmg_true_all', 'dmg_true_all_min', 'dmg_ad_all', 'dmg_ad_all_min',
        'dmg_ap_all', 'dmg_ap_all_min', 'dmg_all', 'dmg_all_min', 'ecart_dmg',
        'dmg_par_kills',
        'vision_score', 'vision_pink', 'vision_wards', 'vision_wards_killed',
        'vision_min', 'vision_avantage',
        'cs', 'cs_jungle', 'cs_min', 'cs_dix_min', 'jgl_dix_min', 'cs_max_avantage',
        'cs_diff_15',
        'dmg_reduit', 'dmg_tank', 'tankratio', 'shield', 'heal_total', 'heal_allies',
        'baron', 'drake', 'early_drake', 'early_baron', 'dmg_tower', 'fourth_dragon',
        'first_elder', 'first_horde', 'petales_sanglants', 'tower', 'inhib',
        'first_tower_time', 'objective_damage',
        'objectives_participated', 'turrets_killed', 'turret_plates_taken',
        'time', 'gold', 'gold_min', 'gold_share', 'ecart_gold_team', 'gold_diff_15',
        'gold_avec_kills', 'biggest_comeback', 'biggest_throw', 'level_max_avantage',
        'temps_dead', 'temps_vivant', 'allie_feeder', 'temps_avant_premiere_mort',
        'snowball', 'skillshot_dodged', 'skillshot_hit', 'temps_cc', 'spells_used',
        'buffs_voles', 'immobilisation', 'temps_cc_inflige', 'first_blood',
        'shutdown_bounty', 'solokilled', 'kills_avec_jgl_early', 'deaths_with_jgl_early',
        'abilityHaste', 'abilityPower', 'armor', 'attackDamage', 'currentGold',
        'healthMax', 'magicResist', 'movementSpeed', 'first_niveau_max',
        'ASSISTS_10', 'ASSISTS_20', 'ASSISTS_30', 'BUILDING_KILL_20',
        'BUILDING_KILL_30', 'CHAMPION_KILL_10', 'CHAMPION_KILL_20',
        'CHAMPION_KILL_30', 'DEATHS_10', 'DEATHS_20', 'DEATHS_30',
        'ELITE_MONSTER_KILL_10', 'ELITE_MONSTER_KILL_20', 'ELITE_MONSTER_KILL_30',
        'LEVEL_UP_10', 'LEVEL_UP_20', 'LEVEL_UP_30', 'TURRET_PLATE_DESTROYED_10',
        'WARD_KILL_10', 'WARD_KILL_20', 'WARD_KILL_30', 'WARD_PLACED_10',
        'WARD_PLACED_20', 'WARD_PLACED_30', 'TOTAL_CS_20', 'TOTAL_CS_30',
        'TOTAL_GOLD_20', 'TOTAL_GOLD_30', 'CS_20', 'CS_30', 'JGL_20', 'JGL_30',
        'l_ecart_cs', 'l_ecart_gold', 'l_ecart_gold_min_durant_game',
        'l_ecart_gold_max_durant_game', 'l_kda', 'l_cs', 'l_cs_max_avantage',
        'l_level_max_avantage', 'l_ecart_gold_team', 'l_ecart_kills_team',
        'l_temps_avant_premiere_mort', 'l_ecart_kills', 'l_ecart_deaths',
        'l_ecart_assists', 'l_ecart_dmg', 'l_allie_feeder', 'l_temps_vivant',
        'l_time', 'l_solokills',
        'tf_takedowns_survived', 'tf_teamfight_outnumbered_wins', 'tf_teamfights',
        'tf_clutches_won', 'tf_damage_window', 'tf_physical_damage_window',
        'tf_magic_damage_window', 'tf_true_damage_window', 'tf_physical_dead_damage',
        'tf_magic_dead_damage', 'tf_true_dead_damage', 'tf_dead_damage_share_pct',
        'tf_damage_window_share_pct', 'tf_duels', 'tf_duels_won', 'tf_skirmishes',
    ]

    search = (record_id or '').lower().strip()
    choices = []
    for record in sorted(liste_records, key=lambda item: RECORD_AUTOCOMPLETE_LABELS.get(item, item).lower()):
        label = RECORD_AUTOCOMPLETE_LABELS.get(record, record)
        if search in record.lower() or search in label.lower():
            choices.append({'name': label, 'value': record})

    return choices[:25]


async def autocomplete_theme_recap(input_txt):
    df = lire_bdd_perso('''select name from theme''', index_col=None).T

    if df.empty:
        return []

    df.sort_values(by='name', inplace=True)
    liste_id = []
    for name in df['name'].unique().tolist():
        if input_txt in name:
            liste_id.append({'name': name, 'value': name})

    return liste_id[:25]
