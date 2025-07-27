import pandas as pd
from fonctions.date import date_du_jour

import urllib.request


def loaddata_oracle():
    chemin = "FL/data_oracle.csv"
    data_oracle = pd.read_csv(chemin)
    return data_oracle


def rechargement_data_oracle():
    jour, month, year = date_du_jour()

    # il faut ajouter le '0' devant, quand c'est nécessaire.

    if int(month) < 10:
        month = '0' + str(month)

    if int(jour) < 10:
        jour = '0' + str(jour)

    try:
        url_telechargement = f'https://oracleselixir-downloadable-match-data.s3-us-west-2.amazonaws.com/{year}_LoL_esports_match_data_from_OraclesElixir_{year}{month}{jour}.csv'

        urllib.request.urlretrieve(url_telechargement, "FL/data_oracle.csv")
    except:
        pass
