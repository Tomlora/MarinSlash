"""
Classe matchlol - Partie 8: Badges, scoring et observations.
"""

import pandas as pd
import numpy as np

from fonctions.gestion_bdd import lire_bdd, lire_bdd_perso, requete_perso_bdd


class BadgesMixin:
    """Mixin pour la gestion des badges et du scoring."""

    def calcul_scoring(self, i):
        """
        Calcule la performance d'un joueur.
        
        Parameters:
            i: Index du joueur (0-9)
            
        Returns:
            float: Score de performance
        """
        score = self.model.predict(pd.DataFrame([[
            self.thisKillsListe[i],
            self.thisAssistsListe[i],
            self.thisDeathsListe[i],
            self.thisDoubleListe[i],
            self.thisTripleListe[i],
            self.thisQuadraListe[i],
            self.thisPentaListe[i],
            self.thisDamagePerMinuteListe[i],
            self.thisMinionPerMinListe[i],
            self.thisVisionPerMinListe[i],
            self.thisKPListe[i],
            self.thisKDAListe[i],
            self.thisTankPerMinListe[i]
        ]]))

        return score

    async def calcul_badges(self, sauvegarder):
        """Calcule et sauvegarde les badges obtenus."""
        if self.thisQ in ['ARAM', 'CLASH ARAM']:
            settings = lire_bdd_perso(
                'SELECT index, score_aram as score from achievements_settings'
            )
        else:
            settings = lire_bdd_perso(
                'SELECT index, score as score from achievements_settings'
            )

        settings = settings.to_dict()

        def insight_text(slug, values, type):
            type_comment = {
                'Positive': ':green_circle:',
                'Negative': ':red_circle:',
                '': ':first_place:'
            }

            dict_insight = {
                'teamfight_god': f'\n{type_comment[type]} Gagné **{values[0]}** sur **{values[1]}** teamfights',
                'lane_tyrant': f"\n{type_comment[type]} **{values[0]}** gold d'avance à 15 min",
                'stomp': f"\n{type_comment[type]} **{values[0]}** gold d'avance",
                'how_could_you': f"\n{type_comment[type]} **{values[0]}** wards placés",
                'not_fan_of_wards': f"\n{type_comment[type]} Placé **{values[0]}** wards",
                'servant_of_darkness': f"\n{type_comment[type]} Détruit **{values[0]}** wards",
                'good_guy': f"\n{type_comment[type]} Acheté **{values[0]}** pink",
                'pick_up_artist': f"\n{type_comment[type]} Sécurisé **{values[0]}** picks",
                'wanderer': f"\n{type_comment[type]} Roam pour sécuriser kills et objectifs",
                'survivor': f"\n{type_comment[type]} Seulement **{values[0]}** mort(s)",
                'elite_skirmisher': f"\n{type_comment[type]} Gagné **{values[0]}** escarmouches sur **{values[1]}**",
                'wrecking_ball': f"\n{type_comment[type]} **{values[0]}** DMG aux structures",
                'ouch_you_hurt': f"\n{type_comment[type]} **{values[0]}** DMG infligés",
                'goblin_hoarder': f"\n{type_comment[type]} **{int(values[0])}** Gold / min",
                'anti_kda_player': f"\n{type_comment[type]} **{round(values[0], 2)}** KDA",
                'not_fan_of_farming': f"\n{type_comment[type]} **{int(values[0])}** farm / min",
                'visionary': f"\n{type_comment[type]} **{values[0]}** wards placés",
                'no_control': f"\n{type_comment[type]} 0 pink",
                'blood_thirsty': f"\n{type_comment[type]} Tu as réussi **{values[0]}** ganks dans les 10 premières minutes.",
                'superior_jungler': f"\n{type_comment[type]} Tu as réussi plus de ganks avec **{values[0]}**",
                'comeback_king': f"\n{type_comment[type]} Tu as réussi à comeback après un début difficile",
                'safety_first': f"\n{type_comment[type]} Tu as placé assez de vision pour préparer les objectifs neutres",
                'no_damage_to_turrets': f"\n{type_comment[type]} **0** DMG sur les tours",
                'mvp': f"\n{type_comment[type]} **Meilleur joueur**"
            }

            if self.thisQ not in ['ARAM', 'CLASH ARAM']:
                dict_insight['ready_to_rumble'] = (
                    f"\n{type_comment[type]} Proactif en early avec **{values[0]}** kills/assists avant 15 minutes"
                )

            if slug == 'early_game_farmer' and values[0] >= 85:
                dict_insight['early_game_farmer'] = (
                    f'\n{type_comment[type]} Farm en early avec **{values[0]}** cs à 10 minutes'
                )

            return dict_insight.get(slug, '')

        self.observations = ''
        txt_sql = ''

        def add_sql(txt_sql, name, values, last_match, id_compte):
            if len(values) != 3:
                values.append(0)
                values.append(0)

            if values[0] == 0:
                txt_sql += f'''UPDATE data_badges SET {name} = True WHERE match_id = '{last_match}' and joueur = '{id_compte}';'''
            elif values[0] != 0 and values[1] == 0:
                txt_sql += f'''UPDATE data_badges SET {name} = True, {name}_value = {values[0]} WHERE match_id = '{last_match}' and joueur = '{id_compte}';'''
            else:
                txt_sql += f'''UPDATE data_badges SET {name} = True, {name}_value1 = {values[0]}, {name}_value2 = {values[1]} WHERE match_id = '{last_match}' and joueur = '{id_compte}';'''

            return txt_sql

        # Traitement des badges
        try:
            for insight in self.badges:
                self.observations += insight_text(insight['slug'], insight['values'], insight['type'])

                badge_names = [
                    'teamfight_god', 'lane_tyrant', 'stomp', 'how_could_you',
                    'not_fan_of_wards', 'servant_of_darkness', 'good_guy',
                    'pick_up_artist', 'wanderer', 'survivor', 'elite_skirmisher',
                    'wrecking_ball', 'ouch_you_hurt', 'goblin_hoarder',
                    'anti_kda_player', 'not_fan_of_farming', 'visionary',
                    'no_control', 'blood_thirsty', 'superior_jungler',
                    'comeback_king', 'safety_first', 'no_damage_to_turrets', 'mvp'
                ]

                if insight['slug'] in badge_names:
                    txt_sql = add_sql(txt_sql, insight['slug'], insight['values'], self.last_match, self.id_compte)
        except TypeError:
            pass

        # Badges additionnels
        self._add_multikill_badges(txt_sql, add_sql)
        self._add_stat_badges(txt_sql, add_sql, settings)

        # Gestion de la longueur
        if len(self.observations) > 1000:
            self.observations2 = self.observations[1000:]
            self.observations = self.observations[:1000]
        else:
            self.observations2 = ''

        # Insertion en BDD
        requete_perso_bdd(
            f'''INSERT INTO data_badges(match_id, joueur)
            VALUES ('{self.last_match}', '{self.id_compte}');'''
        )


        self._add_performance_calcul()

        if txt_sql != '' and sauvegarder:
            requete_perso_bdd(txt_sql)

    def _add_multikill_badges(self, txt_sql, add_sql):
        """Ajoute les badges de multikill."""
        if self.thisDouble >= 3:
            self.observations += f"\n:green_circle: :two: **{self.thisDouble}** doublé"
            txt_sql = add_sql(txt_sql, 'double', [self.thisDouble], self.last_match, self.id_compte)

        if self.thisTriple >= 2:
            self.observations += f"\n:green_circle: :three: **{self.thisTriple}** triplé"
            txt_sql = add_sql(txt_sql, 'triple', [self.thisTriple], self.last_match, self.id_compte)

        if self.thisQuadra >= 2:
            self.observations += f"\n:green_circle: :four: **{self.thisQuadra}** quadra"
            txt_sql = add_sql(txt_sql, 'quadra', [self.thisQuadra], self.last_match, self.id_compte)

        if self.thisPenta >= 1:
            self.observations += f"\n:green_circle: :five: **{self.thisPenta}** penta"
            txt_sql = add_sql(txt_sql, 'penta', [self.thisPenta], self.last_match, self.id_compte)

        if self.thisTotalHealed >= 5000:
            self.observations += f"\n:green_circle: **{self.thisTotalHealed}** HP soignés"
            txt_sql = add_sql(txt_sql, 'heal', [self.thisTotalHealed], self.last_match, self.id_compte)

        if self.thisTotalShielded >= 3000:
            self.observations += f"\n:green_circle: :shield: **{self.thisTotalShielded}** boucliers"
            txt_sql = add_sql(txt_sql, 'shield', [self.thisTotalShielded], self.last_match, self.id_compte)

        return txt_sql

    def _add_stat_badges(self, txt_sql, add_sql, settings):
        """Ajoute les badges basés sur les statistiques."""
        # Vision
        if self.thisVisionAdvantage >= 60 and self.thisQ not in ['ARAM', 'CLASH ARAM']:
            self.observations += f"\n:green_circle: :eye: **{self.thisVisionAdvantage}**% AV vision"
            txt_sql = add_sql(txt_sql, 'vision_avantage', [self.thisVisionAdvantage], self.last_match, self.id_compte)
        elif self.thisVisionAdvantage <= -50 and self.thisQ not in ['ARAM', 'CLASH ARAM']:
            self.observations += f"\n:red_circle: :eye: **{self.thisVisionAdvantage}**% AV vision"
            txt_sql = add_sql(txt_sql, 'vision_avantage', [self.thisVisionAdvantage], self.last_match, self.id_compte)

        # Solokills
        if self.thisSoloKills >= 1:
            self.observations += f"\n:green_circle: :karate_uniform: **{self.thisSoloKills}** solokills"
            txt_sql = add_sql(txt_sql, 'solokills', [self.thisSoloKills], self.last_match, self.id_compte)

        # Farm
        if self.thisMinionPerMin >= 7:
            self.observations += f'\n:green_circle: :ghost: **{self.thisMinionPerMin}** cs/min'
            txt_sql = add_sql(txt_sql, 'minion_min', [self.thisMinionPerMin], self.last_match, self.id_compte)

        # Badges spécifiques ranked/normal
        if self.thisQ in ['RANKED', 'NORMAL', 'FLEX']:
            self._add_ranked_badges(txt_sql, add_sql, settings)

        # Badges communs
        if self.thisQ != 'ARENA 2v2':
            self._add_common_badges(txt_sql, add_sql, settings)

        return txt_sql

    def _add_ranked_badges(self, txt_sql, add_sql, settings):
        """Ajoute les badges spécifiques aux parties classées."""
        if int(self.thisLevelAdvantage) >= settings['Ecart_Level']['score']:
            self.observations += f"\n **:green_circle: :wave: {self.thisLevelAdvantage} niveaux d'avance sur ton adversaire**"
            txt_sql = add_sql(txt_sql, 'level_avantage', [self.thisLevelAdvantage], self.last_match, self.id_compte)

        if float(self.thisDragonTeam) >= settings['Dragon']['score']:
            self.observations += "\n **:green_circle: :dragon: Âme du dragon **"
            txt_sql = add_sql(txt_sql, 'dragon', [self.thisDragonTeam], self.last_match, self.id_compte)

        if int(self.thisDanceHerald) >= 1:
            self.observations += "\n **:green_circle: :dancer: Danse avec l'Herald **"
            txt_sql = add_sql(txt_sql, 'herald_dance', [0], self.last_match, self.id_compte)

        if int(self.thisPerfectGame) >= 1:
            self.observations += "\n:green_circle: :sunny: Perfect Game"
            txt_sql = add_sql(txt_sql, 'perfect_game', [0], self.last_match, self.id_compte)

        if int(self.thisDeaths) == int(settings['Ne_pas_mourir']['score']):
            self.observations += "\n **:green_circle: :heart: N'est pas mort de la game ** \n "
            txt_sql = add_sql(txt_sql, 'ne_pas_mourir', [0], self.last_match, self.id_compte)

        if float(self.thisVisionPerMin) >= settings['Vision/min(support)']['score'] and str(self.thisPosition) == "SUPPORT":
            self.observations += f"\n **:green_circle: :eye: {self.thisVisionPerMin} Vision / min **"
            txt_sql = add_sql(txt_sql, 'vision_min', [self.thisVisionPerMin], self.last_match, self.id_compte)

        if int(self.thisVisionPerMin) >= settings['Vision/min(autres)']['score'] and str(self.thisPosition) != "SUPPORT":
            self.observations += f"\n **:green_circle: :eye: {self.thisVisionPerMin} Vision / min **"
            txt_sql = add_sql(txt_sql, 'vision_min', [self.thisVisionPerMin], self.last_match, self.id_compte)

        if int(self.thisCSAdvantageOnLane) >= settings['CSAvantage']['score']:
            self.observations += f"\n **:green_circle: :ghost: {self.thisCSAdvantageOnLane} CS d'avance sur ton adversaire**"
            txt_sql = add_sql(txt_sql, 'cs_avantage', [self.thisCSAdvantageOnLane], self.last_match, self.id_compte)

        return txt_sql

    def _add_common_badges(self, txt_sql, add_sql, settings):
        """Ajoute les badges communs à tous les modes."""
        if int(self.thisDamageTakenRatio) >= settings['%_dmg_tank']['score']:
            self.observations += f"\n **:green_circle: :shield: {self.thisDamageTakenRatio}% Tanking de ton équipe **"
            txt_sql = add_sql(txt_sql, 'tank_ratio', [self.thisDamageTakenRatio], self.last_match, self.id_compte)

        return txt_sql

    def _add_performance_calcul(self):
    # Récupérer le résumé de performance
        perf = self.get_player_performance_summary()
        
        # Badge MVP
        if perf.get('is_mvp'):
            self.badges.append('MVP')
            self.observations += f"🏆 **MVP** de la partie! Score: {perf['score']}/10\n"
        
        # Badge ACE (meilleur perdant)
        elif perf.get('is_ace') and not self.thisWinBool:
            self.badges.append('ACE')
            self.observations += f"⭐ **ACE** - Meilleur de ton équipe malgré la défaite\n"
        
        # Badge basé sur le point fort
        best_dim = perf.get('best_dimension')
        best_emoji = perf.get('best_dimension_emoji', '')
        best_score = perf.get('best_dimension_score', 0)
        
        if best_score >= 8:
            dim_badges = {
                'Combat': 'Combat King',
                'Économie': 'Gold Efficient',
                'Objectifs': 'Objective Master',
                'Tempo': 'Tempo Lord',
                'Impact': 'Game Changer'
            }
            if best_dim in dim_badges:
                self.badges.append(dim_badges[best_dim])
                # self.observations += f"{best_emoji} **{dim_badges[best_dim]}** - {best_dim}: {best_score}/10\n"
        
        # Afficher le score dans les observations
        score_emoji = self.get_score_emoji(self.player_score)
        rank_text = self.get_rank_text(self.player_rank)
        # self.observations2 += f"\n{score_emoji} Performance: **{self.player_score}/10** ({rank_text})"
