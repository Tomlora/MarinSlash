from fonctions.gestion_bdd import lire_bdd_perso

params = lire_bdd_perso('select * from settings', format='dict', index_col='parametres')

Version = params['version']['value']
saison = int(params['saison']['value'])
heure_aram = int(params['heure_aram']['value'])
heure_lolsuivi = int(params['heure_lolsuivi']['value'])
heure_challenge = int(params['heure_challenge']['value'])