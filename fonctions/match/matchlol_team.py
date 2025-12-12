"""
Classe matchlol - Partie 3: Données d'équipe et comparaisons.
"""

import numpy as np
import pandas as pd
import aiohttp

from fonctions.gestion_bdd import lire_bdd_perso, requete_perso_bdd
from .riot_api import get_champion_masteries
from .masteries import get_masteries_old, get_stat_champion_by_player


class MatchLolTeamData:
    """Extension pour les données d'équipe."""

    async def _extract_team_data(self):
        """Extrait les données d'équipe."""
        participants = self.match_detail['info']['participants']
        teams = self.match_detail['info']['teams']

        # Listes par équipe
        self.allitems = []
        self.thisPseudoListe = []
        self.thisRiotIdListe = []
        self.thisRiotTagListe = []
        self.thisChampIdListe = []
        self.thisChampNameListe = []
        self.thisKillsListe = []
        self.thisDeathsListe = []
        self.thisAssistsListe = []
        self.thisGoldListe = []
        self.thisVisionListe = []
        self.thisMinionListe = []
        self.thisKDAListe = []
        self.thisKPListe = []
        self.thisDamageListe = []
        self.thisDamageRatioListe = []
        self.thisDamageTakenListe = []
        self.thisDamageTakenRatioListe = []
        self.thisDamageSelfMitigatedListe = []
        self.thisDamagePerMinuteListe = []
        self.thisMinionPerMinListe = []
        self.thisVisionPerMinListe = []
        self.thisTankPerMinListe = []
        self.thisLevelListe = []
        self.thisDoubleListe = []
        self.thisTripleListe = []
        self.thisQuadraListe = []
        self.thisPentaListe = []
        self.thisJungleMonsterKilledListe = []
        self.thisPositionListe = []
        self.thisPuuidListe = []
        self.thisPinkListe = []

        # Calcul des totaux d'équipe
        self.thisTeamKills = sum(p['kills'] for p in participants[:5])
        self.thisTeamKillsOp = sum(p['kills'] for p in participants[5:])
        self.thisGold_team1 = sum(p['goldEarned'] for p in participants[:5])
        self.thisGold_team2 = sum(p['goldEarned'] for p in participants[5:])
        self.thisDamage_team1 = sum(p['totalDamageDealtToChampions'] for p in participants[:5])
        self.thisDamage_team2 = sum(p['totalDamageDealtToChampions'] for p in participants[5:])
        self.thisTank_team1 = sum(p['totalDamageTaken'] for p in participants[:5])
        self.thisTank_team2 = sum(p['totalDamageTaken'] for p in participants[5:])

        for i, participant in enumerate(participants):
            # Items
            items = [participant.get(f'item{j}', 0) for j in range(6)] #7 c'est la ward
            self.allitems.append(items)

            # Pseudo et Riot ID
            self.thisPseudoListe.append(participant.get('summonerName', ''))
            self.thisRiotIdListe.append(participant.get('riotIdGameName', ''))
            self.thisRiotTagListe.append(participant.get('riotIdTagline', ''))
            self.thisPuuidListe.append(participant.get('puuid', ''))

            # Champion
            self.thisChampIdListe.append(participant.get('championId', 0))
            self.thisChampNameListe.append(participant.get('championName', ''))

            # Stats principales
            self.thisKillsListe.append(participant.get('kills', 0))
            self.thisDeathsListe.append(participant.get('deaths', 0))
            self.thisAssistsListe.append(participant.get('assists', 0))
            self.thisGoldListe.append(participant.get('goldEarned', 0))
            self.thisVisionListe.append(participant.get('visionScore', 0))
            self.thisMinionListe.append(participant.get('totalMinionsKilled', 0))
            self.thisJungleMonsterKilledListe.append(participant.get('neutralMinionsKilled', 0))
            self.thisLevelListe.append(participant.get('champLevel', 0))
            self.thisPositionListe.append(participant.get('teamPosition', ''))
            self.thisPinkListe.append(participant.get('visionWardsBoughtInGame', 0))
            

            # Multikills
            self.thisDoubleListe.append(participant.get('doubleKills', 0))
            self.thisTripleListe.append(participant.get('tripleKills', 0))
            self.thisQuadraListe.append(participant.get('quadraKills', 0))
            self.thisPentaListe.append(participant.get('pentaKills', 0))

            # Dégâts
            damage = participant.get('totalDamageDealtToChampions', 0)
            damage_taken = participant.get('totalDamageTaken', 0)
            self.thisDamageListe.append(damage)
            self.thisDamageTakenListe.append(damage_taken)
            self.thisDamageSelfMitigatedListe.append(participant.get('damageSelfMitigated', 0))

            # Ratios équipe
            team_damage = self.thisDamage_team1 if i < 5 else self.thisDamage_team2
            team_tank = self.thisTank_team1 if i < 5 else self.thisTank_team2
            self.thisDamageRatioListe.append(damage / team_damage if team_damage > 0 else 0)
            self.thisDamageTakenRatioListe.append(damage_taken / team_tank if team_tank > 0 else 0)

            # Stats par minute
            game_minutes = self.thisTime / 60
            self.thisDamagePerMinuteListe.append(round(damage / game_minutes, 1) if game_minutes > 0 else 0)
            self.thisMinionPerMinListe.append(round((participant.get('totalMinionsKilled', 0) + participant.get('neutralMinionsKilled', 0)) / game_minutes, 1) if game_minutes > 0 else 0)
            self.thisVisionPerMinListe.append(round(participant.get('visionScore', 0) / game_minutes, 2) if game_minutes > 0 else 0)
            self.thisTankPerMinListe.append(round(damage_taken / game_minutes, 1) if game_minutes > 0 else 0)

            # KDA
            deaths = participant.get('deaths', 0)
            kills = participant.get('kills', 0)
            assists = participant.get('assists', 0)
            kda = (kills + assists) / deaths if deaths > 0 else kills + assists
            self.thisKDAListe.append(round(kda, 2))

            # KP
            team_kills = self.thisTeamKills if i < 5 else self.thisTeamKillsOp
            kp = int((kills + assists) / team_kills * 100) if team_kills > 0 else 0
            self.thisKPListe.append(kp)

        # Bans
        self.liste_ban = []
        for team in teams:
            for ban in team.get('bans', []):
                champ_id = ban.get('championId', -1)
                if champ_id != -1:
                    champ_name = self.champ_dict.get(str(champ_id), 'Aucun')
                    self.liste_ban.append(champ_name)
                else:
                    self.liste_ban.append('Aucun')

        # Objectifs
        self._extract_objectives(teams, self.thisId)
        
        self.thisBaronPerso = self.match_detail_challenges['teamBaronKills']
        self.thisElderPerso = self.match_detail_challenges['teamElderDragonKills']

    def _extract_objectives(self, teams, id_joueur):
        """Extrait les objectifs des équipes."""
        
        if id_joueur <= 4:
            team = teams[0]['objectives']
        else:
            team = teams[1]['objectives']
            
        self.thisBaronTeam = team['baron']['kills']
        # self.thisElderPerso = team['dragon']['kills']
        self.thisDragonTeam = team['dragon']['kills']
        self.thisHordeTeam = team['horde']['kills']
        self.thisHeraldTeam = team['riftHerald']['kills']
        self.thisTowerTeam = team['tower']['kills']
        self.thisInhibTeam = team['inhibitor']['kills']


        # Dragons détaillés (si timeline disponible)
        self.dragons1, self.dragons2 = [], []
        if hasattr(self, 'data_timeline') and self.data_timeline:
            for frame in self.data_timeline['info']['frames']:
                for event in frame.get('events', []):
                    if event['type'] == 'ELITE_MONSTER_KILL' and event['monsterType'] == 'DRAGON':
                        dragon_type = event.get('monsterSubType', 'DRAGON').replace('_DRAGON', '').lower()
                        killer_team = event.get('killerTeamId', 0)
                        if killer_team == 100:
                            self.dragons1.append(dragon_type)
                        else:
                            self.dragons2.append(dragon_type)

    async def _extract_comparison_data(self):
        """Extrait les comparaisons entre lanes."""
        if self.thisQ in ["ARAM", "CLASH ARAM", "ARENA 2v2"]:
            self.ecart_top_gold = self.ecart_top_cs = 0
            self.ecart_jgl_gold = self.ecart_jgl_cs = 0
            self.ecart_mid_gold = self.ecart_mid_cs = 0
            self.ecart_adc_gold = self.ecart_adc_cs = 0
            self.ecart_supp_gold = self.ecart_supp_cs = 0
            return

        # Mapping des positions
        position_mapping = {
            'TOP': (0, 5), 'JUNGLE': (1, 6), 'MIDDLE': (2, 7),
            'BOTTOM': (3, 8), 'UTILITY': (4, 9)
        }

        # Trouver les indices par position
        position_indices = {}
        for i, pos in enumerate(self.thisPositionListe):
            if pos in position_mapping:
                team = 0 if i < 5 else 1
                position_indices.setdefault(pos, [None, None])[team] = i

        # Calcul des écarts
        def calc_ecart(pos, stat_liste):
            indices = position_indices.get(pos, [None, None])
            if indices[0] is not None and indices[1] is not None:
                return stat_liste[indices[0]] - stat_liste[indices[1]]
            return 0

        self.ecart_top_gold = calc_ecart('TOP', self.thisGoldListe)
        self.ecart_top_cs = calc_ecart('TOP', [m + j for m, j in zip(self.thisMinionListe, self.thisJungleMonsterKilledListe)])

        self.ecart_jgl_gold = calc_ecart('JUNGLE', self.thisGoldListe)
        self.ecart_jgl_cs = calc_ecart('JUNGLE', [m + j for m, j in zip(self.thisMinionListe, self.thisJungleMonsterKilledListe)])

        self.ecart_mid_gold = calc_ecart('MIDDLE', self.thisGoldListe)
        self.ecart_mid_cs = calc_ecart('MIDDLE', [m + j for m, j in zip(self.thisMinionListe, self.thisJungleMonsterKilledListe)])

        self.ecart_adc_gold = calc_ecart('BOTTOM', self.thisGoldListe)
        self.ecart_adc_cs = calc_ecart('BOTTOM', [m + j for m, j in zip(self.thisMinionListe, self.thisJungleMonsterKilledListe)])

        self.ecart_supp_gold = calc_ecart('UTILITY', self.thisGoldListe)
        self.ecart_supp_cs = calc_ecart('UTILITY', [m + j for m, j in zip(self.thisMinionListe, self.thisJungleMonsterKilledListe)])
        
        role_mapping = {
            'TOP' : (self.ecart_top_gold, self.ecart_top_cs),
            'JUNGLE' : (self.ecart_jgl_gold, self.ecart_jgl_cs),
            'MIDDLE' : (self.ecart_mid_gold, self.ecart_mid_cs),
            'BOTTOM' : (self.ecart_adc_gold, self.ecart_adc_cs),
            'UTILITY' : (self.ecart_supp_gold, self.ecart_supp_cs)
        }
        
        if self.thisPosition in role_mapping:
            gold_diff, cs_diff = role_mapping[self.thisPosition]
            
            if self.teamId == 200:
                gold_diff = -gold_diff
                cs_diff = -cs_diff
                
        self.ecart_gold_noformat = gold_diff
        self.ecart_cs_noformat = cs_diff
        self.ecart_gold_permin = round(gold_diff / self.thisTime, 2)
        
        if self.team == 0:
            self.ecart_gold_team = self.thisGold_team1 - self.thisGold_team2
        else:
            self.ecart_gold_team = self.thisGold_team2 - self.thisGold_team1

    async def _extract_masteries(self):
        """Extrait les maîtrises de tous les joueurs."""
        self.mastery_list = []
        self.mastery_level = []

        # for i in range(self.nb_joueur):
        #     puuid = self.thisPuuidListe[i]
        #     champ_id = self.thisChampIdListe[i]

        #     try:
        #         masteries = await get_champion_masteries(self.session, puuid)
        #         champ_mastery = next(
        #             (m for m in masteries if m['championId'] == champ_id),
        #             {'championLevel': 0, 'championPoints': 0}
        #         )
        #         self.mastery_level.append(champ_mastery['championLevel'])
        #         self.mastery_points.append(champ_mastery['championPoints'])
        #     except Exception:
        #         self.mastery_level.append(0)
        #         self.mastery_points.append(0)
        
        for id, tag in zip(self.thisRiotIdListe, self.thisRiotTagListe):
            try:
                id_tag = f'{id}#{tag}'
                masteries_data = await get_masteries_old(id_tag, self.champ_dict, self.session)
                masteries_data.set_index('championId', inplace=True)
                self.mastery_list.append(masteries_data)
            except:
                self.mastery_list.append(pd.DataFrame)

        for masteries_df, championid in zip(self.mastery_list, self.thisChampIdListe):
            try:
                self.mastery_level.append(masteries_df.loc[championid]['level'])
            except:
                self.mastery_level.append(0)
                
    async def _load_items_data(self):
        """Charge les données des items."""
        try:
            import json
            import aiohttp

            url = f"https://ddragon.leagueoflegends.com/cdn/{self.version['n']['item']}/data/fr_FR/item.json"
            async with self.session.get(url) as response:
                data = await response.json()
                self.items_data = data.get('data', {})
        except Exception:
            self.items_data = {}

    async def _load_rank_data(self):
        """Charge les données de rang de tous les joueurs."""
        self.winrate_joueur = {}
        self.winrate_champ_joueur = {}
        self.all_role = {}
        self.role_pref = {}
        self.role_count = {}
        self.dict_serie = {}

        for i in range(self.nb_joueur):
            riot_id = self.thisRiotIdListe[i].lower()
            riot_tag = self.thisRiotTagListe[i].upper()
            key = f'{riot_id}#{riot_tag}'
            champ_name = self.thisChampNameListe[i]

            try:
                # Stats du joueur via API externe (UGG ou Mobalytics)
                if self.moba_ok:
                    stats = await get_stat_champion_by_player(
                        riot_id, riot_tag, champ_name, self.session
                    )
                    if stats:
                        self.winrate_joueur[key] = {
                            'winrate': stats.get('winRate', 0),
                            'nbgames': stats.get('totalMatches', 0)
                        }
                        self.winrate_champ_joueur[key] = stats

                # Maîtrises via championmastery.gg
                masteries_data = await get_masteries_old(riot_id, riot_tag, self.session)
                if masteries_data:
                    self.all_role[riot_id] = masteries_data.get('roles', {})
                    self.role_pref[riot_id] = masteries_data.get('role_pref', {})
                    self.role_count[riot_id] = masteries_data.get('total_games', 0)

                # Série de victoires/défaites
                self.dict_serie[riot_id] = {
                    'count': 0,
                    'mot': 'Victoire',
                    'points': 0
                }

            except Exception:
                self.winrate_joueur[key] = {'winrate': 0, 'nbgames': 0}
                self.winrate_champ_joueur[key] = {}
                self.dict_serie[riot_id] = {'count': 0, 'mot': 'Victoire', 'points': 0}

    async def _calculate_team_averages(self):
        """Calcule les moyennes d'équipe (tier, rank)."""
        self.avgtier_ally = ''
        self.avgrank_ally = ''
        self.avgtier_enemy = ''
        self.avgrank_enemy = ''

        tier_values = {
            'IRON': 1, 'BRONZE': 2, 'SILVER': 3, 'GOLD': 4,
            'PLATINUM': 5, 'EMERALD': 6, 'DIAMOND': 7,
            'MASTER': 8, 'GRANDMASTER': 9, 'CHALLENGER': 10
        }
        tier_names = {v: k for k, v in tier_values.items()}

        ally_tiers = []
        enemy_tiers = []

        for i in range(self.nb_joueur):
            key = f'{self.thisRiotIdListe[i].lower()}#{self.thisRiotTagListe[i].upper()}'
            if key in self.winrate_joueur:
                tier = self.winrate_joueur[key].get('tier', '')
                if tier in tier_values:
                    if i < 5:
                        ally_tiers.append(tier_values[tier])
                    else:
                        enemy_tiers.append(tier_values[tier])

        if ally_tiers:
            avg_ally = round(np.mean(ally_tiers))
            self.avgtier_ally = tier_names.get(avg_ally, '')

        if enemy_tiers:
            avg_enemy = round(np.mean(enemy_tiers))
            self.avgtier_enemy = tier_names.get(avg_enemy, '')
