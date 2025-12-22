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
    
    Version modifiée pour supporter les records agrégés.
    
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
    from fonctions.channels_discord import mention
    
    # Liste des colonnes agrégées qui peuvent avoir des valeurs 0 valides
    # et qui ne doivent PAS être filtrées sur != 0
    AGGREGATED_COLUMNS_ALLOW_ZERO = [
        'total_penta', 'total_quadra', 'total_triple', 'total_double', 'total_solokills',
        'penta_game', 'quadra_game', 'triple_game', 'double_game', 'solokills_game',
        'total_wins', 'avg_deaths'  # avg_deaths = 0 serait un record !
    ]
    
    # Liste des colonnes agrégées (pour savoir si on doit chercher dans les lignes agrégées)
    AGGREGATED_COLUMNS = [
        'avg_kills', 'avg_deaths', 'avg_assists', 'avg_kda', 'avg_kp',
        'avg_dmg', 'avg_dmg_min', 'avg_gold', 'avg_gold_min',
        'avg_cs', 'avg_cs_min', 'avg_time',
        'avg_vision', 'avg_vision_min',
        'avg_dmg_tank', 'avg_tankratio', 'avg_damageratio',
        'avg_heal', 'avg_shield', 'avg_dmg_reduit',
        'avg_gold_share', 'avg_trade_efficience', 'avg_solokills',
        'penta_game', 'quadra_game', 'triple_game', 'double_game', 'solokills_game',
        'total_penta', 'total_quadra', 'total_triple', 'total_double', 'total_solokills',
        'winrate', 'total_wins'
    ]

    
    try:
        # Vérifier si la colonne existe
        if category not in df.columns:
            if rank:
                return ['inconnu'], ['inconnu'], 0, ['#'], 0, [0]
            else:
                return ['inconnu'], ['inconnu'], 0, ['#'], [0]
        
        # Copie du df pour ne pas modifier l'original
        df_work = df.copy()
        
        # Si c'est une colonne agrégée, on filtre pour ne garder que les lignes agrégées
        is_aggregated_column = category in AGGREGATED_COLUMNS
        
        if is_aggregated_column and 'is_aggregated' in df_work.columns:
            df_work = df_work[df_work['is_aggregated'] == True]
        elif is_aggregated_column:
            # Si pas de colonne is_aggregated, on filtre sur les valeurs non-NaN de la colonne
            df_work = df_work[df_work[category].notna()]
        
        # Conversion en numérique
        df_work[category] = pd.to_numeric(df_work[category], errors='coerce')
        
        # Filtrer les NaN
        df_work = df_work[df_work[category].notna()]
        
        # Filtrer les 0 SAUF pour les colonnes agrégées qui permettent le 0
        if category not in AGGREGATED_COLUMNS_ALLOW_ZERO:
            df_work = df_work[df_work[category] != 0]
            df_work = df_work[df_work[category] != 0.0]
        
        if df_work.empty:
            if rank:
                return ['inconnu'], ['inconnu'], 0, ['#'], 0, [0]
            else:
                return ['inconnu'], ['inconnu'], 0, ['#'], [0]
        
        # Trouver le record
        col = df_work[category]
        if methode == 'max':
            record = col.max(skipna=True)
        elif methode == 'min':
            record = col.min(skipna=True)
        else:
            record = col.max(skipna=True)
        
        # Sélectionne toutes les lignes avec la même valeur
        max_min_rows: pd.DataFrame = df_work.loc[df_work[category] == record]
        
        if rank:
            rank_col = f'{category}_rank_{methode}'
            if rank_col in max_min_rows.columns:
                rank_value = max_min_rows[rank_col].values[0]
            else:
                # Calculer le rang à la volée si la colonne n'existe pas
                rank_value = 1
        
        # Si le df est vide, pas de record
        if max_min_rows.empty:
            if rank:
                return ['inconnu'], ['inconnu'], 0, ['#'], 0, [0]
            else:
                return ['inconnu'], ['inconnu'], 0, ['#'], [0]
        
        joueur = []
        champion = []
        url_game = []
        season = []
        
        for lig, data in max_min_rows.iterrows():
            # On affiche qu'une game du joueur
            player_id = data.get('riot_id', 'inconnu')
            discord_id = data.get('discord', '')
            player_mention = mention(discord_id, 'membre') if discord_id else player_id
            
            if player_id not in joueur and player_mention not in joueur:
                if identifiant == 'riot_id':
                    joueur.append(player_id)
                elif identifiant == 'discord':
                    joueur.append(player_mention)
                
                champion.append(data.get('champion', 'inconnu'))
                season.append(data.get('season', 0))
                
                # Construire l'URL (pour les records agrégés, on prend le dernier match)
                match_id = data.get('match_id', '')
                id_participant = data.get('id_participant', 0)
                
                if match_id and str(match_id).startswith('EUW'):
                    url_game.append(
                        f'https://www.leagueofgraphs.com/fr/match/euw/{str(match_id)[5:]}#participant{int(id_participant)+1}'
                    )
                else:
                    url_game.append('#')
                    
    except Exception as e:
        print(f"Erreur trouver_records_multiples pour {category}: {e}")
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
