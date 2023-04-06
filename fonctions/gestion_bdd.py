
import pandas as pd

from sqlalchemy import *

import os


# engine = create_engine('sqlite:///./obj/BDD/database.db', echo=False)

DB = os.environ.get('API_SQL')
engine = create_engine(DB, echo=False)


def lire_bdd(nom_table,
             format: str = "df"):
    """Lire la BDD

    Parameters
    -----------
    nom_table: :class:`str`
            Le nom de la table
    format: :class:`str`
            Choix entre 'dict' ou 'df'
    """
    conn = engine.connect()
    try:
        df = pd.read_sql(
            text(f'SELECT * FROM {nom_table}'), con=conn, index_col='index')
    except:
        nom_table = nom_table.lower()
        df = pd.read_sql(
            text(f'SELECT * FROM {nom_table}'), con=conn, index_col='index')
    df = df.transpose()
    if format == "dict":
        df = df.to_dict()
    conn.close()
    return df


def lire_bdd_perso(requests: str,
                   format: str = "df",
                   index_col: str = "index",
                   params=None):
    """Lire la BDD

    Parameters
    -----------
    requests: :class:`str`
            Requête SQL avec obligatoirement SELECT (columns) from (table) et éventuellement WHERE
    format: :class:`str`
            Choix entre 'dict' ou 'df'
    index_col: :class:`str`
            Colonne de l'index de la table
    params : dict avec {'variable' : 'value'}


    Les variables doivent être sous forme %(variable)s
    """
    conn = engine.connect()

    if params == None:
        df = pd.read_sql(text(requests), con=conn, index_col=index_col)
    else:
        df = pd.read_sql(text(requests), con=conn,
                         index_col=index_col, params=params)

    df = df.transpose()
    if format == "dict":
        df = df.to_dict()
    conn.close()
    return df


def sauvegarde_bdd(df,
                   nom_table,
                   methode_save='replace',
                   dtype={'Score': Float(),
                          'serie': BigInteger()},
                   index=True):
    """Sauvegarde la BDD au format dataframe

    Parameters
    -----------
    df: :class:`dict` or  `dataframe`
            Dataframe ou dict
    nom_table: :class:`str`
            Nom de la table sql
    method_save: :class:`str`
            Si la table existe déjà, choix entre "append" pour insérer des nouvelles valeurs ou "replace" pour supprimer la table existante et la remplacer
    dtype : :class:`dict`
            Specifying the datatype for columns. If a dictionary is used, the
            keys should be the column names and the values should be the
            SQLAlchemy types or strings for the sqlite3 legacy mode. If a
            scalar is provided, it will be applied to all columns.
    """
    conn = engine.connect()
    # si la variable envoyée n'est pas un dataframe, on l'a met au format dataframe
    if not isinstance(df, pd.DataFrame):
        df = pd.DataFrame(df)
        df = df.transpose()
    df.to_sql(nom_table, con=conn, if_exists=methode_save,
              index=index, method='multi', dtype=dtype)
    conn.commit()
    conn.close()


def supprimer_bdd(nom_table):
    conn = engine.connect()
    sql = text(f'DROP TABLE IF EXISTS {nom_table}')
    conn.execute(sql)
    conn.commit()
    conn.close()


def get_data_bdd(request: text,
                 dict_params=None):
    conn = engine.connect()
    sql = text(request)
    if dict_params == None:
        data = conn.execute(sql)
    else:
        data = conn.execute(sql, dict_params)
    conn.close()

    return data


def requete_perso_bdd(request: text,
                      dict_params: dict = None):
    """
    request : requête sql au format text

    dict_params : dictionnaire {variable : valeur}

    Rappel
    -------
    Dans la requête sql, une variable = :variable """
    conn = engine.connect()
    sql = text(request)
    if dict_params == None:
        conn.execute(sql)
    else:
        conn.execute(sql, dict_params)
    conn.commit()
    conn.close()


def get_guild_data():
    return get_data_bdd(f'''SELECT server_id from channels_module where activation = true ''')


# ------ SW


def sauvegarde_bdd_sw(df,
                      nom_table,
                      methode_save='replace'):
    """Sauvegarde la BDD au format dataframe
    Parameters
    -----------
    df: :class:`dict` or  `dataframe`
            Dataframe ou dict
    nom_table: :class:`str`
            Nom de la table sql
    method_save: :class:`str`
            Si la table existe déjà, choix entre "append" pour insérer des nouvelles valeurs ou "replace" pour supprimer la table existante et la remplacer
    """
    conn = engine.connect()
    # si la variable envoyée n'est pas un dataframe, on l'a met au format dataframe
    if not isinstance(df, pd.DataFrame):
        df = pd.DataFrame(df)
        df = df.transpose()
    df.to_sql(nom_table, con=conn, if_exists=methode_save, index=True,
              method='multi', dtype={'Score': Float(), 'serie': BigInteger()})
    conn.commit()
    conn.close()


async def get_user(joueur,
                   type: str = 'name_user',
                   id_compte: int = 0):
    '''Return l'id, la guilde et la visibilité du joueur demandé
    type : name_user ou id'''
    # à adapter avec l'id du compte quand on aura assez d'infos
    conn = engine.connect()
    if type == 'name_user':
        sql = text('SELECT id, guilde_id, visibility , joueur_id, (SELECT guilde from sw_guilde where sw_user.guilde_id = sw_guilde.guilde_id) as guilde FROM sw_user WHERE joueur = :joueur ')
        data = conn.execute(sql, {'joueur': joueur})
    elif type == 'id':
        sql = text('SELECT id, guilde_id, visibility , joueur_id, (SELECT guilde from sw_guilde where sw_user.guilde_id = sw_guilde.guilde_id) as guilde FROM sw_user WHERE joueur_id =:joueur ')
        data = conn.execute(sql, {'joueur': joueur})
    data = data.mappings().all()
    id_joueur = data[0]['id']

    visibility = data[0]['visibility']
    guildeid = data[0]['guilde_id']
    # Dans l'ancien système, on ne prenait pas l'id. On regarde s'il faut maj
    if data[0]['joueur_id'] == 0 and type == 'name_user':
        sql = text(
            'UPDATE sw_user SET joueur_id = :joueur_id where joueur = :joueur')
        data = conn.execute(sql, {'joueur_id': id_compte, 'joueur': joueur})
        conn.commit()
    conn.close()
    return id_joueur, visibility, guildeid


def update_info_compte(joueur,
                       guildeid,
                       compteid):
    conn = engine.connect()
    params_sql = {'joueur': joueur,
                  'guilde_id': guildeid, 'joueur_id': compteid}
    # sql1 = text('UPDATE sw_score SET guilde = :guilde WHERE "Joueur" = :joueur')
    sql1 = text(
        'UPDATE sw_user SET guilde_id = :guilde_id, joueur = :joueur WHERE joueur_id = :joueur_id;')
    conn.execute(sql1, params_sql)
    conn.commit()
    conn.close()
