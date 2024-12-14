
from fonctions.patch import PatchNote
import interactions
from interactions import Extension, listen, Task, IntervalTrigger
from fonctions.gestion_bdd import (get_data_bdd,
                                   requete_perso_bdd,
                                   get_guild_data)
from fonctions.channels_discord import chan_discord


class LolPronostic(Extension):
    def __init__(self, bot):
        self.bot: interactions.Client = bot



def setup(bot):
    LolPronostic(bot)
