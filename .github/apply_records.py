from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one occurrence, found {count}: {old[:80]!r}")
    file_path.write_text(text.replace(old, new, 1), encoding="utf-8")


def replace_count(path: str, old: str, new: str, expected: int) -> None:
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != expected:
        raise RuntimeError(f"{path}: expected {expected} occurrences, found {count}: {old[:80]!r}")
    file_path.write_text(text.replace(old, new), encoding="utf-8")


# ---------------------------------------------------------------------------
# Historical record loading and record pages
# ---------------------------------------------------------------------------
replace_once(
    "cogs/recordslol.py",
    """            # Farming
            'cs', 'cs_jungle', 'cs_min', 'cs_dix_min', 'jgl_dix_min', 'cs_max_avantage',
            # Tank/Heal
            'dmg_tank', 'dmg_reduit', 'tankratio', 'shield', 'heal_total', 'heal_allies',
            # Gold
            'gold', 'gold_min', 'gold_share',
            # Objectifs
            'baron', 'drake', 'early_drake', 'early_baron', 'dmg_tower',
            'tower', 'inhib', 'fourth_dragon', 'first_elder', 'first_horde',
            # Timing
            'time', 'temps_dead', 'temps_vivant', 'temps_avant_premiere_mort',
            # Combat
            'skillshot_dodged', 'skillshot_hit', 'trade_efficience', 'temps_cc',
            'spells_used', 'buffs_voles', 'immobilisation', 'first_blood',
""",
    """            # Farming
            'cs', 'cs_jungle', 'cs_min', 'cs_dix_min', 'jgl_dix_min', 'cs_max_avantage',
            'cs_diff_15',
            # Tank/Heal
            'dmg_tank', 'dmg_reduit', 'tankratio', 'shield', 'heal_total', 'heal_allies',
            # Gold
            'gold', 'gold_min', 'gold_share', 'gold_diff_15', 'gold_avec_kills',
            'biggest_comeback', 'biggest_throw',
            # Objectifs
            'baron', 'drake', 'early_drake', 'early_baron', 'dmg_tower',
            'tower', 'inhib', 'fourth_dragon', 'first_elder', 'first_horde',
            'objective_damage', 'objectives_participated', 'turrets_killed',
            'turret_plates_taken',
            # Timing
            'time', 'temps_dead', 'temps_vivant', 'temps_avant_premiere_mort',
            # Combat
            'skillshot_dodged', 'skillshot_hit', 'trade_efficience', 'temps_cc',
            'spells_used', 'buffs_voles', 'immobilisation', 'first_blood',
            'shutdown_bounty', 'solokilled', 'kills_avec_jgl_early',
            'deaths_with_jgl_early',
""",
)

replace_once(
    "cogs/recordslol.py",
    """        'data_timeline_palier."TURRET_PLATE_DESTROYED_10"', 'data_timeline_palier."TURRET_PLATE_DESTROYED_20"', 'data_timeline_palier."TURRET_PLATE_DESTROYED_30"',
""",
    """        'data_timeline_palier."TURRET_PLATE_DESTROYED_10"', 'data_timeline_palier."TURRET_PLATE_DESTROYED_20"',
        'data_timeline_palier."TURRET_PLATE_DESTROYED_30" AS turret_plates_taken',
""",
)

replace_once(
    "cogs/recordslol.py",
    """        'records_loser."l_temps_vivant"', 'records_loser."l_time"', 'records_loser."l_solokills"',
    ]
""",
    """        'records_loser."l_temps_vivant"', 'records_loser."l_time"', 'records_loser."l_solokills"',
        'match_player_scoring_data.gold_diff_15', 'match_player_scoring_data.cs_diff_15',
        'match_player_scoring_data.objective_damage',
        'match_player_scoring_data.objectives_participated',
        'match_player_scoring_data.turrets_killed',
    ]
""",
)

