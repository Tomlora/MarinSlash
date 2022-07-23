import calendar
from datetime import datetime
from time import time

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

def jour_de_la_semaine():
    currentMonth = str(datetime.now().month)
    currentYear = str(datetime.now().year)
    currentDay = str(datetime.now().day)
    currentJour = str(findDay(str(currentDay + ' ' + currentMonth + " " + currentYear)))
    return str(currentJour)

def alarm(h, m, liste_jour):
        currentHour, currentMinute = heure_actuelle()
        if currentHour == str(h) and currentMinute == str(m) and jour_de_la_semaine in liste_jour:
            return True
        else:
            return False
        
        
def calcul_time(msg, time_prec):
    time_next = time()
    ecart = int((time_next-time_prec)*100)
    print(f"{msg} : {ecart}")
    return time_next