from fonctions.gestion_bdd import lire_bdd_perso, requete_perso_bdd, get_data_bdd
from time import time
import interactions

class chan_discord():

    def __init__(self,
                 server_id: int,
                 bot=None):

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
              color = interactions.Color.blurple()):
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
        membre / role ou channel

    Returns
    -------
    str
        mention à insérer dans un string
    """
    if type=='membre':
        return f'<@{id_discord}>'
    elif type=='role':
        return f'<@&{id_discord}>'
    elif type=='channel':
        return f'<#{id_discord}>'
