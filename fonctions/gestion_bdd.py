
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

async def autocomplete_riotid(serverid,
                              input_txt):
    df = lire_bdd_perso(f'''select riot_id from tracker where server_id = '{serverid}' ''', index_col=None).T

    if df.empty:
        return []
    
    df['riot_id'] = df['riot_id'].str.lower()
    input_txt = input_txt.lower()

    df.sort_values(by='riot_id', inplace=True)

    liste_id = []
    for i in df['riot_id'].unique().tolist():
        if input_txt in i:
            liste_id.append({"name": f'{i}', "value": f'{i}'})
    
    return liste_id[:25]



async def autocomplete_record(record_id):

    liste_records = ['kills', 'assists', 'deaths', 'double', 'triple', 'quadra', 'penta', 'solokills', 'team_kills', 'team_deaths', 'kda', 'kp', 'kills+assists', 'serie_kills', 'first_double', 'first_triple', 'first_quadra', 'first_penta'] +\
    ['kills_min', 'deaths_min', 'assists_min', 'longue_serie_kills', 'ecart_kills', 'ecart_deaths', 'ecart_assists'] +\
    ['dmg', 'dmg_ad', 'dmg_ap', 'dmg_true', 'damageratio', 'dmg_min', 'dmg/gold', 'crit_dmg', 'dmg_true_all', 'dmg_true_all_min', 'dmg_ad_all', 'dmg_ad_all_min', 'dmg_ap_all', 'dmg_ap_all_min', 'dmg_all', 'dmg_all_min', 'ecart_dmg'] +\
    ['vision_score', 'vision_pink', 'vision_wards', 'vision_wards_killed', 'vision_min', 'vision_avantage'] +\
    ['cs', 'cs_jungle', 'cs_min', 'cs_dix_min', 'jgl_dix_min', 'cs_max_avantage'] +\
    ['dmg_reduit', 'dmg_tank', 'tankratio', 'shield', 'heal_total', 'heal_allies'] +\
    ['baron', 'drake', 'early_drake', 'early_baron', 'dmg_tower', 'fourth_dragon', 'first_elder', 'first_horde', 'petales_sanglants', 'tower', 'inhib', 'early_atakhan'] +\
    ['time', 'gold', 'gold_min', 'gold_share', 'ecart_gold_team', 'level_max_avantage', 'temps_dead', 'temps_vivant', 'allie_feeder', 'temps_avant_premiere_mort', 'snowball',
    'skillshot_dodged', 'temps_cc', 'spells_used', 'buffs_voles', 'immobilisation', 'temps_cc_inflige', 'first_blood'] +\
    ['abilityHaste', 'abilityPower', 'armor', 'attackDamage', 'currentGold', 'healthMax', 'magicResist', 'movementSpeed', 'first_niveau_max'] +\
    ["ASSISTS_10", "ASSISTS_20", "ASSISTS_30",
                                        "BUILDING_KILL_20", "BUILDING_KILL_30",
                                        "CHAMPION_KILL_10", "CHAMPION_KILL_20", "CHAMPION_KILL_30",
                                        "DEATHS_10", "DEATHS_20", "DEATHS_30",
                                        "ELITE_MONSTER_KILL_10", "ELITE_MONSTER_KILL_20", "ELITE_MONSTER_KILL_30",
                                        "LEVEL_UP_10", "LEVEL_UP_20", "LEVEL_UP_30"] +\
    [ "TURRET_PLATE_DESTROYED_10", "WARD_KILL_10", "WARD_KILL_20", "WARD_KILL_30", "WARD_PLACED_10", "WARD_PLACED_20", "WARD_PLACED_30",
                                "TOTAL_CS_20", "TOTAL_CS_30", "TOTAL_GOLD_20", "TOTAL_GOLD_30", "CS_20", "CS_30", "JGL_20", "JGL_30"] +\
    ['l_ecart_cs', 'l_ecart_gold', 'l_ecart_gold_min_durant_game', 'l_ecart_gold_max_durant_game', 'l_kda', 'l_cs', 'l_cs_max_avantage', 'l_level_max_avantage', 'l_ecart_gold_team', 'l_ecart_kills_team', 'l_temps_avant_premiere_mort',
                      'l_ecart_kills', 'l_ecart_deaths', 'l_ecart_assists', 'l_ecart_dmg', 'l_allie_feeder', 'l_temps_vivant', 'l_time', 'l_solokills'] 

    liste_records.sort()

    liste_records = [i for i in liste_records if record_id in i]

    return liste_records[:25]