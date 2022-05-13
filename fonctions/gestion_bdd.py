
import pandas as pd
from sqlalchemy import create_engine, Float

engine = create_engine('sqlite:///./obj/BDD/database.db')


def lire_bdd(nom_table):
    
    df = pd.read_sql(f'SELECT * FROM {nom_table}', con=engine, index_col='index')
    df = df.transpose()
    df = df.to_dict()
    return df


def sauvegarde_bdd(df, nom_table):
    df = pd.DataFrame(df)
    df = df.transpose()
    df.to_sql(nom_table, con=engine, if_exists='replace', index=True, method='multi', dtype={'Score' : Float()})
    
