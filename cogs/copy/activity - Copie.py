from fonctions.date import heure_actuelle
from fonctions.gestion_bdd import get_guild_data
import interactions
from interactions import Extension, listen
from discord.utils import get

# Activity au lancement du bot


class activity(Extension):
    def __init__(self, bot: interactions.Client):
        self.bot = bot

    @listen()
    async def on_startup(self):
        currentHour, currentMinute = heure_actuelle()
        print(f'Connecté au serveur ({currentHour}:{currentMinute})')

        await self.bot.change_presence(interactions.Status.ONLINE,
                                       activity=interactions.Activity(name='My Dress Up Darling',
                                                                      type=interactions.ActivityType.WATCHING))

    @listen()
    async def on_ready(self):

        data = get_guild_data()
        liste_guilde = data.fetchall()

        for server_id in liste_guilde:
            guild = await self.bot.fetch_guild(server_id[0])

            text_channel_list = []
            for channel in guild.channels:
                text_channel_list.append(channel.id)

            print(
                f' Serveurs connectés => Name : {guild.name} | Id : {guild.id} | Chan1 : {text_channel_list[0]}')
            
            role = get(guild.roles, name="Muted")

            if role is not None:
                return role
            else:
                role = await guild.create_role(name="Muted", permissions=interactions.Permissions.VIEW_CHANNEL)
                return role


def setup(bot):
    activity(bot)
