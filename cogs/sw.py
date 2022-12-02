import interactions
from interactions import Choice, Option, Extension, CommandContext
import aiohttp
from datetime import datetime
from fonctions.profil_sw import Rune, Artefact, comparaison
import pandas as pd
import dataframe_image as dfi
import os
import io
import json

from fonctions.gestion_bdd import sauvegarde_bdd_sw, update_info_compte, get_user, requete_perso_bdd

def date_du_jour():
    currentMonth = str(datetime.now().month)
    currentYear = str(datetime.now().year)
    currentDay = str(datetime.now().day)
    return f'{currentDay}/{currentMonth}/{currentYear}'

# Params
category_selected = ['Violent', 'Will', 'Destroy', 'Despair']
category_value = ", ".join(category_selected)

coef_set = {'Violent' : 3,
            'Will' : 3,
            'Destroy' : 2,
            'Despair' : 2}

category_selected_spd = ['Violent', 'Will', 'Destroy', 'Despair', 'Swift']
category_value_spd = ", ".join(category_selected)

coef_set_spd = {'Violent' : 3,
            'Will' : 3,
            'Destroy' : 2,
            'Despair' : 2,
            'Swift' : 3}

class SW(Extension):
    def __init__(self, bot):
        self.bot : interactions.Client = bot
        
        
        
    @interactions.extension_command(name="analyse_sw",
                       description="Summoners Wars",
                       options=[Option(
                           name='scoring',
                           description='Quel type de scoring ?',
                           type=interactions.OptionType.STRING,
                           required=False,
                           choices=[
                               Choice(name='general', value='general'),
                               Choice(name='artefact', value='artefact'),
                               Choice(name='speed', value='speed')
                           ]
                       ),
                           Option(
                                    name="id_msg",
                                    description="Quel mode de jeu ?",
                                    type=interactions.OptionType.STRING, # int pas assez grand pour discord
                                    required=False),
                                    Option(
                                        name='fichier_json',
                                        description='Fichier json',
                                        type=interactions.OptionType.ATTACHMENT,
                                        required=False
                                    )])
    async def analyse_sw(self, ctx:CommandContext, scoring:str = 'general', id_msg:str=None, fichier_json : interactions.Attachment=None):
        
        if id_msg != None:
            session = aiohttp.ClientSession()
            
            id_msg = int(id_msg)
            await ctx.defer(ephemeral=False)
            
            message = await interactions.get(self.bot, interactions.Message, object_id=id_msg, parent_id=ctx.channel_id)
            
            file : interactions.Attachment = message.attachments[0]
            
            async with session.get(file.url) as sw_json:
                data_json = await sw_json.json()
            
            if not file.filename.endswith('.json'):
                await session.close()
                return await ctx.send("Ce n'est pas un fichier json")
        
        if fichier_json != None:
            file = await fichier_json.download()
            data_json = io.TextIOWrapper(file, encoding='utf-8')
            
            data_json = json.load(data_json)
        
        

        
        # info du compte
        
        pseudo = data_json['wizard_info']['wizard_name']
        guildeid = data_json['guild']['guild_info']['guild_id']
        guilde = data_json['guild']['guild_info']['name']
        compteid = data_json['wizard_info']['wizard_id']
        

        data_rune = Rune(data_json)
        await data_rune.prepare_data()

        data_arte = Artefact(data_json)
        await data_arte.prepare_data()

  

        
        # --------------------- calcul score rune
        
        tcd_value, score = await data_rune.scoring_rune(category_selected, coef_set) 
        

        # -------------------------- calcul score spd rune
        
        tcd_spd, score_spd = await data_rune.scoring_spd(category_selected_spd, coef_set_spd)
        

        # calcul score arte
        
        tcd_arte, score_arte = await data_arte.scoring_arte()

        # -------------------------- on enregistre
        try:
            id_joueur, visibility, guilde_id = await get_user(compteid, type='id')
        except IndexError:
            try:
                id_joueur, visibility, guilde_id = await get_user(pseudo, id_compte=compteid)
            except IndexError: #le joueur n'existe pas ou est dans l'ancien système
                requete_perso_bdd('''INSERT INTO sw_user(joueur, visibility, guilde_id, joueur_id) VALUES (:joueur, 0, :guilde_id, :joueur_id);
                                  INSERT INTO sw_guilde(guilde, guilde_id) VALUES (:guilde, :guilde_id)
                                  ON CONFLICT (guilde_id)
                                  DO NOTHING;''',
                                    {'joueur' : pseudo,
                                    'guilde' : guilde,
                                    'guilde_id' : guildeid,
                                    'joueur_id' : compteid})
                
                id_joueur, visibility, guilde_id = await get_user(pseudo)
        
        # Enregistrement SQL
        

        tcd_value['id'] = id_joueur
        tcd_value['date'] = date_du_jour()
        

        
        sauvegarde_bdd_sw(tcd_value, 'sw', 'append')
        

       
        df_scoring = pd.DataFrame({'id' : [id_joueur], 'score' : [score],
                                   'date' : [date_du_jour()]})
        df_scoring.set_index('id', inplace=True)
        
        sauvegarde_bdd_sw(df_scoring, 'sw_score', 'append')
        
        # MAJ guilde
        
        update_info_compte(pseudo, guildeid, compteid) # on update le compte
        
        # On cherche les infos d'Endless...
        
        size_general, avg_score_general, max_general, size_guilde, avg_score_guilde, max_guilde, df_max, df_guilde_max = await comparaison(116424)
        
        result = {
            'general' : [tcd_value[[100,110,120]], score],
            'artefact' : [tcd_arte, score_arte],
            'speed' : [tcd_spd, score_spd]
        }
        dfi.export(result[scoring][0], 'image.png', max_cols=-1, max_rows=-1, table_conversion="matplotlib")
        
        embed = interactions.Embed()
        file = interactions.File(f'image.png')
                        # On prépare l'embed

        
        if scoring == 'general':
            embed.add_field(name=f'Scoring {scoring}', value = f'Joueur : **{pseudo}**\n' +
            f'Score : **{result[scoring][1]}** (__Moyenne Endless__ : **{avg_score_guilde}** )\n' +
            f'Guilde : **{guilde}**')
        else:
            embed.add_field(name=f'Scoring {scoring}', value = f'Joueur : **{pseudo}**\n' +
            f'Score : **{result[scoring][1]}**\n' +
            f'Guilde : **{guilde}**')
            
        embed.set_image(url=f'attachment://image.png')
        
        await ctx.send(embeds=embed, files=file)
        
        os.remove('image.png')
        
        if id_msg != None:
            await session.close()
        

        
        
def setup(bot):
    SW(bot)