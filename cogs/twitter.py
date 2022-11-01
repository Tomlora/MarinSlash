import discord
from discord.ext import commands, tasks
from discord_slash import cog_ext, SlashContext
from discord_slash.utils.manage_components import *
from discord_slash.utils.manage_commands import create_option, create_choice
import os

from TwitterAPI import TwitterAPI


api = TwitterAPI(os.environ['API_TWITTER'],
                 os.environ['SECRET_TWITTER'],
                 os.environ['ACCESS_TWITTER'],
                 os.environ['ACCESS_SECRET_TWITTER'],
                 api_version='2')

def get_user_id(user:str):
    user_r = api.request(f'users/by/username/:{user}')
    user_r = user_r.json()
    user_id = user_r['data']['id']
    return user_id

def get_tweet(user_id:str, num_tweet:int=0):
    tweets = api.request(f'users/:{user_id}/tweets', {'max_results' : 5})
    id_tweet = tweets.json()['data'][num_tweet]['id']
    contenu_tweet = tweets.json()['data'][0]['text']
    
    return id_tweet, contenu_tweet



class Twitter(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
              
    @cog_ext.cog_slash(name="last_tweet",
                       description="Dernier tweet",
                       options=[create_option(name="pseudo", description= "pseudo twitter", option_type=3, required=True)])
    async def last_tweet(self, ctx, pseudo:str):
        
        user_id = get_user_id(pseudo)
        ctx.defer(hidden=False)
        
        id_tweet, msg_tweet = get_tweet(user_id)
        
        url_tweet = f'https://twitter.com/{pseudo}/status/{id_tweet}'
        
        ctx.send(url_tweet)





def setup(bot):
    bot.add_cog(Twitter(bot))