replace_once(
    "cogs/recordslol.py",
    """        LEFT JOIN data_timeline_palier ON matchs.joueur = data_timeline_palier.riot_id AND matchs.match_id = data_timeline_palier.match_id
        LEFT JOIN records_loser ON matchs.joueur = records_loser.joueur AND matchs.match_id = records_loser.match_id
""",
    """        LEFT JOIN data_timeline_palier ON matchs.joueur = data_timeline_palier.riot_id AND matchs.match_id = data_timeline_palier.match_id
        LEFT JOIN match_player_scoring_data ON matchs.match_id = match_player_scoring_data.match_id
            AND matchs.id_participant = match_player_scoring_data.player_index
        LEFT JOIN records_loser ON matchs.joueur = records_loser.joueur AND matchs.match_id = records_loser.match_id
""",
)

replace_once(
    "cogs/recordslol.py",
    """    fichier = lire_bdd_perso(base_query, index_col='id').transpose()

    # Filtres pandas (plus rapides que côté SQL pour des conditions simples sur des données déjà chargées)
""",
    """    fichier = lire_bdd_perso(base_query, index_col='id').transpose()

    # Records narratifs dérivés de l'écart de gold de l'équipe pendant la partie.
    if 'victoire' in fichier.columns:
        victoire_values = fichier['victoire'].astype(str).str.lower()

        if 'ecart_gold_min_durant_game' in fichier.columns:
            min_gold_diff = pd.to_numeric(
                fichier['ecart_gold_min_durant_game'], errors='coerce'
            )
            fichier['biggest_comeback'] = np.where(
                victoire_values.isin(['true', '1', 't']) & (min_gold_diff < 0),
                min_gold_diff.abs(),
                np.nan
            )

        if 'ecart_gold_max_durant_game' in fichier.columns:
            max_gold_diff = pd.to_numeric(
                fichier['ecart_gold_max_durant_game'], errors='coerce'
            )
            fichier['biggest_throw'] = np.where(
                victoire_values.isin(['false', '0', 'f']) & (max_gold_diff > 0),
                max_gold_diff,
                np.nan
            )

    # Filtres pandas (plus rapides que côté SQL pour des conditions simples sur des données déjà chargées)
""",
)

replace_once(
    "cogs/recordslol.py",
    """            'farming': ['cs', 'cs_jungle', 'cs_min', 'cs_dix_min', 'jgl_dix_min', 'cs_max_avantage'],
            'tank_heal': ['dmg_reduit', 'dmg_tank', 'tankratio', 'shield', 'heal_total', 'heal_allies'],
            'objectif': ['baron', 'drake', 'early_drake', 'early_baron', 'dmg_tower', 'fourth_dragon', 'first_elder', 'first_horde', 'petales_sanglants', 'tower', 'inhib', 'early_atakhan', 'first_tower_time'],
            'divers': ['time', 'gold', 'gold_min', 'gold_share', 'ecart_gold_team', 'level_max_avantage', 'temps_dead', 'temps_vivant', 'allie_feeder', 'temps_avant_premiere_mort', 'snowball'],
            'fight': ['skillshot_dodged', 'skillshot_hit', 'skillshots_dodge_min', 'skillshots_hit_min', 'trade_efficience', 'temps_cc', 'spells_used', 'buffs_voles', 'immobilisation', 'temps_cc_inflige', 'first_blood'],
""",
    """            'farming': ['cs', 'cs_jungle', 'cs_min', 'cs_dix_min', 'jgl_dix_min', 'cs_max_avantage', 'cs_diff_15'],
            'tank_heal': ['dmg_reduit', 'dmg_tank', 'tankratio', 'shield', 'heal_total', 'heal_allies'],
            'objectif': ['baron', 'drake', 'early_drake', 'early_baron', 'dmg_tower', 'fourth_dragon', 'first_elder', 'first_horde', 'petales_sanglants', 'tower', 'inhib', 'early_atakhan', 'first_tower_time', 'objective_damage', 'objectives_participated', 'turrets_killed', 'turret_plates_taken'],
            'divers': ['time', 'gold', 'gold_min', 'gold_share', 'ecart_gold_team', 'gold_diff_15', 'gold_avec_kills', 'biggest_comeback', 'biggest_throw', 'level_max_avantage', 'temps_dead', 'temps_vivant', 'allie_feeder', 'temps_avant_premiere_mort', 'snowball'],
            'fight': ['skillshot_dodged', 'skillshot_hit', 'skillshots_dodge_min', 'skillshots_hit_min', 'trade_efficience', 'temps_cc', 'spells_used', 'buffs_voles', 'immobilisation', 'temps_cc_inflige', 'first_blood', 'shutdown_bounty', 'solokilled', 'kills_avec_jgl_early', 'deaths_with_jgl_early'],
""",
)

