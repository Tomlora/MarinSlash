
import interactions
from interactions import Option, Extension, CommandContext
from interactions.ext.tasks import create_task, IntervalTrigger
import os
from fonctions.gestion_bdd import get_data_bdd, requete_perso_bdd
import sys
from fonctions.permissions import isOwner2_slash
from fonctions.channels_discord import chan_discord
import oauthlib.oauth1, aiohttp

client = oauthlib.oauth1.Client(os.environ.get('API_TWITTER'),
                 os.environ.get('SECRET_TWITTER'),
                 os.environ.get('ACCESS_TWITTER'),
                 os.environ.get('ACCESS_SECRET_TWITTER'))

async def get_user_id(user:str, session):

    uri = f'https://api.twitter.com/2/users/by/username/{user}'
    http_method = 'GET'
    headers = {
        'User-Agent': 'python-TwitterAPI'}
    
        # Sign the request data. This needs to be called for each request you make.
    uri,headers,body = client.sign(
        uri = uri,
        http_method = http_method,
        headers = headers
    )
    async with session.get(uri, headers=headers) as user_twitter:
        user_r = await user_twitter.json()

    user_id = user_r['data']['id']
    return user_id

async def get_tweet(user_id:str, session, num_tweet:int=0, max_results:int=10):

    
    uri = f'https://api.twitter.com/2/users/{user_id}/tweets?max_results={max_results}'
    http_method = 'GET'
    headers = {
        'User-Agent': 'python-TwitterAPI'}
    
    # Sign the request data. This needs to be called for each request you make.
    uri,headers,body = client.sign(
        uri = uri,
        http_method = http_method,
        headers = headers
    )
    async with session.get(uri, headers=headers) as tweets_list:
        tweets = await tweets_list.json()

    id_tweet = tweets['data'][num_tweet]['id']
    contenu_tweet = tweets['data'][num_tweet]['text']
    
    return id_tweet, contenu_tweet




class Twitter(Extension):
    def __init__(self, bot):
        self.bot : interactions.Client = bot
              
    @interactions.extension_listener
    async def on_start(self):
        
        self.task1 = create_task(IntervalTrigger(60*2))(self.twitter_suivi)
        self.task1.start()
    
    
    
    # @interactions.extension_command(name="last_tweet",
    #                    description="Dernier tweet",
    #                    options=[Option(name="pseudo",
    #                                    description= "pseudo twitter",
    #                                    type=interactions.OptionType.STRING,
    #                                    required=True),
    #                             Option(name="num_tweet",
    #                                    description="numero tweet, de 0 à 5",
    #                                    type=interactions.OptionType.INTEGER,
    #                                    required=False,
    #                                    min_value=0,
    #                                    max_value=5)])
    # async def last_tweet(self, ctx:CommandContext, pseudo:str, num_tweet:int=0):
        

    #     user_id = get_user_id(pseudo)
    #     ctx.defer(ephemeral=False)
        

    #     id_tweet, msg_tweet = get_tweet(user_id, num_tweet=num_tweet)
        
 
    #     url_tweet = f'https://twitter.com/{pseudo}/status/{id_tweet}'
        
    #     await ctx.send(f'Tweet {pseudo} : ' + url_tweet)
        
    @interactions.extension_command(name="add_tweet",
                       description="Ajoute un twitter au tracking",
                       options=[Option(name="pseudo",
                                       description= "pseudo twitter",
                                       type=interactions.OptionType.STRING,
                                       required=True)])
    @isOwner2_slash()
    async def add_tweet(self, ctx:CommandContext, pseudo:str):
        
        session = aiohttp.ClientSession()
        user_id = await get_user_id(pseudo, session)
        
        requete_perso_bdd('''INSERT INTO public.twitter(
	                    twitter, id_twitter, id_last_msg_twitter)
	                    VALUES (:twitter, :id_twitter, 0);''', 
                     {'twitter' : pseudo, 'id_twitter' : user_id})
        ctx.defer(ephemeral=False)
        
        
        await ctx.send(f'{pseudo} ajouté !')
        
        

    async def twitter_suivi(self):
        # TODO : faire par serveur
        session = aiohttp.ClientSession()

    
        df_twitter =  get_data_bdd('Select * from twitter')
        df_twitter = df_twitter.mappings().all()
            
        for twitter in df_twitter:
            # info de la BDD
            user = twitter['twitter'] # user
            id_last_msg = twitter['id_last_msg_twitter'] # id dernier msg
                
            # on récupère l'id twitter
            user_id = await get_user_id(user, session)
                
            # now on cherche les tweets
            try:
                id_tweet, contenu_tweet = await get_tweet(user_id, session, max_results=5)
            except KeyError: # si un tweet est supprimé, il n'y a plus de data, mais il y a toujours une trace. On passe au tweet suivant
                continue
                
            if ('sources' in contenu_tweet.lower() or 'source' in contenu_tweet.lower())\
            and (str(id_tweet) != str(id_last_msg))\
            and ('lec' in contenu_tweet.lower()
                 or 'lcs' in contenu_tweet.lower()
                 or 'lfl' in contenu_tweet.lower()
                 or 'lck' in contenu_tweet.lower()
                 or 'lpl' in contenu_tweet.lower()): 
                
                url_tweet = f'https://twitter.com/{user}/status/{id_tweet}'
                
                data = get_data_bdd(f'''SELECT DISTINCT channels_module.server_id from channels_module 
                                    INNER JOIN tracker on tracker.server_id = channels_module.server_id
                                    where channels_module.twitter = true''').fetchall()


                for server_id in data:
                    discord_server_id = chan_discord(int(server_id[0]))

                    channel_tracklol = await interactions.get(client=self.bot,
                                                                    obj=interactions.Channel,
                                                                    object_id=discord_server_id.lol) 
                    try:
                        await channel_tracklol.send(f'**MERCATO** {user} : ' + url_tweet)
                        requete_perso_bdd('UPDATE twitter SET id_last_msg_twitter = :id_last_msg WHERE id_twitter = :id_twitter', {'id_last_msg' : id_tweet,
                                                                                                                                'id_twitter' : user_id} )
                    except: # pas de détection du channel
                        print(sys.exc_info())
                        pass
        await session.close()


def setup(bot):
    Twitter(bot)