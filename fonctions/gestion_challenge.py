import ast
from fonctions.match import get_summoner_by_name, my_region, get_challenges_config, api_key_lol
import pandas as pd
import aiohttp
from fonctions.gestion_bdd import lire_bdd_perso, sauvegarde_bdd, requete_perso_bdd
from interactions import Embed


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


async def get_data_joueur_challenges(summonername: str, session, puuid=None):
    
    if puuid == None:
        me = await get_summoner_by_name(session, summonername)
        puuid = me['puuid']
    data_joueur = await get_challenges_data_joueur(session, puuid)
    data_total_joueur = dict()

    data_total_joueur[summonername] = data_joueur['totalPoints']  # dict

    data_joueur_category = pd.DataFrame(data_joueur['categoryPoints'])

    data_joueur_challenges = pd.DataFrame(data_joueur['challenges'])
    # on ajoute le joueur
    data_joueur_category.insert(0, "Joueur", summonername)
    data_joueur_challenges.insert(0, "Joueur", summonername)

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
                            'shortDescription', 'description', 'IRON', 'SILVER', 'GOLD', 'PLATINUM', 'DIAMOND', 'MASTER', 'GRANDMASTER', 'CHALLENGER']]
    data_joueur_challenges = data_joueur_challenges.reindex(columns=['Joueur', 'challengeId', 'name', 'value', 'percentile', 'level', 'level_number',
                                                            'state',  'position', 'shortDescription', 'description', 'IRON', 'SILVER', 'GOLD', 'PLATINUM', 'DIAMOND', 'MASTER', 'GRANDMASTER', 'CHALLENGER'])
    return data_total_joueur, data_joueur_category, data_joueur_challenges



