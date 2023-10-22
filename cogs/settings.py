from fonctions.permissions import isOwner_slash
from fonctions.gestion_bdd import get_data_bdd, requete_perso_bdd
from interactions import SlashCommandOption, Extension, SlashContext, SlashCommandChoice, slash_command
import interactions
from interactions.ext.paginators import Paginator


class Settings(Extension):
    def __init__(self, bot):
        self.bot: interactions.Client = bot

    @slash_command(name="settings",
                   description="settings",
                   default_member_permissions=interactions.Permissions.MANAGE_GUILD)
    async def settings(self, ctx: SlashContext):
           # on récupère les infos
        await ctx.defer(ephemeral=False)

        data = get_data_bdd(
                'SELECT * from channels_module WHERE server_id = :server_id ', {'server_id': int(ctx.guild_id)})
           # on transforme
        data = data.mappings().all()[0]

            # on prépare l'embed 1 avec les modules

        embed1 = interactions.Embed(title=f'Settings pour {ctx.guild.name} (Modules)',
                                        thumbnail=interactions.EmbedAttachment(url=ctx.guild.icon.as_url()))
            

        for variable, valeur in data.items():
            if not variable == 'activation':  # on ne veut pas cette variable dans notre embed
                embed1.add_field(name=variable, value=valeur, inline=True)

            # embed 2 avec les identifiants channels

        embed2 = interactions.Embed(title=f'Settings pour {ctx.guild.name} (Channels)',
                                        thumbnail=interactions.EmbedAttachment(url=ctx.guild.icon.as_url()))

        data2 = get_data_bdd(
                'SELECT * from channels_discord WHERE server_id = :server_id ', {'server_id': int(ctx.guild_id)})

            # on transforme
        data2 = data2.mappings().all()[0]

        for variable, valeur in data2.items():
            if variable == 'server_id':  # en fonction de la variable, discord ne mentionne pas de la même manière. Pour un serveur id, classique
                embed2.add_field(name=variable, value=valeur, inline=True)
            elif variable in ['id_owner', 'id_owner2']:  # pour un membre, c'est @
                embed2.add_field(
                        name=variable, value=f'<@{valeur}>', inline=True)
            elif variable == 'role_admin':  # pour un role, c'est @&
                embed2.add_field(
                        name=variable, value=f'<@&{valeur}>', inline=True)
            else:  # pour un channel, c'est #
                embed2.add_field(
                        name=variable, value=f'<#{valeur}>', inline=True)

        embeds = [embed1, embed2]
        paginator = Paginator.create_from_embeds(
                self.bot,
                *embeds)
            
        paginator.show_select_menu = True
        await paginator.send(ctx)


    @slash_command(name="modifier_modules",
                   description="modifier les modules du serveur",
                   default_member_permissions=interactions.Permissions.MANAGE_GUILD,
                   options=[
                       SlashCommandOption(name="parametres",
                                          description="parametres",
                                          type=interactions.OptionType.STRING,
                                          required=True,
                                          choices=[
                                              SlashCommandChoice(
                                                  name='lol', value='lol'),
                                              SlashCommandChoice(
                                                  name='twitter', value='twitter'),
                                              SlashCommandChoice(
                                                  name='twitch', value='twitch'),
                                              SlashCommandChoice(
                                                  name='tft', value='tft'),
                                              SlashCommandChoice(name='sw', value='sw')]),
                       SlashCommandOption(name='activation',
                                          description='que faire ?',
                                          type=interactions.OptionType.BOOLEAN,
                                          required=True)
                   ]
                   )
    async def modifier_modules(self, ctx: SlashContext, parametres, activation):


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


    @slash_command(name="modifier_settings",
                   description="modifier les parametres du serveur",
                   default_member_permissions=interactions.Permissions.MANAGE_GUILD)
    async def modifier_settings(self, ctx: SlashContext):
        pass

    @modifier_settings.subcommand('channel',
                                  options=[
                                      SlashCommandOption(name='parametres',
                                                         description='quel module à modifier ?',
                                                         type=interactions.OptionType.STRING,
                                                         required=True,
                                                         choices=[
                                                              SlashCommandChoice(
                                                                  name='message_prive', value='chan_pm'),
                                                              SlashCommandChoice(
                                                                  name='tracking_lol_ranked', value='chan_tracklol'),
                                                              SlashCommandChoice(
                                                                  name='twitch', value='chan_twitch'),
                                                              SlashCommandChoice(
                                                                  name='lol_actu', value='chan_lol'),
                                                              SlashCommandChoice(
                                                                  name='accueil', value='chan_accueil'),
                                                              SlashCommandChoice(
                                                                  name='tft', value='chan_tft'),
                                                              SlashCommandChoice(
                                                                  name='tracking_lol_autre', value='chan_lol_others')
                                                         ]),
                                      SlashCommandOption(name='channel',
                                                         description='channel',
                                                         type=interactions.OptionType.CHANNEL,
                                                         required=True)])
    async def modify_channel(self, ctx: SlashContext, channel: interactions.BaseChannel, parametres):

        requete_perso_bdd(f'UPDATE channels_discord SET {parametres} = :channel_id WHERE server_id = :server_id', {'channel_id': int(channel.id),
                                                                                                                       'server_id': int(ctx.guild.id)})
        await ctx.send('Modification effectuée avec succès.')



    @modifier_settings.subcommand('admin',
                                  options=[
                                      SlashCommandOption(name='parametres',
                                                         description='quel role ?',
                                                         type=interactions.OptionType.STRING,
                                                         choices=[
                                                             SlashCommandChoice(name='admin', value='id_owner2')]),
                                      SlashCommandOption(name='proprietaire',
                                                         description='proprietaire du discord',
                                                         type=interactions.OptionType.USER)
                                  ])
    async def modify_admin(self, ctx: SlashContext, parametres, proprietaire: interactions.User):

        requete_perso_bdd(f'UPDATE channels_discord SET {parametres} = :joueur_id WHERE server_id = :server_id', {'joueur_id': int(proprietaire.id),
                                                                                                                      'server_id': int(ctx.guild.id)})
        await ctx.send('Modification effectuée avec succès.')


    @modifier_settings.subcommand('role_staff',
                                  options=[
                                      SlashCommandOption(name='parametres',
                                                         description='quel partie du staff ?',
                                                         type=interactions.OptionType.STRING,
                                                         choices=[
                                                             SlashCommandChoice(
                                                                 name='admin', value='role_admin')
                                                         ]),
                                      SlashCommandOption(name='role',
                                                         description='quel role pour le staff ?',
                                                         type=interactions.OptionType.ROLE)
                                  ])
    async def modifier_staff(self, ctx: SlashContext, parametres, role: interactions.Role):

        requete_perso_bdd(f'UPDATE channels_discord SET {parametres} = :role_id WHERE server_id = :server_id', {'role_id': int(role.id),
                                                                                                                    'server_id': int(ctx.guild.id)})
        await ctx.send('Modification effectuée avec succès.')




def setup(bot):
    Settings(bot)
