import ast
from fonctions.match import get_summoner_by_name, my_region, get_challenges_config, api_key_lol
import pandas as pd
import aiohttp
from fonctions.gestion_bdd import lire_bdd_perso, sauvegarde_bdd, requete_perso_bdd
from fonctions.match import emote_rank_discord
from interactions import Embed
import humanize


async def get_challenges_data_joueur(session, puuid):
    async with session.get(f'https://{my_region}.api.riotgames.com/lol/challenges/v1/player-data/{puuid}?api_key={api_key_lol}') as challenge_joueur:
        data_joueur = await challenge_joueur.json()
        return data_joueur
    
def extraire_variables_imbriquees(df, colonne):
    df[colonne] = [ast.literal_eval(str(item))
                   for index, item in df[colonne].iteritems()]

    df = pd.concat([df.drop([colonne], axis=1),
                   df[colonne].apply(pd.Series)], axis=1)
    return df


async def get_data_challenges(session):
    data_challenges = await get_challenges_config(session)
    data_challenges = pd.DataFrame(data_challenges)
    data_challenges = extraire_variables_imbriquees(
        data_challenges, 'localizedNames')
    data_challenges = data_challenges[['id', 'state', 'thresholds', 'fr_FR']]
    data_challenges = extraire_variables_imbriquees(data_challenges, 'fr_FR')
    data_challenges = extraire_variables_imbriquees(
        data_challenges, 'thresholds')
    data_challenges = data_challenges[['id', 'state', 'name', 'shortDescription', 'description', 'IRON', 'BRONZE',
                                       'SILVER', 'GOLD', 'PLATINUM', 'DIAMOND', 'MASTER', 'GRANDMASTER', 'CHALLENGER']]  # on change l'ordre
    return data_challenges


async def get_data_joueur_challenges(id_compte: int, session, puuid=None):
    

    data_joueur = await get_challenges_data_joueur(session, puuid)
    data_total_joueur = dict()

    data_total_joueur[id_compte] = data_joueur['totalPoints']  # dict

    data_joueur_category = pd.DataFrame(data_joueur['categoryPoints'])

    data_joueur_challenges = pd.DataFrame(data_joueur['challenges'])
    # on ajoute le joueur
    data_joueur_category.insert(0, "Joueur", id_compte)
    data_joueur_challenges.insert(0, "Joueur", id_compte)

    if data_joueur_challenges.empty:  # si le dataset est vide, on fait rien.
        return 0, 0, 0

    try:  # certains joueurs n'ont pas ces colonnes... impossible de dire pourquoi
        data_joueur_challenges.drop(
            ['playersInLevel', 'achievedTime'], axis=1, inplace=True)
    except KeyError:
        data_joueur_challenges.drop(['achievedTime'], axis=1, inplace=True)

    data_challenges = await get_data_challenges(session)
    # on fusionne en fonction de l'id :
    data_joueur_challenges = data_joueur_challenges.merge(
        data_challenges, left_on="challengeId", right_on='id')
    # on a besoin de savoir ce qui est le mieux dans les levels : on va donc créer une variable chiffrée représentatif de chaque niveau :

    dict_rankid_challenges = {"NONE": 0,
                              "IRON": 1,
                              "BRONZE": 2,
                              "SILVER": 3,
                              "GOLD": 4,
                              "PLATINUM": 5,
                              "DIAMOND": 6,
                              "MASTER": 7,
                              "GRANDMASTER": 8,
                              "CHALLENGER": 9
                              }
    data_joueur_challenges['level_number'] = data_joueur_challenges['level'].map(
        dict_rankid_challenges)

    try:  # si erreur, le joueur n'a aucun classement
        data_joueur_challenges['position'].fillna(0, inplace=True)
    except:
        data_joueur_challenges['position'] = 0

    # on retient ce qu'il nous intéresse
    data_joueur_challenges[['Joueur', 'challengeId', 'name', 'value', 'percentile', 'level', 'level_number', 'state', 'position',
                            'shortDescription', 'description', 'IRON', 'BRONZE', 'SILVER', 'GOLD', 'PLATINUM', 'DIAMOND', 'MASTER', 'GRANDMASTER', 'CHALLENGER']]
    data_joueur_challenges = data_joueur_challenges.reindex(columns=['Joueur', 'challengeId', 'name', 'value', 'percentile', 'level', 'level_number',
                                                            'state',  'position', 'shortDescription', 'description', 'IRON', 'BRONZE', 'SILVER', 'GOLD', 'PLATINUM', 'DIAMOND', 'MASTER', 'GRANDMASTER', 'CHALLENGER'])
    data_challenge = data_joueur_challenges[['name', 'challengeId', 'state', 'shortDescription', 'description', 'IRON', 'BRONZE', 'SILVER', 'GOLD', 'PLATINUM', 'DIAMOND', 'MASTER', 'GRANDMASTER', 'CHALLENGER']]
    data_joueur_to_save = data_joueur_challenges.drop(['name', 'state', 'shortDescription', 'description', 'IRON', 'BRONZE', 'SILVER', 'GOLD', 'PLATINUM', 'DIAMOND', 'MASTER', 'GRANDMASTER', 'CHALLENGER'], axis=1)
    
    # on verifie que les challenges n'existent pas déjà dans la bdd, sinon on les ajoute
    
    data_actuel = lire_bdd_perso('''SELECT index, name from challenges''').transpose()
    
    data_challenge = data_challenge[~data_challenge['name'].isin(data_actuel['name'])]
    
    if not data_challenge.empty:
        sauvegarde_bdd(data_challenge, 'challenges', 'append', index=False)
    return data_total_joueur, data_joueur_category, data_joueur_challenges, data_joueur_to_save



