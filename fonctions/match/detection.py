"""
Classe matchlol - Partie 7: Détection des joueurs (smurf, OTP, autofill, etc.).
"""

import pandas as pd

from fonctions.gestion_bdd import lire_bdd_perso, requete_perso_bdd
from fonctions.channels_discord import mention
from utils.emoji import emote_champ_discord, emote_rank_discord


class DetectionMixin:
    """Mixin pour la détection de patterns joueurs."""

    async def detection_joueurs_pro(self):
        """Détecte les joueurs professionnels dans la partie."""
        df_data_pro = lire_bdd_perso(
            '''SELECT data_acc_proplayers.*, data_proplayers.home, data_proplayers.role, data_proplayers.team_plug 
            FROM data_acc_proplayers
            LEFT JOIN data_proplayers ON data_acc_proplayers.joueur = data_proplayers.plug
            WHERE region = 'EUW' ''',
            index_col=None
        ).T

        df_data_pro['tag'] = df_data_pro['compte'].apply(
            lambda x: x.split('#')[1].upper() if '#' in x else ''
        )
        df_data_pro['compte'] = df_data_pro['compte'].apply(lambda x: x.split('#')[0])

        self.observations_proplayers = ''

        for num_joueur, (joueur, riot_tag) in enumerate(zip(self.thisPseudoListe, self.thisRiotTagListe)):
            riot_tag = riot_tag.upper()
            match_df = df_data_pro[
                (df_data_pro['compte'] == joueur) & (df_data_pro['tag'] == riot_tag)
            ]

            if not match_df.empty:
                name_joueur = match_df['joueur'].values[0]
                role_joueur = match_df['role'].values[0]
                team_joueur = match_df['team_plug'].values[0]
                champ_joueur = self.thisChampNameListe[num_joueur]
                emote_champ = emote_champ_discord.get(champ_joueur.capitalize(), f'({champ_joueur})')
                emote = ':blue_circle:' if num_joueur <= 4 else ':red_circle:'

                if team_joueur in ('', None):
                    self.observations_proplayers += f'{emote} **{name_joueur}** {emote_champ} : {role_joueur} \n'
                else:
                    self.observations_proplayers += f'{emote} **{name_joueur}** {emote_champ} : {role_joueur} chez {team_joueur} \n'

    async def detection_smurf(self):
        """Détecte les potentiels smurfs basé sur le winrate."""
        self.observations_smurf = ''

        for num, (joueur, stat) in enumerate(self.winrate_joueur.items()):
            if (joueur != f'{self.riot_id.lower()}#{self.riot_tag.upper()}' and
                    stat['winrate'] >= 70 and stat['nbgames'] >= 20):
                emote = ':blue_circle:' if num <= 4 else ':red_circle:'
                self.observations_smurf += (
                    f'{emote} **{joueur.split("#")[0]}** : WR : {stat["winrate"]}% '
                    f'({stat["nbgames"]} parties) \n'
                )

        for num, (joueur, stat) in enumerate(self.winrate_champ_joueur.items()):
            if isinstance(stat, dict):
                if (joueur != f'{self.riot_id.lower()}#{self.riot_tag.upper()}' and
                        stat['winrate'] >= 70 and stat['totalMatches'] >= 15):
                    emote_champ = emote_champ_discord.get(
                        stat["championId"].capitalize(), stat["championId"]
                    )
                    emote = ':blue_circle:' if num <= 4 else ':red_circle:'
                    self.observations_smurf += (
                        f'{emote} **{joueur.split("#")[0]}** : WR : {stat["winrate"]}% '
                        f'({stat["totalMatches"]} parties) sur {emote_champ} \n'
                    )

    async def detection_mauvais_joueur(self):
        """Détecte les joueurs avec un faible winrate."""
        self.observations_mauvais_joueur = ''

        for num, (joueur, stat) in enumerate(self.winrate_joueur.items()):
            if (joueur != f'{self.riot_id.lower()}#{self.riot_tag.upper()}' and
                    stat['winrate'] <= 40 and stat['nbgames'] >= 20):
                emote = ':blue_circle:' if num <= 4 else ':red_circle:'
                self.observations_mauvais_joueur += (
                    f'{emote} **{joueur.split("#")[0]}** : WR : {stat["winrate"]}% '
                    f'({stat["nbgames"]} parties) \n'
                )

        for num, (joueur, stat) in enumerate(self.winrate_champ_joueur.items()):
            if isinstance(stat, dict):
                if (joueur != f'{self.riot_id.lower()}#{self.riot_tag.upper()}' and
                        stat['winrate'] <= 40 and stat['totalMatches'] >= 15):
                    emote_champ = emote_champ_discord.get(
                        stat["championId"].capitalize(), stat["championId"]
                    )
                    emote = ':blue_circle:' if num <= 4 else ':red_circle:'
                    self.observations_mauvais_joueur += (
                        f'{emote} **{joueur.split("#")[0]}** : WR : {stat["winrate"]}% '
                        f'({stat["totalMatches"]} parties) sur {emote_champ} \n'
                    )

    async def detection_first_time(self):
        """Détecte les joueurs qui jouent un champion pour la première fois ou sont autofill."""
        self.first_time = ''

        dict_pos = {
            0: 'top', 1: 'jungle', 2: 'mid', 3: 'adc', 4: 'support',
            5: 'top', 6: 'jungle', 7: 'mid', 8: 'adc', 9: 'support'
        }

        for num, (joueur, stat) in enumerate(self.winrate_champ_joueur.items()):
            if isinstance(stat, dict):
                if (joueur != f'{self.riot_id.lower()}#{self.riot_tag.upper()}' and
                        stat['totalMatches'] <= 5):
                    emote = ':blue_circle:' if num <= 4 else ':red_circle:'
                    emote_champ = emote_champ_discord.get(
                        stat["championId"].capitalize(), stat["championId"]
                    )
                    self.first_time += (
                        f'{emote} **{joueur.split("#")[0]}** : {stat["totalMatches"]} games '
                        f'sur {emote_champ} \n'
                    )

            pseudo = joueur.split("#")[0]

            if pseudo in self.all_role.keys():
                emote = ':blue_circle:' if num <= 4 else ':red_circle:'

                role = dict_pos[num]
                main_role = self.role_pref[pseudo]['main_role']
                poids_main_role = self.role_pref[pseudo]['poids_role']
                emote_champ = emote_champ_discord.get(
                    self.thisChampNameListe[num].capitalize(),
                    self.thisChampNameListe[num].capitalize()
                )

                try:
                    if self.all_role[pseudo][role]['poids'] <= 15 and self.role_count[pseudo] > 30:
                        self.first_time += (
                            f'{emote} **{pseudo}** {emote_champ} Autofill ({role.upper()}) : '
                            f'Main {main_role.upper()} ({poids_main_role}%) \n'
                        )
                except KeyError:
                    pass

    async def detection_otp(self):
        """Détecte les joueurs OTP (One Trick Pony)."""
        self.otp = ''

        for num, (joueur, stat) in enumerate(self.winrate_champ_joueur.items()):
            if isinstance(stat, dict):
                if (joueur != f'{self.riot_id.lower()}#{self.riot_tag.upper()}' and
                        stat['totalMatches'] >= 20 and stat['poids_games'] > 70):
                    emote_champ = emote_champ_discord.get(
                        stat["championId"].capitalize(), stat["championId"]
                    )
                    emote = ':blue_circle:' if num <= 4 else ':red_circle:'

                    self.otp += (
                        f'{emote} **{joueur.split("#")[0]}** : {emote_champ} '
                        f'{stat["poids_games"]}% pick | {stat["winrate"]}% WR \n'
                    )

    async def detection_serie_victoire(self):
        """Détecte les joueurs en série de victoires/défaites."""
        self.serie_victoire = ''

        for i, (joueur, stats) in enumerate(self.dict_serie.items()):
            if stats['count'] >= 5:
                emote = ':green_circle:' if i <= 4 else ':red_circle:'
                mot = ':white_check_mark:' if stats['mot'] == 'Victoire' else ':x:'
                self.serie_victoire += (
                    f'{emote} **{joueur}** {mot} {stats["count"]} consécutives \n'
                )

    async def ecart_cs_by_role(self):
        """Génère le texte des écarts de CS significatifs par rôle."""
        self.ecart_cs_txt = ''

        for i, role in enumerate(['top', 'jgl', 'mid', 'adc', 'supp']):
            ecart_cs_role = getattr(self, f'ecart_{role}_cs')

            if ecart_cs_role > 70:
                self.ecart_cs_txt += f':blue_circle: {role.upper()} : **{ecart_cs_role}** cs \n'
            if ecart_cs_role < -70:
                self.ecart_cs_txt += f':red_circle: {role.upper()} **{abs(ecart_cs_role)}** cs \n'

    async def detection_gap(self):
        """Détecte les gaps significatifs entre joueurs."""
        self.txt_gap = ''

        if hasattr(self, 'df_data_match'):
            roles = ['TOP', 'JGL', 'MID', 'ADC', 'SUPP']
            self.ecarts_gap = {}
            self.emote_gap = {}
            self.max_ecart_role = None
            self.max_ecart_valeur = 0

            if not self.df_data_match.empty:
                for i in range(5):
                    joueur = self.thisRiotIdListe[i].lower()
                    adversaire = self.thisRiotIdListe[i + 5].lower()

                    points_joueur = self.dict_serie[joueur]['points']
                    points_adversaire = self.dict_serie[adversaire]['points']

                    ecart = points_joueur - points_adversaire
                    ecart = 0 if points_joueur == 0 or points_adversaire == 0 else ecart
                    role = roles[i]
                    self.emote_gap[role] = ':green_circle:' if ecart > 0 else ':red_circle:'
                    self.ecarts_gap[role] = abs(ecart)

            for key, value in self.ecarts_gap.items():
                if value > 20:
                    emote = self.emote_gap[key]
                    self.txt_gap += f'{emote}**{key}** GAP | '


