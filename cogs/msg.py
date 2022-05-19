import discord
from discord.ext import commands
import main


class Msg(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(brief="Envoie un mp à un utilisateur", help="Envoie un mp à un utilisateur")
    async def reply_mp(self, ctx, member: discord.Member, *contenu_msg):

        user = member
        msg = ""
        for contenu_msg in contenu_msg:
            msg = msg + " " + contenu_msg

        await user.send(msg)
        await ctx.send(f'Message envoyé à {member}')

    @reply_mp.error
    async def info_error(self, ctx, error):
        if isinstance(error, commands.BadArgument):
            await ctx.send(f"L'utilisateur est introuvable")

    @commands.command()
    async def reply_channel(self, ctx, nom_chan: str, *, contenu_msg):

        # On vérifie que l'utilisateur a donné un nom, et non l'ID du chan. Sinon on convertit
        if nom_chan.isnumeric():
            nom_chan = int(nom_chan)
            nom_chan = str(self.bot.get_channel(nom_chan))

        channel = discord.utils.get(self.bot.get_all_channels(), name=nom_chan)

        await channel.send(contenu_msg)

    @reply_channel.error
    async def info_error2(self, ctx, error):
        if isinstance(error, commands.BadArgument):
            await ctx.send(f"Le channel est introuvable")

    @commands.command(brief="Envoie un mp à soi-même")
    async def me(self, ctx, *contenu_msg):  # message à soi-même
        user = ctx.message.author
        msg = ""
        for contenu_msg in contenu_msg:
            msg = msg + " " + contenu_msg
        await user.send(msg)

    @commands.command()
    async def q(self, ctx, id_message: int):
        msg = await ctx.fetch_message(id_message)
        author = msg.author
        content = msg.content
        avatar = author.avatar_url
        msg_channel = msg.channel

        embed = discord.Embed(title=msg_channel,
                              description=content,
                              color=discord.Color.blue())
        embed.set_author(name=author, icon_url=avatar)
        embed.set_footer(text=f'Version {main.Var_version} by Tomlora')
        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Msg(bot))
