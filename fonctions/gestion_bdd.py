
import pandas as pd

from sqlalchemy import *
import uuid
import os

DB = os.environ.get('API_SQL')
engine = create_engine(DB, echo=False)


def upsert_df(df: pd.DataFrame, table_name: str):
    """Implements the equivalent of pd.DataFrame.to_sql(..., if_exists='update')
    (which does not exist). Creates or updates the db records based on the
    dataframe records.
    Conflicts to determine update are based on the dataframes index.
    This will set unique keys constraint on the table equal to the index names
    1. Create a temp table from the dataframe
    2. Insert/update from temp table into table_name
    Returns: True if successful
    """

    conn = engine.connect()

    # If the table does not exist, we should just use to_sql to create it
    if not conn.execute(text(
        f"""SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE  table_schema = 'public'
            AND    table_name   = '{table_name}');
            """)
    ).first()[0]:
        df.to_sql(table_name, conn)
        return True

    # If it already exists...
    temp_table_name = f"temp_{uuid.uuid4().hex[:6]}"
    df.to_sql(temp_table_name, conn, index=True)

    index = list(df.index.names)
    index_sql_txt = ", ".join([f'"{i}"' for i in index])
    columns = list(df.columns)
    headers = index + columns
    headers_sql_txt = ", ".join(
        [f'"{i}"' for i in headers]
    )  # index1, index2, ..., column 1, col2, ...

    # col1 = exluded.col1, col2=excluded.col2
    update_column_stmt = ", ".join([f'"{col}" = EXCLUDED."{col}"' for col in columns])

    # For the ON CONFLICT clause, postgres requires that the columns have unique constraint
    query_pk = f"""
    ALTER TABLE "{table_name}" DROP CONSTRAINT IF EXISTS unique_constraint_for_upsert;
    ALTER TABLE "{table_name}" ADD CONSTRAINT unique_constraint_for_upsert UNIQUE ({index_sql_txt});
    """
    conn.execute(text(query_pk))

    # Compose and execute upsert query
    query_upsert = f"""
    INSERT INTO "{table_name}" ({headers_sql_txt}) 
    SELECT {headers_sql_txt} FROM "{temp_table_name}"
    ON CONFLICT ({index_sql_txt}) DO UPDATE 
    SET {update_column_stmt};
    """
    conn.execute(text(query_upsert))
    conn.execute(text(f"DROP TABLE {temp_table_name}"))

    return True

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
                      dict_params: dict = None,
                      get_row_affected:bool = False):
    """
    request : requête sql au format text

    dict_params : dictionnaire {variable : valeur}

    Rappel
    -------
    Dans la requête sql, une variable = :variable """
    conn = engine.connect()
    sql = text(request)
    if dict_params == None:
        cursor = conn.execute(sql)
    else:
        cursor = conn.execute(sql, dict_params)
        
    nb_row_affected = cursor.rowcount
    
    conn.commit()
    conn.close()
    
    if get_row_affected:
        return nb_row_affected


def get_guild_data():
    return get_data_bdd(f'''SELECT server_id from channels_module where activation = true ''')



def get_tag(riot_id : str):
    dict_tag = lire_bdd_perso(f'''select riot_tagline from tracker where riot_id = '{riot_id.lower().replace(" ", "")}' ''', index_col=None, format='dict')

    if len(dict_tag) > 1:
        raise ValueError('Plusieurs comptes avec ce riot_id')
    
    tagline = dict_tag[0]['riot_tagline']

    return tagline

