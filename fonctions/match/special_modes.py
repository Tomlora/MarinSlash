"""
Classe matchlol - Partie 10: Modes spéciaux (ARENA 2v2, SWARM).
"""

import numpy as np

from fonctions.gestion_bdd import requete_perso_bdd, lire_bdd_perso
from .utils import dict_data_swarm, range_value_arena


class ArenaModeMixin:
    """Mixin pour le mode ARENA 2v2."""

    async def prepare_data_arena(self):
        """Prépare les données spécifiques au mode Arena."""
        self.nb_joueur = 16
        participants = self.match_detail['info']['participants']

        # Listes de données
        self.thisPlacementListe = []
        self.thisSubteamPlacementListe = []
        self.thisAugmentsListe = []

        for i, participant in enumerate(participants):
            # Placement
            self.thisPlacementListe.append(participant.get('placement', 0))
            self.thisSubteamPlacementListe.append(participant.get('subteamPlacement', 0))

            # Augments
            augments = []
            for j in range(1, 7):
                augment = participant.get(f'playerAugment{j}', 0)
                if augment != 0:
                    augments.append(augment)
            self.thisAugmentsListe.append(augments)

        # Données du joueur
        self.thisPlacement = self.thisPlacementListe[self.index]
        self.thisSubteamPlacement = self.thisSubteamPlacementListe[self.index]
        self.thisAugments = self.thisAugmentsListe[self.index]

        # Déterminer le partenaire
        self.partner_index = None
        for i, participant in enumerate(participants):
            if (i != self.index and 
                participant.get('subteamPlacement') == self.thisSubteamPlacement):
                self.partner_index = i
                break

        # Stats du partenaire
        if self.partner_index is not None:
            self.partnerChampName = self.thisChampNameListe[self.partner_index]
            self.partnerKills = self.thisKillsListe[self.partner_index]
            self.partnerDeaths = self.thisDeathsListe[self.partner_index]
            self.partnerAssists = self.thisAssistsListe[self.partner_index]
            self.partnerDamage = self.thisDamageListe[self.partner_index]

        # Victoire si top 4
        self.thisWinBool = self.thisPlacement <= 4
        self.thisWinId = str(self.thisWinBool)

    async def save_data_arena(self):
        """Sauvegarde les données Arena en base."""
        requete_perso_bdd(
            '''INSERT INTO matchs_arena 
            (match_id, joueur, placement, subteam_placement, augment1, augment2, augment3, 
            augment4, augment5, augment6, partner_champion, partner_kills, partner_deaths, 
            partner_assists, partner_damage)
            VALUES 
            (:match_id, :joueur, :placement, :subteam_placement, :augment1, :augment2, :augment3,
            :augment4, :augment5, :augment6, :partner_champion, :partner_kills, :partner_deaths,
            :partner_assists, :partner_damage)
            ON CONFLICT (match_id, joueur) DO NOTHING''',
            {
                'match_id': self.last_match,
                'joueur': self.id_compte,
                'placement': self.thisPlacement,
                'subteam_placement': self.thisSubteamPlacement,
                'augment1': self.thisAugments[0] if len(self.thisAugments) > 0 else 0,
                'augment2': self.thisAugments[1] if len(self.thisAugments) > 1 else 0,
                'augment3': self.thisAugments[2] if len(self.thisAugments) > 2 else 0,
                'augment4': self.thisAugments[3] if len(self.thisAugments) > 3 else 0,
                'augment5': self.thisAugments[4] if len(self.thisAugments) > 4 else 0,
                'augment6': self.thisAugments[5] if len(self.thisAugments) > 5 else 0,
                'partner_champion': getattr(self, 'partnerChampName', ''),
                'partner_kills': getattr(self, 'partnerKills', 0),
                'partner_deaths': getattr(self, 'partnerDeaths', 0),
                'partner_assists': getattr(self, 'partnerAssists', 0),
                'partner_damage': getattr(self, 'partnerDamage', 0),
            }
        )

    def calcul_scoring_arena(self, i):
        """Calcule le score de performance pour Arena."""
        # Score basé sur le placement et les stats
        placement_score = (9 - self.thisPlacementListe[i]) * 10
        kda_score = (self.thisKillsListe[i] + self.thisAssistsListe[i] * 0.5 - self.thisDeathsListe[i] * 2) * 2
        damage_score = self.thisDamageListe[i] / 1000

        return placement_score + kda_score + damage_score


