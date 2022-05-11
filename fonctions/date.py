import calendar
from datetime import datetime
import main

def findDay(date):
        born = datetime.strptime(date, '%d %m %Y').weekday()
        return calendar.day_name[born]

def alarm(h, m, message):
        currentHour = str(datetime.now().hour)
        currentMinute = str(datetime.now().minute)
        if currentHour == str(h) and currentMinute == str(m):
            channel = main.bot.get_channel(main.chan_lol)
            return channel.send(message)
        else:
            return False
        
        
def jour_de_la_semaine():
    currentMonth = str(datetime.now().month)
    currentYear = str(datetime.now().year)
    currentDay = str(datetime.now().day)
    currentJour = str(findDay(str(currentDay + ' ' + currentMonth + " " + currentYear)))
    return str(currentJour)