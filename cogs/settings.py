from fonctions.permissions import isOwner_slash
from fonctions.gestion_bdd import get_data_bdd, requete_perso_bdd
from interactions import Option, Extension, CommandContext, Choice
import interactions
from interactions.ext.paginator import Page, Paginator


class Settings(Extension):
    def __init__(self, bot):
        self.bot: interactions.Client = bot
        
    @interactions.extension_command(name="settings",
                                    description="settings")
    async def settings(self, ctx: CommandContext):
        if isOwner_slash(ctx):
           # on récupère les infos
            await ctx.defer(ephemeral=False)
            
            data = get_data_bdd(
                'SELECT * from channels_module WHERE server_id = :server_id ', {'server_id': int(ctx.guild_id)})
           # on transforme
            data = data.mappings().all()[0]
            
            # on prépare l'embed 1 avec les modules

            embed1 = interactions.Embed(title=f'Settings pour {ctx.guild.name} (Modules)',
                                       thumbnail=interactions.EmbedImageStruct(url=ctx.guild.icon_url))

            for variable, valeur in data.items():
                if not variable == 'activation': # on ne veut pas cette variable dans notre embed
                    embed1.add_field(name=variable, value=valeur, inline=True)
                
            # embed 2 avec les identifiants channels    

            embed2 = interactions.Embed(title=f'Settings pour {ctx.guild.name} (Channels)',
                                       thumbnail=interactions.EmbedImageStruct(url=ctx.guild.icon_url))
            
            data2 = get_data_bdd(
                'SELECT * from channels_discord WHERE server_id = :server_id ', {'server_id': int(ctx.guild_id)})
            
            # on transforme
            data2 = data2.mappings().all()[0]
            
            for variable, valeur in data2.items():
                if variable == 'server_id': # en fonction de la variable, discord ne mentionne pas de la même manière. Pour un serveur id, classique
                    embed2.add_field(name=variable, value=valeur, inline=True)
                elif variable in ['id_owner', 'id_owner2']: # pour un membre, c'est @
                    embed2.add_field(name=variable, value=f'<@{valeur}>', inline=True)
                elif variable == 'role_admin' : # pour un role, c'est @&
                    embed2.add_field(name=variable, value=f'<@&{valeur}>', inline=True)
                else: # pour un channel, c'est #
                    embed2.add_field(name=variable, value=f'<#{valeur}>', inline=True)
                
            await Paginator(
                client=self.bot,
                ctx=ctx,
                pages=[
                    Page(embed1.title, embed1),
                    Page(embed2.title, embed2),
                ]
            ).run()
            
            

        else:
            await ctx.send("Tu n'as pas l'autorisation.")

    @interactions.extension_command(name="modifier_modules",
                                    description="modifier les modules du serveur",
                                    options=[
                                        Option(name="parametres",
                                                    description="parametres",
                                                    type=interactions.OptionType.STRING,
                                                    required=True,
                                                    choices=[
                                                        Choice(
                                                            name='lol', value='lol'),
                                                        Choice(
                                                            name='twitter', value='twitter'),
                                                        Choice(
                                                            name='twitch', value='twitch'),
                                                        Choice(
                                                            name='tft', value='tft'),
                                                        Choice(name='sw', value='sw')]),
                                        Option(name='activation',
                                               description='que faire ?',
                                               type=interactions.OptionType.BOOLEAN,
                                               required=True)
                                    ]
                                    )
    async def modifier_modules(self, ctx: CommandContext, parametres, activation):

        if isOwner_slash(ctx):
            dict_params = {'lol': ['league_ranked, league_aram'],
                           'twitter': ['twitter'],
                           'twitch': ['twitch'],
                           'tft': ['league_tft'],
                           'sw': ['summoners_war']}


            params = dict_params[parametres]


            for parametre in params:
                requete_perso_bdd(f'UPDATE channels_module SET {parametre} = {activation} where server_id = :server_id', {
                                  'server_id': int(ctx.guild_id)})

            await ctx.send(
                f'Les paramètres pour {parametres} ont été modifiés avec succès pour ce serveur.')
        else:
            await ctx.send("Tu n'es pas autorisé à utiliser cette commande.")

    @interactions.extension_command(name="modifier_settings",
                                    description="modifier les parametres du serveur",
                                    options=[
                                        Option(name="channel",
                                                    description="changer le channel d'un module",
                                                    type=interactions.OptionType.SUB_COMMAND,
                                                    options=[
                                                        Option(name='parametres',
                                                               description='quel module à modifier ?',
                                                               type=interactions.OptionType.STRING,
                                                               required=True,
                                                                choices=[
                                                                    Choice(
                                                                        name='message_prive', value='chan_pm'),
                                                                    Choice(
                                                                        name='tracking_lol_ranked', value='chan_tracklol'),
                                                                    Choice(
                                                                        name='twitch', value='chan_twitch'),
                                                                    Choice(
                                                                        name='lol_actu', value='chan_lol'),
                                                                    Choice(
                                                                        name='accueil', value='chan_accueil'),
                                                                    Choice(
                                                                        name='tft', value='chan_tft'),
                                                                    Choice(
                                                                        name='tracking_lol_autre', value='chan_lol_others')
                                                                ]),
                                                        Option(name='channel',
                                                               description='channel',
                                                               type=interactions.OptionType.CHANNEL,
                                                               required=True)]),

                                        Option(name='admin',
                                               description="qui est l'admin ?",
                                               type=interactions.OptionType.SUB_COMMAND,
                                               options=[
                                                   Option(name='parametres',
                                                          description='quel role ?',
                                                          type=interactions.OptionType.STRING,
                                                          choices=[
                                                              Choice(name='admin', value='id_owner2')]),
                                                   Option(name='proprietaire',
                                                          description='proprietaire du discord',
                                                          type=interactions.OptionType.USER)
                                               ])])
    async def modifier_channel(self, ctx: CommandContext, sub_command: str, parametres, channel: interactions.Channel = None, proprietaire: interactions.User = None):
        if isOwner_slash(ctx):
            if sub_command == 'channel':
                requete_perso_bdd(f'UPDATE channels_discord SET {parametres} = :channel_id WHERE server_id = :server_id', {'channel_id': int(channel.id),
                                                                                                                           'server_id': int(ctx.guild.id)})
            elif sub_command == 'admin':
                requete_perso_bdd(f'UPDATE channels_discord SET {parametres} = :joueur_id WHERE server_id = :server_id', {'joueur_id': int(proprietaire.id),
                                                                                                                           'server_id': int(ctx.guild.id)})
                
            await ctx.send('Modification effectuée avec succès.')
        else:
            await ctx.send("Tu n'es pas autorisé à utiliser cette commande.")


def setup(bot):
    Settings(bot)