replace_once(
    "cogs/recordslol.py",
    """            for item in ['cs_jungle', 'jgl_dix_min']:
                if item in fichier_farming:
                    fichier_farming.remove(item)

            for item in ['first_double', 'first_triple', 'first_quadra', 'first_penta']:
""",
    """            for item in ['cs_jungle', 'jgl_dix_min', 'cs_diff_15']:
                if item in fichier_farming:
                    fichier_farming.remove(item)

            for item in ['gold_diff_15', 'gold_avec_kills', 'biggest_comeback', 'biggest_throw']:
                if item in fichier_divers:
                    fichier_divers.remove(item)

            for item in ['shutdown_bounty', 'solokilled', 'kills_avec_jgl_early', 'deaths_with_jgl_early']:
                if item in fichier_fight:
                    fichier_fight.remove(item)

            for item in ['first_double', 'first_triple', 'first_quadra', 'first_penta']:
""",
)

replace_once(
    "cogs/recordslol.py",
    """            for stat in ['cs_jungle', 'jgl_dix_min']:
                if stat in fichier_farming:
                    fichier_farming.remove(stat)

            to_remove_timer = [
""",
    """            for stat in ['cs_jungle', 'jgl_dix_min', 'cs_diff_15']:
                if stat in fichier_farming:
                    fichier_farming.remove(stat)

            for stat in ['gold_diff_15', 'gold_avec_kills', 'biggest_comeback', 'biggest_throw']:
                if stat in fichier_divers:
                    fichier_divers.remove(stat)

            for stat in ['shutdown_bounty', 'solokilled', 'kills_avec_jgl_early', 'deaths_with_jgl_early']:
                if stat in fichier_fight:
                    fichier_fight.remove(stat)

            to_remove_timer = [
""",
)

# ---------------------------------------------------------------------------
# Live record checks
# ---------------------------------------------------------------------------
replace_once(
    "cogs/leagueoflegends.py",
    """                    'data_timeline_palier."WARD_PLACED_30"',
                ]
""",
    """                    'data_timeline_palier."WARD_PLACED_30"',
                    'data_timeline_palier."TURRET_PLATE_DESTROYED_30" AS turret_plates_taken',
                    'match_player_scoring_data.gold_diff_15',
                    'match_player_scoring_data.cs_diff_15',
                    'match_player_scoring_data.objective_damage',
                    'match_player_scoring_data.objectives_participated',
                    'match_player_scoring_data.turrets_killed',
                ]
""",
)

replace_once(
    "cogs/leagueoflegends.py",
    """                    LEFT JOIN data_timeline_palier
                        ON matchs.joueur = data_timeline_palier.riot_id
                        AND matchs.match_id = data_timeline_palier.match_id
                    WHERE mode = '{match_info.thisQ}'
""",
    """                    LEFT JOIN data_timeline_palier
                        ON matchs.joueur = data_timeline_palier.riot_id
                        AND matchs.match_id = data_timeline_palier.match_id
                    LEFT JOIN match_player_scoring_data
                        ON matchs.match_id = match_player_scoring_data.match_id
                        AND matchs.id_participant = match_player_scoring_data.player_index
                    WHERE mode = '{match_info.thisQ}'
""",
)

