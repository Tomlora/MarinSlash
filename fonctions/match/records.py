"""
Fonctions de gestion des records.
Recherche et affichage des records personnels et globaux.
"""

import pandas as pd
from fonctions.channels_discord import mention
from fonctions.gestion_bdd import lire_bdd_perso


def get_id_account_bdd(riot_id, riot_tag):
    """Récupère l'ID de compte depuis la base de données."""
    id_acc = lire_bdd_perso(
        f'''SELECT * from tracker where riot_id = '{riot_id.replace(' ', '')}' and riot_tagline = '{riot_tag}' '''
    ).loc['id_compte'].values[0]
    return id_acc


def trouver_records(df, category, methode='max', identifiant='riot_id'):
    """
    Trouve la ligne avec le record associé.

    Parameters
    ----------
    df : DataFrame
        DataFrame avec les records
    category : str
        Colonne où chercher le record
    methode : str, optional
        'min' ou 'max', by default 'max'
    identifiant : str, optional
        'joueur' ou 'discord', by default 'joueur'
        joueur renvoie au pseudo lol
        discord renvoie à la mention discord

    Returns
    -------
    tuple
        (joueur, champion, record, url_game)
    """
    try:
        df[category] = pd.to_numeric(df[category])
        # Pas de 0 - ça veut dire qu'ils n'ont pas fait l'objectif
        df = df[df[category] != 0]
        df = df[df[category] != 0.0]
        
        if methode == 'max':
            col = df[category].idxmax(skipna=True)
        elif methode == 'min':
            col = df[category].idxmin(skipna=True)
        
        lig = df.loc[col]

        if identifiant == 'riot_id':
            joueur = lig['riot_id']
        elif identifiant == 'discord':
            joueur = mention(lig['discord'], 'membre')

        champion = lig['champion']
        record = lig[category]
        url_game = f'https://www.leagueofgraphs.com/fr/match/euw/{str(lig["match_id"])[5:]}#participant{int(lig["id_participant"])+1}'

    except Exception:
        return 'inconnu', 'inconnu', 0, '#'

    return joueur, champion, record, url_game


def trouver_records_multiples(df, category, methode='max', identifiant='riot_id', rank: bool = False):
    """
    Trouve les lignes avec le record associé (gère les égalités).

    Parameters
    ----------
    df : DataFrame
        DataFrame avec les records
    category : str
        Colonne où chercher le record
    methode : str, optional
        'min' ou 'max', by default 'max'
    identifiant : str, optional
        'riot_id' ou 'discord', by default 'riot_id'
    rank : bool, optional
        Inclure le rang dans le retour, by default False

    Returns
    -------
    tuple
        (joueurs, champions, record, urls, [rank_value], seasons)
    """
    try:
        df[category] = pd.to_numeric(df[category])

        if methode == 'max':
            df = df[df[category] != 0]
            df = df[df[category] != 0.0]
            col = df[category]
            record = col.max(skipna=True)
        elif methode == 'min':
            df = df[df[category] != 0]
            df = df[df[category] != 0.0]
            col = df[category]
            record = col.min(skipna=True)
            
        # Sélectionne toutes les lignes avec la même valeur
        max_min_rows: pd.DataFrame = df.loc[df[category] == record]

        if rank:
            rank_value = max_min_rows[f'{category}_rank_{methode}'].values[0]

        # Si le df est vide, pas de record
        if max_min_rows.empty and not rank:
            return ['inconnu'], ['inconnu'], 0, ['#'], [0]
        elif max_min_rows.empty and rank:
            return ['inconnu'], ['inconnu'], 0, ['#'], 0, [0]

        joueur = []
        champion = []
        url_game = []
        season = []

        for lig, data in max_min_rows.iterrows():
            # On affiche qu'une game du joueur
            if data['riot_id'] not in joueur and mention(data['discord'], 'membre') not in joueur:
                if identifiant == 'riot_id':
                    joueur.append(data['riot_id'])
                elif identifiant == 'discord':
                    joueur.append(mention(data['discord'], 'membre'))

                champion.append(data['champion'])
                season.append(data['season'])
                url_game.append(
                    f'https://www.leagueofgraphs.com/fr/match/euw/{str(data["match_id"])[5:]}#participant{int(data["id_participant"])+1}'
                )

    except Exception:
        if rank:
            return ['inconnu'], ['inconnu'], 0, ['#'], 0, [0]
        else:
            return ['inconnu'], ['inconnu'], 0, ['#'], [0]

    if rank:
        return joueur, champion, record, url_game, rank_value, season
    else:
        return joueur, champion, record, url_game, season


def top_records(df, category, methode='max', identifiant='riot_id', top_n=10):
    """
    Retourne le top N des records pour une catégorie.

    Parameters
    ----------
    df : DataFrame
        DataFrame avec les records
    category : str
        Colonne où chercher les records
    methode : str, optional
        'min' ou 'max', by default 'max'
    identifiant : str, optional
        'riot_id' ou 'discord', by default 'riot_id'
    top_n : int, optional
        Nombre de records à retourner, by default 10

    Returns
    -------
    list
        Liste de tuples (joueur, champion, record, url_game)
    """
    try:
        df[category] = pd.to_numeric(df[category], errors='coerce')
        df = df[df[category].notna()]
        df = df[df[category] != 0]
        df = df[df[category] != 999]

        df_sorted = df.sort_values(by=category, ascending=(methode != 'max')).head(top_n)

        records = []
        for _, lig in df_sorted.iterrows():
            if identifiant == 'riot_id':
                joueur = lig.get('riot_id', 'inconnu')
            elif identifiant == 'discord':
                joueur = mention(lig.get('discord', ''), 'membre')
            else:
                joueur = 'inconnu'

            champion = lig.get('champion', 'inconnu')
            record = lig[category]
            url_game = f'https://www.leagueofgraphs.com/fr/match/euw/{str(lig.get("match_id", ""))[5:]}#participant{int(lig.get("id_participant", 0)) + 1}'

            records.append((joueur, champion, record, url_game))

        return records

    except Exception:
        return []


def get_stat_null_rules():
    """Récupère les règles d'exclusion pour les stats nulles."""
    query = "SELECT stat_name, champion FROM records_exclusion"
    df = lire_bdd_perso(query, index_col=None).T

    stat_null_rules = {}
    for stat_name, group in df.groupby("stat_name"):
        stat_null_rules[stat_name] = group["champion"].tolist()
    return stat_null_rules
