import calendar
from datetime import datetime


def findDay(date):
    born = datetime.strptime(date, '%d %m %Y').weekday()
    return calendar.day_name[born]


def date_du_jour():
    currentMonth = str(datetime.now().month)
    currentYear = str(datetime.now().year)
    currentDay = str(datetime.now().day)
    return currentDay, currentMonth, currentYear


def heure_actuelle():
    currentHour = datetime.now().hour
    currentMinute = datetime.now().minute
    return currentHour, currentMinute

# def jour_de_la_semaine():
#     currentMonth = str(datetime.now().month)
#     currentYear = str(datetime.now().year)
#     currentDay = str(datetime.now().day)
#     currentJour = str(findDay(str(currentDay + ' ' + currentMonth + " " + currentYear)))
#     return str(currentJour)
