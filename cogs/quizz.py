from interactions import SlashCommandOption, Extension, SlashContext, SlashCommandChoice, slash_command
import interactions
from fonctions.gestion_bdd import requete_perso_bdd, lire_bdd_perso
from fonctions.match import fix_temps
import random
import asyncio
import pandas as pd

class Quizz(Extension):
    def __init__(self, bot):
        self.bot: interactions.Client = bot
        
    def indice_a_trou(self, joueur):
        return f'{joueur[0]}{(len(joueur)-2)*"-"}{joueur[-1]}'    
        
    async def indice(self, ctx : SlashContext, msg : interactions.Message, liste_indice):
        
        time_to_sleep = 60
        
        if len(liste_indice) >= 1:
            await asyncio.sleep(time_to_sleep)
            await msg.edit(content=f'{msg.content} \n **Indice 1** {liste_indice[0]}')
        
        if len(liste_indice) >= 2:
            await asyncio.sleep(time_to_sleep)
            await msg.edit(content=f'{msg.content} \n **Indice 2** {liste_indice[1]}')

        if len(liste_indice) >= 3:
            await asyncio.sleep(time_to_sleep)
            await msg.edit(content=f'{msg.content} \n **Indice 3** {liste_indice[2]}')
            
        if len(liste_indice) >= 4:
            await asyncio.sleep(time_to_sleep)
            await msg.edit(content=f'{msg.content} \n **Indice 4** {liste_indice[3]}')
            
        if len(liste_indice) >= 5:
            await asyncio.sleep(time_to_sleep * 2)
            await msg.edit(content=f'{msg.content} \n **Indice 5** {liste_indice[4]}')
    
    async def gestion_quizz(self, ctx : SlashContext, quizz_selected, championnat_selected, stat_selected, df_reponse):
        async def check(msg : interactions.api.events.MessageCreate):
            if msg.message.content.startswith('?'):
                return True
            else:
                return False
            
        if quizz_selected == 'Top1':
            
            joueur = df_reponse['playername']
            date = df_reponse['date']
            equipe = df_reponse['teamname']
            position = df_reponse['position']
            
            while True:
 
                    
                try:
                        
                    answer : interactions.api.events.MessageCreate = await self.bot.wait_for(interactions.api.events.MessageCreate,
                                                                                                 checks=check,
                                                                                                 timeout=600)
                        
                    print(joueur)
                                               
                    answer_content = answer.message.content[1:]
                    answer_author = answer.message.author
                    discord_id = int(answer_author.id)

                        
                    if joueur.lower() == answer_content.lower():
                        await ctx.send(f"Bonne réponse !' C'est {joueur} avec **{df_reponse[stat_selected]}** le {date} avec {equipe}")
                        requete_perso_bdd(f'''INSERT INTO quizz({discord_id}) VALUES ({discord_id})
                                                    ON CONFLICT (discord_id)
                                                    DO NOTHING;
                                                    UPDATE quizz
                                                SET count_top1="count_top1"+1, result_top1="result_top1"+1
                                                WHERE discord_id = {discord_id};''')
                        break
                    else:
                        await ctx.send('Mauvaise réponse !')
                
                except asyncio.TimeoutError:
                        
                    await ctx.send(f'Fini ! La réponse était {joueur}' )
                    break                    

        elif quizz_selected == 'Top5':

            joueur = df_reponse['playername'].tolist()
            score = df_reponse[stat_selected].tolist()
            date = df_reponse['date'].tolist()
            position = df_reponse['position'].tolist()
                        
            while True:    

                try:
                    answer : interactions.api.events.MessageCreate = await self.bot.wait_for(interactions.api.events.MessageCreate,
                                                                                                 checks=check,
                                                                                                 timeout=600)
                        
                    answer_content = answer.message.content[1:].lower().split(', ')
                    answer_author = answer.message.author
                    discord_id = int(answer_author.id)
                        
                    print(joueur)
                    print(answer_content)

                    if joueur == answer_content:
                        txt_result = ''
                        for player, score, date in zip(joueur, score, date):
                            txt_result += f'**{player}** : {score} ({date}) | '
                        await ctx.send(f'Bonne réponse ! {txt_result}')
                        requete_perso_bdd(f'''INSERT INTO quizz(discord_id) VALUES ({discord_id})
                                                    ON CONFLICT (discord_id)
                                                    DO NOTHING;
                                                    UPDATE quizz
                                                SET count_top5="count_top5"+1, result_top1="result_top5"+1
                                                WHERE discord_id = {discord_id};''')
                        break
                    else:

                        elements_identiques = []
                                
                                
                        try:
                                    # Parcourez les deux listes en utilisant une boucle for
                            for i in range(len(joueur)):
                                if joueur[i] == answer_content[i]:
                                    elements_identiques.append(joueur[i])
                                            
                                    # Trouver l'intersection des deux ensembles
                            ensemble1 = set(joueur)
                            ensemble2 = set(answer_content)
                            intersection = ensemble1.intersection(ensemble2)

                                    # Convertir l'intersection en liste (si nécessaire)
                            joueur_trouves = list(intersection)
                                    
                                    # Format
                            joueur_trouves_format = f"**{', '.join(joueur_trouves)}**"
                            elements_identiques_format = f"**{', '.join(elements_identiques)}**"
                                    
                            if joueur_trouves_format == '':
                                joueur_trouves_format = 'personne'
                            if elements_identiques_format == '':    
                                elements_identiques_format = 'Aucun ne'

                            await ctx.send(f"Mauvaise réponse... Tu as trouvé {joueur_trouves_format}. {elements_identiques_format} sont bien placés.")
                
                        except IndexError: # le joueur n'a pas donné assez de réponse
                            await ctx.send("Tu n'as pas donné assez de réponse")
                                    
                except asyncio.TimeoutError:
                        
                    await ctx.send(f'Fini ! La réponse était {joueur}' )
                    break
                
        elif quizz_selected == 'Joueur':
            # pour celui-ci, df_reponse = le joueur
            while True:    
     
                try:
                    answer : interactions.api.events.MessageCreate = await self.bot.wait_for(interactions.api.events.MessageCreate,
                                                                                                 checks=check,
                                                                                                 timeout=600)                     
                    answer_content = answer.message.content.lower()[1:]
                    answer_author = answer.message.author
                    discord_id = int(answer_author.id)
                        
                    print(df_reponse)
                    print(answer_content)
                        
                    if df_reponse.lower() == answer_content:
                        await ctx.send('Bonne réponse !')
                        requete_perso_bdd(f'''INSERT INTO quizz(discord_id) VALUES ({discord_id})
                                                    ON CONFLICT (discord_id)
                                                    DO NOTHING;
                                                    UPDATE quizz
                                                SET count_joueur="count_joueur"+1, result_joueur="result_joueur"+1
                                                WHERE discord_id = {discord_id};''')
                        break
                    else:
                        await ctx.send('Mauvaise réponse')
                
                except asyncio.TimeoutError:
                        
                    await ctx.send(f'Fini ! La réponse était {df_reponse}')
                    break
                
        elif quizz_selected == 'Top4team':
            joueur = df_reponse['teamname'].tolist()
            score = df_reponse[stat_selected].tolist()
            date = df_reponse['date'].tolist()
            while True:
                try:
                    answer : interactions.api.events.MessageCreate = await self.bot.wait_for(interactions.api.events.MessageCreate,
                                                                                                    checks=check,
                                                                                                    timeout=600)                                            
                    answer_content = answer.message.content[1:].lower().split(', ')
                    answer_author = answer.message.author
                    discord_id = int(answer_author.id)
                            
                    print(joueur)
                    print(answer_content)

                    if joueur == answer_content:
                        txt_result = ''
                        for player, score, date in zip(joueur, score, date):
                            txt_result += f'**{player}** : {score} ({date}) | '
                        await ctx.send(f'Bonne réponse ! {txt_result}')
                        requete_perso_bdd(f'''INSERT INTO quizz(discord_id) VALUES ({discord_id})
                                                        ON CONFLICT (discord_id)
                                                        DO NOTHING;
                                                        UPDATE quizz
                                                    SET count_top6_team="count_top6_team"+1, result_top6_team="result_top6_team"+1
                                                    WHERE discord_id = {discord_id};''')
                        break
                    else:
                        elements_identiques = []

                        try:
                                # Parcourez les deux listes en utilisant une boucle for
                            for i in range(len(joueur)):
                                if joueur[i] == answer_content[i]:
                                    elements_identiques.append(joueur[i])
                                                
                                    # Trouver l'intersection des deux ensembles
                            ensemble1 = set(joueur)
                            ensemble2 = set(answer_content)
                            intersection = ensemble1.intersection(ensemble2)

                                    # Convertir l'intersection en liste (si nécessaire)
                            joueur_trouves = list(intersection)
                                        
                                    # Format
                            joueur_trouves_format = f"**{', '.join(joueur_trouves)}**"
                            elements_identiques_format = f"**{', '.join(elements_identiques)}**"
                                        
                            if joueur_trouves_format == '':
                                joueur_trouves_format = 'personne'
                            if elements_identiques_format == '':    
                                elements_identiques_format = 'Aucun ne'

                            await ctx.send(f"Mauvaise réponse... Tu as trouvé {joueur_trouves_format}. {elements_identiques_format} sont bien placés.")
                        
                        except IndexError: # le joueur n'a pas donné assez de réponse
                                await ctx.send("Tu n'as pas donné assez de réponse")
                                
                except asyncio.TimeoutError:
                            
                    await ctx.send(f'Fini ! La réponse était {joueur}')
                    break
                
    @slash_command(name='quizz_lol',
                   description='Quizz lol')
    async def quizz_lol(self, ctx: SlashContext):

        await ctx.defer(ephemeral=False)
        

        
        await ctx.send('Pour répondre, le message doit être au format `?Réponse` ')
        

        quizz_selected = random.choice(['Top1', 'Top5', 'Top4team', 'Joueur'])
    
        if quizz_selected in ['Top1', 'Top5']:
                        
            def __sort_stats(df, stat, filter_league : list = None):

                df_cs = df.sort_values([stat], ascending=False)

                df_cs = df_cs.dropna(subset=['playername']) # on vire les équipes
                
                if filter_league != None:
                    df_cs = df_cs[df_cs['league'].isin(filter_league)]

                return df_cs[['league', 'playername', 'champion', 'position', 'teamname', 'date', stat]]
            
            

            championnat_selected = random.choice(['LEC', 'LCS', 'LFL', 'LCK', 'MSI', 'Worlds'])
            stat_selected = random.choice(['kills', 'total cs', 'deaths', 'assists', 'doublekills', 'triplekills', 'quadrakills', 'damagetochampions', 'visionscore'])

            df_stats = lire_bdd_perso(f'''SELECT index, league, date, champion, position, playername, teamname, "{stat_selected}" from data_history_lol
                                      WHERE league = '{championnat_selected}' ''').T            
            
            df_filter = __sort_stats(df_stats, stat_selected, [championnat_selected])
            
            del df_stats
            
            df_filter = df_filter.sort_values(stat_selected, ascending=False)
            
        
            if quizz_selected == 'Top1':  
                
                result = df_filter.head(1).iloc[0]  
                joueur = result['playername']
                # date = result['date']
                # equipe = result['teamname']
                position = result['position']
        

                indice1 = f'Il joue au poste {position}.'

                indice2 = f' La réponse commence par {joueur[0]}'

                indice3 = f'La réponse finit par {joueur[-1]}'

                indice4 = f'La réponse est en {len(joueur)} lettres.'
                
                liste_indice = [indice1, indice2, indice3, indice4]

                msg = await ctx.send(f'Quel joueur a le record de {stat_selected} en {championnat_selected} en une seule partie ?')

                    
            elif quizz_selected == 'Top5':  
                
                result = df_filter.head(5) 
                result['playername'] = result['playername'].apply(lambda x : x.lower())
                joueur = result['playername'].tolist()
                # score = result[stat_selected].tolist()
                # date = result['date'].tolist()
                position = result['position'].tolist()
                
                
                indice1 = f"{', '.join(position)}"
                indice2 = f'{joueur[0][0]} - {joueur[1][0]} - {joueur[2][0]} - {joueur[3][0]} - {joueur[4][0]}'
                indice3 = f'{self.indice_a_trou(joueur[0])} - {self.indice_a_trou(joueur[1])} - {self.indice_a_trou(joueur[2])} - {self.indice_a_trou(joueur[3])} - {self.indice_a_trou(joueur[4])}'
                
                liste_indice = [indice1, indice2, indice3]

                msg = await ctx.send(f'Le top 5 des joueurs avec le record de **{stat_selected}** en **{championnat_selected}** ? \n La réponse doit être au format : `?Joueur1, Joueur2, Joueur3, Joueur4, Joueur5` ')
                
                
                

                    
        elif quizz_selected in ['Joueur']:  
            
            championnat_selected = None
            
            df_joueur = lire_bdd_perso('''SELECT index, league, date, playername, position, teamname from data_history_lol ''').T
            
            df_joueur_filter = df_joueur[df_joueur['league'].isin(['LEC', 'LCS', 'LFL', 'LCK', 'Worlds'])]

            result = random.choice(df_joueur_filter['playername'].unique().tolist())
            
            df_joueur_history = df_joueur[df_joueur['playername'] == result]
            
            df_joueur_history['date'] = pd.to_datetime(df_joueur_history['date'])
                
            df_joueur_history = df_joueur_history.sort_values('date')
            
            df_joueur_history['year'] = df_joueur_history['date'].dt.year
            
            df_joueur_unique = df_joueur_history.drop_duplicates(subset=['league', 'teamname', 'position', 'year'])

            del df_joueur, df_joueur_filter

            
            indice1 = f'La réponse commence par {result[:1]}.'

            indice2 = f'La réponse finit par {result[1:]}'
            
            indice3 = self.indice_a_trou(result)
            
            liste_indice = [indice1, indice2, indice3]
                
            txt = ''

            for index, data in df_joueur_unique.iterrows():
                txt += f'''**{data['year']}** : {data['teamname']} ({data['league']}) en tant que {data['position']} \n'''
                

            msg = await ctx.send(txt)
                      

        elif quizz_selected == 'Top4team':
            def __sort_stats_equipe(df, stat, filter_league : list = None):

                            df_cs = df.sort_values([stat], ascending=False)

                            df_cs = df_cs[df_cs['position'] == 'team'] # on ne retient que les équipes
                            
                            if filter_league != None:
                                df_cs = df_cs[df_cs['league'].isin(filter_league)]

                            return df_cs[['league', 'teamname', 'date', stat]]
            
            

            championnat_selected = random.choice(['LEC', 'LCS', 'LFL', 'LCK', 'MSI', 'Worlds'])
            stat_selected = random.choice(['kills', 'gamelength'])

            df_stats = lire_bdd_perso(f'''SELECT index, league, date, position, teamname, "{stat_selected}" from data_history_lol
                                      WHERE league = '{championnat_selected}' ''').T            
            
            df_filter = __sort_stats_equipe(df_stats, stat_selected, [championnat_selected])
            
            del df_stats
            
            df_filter = df_filter.sort_values(stat_selected, ascending=False)
            
                 
            result = df_filter.head(4) 
            result['teamname'] = result['teamname'].apply(lambda x : x.lower())
            joueur = result['teamname'].tolist()
            # score = result[stat_selected].tolist()
            # date = result['date'].tolist()
            
            indice1 = f'{joueur[0][0]} - {joueur[1][0]} - {joueur[2][0]} - {joueur[3][0]}'
            indice2 = f'{self.indice_a_trou(joueur[0])} - {self.indice_a_trou(joueur[1])} - {self.indice_a_trou(joueur[2])} - {self.indice_a_trou(joueur[3])}'
            
            liste_indice = [indice1, indice2]
                

            msg = await ctx.send(f'Le top 4 des équipes avec le record de **{stat_selected}** en **{championnat_selected}** en 1 seule game ? \n La réponse doit être au format : `?Equipe1, Equipe2, Equipe3, Equipe4` ')

        await asyncio.gather(self.gestion_quizz(ctx, quizz_selected, championnat_selected, stat_selected, result),
                             self.indice(ctx, msg, liste_indice))

    



# await asyncio.gather(coro(), coro2())
def setup(bot):
    Quizz(bot)
