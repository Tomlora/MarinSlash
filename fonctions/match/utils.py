"""
Utilitaires généraux pour le traitement des matchs LoL.
Fonctions helper, formatage, et outils divers.
"""

import numpy as np
from collections import Counter
from PIL import ImageFont


def mode(lst):
    """
    Trouve le(s) mode(s) d'une liste (valeur(s) la/les plus fréquente(s)).
    Ignore les valeurs vides.
    """
    cleaned_lst = [value for value in lst if value != '']
    
    if not cleaned_lst:
        return ''
    
    counts = Counter(cleaned_lst)
    mode_value = max(counts.values())
    modes = [key for key, value in counts.items() if value == mode_value]
    return modes


def fix_temps(duree):
    """Convertit le temps en secondes en minutes et secondes."""
    minutes = int(duree)
    secondes = int((duree - minutes) * 60) / 100
    return minutes + secondes


def range_value(i, liste, min: bool = False, return_top: bool = False, value_meilleur = (0, 128, 0), value_pire = (220, 20, 60), couleur_fill=(0, 0, 0)):
    """
    Détermine la couleur en fonction de la position dans le classement.
    Vert pour max, rouge pour min, noir sinon.
    """
    if i == np.argmax(liste[:5]) or i - 5 == np.argmax(liste[5:]):
        fill = value_meilleur
        top = 'max'
    elif min and (i == np.argmin(liste[:5]) or i - 5 == np.argmin(liste[5:])):
        fill = value_pire
        top = 'min'
    else:
        fill = couleur_fill
        top = None

    return (fill, top) if return_top else fill


def range_value_arena(i, liste, min: bool = False, return_top: bool = False):
    """
    Version Arena de range_value pour les modes avec moins de joueurs.
    """
    if i == np.argmax(liste):
        fill = (0, 128, 0)
        top = 'max'
    elif min and i == np.argmin(liste):
        fill = (220, 20, 60)
        top = 'min'
    else:
        fill = (0, 0, 0)
        top = None

    return (fill, top) if return_top else fill


def charger_font(size):
    """Charge une police DejaVuSans avec la taille spécifiée."""
    font = ImageFont.truetype("utils/font/DejaVuSans.ttf", size)
    return font


def dict_data(thisId: int, match_detail, info):
    """
    Extrait une liste de données pour tous les participants d'un match.
    Réordonne les données si le joueur est dans la seconde équipe.
    """
    try:
        if thisId > 4:
            liste = [match_detail['info']['participants'][i][info] for i in range(5, 10)] + \
                    [match_detail['info']['participants'][i][info] for i in range(5)]
        else:
            liste = [match_detail['info']['participants'][i][info] for i in range(10)]
    except Exception:
        if thisId > 4:
            liste = [match_detail['info']['participants'][i]['challenges'][info] for i in range(5, 10)] + \
                    [match_detail['info']['participants'][i]['challenges'][info] for i in range(5)]
        else:
            liste = [match_detail['info']['participants'][i]['challenges'][info] for i in range(10)]

    return liste


def dict_data_swarm(thisId: int, match_detail, info, nb_joueur):
    """
    Version Swarm de dict_data pour les modes avec nombre variable de joueurs.
    """
    try:
        liste = [match_detail['info']['participants'][i][info] for i in range(nb_joueur)]
    except Exception:
        if thisId > 4:
            liste = [match_detail['info']['participants'][i]['challenges'][info] for i in range(0, 3)] + \
                    [match_detail['info']['participants'][i]['challenges'][info] for i in range(nb_joueur)]
        else:
            liste = [match_detail['info']['participants'][i]['challenges'][info] for i in range(nb_joueur)]

    return liste


def load_timeline(timeline):
    """
    Charge et formate les données de timeline d'un match.
    
    Returns:
        tuple: (DataFrame timeline, nombre de minutes)
    """
    import pandas as pd
    
    df_timeline = pd.DataFrame(
        timeline['info']['frames'][1]['participantFrames'])
    df_timeline = df_timeline.transpose()
    df_timeline['timestamp'] = 0

    minute = len(timeline['info']['frames']) - 1

    for i in range(1, minute):
        df_timeline2 = pd.DataFrame(
            timeline['info']['frames'][i]['participantFrames'])
        df_timeline2 = df_timeline2.transpose()
        df_timeline2['timestamp'] = i
        df_timeline = df_timeline.append(df_timeline2)

    df_timeline['riot_id'] = df_timeline['participantId']
            
    return df_timeline, minute
