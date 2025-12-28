"""
Classe matchlol - Partie 5: Gestion de la timeline.
"""

import numpy as np
import pandas as pd
import sqlalchemy.exc

from fonctions.gestion_bdd import requete_perso_bdd, lire_bdd_perso, sauvegarde_bdd
from .utils import fix_temps, load_timeline


class TimelineMixin:
    """Mixin pour la gestion de la timeline."""

    async def save_timeline(self):
        """Sauvegarde les données de timeline."""
        def unpack_dict_championStats(row):
            return pd.Series(row['championStats'])

        def unpack_dict_damageStats(row):
            return pd.Series(row['damageStats'])

        self.df_timeline_load, self.minute = load_timeline(self.data_timeline)

        self.df_timeline_joueur = self.df_timeline_load[
            self.df_timeline_load['riot_id'] == self.index_timeline
        ]

        self.df_timeline_position = self.df_timeline_joueur[[
            'position', 'timestamp', 'totalGold', 'xp', 'jungleMinionsKilled',
            'currentGold', 'level', 'minionsKilled'
        ]]

        self.df_timeline_position['total_cs'] = (
            self.df_timeline_position['minionsKilled'] +
            self.df_timeline_position['jungleMinionsKilled']
        )

        self.df_timeline_position['riot_id'] = self.id_compte
        self.df_timeline_position['match_id'] = self.last_match

        self.df_timeline_position['position_x'] = self.df_timeline_position['position'].apply(
            lambda x: x['x']
        )
        self.df_timeline_position['position_y'] = self.df_timeline_position['position'].apply(
            lambda x: x['y']
        )
        self.df_timeline_position.drop('position', axis=1, inplace=True)

        self.df_timeline_stats = self.df_timeline_joueur.apply(unpack_dict_championStats, axis=1)
        self.df_timeline_dmg = self.df_timeline_joueur.apply(unpack_dict_damageStats, axis=1)

        self.df_timeline_position = pd.concat([
            self.df_timeline_position,
            self.df_timeline_stats,
            self.df_timeline_dmg
        ], axis=1)

        # Stats max de la timeline
        self.max_abilityHaste = self.df_timeline_position['abilityHaste'].max()
        self.max_ap = self.df_timeline_position['abilityPower'].max()
        self.max_armor = self.df_timeline_position['armor'].max()
        self.max_ad = self.df_timeline_position['attackDamage'].max()
        self.currentgold = self.df_timeline_position['currentGold'].max()
        self.max_hp = self.df_timeline_position['healthMax'].max()
        self.max_mr = self.df_timeline_position['magicResist'].max()
        self.movement_speed = self.df_timeline_position['movementSpeed'].max()

        def get_value(df, timestamp, column):
            try:
                return df.loc[df['timestamp'] == timestamp, column].values[0]
            except:
                return 0

        # Stats à des moments clés
        self.total_cs_20 = get_value(self.df_timeline_position, 20, 'total_cs')
        self.total_cs_30 = get_value(self.df_timeline_position, 30, 'total_cs')
        self.total_gold_20 = get_value(self.df_timeline_position, 20, 'totalGold')
        self.total_gold_30 = get_value(self.df_timeline_position, 30, 'totalGold')
        self.minions_20 = get_value(self.df_timeline_position, 20, 'minionsKilled')
        self.minions_30 = get_value(self.df_timeline_position, 30, 'minionsKilled')
        self.jgl_killed_20 = get_value(self.df_timeline_position, 20, 'jungleMinionsKilled')
        self.jgl_killed_30 = get_value(self.df_timeline_position, 30, 'jungleMinionsKilled')

        self.totalDamageDone_10 = get_value(self.df_timeline_position, 10, 'totalDamageDoneToChampions')
        self.totalDamageDone_20 = get_value(self.df_timeline_position, 20, 'totalDamageDoneToChampions')
        self.totalDamageDone_30 = get_value(self.df_timeline_position, 30, 'totalDamageDoneToChampions')

        self.totalDamageTaken_10 = get_value(self.df_timeline_position, 10, 'totalDamageTaken')
        self.totalDamageTaken_20 = get_value(self.df_timeline_position, 20, 'totalDamageTaken')
        self.totalDamageTaken_30 = get_value(self.df_timeline_position, 30, 'totalDamageTaken')

        self.trade_efficience_10 = round(
            self.totalDamageDone_10 / (self.totalDamageTaken_10 + 1) * 100, 2
        )
        self.trade_efficience_20 = round(
            self.totalDamageDone_20 / (self.totalDamageTaken_20 + 1) * 100, 2
        )
        self.trade_efficience_30 = round(
            self.totalDamageDone_30 / (self.totalDamageTaken_30 + 1) * 100, 2
        )

        try:
            sauvegarde_bdd(
                self.df_timeline_position,
                'data_timeline',
                methode_save='append',
                index=False
            )
        except sqlalchemy.exc.IntegrityError:
            pass

    async def save_timeline_event(self):
        """Sauvegarde les événements de la timeline."""
        self.df_events = pd.DataFrame(self.data_timeline['info']['frames'][1]['events'])

        self.minute = len(self.data_timeline['info']['frames']) - 1

        for i in range(1, self.minute):
            df_timeline2 = pd.DataFrame(
                self.data_timeline['info']['frames'][i]['events']
            )
            self.df_events = self.df_events.append(df_timeline2)

        # Filtrer les événements du joueur
        self.df_events_joueur = self.df_events[
            (self.df_events['participantId'] == self.index_timeline) |
            (self.df_events['creatorId'] == self.index_timeline) |
            (self.df_events['killerId'] == self.index_timeline) |
            (self.df_events['victimId'] == self.index_timeline) |
            self.df_events['assistingParticipantIds'].apply(
                lambda x: isinstance(x, list) and self.index_timeline in x
            )
        ]

        self.df_events_team = self.df_events[
            (self.df_events['teamId'] == self.teamId) |
            (self.df_events['killerTeamId'] == self.teamId)
        ]

        def format_df_events(df):
            df['riot_id'] = self.id_compte
            df['match_id'] = self.last_match

            df['position_x'] = df['position'].apply(lambda x: x['x'] if isinstance(x, dict) else 0)
            df['position_y'] = df['position'].apply(lambda x: x['y'] if isinstance(x, dict) else 0)
            df.drop('position', axis=1, inplace=True)

            df.drop(['victimDamageDealt', 'victimDamageReceived', 'participantId', 'creatorId'],
                    axis=1, inplace=True, errors='ignore')

            if 'actualStartTime' in df.columns:
                df.drop(['actualStartTime'], axis=1, inplace=True)
            if 'name' in df.columns:
                df.drop(['name'], axis=1, inplace=True)

            df.reset_index(inplace=True, drop=True)

            df.loc[(df['type'] == 'CHAMPION_KILL') &
                   (df['victimId'] == self.index_timeline), 'type'] = 'DEATHS'

            df['timestamp'] = np.round(df['timestamp'] / 60000, 2)
            df['timestamp'] = df['timestamp'].apply(fix_temps)

            df['wardType'] = df['wardType'].map({
                'YELLOW_TRINKET': 'Trinket jaune',
                'UNDEFINED': 'Balise Zombie',
                'CONTROL_WARD': 'Pink',
                'SIGHT_WARD': 'Ward support',
                'BLUE_TRINKET': 'Trinket bleu'
            })

            return df

        self.df_events_joueur = format_df_events(self.df_events_joueur)
        self.df_events_team = format_df_events(self.df_events_team)

        if 'monsterSubType' not in self.df_events_team.columns:
            self.df_events_team['monsterSubType'] = ''

        # Extraction des timestamps importants
        await self._extract_important_timestamps()
        await self._extract_gold_diff()
        await self._extract_timeline_stats()

    async def _extract_important_timestamps(self):
        """Extrait les timestamps importants des événements."""
        def timestamp_killmulti(df):
            return 999 if df.empty else df['timestamp'].min()

        # Dragons
        self.df_events_monster_kill = self.df_events_team[
            self.df_events_team['type'] == 'ELITE_MONSTER_KILL'
        ][['type', 'timestamp', 'monsterType', 'monsterSubType']]
        self.df_events_dragon = self.df_events_monster_kill[
            self.df_events_monster_kill['monsterType'] == 'DRAGON'
        ]

        # 4ème dragon (soul)
        try:
            index_fourth_dragon = self.df_events_dragon.index[3]
            self.timestamp_fourth_dragon = self.df_events_dragon.loc[index_fourth_dragon, 'timestamp']
        except IndexError:
            self.timestamp_fourth_dragon = 999.0

        if self.thisDragonTeam < 4:
            self.timestamp_fourth_dragon = 999.0

        # Elder
        self.df_events_elder = self.df_events_team[
            self.df_events_team['monsterSubType'] == 'ELDER_DRAGON'
        ]
        self.timestamp_first_elder = 999.0 if self.df_events_elder.empty else self.df_events_elder['timestamp'].min()

        # Horde
        self.df_events_horde = self.df_events_team[self.df_events_team['monsterType'] == 'HORDE']
        self.timestamp_first_horde = 999.0 if self.df_events_horde.empty else self.df_events_horde['timestamp'].min()

        # Atakhan
        self.df_events_atakhan = self.df_events_team[self.df_events_team['monsterType'] == 'ATAKHAN']
        self.timestamp_first_atakhan = 999.0 if self.df_events_atakhan.empty else self.df_events_atakhan['timestamp'].min()

        # Autres événements
        self.df_niveau_max = self.df_events_joueur[self.df_events_joueur['level'] == 18.0]
        self.df_first_blood = self.df_events_joueur[self.df_events_joueur['killType'] == 'KILL_FIRST_BLOOD']
        self.df_kills = self.df_events_joueur[
            self.df_events_joueur['type'].isin(['CHAMPION_KILL', 'CHAMPION_SPECIAL_KILL'])
        ]
        self.df_deaths = self.df_events_joueur[self.df_events_joueur['type'] == 'DEATHS']

        # Ganks early
        self.df_kills_with_jgl_early = self.df_events_joueur[
            (self.df_events_joueur['type'].isin(['CHAMPION_KILL', 'CHAMPION_SPECIAL_KILL'])) &
            (self.df_events_joueur['assistingParticipantIds'].apply(
                lambda x: isinstance(x, list) and (7 in x or 2 in x)
            )) &
            (self.df_events_joueur['timestamp'].between(2, 10))
        ]

        self.df_deaths_with_jgl_early = self.df_events_joueur[
            (self.df_events_joueur['type'].isin(['DEATHS'])) &
            (self.df_events_joueur['assistingParticipantIds'].apply(
                lambda x: isinstance(x, list) and (7 in x or 2 in x)
            )) &
            (self.df_events_joueur['timestamp'].between(2, 10))
        ]

        # Solo killed
        if not self.df_deaths.empty:
            self.df_deaths['nb_participants'] = self.df_deaths['assistingParticipantIds'].apply(
                lambda x: len(x) + 1 if isinstance(x, list) else 1
            )
            self.get_solokilled = self.df_deaths[self.df_deaths['nb_participants'] == 1].shape[0]
        else:
            self.get_solokilled = 0

        # Gold avec kills
        if not self.df_kills.empty:
            self.df_kills['nb_participants'] = self.df_kills['assistingParticipantIds'].apply(
                lambda x: len(x) + 1 if isinstance(x, list) else 1
            )
            self.df_kills_self = self.df_kills[self.df_kills['killerId'] == self.index_timeline]
            self.gold_with_kills = self.df_kills_self['bounty'].sum() + self.df_kills_self['shutdownBounty'].sum()
            self.bounty_recupere = self.df_kills_self['shutdownBounty'].sum()
        else:
            self.gold_with_kills = 0
            self.bounty_recupere = 0

        # Kills/deaths avec jungler
        if not self.df_kills_with_jgl_early.empty and self.thisPosition != 'JUNGLE':
            self.kills_with_jgl_early = self.df_kills_with_jgl_early.shape[0]
        else:
            self.kills_with_jgl_early = 0

        if not self.df_deaths_with_jgl_early.empty and self.thisPosition != 'JUNGLE':
            self.deaths_with_jgl_early = self.df_deaths_with_jgl_early.shape[0]
        else:
            self.deaths_with_jgl_early = 0

        self.timestamp_niveau_max = timestamp_killmulti(self.df_niveau_max)
        self.timestamp_first_blood = timestamp_killmulti(self.df_first_blood)

        # Multikills
        if 'multiKillLength' in self.df_events_joueur.columns:
            self.df_events_doublekills = self.df_events_joueur[self.df_events_joueur['multiKillLength'] == 2.0]
            self.df_events_triplekills = self.df_events_joueur[self.df_events_joueur['multiKillLength'] == 3.0]
            self.df_events_quadrakills = self.df_events_joueur[self.df_events_joueur['multiKillLength'] == 4.0]
            self.df_events_pentakills = self.df_events_joueur[self.df_events_joueur['multiKillLength'] == 5.0]

            self.timestamp_doublekill = timestamp_killmulti(self.df_events_doublekills)
            self.timestamp_triplekill = timestamp_killmulti(self.df_events_triplekills)
            self.timestamp_quadrakill = timestamp_killmulti(self.df_events_quadrakills)
            self.timestamp_pentakill = timestamp_killmulti(self.df_events_pentakills)
        else:
            self.timestamp_doublekill = 999
            self.timestamp_triplekill = 999
            self.timestamp_quadrakill = 999
            self.timestamp_pentakill = 999

    async def _extract_gold_diff(self):
        """Extrait les différences de gold pendant la partie."""
        participants = self.match_detail['info']['participants']

        if self.teamId == 100:
            team = ['Team alliée', 'Team adverse']
        elif self.teamId == 200:
            team = ['Team adverse', 'Team alliée']

        self.df_timeline_load['riot_id'] = self.df_timeline_load['participantId']
        self.df_timeline_load['team'] = np.where(
            self.df_timeline_load['riot_id'] <= 5, team[0], team[1]
        )

        self.df_timeline_load = self.df_timeline_load.groupby(
            ['team', 'timestamp'], as_index=False
        )['totalGold'].sum()

        self.df_timeline_adverse = self.df_timeline_load[
            self.df_timeline_load['team'] == 'Team adverse'
        ].reset_index(drop=True)
        self.df_timeline_alliee = self.df_timeline_load[
            self.df_timeline_load['team'] == 'Team alliée'
        ].reset_index(drop=True)

        self.df_timeline_diff = pd.DataFrame(columns=['timestamp', 'ecart'])
        self.df_timeline_diff['timestamp'] = self.df_timeline_load['timestamp']
        self.df_timeline_diff['ecart'] = (
            self.df_timeline_alliee['totalGold'] - self.df_timeline_adverse['totalGold']
        )

        self.df_timeline_diff.dropna(axis=0, inplace=True)

        self.val_min_ecart_gold = self.df_timeline_diff['ecart'].min()
        self.val_max_ecart_gold = self.df_timeline_diff['ecart'].max()

        self.df_timeline_diff['match_id'] = self.last_match
        self.df_timeline_diff['riot_id'] = self.id_compte
        self.df_timeline_diff['gold_adv'] = self.df_timeline_adverse['totalGold']
        self.df_timeline_diff['gold_allie'] = self.df_timeline_alliee['totalGold']

        # Mise à jour de la BDD
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

        # Sauvegarde des événements et timeline
        self._save_timeline_tables()

    def _save_timeline_tables(self):
        """Sauvegarde les tables de timeline."""
        df_exists = lire_bdd_perso(
            f'''SELECT match_id, riot_id FROM data_timeline_events WHERE 
            match_id = '{self.last_match}' AND riot_id = {self.id_compte}''',
            index_col=None
        )

        if df_exists.empty:
            try:
                sauvegarde_bdd(
                    self.df_events_joueur,
                    'data_timeline_events',
                    methode_save='append',
                    index=False
                )
            except sqlalchemy.exc.IntegrityError:
                pass

        df_exists = lire_bdd_perso(
            f'''SELECT match_id, riot_id FROM matchs_timestamp_gold WHERE
            match_id = '{self.last_match}' AND riot_id = {self.id_compte}''',
            index_col=None
        )

        if df_exists.empty:
            try:
                sauvegarde_bdd(
                    self.df_timeline_diff,
                    'matchs_timestamp_gold',
                    methode_save='append',
                    index=False
                )
            except sqlalchemy.exc.IntegrityError:
                pass

    async def _extract_timeline_stats(self):
        """Extrait les stats par palier de temps."""
        def filtre_timeline(time):
            df_filtre_timeline = self.df_events_joueur[self.df_events_joueur['timestamp'] <= time]

            df_filtre_timeline.loc[
                (df_filtre_timeline['type'] == 'CHAMPION_SPECIAL_KILL') &
                (df_filtre_timeline['killerId'] == self.index_timeline), 'type'
            ] = 'CHAMPION_KILL'

            df_filtre_timeline.loc[
                (df_filtre_timeline['type'] == 'CHAMPION_KILL') &
                (df_filtre_timeline['killerId'] != self.index_timeline), 'type'
            ] = 'ASSISTS'

            df_filtre_timeline.drop_duplicates(subset=['timestamp', 'killerId', 'type'], inplace=True)
            df_filtre_timeline = df_filtre_timeline[df_filtre_timeline['wardType'] != 'Balise Zombie']
            df_filtre_timeline = df_filtre_timeline.groupby(
                ['type', 'riot_id', 'match_id'], as_index=False
            ).count()

            df_filtre_timeline['type'] = df_filtre_timeline.apply(
                lambda x: x['type'] + '_' + str(time), axis=1
            )
            df_filtre_timeline.rename(columns={'timestamp': 'value'}, inplace=True)
            return df_filtre_timeline[['type', 'riot_id', 'match_id', 'value']]

        self.df_10min = filtre_timeline(10)
        self.df_20min = filtre_timeline(20)
        self.df_30min = filtre_timeline(30)

        # Ajout des stats supplémentaires
        for time, df, dmg, tank, trade in [
            (10, self.df_10min, self.totalDamageDone_10, self.totalDamageTaken_10, self.trade_efficience_10),
            (20, self.df_20min, self.totalDamageDone_20, self.totalDamageTaken_20, self.trade_efficience_20),
            (30, self.df_20min, self.totalDamageDone_30, self.totalDamageTaken_30, self.trade_efficience_30)
        ]:
            df.loc[len(df)] = [f'TOTAL_DMG_{time}', self.id_compte, self.last_match, dmg]
            df.loc[len(df)] = [f'TOTAL_DMG_TAKEN_{time}', self.id_compte, self.last_match, tank]
            df.loc[len(df)] = [f'TRADE_EFFICIENCE_{time}', self.id_compte, self.last_match, trade]

        # Stats 20/30 min
        for time, cs, gold, minions, jgl in [
            (20, self.total_cs_20, self.total_gold_20, self.minions_20, self.jgl_killed_20),
            (30, self.total_cs_30, self.total_gold_30, self.minions_30, self.jgl_killed_30)
        ]:
            self.df_20min.loc[len(self.df_20min)] = [f'TOTAL_CS_{time}', self.id_compte, self.last_match, cs]
            self.df_20min.loc[len(self.df_20min)] = [f'TOTAL_GOLD_{time}', self.id_compte, self.last_match, gold]
            self.df_20min.loc[len(self.df_20min)] = [f'CS_{time}', self.id_compte, self.last_match, minions]
            self.df_20min.loc[len(self.df_20min)] = [f'JGL_{time}', self.id_compte, self.last_match, jgl]

        self.df_time = pd.concat([self.df_10min, self.df_20min, self.df_30min])

        self.df_time_pivot = self.df_time.pivot_table(
            index=['riot_id', 'match_id'],
            columns='type',
            values='value',
            aggfunc='sum'
        ).reset_index()

        def safe_get_first(df, column):
            return int(df[column][0]) if column in df and not df[column].empty else 0

        # Extraction des valeurs
        for time in [10, 20, 30]:
            setattr(self, f'assists_{time}', safe_get_first(self.df_time_pivot, f'ASSISTS_{time}'))
            setattr(self, f'deaths_{time}', safe_get_first(self.df_time_pivot, f'DEATHS_{time}'))
            setattr(self, f'champion_kill_{time}', safe_get_first(self.df_time_pivot, f'CHAMPION_KILL_{time}'))
            setattr(self, f'level_{time}', safe_get_first(self.df_time_pivot, f'LEVEL_UP_{time}'))
            setattr(self, f'WARD_KILL_{time}', safe_get_first(self.df_time_pivot, f'WARD_KILL_{time}'))
            setattr(self, f'WARD_PLACED_{time}', safe_get_first(self.df_time_pivot, f'WARD_KILL_{time}'))

        self.jgl_20 = safe_get_first(self.df_time_pivot, 'JGL_20')
        self.jgl_30 = safe_get_first(self.df_time_pivot, 'JGL_30')

        # Sauvegarde
        df_exists = lire_bdd_perso(
            f'''SELECT match_id, riot_id FROM data_timeline_palier WHERE 
            match_id = '{self.last_match}' AND riot_id = {self.id_compte}''',
            index_col=None
        )

        if df_exists.empty:
            try:
                sauvegarde_bdd(
                    self.df_time_pivot,
                    'data_timeline_palier',
                    methode_save='append',
                    index=False
                )
            except sqlalchemy.exc.IntegrityError:
                pass

    async def _extract_early_game_data(self):
        """
        Extrait les données early game de la timeline.
        
        Doit être appelé après get_data_timeline().
        Remplit :
        - thisGoldAt15Liste, thisCsAt15Liste, thisXpAt15Liste
        - thisSoloKillsListe
        - firstBloodKillIndex, firstBloodAssistIndices
        - firstTowerKillIndex, firstTowerAssistIndices
        """
        if not hasattr(self, 'data_timeline') or self.data_timeline is None:
            return
        
        # Initialisation
        self.thisGoldAt15Liste = [0] * 10
        self.thisCsAt15Liste = [0] * 10
        self.thisXpAt15Liste = [0] * 10
        self.thisSoloKillsListe = [0] * 10
        self.firstBloodKillIndex = -1
        self.firstBloodAssistIndices = []
        self.firstTowerKillIndex = -1
        self.firstTowerAssistIndices = []
        
        frames = self.data_timeline.get('info', {}).get('frames', [])
        
        # Trouver la frame à 15 min (frame 15, car 1 frame = 1 min)
        frame_15 = None
        for frame in frames:
            timestamp_min = frame.get('timestamp', 0) // 60000
            if timestamp_min >= 15:
                frame_15 = frame
                break
        
        # Si game < 15 min, prendre la dernière frame disponible
        if frame_15 is None and frames:
            frame_15 = frames[-1]

        # Extraire les stats @15 min
        if frame_15:
            participant_frames = frame_15.get('participantFrames', {})
            for pid_str, pframe in participant_frames.items():
                try:
                    pid = int(pid_str) - 1  # API: 1-10, nous: 0-9
                    if 0 <= pid < 10:
                        self.thisGoldAt15Liste[pid] = pframe.get('totalGold', 0)
                        self.thisCsAt15Liste[pid] = pframe.get('minionsKilled', 0) + pframe.get('jungleMinionsKilled', 0)
                        self.thisXpAt15Liste[pid] = pframe.get('xp', 0)
                except (ValueError, IndexError) as e:
                    print('Erreur extraction stats @15 min:', e)
                    continue

        # Parcourir les events pour first blood, first tower, solo kills
        first_blood_found = False
        first_tower_found = False
        
        for frame in frames:
            events = frame.get('events', [])
            for event in events:
                event_type = event.get('type', '')
                
                # First Blood
                if event_type == 'CHAMPION_KILL' and not first_blood_found:
                    killer_id = event.get('killerId', 0) - 1
                    assists = [a - 1 for a in event.get('assistingParticipantIds', [])]
                    
                    if 0 <= killer_id < 10:
                        self.firstBloodKillIndex = killer_id
                        self.firstBloodAssistIndices = [a for a in assists if 0 <= a < 10]
                        first_blood_found = True
                
                # First Tower
                if event_type == 'BUILDING_KILL' and not first_tower_found:
                    building_type = event.get('buildingType', '')
                    if building_type == 'TOWER_BUILDING':
                        killer_id = event.get('killerId', 0) - 1
                        assists = [a - 1 for a in event.get('assistingParticipantIds', [])]
                        
                        if 0 <= killer_id < 10:
                            self.firstTowerKillIndex = killer_id
                            self.firstTowerAssistIndices = [a for a in assists if 0 <= a < 10]
                            first_tower_found = True
                
                # Solo Kills (kill sans assist)
                if event_type == 'CHAMPION_KILL':
                    killer_id = event.get('killerId', 0) - 1
                    assists = event.get('assistingParticipantIds', [])
                    
                    if 0 <= killer_id < 10 and len(assists) == 0:
                        self.thisSoloKillsListe[killer_id] += 1