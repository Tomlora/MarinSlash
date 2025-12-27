import os
import sys
import aiohttp
import pandas as pd
import warnings
import interactions
from interactions import SlashCommandOption, Extension, SlashContext, listen, slash_command, Task, IntervalTrigger, TimeTrigger
from utils.params import Version, saison
from utils.emoji import emote_champ_discord, emote_rank_discord, emote_v2
from fonctions.api_calls import getRankings
from fonctions.api_moba import test_mobalytics_api
from fonctions.permissions import isOwner_slash
from fonctions.gestion_challenge import challengeslol
from fonctions.autocomplete import autocomplete_riotid
from fonctions.channels_discord import identifier_role_by_name
from datetime import datetime
import traceback
import humanize
from asyncio import sleep
from collections import Counter, defaultdict
import re 
from utils.emoji import dict_place
import io 
from PIL import Image
import pickle

from fonctions.gestion_bdd import (lire_bdd,
                                   sauvegarde_bdd,
                                   get_data_bdd,
                                   requete_perso_bdd,
                                   lire_bdd_perso,
                                   get_tag)

# Import de la nouvelle classe MatchLol
from fonctions.match import MatchLol

from fonctions.match.riot_api import (
                             get_summoner_by_puuid,
                             get_list_matchs_with_puuid,
                             getId_with_puuid,
                             get_league_by_puuid,
                             get_spectator
                             )

from fonctions.match.records import top_records, get_id_account_bdd, get_stat_null_rules
from utils.lol import label_rank, label_tier, dict_rankid
from fonctions.channels_discord import chan_discord, rgb_to_discord


warnings.simplefilter(action='ignore', category=FutureWarning)
pd.options.mode.chained_assignment = None  # default='warn'

import re
from collections import defaultdict, OrderedDict



def format_score_bar(score: float, width: int = 10) -> str:
    """Crée une barre visuelle pour un score."""
    filled = int(score)
    empty = width - filled
    return '█' * filled + '░' * empty


def get_score_color_emoji(score: float) -> str:
    """Retourne un emoji coloré basé sur le score."""
    if score >= 9.0:
        return '🏆'
    elif score >= 8.0:
        return '⭐'
    elif score >= 7.0:
        return '✅'
    elif score >= 5.0:
        return '➖'
    elif score >= 3.0:
        return '⚠️'
    else:
        return '❌'


def get_dim_emoji(dimension: str) -> str:
    """Retourne l'emoji d'une dimension."""
    return {'Combat': '⚔️', 'Économie': '💰', 'Objectifs': '🎯', 
            'Tempo': '⚡', 'Impact': '👑'}.get(dimension, '📊')


def get_dim_name_fr(dimension: str) -> str:
    """Retourne le nom français d'une dimension."""
    return {
        'combat_value': 'Combat',
        'economic_efficiency': 'Économie', 
        'objective_contribution': 'Objectifs',
        'pace_rating': 'Tempo',
        'win_impact': 'Impact'
    }.get(dimension, dimension)


