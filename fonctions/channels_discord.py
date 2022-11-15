from fonctions.gestion_bdd import lire_bdd_perso

class chan_discord():

    def __init__(self, server_id:int):
        self.server_id = server_id
        
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

        
