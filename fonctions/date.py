import calendar
from datetime import datetime

def findDay(date):
        born = datetime.strptime(date, '%d %m %Y').weekday()
        return calendar.day_name[born]
    
def heure_actuelle():
    currentHour = str(datetime.now().hour)
    currentMinute = str(datetime.now().minute)
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
        
        