def explain_dimension_diff(dim_key: str, player_val: float, other_val: float, 
                           player_stats: dict, other_stats: dict, role: str) -> str:
    """
    Génère une explication textuelle pour la différence dans une dimension.
    
    Returns:
        str: Explication de pourquoi l'autre joueur a un meilleur/moins bon score
    """
    diff = other_val - player_val
    if abs(diff) < 0.5:
        return None  # Différence négligeable
    
    explanations = []
    
    if dim_key == 'combat_value':
        # Comparer KDA, KP, deaths
        p_kda = player_stats.get('kda', 0)
        o_kda = other_stats.get('kda', 0)
        p_kp = player_stats.get('kp', 0)
        o_kp = other_stats.get('kp', 0)
        p_deaths = player_stats.get('deaths', 0)
        o_deaths = other_stats.get('deaths', 0)
        
        if o_kda > p_kda + 1:
            explanations.append(f"KDA supérieur ({o_kda:.1f} vs {p_kda:.1f})")
        if o_kp > p_kp + 10:
            explanations.append(f"meilleure participation ({o_kp}% vs {p_kp}% KP)")
        if p_deaths > o_deaths + 2:
            explanations.append(f"moins de morts ({o_deaths} vs {p_deaths})")
            
    elif dim_key == 'economic_efficiency':
        p_cs = player_stats.get('cs_per_min', 0)
        o_cs = other_stats.get('cs_per_min', 0)
        p_dpg = player_stats.get('damage_per_gold', 0)
        o_dpg = other_stats.get('damage_per_gold', 0)
        
        if o_cs > p_cs + 1:
            explanations.append(f"meilleur farm ({o_cs:.1f} vs {p_cs:.1f} CS/min)")
        if o_dpg > p_dpg + 0.3:
            explanations.append(f"meilleur ratio dégâts/gold")
            
    elif dim_key == 'objective_contribution':
        p_obj = player_stats.get('objectives_participated', 0)
        o_obj = other_stats.get('objectives_participated', 0)
        p_vision = player_stats.get('vision_per_min', 0)
        o_vision = other_stats.get('vision_per_min', 0)
        p_turret = player_stats.get('turret_damage', 0)
        o_turret = other_stats.get('turret_damage', 0)
        
        if o_obj > p_obj + 1:
            explanations.append(f"plus de participations aux objectifs ({o_obj:.0f} vs {p_obj:.0f})")
        if o_vision > p_vision + 0.5:
            explanations.append(f"meilleure vision ({o_vision:.1f} vs {p_vision:.1f}/min)")
        if o_turret > p_turret + 2000:
            explanations.append(f"plus de dégâts aux tours ({o_turret:,} vs {p_turret:,})")
            
    elif dim_key == 'pace_rating':
        p_gpm = player_stats.get('gold_per_min', 0)
        o_gpm = other_stats.get('gold_per_min', 0)
        p_dpm = player_stats.get('damage_per_min', 0)
        o_dpm = other_stats.get('damage_per_min', 0)
        
        if o_gpm > p_gpm + 30:
            explanations.append(f"plus de gold/min ({o_gpm:.0f} vs {p_gpm:.0f})")
        if o_dpm > p_dpm + 100:
            explanations.append(f"plus de dégâts/min ({o_dpm:.0f} vs {p_dpm:.0f})")
            
    elif dim_key == 'win_impact':
        p_dmg_share = player_stats.get('damage_share', 0) * 100
        o_dmg_share = other_stats.get('damage_share', 0) * 100
        p_gold_share = player_stats.get('gold_share', 0) * 100
        o_gold_share = other_stats.get('gold_share', 0) * 100
        
        if o_dmg_share > p_dmg_share + 5:
            explanations.append(f"plus grande part des dégâts ({o_dmg_share:.0f}% vs {p_dmg_share:.0f}%)")
        if o_gold_share < p_gold_share - 3 and o_dmg_share >= p_dmg_share:
            explanations.append(f"plus efficace avec moins de ressources")
    
    return ', '.join(explanations) if explanations else None


def generate_comparison_text(player_summary: dict, other_summary: dict,
                             player_stats: dict, other_stats: dict,
                             player_name: str, other_name: str) -> list:
    """
    Génère un texte explicatif comparant deux joueurs.
    
    Returns:
        list: Liste de lignes explicatives
    """
    lines = []
    
    p_breakdown = player_summary.get('breakdown', {})
    o_breakdown = other_summary.get('breakdown', {})
    
    p_score = player_summary.get('score', 0)
    o_score = other_summary.get('score', 0)
    
    score_diff = o_score - p_score
    
    if score_diff > 0:
        lines.append(f"**{other_name}** a {score_diff:.1f} pts de plus que toi. Voici pourquoi :\n")
    else:
        lines.append(f"Tu as {abs(score_diff):.1f} pts de plus que **{other_name}**. Voici tes forces :\n")
    
    # Analyser chaque dimension
    dimensions = [
        ('combat_value', 'Combat', '⚔️'),
        ('economic_efficiency', 'Économie', '💰'),
        ('objective_contribution', 'Objectifs', '🎯'),
        ('pace_rating', 'Tempo', '⚡'),
        ('win_impact', 'Impact', '👑'),
    ]
    
    advantages_other = []
    advantages_player = []
    
    for dim_key, dim_name, emoji in dimensions:
        p_val = p_breakdown.get(dim_key, 0)
        o_val = o_breakdown.get(dim_key, 0)
        diff = o_val - p_val
        
        explanation = explain_dimension_diff(
            dim_key, p_val, o_val, 
            player_stats, other_stats,
            player_summary.get('role', '')
        )
        
        if diff >= 1.0:
            reason = f" ({explanation})" if explanation else ""
            advantages_other.append(f"{emoji} **{dim_name}**: {o_val} vs {p_val} (+{diff:.1f}){reason}")
        elif diff <= -1.0:
            reason = f" ({explanation})" if explanation else ""
            advantages_player.append(f"{emoji} **{dim_name}**: {p_val} vs {o_val} (+{abs(diff):.1f})")
    
    if advantages_other:
        lines.append("📈 **Ses avantages:**")
        for adv in advantages_other:
            lines.append(f"  • {adv}")
    
    if advantages_player:
        lines.append("\n📉 **Tes avantages:**")
        for adv in advantages_player:
            lines.append(f"  • {adv}")
    
    # Conseil d'amélioration
    if score_diff > 0:
        worst_dim = player_summary.get('worst_dimension', '')
        worst_score = player_summary.get('worst_dimension_score', 0)
        if worst_score < 5:
            lines.append(f"\n💡 **Conseil:** Améliore ton score en **{worst_dim}** ({worst_score}/10) pour progresser.")
    
    return lines


