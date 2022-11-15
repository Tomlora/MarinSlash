from fonctions.gestion_bdd import lire_bdd_perso, requete_perso_bdd

class chan_discord():

    def __init__(self, server_id:int):
        self.server_id = server_id
        
        # si le serveur n'est pas dans la liste :
        self.data = lire_bdd_perso(f'SELECT server_id from channels_discord', index_col='server_id').transpose() 
        
        if not int(self.server_id) in self.data.index:
            self.verif_server() 
                
        self.dict_channel = lire_bdd_perso('Select * from channels_discord where server_id = %(server_id)s', index_col='server_id', format='dict', params={'server_id' : self.server_id} )
        
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
            
            # on vérifie que le serveur est enregistré
        
        requete_perso_bdd(f'''INSERT INTO public.channels_discord(
                    server_id, id_owner, id_owner2, chan_pm, chan_tracklol, chan_accueil, chan_twitch, chan_lol, chan_tft, chan_lol_others, role_admin)
                    VALUES (:server_id, :chan, :chan, :chan, :chan, :chan, :chan, :chan, :chan, :chan, :chan);''',
                {'server_id' : self.server_id, 'chan' : self.text_channel_list[0]})
             

        
