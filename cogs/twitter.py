import discord
from discord.ext import commands, tasks
from discord_slash import cog_ext, SlashContext
from discord_slash.utils.manage_components import *
from discord_slash.utils.manage_commands import create_option, create_choice
import os
from fonctions.gestion_bdd import get_data_bdd, requete_perso_bdd

from TwitterAPI import TwitterAPI
import main


api = TwitterAPI(os.environ.get('API_TWITTER'),
                 os.environ.get('SECRET_TWITTER'),
                 os.environ.get('ACCESS_TWITTER'),
                 os.environ.get('ACCESS_SECRET_TWITTER'),
                 api_version='2')

def get_user_id(user:str):

    user_r = api.request(f'users/by/username/:{user}')
    user_r = user_r.json()
    user_id = user_r['data']['id']
    return user_id

def get_tweet(user_id:str, num_tweet:int=0):

    tweets = api.request(f'users/:{user_id}/tweets', {'max_results' : 5})
    id_tweet = tweets.json()['data'][num_tweet]['id']
    contenu_tweet = tweets.json()['data'][num_tweet]['text']
    
    return id_tweet, contenu_tweet



class Twitter(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.twitter_suivi.start()
              
    @cog_ext.cog_slash(name="last_tweet",
                       description="Dernier tweet",
                       options=[create_option(name="pseudo", description= "pseudo twitter", option_type=3, required=True),
                                create_option(name="numt_weet", description="numero tweet, de 0 à 5", option_type=4, required=False)])
    async def last_tweet(self, ctx, pseudo:str, num_tweet:int=0):
        

        user_id = get_user_id(pseudo)
        ctx.defer(hidden=False)
        

        id_tweet, msg_tweet = get_tweet(user_id, num_tweet=num_tweet)
        
 
        url_tweet = f'https://twitter.com/{pseudo}/status/{id_tweet}'
        
        await ctx.send(f'Tweet {pseudo} : ' + url_tweet)
        
    @cog_ext.cog_slash(name="add_tweet",
                       description="Ajoute un twitter au tracking",
                       options=[create_option(name="pseudo", description= "pseudo twitter", option_type=3, required=True)])
    @main.isOwner2_slash()
    async def add_tweet(self, ctx, pseudo:str):
        user_id = get_user_id(pseudo)
        
        requete_perso_bdd('''INSERT INTO public.twitter(
	                    twitter, id_twitter, id_last_msg_twitter)
	                    VALUES (:twitter, :id_twitter, 0);''', 
                     {'twitter' : pseudo, 'id_twitter' : user_id})
        ctx.defer(hidden=False)
        
        
        ctx.send(f'{pseudo} ajouté !')
        
        
    @tasks.loop(minutes=1, count=None )
    async def twitter_suivi(self):
        try:
            channel_tracklol = self.bot.get_channel(int(main.chan_tracklol)) 
                
            df_twitter =  get_data_bdd('Select * from twitter')
            df_twitter = df_twitter.mappings().all()
            
            for twitter in df_twitter:
                # info de la BDD
                user = twitter['twitter'] # user
                id_last_msg = twitter['id_last_msg_twitter'] # id dernier msg
                
                # on récupère l'id twitter
                user_id = get_user_id(user)
                
                # now on cherche les tweets
                id_tweet, contenu_tweet = get_tweet(user_id)
                
                if ('sources' in contenu_tweet.lower() or 'source' in contenu_tweet.lower()) and (str(id_tweet) != str(id_last_msg)): # info officiel
                    url_tweet = f'https://twitter.com/{user}/status/{id_tweet}'
                    await channel_tracklol.send(f'MERCATO {user} : ' + url_tweet)
                    requete_perso_bdd('UPDATE twitter SET id_last_msg_twitter = :id_last_msg WHERE id_twitter = :id_twitter', {'id_last_msg' : id_tweet,
                                                                                                                            'id_twitter' : user_id} )

        except:
            print('Erreur de détection du channel')



def setup(bot):
    bot.add_cog(Twitter(bot))