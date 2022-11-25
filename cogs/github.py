import interactions
from interactions import Option
from bs4 import BeautifulSoup
import requests
import json
import pandas as pd
from interactions.ext.wait_for import wait_for_component, setup as stp
import asyncio




class Github(interactions.Extension):
    def __init__(self, bot):
        self.bot : interactions.CommandContext = bot
        stp(self.bot)
        
        
        
    @interactions.extension_command(name="github",
                       description="GitHub",
                       options=[Option(name="pseudo",
                                       description= "Pseudo Github",
                                       type=interactions.OptionType.STRING,
                                       required=True)])
    async def github(self, ctx:interactions.CommandContext, pseudo:str):
        req = requests.get(f'https://api.github.com/users/{pseudo}')
        
        if req.status_code == 200:
            data_user = json.loads(req.text) # on récupère la data de l'utilisateur
            
            await ctx.defer(ephemeral=False)
            
            # on requête la data des repos :  
            
            req_repos = requests.get(data_user["repos_url"])
            
            data_user_repos = json.loads(req_repos.text)
            
            if len(data_user_repos) > 1:
            
                df = pd.DataFrame(data_user_repos)
                
                df.sort_values('name', axis=0, inplace=True)
                
                # catégorie . Le string i est obligatoire pour discord
                select = interactions.SelectMenu(
                        options=[interactions.SelectOption(label=df['name'][i], value=str(i),
                                                    description=str(df['description'][i])[:100]) for i in range(0,len(data_user_repos))],
                        custom_id="github_selection",
                        placeholder = "Choisis le dossier")
                
                await ctx.send("Choisis le dossier github",
                                            components=select)

                async def check(button_ctx):
                        if int(button_ctx.author.user.id) == int(ctx.author.user.id):
                            return True
                        await ctx.send("I wasn't asking you!", ephemeral=True)
                        return False
                    
                try:
                    button_ctx: interactions.ComponentContext = await self.bot.wait_for_component(
                        components=select, check=check, timeout=15
                    )
                    print(button_ctx.data.values[0])
                    print(button_ctx.data.values)
                    data_user_repos = json.loads(req_repos.text)[int(button_ctx.data.values[0])]

                    # With this new Context, you're able to send a new response.
                except asyncio.TimeoutError:
                    # When it times out, edit the original message and remove the button(s)
                    return await ctx.edit(components=[])
            
            
                em = interactions.Embed()
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

                await ctx.send(embeds=em)
            
            else:
                await ctx.send('Repertoire introuvable')
                
        elif req.status_code == 404:
            """if repository not found"""
            await ctx.send('Repertoire introuvable')
        elif req.status_code == 503:
            """GithubAPI down"""
            await ctx.send("GithubAPI down")
        else:
            await ctx.send('Erreur')




def setup(bot):
    Github(bot)