replace_once(
    "cogs/leagueoflegends.py",
    """                df = lire_bdd_perso(base_query, index_col='id').transpose()

                if 'champion' in df.columns:
""",
    """                df = lire_bdd_perso(base_query, index_col='id').transpose()

                if 'victoire' in df.columns:
                    victoire_values = df['victoire'].astype(str).str.lower()

                    if 'ecart_gold_min_durant_game' in df.columns:
                        min_gold_diff = pd.to_numeric(
                            df['ecart_gold_min_durant_game'], errors='coerce'
                        )
                        df['biggest_comeback'] = np.where(
                            victoire_values.isin(['true', '1', 't']) & (min_gold_diff < 0),
                            min_gold_diff.abs(),
                            np.nan
                        )

                    if 'ecart_gold_max_durant_game' in df.columns:
                        max_gold_diff = pd.to_numeric(
                            df['ecart_gold_max_durant_game'], errors='coerce'
                        )
                        df['biggest_throw'] = np.where(
                            victoire_values.isin(['false', '0', 'f']) & (max_gold_diff > 0),
                            max_gold_diff,
                            np.nan
                        )

                if 'champion' in df.columns:
""",
)

replace_once(
    "cogs/leagueoflegends.py",
    """            if sauvegarder and match_info.thisTime >= 10.0 and match_info.thisQ not in ['ARENA 2v2', 'SWARM']:
                await match_info.save_data()

            else:
""",
    """            if sauvegarder and match_info.thisTime >= 10.0 and match_info.thisQ not in ['ARENA 2v2', 'SWARM']:
                await match_info.save_data()

                # La timeline est analysée avant l'insertion de la ligne `matchs`.
                # On rejoue donc la mise à jour une fois la ligne effectivement créée.
                if (
                    match_info.thisQ in ['RANKED', 'FLEX', 'SWIFTPLAY']
                    and hasattr(match_info, 'val_min_ecart_gold')
                ):
                    match_info.persist_match_timeline_fields()

            else:
""",
)

replace_once(
    "cogs/leagueoflegends.py",
    """                    'skillshot_dodged': match_info.thisSkillshot_dodged,
                    'temps_cc': match_info.time_CC,
""",
    """                    'skillshot_dodged': match_info.thisSkillshot_dodged,
                    'skillshot_hit': match_info.thisSkillshot_hit,
                    'temps_cc': match_info.time_CC,
""",
)

replace_once(
    "cogs/leagueoflegends.py",
    """                # Paramètres spécifiques aux ranked
                if match_info.thisQ in ['RANKED', 'FLEX', 'SWIFTPLAY']:
""",
    """                tracked_metrics = None
                if (
                    hasattr(match_info, 'player_metrics_liste')
                    and 0 <= match_info.thisId < len(match_info.player_metrics_liste)
                ):
                    tracked_metrics = match_info.player_metrics_liste[match_info.thisId]

                # Paramètres spécifiques aux ranked
                if match_info.thisQ in ['RANKED', 'FLEX', 'SWIFTPLAY']:
""",
)

