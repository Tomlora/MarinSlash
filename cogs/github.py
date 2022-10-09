import discord
from discord.ext import commands
from discord_slash import cog_ext, SlashContext
from discord_slash.utils.manage_components import *
from discord_slash.utils.manage_commands import create_option, create_choice
from bs4 import BeautifulSoup
import requests
import json
import pandas as pd





class Github(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
        
        
    @cog_ext.cog_slash(name="github",
                       description="GitHub",
                       options=[create_option(name="pseudo", description= "Pseudo Github", option_type=3, required=True)])
    async def github(self, ctx, pseudo:str):
        req = requests.get(f'https://api.github.com/users/{pseudo}')
        data_user = json.loads(req.text) # on récupère la data de l'utilisateur
        
        ctx.defer(hidden=False)
        
        # on requête la data des repos :  
        
        req_repos = requests.get(data_user["repos_url"])
        
        data_user_repos = json.loads(req_repos.text)
        
        df = pd.DataFrame(data_user_repos)
        
        df.sort_values('name', axis=0, inplace=True)
        
        # catégorie . Le string i est obligatoire pour discord
        select = create_select(
                options=[create_select_option(df['name'][i], value=str(i),
                                              description=df['description'][i]) for i in range(0,len(data_user_repos))],
                placeholder = "Choisis le dossier")

        fait_choix = await ctx.send('Choisis le dossier github ', components=[create_actionrow(select)])
            
        def check(m):
            return m.author_id == ctx.author.id and m.origin_message.id == fait_choix.id
            
        id_answer = await wait_for_component(self.bot, components=select, check=check)
        
        id_answer.edit_origin(content='...')
        
        answer = id_answer.values[0]
        
        data_user_repos = json.loads(req_repos.text)[int(answer)]
        
        if req.status_code == 200:
            em = discord.Embed()
            em.set_author(name=data_user_repos['owner']['login'], icon_url=data_user_repos['owner']['avatar_url'],
                          url=data_user_repos['owner']['html_url'])
            em.set_thumbnail(url=data_user_repos['owner']['avatar_url'])
            em.add_field(name="Repository:", value=f"[{data_user_repos['name']}]({data_user_repos['html_url']})", inline=True)
            em.add_field(name="Language:", value=data_user_repos['language'], inline=True)

            try:
                license_url = f"[{data_user_repos['license']['spdx_id']}]({json.loads(requests.get(data_user_repos['license']['url']).text)['html_url']})"
            except:
                license_url = "None"
            em.add_field(name="License:", value=license_url, inline=True)
            if data_user_repos['stargazers_count'] != 0:
                em.add_field(name="Star:", value=data_user_repos['stargazers_count'], inline=True)
            if data_user_repos['forks_count'] != 0:
                em.add_field(name="Fork:", value=data_user_repos['forks_count'], inline=True)
            if data_user_repos['open_issues'] != 0:
                em.add_field(name="Issues:", value=data_user_repos['open_issues'], inline=True)
            em.add_field(name="Description:", value=data_user_repos['description'], inline=False)

            for meta in BeautifulSoup(requests.get(data_user_repos['html_url']).text, features="html.parser").find_all('meta'):
                try:
                    if meta.attrs['property'] == "og:image":
                        em.set_image(url=meta.attrs['content'])
                        break
                except:
                    pass

            await ctx.send(embed=em)
        elif req.status_code == 404:
            """if repository not found"""
            await ctx.send('Repertoire introuvable')
        elif req.status_code == 503:
            """GithubAPI down"""
            await ctx.send("GithubAPI down")
        else:
            await ctx.send('Erreur')




def setup(bot):
    bot.add_cog(Github(bot))