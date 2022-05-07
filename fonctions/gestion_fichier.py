import pickle

def loadConfig(ctx):
    try:
        guild = ctx.guild.id
        with open(f'config/{guild}/config.pkl', 'rb') as f:
            fichier = pickle.load(f)
        return fichier
    except Exception:
        return {}


def writeConfig(ctx, data):
    guild = ctx.guild.id
    with open(f'config/{guild}/config.pkl', 'rb') as f:
        pickle.dump(data, f, protocol=0)

def loadData(name):
    try:
        with open('obj/' + name + '.pkl', 'rb') as f:
            fichier = pickle.load(f)
        return fichier
    except Exception:
        return {}


def writeData(data, name):
    with open('obj/' + name + '.pkl', 'wb+') as f:
        pickle.dump(data, f, protocol=0)
        

def reset_records_help(key: str, fichier: int):
    if fichier == 1:
        name = 'records'
    elif fichier == 2:
        name = 'records2'

    with open('obj/' + name + '.pkl', 'rb') as f:
        fichier = pickle.load(f)
        fichier[key] = {
            "Score": 0,
            "Champion": "Ezreal",
            "Joueur": "Tomlora"
        }

    with open('obj/' + name + '.pkl', 'wb+') as f:
        pickle.dump(fichier, f, protocol=0)
        

# Fantasy

def loadDataFL(name="fantasy"):
    try:
        with open('FL/' + name + '.pkl', 'rb') as f:
            return pickle.load(f)
    except Exception:
        return {}

def writeDataFL(obj, name="fantasy"):
    with open('FL/' + name + '.pkl', 'wb+') as f:
        pickle.dump(obj, f, protocol=0)
    
    # cote
        
def loadDataRate():
    try:
        name = "rate"
        with open('FL/' + name + '.pkl', 'rb') as f:
            return pickle.load(f)
    except Exception:
        return {}

def writeDataRate(obj, name="rate"):
    with open('FL/' + name + '.pkl', 'wb+') as f:
        pickle.dump(obj, f, protocol=0)