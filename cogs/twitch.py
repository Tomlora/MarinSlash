from discord.ext import commands, tasks
import main
import requests
import os
from fonctions.gestion_bdd import get_data_bdd, requete_perso_bdd
from discord_slash.utils.manage_components import *
from discord_slash.utils.manage_commands import create_option, create_choice
from discord_slash import cog_ext, SlashContext

identifiant = False

# https://dev.twitch.tv/docs/api/reference#get-users


class Twitch(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.Twitch_verif.start()
        self.URL = 'https://id.twitch.tv/oauth2/token'
        self.client_id = os.environ.get('client_id_twitch')
        self.client_secret = os.environ.get('client_secret_twitch')
        self.body =  {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            "grant_type": 'client_credentials'
        }

    @commands.command(brief="Vérifie si un utilisateur Twitch est connecté")
    async def TwitchLive(self, pseudo_twitch: str, statut_twitch:bool):  # return the stream Id is streaming else returns -1

        channel_lol = self.bot.get_channel(main.chan_twitch)

        r = requests.post(url=self.URL, params=self.body)

        # data output
        try:
            keys = r.json()["access_token"]
        except:
            print('Twitch : Data non disponible')

        headers = {
            'Client-ID': self.client_id,
            'Authorization': 'Bearer ' + keys
        }

        stream_data = requests.get(url='https://api.twitch.tv/helix/search/channels?query=' + pseudo_twitch, headers=headers).json()

        if stream_data['data'][0]['is_live'] == True: # si le joueur est en live
            jeu = stream_data['data'][0]['game_name'] # on récupère le jeu streamé
            if statut_twitch == False: # on vérifier si on a déjà fait l'annonce
                requete_perso_bdd('''UPDATE twitch SET is_live = True WHERE index = :joueur ''', {'joueur' : pseudo_twitch.lower()})
                await channel_lol.send(
                        f'{pseudo_twitch} est en ligne sur {jeu}! https://www.twitch.tv/{pseudo_twitch}')
        elif stream_data['data'][0]['is_live'] == False and statut_twitch == True : # si le joueur a fini son stream
            requete_perso_bdd('''UPDATE twitch SET is_live = False WHERE index = :joueur ''', {'joueur' : pseudo_twitch.lower()})

    @tasks.loop(minutes=1, count=None)
    async def Twitch_verif(self):
        if self.bot.get_channel(main.chan_twitch):
            
            data_joueur = get_data_bdd("SELECT index, is_live from twitch").mappings().all()
            
            for joueur in data_joueur:
                await self.TwitchLive(joueur['index'], joueur['is_live'])
        else:
            print('Verification Twitch impossible, channel non disponible')


    @cog_ext.cog_slash(name="addtwitch",
                       description="Ajoute un compte au tracker twitch",
                       options=[create_option(name="pseudo_twitch", description = "Pseudo du compte Twitch", option_type=3, required=True)])
    async def add_twitch(self, ctx, pseudo_twitch:str):
        
        await ctx.defer(hidden=False)
        
        requete_perso_bdd('''INSERT INTO twitch(index, is_live)
	                    VALUES (:index, :is_live);''', {'index' : pseudo_twitch.lower(), 'is_live' : False})
        await ctx.send('Joueur ajouté au tracker Twitch')
        
    @cog_ext.cog_slash(name="deltwitch",
                       description="Supprime un compte du tracker twitch",
                       options=[create_option(name="pseudo_twitch", description = "Pseudo du compte Twitch", option_type=3, required=True)])
    async def del_twitch(self, ctx, pseudo_twitch:str):
        
        await ctx.defer(hidden=False)
        requete_perso_bdd('''DELETE FROM twitch WHERE index = :index;''', {'index' : pseudo_twitch.lower()})
        
        await ctx.send('Joueur supprimé du tracker Twitch')
        
    

def setup(bot):
    bot.add_cog(Twitch(bot))