class challengeslol():

    def __init__(self,
                 summonerName,
                 puuid=None,
                 session=None):
        """Class pour traiter les matchs

        Parameters
        ----------
        summonerName : `str`
            nom d'un joueur lol
        """
        self.summonerName = summonerName.lower().replace(' ', '')
        self.puuid = puuid
        self.session = session
        self.category = ['CRISTAL', 'IMAGINATION', 'EXPERTISE', 'VÉTÉRANCE', "TRAVAIL D'ÉQUIPE"]
        
    async def preparation_data(self):
        
        if self.puuid == None:
            me = await get_summoner_by_name(self.session, self.summonerName)
            self.puuid = me['puuid']
        else:
            self.puuid = self.puuid
        
        if self.session == None:
            self.session = aiohttp.ClientSession()
        else:
            self.session = self.session
            
        self.data_total, self.data_category, self.data_joueur = await get_data_joueur_challenges(self.summonerName, self.session, self.puuid)
        
    async def sauvegarde(self):
        if isinstance(self.data_joueur, pd.DataFrame):
            requete_perso_bdd(f'''DELETE FROM challenges_data where "Joueur" = '{self.summonerName}';
                              DELETE FROM challenges_category where "Joueur" = '{self.summonerName}';
                              DELETE FROM challenges_total where "index" = '{self.summonerName}' ''')
            sauvegarde_bdd(self.data_total, 'challenges_total', 'append')
            sauvegarde_bdd(self.data_category, 'challenges_category', 'append')
            sauvegarde_bdd(self.data_joueur, 'challenges_data', 'append')
        
    async def comparaison(self):
        self.df_old_data = lire_bdd_perso(f'''SELECT * from challenges_data where "Joueur" = '{self.summonerName}' ''').transpose().sort_index().rename(columns={'value' : 'value_precedente',
                                                                                                                                'percentile': 'percentile_precedent',
                                                                                                                                'level' : 'level_precedent',
                                                                                                                                'position' : 'position_precedente'})
        
        if not self.df_old_data.empty:
        
            self.data_comparaison = self.data_joueur.merge(self.df_old_data[['Joueur', 'challengeId', 'value_precedente', 'percentile_precedent', 'level_precedent', 'position_precedente']],
                                                        how='left',
                                                        on=['Joueur', 'challengeId'])
            
            self.data_comparaison['dif_value'] = self.data_comparaison['value'] - self.data_comparaison['value_precedente']
            self.data_comparaison['dif_percentile'] = self.data_comparaison['percentile'] - self.data_comparaison['percentile_precedent']
            self.data_comparaison['dif_level'] = (self.data_comparaison["level"] != self.data_comparaison["level_precedent"])
            self.data_comparaison['dif_position'] = self.data_comparaison["position_precedente"] - self.data_comparaison["position"]
            
            self.data_comparaison.sort_values('dif_value', ascending=False, inplace=True)
            
            self.data_new_value = self.data_comparaison[self.data_comparaison['dif_value'] > 0]
            self.data_new_value['evolution'] = (self.data_new_value['value'] - self.data_new_value['value_precedente']) / self.data_new_value['value_precedente'] * 100
            self.data_new_percentile = self.data_comparaison[(self.data_comparaison['dif_percentile'] > 0.01)]
            self.data_new_level = self.data_comparaison[self.data_comparaison['dif_level'] == True]
            self.data_new_position = self.data_comparaison[self.data_comparaison['dif_position'] != 0]
            self.data_evolution = self.data_new_value.sort_values('evolution', ascending=False)
            

            
            # on ne retient pas les petites améliorations, ça n'a aucun sens
            self.data_evolution = self.data_evolution[(self.data_evolution['evolution'] > 1) & (self.data_evolution['dif_value'] > 2)]
            
            # on retire les categories de new_value et new_percentile
            
            self.data_new_value = self.data_new_value[~self.data_new_value['name'].isin(self.category)]
            # si on veut éviter des doublons : 
            # self.data_new_value = self.data_new_value[~self.data_new_value['name'].isin(self.data_evolution.head(5)['name'])]
            
            self.data_new_percentile = self.data_new_percentile[~self.data_new_percentile['name'].isin(self.category)]
            
            self.data_new_percentile.sort_values('dif_percentile', ascending=False, inplace=True)
            self.data_new_position.sort_values('dif_position', ascending=False, inplace=True)
            
            
            
    
    async def embedding_discord(self, embed : Embed):
        
                    # nouveau système de records
        chunk = 1
        chunk_size = 700

        def check_chunk(texte, chunk, chunk_size):
            '''Détection pour passer à l'embed suivant'''
            if len(texte) >= chunk * chunk_size:
                    # Detection pour passer à l'embed suivant
                chunk += 1
                texte += '#'
            return texte, chunk
        
        txt = ''
        txt_24h = '' # pour les defis qui ne sont maj que toutes les 24h
        
        if not self.data_new_value.empty:
            for joueur, data in self.data_new_value.head(5).iterrows():
                txt, chunk = check_chunk(txt, chunk, chunk_size)
                txt += f'\n:sparkles: **{data["name"]}** [{data["level"]}] ({data["shortDescription"]}) : Tu as **{int(data["value"])}** pts (+{int(data["dif_value"])}) '
        
        chunk = 1            
        if not self.data_evolution.empty:
            for joueur, data in self.data_evolution.head(5).iterrows():
                if txt.count(data['name']) == 0: # on ne veut pas de doublons
                    txt, chunk = check_chunk(txt, chunk, chunk_size)
                    txt += f'\n:comet: **{data["name"]}** [{data["level"]}] ({data["shortDescription"]}) : Tu as **{int(data["value"])}** pts (+{int(data["dif_value"])} / **+{data["evolution"]:.2f}%**)'
        
        chunk = 1      
        if not self.data_new_percentile.empty:
            for joueur, data in self.data_new_percentile.head(5).iterrows():
                txt_24h, chunk = check_chunk(txt_24h, chunk, chunk_size)
                txt_24h += f'\n:zap: **{data["name"]}** [{data["level"]}] ({data["shortDescription"]}) : Tu es désormais dans les **{data["percentile"]:.2f}%** (+{data["dif_percentile"]:.2f}%) top'
                
        chunk = 1          
        if not self.data_new_position.empty:
            for joueur, data in self.data_new_position.head(5).iterrows():
                txt_24h, chunk = check_chunk(txt_24h, chunk, chunk_size)
                txt_24h += f'\n:arrow_up: **{data["name"]}** [{data["level"]}] ({data["shortDescription"]}) : Tu es **{int(data["position"])}**ème (+{int(data["dif_position"])}) places'
                
        chunk = 1      
        if not self.data_new_level.empty:
            for joueur, data in self.data_new_level.iterrows():
                txt, chunk = check_chunk(txt, chunk, chunk_size)
                txt += f'\n:up: **{data["name"]}** [{data["level"]}] ({data["shortDescription"]}) : Tu es passé **{(data["level"])}**'
        
        if len(txt) <= chunk_size: # si le texte est inférieur au chunk_size, on l'envoie directement
            txt = txt.replace('#', '').replace(' #', '') # on supprime la balise qui nous servait de split
            
            if txt != '':    
                embed.add_field(name='Challenges', value=txt, inline=False)
                
        else: # si le texte est supérieur

            txt = txt.split('#')  # on split sur notre mot clé

            for i in range(len(txt)): # pour chaque partie du texte, on l'envoie dans un embed différent
                
                field_name = f"Challenges {i + 1}"
                field_value = txt[i]
                # parfois la découpe renvoie un espace vide.
                if not field_value in ['', ' ']:
                    embed.add_field(name=field_name,
                                    value=field_value, inline=False)
                
        if len(txt_24h) <= chunk_size: # si le texte est inférieur au chunk_size, on l'envoie directement
            txt_24h = txt_24h.replace('#', '').replace(' #', '') # on supprime la balise qui nous servait de split
            
            if txt_24h != '':
                embed.add_field(name='Challenges (Classement)', value=txt_24h, inline=False)   
                
        else: # si le texte est supérieur
            txt_24h = txt.split('#')  # on split sur notre mot clé

            for i in range(len(txt_24h)): # pour chaque partie du texte, on l'envoie dans un embed différent
                
                field_name = f"Challenges (Classement) {i + 1}"
                field_value = txt_24h[i]
                # parfois la découpe renvoie un espace vide.
                if not field_value in ['', ' ']:
                    embed.add_field(name=field_name,
                                    value=field_value, inline=False) 
                    
        return embed
        
        