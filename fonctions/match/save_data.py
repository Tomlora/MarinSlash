"""
Classe matchlol - Partie 4: Sauvegarde des données en base de données.
"""

import numpy as np
import pandas as pd
import sqlalchemy.exc
from sqlalchemy.exc import IntegrityError
import pickle
from fonctions.gestion_bdd import requete_perso_bdd, lire_bdd_perso, sauvegarde_bdd
from .utils import fix_temps, load_timeline
from .riot_api import get_data_champ_tags


class SaveDataMixin:
    """Mixin pour la sauvegarde des données."""

    async def save_data(self):
        """Sauvegarde l'ensemble des données dans la base de données."""
        if self.thisDeaths >= 1:
            self.kda_save = self.thisKDA
        else:
            self.kda_save = round(
                (int(self.thisKills) + int(self.thisAssists)) / (int(self.thisDeaths) + 1), 2
            )

        df_exists = lire_bdd_perso(
            f'''SELECT match_id, joueur from matchs
            WHERE match_id = '{self.last_match}' 
            AND joueur = {self.id_compte}''',
            index_col=None
        )

        if df_exists.empty:
            self._insert_match_data()
            self._insert_participant_data()
            self._insert_other_match_data()
            self._insert_points_data()

        df_data_champ = await get_data_champ_tags(self.session, self.version['n']['champion'])
        sauvegarde_bdd(df_data_champ, 'data_champion_tag', index=False)

    def _insert_match_data(self):
        """Insère les données principales du match."""
        requete_perso_bdd(
            '''INSERT INTO matchs(
            match_id, joueur, role, champion, kills, assists, deaths, double, triple, quadra, penta,
            victoire, team_kills, team_deaths, "time", dmg, dmg_ad, dmg_ap, dmg_true, vision_score, cs, cs_jungle, vision_pink, vision_wards, vision_wards_killed,
            gold, cs_min, vision_min, gold_min, dmg_min, solokills, dmg_reduit, heal_total, heal_allies, serie_kills, cs_dix_min, jgl_dix_min,
            baron, drake, team, herald, cs_max_avantage, level_max_avantage, afk, vision_avantage, early_drake, temps_dead,
            item1, item2, item3, item4, item5, item6, kp, kda, mode, season, date, damageratio, tankratio, rank, tier, lp, id_participant, dmg_tank, shield,
            early_baron, allie_feeder, snowball, temps_vivant, dmg_tower, gold_share, mvp, ecart_gold_team, "kills+assists", datetime, temps_avant_premiere_mort, "dmg/gold", ecart_gold, ecart_gold_min,
            split, skillshot_dodged, temps_cc, spells_used, buffs_voles, s1cast, s2cast, s3cast, s4cast, horde, moba, kills_min, deaths_min, assists_min, ecart_cs, petales_sanglants, atakhan, crit_dmg, immobilisation, skillshot_hit, temps_cc_inflige, tower, inhib,
            dmg_true_all, dmg_true_all_min, dmg_ad_all, dmg_ad_all_min, dmg_ap_all, dmg_ap_all_min, dmg_all, dmg_all_min, records, longue_serie_kills, ecart_kills, ecart_deaths, ecart_assists, ecart_dmg, trade_efficience, skillshots_dodge_min, skillshots_hit_min, dmg_par_kills,
            first_tower_time, hardcarry, teamcarry, killsratio, deathsratio, solokillsratio)
            VALUES (:match_id, :joueur, :role, :champion, :kills, :assists, :deaths, :double, :triple, :quadra, :penta,
            :result, :team_kills, :team_deaths, :time, :dmg, :dmg_ad, :dmg_ap, :dmg_true, :vision_score, :cs, :cs_jungle, :vision_pink, :vision_wards, :vision_wards_killed,
            :gold, :cs_min, :vision_min, :gold_min, :dmg_min, :solokills, :dmg_reduit, :heal_total, :heal_allies, :serie_kills, :cs_dix_min, :jgl_dix_min,
            :baron, :drake, :team, :herald, :cs_max_avantage, :level_max_avantage, :afk, :vision_avantage, :early_drake, :temps_dead,
            :item1, :item2, :item3, :item4, :item5, :item6, :kp, :kda, :mode, :season, :date, :damageratio, :tankratio, :rank, :tier, :lp, :id_participant, :dmg_tank, :shield,
            :early_baron, :allie_feeder, :snowball, :temps_vivant, :dmg_tower, :gold_share, :mvp, :ecart_gold_team, :ka, to_timestamp(:date), :time_first_death, :dmgsurgold, :ecart_gold_individuel, :ecart_gold_min,
            :split, :skillshot_dodged, :temps_cc, :spells_used, :buffs_voles, :s1cast, :s2cast, :s3cast, :s4cast, :horde, :moba, :kills_min, :deaths_min, :assists_min, :ecart_cs, :petales_sanglants, :atakhan, :crit_dmg, :immobilisation, :skillshot_hit, :temps_cc_inflige, :tower, :inhib,
            :dmg_true_all, :dmg_true_all_min, :dmg_ad_all, :dmg_ad_all_min, :dmg_ap_all, :dmg_ap_all_min, :dmg_all, :dmg_all_min, :records, :longue_serie_kills, :ecart_kills, :ecart_deaths, :ecart_assists, :ecart_dmg, :trade_efficience, :skillshots_dodge_min, :skillshot_hit_min, :dmg_par_kills,
            :first_tower_time, :hardcarry, :teamcarry, :killsratio, :deathsratio, :solokillsratio);
            UPDATE tracker SET riot_id= :riot_id, riot_tagline= :riot_tagline where id_compte = :joueur;
            INSERT INTO public.matchs_updated(match_id, joueur, updated)
            VALUES (:match_id, :joueur, true);
            UPDATE prev_lol SET match_id = :match_id where riot_id = :riot_id and riot_tag = :riot_tagline and match_id = '';
            UPDATE prev_lol_features SET match_id = :match_id where riot_id = :riot_id and riot_tag = :riot_tagline and match_id = '' ''',
            self._get_match_params()
        )

    def _get_match_params(self):
        """Retourne les paramètres pour l'insertion du match."""
        return {
            'match_id': self.last_match,
            'joueur': self.id_compte,
            'role': self.thisPosition,
            'champion': self.thisChampName,
            'kills': self.thisKills,
            'assists': self.thisAssists,
            'deaths': self.thisDeaths,
            'double': self.thisDouble,
            'triple': self.thisTriple,
            'quadra': self.thisQuadra,
            'penta': self.thisPenta,
            'result': self.thisWinBool,
            'team_kills': self.thisTeamKills,
            'team_deaths': self.thisTeamKillsOp,
            'time': self.thisTime,
            'dmg': self.thisDamageNoFormat,
            'dmg_ad': self.thisDamageADNoFormat,
            'dmg_ap': self.thisDamageAPNoFormat,
            'dmg_true': self.thisDamageTrueNoFormat,
            'vision_score': self.thisVision,
            'cs': self.thisMinion,
            'cs_jungle': self.thisJungleMonsterKilled,
            'vision_pink': self.thisPink,
            'vision_wards': self.thisWards,
            'vision_wards_killed': self.thisWardsKilled,
            'gold': self.thisGoldNoFormat,
            'cs_min': self.thisMinionPerMin,
            'vision_min': self.thisVisionPerMin,
            'gold_min': self.thisGoldPerMinute,
            'dmg_min': self.thisDamagePerMinute,
            'solokills': self.thisSoloKills,
            'dmg_reduit': self.thisDamageSelfMitigated,
            'heal_total': self.thisTotalHealed,
            'heal_allies': self.thisTotalOnTeammates,
            'serie_kills': self.thisKillingSprees,
            'cs_dix_min': self.thisCSafter10min,
            'jgl_dix_min': self.thisJUNGLEafter10min,
            'baron': self.thisBaronTeam,
            'drake': self.thisDragonTeam,
            'team': self.team,
            'herald': self.thisHeraldTeam,
            'cs_max_avantage': self.thisCSAdvantageOnLane,
            'level_max_avantage': self.thisLevelAdvantage,
            'afk': self.AFKTeamBool,
            'vision_avantage': self.thisVisionAdvantage,
            'early_drake': self.earliestDrake,
            'temps_dead': self.thisTimeSpendDead,
            'item1': self.thisItems[0],
            'item2': self.thisItems[1],
            'item3': self.thisItems[2],
            'item4': self.thisItems[3],
            'item5': self.thisItems[4],
            'item6': self.thisItems[5],
            'kp': self.thisKP,
            'kda': self.kda_save,
            'mode': self.thisQ,
            'season': self.season,
            'date': int(self.timestamp),
            'damageratio': self.thisDamageRatio,
            'tankratio': self.thisDamageTakenRatio,
            'rank': self.thisRank,
            'tier': self.thisTier,
            'lp': self.thisLP,
            'id_participant': self.thisId,
            'dmg_tank': self.thisDamageTakenNoFormat,
            'shield': self.thisTotalShielded,
            'early_baron': self.earliestBaron,
            'allie_feeder': self.thisAllieFeeder,
            'snowball': self.snowball,
            'temps_vivant': self.thisTimeSpendAlive,
            'dmg_tower': self.thisDamageTurrets,
            'gold_share': self.gold_share,
            'mvp': self.mvp,
            'ecart_gold_team': self.ecart_gold_team,
            'ka': self.thisKills + self.thisAssists,
            'time_first_death': self.thisTimeLiving,
            'dmgsurgold': self.DamageGoldRatio,
            'ecart_gold_individuel': self.ecart_gold_noformat,
            'ecart_gold_min': self.ecart_gold_permin,
            'riot_id': self.riot_id.lower(),
            'riot_tagline': self.riot_tag,
            'split': self.split,
            'skillshot_dodged': self.thisSkillshot_dodged,
            'temps_cc': self.time_CC,
            'spells_used': self.thisSpellUsed,
            'buffs_voles': self.thisbuffsVolees,
            's1cast': self.s1cast,
            's2cast': self.s2cast,
            's3cast': self.s3cast,
            's4cast': self.s4cast,
            'horde': self.thisHordeTeam,
            'moba': self.moba_ok,
            'kills_min': self.kills_min,
            'deaths_min': self.deaths_min,
            'assists_min': self.assists_min,
            'ecart_cs': self.ecart_cs_noformat,
            'petales_sanglants': self.petales_sanglants,
            'atakhan': self.thisAtakhanTeam,
            'crit_dmg': self.largest_crit,
            'immobilisation': self.enemy_immobilisation,
            'skillshot_hit': self.thisSkillshot_hit,
            'temps_cc_inflige': self.totaltimeCCdealt,
            'tower': self.thisTowerTeam,
            'inhib': self.thisInhibTeam,
            'dmg_true_all': self.thisDamageTrueAllNoFormat,
            'dmg_true_all_min': self.thisDamageTrueAllPerMinute,
            'dmg_ad_all': self.thisDamageADAllNoFormat,
            'dmg_ad_all_min': self.thisDamageADAllPerMinute,
            'dmg_ap_all': self.thisDamageAPAllNoFormat,
            'dmg_ap_all_min': self.thisDamageAPAllPerMinute,
            'dmg_all': self.thisDamageAllNoFormat,
            'dmg_all_min': self.thisDamageAllPerMinute,
            'records': True,
            'longue_serie_kills': self.thisKillsSeries,
            'ecart_kills': self.ecart_kills,
            'ecart_deaths': self.ecart_morts,
            'ecart_assists': self.ecart_assists,
            'ecart_dmg': self.ecart_dmg,
            'trade_efficience': self.trade_efficience,
            'skillshots_dodge_min': self.thisSkillshot_dodged_per_min,
            'skillshot_hit_min': self.thisSkillshot_hit_per_min,
            'dmg_par_kills': self.damage_per_kills,
            'first_tower_time': self.first_tower_time,
            'hardcarry': int(self.carry_points),
            'teamcarry': int(self.team_points),
            'killsratio': self.killsratio,
            'deathsratio': self.deathsratio,
            'solokillsratio': self.solokillsratio
        }

    def _insert_participant_data(self):
        """Insère les données des participants."""
        if self.thisQ not in ['ARENA 2v2', 'OTHER']:
            for i in range(10):
                try:
                    team = 'allie' if i < 5 else 'ennemi'
                    position = str(i % 5 + 1)
                    joueur = f"{self.thisRiotIdListe[i]}#{self.thisRiotTagListe[i]}"
                    tier = self.liste_rank[i]
                    div = self.liste_tier[i]
                    champion = self.thisChampNameListe[i]

                    requete_perso_bdd(
                        '''INSERT INTO match_participant (
                        match_id, team, position, joueur, tier, div, champion,
                        tierallie_avg, divallie_avg, tierennemy_avg, divennemy_avg
                        ) VALUES (
                        :match_id, :team, :position, :joueur, :tier, :div, :champion,
                        :tierallie_avg, :divallie_avg, :tierennemy_avg, :divennemy_avg
                        );''',
                        {
                            'match_id': self.last_match,
                            'team': team,
                            'position': position,
                            'joueur': joueur,
                            'tier': tier,
                            'div': div,
                            'champion': champion,
                            'tierallie_avg': self.avgtier_ally,
                            'divallie_avg': self.avgrank_ally,
                            'tierennemy_avg': self.avgtier_enemy,
                            'divennemy_avg': self.avgrank_enemy
                        }
                    )
                except sqlalchemy.exc.IntegrityError:
                    continue

    def _insert_other_match_data(self):
        """Insère les données additionnelles du match."""
        if self.thisQ not in ['ARENA 2v2', 'OTHER']:
            requete_perso_bdd(
                '''INSERT INTO matchs_autres(
                match_id, vision1, vision2, vision3, vision4, vision5, vision6, vision7, vision8, vision9, vision10,
                pink1, pink2, pink3, pink4, pink5, pink6, pink7, pink8, pink9, pink10,
                ecart_gold_top, ecart_gold_jgl, ecart_gold_mid, ecart_gold_adc, ecart_gold_supp)
                VALUES (:match_id, :v1, :v2, :v3, :v4, :v5, :v6, :v7, :v8, :v9, :v10,
                :p1, :p2, :p3, :p4, :p5, :p6, :p7, :p8, :p9, :p10,
                :ecart_top, :ecart_jgl, :ecart_mid, :ecart_adc, :ecart_supp)
                ON CONFLICT (match_id)
                DO NOTHING;''',
                {
                    'match_id': self.last_match,
                    'v1': self.thisVisionListe[0], 'v2': self.thisVisionListe[1],
                    'v3': self.thisVisionListe[2], 'v4': self.thisVisionListe[3],
                    'v5': self.thisVisionListe[4], 'v6': self.thisVisionListe[5],
                    'v7': self.thisVisionListe[6], 'v8': self.thisVisionListe[7],
                    'v9': self.thisVisionListe[8], 'v10': self.thisVisionListe[9],
                    'p1': self.thisPinkListe[0], 'p2': self.thisPinkListe[1],
                    'p3': self.thisPinkListe[2], 'p4': self.thisPinkListe[3],
                    'p5': self.thisPinkListe[4], 'p6': self.thisPinkListe[5],
                    'p7': self.thisPinkListe[6], 'p8': self.thisPinkListe[7],
                    'p9': self.thisPinkListe[8], 'p10': self.thisPinkListe[9],
                    'ecart_top': self.ecart_top_gold,
                    'ecart_jgl': self.ecart_jgl_gold,
                    'ecart_mid': self.ecart_mid_gold,
                    'ecart_adc': self.ecart_adc_gold,
                    'ecart_supp': self.ecart_supp_gold
                }
            )

    def _insert_points_data(self):
        """Insère les données de points."""
        params = {'match_id': self.last_match}
        
        for i in range(10):
            riot_id = self.thisRiotIdListe[i].lower()
            params[f'hardcarry{i+1}'] = self.dict_serie.get(riot_id, {}).get('carry_points', -1)
            params[f'teamcarry{i+1}'] = self.dict_serie.get(riot_id, {}).get('team_points', -1)

        requete_perso_bdd(
            '''INSERT INTO matchs_points(
            match_id, hardcarry1, hardcarry2, hardcarry3, hardcarry4, hardcarry5,
            hardcarry6, hardcarry7, hardcarry8, hardcarry9, hardcarry10,
            teamcarry1, teamcarry2, teamcarry3, teamcarry4, teamcarry5,
            teamcarry6, teamcarry7, teamcarry8, teamcarry9, teamcarry10)
            VALUES (:match_id, :hardcarry1, :hardcarry2, :hardcarry3, :hardcarry4, :hardcarry5,
            :hardcarry6, :hardcarry7, :hardcarry8, :hardcarry9, :hardcarry10,
            :teamcarry1, :teamcarry2, :teamcarry3, :teamcarry4, :teamcarry5,
            :teamcarry6, :teamcarry7, :teamcarry8, :teamcarry9, :teamcarry10)
            ON CONFLICT (match_id)
            DO NOTHING;''',
            params
        )

    def sauvegarde_embed(self, embed):
    
        pickle_embed = pickle.dumps(embed)
        
        try:
            requete_perso_bdd('''INSERT INTO match_embed (match_id, joueur, data) VALUES (:match_id, :joueur, :data) ''',
                            dict_params={'match_id' : self.last_match, 'joueur' : self.id_compte, 'data' : pickle_embed})
        except IntegrityError:
            pass