class SwarmModeMixin:
    """Mixin pour le mode SWARM."""

    async def prepare_data_swarm(self):
        """Prépare les données spécifiques au mode Swarm."""
        participants = self.match_detail['info']['participants']

        # Extraction des données Swarm
        self.swarm_data = dict_data_swarm(self.match_detail_participants)

        # Données principales
        self.thisSwarmLevel = self.swarm_data.get('playerScore0', 0)  # Niveau atteint
        self.thisSwarmGold = self.swarm_data.get('goldEarned', 0)
        self.thisSwarmKills = self.swarm_data.get('kills', 0)
        self.thisSwarmDeaths = self.swarm_data.get('deaths', 0)
        self.thisSwarmDamage = self.swarm_data.get('totalDamageDealtToChampions', 0)
        self.thisSwarmHealing = self.swarm_data.get('totalHeal', 0)

        # Durée de survie
        self.thisSwarmSurvivalTime = self.match_detail['info'].get('gameDuration', 0)

        # Victoire (survie jusqu'à la fin ou boss vaincu)
        self.thisWinBool = self.match_detail_participants.get('win', False)
        self.thisWinId = str(self.thisWinBool)

        # Augments/upgrades Swarm
        self.thisSwarmAugments = []
        for key in self.swarm_data:
            if 'Augment' in key or 'upgrade' in key.lower():
                self.thisSwarmAugments.append(self.swarm_data[key])

    async def save_data_swarm(self):
        """Sauvegarde les données Swarm en base."""
        requete_perso_bdd(
            '''INSERT INTO matchs_swarm 
            (match_id, joueur, champion, level_reached, gold_earned, kills, deaths,
            damage_dealt, healing_done, survival_time, victory)
            VALUES 
            (:match_id, :joueur, :champion, :level_reached, :gold_earned, :kills, :deaths,
            :damage_dealt, :healing_done, :survival_time, :victory)
            ON CONFLICT (match_id, joueur) DO NOTHING''',
            {
                'match_id': self.last_match,
                'joueur': self.id_compte,
                'champion': self.thisChampName,
                'level_reached': self.thisSwarmLevel,
                'gold_earned': self.thisSwarmGold,
                'kills': self.thisSwarmKills,
                'deaths': self.thisSwarmDeaths,
                'damage_dealt': self.thisSwarmDamage,
                'healing_done': self.thisSwarmHealing,
                'survival_time': self.thisSwarmSurvivalTime,
                'victory': self.thisWinBool,
            }
        )


class ClashModeMixin:
    """Mixin pour le mode CLASH."""

    async def prepare_data_clash(self):
        """Prépare les données spécifiques au mode Clash."""
        # Le Clash utilise les mêmes données que ranked mais avec des métadonnées supplémentaires
        info = self.match_detail['info']

        self.clash_tournament_id = info.get('tournamentCode', '')
        self.clash_game_type = info.get('gameType', 'CLASH')

        # Déterminer le type de Clash (ARAM ou SR)
        map_id = info.get('mapId', 11)
        if map_id == 12:  # ARAM map
            self.thisQ = 'CLASH ARAM'
        else:
            self.thisQ = 'CLASH'

    async def save_data_clash(self):
        """Sauvegarde les données Clash en base."""
        if hasattr(self, 'clash_tournament_id') and self.clash_tournament_id:
            requete_perso_bdd(
                '''UPDATE matchs SET tournament_code = :tournament_code
                WHERE match_id = :match_id AND joueur = :joueur''',
                {
                    'tournament_code': self.clash_tournament_id,
                    'match_id': self.last_match,
                    'joueur': self.id_compte,
                }
            )
