
import pandas as pd

from sqlalchemy import *

import os



# engine = create_engine('sqlite:///./obj/BDD/database.db', echo=False)

DB = os.environ.get('API_SQL')
engine = create_engine(DB, echo=False)



def lire_bdd(nom_table, format:str="df"):
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
        df = pd.read_sql(f'SELECT * FROM {nom_table}', con=conn, index_col='index')
    except:
        nom_table = nom_table.lower()
        df = pd.read_sql(f'SELECT * FROM {nom_table}', con=conn, index_col='index')
    df = df.transpose()
    if format == "dict":
        df = df.to_dict()
    conn.close()
    return df
    


def sauvegarde_bdd(df, nom_table, methode_save='replace'):
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
    if not isinstance(df, pd.DataFrame): # si la variable envoyée n'est pas un dataframe, on l'a met au format dataframe
        df = pd.DataFrame(df)
        df = df.transpose()
    df.to_sql(nom_table, con=conn, if_exists=methode_save, index=True, method='multi', dtype={'Score' : Float(), 'serie' : BigInteger()})
    conn.close()
    
def supprimer_bdd(nom_table):
    conn = engine.connect()
    sql = text(f'DROP TABLE IF EXISTS {nom_table}')
    conn.execute(sql)
    conn.close()
    
# def supprimer_data(Joueur, date):
#     conn = engine.connect()
#     params_sql = {'joueur' : Joueur, 'date' : date}
#     sql1 = text(f'DELETE FROM sw WHERE "Joueur" = :joueur AND date = :date')  # :var_name
#     sql2 = text(f'DELETE FROM sw_score WHERE "Joueur" = :joueur AND date = :date')
#     conn.execute(sql1, params_sql)
#     conn.execute(sql2, params_sql)
#     conn.close    

def get_data_bdd(request:text, dict_params = None):
    conn = engine.connect()
    sql = text(request)
    if dict_params == None:
        data = conn.execute(sql)
    else:
        data = conn.execute(sql, dict_params)
    conn.close()
    
    return data
    
def requete_perso_bdd(request:text, dict_params:dict):
    """
    request : requête sql au format text
    
    dict_params : dictionnaire {variable : valeur}
    
    Rappel
    -------
    Dans la requête sql, une variable = :variable """
    conn = engine.connect()
    sql = text(request)
    conn.execute(sql, dict_params)
    conn.close
    