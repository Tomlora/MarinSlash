"""
Classe matchlol - Partie 3: Préparation des données externes (UGG, Mobalytics).
"""

import pickle
import numpy as np
import pandas as pd

from fonctions.api_calls import getPlayerStats, getRanks, update_ugg, get_role, get_player_match_history
from fonctions.api_moba import (
    update_moba, get_mobalytics, get_player_match_history_moba,
    get_role_stats, get_wr_ranked, detect_win_streak,
    get_stat_champion_by_player_mobalytics, get_rank_moba
)
from fonctions.gestion_bdd import lire_bdd_perso
from .masteries import get_stat_champion_by_player


class ExternalDataMixin:
    """Mixin pour la récupération des données externes (UGG, Mobalytics)."""

    async def prepare_data_moba(self):
        """Prépare les données depuis Mobalytics."""
        self.liste_rank = []
        self.liste_tier = []
        self.liste_lp = []
        self.winrate_joueur = {}
        self.winrate_champ_joueur = {}
        self.role_pref = {}
        self.all_role = {}
        self.role_count = {}
        self.dict_serie = {}

        print(self.thisRiotIdListe)
        print(self.thisRiotTagListe)
        print(self.last_match[5:])        

        if self.activate_mobalytics == 'True':
            # On update le profil mobalytics pour chaque joueur
            for riot_id, riot_tag in zip(self.thisRiotIdListe, self.thisRiotTagListe):
                await update_moba(self.session, riot_id, riot_tag)
            try:
                self.data_mobalytics_complete = await get_mobalytics(f'{self.riot_id}#{self.riot_tag}', self.session, int(self.last_match[5:]))
                print(self.data_mobalytics_complete)
                self.moba_ok = True
            except:
                self.moba_ok = False
        else:
            self.moba_ok = False

        self.model = pickle.load(open('model/scoring_rf.pkl', 'rb'))
        print('Statut moba', self.moba_ok)
        if self.moba_ok:

            try:
                self.avgtier_ally = self.data_mobalytics_complete['data']['lol']['player']['match']['teams'][self.n_moba]['avgTier']['tier']
                self.avgrank_ally = self.data_mobalytics_complete['data']['lol']['player']['match']['teams'][self.n_moba]['avgTier']['division']

                self.avgtier_enemy = self.data_mobalytics_complete['data']['lol']['player']['match']['teams'][self.team]['avgTier']['tier']
                self.avgrank_enemy = self.data_mobalytics_complete['data']['lol']['player']['match']['teams'][self.team]['avgTier']['division']


            except TypeError:
                self.avgtier_ally = ''
                self.avgrank_ally = ''

                self.avgtier_enemy = ''
                self.avgrank_enemy = ''

            for i in range(self.nb_joueur):
                riot_id = self.thisRiotIdListe[i].lower()
                riot_tag = self.thisRiotTagListe[i].lower()
                pseudo = f"{riot_id}#{riot_tag}"
                
                print(riot_id)
                print(riot_tag)

                # --- RANK ET TIER ---
                try:
                    tier, rank, lp = await get_rank_moba(self.session, riot_id, riot_tag)
                    print('tier', tier)
                    print('rank', rank)
                except Exception:
                    rank = ''
                    tier = ''
                    lp = 0
                self.liste_rank.append(rank)
                self.liste_tier.append(tier)
                self.liste_lp.append(lp)

                # --- WINRATE GLOBAL ---
                try:
                    wr_res = await get_wr_ranked(self.session, riot_id, riot_tag)
                    stats = wr_res['data']['lol']['player']['queuesStats']['items']
                    ranked_stats = next((q for q in stats if q.get('virtualQueue', '') == 'RANKED_SOLO'), None)
                    if ranked_stats:
                        wr = int(round(ranked_stats.get('winrate', 0) * 100))
                        nbgames = ranked_stats.get('gamesCount', 0)
                    else:
                        wr, nbgames = 0, 0
                except Exception:
                    wr, nbgames = 0, 0
                self.winrate_joueur[pseudo] = {'winrate': wr, 'nbgames': nbgames}

                try:
                    self.df_data_stat = await get_stat_champion_by_player_mobalytics(self.session, riot_id, riot_tag)
                    self.df_data_stat['championId'] = self.df_data_stat['championId'].astype(str).replace(self.champ_dict)

                    champ_name = self.thisChampNameListe[i]
                    dict_data_stat = ''

                    if champ_name and not self.df_data_stat.empty and self.df_data_stat['totalMatches'].sum() > 30:
                        filtered = self.df_data_stat[self.df_data_stat['championId'] == champ_name].copy()
                        self.df_data_stat['poids_games'] = (self.df_data_stat['totalMatches'] / self.df_data_stat['totalMatches'].sum() * 100).astype(int)

                        if not filtered.empty:
                            filtered['winrate'] = (filtered['wins'] / filtered['totalMatches'] * 100).astype(int)
                            filtered['poids_games'] = (filtered['totalMatches'] / self.df_data_stat['totalMatches'].sum() * 100).astype(int)
                            filtered['kda'] = np.round(
                                (filtered['kills'] + filtered['assists']) / filtered['deaths'].replace(0, 1), 2
                            )
                            dict_data_stat = filtered.to_dict(orient='records')[0]
                        else:
                            dict_data_stat = {
                                'championId': champ_name,
                                'totalMatches': 1,
                                'poids_games': 0,
                                'winrate': 50
                            }
                except Exception:
                    dict_data_stat = ''

                self.winrate_champ_joueur[pseudo] = dict_data_stat


                # --- ROLE PREF ---
                try:
                    data_pref_role = await get_role_stats(self.session, self.thisRiotIdListe[i], self.thisRiotTagListe[i])
                    if not data_pref_role.empty:
                        data_pref_role = data_pref_role.sort_values('poids_role', ascending=False)
                        self.role_pref[riot_id] = {
                            'main_role': data_pref_role.iloc[0]['role'],
                            'poids_role': int(data_pref_role.iloc[0]['poids_role'])
                        }
                        # self.all_role[riot_id] = data_pref_role.to_dict('index')
                        # On ne garde que RANKED_SOLO
                        role_df = data_pref_role.copy()
                        # Normalise les noms de rôle et les mets en minuscule
                        role_df['role'] = role_df['role'].str.lower()

                        # Rôles de League standards
                        roles_standard = ['top', 'jungle', 'mid', 'adc', 'support']

                        # Construction du mapping
                        role_dict = {}
                        total_games = role_df['nbgames'].sum() if not role_df.empty else 0
                        for role in roles_standard:
                            if role in role_df['role'].values:
                                row = role_df[role_df['role'] == role].iloc[0]
                                game_count = int(row['nbgames'])
                                win_count = int(row['wins'])
                                poids = int(round((game_count / total_games * 100))) if total_games > 0 else 0
                            else:
                                game_count = 0
                                win_count = 0
                                poids = 0
                            role_dict[role] = {
                                'gameCount': game_count,
                                'winCount': win_count,
                                'poids': poids
                            }

                        self.all_role[riot_id] = role_dict

                        self.role_count[riot_id] = int(data_pref_role['nbgames'].sum())
                    else:
                        self.role_pref[riot_id] = {'main_role': '', 'poids_role': 0}
                        self.all_role[riot_id] = {}
                        self.role_count[riot_id] = 0
                except Exception:
                    self.role_pref[riot_id] = {'main_role': '', 'poids_role': 0}
                    self.all_role[riot_id] = {}
                    self.role_count[riot_id] = 0

                # --- SERIE WIN/LOSE ---
                try:
                    match_history = await get_player_match_history_moba(
                        self.session,
                        riot_id,
                        riot_tag,
                        top=20
                    )
                    serie = detect_win_streak(match_history, self.thisRiotIdListe[i], self.thisRiotTagListe[i])
                    self.dict_serie[riot_id] = serie
                except Exception:
                    self.dict_serie[riot_id] = {'mot': '', 'count': 0}

                # --- POINTS (pas dans Mobalytics, on laisse à -1 comme UGG) ---
                self.dict_serie[riot_id]['carry_points'] = -1
                self.dict_serie[riot_id]['team_points'] = -1
                self.dict_serie[riot_id]['points'] = -1

        # Variables principales du joueur (inchangées)
        stats_mode = "RANKED_FLEX_SR" if self.thisQ == 'FLEX' else "RANKED_SOLO_5x5"
        try:
            for i in range(len(self.thisStats)):
                if str(self.thisStats[i]['queueType']) == stats_mode:
                    self.i = i
                    break
            self.thisWinrate = int(self.thisStats[self.i]['wins']) / (
                int(self.thisStats[self.i]['wins']) + int(self.thisStats[self.i]['losses']))
            self.thisWinrateStat = str(int(self.thisWinrate * 100))
            self.thisRank = str(self.thisStats[self.i]['rank'])
            self.thisTier = str(self.thisStats[self.i]['tier'])
            self.thisLP = str(self.thisStats[self.i]['leaguePoints'])
            self.thisVictory = str(self.thisStats[self.i]['wins'])
            self.thisLoose = str(self.thisStats[self.i]['losses'])
            self.thisWinStreak = str(self.thisStats[self.i]['hotStreak'])
        except (IndexError, AttributeError):
            self.thisWinrate = '0'
            self.thisWinrateStat = '0'
            self.thisRank = 'En placement'
            self.thisTier = " "
            self.thisLP = '0'
            self.thisVictory = '0'
            self.thisLoose = '0'
            self.thisWinStreak = '0'
        except KeyError:
            if self.thisQ == 'ARAM':
                self.thisWinrate = '0'
                self.thisWinrateStat = '0'
                self.thisRank = 'Inconnu'
                self.thisTier = " "
                self.thisLP = '0'
                self.thisVictory = '0'
                self.thisLoose = '0'
                self.thisWinStreak = '0'
            else:
                data_joueur = lire_bdd_perso(f'SELECT * from suivi_s{self.season} where index = {self.id_compte}').T
                self.thisWinrate = int(data_joueur['wins'].values[0]) / (
                    int(data_joueur['wins'].values[0]) + int(data_joueur['losses'].values[0]))
                self.thisWinrateStat = str(int(self.thisWinrate * 100))
                self.thisRank = str(data_joueur['rank'].values[0])
                self.thisTier = str(data_joueur['tier'].values[0])
                self.thisLP = str(data_joueur['LP'].values[0])
                self.thisVictory = str(data_joueur['wins'].values[0])
                self.thisLoose = str(data_joueur['losses'].values[0])
                self.thisWinStreak = str(data_joueur['serie'].values[0])


        self.carry_points = -1
        self.team_points = -1

    async def prepare_data_ugg(self):
        """Prépare les données depuis UGG."""
        self.liste_rank = []
        self.liste_tier = []
        
        self.winrate_joueur = {}
        
        self.winrate_champ_joueur = {}
        

        self.avgtier_ally = ''
        self.avgrank_ally = ''

        self.avgtier_enemy = ''
        self.avgrank_enemy = ''       
        
        self.role_pref = {}
        self.all_role = {}
        self.role_count = {}
        self.dict_serie = {}
        
        for i in range(self.nb_joueur):
            
            if self.ugg == 'True':
                try:
                    success = await update_ugg(self.session, self.thisRiotIdListe[i].lower(), self.thisRiotTagListe[i].lower())
                except:
                    pass
                

            

            self.data_rank = await getRanks(self.session, self.thisRiotIdListe[i].lower(), self.thisRiotTagListe[i].lower(), season=self.season_ugg)

 
 
            
            if self.data_rank != '': 
                try:
                    self.df_rank = pd.DataFrame(self.data_rank['data']['fetchProfileRanks']['rankScores'])
                except TypeError:
                    self.df_rank = ''
            
            self.df_data_stat = await get_stat_champion_by_player(self.session, self.champ_dict, self.thisRiotIdListe[i].lower(), self.thisRiotTagListe[i].lower(), self.list_season_ugg)

           
            if isinstance(self.df_data_stat, pd.DataFrame):



                self.df_data_stat['poids_games'] = (self.df_data_stat['totalMatches'] / self.df_data_stat['totalMatches'].sum() * 100).astype(int)


                self.df_data_stat = self.df_data_stat[self.df_data_stat['championId'] == self.thisChampNameListe[i]]

                if self.df_data_stat.empty:
                    dict_data_stat = ''
                else:
                    try:
                        self.df_data_stat['kda'] = np.round((self.df_data_stat['kills'] + self.df_data_stat['assists']) /  self.df_data_stat['deaths'],2)
                    except ZeroDivisionError:
                        self.df_stat_kda['kda'] = np.round((self.df_data_stat['kills'] + self.df_data_stat['assists']) /  1,2)
                    dict_data_stat = self.df_data_stat.to_dict(orient='records')[0]
            else:
                dict_data_stat = ''
            

            try:
                if isinstance(self.df_rank, pd.DataFrame):
                    nbgames = self.df_rank.loc[self.df_rank['queueType'] == 'ranked_solo_5x5']['wins'].values[0] + self.df_rank.loc[self.df_rank['queueType'] == 'ranked_solo_5x5']['losses'].values[0]
                    wr = round((self.df_rank.loc[self.df_rank['queueType'] == 'ranked_solo_5x5']['wins'].values[0] / nbgames) * 100)
                else:
                    nbgames = 0
                    wr = 0
            except IndexError:
                wr = 0
                nbgames = 0
            except AttributeError:
                wr = 0
                nbgames = 0
            
            self.winrate_joueur[f'{self.thisRiotIdListe[i].lower()}#{self.thisRiotTagListe[i].upper()}'] = {'winrate' : wr, 'nbgames' : nbgames}
            self.winrate_champ_joueur[f'{self.thisRiotIdListe[i].lower()}#{self.thisRiotTagListe[i].upper()}'] = dict_data_stat
            


            try:
                rank_joueur = self.df_rank.loc[self.df_rank['queueType'] == 'ranked_solo_5x5']['tier'].values[0]
                tier_joueur = self.df_rank.loc[self.df_rank['queueType'] == 'ranked_solo_5x5']['rank'].values[0]
                self.liste_rank.append(rank_joueur)
                self.liste_tier.append(tier_joueur)
                    
            except:
                self.liste_rank.append('')
                self.liste_tier.append('')

            ###

            self.data_pref_role = await get_role(self.session, self.thisRiotIdListe[i].lower(), self.thisRiotTagListe[i].lower())

            if isinstance(self.data_pref_role, dict):

                try:

                    self.df_pref_role = pd.DataFrame(self.data_pref_role).T
                    self.df_pref_role['poids'] = (self.df_pref_role['gameCount'] / self.df_pref_role['gameCount'].sum() * 100).astype(int)
                    self.df_pref_role.sort_values('poids', ascending=False, inplace=True)

                    self.role_pref[self.thisRiotIdListe[i].lower()] = {'main_role' : self.df_pref_role.index[0], 'poids_role' : self.df_pref_role.iloc[0]['poids']}

                    self.all_role[self.thisRiotIdListe[i].lower()] = self.df_pref_role.to_dict('index')

                    self.role_count[self.thisRiotIdListe[i].lower()] = self.df_pref_role['gameCount'].sum()
                
                except pd.errors.IntCastingNaNError:
                    continue


            
            ## Detection Serie de Victoire / Defaite + Calcul Score

            self.df_data = await get_player_match_history(self.session, self.thisRiotIdListe[i].lower(), self.thisRiotTagListe[i], seasonIds=[self.season_ugg])

            # Vérifie si self.df_data existe et contient les données attendues
            try:
                self.df_data_match_history = pd.DataFrame(self.df_data['data']['fetchPlayerMatchSummaries']['matchSummaries'])
                self.df_data_match_history = self.df_data_match_history[self.df_data_match_history['queueType'] == 'ranked_solo_5x5'] # seuls les matchs classés
                self.df_data_match_history['matchCreationTime'] = pd.to_datetime(self.df_data_match_history['matchCreationTime'], unit='ms')

                #### Serie de wins/loses

                # Première valeur
                win_lose = self.df_data_match_history['win'].iloc[0]

                # Compter combien de fois cette valeur apparaît consécutivement depuis le début
                count = (self.df_data_match_history['win'] == win_lose).cumprod().sum()

                mot =  "Victoire" if win_lose else "Defaite"

                self.dict_serie[self.thisRiotIdListe[i].lower()] = {'mot' : mot, 'count' : count}
            except (TypeError, KeyError):
                # Si pas de données, on met une valeur par défaut
                self.dict_serie[self.thisRiotIdListe[i].lower()] = {'mot': '', 'count': 0}


            #### Points 

            try:

                self.df_data_match = self.df_data_match_history[self.df_data_match_history['matchId'] == int(self.last_match[5:])]

                if not self.df_data_match.empty:
                    self.carry_points = self.df_data_match['psHardCarry'].values[0] 
                    self.team_points = self.df_data_match['psTeamPlay'].values[0]
                
                else:
                    self.carry_points = -1
                    self.team_points = -1

                
                self.dict_serie[self.thisRiotIdListe[i].lower()]['carry_points'] = int(self.carry_points)
                self.dict_serie[self.thisRiotIdListe[i].lower()]['team_points'] = int(self.team_points)
                self.dict_serie[self.thisRiotIdListe[i].lower()]['points'] = (self.carry_points + self.team_points) / 2

            except:
                self.df_data_match = pd.DataFrame([])
                self.carry_points = -1
                self.team_points = -1
                self.dict_serie[self.thisRiotIdListe[i].lower()]['carry_points'] = int(self.carry_points)
                self.dict_serie[self.thisRiotIdListe[i].lower()]['team_points'] = int(self.team_points)
                self.dict_serie[self.thisRiotIdListe[i].lower()]['points'] = (self.carry_points + self.team_points) / 2