replace_once(
    "cogs/leagueoflegends.py",
    """                        'first_niveau_max': match_info.timestamp_niveau_max,
                        'first_blood': match_info.timestamp_first_blood,
                        'tower': match_info.thisTowerTeam,
""",
    """                        'first_niveau_max': match_info.timestamp_niveau_max,
                        'first_blood': match_info.timestamp_first_blood,
                        'early_atakhan': getattr(match_info, 'timestamp_first_atakhan', 999),
                        'gold_diff_15': getattr(tracked_metrics, 'gold_diff_15', 0),
                        'cs_diff_15': getattr(tracked_metrics, 'cs_diff_15', 0),
                        'objective_damage': getattr(tracked_metrics, 'objective_damage', 0),
                        'objectives_participated': getattr(tracked_metrics, 'objectives_participated', 0),
                        'turrets_killed': getattr(tracked_metrics, 'turrets_killed', 0),
                        'turret_plates_taken': getattr(match_info, 'thisTurretPlatesTaken', 0),
                        'shutdown_bounty': getattr(match_info, 'bounty_recupere', 0),
                        'gold_avec_kills': getattr(match_info, 'gold_with_kills', 0),
                        'solokilled': getattr(match_info, 'get_solokilled', 0),
                        'kills_avec_jgl_early': getattr(match_info, 'kills_with_jgl_early', 0),
                        'deaths_with_jgl_early': getattr(match_info, 'deaths_with_jgl_early', 0),
                        'biggest_comeback': (
                            abs(min(getattr(match_info, 'val_min_ecart_gold', 0), 0))
                            if match_info.thisWinBool else 0
                        ),
                        'biggest_throw': (
                            max(getattr(match_info, 'val_max_ecart_gold', 0), 0)
                            if not match_info.thisWinBool else 0
                        ),
                        'tower': match_info.thisTowerTeam,
""",
)

replace_count(
    "cogs/leagueoflegends.py",
    """                        'first_horde', 'first_double', 'first_triple', 'first_quadra',
""",
    """                        'first_horde', 'early_atakhan', 'first_double', 'first_triple', 'first_quadra',
""",
    expected=2,
)

# ---------------------------------------------------------------------------
# Timeline persistence and ward statistics
# ---------------------------------------------------------------------------
replace_once(
    "fonctions/match/timeline.py",
    """    async def _extract_gold_diff(self):
""",
    """    def persist_match_timeline_fields(self):
        \"\"\"Persiste dans `matchs` les valeurs calculées depuis la timeline.\"\"\"
        requete_perso_bdd(
            '''UPDATE matchs SET fourth_dragon = :fourth_dragon,
            first_elder = :first_elder,
            first_horde = :first_horde,
            first_double = :first_double,
            first_triple = :first_triple,
            first_quadra = :first_quadra,
            first_penta = :first_penta,
            first_niveau_max = :first_niveau_max,
            first_blood = :first_blood,
            early_atakhan = :first_atakhan,
            solokilled = :solokilled,
            gold_avec_kills = :gold_avec_kills,
            kills_avec_jgl_early = :kills_avec_jgl_early,
            deaths_with_jgl_early = :deaths_with_jgl_early,
            shutdown_bounty = :shutdown_bounty,
            ecart_gold_min_durant_game = :ecart_gold_min_durant_game,
            ecart_gold_max_durant_game = :ecart_gold_max_durant_game
            WHERE match_id = :match_id AND joueur = :joueur''',
            {
                'fourth_dragon': getattr(self, 'timestamp_fourth_dragon', 999),
                'first_elder': getattr(self, 'timestamp_first_elder', 999),
                'first_horde': getattr(self, 'timestamp_first_horde', 999),
                'first_double': getattr(self, 'timestamp_doublekill', 999),
                'first_triple': getattr(self, 'timestamp_triplekill', 999),
                'first_quadra': getattr(self, 'timestamp_quadrakill', 999),
                'first_penta': getattr(self, 'timestamp_pentakill', 999),
                'first_niveau_max': getattr(self, 'timestamp_niveau_max', 999),
                'first_blood': getattr(self, 'timestamp_first_blood', 999),
                'first_atakhan': getattr(self, 'timestamp_first_atakhan', 999),
                'solokilled': getattr(self, 'get_solokilled', 0),
                'gold_avec_kills': getattr(self, 'gold_with_kills', 0),
                'kills_avec_jgl_early': getattr(self, 'kills_with_jgl_early', 0),
                'deaths_with_jgl_early': getattr(self, 'deaths_with_jgl_early', 0),
                'shutdown_bounty': getattr(self, 'bounty_recupere', 0),
                'ecart_gold_min_durant_game': getattr(self, 'val_min_ecart_gold', 0),
                'ecart_gold_max_durant_game': getattr(self, 'val_max_ecart_gold', 0),
                'match_id': self.last_match,
                'joueur': self.id_compte
            }
        )

    async def _extract_gold_diff(self):
""",
)

