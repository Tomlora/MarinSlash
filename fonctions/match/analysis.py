"""
Classe matchlol - Partie 6: Analyse avancée (skirmishes, roam, clutch, etc.).
"""

import math
import numpy as np

from .utils import fix_temps


class AdvancedAnalysisMixin:
    """Mixin pour les analyses avancées du match."""

    async def perfect_farm_window(self, cs_min=10):
        """
        Calcule la plus longue période où le joueur maintient un CS/min > 10.
        
        Returns:
            int: Nombre de minutes consécutives avec farm parfait
        """
        if not self.data_timeline:
            return 0

        cs_per_minute = []

        for minute, frame in enumerate(self.data_timeline['info']['frames'][1:], 1):
            cs = (frame['participantFrames'][str(self.index_timeline)]['minionsKilled'] +
                  frame['participantFrames'][str(self.index_timeline)].get('jungleMinionsKilled', 0))
            cs_per_minute.append(cs)

        max_window = 0
        window = 0

        for i, cs in enumerate(cs_per_minute):
            rate = cs / (i + 1)
            if rate >= cs_min:
                window += 1
                max_window = max(max_window, window)
            else:
                window = 0

        return max_window

    async def reverse_sweep(self):
        """
        Vérifie si l'équipe était derrière à 15min mais gagne la partie.
        
        Returns:
            bool: True si comeback réalisé
        """
        participants = self.match_detail['info']['participants']
        team_id = self.teamId

        try:
            frame_15 = self.data_timeline['info']['frames'][15]
        except (IndexError, KeyError, TypeError):
            return False

        team_gold = sum([
            frame_15['participantFrames'][str(i + 1)]['totalGold']
            for i, p in enumerate(participants) if p['teamId'] == team_id
        ])
        opp_gold = sum([
            frame_15['participantFrames'][str(i + 1)]['totalGold']
            for i, p in enumerate(participants) if p['teamId'] != team_id
        ])

        my_team = [i + 1 for i, p in enumerate(participants) if p['teamId'] == team_id]
        opp_team = [i + 1 for i, p in enumerate(participants) if p['teamId'] != team_id]

        my_towers = frame_15['participantFrames'][str(my_team[0])].get('towerKills', 0)
        opp_towers = frame_15['participantFrames'][str(opp_team[0])].get('towerKills', 0)

        # Dragons à 15min
        drake_events = []
        for f in self.data_timeline['info']['frames'][:16]:
            for e in f.get('events', []):
                if e['type'] == 'ELITE_MONSTER_KILL' and e['monsterType'] == 'DRAGON':
                    drake_events.append(e)

        my_drakes = len([d for d in drake_events if participants[d['killerId'] - 1]['teamId'] == team_id])
        opp_drakes = len([d for d in drake_events if participants[d['killerId'] - 1]['teamId'] != team_id])

        behind = team_gold < opp_gold and my_towers < opp_towers and my_drakes < opp_drakes
        win = self.thisWinBool

        return behind and win

    async def deep_vision(self):
        """
        Compte le nombre de wards posées dans la moitié ennemie de la map.
        
        Returns:
            int: Nombre de deep wards
        """
        if not self.data_timeline:
            return 0

        team_id = self.teamId
        total_deep_wards = 0

        for frame in self.data_timeline['info']['frames']:
            for event in frame.get('events', []):
                if event['type'] == 'WARD_PLACED' and event.get('creatorId') == self.index_timeline:
                    x = event.get('position', {}).get('x', 0)
                    if (team_id == 100 and x > 7500) or (team_id == 200 and x < 7500):
                        total_deep_wards += 1

        return total_deep_wards

    async def fight_participation(self, min_fight_size=3, fight_radius=1200, fight_interval=10000):
        """
        Pourcentage de teamfights où le joueur a participé.
        
        Returns:
            float: Pourcentage de participation aux teamfights
        """
        if not self.data_timeline:
            return 0

        participants = self.match_detail['info']['participants']
        fights = []
        last_fight_time = 0

        for frame in self.data_timeline['info']['frames']:
            for event in frame.get('events', []):
                if event['type'] == 'CHAMPION_KILL':
                    time = event['timestamp']
                    if fights and abs(time - last_fight_time) < fight_interval:
                        fights[-1]['events'].append(event)
                    else:
                        fights.append({'events': [event]})
                    last_fight_time = time

        my_participation = 0
        total_fights = 0

        for fight in fights:
            involved = set()
            event_times = []
            fight_positions = []

            for ev in fight['events']:
                event_times.append(ev['timestamp'])
                if 'position' in ev:
                    fight_positions.append((ev['position']['x'], ev['position']['y']))
                involved.add(ev['killerId'])
                involved.add(ev['victimId'])
                if 'assistingParticipantIds' in ev:
                    involved.update(ev['assistingParticipantIds'])

            team_mapping = {p['participantId']: p['teamId'] for p in participants}
            involved = {pid for pid in involved if pid in team_mapping}

            if len(involved) < min_fight_size:
                continue

            total_fights += 1

            if self.index_timeline in involved:
                my_participation += 1
                continue

            # Participation par présence physique
            participated = False
            for fight_time, fight_pos in zip(event_times, fight_positions):
                closest_frame = min(
                    self.data_timeline['info']['frames'],
                    key=lambda f: abs(f['timestamp'] - fight_time)
                )
                pos = closest_frame['participantFrames'][str(self.index_timeline)].get('position', None)
                if pos:
                    dx = pos['x'] - fight_pos[0]
                    dy = pos['y'] - fight_pos[1]
                    dist = math.sqrt(dx * dx + dy * dy)
                    if dist <= fight_radius:
                        participated = True
                        break
            if participated:
                my_participation += 1

        return round(100 * my_participation / total_fights, 1) if total_fights else 0

    async def kills_from_behind(self):
        """
        Nombre de kills réalisés quand l'équipe était en retard de gold.
        
        Returns:
            int: Nombre de kills from behind
        """
        if not self.data_timeline:
            return 0

        team_id = self.teamId
        participants = self.match_detail['info']['participants']
        kills_behind = 0

        team_gold_frames = []
        for frame in self.data_timeline['info']['frames']:
            my_gold = sum([
                frame['participantFrames'][str(i + 1)]['totalGold']
                for i, p in enumerate(participants) if p['teamId'] == team_id
            ])
            opp_gold = sum([
                frame['participantFrames'][str(i + 1)]['totalGold']
                for i, p in enumerate(participants) if p['teamId'] != team_id
            ])
            team_gold_frames.append((my_gold, opp_gold, frame['timestamp']))

        for frame in self.data_timeline['info']['frames']:
            for event in frame.get('events', []):
                if event['type'] == 'CHAMPION_KILL' and event.get('killerId') == self.index_timeline:
                    times = [abs(event['timestamp'] - g[2]) for g in team_gold_frames]
                    idx = times.index(min(times))
                    my_gold, opp_gold, _ = team_gold_frames[idx]
                    if my_gold < opp_gold:
                        kills_behind += 1

        return kills_behind

    async def roam_score(self):
        """
        Nombre de roams réussis avant 15min.
        
        Returns:
            int: Score de roam
        """
        if not self.data_timeline:
            return 0

        participants = self.match_detail['info']['participants']
        my_lane = self.match_detail_participants.get('individualPosition', None)
        roams = 0

        for frame in self.data_timeline['info']['frames']:
            for event in frame.get('events', []):
                if event['timestamp'] > 900000:
                    continue
                if event['type'] == 'CHAMPION_KILL':
                    if (event.get('killerId') == self.index_timeline or
                            self.index_timeline in event.get('assistingParticipantIds', [])):
                        victim_id = event.get('victimId')
                        if victim_id:
                            victim = participants[victim_id - 1]
                            victim_lane = victim.get('individualPosition', None)
                            if my_lane and victim_lane and my_lane != victim_lane:
                                roams += 1

        return roams

    async def lane_pressure(self):
        """
        Pourcentage de temps passé sur sa lane entre 3 et 15 min.
        
        Returns:
            float: Pourcentage de lane pressure
        """
        if not self.data_timeline:
            return 0

        my_lane = self.match_detail_participants.get('individualPosition', None)
        lane_zones = {
            'TOP': lambda x, y: x < 4000 and y > 9500,
            'MID': lambda x, y: 5200 < x < 11800 and 5200 < y < 11800,
            'BOTTOM': lambda x, y: x > 11000 and y < 3300,
        }

        total_frames = 0
        on_lane_frames = 0

        for i, frame in enumerate(self.data_timeline['info']['frames']):
            time = frame['timestamp']
            if 180000 < time < 900000 and str(self.index_timeline) in frame['participantFrames']:
                pos = frame['participantFrames'][str(self.index_timeline)].get('position', None)
                if pos and my_lane in lane_zones:
                    total_frames += 1
                    if lane_zones[my_lane](pos['x'], pos['y']):
                        on_lane_frames += 1

        return round(100 * on_lane_frames / total_frames, 1) if total_frames else 0

    async def first_to_die(self):
        """
        Vérifie si le joueur est le premier à mourir dans la partie.
        
        Returns:
            bool: True si premier mort
        """
        if not self.data_timeline:
            return False

        deaths = []
        for frame in self.data_timeline['info']['frames']:
            for event in frame.get('events', []):
                if event['type'] == 'CHAMPION_KILL':
                    deaths.append((event['timestamp'], event['victimId']))

        if not deaths:
            return False

        deaths.sort()
        return deaths[0][1] == self.index_timeline

    async def turning_point_minute(self):
        """
        Minute où l'équipe est passée devant au gold.
        
        Returns:
            int or None: Minute du turning point
        """
        participants = self.match_detail['info']['participants']
        team_id = self.teamId
        gold_diff = []

        for i, frame in enumerate(self.data_timeline['info']['frames']):
            my_gold = sum([
                frame['participantFrames'][str(j + 1)]['totalGold']
                for j, p in enumerate(participants) if p['teamId'] == team_id
            ])
            opp_gold = sum([
                frame['participantFrames'][str(j + 1)]['totalGold']
                for j, p in enumerate(participants) if p['teamId'] != team_id
            ])
            gold_diff.append(my_gold - opp_gold)

        for i in range(1, len(gold_diff)):
            if gold_diff[i - 1] < 0 and gold_diff[i] >= 0:
                return i

        return None

    async def worst_death(self):
        """
        Trouve la mort qui a coûté le plus d'objectifs.
        
        Returns:
            tuple or None: (minute, impact) de la pire mort
        """
        if not self.data_timeline:
            return None

        deaths = []
        for frame in self.data_timeline['info']['frames']:
            for event in frame.get('events', []):
                if event['type'] == 'CHAMPION_KILL' and event.get('victimId') == self.index_timeline:
                    deaths.append(event['timestamp'])

        worst_impact = 0
        worst_death_time = None

        for death in deaths:
            impact = 0
            for frame in self.data_timeline['info']['frames']:
                for event in frame.get('events', []):
                    if death < event['timestamp'] < death + 40000:
                        if event['type'] == 'ELITE_MONSTER_KILL' and event['monsterType'] == 'BARON_NASHOR':
                            impact += 5
                        if event['type'] == 'BUILDING_KILL' and event.get('buildingType') == 'TOWER_BUILDING':
                            impact += 2
            if impact > worst_impact:
                worst_impact = impact
                worst_death_time = death

        if worst_death_time:
            return worst_death_time // 60000, worst_impact
        return None

    async def detect_2v2_skirmishes(self, window=0.2):
        """
        Détecte les skirmishes 2v2 dans le match.
        
        Returns:
            list: Liste des skirmishes détectés
        """
        df = self.df_events.copy()
        df['timestamp'] = np.round(df['timestamp'] / 60000, 2)

        df_kill = df[df['type'] == 'CHAMPION_KILL'].copy()
        if df_kill.empty:
            return []

        participants = self.match_detail['info']['participants']
        team_mapping = {p['participantId']: p['teamId'] for p in participants}

        skirmishes = []
        visited = set()

        for idx, row in df_kill.iterrows():
            t = row['timestamp']
            window_kills = df_kill[
                (df_kill['timestamp'] >= t - window) & (df_kill['timestamp'] <= t + window)
            ]
            kills_idx_tuple = tuple(sorted(window_kills.index))

            if kills_idx_tuple in visited or len(window_kills) < 2:
                continue
            visited.add(kills_idx_tuple)

            involved = set()
            for _, kill in window_kills.iterrows():
                involved.add(kill['killerId'])
                involved.add(kill['victimId'])
                if 'assistingParticipantIds' in kill and isinstance(kill['assistingParticipantIds'], list):
                    involved.update(kill['assistingParticipantIds'])

            involved = {pid for pid in involved if pid in team_mapping}

            if len(involved) == 4:
                teams = [team_mapping[pid] for pid in involved]
                if teams.count(100) == 2 and teams.count(200) == 2:
                    kills_100 = sum(team_mapping[kill['killerId']] == 100 for _, kill in window_kills.iterrows())
                    kills_200 = sum(team_mapping[kill['killerId']] == 200 for _, kill in window_kills.iterrows())

                    if kills_100 > 0 or kills_200 > 0:
                        winner = None
                        if kills_100 > kills_200:
                            winner = 100
                        elif kills_200 > kills_100:
                            winner = 200

                        skirmishes.append({
                            "timestamp": int(t),
                            "joueurs_100": [self.thisChampNameListe[int(pid - 1)] for pid in involved if team_mapping[pid] == 100],
                            "joueurs_200": [self.thisChampNameListe[int(pid - 1)] for pid in involved if team_mapping[pid] == 200],
                            "kills_100": kills_100,
                            "kills_200": kills_200,
                            "winner": winner
                        })

        return skirmishes

    async def detect_2v3_skirmishes(self, window=0.2):
        """
        Détecte les skirmishes 2v3 dans le match.
        
        Returns:
            list: Liste des skirmishes 2v3 détectés
        """
        df = self.df_events.copy()
        df['timestamp'] = np.round(df['timestamp'] / 60000, 2)

        df_kill = df[df['type'] == 'CHAMPION_KILL'].copy()
        if df_kill.empty:
            return []

        participants = self.match_detail['info']['participants']
        team_mapping = {p['participantId']: p['teamId'] for p in participants}

        skirmishes = []
        visited = set()

        for idx, row in df_kill.iterrows():
            t = row['timestamp']
            window_kills = df_kill[
                (df_kill['timestamp'] >= t - window) & (df_kill['timestamp'] <= t + window)
            ]
            kills_idx_tuple = tuple(sorted(window_kills.index))

            if kills_idx_tuple in visited or len(window_kills) < 2:
                continue
            visited.add(kills_idx_tuple)

            involved = set()
            for _, kill in window_kills.iterrows():
                involved.add(kill['killerId'])
                involved.add(kill['victimId'])
                if 'assistingParticipantIds' in kill and isinstance(kill['assistingParticipantIds'], list):
                    involved.update(kill['assistingParticipantIds'])

            involved = {pid for pid in involved if pid in team_mapping}

            team_100 = [pid for pid in involved if team_mapping[pid] == 100]
            team_200 = [pid for pid in involved if team_mapping[pid] == 200]
            sizes = (len(team_100), len(team_200))

            if sorted(sizes) == [2, 3]:
                kills_100 = sum(team_mapping[kill['killerId']] == 100 for _, kill in window_kills.iterrows())
                kills_200 = sum(team_mapping[kill['killerId']] == 200 for _, kill in window_kills.iterrows())

                if kills_100 > 0 or kills_200 > 0:
                    winner = None
                    if kills_100 > kills_200:
                        winner = 100
                    elif kills_200 > kills_100:
                        winner = 200

                    skirmishes.append({
                        "timestamp": int(t),
                        "joueurs_100": [self.thisChampNameListe[int(pid - 1)] for pid in team_100],
                        "joueurs_200": [self.thisChampNameListe[int(pid - 1)] for pid in team_200],
                        "kills_100": kills_100,
                        "kills_200": kills_200,
                        "winner": winner
                    })

        return skirmishes
