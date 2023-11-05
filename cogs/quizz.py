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

    @slash_command(name='quizz_lol',
                   description='participer')
    async def fantasy_add(self, ctx: SlashContext):

        await ctx.defer(ephemeral=False)
        
        quizz_selected = random.choice(['Top1', 'Top5', 'Joueur'])
        
        async def check(msg : interactions.api.events.MessageCreate):
            if int(msg.message.author.id) == int(ctx.author.id):
                return True
            else:
                return False
        
        if quizz_selected in ['Top1', 'Top5']:
                        
            def __sort_stats(df, stat, filter_league : list = None):

                df_cs = df.sort_values([stat], ascending=False)

                df_cs = df_cs.dropna(subset=['playername']) # on vire les équipes
                
                if filter_league != None:
                    df_cs = df_cs[df_cs['league'].isin(filter_league)]

                return df_cs[['league', 'playername', 'champion', 'teamname', 'date', stat]]
            
            
            df_stats = lire_bdd_perso('''SELECT index, league, date, champion, playername, teamname, kills, "total cs" from data_history_lol ''').T
            championnat_selected = random.choice(['LEC', 'LCS', 'LFL','MSI', 'Worlds'])
            stat_selected = random.choice(['kills', 'total cs'])
            
            
            df_filter = __sort_stats(df_stats, stat_selected, [championnat_selected])
            
            df_filter = df_filter.sort_values(stat_selected, ascending=False)
            
            nb_essais = 5
        
            if quizz_selected == 'Top1':  
                
                result = df_filter.head(1).iloc[0]  
                joueur = result['playername']
                date = result['date']
        
                print(joueur)
                

                await ctx.send(f'Quel joueur a le record de {stat_selected} en {championnat_selected} ?')
                    
                while True:    
                    
                    try:
                        answer : interactions.api.events.MessageCreate = await self.bot.wait_for(interactions.api.events.MessageCreate,
                                                                                                 checks=check,
                                                                                                 timeout=60)
                        
                        answer_content = answer.message.content
                        
                        if joueur.lower() == answer_content.lower():
                            await ctx.send(f"Bonne réponse !' C'est {joueur} avec **{result[stat_selected]}** le {date} ")
                            break
                        else:
                            nb_essais -= 1
                            
                            if nb_essais==0:
                                await ctx.send("Aie, tu as utilisé tous tes essais")
                                break
                            else:
                                await ctx.send(f'Mauvaise réponse... Tu as encore {nb_essais} essais')
                
                    except asyncio.TimeoutError:
                        
                        await ctx.send('Fini !')
                        break
                    
            elif quizz_selected == 'Top5':  
                
                result = df_filter.head(5) 
                result['playername'] = result['playername'].apply(lambda x : x.lower())
                joueur = result['playername'].tolist()
                score = result[stat_selected].tolist()
                date = result['date'].tolist()
                

                await ctx.send(f'Le top 5 des joueurs avec le record de **{stat_selected}** en **{championnat_selected}** ? \n La réponse doit être au format :`Joueur1, Joueur2, Joueur3, Joueur4, Joueur5` ')
                    
                while True:    
                    
                    try:
                        answer : interactions.api.events.MessageCreate = await self.bot.wait_for(interactions.api.events.MessageCreate,
                                                                                                 checks=check,
                                                                                                 timeout=180)
                        
                        answer_content = answer.message.content.lower().split(', ')
                        
                        print(joueur)
                        print(answer_content)
                        

                        if joueur == answer_content:
                            txt_result = ''
                            for player, score, date in zip(joueur, score, date):
                                txt_result += f'**{player}** : {score} ({date}) | '
                            await ctx.send(f'Bonne réponse ! {txt_result}')
                            break
                        else:
                            nb_essais -= 1
                            
                            if nb_essais==0:
                                await ctx.send("Aie, tu as utilisé tous tes essais")
                                break
                            else:
                                elements_identiques = []

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
                                    elements_identiques_format = 'aucun'

                                await ctx.send(f"Mauvaise réponse... Tu as trouvé {joueur_trouves_format} et {elements_identiques_format} sont bien placés. Tu as encore {nb_essais} essais")
                
                    except asyncio.TimeoutError:
                        
                        await ctx.send('Fini !')
                        break
                    
        elif quizz_selected in ['Joueur']:  
            
            df_joueur = lire_bdd_perso('''SELECT index, league, date, playername, position, teamname from data_history_lol ''').T
            
            df_joueur_filter = df_joueur[df_joueur['league'].isin(['LEC', 'LCS', 'LFL', 'LPL', 'LCK', 'Worlds'])]

            joueur_selected = random.choice(df_joueur_filter['playername'].unique().tolist())

            df_joueur_history = df_joueur[df_joueur['playername'] == joueur_selected]
            
            df_joueur_history['date'] = pd.to_datetime(df_joueur_history['date'])
                
            df_joueur_history = df_joueur_history.sort_values('date')
            
            df_joueur_history['year'] = df_joueur_history['date'].dt.year
            
            df_joueur_unique = df_joueur_history.drop_duplicates(subset=['teamname', 'position', 'year'])

            
            txt = ''

            for index, data in df_joueur_unique.iterrows():
                txt += f'''**{data['year']}** : {data['teamname']} ({data['league']}) en tant que {data['position']} \n'''
                

            await ctx.send(txt)
            
            nb_essais = 10
                    
            while True:    
                    
                try:
                    answer : interactions.api.events.MessageCreate = await self.bot.wait_for(interactions.api.events.MessageCreate,
                                                                                                 checks=check,
                                                                                                 timeout=180)
                        
                    answer_content = answer.message.content.lower()
                        
                    print(joueur_selected.lower())
                    print(answer_content)
                        
                    if joueur_selected.lower() == answer_content:
                        await ctx.send('Bonne réponse !')
                        break
                    else:
                        nb_essais -= 1
                            
                        if nb_essais==0:
                            await ctx.send("Aie, tu as utilisé tous tes essais")
                            break
                        else:
                            await ctx.send(f'Mauvaise réponse... Tu as encore {nb_essais} essais')

                
                except asyncio.TimeoutError:
                        
                    await ctx.send('Fini !')
                    break



def setup(bot):
    Quizz(bot)