# =============================================================================
# 2. Fonction pour collecter les stats d'un joueur pour comparaison
# =============================================================================

def collect_player_stats(match_info, player_idx: int) -> dict:
    """Collecte les statistiques d'un joueur pour la comparaison."""
    
    # Calculer gold/min manuellement
    gold = match_info.thisGoldListe[player_idx] if player_idx < len(match_info.thisGoldListe) else 0
    game_time = match_info.thisTime if hasattr(match_info, 'thisTime') else 30
    gold_per_min = gold / max(1, game_time)
    
    # Calculer gold share (ratio par rapport à l'équipe)
    team_start = 0 if player_idx < 5 else 5
    team_end = 5 if player_idx < 5 else 10
    team_gold = sum(match_info.thisGoldListe[team_start:team_end])
    gold_share = gold / max(1, team_gold)
    
    return {
        'kda': match_info.thisKDAListe[player_idx] if player_idx < len(match_info.thisKDAListe) else 0,
        'kp': match_info.thisKPListe[player_idx] if player_idx < len(match_info.thisKPListe) else 0,
        'deaths': match_info.thisDeathsListe[player_idx] if player_idx < len(match_info.thisDeathsListe) else 0,
        'cs_per_min': match_info.thisMinionPerMinListe[player_idx] if player_idx < len(match_info.thisMinionPerMinListe) else 0,
        'damage_per_gold': (match_info.thisDamageListe[player_idx] / max(1, match_info.thisGoldListe[player_idx])) if player_idx < len(match_info.thisDamageListe) else 0,
        'gold_per_min': gold_per_min,
        'damage_per_min': match_info.thisDamagePerMinuteListe[player_idx] if player_idx < len(match_info.thisDamagePerMinuteListe) else 0,
        'objectives_participated': match_info.thisObjectivesParticipatedListe[player_idx] if hasattr(match_info, 'thisObjectivesParticipatedListe') and player_idx < len(match_info.thisObjectivesParticipatedListe) else 0,
        'vision_per_min': match_info.thisVisionPerMinListe[player_idx] if player_idx < len(match_info.thisVisionPerMinListe) else 0,
        'turret_damage': match_info.thisDamageTurretsListe[player_idx] if player_idx < len(match_info.thisDamageTurretsListe) else 0,
        'damage_share': match_info.thisDamageRatioListe[player_idx] if player_idx < len(match_info.thisDamageRatioListe) else 0,
        'gold_share': gold_share,
    }


