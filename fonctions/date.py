import calendar
from datetime import datetime
from dateutil import tz


def findDay(date):
    born = datetime.strptime(date, '%d %m %Y').weekday()
    return calendar.day_name[born]


def date_du_jour():
    """Renvoie la date du jour.

    Returns
    -------
    _currentDay_ `str`
    
    _currentMonth_ `str`
    
    _currentYear_ `str`    
    """
    currentMonth = str(datetime.now().month)
    currentYear = str(datetime.now().year)
    currentDay = str(datetime.now().day)
    return currentDay, currentMonth, currentYear


def heure_actuelle():
    """_Renvoie l'heure et la minute actuelle_

    Returns
    -------
    _currentHour_ `int`
    
    _currentMinute_ `int`    
    """
    timezone=tz.gettz('Europe/Paris')
    currentHour = datetime.now(tz=timezone).hour
    currentMinute = datetime.now(tz=timezone).minute
    return currentHour, currentMinute

def time_actuelle():
    '''Renvoie l'heure complète'''
    timezone=tz.gettz('Europe/Paris')
    
    return datetime.now(tz=timezone)
    

# def jour_de_la_semaine():
#     currentMonth = str(datetime.now().month)
#     currentYear = str(datetime.now().year)
#     currentDay = str(datetime.now().day)
#     currentJour = str(findDay(str(currentDay + ' ' + currentMonth + " " + currentYear)))
#     return str(currentJour)
