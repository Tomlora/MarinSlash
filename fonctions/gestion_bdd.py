
import pandas as pd
import sqlite3

def lire_bdd(nom_table, index=None, url='./obj/BDD/database.db'):
    df = pd.read_sql(f'SELECT * FROM {nom_table}', con=sqlite3.connect(url), index_col = index)
    return df

def sauvegarde_bdd(df, nom_table, index=None, url='./obj/BDD/database.db'):
    df.to_sql(nom_table, con=sqlite3.connect(url), if_exists='replace', index_label=index)