replace_once(
    "fonctions/match/timeline.py",
    """        # Mise à jour de la BDD
        requete_perso_bdd(
            '''UPDATE matchs SET fourth_dragon = :fourth_dragon,
            first_elder = :first_elder,
            first_horde = :first_horde,
            first_double = :first_double,
            first_triple = :first_triple,
            first_quadra = :first_quadra,
            first_penta = :first_penta,
            first_niveau_max = :first_niveau_max,
            first_blood = :first_blood,
            early_atakhan = :first_atakhan,
            solokilled = :solokilled,
            gold_avec_kills = :gold_avec_kills,
            kills_avec_jgl_early = :kills_avec_jgl_early,
            deaths_with_jgl_early = :deaths_with_jgl_early,
            shutdown_bounty = :shutdown_bounty,
            ecart_gold_min_durant_game = :ecart_gold_min_durant_game,
            ecart_gold_max_durant_game = :ecart_gold_max_durant_game
            WHERE match_id = :match_id AND joueur = :joueur''',
            {
                'fourth_dragon': self.timestamp_fourth_dragon,
                'first_elder': self.timestamp_first_elder,
                'first_horde': self.timestamp_first_horde,
                'first_double': self.timestamp_doublekill,
                'first_triple': self.timestamp_triplekill,
                'first_quadra': self.timestamp_quadrakill,
                'first_penta': self.timestamp_pentakill,
                'first_niveau_max': self.timestamp_niveau_max,
                'first_blood': self.timestamp_first_blood,
                'first_atakhan': self.timestamp_first_atakhan,
                'solokilled': self.get_solokilled,
                'gold_avec_kills': self.gold_with_kills,
                'kills_avec_jgl_early': self.kills_with_jgl_early,
                'deaths_with_jgl_early': self.deaths_with_jgl_early,
                'shutdown_bounty': self.bounty_recupere,
                'ecart_gold_min_durant_game': self.val_min_ecart_gold,
                'ecart_gold_max_durant_game': self.val_max_ecart_gold,
                'match_id': self.last_match,
                'joueur': self.id_compte
            }
        )
""",
    """        # Mise à jour immédiate pour les matchs déjà présents (recalcul/backfill).
        # Pour un nouveau match, cette méthode est rejouée après `save_data()`.
        self.persist_match_timeline_fields()
""",
)

replace_once(
    "fonctions/match/timeline.py",
    """            setattr(self, f'WARD_PLACED_{time}', safe_get_first(self.df_time_pivot, f'WARD_KILL_{time}'))
""",
    """            setattr(self, f'WARD_PLACED_{time}', safe_get_first(self.df_time_pivot, f'WARD_PLACED_{time}'))
""",
)

# ---------------------------------------------------------------------------
# Record display emojis
# ---------------------------------------------------------------------------
replace_once(
    "utils/emoji.py",
    """    'deathsratio' : ':skull:',
    'solokillsratio' : ':crossed_swords:'
}
""",
    """    'deathsratio' : ':skull:',
    'solokillsratio' : ':crossed_swords:',
    'gold_diff_15' : ':euro:',
    'cs_diff_15' : ':ghost:',
    'objective_damage' : ':dart:',
    'objectives_participated' : ':trophy:',
    'turrets_killed' : ':tokyo_tower:',
    'turret_plates_taken' : ':tokyo_tower:',
    'shutdown_bounty' : ':moneybag:',
    'gold_avec_kills' : ':moneybag:',
    'solokilled' : ':skull:',
    'kills_avec_jgl_early' : ':crossed_swords:',
    'deaths_with_jgl_early' : ':skull:',
    'biggest_comeback' : ':chart_with_upwards_trend:',
    'biggest_throw' : ':chart_with_downwards_trend:'
}
""",
)

print("LoL record patch applied successfully")
