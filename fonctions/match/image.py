"""
Classe matchlol - Partie 9: Génération d'image de résumé.
"""

import numpy as np
from io import BytesIO
from PIL import Image, ImageDraw

from fonctions.gestion_bdd import lire_bdd, get_data_bdd, lire_bdd_perso, requete_perso_bdd
from utils.lol import elo_lp, dict_points
from utils.emoji import emote_rank_discord
import pandas as pd
from .riot_api import get_image
from .utils import charger_font, range_value
from fonctions.api_calls import getRanks


class ImageGenerationMixin:
    """Mixin pour la génération d'images de résumé."""

    async def get_theme(self):

        dict_color = lire_bdd_perso(f'''SELECT *                                   
                                     from theme
        where index = (select theme from tracker where puuid = '{self.puuid}' ) ''', format='dict', index_col=None)[0]

        principal = (dict_color['r_principal'], dict_color['g_principal'], dict_color['b_principal'])
        secondaire = (dict_color['r_secondaire'], dict_color['g_secondaire'], dict_color['b_secondaire'])
        texte = (dict_color['r_texte'], dict_color['g_texte'], dict_color['b_texte'])
        player = (dict_color['r_player'], dict_color['g_player'], dict_color['b_player'])

        dict_scoring = {1 : (dict_color['r_top1'], dict_color['g_top1'], dict_color['b_top1']),
                        2 : (dict_color['r_top2'], dict_color['g_top2'], dict_color['b_top2']),
                        3 : (dict_color['r_top3'], dict_color['g_top3'], dict_color['b_top3']),
                        8 : (dict_color['r_top8'], dict_color['g_top8'], dict_color['b_top8']),
                        9 : (dict_color['r_top9'], dict_color['g_top9'], dict_color['b_top9']),
                        10 : (dict_color['r_top10'], dict_color['g_top10'], dict_color['b_top10'])}
        

        victoire60 = (dict_color['r_victoire60'], dict_color['g_victoire60'], dict_color['b_victoire60'])
        victoire50 = (dict_color['r_victoire50'], dict_color['g_victoire50'], dict_color['b_victoire50'])
        victoire30 = (dict_color['r_victoire30'], dict_color['g_victoire30'], dict_color['b_victoire30'])


        kda5 = (dict_color['r_kda5'], dict_color['g_kda5'], dict_color['b_kda5'])
        kda4 = (dict_color['r_kda4'], dict_color['g_kda4'], dict_color['b_kda4'])
        kda3 = (dict_color['r_kda3'], dict_color['g_kda3'], dict_color['b_kda3'])
        kda1 = (dict_color['r_kda1'], dict_color['g_kda1'], dict_color['b_kda1'])

        allie = (dict_color['r_allie'], dict_color['g_allie'], dict_color['b_allie'])
        ennemi = (dict_color['r_ennemi'], dict_color['g_ennemi'], dict_color['b_ennemi'])

        texte_allie = (dict_color['r_texte_allie'], dict_color['g_texte_allie'], dict_color['b_texte_allie'])
        texte_ennemi = (dict_color['r_texte_ennemi'], dict_color['g_texte_ennemi'], dict_color['b_texte_ennemi'])

        return principal, secondaire, texte, player, dict_scoring, victoire60, victoire50, victoire30, kda5, kda4, kda3, kda1, allie, ennemi, texte_allie, texte_ennemi


    async def resume_general(self,
                             name_img,
                             embed,
                             difLP):


        principal, secondaire, fill, player, color_scoring, victoire60, victoire50, victoire30, kda5, kda4, kda3, kda1, color_allie, color_ennemi, txt_allie, txt_ennemi = await self.get_theme()

        meilleur_joueur = color_scoring[1]
        pire_joueur = color_scoring[10]
 

        # Gestion de l'image 2
        lineX = 3050
        lineY = 100


        
        x_ecart = 125
        x_kills = 1000 + 280
        x_score = x_kills - 160
        x_deaths = x_kills + 100
        x_assists = x_deaths + 100
        x_level = x_score - 125

        x_kda = x_assists + 110

        x_kp = x_kda + 150

        x_cs = x_kp + 150

        x_vision = x_cs + 150

        x_dmg_percent = x_vision + 110

        x_dmg_taken = x_dmg_percent + 260

        x_kill_total = 850
        x_objectif = 2000


        x_name = 260
        y = 120
        y_name = y - 60
        x_rank = 2250

        x_metric = 120
        y_metric = 400

        font = charger_font(50)
        font_little = charger_font(40)        


        im = Image.new("RGBA", (lineX, lineY * 13 + 190),
                       principal)  # Ligne blanche
        d = ImageDraw.Draw(im)

        line = Image.new("RGB", (lineX, 190), secondaire)  # Ligne grise
        im.paste(line, (0, 0))

        if len(self.riot_id) <= 12: # Sinon trop long et écrase le kda
            d.text((x_name-240, y_name+60), self.riot_id, font=font, fill=fill)


            im.paste(im=await get_image("avatar", self.avatar, self.session, 100, 100, self.version['n']['profileicon']),
                    box=(x_name-240, y_name-50))
            try:
                im.paste(im=await get_image("champion", self.thisChampName, self.session, 100, 100, self.version['n']['profileicon']),
                    box=(x_name-120, y_name-50))
            except:
                im.paste(im=await get_image("champion", self.thisChampName.capitalize(), self.session, 100, 100, self.version['n']['profileicon']),
                    box=(x_name-120, y_name-50))
        else:
            im.paste(im=await get_image("avatar", self.avatar, self.session, 100, 100, self.version['n']['profileicon']),
                    box=(x_name-240, y_name-20))
            try:
                im.paste(im=await get_image("champion", self.thisChampName, self.session, 100, 100, self.version['n']['profileicon']),
                        box=(x_name-120, y_name-20))
            except:
                im.paste(im=await get_image("champion", self.thisChampName.capitalize(), self.session, 100, 100, self.version['n']['profileicon']),
                        box=(x_name-120, y_name-20))

        d.text((x_name+1000, y_name-20),
               f"Niveau {self.level_summoner}", font=font_little, fill=fill)


        try:
            if not self.thisQ in ['ARAM', 'CLASH ARAM']:
                data_last_season = get_data_bdd(f'''SELECT index, tier, rank from suivi_s{self.last_season} where index = {self.id_compte} ''')
                data_last_season = data_last_season.mappings().all()[0]
                self.tier_last_season = data_last_season['tier']
                self.rank_last_season = data_last_season['rank']
            else:
                data_last_season = get_data_bdd(f'''SELECT index, rank from ranked_aram_s{self.season-1} where index = {self.id_compte} ''')
                self.tier_last_season = data_last_season.mappings().all()[0]['rank']

            img_tier_last_season = await get_image("tier", self.tier_last_season, self.session, 100, 100)

            im.paste(img_tier_last_season,(x_name+1250, y_name-50), img_tier_last_season.convert('RGBA'))
            if not self.thisQ in ['ARAM', 'CLASH ARAM']:
                d.text((x_name+1350, y_name-30), f'{self.rank_last_season}', font=font, fill=fill)   

        except Exception:
            pass  

        if not self.thisQ in ["ARAM", 'CLASH ARAM']:  # si ce n'est pas le mode aram, on prend la soloq normal
            if self.thisTier != ' ':  # on vérifie que le joueur a des stats en soloq, sinon il n'y a rien à afficher

                requete_perso_bdd('''UPDATE matchs SET ecart_lp = :ecart_lp WHERE match_id = :match_id AND joueur = :id_compte''', {'ecart_lp': difLP,
                                                                                                                        'match_id': self.last_match,
                                                                                                                        'id_compte': self.id_compte})
                img_rank = await get_image('tier', self.thisTier, self.session, 220, 220)

                im.paste(img_rank, (x_rank, y-140), img_rank.convert('RGBA'))

                d.text((x_rank+220, y-110),
                       f'{self.thisTier} {self.thisRank}', font=font, fill=fill)
                d.text((x_rank+220, y-45),
                       f'{self.thisLP} LP ({difLP})', font=font_little, fill=fill)


                d.text(
                        (x_rank+220, y+10), f'{self.thisVictory}W {self.thisLoose}L     {self.thisWinrateStat}% ', font=font_little, fill=fill)
            else:  # si pas de stats en soloq
                d.text((x_rank+220, y-45), 'En placement', font=font, fill=fill)

        else:  # si c'est l'aram, le traitement est différent

            data_aram = get_data_bdd(f''' SELECT ranked_aram_s{self.season}.index,wins, losses, lp, games, k, d, a, ranked_aram_s{self.season}.activation, rank, serie
                                     from ranked_aram_s{self.season}
                                     INNER JOIN tracker on tracker.id_compte = ranked_aram_s{self.season}.index
                                     WHERE tracker.id_compte = :id_compte ''',
                                     {'id_compte': self.id_compte}).mappings().all()

            wins_actual = data_aram[0]['wins']
            losses_actual = data_aram[0]['losses']
            lp_actual = data_aram[0]['lp']
            games_actual = data_aram[0]['games']
            k_actual = data_aram[0]['k']
            d_actual = data_aram[0]['d']
            a_actual = data_aram[0]['a']
            activation = data_aram[0]['activation']
            rank_actual = data_aram[0]['rank']
            serie_wins = data_aram[0]['serie']

            if activation:

                games = games_actual + 1

                if str(self.thisWinId) == 'True':
                    wins = wins_actual + 1
                    losses = losses_actual

                else:
                    wins = wins_actual
                    losses = losses_actual + 1

                wr = round(wins / games, 2)*100

                # si afk et lose, pas de perte
                if self.AFKTeam >= 1 and str(self.thisWinId) != "True":
                    points = 0
                else:
                    # calcul des LP
                    if games <= 5:
                        points = 50 if str(self.thisWinId) == 'True' else 0
                    elif wr >= 60:
                        points = 30 if str(self.thisWinId) == 'True' else -10
                    elif wr <= 40:
                        points = 10 if str(self.thisWinId) == "True" else -20
                    else:
                        if str(self.thisWinId) == "True":
                            points = dict_points[int(wr)][0]
                        else:
                            points = dict_points[int(wr)][1]

                lp = lp_actual + points
                
                # TODO : serie de wins
                
                if self.thisWinBool:
                    serie_wins = serie_wins + 1
                else:
                    serie_wins = 0
                
                if serie_wins > 1:    
                    bonus_lp_serie = serie_wins * 2
                else:
                    bonus_lp_serie = 0 
                    
                lp = lp + bonus_lp_serie  

                # rank

                ranks = [
                    ('IRON', 100),
                    ('BRONZE', 200),
                    ('SILVER', 300),
                    ('GOLD', 500),
                    ('PLATINUM', 800),
                    ('EMERALD', 1100),
                    ('DIAMOND', 1400),
                    ('MASTER', 1600),
                    ('GRANDMASTER', 2000),
                    ('CHALLENGER', float('inf'))
                ]

                for rank, lp_threshold in ranks:
                    if lp < lp_threshold:
                        break
                    
                # SIMULATION CHANGEMENT ELO

                if games > 5 and self.AFKTeam == 0:  # si plus de 5 games et pas d'afk
                    lp = lp - elo_lp[rank]  # malus en fonction du elo

                # pas de lp negatif
                if lp < 0:
                    lp = 0

                if rank_actual != rank:
                    embed.add_field(
                        name="Changement d'elo", value=f" :star: {emote_rank_discord[rank]} Tu es passé de **{rank_actual}** à **{rank}**")

                k = k_actual + self.thisKills
                difLP = lp - lp_actual
                deaths = d_actual + self.thisDeaths
                a = a_actual + self.thisAssists

                img_rank = await get_image('tier', rank, self.session, 220, 220)

                im.paste(img_rank, (x_rank, y-140), img_rank.convert('RGBA'))
                d.text((x_rank+220, y-110), f'{rank}', font=font, fill=fill)
                d.text((x_rank+220, y-45),
                       f'{lp} LP ({difLP})', font=font_little, fill=fill)

                d.text((x_rank+220, y+10),
                       f'{wins}W {losses}L     {round(wr,1)}% ', font=font_little, fill=fill)

                # on met à jour
                requete_perso_bdd(f'''UPDATE ranked_aram_s{self.season}
                                    SET wins = :wins,
                                    losses = :losses,
                                    lp = :lp,
                                    games = :games,
                                    k = :k,
                                    d = :d,
                                    a = :a,
                                    rank = :rank,
                                    serie = :serie
                                  WHERE index = :index;
                                  UPDATE matchs
                                  SET tier = :rank,
                                  lp = :lp
                                  WHERE joueur = :index AND
                                  match_id = :match_id AND
                                  mode='ARAM';''',
                                  {'wins': wins,
                                   'losses': losses,
                                   'lp': lp,
                                   'games': games,
                                   'k': k,
                                   'd': deaths,
                                   'a': a,
                                   'rank': rank,
                                   'index': self.id_compte,
                                   'match_id': self.last_match,
                                   'serie' : serie_wins})  

                requete_perso_bdd('''UPDATE matchs SET ecart_lp = :ecart_lp WHERE match_id = :match_id AND joueur = :joueur''', {'ecart_lp': difLP,
                                                                                                                        'match_id': self.last_match,
                                                                                                                        'joueur': self.id_compte})     

        line = Image.new("RGB", (lineX, lineY), secondaire)  # Ligne grise

        dict_position = {"TOP": 2, "JUNGLE": 3,
                         "MID": 4, "ADC": 5, "SUPPORT": 6}

        def draw_secondaire_line(i: int) -> None:
            im.paste(line, (0, (i * lineY) + 190))

        def draw_blue_line(i: int) -> None:
            im.paste(Image.new("RGB", (lineX, lineY),
                     color_allie), (0, (i * lineY) + 190))

        def draw_red_line(i: int) -> None:
            im.paste(Image.new("RGB", (lineX, lineY),
                     color_ennemi), (0, (i * lineY) + 190))

        def draw_light_blue_line(i: int) -> None:
            im.paste(Image.new("RGB", (lineX, lineY),
                     player), (0, (i*lineY) + 190))

        def draw_text_line() -> None:
            im.paste(Image.new("RGB", (lineX, 3),
                     fill), (0, 180))

        for i in range(13):
            if i % 2 == 0:
                draw_secondaire_line(i)
            elif i == 1:
                draw_blue_line(i)
            elif i == 7:
                draw_red_line(i)

            if not self.thisQ  in ["ARAM", "CLASH ARAM"] and i == dict_position[self.thisPosition]:
                draw_light_blue_line(i)

        draw_text_line()

        # Ban 

        x_ecart_ban = 90

        for i, champ_ban in enumerate(self.liste_ban):
        
            if champ_ban != '-1' and champ_ban != 'Aucun':
                if i <= 4:
                    x_ban = 300 + (i * x_ecart_ban)
                    y_ban = lineY + 200

                    im.paste(im=await get_image("champion", champ_ban, self.session, 80, 80, self.version['n']['profileicon']),
                                box=(x_ban, y_ban))
                
                else:

                    x_ban = 300 + ((i-5) * x_ecart_ban)
                    y_ban = 7* lineY + 200     

                    im.paste(im=await get_image("champion", champ_ban, self.session, 80, 80, self.version['n']['profileicon']),
                                box=(x_ban, y_ban))          

        # match
        d.text((10, 20 + 190), self.thisQ, font=font, fill=fill)

        money = await get_image('gold', 'dragon', self.session, 60, 60)

        # gold team

        im.paste(money, (10, 120 + 190), money.convert('RGBA'))
        d.text((83, 120 + 190), f'{round(self.thisGold_team1/1000,1)}k',
               font=font, fill=txt_allie)
        im.paste(money, (10, 720 + 190), money.convert('RGBA'))
        d.text((83, 720 + 190), f'{round(self.thisGold_team2/1000,1)}k', font=font, fill=txt_ennemi)

        ## AVG rank
        
        if self.moba_ok:
            try:
                self.img_ally_avg = await get_image('tier', self.avgtier_ally.upper(), self.session, 100, 100)

                im.paste(self.img_ally_avg, (x_score-365, 120-20 + 190), self.img_ally_avg.convert('RGBA'))

                d.text((x_score-265, 120 + 190), str(
                            self.avgrank_ally), font=font, fill=txt_allie)

            except FileNotFoundError:
                self.img_ally_avg = 'UNRANKED'
            try:
                self.img_enemy_avg = await get_image('tier', self.avgtier_enemy.upper(), self.session, 100, 100)

                im.paste(self.img_enemy_avg, (x_score-365, 720-20 + 190), self.img_enemy_avg.convert('RGBA'))

            except FileNotFoundError:
                self.img_enemy_avg = 'UNRANKED'

            d.text((x_score-265, 720 + 190), str(
                        self.avgrank_enemy), font=font, fill=txt_ennemi)

        for y in range(123 + 190, 724 + 190, 600):
            color = txt_allie if y == 123 + 190 else txt_ennemi
            d.text((x_level-10, y), 'LVL', font=font, fill=(color))
            # d.text((x_name, y), 'Name', font=font, fill=color)


            d.text((x_kills, y), 'K', font=font, fill=color)
            d.text((x_deaths, y), 'D', font=font, fill=color)
            d.text((x_assists, y), 'A', font=font, fill=color)
            d.text((x_kda, y), 'KDA', font=font, fill=color)
            d.text((x_kp+10, y), 'KP', font=font, fill=color)
            d.text((x_cs, y), 'CS', font=font, fill=color)
            d.text((x_dmg_percent+30, y), "DMG", font=font, fill=color)
            d.text((x_dmg_taken+10, y), 'TANK', font=font, fill=color)
            d.text((x_score-20, y), 'MVP', font=font, fill=color)

            if not self.thisQ in ["ARAM", "CLASH ARAM"]:
                d.text((x_vision, y), 'VS', font=font, fill=color)

        # participants
        initial_y = 223 + 190
        


        array_scoring = np.array([]) # qu'on va mettre du plus grand au plus petit
        liste = []  # en ordre en fonction des joueurs
        for i in range(0,10):
            liste.append(self.calcul_scoring(i))
            scoring_joueur = liste[i]
            array_scoring = np.append(array_scoring, scoring_joueur)

        array_scoring_trie = array_scoring.copy()
        array_scoring_trie.sort()
            



            
        for i in range(self.nb_joueur):
            try:
                im.paste(
                    im=await get_image("champion", self.thisChampNameListe[i], self.session, profil_version=self.version['n']['champion']),
                    box=(10, initial_y-13),
                )
            except:
                im.paste(
                    im=await get_image("champion", self.thisChampNameListe[i].capitalize(), self.session, profil_version=self.version['n']['champion']),
                    box=(10, initial_y-13),
                )

            if self.mastery_level[i] >= 100:
                x_mastery = 15
                font_mastery = font_little
            elif self.mastery_level[i] >= 10:
                x_mastery = 20
                font_mastery = font
            else:
                x_mastery = 35
                font_mastery = font

            d.text((x_mastery, initial_y),
                   str(self.mastery_level[i]), font=font_mastery, fill=(255, 255, 255))
            
            # couleur
            if i <= 4:
                ecart_level = self.thisLevelListe[i] - self.thisLevelListe[i+5]

                if ecart_level > 0:
                    fill_level = meilleur_joueur
                elif ecart_level < 0:
                    fill_level = pire_joueur
                else:
                    fill_level = fill
            else:
                fill_level = fill

            d.text((x_level, initial_y),
                   str(self.thisLevelListe[i]), font=font, fill=fill_level)


            if self.thisRiotIdListe[i] == '' or self.thisRiotIdListe[i] == ' ':
                d.text((x_name, initial_y),
                    self.thisPseudoListe[i], font=font, fill=fill)
            else:
                d.text((x_name, initial_y),
                    self.thisRiotIdListe[i], font=font, fill=fill)

            # rank
           

            if self.moba_ok:
                try:
                    rank_joueur = self.liste_tier[i]
                    tier_joueur = self.liste_rank[i]

                    if rank_joueur in ['MASTER', 'GRANDMASTER', 'CHALLENGER']:
                        tier_joueur = self.liste_lp[i]

                except:
                    rank_joueur = ''
                    tier_joueur = ''
            else:
                try:
                    
                    data_rank = await getRanks(self.session, self.thisRiotIdListe[i].lower(), self.thisRiotTagListe[i].lower(), season=self.season_ugg)
                    df_rank = pd.DataFrame(data_rank['data']['fetchProfileRanks']['rankScores'])
                    rank_joueur = df_rank.loc[df_rank['queueType'] == 'ranked_solo_5x5']['tier'].values[0]
                    tier_joueur = df_rank.loc[df_rank['queueType'] == 'ranked_solo_5x5']['rank'].values[0]


                    if rank_joueur.upper() in ['MASTER', 'GRANDMASTER', 'CHALLENGER']:
                        tier_joueur = df_rank.loc[df_rank['queueType'] == 'ranked_solo_5x5']['lp'].values[0]

                except:
                    rank_joueur = ''
                    tier_joueur = ''

            if rank_joueur != '' and rank_joueur != 'UNRANKED':
                img_rank_joueur = await get_image('tier', rank_joueur.upper(), self.session, 100, 100)

                im.paste(img_rank_joueur, (x_score-365, initial_y-20), img_rank_joueur.convert('RGBA'))

                d.text((x_score-265, initial_y), str(
                        tier_joueur), font=font, fill=fill)


            scoring = np.where(array_scoring_trie == liste[i])[0][0] + 1
            if self.thisRiotIdListe[i].lower().replace(' ', '') == self.riot_id:
                requete_perso_bdd('''UPDATE matchs
                                      SET mvp = :mvp 
                                      WHERE match_id = :match_id
                                      AND joueur = :joueur''',
                                      {'mvp' : int(scoring), # self.player_score . Ancien : mvp_modele
                                       'match_id' : self.last_match,
                                       'joueur' : self.id_compte})
                

            if self.thisQ == 'ARAM':
                d.text((x_score+20, initial_y),
                        str(scoring),
                        font=font,
                        fill=color_scoring.get(scoring, fill))
                

            elif self.thisQ in ['RANKED', 'FLEX', 'NORMAL', 'SWIFTPLAY']:
                if hasattr(self, 'scores_liste') and i < len(self.scores_liste):
                    score = self.scores_liste[i]
                    indicator = self._get_player_rank(i)
                    
                    # Couleur basée sur le score
                    if indicator == 10:
                        color = color_scoring[10]   # Rouge
                    elif indicator >= 8:
                        color = color_scoring[8]
                    elif indicator >= 6:
                        color = fill # Jaune
                    elif indicator >= 4:
                        color = fill  # Orange
                    else:
                        color = color_scoring[1]  # Vert
                    
                    # # Indicateur MVP/ACE
                    # indicator = ""
                    # if i == self.mvp_index:
                    #     indicator = "👑"
                    # elif i == self.ace_index:
                    #     indicator = "⭐"

                    
                    
                    d.text((x_score+15, initial_y), f"{indicator}", fill=color, font=font)

            if len(str(self.thisKillsListe[i])) == 1:
                d.text((x_kills, initial_y), str(
                    self.thisKillsListe[i]), font=font, fill=fill)
            else:
                d.text((x_kills - 20, initial_y),
                       str(self.thisKillsListe[i]), font=font, fill=fill)

            if len(str(self.thisDeathsListe[i])) == 1:
                d.text((x_deaths, initial_y), str(
                    self.thisDeathsListe[i]), font=font, fill=fill)
            else:
                d.text((x_deaths - 20, initial_y),
                       str(self.thisDeathsListe[i]), font=font, fill=fill)

            if len(str(self.thisAssistsListe[i])) == 1:
                d.text((x_assists, initial_y), str(
                    self.thisAssistsListe[i]), font=font, fill=fill)
            else:
                d.text((x_assists - 20, initial_y),
                       str(self.thisAssistsListe[i]), font=font, fill=fill)

            fill_color = range_value(i, self.thisKDAListe, True, value_meilleur=meilleur_joueur, value_pire=pire_joueur, couleur_fill=fill)

            # Recentrer le résultat quand chiffre rond
            if len(str(round(self.thisKDAListe[i], 2))) == 1:
                d.text((x_kda + 35, initial_y),
                       str(round(self.thisKDAListe[i], 2)), font=font, fill=fill_color)
            else:
                d.text((x_kda, initial_y), str(
                    round(self.thisKDAListe[i], 2)), font=font, fill=fill_color)

            fill_color = range_value(i, self.thisKPListe, True, value_meilleur=meilleur_joueur, value_pire=pire_joueur, couleur_fill=fill)

            d.text((x_kp, initial_y), str(
                self.thisKPListe[i]) + "%", font=font, fill=fill_color)

            fill_color = range_value(i, np.array(self.thisMinionListe) +
                               np.array(self.thisJungleMonsterKilledListe), value_meilleur=meilleur_joueur, value_pire=pire_joueur, couleur_fill=fill)

            if len(str(self.thisMinionListe[i] + self.thisJungleMonsterKilledListe[i])) != 2:
                d.text((x_cs, initial_y), str(
                    self.thisMinionListe[i] + self.thisJungleMonsterKilledListe[i]), font=font, fill=fill_color, couleur_fill=fill)
            else:
                d.text((x_cs + 10, initial_y), str(
                    self.thisMinionListe[i] + self.thisJungleMonsterKilledListe[i]), font=font, fill=fill_color, couleur_fill=fill)

            if not self.thisQ in ["ARAM", "CLASH ARAM"]:

                fill_color = range_value(i, self.thisVisionListe, value_meilleur=meilleur_joueur, value_pire=pire_joueur, couleur_fill=fill)

                d.text((x_vision, initial_y), str(
                    self.thisVisionListe[i]), font=font, fill=fill_color)

            fill_color = range_value(i, self.thisDamageListe, value_meilleur=meilleur_joueur, value_pire=pire_joueur, couleur_fill=fill)

            d.text((x_dmg_percent, initial_y),
                   f'{int(self.thisDamageListe[i]/1000)}k ({int(self.thisDamageRatioListe[i]*100)}%)', font=font, fill=fill_color)

            fill_color = range_value(i, np.array(
                self.thisDamageTakenListe) + np.array(self.thisDamageSelfMitigatedListe), value_meilleur=meilleur_joueur, value_pire=pire_joueur, couleur_fill=fill)

            d.text((x_dmg_taken + 25, initial_y),
                   f'{int(self.thisDamageTakenListe[i]/1000) + int(self.thisDamageSelfMitigatedListe[i]/1000)}k', font=font, fill=fill_color)
            

            n = 0
            for image in self.allitems[i]:
                if image != 0:
                    im.paste(await get_image("items", image, self.session, resize_x=65, resize_y=65, profil_version=self.version['n']['item']),
                            box=(x_dmg_taken + 150 + n, initial_y))
                    n += 80

            initial_y += 200 if i == 4 else 100
        if not self.thisQ in ["ARAM", "CLASH ARAM"]:
            y_ecart = 220 + 190
            for ecart in [self.ecart_top_gold, self.ecart_jgl_gold, self.ecart_mid_gold, self.ecart_adc_gold, self.ecart_supp_gold]:
                if ecart > 0:
                    d.text((x_ecart, y_ecart), str(round(ecart/1000, 1)
                                                   ) + "k", font=font, fill=(0, 128, 0))
                else:
                    d.text((x_ecart-10, y_ecart), str(round(ecart/1000, 1)
                                                      ) + "k", font=font, fill=(255, 0, 0))

                y_ecart = y_ecart + 100



        if not self.thisQ in ["ARAM", "CLASH ARAM"]:


            tower = await get_image('monsters', 'tower', self.session, resize_y=100)
            inhibiteur = await get_image('monsters', 'inhibitor', self.session)
            drk = await get_image('monsters', 'dragon', self.session)
            elder = await get_image('monsters', 'elder', self.session)
            herald = await get_image('monsters', 'herald', self.session)
            nashor = await get_image('monsters', 'nashor', self.session)
            horde = await get_image('monsters', 'horde', self.session)
            # atakhan = await get_image('monsters', 'atakhan', self.session)

            im.paste(tower, (x_objectif - 400, 190), tower.convert('RGBA'))
            d.text((x_objectif - 400 + 100, 25 + 190), str(self.thisTowerTeam),
                   font=font, fill=fill)
            
            im.paste(inhibiteur, (x_objectif - 200, 10 + 190), inhibiteur.convert('RGBA'))
            d.text((x_objectif - 200 + 100, 25 + 190), str(self.thisInhibTeam),
                   font=font, fill=fill)

            im.paste(drk, (x_objectif, 10 + 190), drk.convert('RGBA'))
            d.text((x_objectif + 100, 25 + 190), str(self.thisDragonTeam),
                   font=font, fill=fill)

            im.paste(elder, (x_objectif + 200, 10 + 190), elder.convert('RGBA'))
            d.text((x_objectif + 200 + 100, 25 + 190),
                   str(self.thisElderPerso), font=font, fill=fill)

            im.paste(herald, (x_objectif + 400, 10 + 190), herald.convert('RGBA'))
            d.text((x_objectif + 400 + 100, 25 + 190),
                   str(self.thisHeraldTeam), font=font, fill=fill)

            im.paste(nashor, (x_objectif + 600, 10 + 190), nashor.convert('RGBA'))
            d.text((x_objectif + 600 + 100, 25 + 190),
                   str(self.thisBaronTeam), font=font, fill=fill)
            
            im.paste(horde, (x_objectif + 800, 10 + 190), horde.convert('RGBA'))
            d.text((x_objectif + 800 + 100, 25 + 190),
                   str(self.thisHordeTeam), font=font, fill=fill)
            
            # im.paste(atakhan, (x_objectif + 1000, 10 + 190), atakhan.convert('RGBA'))
            # d.text((x_objectif + 1000 + 100, 25 + 190),
            #        str(self.thisAtakhanTeam), font=font, fill=fill)

        img_timer = await get_image('timer', 'timer', self.session)
        img_blue_epee = await get_image('epee', 'blue', self.session)
        img_red_epee = await get_image('epee', 'red', self.session)

        im.paste(img_timer, (x_kill_total-500, 10 + 190),
                 img_timer.convert('RGBA'))
        d.text((x_kill_total -500 + 100, 23 + 190), f'{(int(self.thisTime))}m',
               font=font, fill=fill)

        im.paste(img_blue_epee, (x_kill_total - 100, 10 + 190),
                 img_blue_epee.convert('RGBA'))
        d.text((x_kill_total - 100 + 100, 23 + 190), str(self.thisTeamKills),
               font=font, fill=fill)

        im.paste(img_red_epee, (x_kill_total + 200, 10 + 190),
                 img_red_epee.convert('RGBA'))
        d.text((x_kill_total + 200 + 100, 23 + 190),
               str(self.thisTeamKillsOp), font=font, fill=fill)
        

        # Stat du jour
        if self.thisQ in ['ARAM', 'CLASH ARAM']:
            suivi_24h = lire_bdd(f'ranked_aram_S{self.season}', 'dict')
        else:
            suivi_24h = lire_bdd(f'suivi_S{self.season}', 'dict')

        if self.thisQ not in ['ARAM', 'CLASH ARAM', 'FLEX']:

            difwin = int(self.thisVictory) - \
                        int(suivi_24h[self.id_compte]["wins_jour"])
            diflos = int(self.thisLoose) - \
                        int(suivi_24h[self.id_compte]["losses_jour"])

            if (difwin + diflos) > 0:  # si pas de ranked aujourd'hui, inutile

                victoire_text = f'Victoires 24h : {difwin}'
                defaite_text = f'Defaites 24h : {diflos}'

                
                d.text((x_metric + 850, y_name+50),
                           victoire_text,
                            font=font_little, 
                            fill=fill)
                d.text((x_metric + 1460, y_name+50),
                           defaite_text,
                            font=font_little,
                            fill=fill)


        elif self.thisQ in ['ARAM', 'CLASH ARAM'] and activation:

            difwin = wins - \
                        int(suivi_24h[self.id_compte]["wins_jour"])
            diflos = losses - \
                        int(suivi_24h[self.id_compte]["losses_jour"])

            if (difwin + diflos) > 0:  # si pas de ranked aujourd'hui, inutile
                if serie_wins > 0:
                    d.text((x_metric + 850, y_name+50),
                       
                           f'Victoires 24h : {difwin} (S : {serie_wins})', font=font_little, fill=fill)
                else:
                    d.text((x_metric + 850, y_name+50),
                       
                           f'Victoires 24h : {difwin}', font=font_little, fill=fill)                    
                d.text((x_metric + 1460, y_name+50),
                           f'Defaites 24h : {diflos}', font=font_little, fill=fill)
                


        time = 10 if self.thisQ == 'ARAM' else 15
        
        stats_joueur_split = lire_bdd_perso(f'''SELECT tracker.id_compte, avg(kills) as kills, avg(deaths) as deaths, avg(assists) as assists, 
                    (count(victoire) filter (where victoire = True)) as victoire,
                    avg(kp) as kp,
                    count(victoire) as nb_games,
                    (avg(mvp) filter (where mvp != 0)) as mvp
                    from matchs
                    INNER JOIN tracker on matchs.joueur = tracker.id_compte
                    WHERE tracker.id_compte = {self.id_compte}
                    and champion = '{self.thisChampName}'
                    and season = {self.season}
                    and mode = '{self.thisQ}'
                    and time > {time}
                    and split = {self.split}
                    GROUP BY tracker.id_compte''', index_col='id_compte').transpose()

        if not stats_joueur_split.empty:
            k = round(
                    stats_joueur_split.loc[self.id_compte, 'kills'], 1)
            deaths = round(
                    stats_joueur_split.loc[self.id_compte, 'deaths'], 1)
            a = round(
                    stats_joueur_split.loc[self.id_compte, 'assists'], 1)
            kp = int(stats_joueur_split.loc[self.id_compte, 'kp'])

            if deaths == 0:
                kda = round((k+a),2)
            else:
                kda = round((k+a)/deaths,2)

            if kda >= 10: # sinon cela donne 4 chiffres, et dépasse le cadre du texte
                kda = round(kda, 1)            
                
            try:
                mvp = round(stats_joueur_split.loc[self.id_compte, 'mvp'], 1)
            except TypeError:
                mvp = 0

            ratio_victoire = int((stats_joueur_split.loc[self.id_compte, 'victoire'] / stats_joueur_split.loc[self.id_compte, 'nb_games'])*100)
            nb_games = int(stats_joueur_split.loc[self.id_compte, 'nb_games'])
                


            if mvp == 0:
                d.text((x_metric + 300, y_name-50),
                           f' {nb_games} P', font=font_little, fill=fill)
            else:

                d.text((x_metric + 300, y_name-50),
                           f' {nb_games} Parties | {mvp} MVP', font=font_little, fill=fill)
                
            if ratio_victoire >= 60:
                color_victoire = victoire60
            elif ratio_victoire >= 50:
                color_victoire = victoire50
            elif ratio_victoire <= 30 and nb_games >= 10:
                color_victoire = victoire30
            else:
                color_victoire = fill
                
            d.text((x_metric + 300, y_name+10),
                           f' {ratio_victoire}% V', font=font_little, fill=color_victoire)    
            

            if kda >= 5:
                color_kda = kda5 # (255, 140, 0)
            elif kda >= 4:
                color_kda = kda4
            elif kda >= 3:
                color_kda = kda3
            elif kda < 1:
                color_kda = kda1
            else:
                color_kda = fill
            


            
            d.text((x_metric + 300, y_name+70),
                           f' {kda}', font=font_little, fill=color_kda)     

            d.text((x_metric + 410, y_name+70),
                           f'({k} / {deaths} / {a})', font=font_little, fill=fill)     

                


        im.save(f'{name_img}.png')

        # si sauvegarde 

        buffer = BytesIO() 
        
        im.save(buffer, format='PNG')
        image_bytes = buffer.getvalue()

        requete_perso_bdd('''INSERT INTO match_images (match_id, image) VALUES (:match_id, :image)
                        ON CONFLICT (match_id) DO NOTHING''',
                        dict_params={'match_id': self.last_match, 'image': image_bytes})        

        await self.session.close()

        return embed
