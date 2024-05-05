from fonctions.date import heure_actuelle
from fonctions.gestion_bdd import lire_bdd_perso, requete_perso_bdd
import interactions
from interactions import Extension
import interactions
from interactions import SlashCommandOption, Extension, SlashContext, SlashCommandChoice, listen, slash_command, Task, IntervalTrigger, TimeTrigger
from fonctions.permissions import isOwner_or_mod_slash
from sqlalchemy.exc import IntegrityError
from fonctions.word import suggestion_word
from fonctions.channels_discord import mention
from interactions.ext.paginators import Paginator

# Activity au lancement du bot


class customcmd(Extension):
    def __init__(self, bot: interactions.Client):
        self.bot = bot

    @slash_command(name='custom', description='Custom commande')
    async def custom(self, ctx: SlashContext):
        pass
    

    @custom.subcommand("cmd",
                           sub_cmd_description="Utiliser la commande",
                           options=[SlashCommandOption(name="nom",
                                                       description="Nom de la commande",
                                                       type=interactions.OptionType.STRING,
                                                       required=True)])
    
    async def custom_use(self, ctx: SlashContext, nom):
        
        nom = nom.lower()
        
        cmd = lire_bdd_perso(f'''SELECT nom, content FROM custom_cmd WHERE nom = '{nom}' AND server_id = {int(ctx.guild.id)}''',
                              index_col='nom',
                              format='dict')
        
        size_cmd = len(cmd)
        
        if size_cmd == 1:
            await ctx.send(cmd[nom]['content'])
        elif size_cmd == 0:
            cmd = lire_bdd_perso(f'''SELECT nom, content FROM custom_cmd where server_id = {int(ctx.guild.id)} ''',
                                 index_col='nom',
                                 format='dict')
            
            suggestion = suggestion_word(nom, cmd.keys())
            
            await ctx.send(f"Commande introuvable. N'est-ce pas plutôt **{suggestion}** ? ")
        
        

    @custom.subcommand('add',
                       sub_cmd_description='Ajouter une nouvelle custom commande',
                       options=[SlashCommandOption(name="nom",
                                                   description="Nom de la commande",
                                                   type=interactions.OptionType.STRING,
                                                   required=True),
                                SlashCommandOption(name='contenu',
                                                   description='Contenu de la commande',
                                                   type=interactions.OptionType.STRING,
                                                   required=True)])
    
    async def custom_add(self, ctx: SlashContext, nom, contenu):
        
        nom = nom.lower()
        
        try:
            requete_perso_bdd('''INSERT INTO public.custom_cmd(
        nom, server_id, content, author)
            VALUES (:nom, :server_id, :content, :author); ''',
            dict_params={'nom' : nom,
                        'server_id' : int(ctx.guild.id),
                        'content' : contenu,
                        'author' : int(ctx.author.id)})
            
            await ctx.send(f'La commande {nom} a été ajouté')
        
        except IntegrityError:
            
            await ctx.send(f'La commande {nom} existe déjà')
        

    @custom.subcommand('delete',
                       sub_cmd_description='Supprime une nouvelle custom commande',
                       options=[SlashCommandOption(name="nom",
                                                   description="Nom de la commande",
                                                   type=interactions.OptionType.STRING,
                                                   required=True)])
    
    async def custom_delete(self, ctx: SlashContext, nom):
        
        nom = nom.lower()
        
        if isOwner_or_mod_slash(ctx):    
            
            requete_perso_bdd('''DELETE FROM public.custom_cmd
        WHERE nom = :nom and server_id = :server_id ''',
            dict_params={'nom' : nom,
                        'server_id' : int(ctx.guild.id)})
            
            await ctx.send(f'La commande {nom} a été supprimé')
            
        else:
            await ctx.send("Tu n'as pas l'autorisation.")
            
    
    @custom.subcommand('liste',
                       sub_cmd_description='Liste des commandes disponibles')
    
    async def custom_list(self, ctx : SlashContext):
        
        df = lire_bdd_perso(f'''SELECT nom, content, author FROM custom_cmd WHERE server_id = {int(ctx.guild.id)}''',
                            index_col='nom').T
        
        embed = interactions.Embed(title='Liste des commandes')
        liste_embed = []
        i = 0
        
        for nom, data in df.iterrows():
            embed.add_field(name=nom, value=f"Crée par **{mention(data['author'], 'membre')}**")
            
            i = i + 1
            
            if i == 10: # Nouveau embed si on approche de la taille max
                liste_embed.append(embed)
                embed = interactions.Embed(title='Liste des commandes')
                i = 0
                
        if len(liste_embed) == 0 or i != 0: # si toujours premier embed ou embed incomplet
            liste_embed.append(embed)

            
        paginator = Paginator.create_from_embeds(
            self.bot,
            *liste_embed)
        paginator.show_select_menu = True
        
        await paginator.send(ctx)   
            
        



def setup(bot):
    customcmd(bot)