class LolScore(Extension):
    def __init__(self, bot):
        self.bot: interactions.Client = bot

    # =============================================================================
    # 3. Ajouter cette méthode dans la classe LeagueofLegends
    # =============================================================================

    @slash_command(
    name="explain",
    description="Affiche le détail des scores de performance d'une partie",
    sub_cmd_name='scoring',
    options=[
        SlashCommandOption(
            name="riot_id",
            description="Nom du joueur",
            type=interactions.OptionType.STRING,
            required=True,
            autocomplete=True
        ),
        SlashCommandOption(
            name="riot_tag",
            description="Tag",
            type=interactions.OptionType.STRING,
            required=False
        ),
        SlashCommandOption(
            name="match_id",
            description="ID du match (ex: EUW1_1234567890)",
            type=interactions.OptionType.STRING,
            required=False
        ),
        SlashCommandOption(
            name="numerogame",
            description="Numéro de la game (0 = plus récente)",
            type=interactions.OptionType.INTEGER,
            required=False,
            min_value=0,
            max_value=20
        ),
        SlashCommandOption(
            name="comparer_a",
            description="Comparer à un joueur spécifique (sinon: MVP ou meilleur)",
            type=interactions.OptionType.STRING,
            required=False,
            autocomplete=False
        )
    ]
)
    async def game_scoring(
        self,
        ctx: SlashContext,
        riot_id: str,
        riot_tag: str = None,
        match_id: str = None,
        numerogame: int = 0,
        comparer_a: str = None
    ):
        """Affiche le détail des scores de tous les joueurs d'une partie avec explications."""
        
        await ctx.defer(ephemeral=False)
        
        # Résolution du tag
        if riot_tag is None:
            try:
                riot_tag = get_tag(riot_id)
            except ValueError:
                return await ctx.send('Plusieurs comptes avec ce riot_id, merci de préciser le tag')
        
        riot_id = riot_id.lower().replace(' ', '')
        riot_tag = riot_tag.upper()
        
        # Récupération de l'ID compte
        try:
            id_compte = get_id_account_bdd(riot_id, riot_tag)
        except IndexError:
            return await ctx.send("Ce compte n'existe pas ou n'est pas enregistré")
        
        # Création de l'instance MatchLol
        match_info = MatchLol(
            id_compte=id_compte,
            riot_id=riot_id,
            riot_tag=riot_tag,
            idgames=numerogame,
            queue=0,
            identifiant_game=match_id
        )
        
        try:
            # Récupération des données
            await match_info.get_data_riot()
            await match_info.prepare_data()
            await match_info._extract_team_data()
            
            # Calcul des scores
            await match_info.calculate_all_scores()
            
            # Récupération des résumés
            all_summaries = match_info.get_all_players_performance_summary()
            
            if not all_summaries:
                return await ctx.send("Impossible de calculer les scores pour cette partie.")
            
            # Index du joueur qui a demandé
            player_idx = match_info.thisId
            
            if match_info.thisId > 4:
                player_idx = match_info.thisId - 5

            player_summary = all_summaries[player_idx]
            player_score = player_summary.get('score', 0)
            player_name = match_info.thisRiotIdListe[player_idx]
            
            # Déterminer l'équipe gagnante
            blue_win = match_info.thisWinBool if player_idx < 5 else not match_info.thisWinBool
            
            # MVP et ACE
            mvp_idx = match_info.mvp_index
            ace_idx = match_info.ace_index
            
            mvp_champ = match_info.thisChampNameListe[mvp_idx]
            mvp_name = match_info.thisRiotIdListe[mvp_idx]
            mvp_score = match_info.scores_liste[mvp_idx]
            mvp_emoji = emote_champ_discord.get(mvp_champ.capitalize(), '')
            
            ace_champ = match_info.thisChampNameListe[ace_idx]
            ace_name = match_info.thisRiotIdListe[ace_idx]
            ace_score = match_info.scores_liste[ace_idx]
            ace_emoji = emote_champ_discord.get(ace_champ.capitalize(), '')
            
            # =====================================================================
            # EMBED 1: Ton score et comparaison
            # =====================================================================
            
            player_champ = match_info.thisChampNameListe[player_idx]
            player_emoji = emote_champ_discord.get(player_champ.capitalize(), '')
            player_role = player_summary.get('role', '?')
            player_breakdown = player_summary.get('breakdown', {})
            
            embed1 = interactions.Embed(
                title=f"📊 Ton Score: {player_score}/10 {get_score_color_emoji(player_score)}",
                description=f"{player_emoji} **{player_name}** ({player_role}) • {match_info.thisQ} • {match_info.thisTime} min",
                color=0x00FF00 if match_info.thisWinBool else 0xFF4444
            )
            
            # Tes dimensions
            dims_text = []
            for dim_key, dim_name, emoji in [
                ('combat_value', 'Combat', '⚔️'),
                ('economic_efficiency', 'Économie', '💰'),
                ('objective_contribution', 'Objectifs', '🎯'),
                ('pace_rating', 'Tempo', '⚡'),
                ('win_impact', 'Impact', '👑'),
            ]:
                val = player_breakdown.get(dim_key, 0)
                bar = format_score_bar(val)
                dims_text.append(f"{emoji} {dim_name}: `[{bar}]` **{val}**")
            
            embed1.add_field(
                name="📈 Tes Dimensions",
                value='\n'.join(dims_text),
                inline=False
            )
            
            # Points forts et faibles
            best_dim = player_summary.get('best_dimension', '')
            best_score = player_summary.get('best_dimension_score', 0)
            worst_dim = player_summary.get('worst_dimension', '')
            worst_score = player_summary.get('worst_dimension_score', 0)
            
            embed1.add_field(
                name="💪 Point fort",
                value=f"{get_dim_emoji(best_dim)} {best_dim}: **{best_score}**/10",
                inline=True
            )
            embed1.add_field(
                name="📉 À améliorer",
                value=f"{get_dim_emoji(worst_dim)} {worst_dim}: **{worst_score}**/10",
                inline=True
            )
            
            # =====================================================================
            # COMPARAISON avec un autre joueur
            # =====================================================================
            
            # Déterminer avec qui comparer
            compare_idx = None
            
            if comparer_a:
                # Chercher le joueur spécifié
                comparer_a_lower = comparer_a.lower()
                for i, name in enumerate(match_info.thisRiotIdListe):
                    if name.lower() == comparer_a_lower or comparer_a_lower in name.lower():
                        compare_idx = i
                        break
            
            if compare_idx is None:
                # Par défaut: comparer au MVP (ou au meilleur de ton équipe si tu es MVP)
                if player_idx == mvp_idx:
                    # Tu es MVP, compare avec le 2ème meilleur de ton équipe
                    team_start = 0 if player_idx < 5 else 5
                    team_end = 5 if player_idx < 5 else 10
                    team_scores = [(i, match_info.scores_liste[i]) for i in range(team_start, team_end) if i != player_idx]
                    team_scores.sort(key=lambda x: x[1], reverse=True)
                    if team_scores:
                        compare_idx = team_scores[0][0]
                else:
                    # Comparer au MVP
                    compare_idx = mvp_idx
            
            # Générer la comparaison
            if compare_idx is not None and compare_idx != player_idx:
                compare_summary = all_summaries[compare_idx]
                compare_name = match_info.thisRiotIdListe[compare_idx]
                compare_champ = match_info.thisChampNameListe[compare_idx]
                compare_emoji = emote_champ_discord.get(compare_champ.capitalize(), '')
                compare_score = compare_summary.get('score', 0)
                compare_role = compare_summary.get('role', '?')
                
                # Collecter les stats pour l'explication détaillée
                player_stats = collect_player_stats(match_info, player_idx)
                compare_stats = collect_player_stats(match_info, compare_idx)
                
                # Générer le texte de comparaison
                comparison_lines = generate_comparison_text(
                    player_summary, compare_summary,
                    player_stats, compare_stats,
                    player_name, compare_name
                )
                
                embed1.add_field(
                    name=f"🔍 Comparaison avec {compare_emoji} {compare_name} ({compare_role}) - {compare_score}/10",
                    value='\n'.join(comparison_lines),
                    inline=False
                )
            
            # Badge si MVP/ACE
            if player_idx == mvp_idx:
                embed1.set_footer(text="🏆 Tu es le MVP de cette partie !")
            elif player_idx == ace_idx:
                embed1.set_footer(text="⭐ Tu es l'ACE (meilleur de l'équipe perdante)")
            else:
                rank = player_summary.get('rank', 0)
                embed1.set_footer(text=f"Classement: #{rank}/10 • Match {match_info.last_match}")
            
            # =====================================================================
            # EMBED 2: Vue d'ensemble de tous les joueurs
            # =====================================================================
            
            embed2 = interactions.Embed(
                title="👥 Tous les joueurs",
                description=f"[Voir sur League of Graphs]({match_info.url_game})",
                color=0x2F3136
            )
            
            embed2.add_field(
                name="🏆 MVP",
                value=f"{mvp_emoji} **{mvp_name}** `{mvp_score}/10`",
                inline=True
            )
            embed2.add_field(
                name="⭐ ACE",
                value=f"{ace_emoji} **{ace_name}** `{ace_score}/10`",
                inline=True
            )
            # embed2.add_field(name="", value="", inline=False)
            
            # Fonction pour formater un joueur (compact)
            def format_player_compact(i, summary):
                champ = match_info.thisChampNameListe[i]
                name = match_info.thisRiotIdListe[i]
                score = summary.get('score', 0)
                role = summary.get('role', '?')
                
                champ_emoji = emote_champ_discord.get(champ.capitalize(), '')
                score_emoji = get_score_color_emoji(score)
                
                badge = ''
                if summary.get('is_mvp'):
                    badge = ' 🏆'
                elif summary.get('is_ace'):
                    badge = ' ⭐'
                
                # Mettre en évidence le joueur qui a demandé
                if i == player_idx:
                    return f"**▶ {champ_emoji} {name}** ({role}) `{score}` {score_emoji}{badge}"
                
                best = summary.get('best_dimension', '')
                return f"{champ_emoji} {name} ({role}) `{score}` {score_emoji}{badge} │ {get_dim_emoji(best)}{best}"
            
            # Équipe Bleue
            blue_status = "🏆" if blue_win else "💀"
            blue_content = []
            for i in range(5):
                if i < len(all_summaries):
                    blue_content.append(format_player_compact(i, all_summaries[i]))
            
            embed2.add_field(
                name=f"🔵 Équipe Bleue {blue_status}",
                value='\n'.join(blue_content),
                inline=False
            )
            
            # Équipe Rouge
            red_status = "🏆" if not blue_win else "💀"
            red_content = []
            for i in range(5, 10):
                if i < len(all_summaries):
                    red_content.append(format_player_compact(i, all_summaries[i]))
            
            embed2.add_field(
                name=f"🔴 Équipe Rouge {red_status}",
                value='\n'.join(red_content),
                inline=False
            )
            
            # Envoyer les deux embeds
            await ctx.send(embeds=[embed1, embed2])
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            await ctx.send(f"Erreur lors de l'analyse: {str(e)}")
        
        finally:
            if hasattr(match_info, 'session') and match_info.session:
                await match_info.session.close()


    @game_scoring.autocomplete("riot_id")
    async def autocomplete_game_scoring(self, ctx: interactions.AutocompleteContext):
        liste_choix = await autocomplete_riotid(int(ctx.guild.id), ctx.input_text)
        await ctx.send(choices=liste_choix)


    # =============================================================================
    # 3. Commande alternative depuis la BDD (historique)
    # =============================================================================

    @slash_command(
        name="history",
        description="Affiche les scores d'une partie enregistrée",
        sub_cmd_name='scoring',
        options=[
            SlashCommandOption(
                name="match_id",
                description="ID du match (ex: 1234567890 ou EUW1_1234567890)",
                type=interactions.OptionType.STRING,
                required=True
            )
        ]
    )
    async def scoring_history(self, ctx: SlashContext, match_id: str):
        """Affiche les scores depuis la base de données."""
        
        await ctx.defer(ephemeral=False)
        
        if not match_id.startswith('EUW'):
            match_id = f'EUW1_{match_id}'
        
        df = lire_bdd_perso(f'''
            SELECT * FROM match_scoring 
            WHERE match_id = '{match_id}'
            ORDER BY player_index
        ''', index_col='player_index')
        
        if df.empty:
            return await ctx.send(f"❌ Aucune donnée pour `{match_id}`")
        
        df = df.T
        
        embed = interactions.Embed(
            title=f"📊 Scores (Historique)",
            description=f"Match: `{match_id}`",
            color=0x2F3136
        )
        
        # Trouver MVP et ACE
        for idx in df.index:
            row = df.loc[idx]
            if row['is_mvp']:
                champ_emoji = emote_champ_discord.get(row['champion'].capitalize(), '')
                embed.add_field(name="🏆 MVP", value=f"{champ_emoji} **{row['riot_id']}** `{row['score']}/10`", inline=True)
            if row['is_ace']:
                champ_emoji = emote_champ_discord.get(row['champion'].capitalize(), '')
                embed.add_field(name="⭐ ACE", value=f"{champ_emoji} **{row['riot_id']}** `{row['score']}/10`", inline=True)
        
        # Blue team
        blue_lines = []
        red_lines = []
        
        for idx in df.index:
            row = df.loc[idx]
            champ_emoji = emote_champ_discord.get(row['champion'].capitalize(), '')
            score_emoji = get_score_color_emoji(row['score'])
            best_emoji = get_dim_emoji(row['best_dimension'])
            
            badge = ' 🏆' if row['is_mvp'] else (' ⭐' if row['is_ace'] else '')
            line = f"{champ_emoji} **{row['riot_id']}** `{row['score']}` {score_emoji}{badge} │ {best_emoji}{row['best_dimension']}"
            
            if row['team'] == 'blue':
                blue_lines.append(line)
            else:
                red_lines.append(line)
        
        embed.add_field(name="🔵 Blue", value='\n'.join(blue_lines) or "Aucun", inline=False)
        embed.add_field(name="🔴 Red", value='\n'.join(red_lines) or "Aucun", inline=False)
        
        await ctx.send(embeds=embed)



def setup(bot):
    LolScore(bot)