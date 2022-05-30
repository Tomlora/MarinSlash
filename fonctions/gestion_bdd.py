
import pandas as pd

from sqlalchemy import *

engine = create_engine('sqlite:///./obj/BDD/database.db', echo=False)
conn = engine.connect()


def lire_bdd(nom_table, format:str="df"):
    """Lire la BDD

    Parameters
    -----------
    nom_table: :class:`str`
            Le nom de la table
    format: :class:`str`
            Choix entre 'dict' ou 'df'
    """
    
    df = pd.read_sql(f'SELECT * FROM {nom_table}', con=conn, index_col='index')
    df = df.transpose()
    if format == "dict":
        df = df.to_dict()
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
    if not isinstance(df, pd.DataFrame): # si la variable envoyée n'est pas un dataframe, on l'a met au format dataframe
        df = pd.DataFrame(df)
        df = df.transpose()
    df.to_sql(nom_table, con=conn, if_exists=methode_save, index=True, method='multi', dtype={'Score' : Float(), 'serie' : BigInteger()})
    
    
def supprimer_bdd(nom_table):
    sql = text(f'DROP TABLE IF EXISTS {nom_table}')
    conn.execute(sql)
    
