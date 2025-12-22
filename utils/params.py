from fonctions.gestion_bdd import lire_bdd_perso
import os

params = lire_bdd_perso('select * from settings', format='dict', index_col='parametres')

Version = params['version']['value']
saison = int(params['saison']['value'])
heure_aram = int(params['heure_aram']['value'])
heure_lolsuivi = int(params['heure_lolsuivi']['value'])
heure_challenge = int(params['heure_challenge']['value'])
set_tft = int(params['set_tft']['value'])



api_key_lol = os.environ.get('API_LOL')
api_moba = os.environ.get('API_moba')
url_api_moba = os.environ.get('url_moba')

my_region = 'euw1'
region = "EUROPE"



