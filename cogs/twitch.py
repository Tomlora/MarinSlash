from discord.ext import commands, tasks
import main
import requests
import os

identifiant = False


class Twitch(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.Twitch_verif.start()

    @commands.command(brief="Vérifie si un utilisateur Twitch est connecté")
    async def TwitchLive(self, pseudo_twitch: str):  # return the stream Id is streaming else returns -1

        # writes new file in obj folder
        def LoadLoLData(pseudo_twitch):
            global identifiant
            with open("obj/twitch.txt", "r") as fichier:
                for ligne in fichier:
                    if not ligne:
                        print('La liste est vide')
                        identifiant = False
                    elif ligne == pseudo_twitch:
                        identifiant = True
                        break
                    else:
                        identifiant = False
            return identifiant

        def WriteLoLData(pseudo_twitch):
            with open("obj/twitch.txt", "a") as fichier:
                fichier.write("\n" + pseudo_twitch)

        def DelLoLData(pseudo_twitch):

            with open("obj/twitch.txt", "r") as fichier:
                x = fichier.read()
            with open("obj/twitch.txt", "wt") as fichier:
                x = x.replace(pseudo_twitch, "")
                fichier.write(x)

        URL = 'https://id.twitch.tv/oauth2/token'
        client_id = os.environ.get('client_id_twitch')
        client_secret = os.environ.get('client_secret_twitch')
        streamer_name = str(pseudo_twitch)

        channel_lol = self.bot.get_channel(main.chan_twitch)

        body = {
            'client_id': client_id,
            'client_secret': client_secret,
            "grant_type": 'client_credentials'
        }

        r = requests.post(url=URL, params=body)

        # data output
        try:
            keys = r.json()["access_token"]
        except:
            print('Twitch : Data non disponible')

        headers = {
            'Client-ID': client_id,
            'Authorization': 'Bearer ' + keys
        }

        stream = requests.get(url='https://api.twitch.tv/helix/streams?user_login=' + streamer_name, headers=headers)

        stream_data = stream.json()

        if len(stream_data['data']) == 1:
            jeu = stream_data['data'][0]['game_name']
            if not LoadLoLData(pseudo_twitch=pseudo_twitch):
                WriteLoLData(pseudo_twitch=pseudo_twitch)
                if pseudo_twitch == str('liquid_state'):
                    ylarabka = 177545266516197376
                    kazsc = 195223919911763972
                    await channel_lol.send(
                        f'{pseudo_twitch} est en ligne sur {jeu}! https://www.twitch.tv/{pseudo_twitch} <@{ylarabka}> <@{kazsc}>')
                else:
                    await channel_lol.send(
                        f'{pseudo_twitch} est en ligne sur {jeu}! https://www.twitch.tv/{pseudo_twitch}')
        else:
            DelLoLData(pseudo_twitch)

    @tasks.loop(minutes=1, count=None)
    async def Twitch_verif(self):
        if self.bot.get_channel(main.chan_twitch):
            # print('Verification Twitch..')

            await self.TwitchLive(str('liquid_state'))
            await self.TwitchLive(str('Tomlora'))
        else:
            print('Verification Twitch impossible, channel non disponible')


def setup(bot):
    bot.add_cog(Twitch(bot))