class challengeslol():

    def __init__(self,
                 id_compte,
                 puuid=None,
                 session:aiohttp.ClientSession=None,
                 nb_challenges:int=8):
        """Class pour traiter les matchs

        Parameters
        ----------
        summonerName : `str`
            nom d'un joueur lol
        """
        self.id_compte = id_compte
        self.puuid = puuid
        self.session = session
        self.category = ['CRISTAL', 'IMAGINATION', 'EXPERTISE', 'VÉTÉRANCE', "TRAVAIL D'ÉQUIPE"]
        self.langue = 'fr_FR'
        self.nb_challenges = nb_challenges
        
        try:
            humanize.activate(self.langue, path='C:/Users/Kevin/PycharmProjects/bot_discord_aio/translations/')
        except FileNotFoundError:
            humanize.i18n.activate(self.langue)
        
    async def preparation_data(self):
        

        self.puuid = self.puuid
        
        if self.session == None:
            self.session = aiohttp.ClientSession()
        else:
            self.session = self.session
            
        self.data_total, self.data_category, self.data_joueur, self.data_to_save = await get_data_joueur_challenges(self.id_compte, self.session, self.puuid)
        
        self.rank_total = self.data_total[self.id_compte]['level']
        self.points_total = self.data_total[self.id_compte]['current']
        self.percentile_total = self.data_total[self.id_compte]['percentile']*100
        
    async def sauvegarde(self):
        if isinstance(self.data_to_save, pd.DataFrame):
            requete_perso_bdd(f'''DELETE FROM challenges_data where "Joueur" = {self.id_compte};
                              DELETE FROM challenges_category where "Joueur" = {self.id_compte};
                              DELETE FROM challenges_total where "index" = {self.id_compte} ''')
            sauvegarde_bdd(self.data_total, 'challenges_total', 'append')
            sauvegarde_bdd(self.data_category, 'challenges_category', 'append')
            sauvegarde_bdd(self.data_to_save, 'challenges_data', 'append')
        
    async def comparaison(self):
       
        self.df_old_data = lire_bdd_perso(f'''SELECT "Joueur", value, percentile, level, level_number, position, challenges.* from challenges_data
                                          INNER JOIN challenges ON challenges_data."challengeId" = challenges."challengeId"
                                          where "Joueur" = {self.id_compte} ''', index_col='index')\
                                              .transpose()\
                                                  .sort_index()\
                                                      .rename(columns={'value' : 'value_precedente',
                                                                        'percentile': 'percentile_precedent',
                                                                        'level' : 'level_precedent',
                                                                        'position' : 'position_precedente'})
        
        try:
            self.points_total_before = lire_bdd_perso(f'''SELECT index, current FROM challenges_total where index = {self.id_compte} ''')\
                .loc['current', self.id_compte]
        except:
            self.points_total_before = 0
            
        self.dif_points_total = self.points_total - self.points_total_before    
        
        if not self.df_old_data.empty:
        
            self.data_comparaison = self.data_joueur.merge(self.df_old_data[['Joueur', 'challengeId', 'value_precedente', 'percentile_precedent', 'level_precedent', 'position_precedente']],
                                                        how='left',
                                                        on=['Joueur', 'challengeId'])
            
            self.data_comparaison['dif_value'] = self.data_comparaison['value'] - self.data_comparaison['value_precedente']
            self.data_comparaison['dif_percentile'] = self.data_comparaison['percentile'] - self.data_comparaison['percentile_precedent']
            self.data_comparaison['dif_level'] = (self.data_comparaison["level"] != self.data_comparaison["level_precedent"])
            self.data_comparaison['dif_position'] = self.data_comparaison["position_precedente"] - self.data_comparaison["position"]
            
            # on supprime les challenges non-désirés
            
            df_exclusion = lire_bdd_perso(f'''SELECT id, "challengeId" from challenge_exclusion where index = {self.id_compte} ''',
                                          index_col='id').transpose()
            
            if not df_exclusion.empty:
                self.data_comparaison = self.data_comparaison[~self.data_comparaison['challengeId'].isin(df_exclusion['challengeId'])]
            
            # on supprime les caractères inutiles
            
            self.data_comparaison['shortDescription'] = self.data_comparaison['shortDescription'].str.replace('.', '')
            self.data_comparaison['shortDescription'] = self.data_comparaison['shortDescription'].str.replace('compétences', 'spells')
            self.data_comparaison['shortDescription'] = self.data_comparaison['shortDescription'].str.replace('sbires', 'cs')
            self.data_comparaison['shortDescription'] = self.data_comparaison['shortDescription'].str.replace('champion', 'champ')
            self.data_comparaison['shortDescription'] = self.data_comparaison['shortDescription'].str.replace('boucliers', 'shield')
            self.data_comparaison['shortDescription'] = self.data_comparaison['shortDescription'].str.replace('jungle', 'jgl')

           
            # définir la fonction pour calculer la différence entre la valeur actuelle et la valeur à atteindre pour le palier suivant
            def difference_vers_palier_suivant(row):
                palier_actuel = row['level']
                valeur_actuelle = row['value']
                if palier_actuel == 'CHALLENGER':
                    return 0
                if palier_actuel == 'NONE':
                    return 0
                else:
                    palier_suivant = self.data_comparaison.columns[self.data_comparaison.columns.get_loc(palier_actuel) + 1] # cherche le numéro de la colonne, passe à la suivante et renvoie la colonne spécifiée
                    valeur_palier_suivant = row[palier_suivant]
                    difference = valeur_palier_suivant - valeur_actuelle
                    if difference > 0: # si la différence est négative, c'est qu'on a atteinnt le palier maximum
                        return difference
                    else:
                        return 0


            # appliquer la fonction à chaque ligne du dataframe
            self.data_comparaison['diff_vers_palier_suivant'] = self.data_comparaison.apply(difference_vers_palier_suivant, axis=1)
            self.data_comparaison['diff_vers_palier_suivant'].fillna(0, inplace=True)
            self.data_comparaison[['position_precedente', 'dif_value', 'dif_percentile', 'dif_position']] = self.data_comparaison[['position_precedente', 'dif_value', 'dif_percentile', 'dif_position']].fillna(0)
            
            self.data_comparaison.sort_values('dif_value', ascending=False, inplace=True)
            
            self.data_new_value = self.data_comparaison[self.data_comparaison['dif_value'] > 0]
            self.data_new_value['evolution'] = (self.data_new_value['value'] - self.data_new_value['value_precedente']) / self.data_new_value['value_precedente'] * 100
            self.data_new_percentile = self.data_comparaison[(self.data_comparaison['dif_percentile'] > 0.01)]
            self.data_new_level = self.data_comparaison[self.data_comparaison['dif_level'] == True]
            self.data_new_position = self.data_comparaison[self.data_comparaison['dif_position'] != 0]
            self.data_evolution = self.data_new_value.sort_values('evolution', ascending=False)
            

            
            # on ne retient pas les petites améliorations, ça n'a aucun sens
            self.data_evolution = self.data_evolution[(self.data_evolution['evolution'] > 2) & (self.data_evolution['dif_value'] > 2)]
            
            # on retire les categories de new_value et new_percentile
            
            self.data_new_value = self.data_new_value[~self.data_new_value['name'].isin(self.category)]
            # si on veut éviter des doublons : 
            # self.data_new_value = self.data_new_value[~self.data_new_value['name'].isin(self.data_evolution.head(5)['name'])]
            
            self.data_new_percentile = self.data_new_percentile[~self.data_new_percentile['name'].isin(self.category)]
            
            self.data_new_percentile.sort_values('dif_percentile', ascending=False, inplace=True)
            self.data_new_position.sort_values('dif_position', ascending=False, inplace=True)
            self.data_new_level.sort_values('level_number', ascending=False, inplace=True)
            
            
            
    
    async def embedding_discord(self, embed : Embed) -> Embed:
        
        if self.df_old_data.empty: # si on a pas les anciennes données, on ne peut pas comparer.
            return embed
        
        '''Création des embeds pour discord'''
        chunk = 1
        chunk_size = 850

        def check_chunk(texte, chunk, chunk_size):
            '''Détection pour passer à l'embed suivant'''
            if len(texte) >= chunk * chunk_size:
                    # Detection pour passer à l'embed suivant
                chunk += 1
                texte += '#'
            return texte, chunk
        
        def format_nombre(nombre):
            '''Formate les nombres pour les rendre plus lisibles'''
            try:
                if len(str(int(nombre))) <= 6 :
                    return humanize.intcomma(int(nombre)) # on met des espaces entre les milliers
                else:
                    return humanize.intword(int(nombre)).replace('million', 'M') # on transforme le nombre en mots
            except ValueError:
                return 0
        
        txt = ''
        txt_24h = '' # pour les defis qui ne sont maj que toutes les 24h
        txt_level_up = ''
        txt_evolution = ''
        
        if not self.data_new_value.empty:
            for joueur, data in self.data_new_value.head(self.nb_challenges).iterrows():
                txt, chunk = check_chunk(txt, chunk, chunk_size)
                value = format_nombre(data['value'])
                dif_value = format_nombre(data['dif_value'])
                next_palier = format_nombre(data['diff_vers_palier_suivant'])
                position = format_nombre(data['position'])
                if next_palier == str(0):
                    if position == str(0):
                        txt += f'\n:sparkles: **{data["name"]}** ({data["shortDescription"]}) [{emote_rank_discord[data["level"]]}] : \n> **{value}** (+{dif_value}) '
                    else:
                        txt += f'\n:sparkles: **{data["name"]}** ({data["shortDescription"]}) [{emote_rank_discord[data["level"]]} | **{position}**ème] : \n> **{value}** (+{dif_value}) '
                else:
                    if position == str(0):
                        txt += f'\n:sparkles: **{data["name"]}** ({data["shortDescription"]}) [{emote_rank_discord[data["level"]]}] : \n> **{value}** (+{dif_value}) :arrow_right: **{next_palier}** pour :up:'
                    else:
                        txt += f'\n:sparkles: **{data["name"]}** ({data["shortDescription"]}) [{emote_rank_discord[data["level"]]} | **{position}**ème] : \n> **{value}** (+{dif_value}) :arrow_right: **{next_palier}** pour :up:'
        
        
        if not self.data_evolution.empty and len(embed) <= 5000:
            for joueur, data in self.data_evolution.head(5).iterrows():
                if txt_evolution.count(data['name']) == 0: # on ne veut pas de doublons
                    txt_evolution, chunk = check_chunk(txt_evolution, chunk, chunk_size)
                    value = format_nombre(data['value'])
                    dif_value = format_nombre(data['dif_value'])
                    txt_evolution += f'\n:comet: **{data["name"]}** ({data["shortDescription"]}) [{emote_rank_discord[data["level"]]}] : \n> **{value}** (+{dif_value} / **+{data["evolution"]:.2f}%**)'
        
        chunk = 1      
        if not self.data_new_percentile.empty and len(embed) <= 5000:
            for joueur, data in self.data_new_percentile.head(5).iterrows():
                txt_24h, chunk = check_chunk(txt_24h, chunk, chunk_size)
                percentile = data['percentile'] * 100
                dif_percentile = data['dif_percentile'] * 100
                txt_24h += f'\n:zap: **{data["name"]}** ({data["shortDescription"]}) [{emote_rank_discord[data["level"]]}] : \n> **{percentile:.2f}%** (+{dif_percentile:.2f}%) top'
                
      
        if not self.data_new_position.empty and len(embed) <= 5500:
            for joueur, data in self.data_new_position.head(self.nb_challenges).iterrows():
                txt_24h, chunk = check_chunk(txt_24h, chunk, chunk_size)
                position = format_nombre(data['position'])
                value = format_nombre(data['value'])
                dif_value = format_nombre(data['dif_position'])
                if data['dif_position'] > 0:
                    txt_24h += f'\n:arrow_up: **{data["name"]}** ({data["shortDescription"]}) [{emote_rank_discord[data["level"]]}] : \n> **{position}**ème (**+{dif_value}**) avec **{value}**'
                else:
                    txt_24h += f'\n:arrow_down: **{data["name"]}** ({data["shortDescription"]}) [{emote_rank_discord[data["level"]]}] : \n> **{position}**ème (**{dif_value}**) avec **{value}**'
                
        chunk = 1      
        if not self.data_new_level.empty:
            for joueur, data in self.data_new_level.head(5).iterrows():
                txt_level_up, chunk = check_chunk(txt_level_up, chunk, chunk_size)
                next_palier = format_nombre(data['diff_vers_palier_suivant'])
                value = format_nombre(data['value'])
                
                if next_palier == str(0):
                    txt_level_up += f'\n:up: **{data["name"]}** ({data["shortDescription"]}) : \n> Tu es désormais **{(emote_rank_discord[data["level"]])}** avec **{value}**'
                else:
                    txt_level_up += f'\n:up: **{data["name"]}** ({data["shortDescription"]}) : \n> Tu es désormais **{(emote_rank_discord[data["level"]])}** avec **{value}** :arrow_right: **{next_palier}** pts pour :up:'
                
        
        
        def format_txt_embed(texte, chunk_size, titre, embed):
            '''Formate le texte pour l'envoyer dans un embed'''     
        
            if len(texte) <= chunk_size: # si le texte est inférieur au chunk_size, on l'envoie directement
                texte = texte.replace('#', '').replace(' #', '') # on supprime la balise qui nous servait de split
                
                if texte != '':
                    if titre == 'Challenges (Level)':
                        if self.dif_points_total != 0:
                            titre += f' | {self.points_total} pts (+{self.dif_points_total}) [{emote_rank_discord[self.rank_total]} ({self.percentile_total:.2f}%)]' 
                            # titre += f' | {self.points_total} pts [{emote_rank_discord[self.rank_total]} ({self.percentile_total:.2f}%)]' 
                        else:
                            titre += f' | {self.points_total} pts [{emote_rank_discord[self.rank_total]} ({self.percentile_total:.2f}%)]' 
                    embed.add_field(name=titre, value=texte, inline=False)
                    
            else: # si le texte est supérieur

                texte = texte.split('#')  # on split sur notre mot clé

                for i in range(len(texte)): # pour chaque partie du texte, on l'envoie dans un embed différent
                    if i == 0 and titre == 'Challenges (Level)':
                        if self.dif_points_total != 0:
                            field_name = f'{titre} | {self.points_total} pts  (+{self.dif_points_total}) [{emote_rank_discord[self.rank_total]} ({self.percentile_total:.2f}%)]' 
                            # field_name = f'{titre} | {self.points_total} pts [{emote_rank_discord[self.rank_total]} ({self.percentile_total:.2f}%)]' 
                        else:
                            field_name = f'{titre} | {self.points_total} pts [{emote_rank_discord[self.rank_total]} ({self.percentile_total:.2f}%)]'
                    elif i == 0:
                        field_name = titre
                    else:
                        field_name = f"{titre} {i + 1}"
                    field_value = texte[i]
                    # parfois la découpe renvoie un espace vide.
                    if not field_value in ['', ' ']:
                        try:
                            embed.add_field(name=field_name,
                                        value=field_value, inline=False)
                        except ValueError:
                            embed.add_field(name=field_name, value=field_value[:1000], inline=False)
            
            return embed
        
        # embed = format_txt_embed(txt, chunk_size, 'Challenges', embed)
        embed = format_txt_embed(txt_level_up, chunk_size, 'Challenges (Level)', embed)
        embed = format_txt_embed(txt_24h, chunk_size, 'Challenges (Classement)', embed)
        embed = format_txt_embed(txt_evolution, chunk_size, 'Challenges (Meilleurs progrès)', embed)
        
        
                    
        return embed
        
        