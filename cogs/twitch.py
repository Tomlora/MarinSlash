import aiohttp
import os
from fonctions.gestion_bdd import get_data_bdd, requete_perso_bdd
import interactions
from interactions import Option, Extension, CommandContext
from interactions.ext.tasks import create_task, IntervalTrigger

from fonctions.channels_discord import chan_discord


# https://dev.twitch.tv/docs/api/reference#get-users


class Twitch(Extension):
    def __init__(self, bot):
        self.bot: interactions.Client = bot
        self.URL = 'https://id.twitch.tv/oauth2/token'
        self.client_id = os.environ.get('client_id_twitch')
        self.client_secret = os.environ.get('client_secret_twitch')
        self.body = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            "grant_type": 'client_credentials'
        }

    @interactions.extension_listener
    async def on_start(self):
        self.task1 = create_task(IntervalTrigger(60*4))(self.Twitch_verif)
        self.task1.start()

    # return the stream Id is streaming else returns -1
    async def TwitchLive(self, pseudo_twitch: str, statut_twitch: bool, session):
        # TODO : Faire par serveur discord
        discord_server_id = chan_discord(494217748046544906)

        channel_lol = await interactions.get(client=self.bot,
                                             obj=interactions.Channel,
                                             object_id=discord_server_id.twitch)

        async with session.post(self.URL, params=self.body) as user_twitch:
            r = await user_twitch.json()

            # data output
        try:
            keys = r["access_token"]
        except:
            print('Twitch : Data non disponible')

        headers = {
            'Client-ID': self.client_id,
            'Authorization': 'Bearer ' + keys
        }

        async with session.get('https://api.twitch.tv/helix/search/channels?query=' + pseudo_twitch, headers=headers) as stream:
            stream_data = await stream.json()

        if stream_data['data'][0]['is_live'] == True:  # si le joueur est en live
            # on récupère le jeu streamé
            jeu = stream_data['data'][0]['game_name']
            if statut_twitch == False:  # on vérifier si on a déjà fait l'annonce
                requete_perso_bdd('''UPDATE twitch SET is_live = True WHERE index = :joueur ''', {
                                  'joueur': pseudo_twitch.lower()})
                await channel_lol.send(
                    f'{pseudo_twitch} est en ligne sur {jeu}! https://www.twitch.tv/{pseudo_twitch}')
        # si le joueur a fini son stream
        elif stream_data['data'][0]['is_live'] == False and statut_twitch == True:
            requete_perso_bdd('''UPDATE twitch SET is_live = False WHERE index = :joueur ''', {
                              'joueur': pseudo_twitch.lower()})

    async def Twitch_verif(self):

        session = aiohttp.ClientSession()

        data_joueur = get_data_bdd(
            "SELECT index, is_live from twitch").mappings().all()

        for joueur in data_joueur:
            await self.TwitchLive(joueur['index'], joueur['is_live'], session)

        await session.close()

    @interactions.extension_command(name="addtwitch",
                                    description="Ajoute un compte au tracker twitch",
                                    options=[Option(name="pseudo_twitch",
                                                    description="Pseudo du compte Twitch",
                                                    type=interactions.OptionType.STRING,
                                                    required=True)])
    async def add_twitch(self, ctx: CommandContext, pseudo_twitch: str):

        await ctx.defer(ephemeral=False)

        requete_perso_bdd('''INSERT INTO twitch(index, is_live)
	                    VALUES (:index, :is_live);''', {'index': pseudo_twitch.lower(), 'is_live': False})
        await ctx.send('Joueur ajouté au tracker Twitch')

    @interactions.extension_command(name="deltwitch",
                                    description="Supprime un compte du tracker twitch",
                                    options=[Option(name="pseudo_twitch",
                                                    description="Pseudo du compte Twitch",
                                                    type=interactions.OptionType.STRING,
                                                    required=True)])
    async def del_twitch(self, ctx: CommandContext, pseudo_twitch: str):

        await ctx.defer(ephemeral=False)
        requete_perso_bdd('''DELETE FROM twitch WHERE index = :index;''', {
                          'index': pseudo_twitch.lower()})

        await ctx.send('Joueur supprimé du tracker Twitch')


def setup(bot):
    Twitch(bot)