class ObjectifsMixin:
    """Mixin pour la gestion des objectifs personnels."""

    async def traitement_objectif(self):
        """Traite les objectifs personnels du joueur."""
        objectifs_en_attente = lire_bdd_perso(
            f'''SELECT * FROM objectifs_lol_suivi
            WHERE id_compte = {self.id_compte}
            AND match_id IS NULL''',
            index_col=None
        ).transpose()

        for _, obj in objectifs_en_attente.iterrows():
            objectif_id = obj['objectif_id']
            valeur_attendue = obj['valeur_attendue']

            # Check si déjà existant
            check = lire_bdd_perso(
                f'''SELECT 1 FROM objectifs_lol_suivi
                WHERE id_compte = {self.id_compte}
                AND match_id = '{self.last_match}'
                AND objectif_id = {objectif_id}
                LIMIT 1''',
                index_col=None
            )
            if not check.empty:
                continue

            # Évaluation selon le type d'objectif
            if objectif_id == 1:  # CS/min
                valeur_obtenue = self.thisMinionPerMin
                atteint = valeur_obtenue >= valeur_attendue
            elif objectif_id == 2:  # KP%
                valeur_obtenue = self.thisKP
                atteint = valeur_obtenue >= valeur_attendue
            elif objectif_id == 3:  # KDA
                valeur_obtenue = self.thisKDA if self.thisDeaths != 0 else self.thisKills + self.thisAssists
                atteint = valeur_obtenue >= valeur_attendue
            elif objectif_id == 4:  # Deaths max
                valeur_obtenue = self.thisDeaths
                atteint = valeur_obtenue <= valeur_attendue
            else:
                valeur_obtenue = 0
                atteint = False

            requete_perso_bdd(
                """INSERT INTO objectifs_lol_suivi
                (id_compte, match_id, objectif_id, valeur_attendue, valeur_obtenue, atteint, date_partie)
                VALUES
                (:id_compte, :match_id, :objectif_id, :valeur_attendue, :valeur_obtenue, :atteint, NOW())""",
                {
                    'id_compte': self.id_compte,
                    'match_id': self.last_match,
                    'objectif_id': objectif_id,
                    'valeur_attendue': valeur_attendue,
                    'valeur_obtenue': valeur_obtenue,
                    'atteint': atteint,
                }
            )

    async def show_objectifs(self):
        """Affiche les objectifs du joueur pour ce match."""
        objectifs = lire_bdd_perso(
            f'''SELECT suiv.*, types.nom, types.description
            FROM objectifs_lol_suivi suiv
            JOIN objectifs_lol_types types ON suiv.objectif_id = types.id
            WHERE suiv.id_compte = {self.id_compte}
            AND suiv.match_id = '{self.last_match}' ''',
            index_col=None
        ).transpose()

        if not objectifs.empty:
            txt = ''
            description = "🎯 Objectifs personnels :\n"
            for _, data in objectifs.iterrows():
                etat = "✅" if data['atteint'] else "❌"
                txt += f"- {etat} {data['description']} ({data['valeur_attendue']}): {round(data['valeur_obtenue'], 2)}\n"

            return description, txt
        return None, None
