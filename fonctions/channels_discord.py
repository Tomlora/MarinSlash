from fonctions.gestion_bdd import lire_bdd_perso, requete_perso_bdd, get_data_bdd
from time import time
import interactions
import re
class chan_discord():

    def __init__(self,
                 server_id: int,
                 bot :interactions.Client = None):
        """Class pour récupérer toutes les identifiants d'un serveur discord

        Parameters
        ----------
        server_id : `int`
            id du serveur
        bot : interactions.Client, optional
            bot interactions
        """

        self.server_id = server_id
        self.bot_discord = bot

        # si le serveur n'est pas dans la liste, on l'ajoute :
        self.data = lire_bdd_perso(
            f'SELECT server_id from channels_discord', index_col='server_id').transpose()

        if not int(self.server_id) in self.data.index:
            self.verif_server()

        # on récupère les identifiants

        self.dict_channel = lire_bdd_perso('Select * from channels_discord where server_id = %(server_id)s',
                                           index_col='server_id', format='dict', params={'server_id': self.server_id})

        self.dict_channel = self.dict_channel[self.server_id]

        self.id_owner = self.dict_channel['id_owner']
        self.id_owner2 = self.dict_channel['id_owner2']
        self.chan_pm = self.dict_channel['chan_pm']
        self.tracklol = self.dict_channel['chan_tracklol']
        self.chan_accueil = self.dict_channel['chan_accueil']
        self.twitch = self.dict_channel['chan_twitch']
        self.lol = self.dict_channel['chan_lol']
        self.tft = self.dict_channel['chan_tft']
        self.lol_others = self.dict_channel['chan_lol_others']
        self.role_admin = self.dict_channel['role_admin']

    def verif_server(self):

        self.text_channel_list = []
        self.guild = self.bot_discord.get_guild(self.server_id)
        for channel in self.guild.text_channels:
            self.text_channel_list.append(channel.id)

        requete_perso_bdd(f'''INSERT INTO public.channels_discord(
                    server_id, id_owner, id_owner2, chan_pm, chan_tracklol, chan_accueil, chan_twitch, chan_lol, chan_tft, chan_lol_others, role_admin)
                    VALUES (:server_id, :chan, :chan, :chan, :chan, :chan, :chan, :chan, :chan, :chan, :chan);''',
                          {'server_id': self.server_id, 'chan': self.text_channel_list[0]})


def rgb_to_discord(r: int, g: int, b: int):
    """Transpose les couleurs rgb en couleur personnalisée discord."""
    return ((r << 16) + (g << 8) + b)


def verif_module(variable: str, guild_id: int) -> bool:
    """Vérifie si le module est activé pour le serveur associé

    Parameters
    ----------
    variable : `str`
        nom du module
    guild_id : `int`
        identifiant de la guilde

    Returns
    -------
    _result_
        True or False
    """
    result = get_data_bdd(f'SELECT {variable} FROM channels_module where server_id = :server_id', {
                          'server_id': guild_id}).fetchall()[0][0]
    return result == True


def get_embed(fig,
              name,
              color = interactions.Color.BLURPLE):
    """Prépare l'image à insérer avec l'embed

    Parameters
    ----------
    fig : `plotly_express`
        figure plotly_express déjà paramétré
    name : `string`
        nom de l'image
    color : `interactions.Color`, optional
        couleur de l'embed, by default interactions.Color.blurple()

    Returns
    -------
    Embed + file
    
    >>> await ctx.send(embeds=embed, files=file)
    """
    fig.write_image(f'{name}.png')
    file = interactions.File(f'{name}.png')
    # On prépare l'embed
    embed = interactions.Embed(color=color)
    embed.set_image(url=f'attachment://{name}.png')

    return embed, file


def mention(id_discord:int, type:str) -> str:
    """Formate l'id pour mentionner un membre, un role ou un channel

    Parameters
    ----------
    id_discord : int
        id à mentionner
    type : str
        'membre' / 'role' ou 'channel'

    Returns
    -------
    str
        mention à insérer dans un string
    """
    
    dict_mention = {'membre' : f'<@{id_discord}>',
                    'role' : f'<@&{id_discord}>',
                    'channel' : f'<#{id_discord}>'}

    return dict_mention[type]


async def convertion_temps(ctx : interactions.CommandContext, time) -> int:
    """Convertit un format XhXmXs en secondes

    Parameters
    ----------
    ctx : interactions.CommandContext
        _description_
    time : _str_
        Temps sous la forme "1h20m" ou "1h20m50s"

    Returns
    -------
    _int_
        Temps en secondes
    """
    match = re.match(r"(\d+)([hms])?", time)
    if not match:
        ctx.send("Entrez le temps sous la forme '2h30m' ou '15s'", ephemeral=True)
    
    time_conversions = {
    "h": 3600,
    "m": 60,
    "s": 1
    }
    
    amount = int(match.group(1))
    unit = match.group(2)
    seconds = amount * time_conversions[unit]
    
    return seconds