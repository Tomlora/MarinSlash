import asyncio
from datetime import datetime
import interactions
from interactions import Extension, listen, slash_command, SlashContext, SlashCommandOption, OptionType, Permissions, Task, TimeTrigger
import aiohttp
import traceback

from fonctions.gestion_bdd import requete_perso_bdd, lire_bdd_perso
from utils.params import api_key_lol, region, my_region
from utils.emoji import emote_rank_discord

def calculate_rank_score(tier: str, rank: str, lp: int) -> int:
    """Calcule un score unique pour comparer n'importe quel rang."""
    tier_values = {
        "CHALLENGER": 2800,
        "GRANDMASTER": 2400,
        "MASTER": 2000,
        "DIAMOND": 1600,
        "EMERALD": 1200,
        "PLATINUM": 800,
        "GOLD": 400,
        "SILVER": 0,
        "BRONZE": -400,
        "IRON": -800
    }
    rank_values = {"I": 300, "II": 200, "III": 100, "IV": 0}
    
    return tier_values.get(tier.upper(), 0) + rank_values.get(rank.upper(), 0) + lp


class RateLimiter:
    """Rate limiter pour l'API Riot (60 requêtes/minute)."""
    
    def __init__(self, calls_per_minute: int = 60):
        self.calls_per_minute = calls_per_minute
        self.interval = 60.0 / calls_per_minute
        self.last_call = 0
    
    async def wait(self):
        now = asyncio.get_event_loop().time()
        elapsed = now - self.last_call
        
        if self.last_call > 0 and elapsed < self.interval:
            await asyncio.sleep(self.interval - elapsed)
        
        self.last_call = asyncio.get_event_loop().time()


class LadderCollector(Extension):
    
    def __init__(self, bot):
        self.bot = bot
        self.rate_limiter = RateLimiter(calls_per_minute=55)
        self.is_collecting = False
        self.progress = {"current": 0, "total": 0, "tier": "", "errors": 0}
    
    # ==========================================================================
    # TÂCHE PLANIFIÉE
    # ==========================================================================
    
    @Task.create(TimeTrigger(hour=3, minute=0))
    async def scheduled_ladder_update(self):
        print(f"[{datetime.now()}] Démarrage automatique de la collecte du ladder EUW...")
        await self.collect_and_store_ladder()
    
    @listen()
    async def on_startup(self):
        self.scheduled_ladder_update.start()
        print("Tache de collecte du ladder planifiee a 3h00")
    
    # ==========================================================================
    # COMMANDES ADMIN
    # ==========================================================================
    
    @slash_command(
        name="ladder_update",
        description="[Admin] Lance manuellement la mise à jour du ladder EUW",
        default_member_permissions=Permissions.ADMINISTRATOR
    )
    async def ladder_update(self, ctx: SlashContext):
        """Lance manuellement la collecte du ladder."""
        
        if self.is_collecting:
            return await ctx.send(
                f":warning: Collecte déjà en cours...\n"
                f"Progression: **{self.progress['tier']}** - {self.progress['current']:,} joueurs collectés\n"
                f"Erreurs: {self.progress['errors']}",
                ephemeral=True
            )
        
        await ctx.send(
            ":dart: **Lancement de la collecte du ladder EUW**\n"
            ":timer: Durée estimée: ~50 minutes\n"
            "Utilisez `/ladder_status` pour suivre la progression.",
            ephemeral=True
        )
        
        # Lancer en tâche de fond
        asyncio.create_task(self.collect_and_store_ladder())
    
    @slash_command(
        name="ladder_status",
        description="[Admin] Affiche le statut de la collecte du ladder",
        default_member_permissions=Permissions.ADMINISTRATOR
    )
    async def ladder_status(self, ctx: SlashContext):
        """Affiche le statut de la collecte."""
        
        if self.is_collecting:
            await ctx.send(
                f":arrows_counterclockwise: **Collecte en cours**\n"
                f"Tier actuel: **{self.progress['tier']}**\n"
                f"Joueurs collectés: **{self.progress['current']:,}**\n"
                f"Erreurs: **{self.progress['errors']}**",
                ephemeral=True
            )
        else:
            # Récupérer les stats de la dernière collecte
            df = lire_bdd_perso('''
                SELECT COUNT(*) as total, MAX(updated_at) as last_update
                FROM ladder_euw
            ''', index_col=None).T
            
            if df.empty or df.iloc[0]['total'] == 0:
                return await ctx.send(":x: Aucune donnée de ladder disponible.", ephemeral=True)
            
            total = df.iloc[0]['total']
            last_update = df.iloc[0]['last_update']
            
            await ctx.send(
                f":white_check_mark: **Ladder à jour**\n"
                f"Joueurs indexés: **{total:,}**\n"
                f"Dernière mise à jour: **{last_update}**",
                ephemeral=True
            )
    
    @slash_command(
        name="ladder_reset",
        description="[Admin] Reset le statut de collecte en cas de blocage",
        default_member_permissions=Permissions.ADMINISTRATOR
    )
    async def ladder_reset(self, ctx: SlashContext):
        """Reset le statut de collecte."""
        self.is_collecting = False
        self.progress = {"current": 0, "total": 0, "tier": "", "errors": 0}
        await ctx.send(":white_check_mark: Statut de collecte reseté", ephemeral=True)
    
    # ==========================================================================
    # COMMANDE LEADERBOARD
    # ==========================================================================
    
    @slash_command(
        name="ladder",
        description="Affiche le classement EUW global des joueurs suivis",
    )
    async def ladder(self, ctx: SlashContext):
        """Affiche le classement des joueurs suivis sur le ladder EUW."""
        
        await ctx.defer()
        
        df = lire_bdd_perso('''
            SELECT 
                t.riot_id,
                t.riot_tagline,
                l.tier,
                l.rank,
                l.lp,
                l.wins,
                l.losses,
                l.rank_global,
                (SELECT COUNT(*) FROM ladder_euw) as total_players
            FROM tracker t
            INNER JOIN ladder_euw l ON t.puuid = l.puuid
            WHERE t.server_id = :server_id
              AND t.banned = false
              AND t.activation = true
            ORDER BY l.rank_global ASC
        ''', params={'server_id': int(ctx.guild_id)}, index_col=None).T
        
        if df.empty:
            return await ctx.send(":x: Aucun joueur suivi trouvé dans le ladder EUW.")
        
        total_players = df.iloc[0]['total_players']
        
        # Emotes pour le podium
        podium = {0: ":first_place:", 1: ":second_place:", 2: ":third_place:"}
        
 
        
        embed = interactions.Embed(
            title="<:world_emoji:1333120623613841489> Classement EUW Global",
            description=f"Position de vos joueurs parmi **{total_players:,}** joueurs ranked",
            color=0xFFD700
        )
        
        leaderboard_text = ""
        for idx, row in df.iterrows():
            position = podium.get(idx, f"`{idx + 1}.`")
            riot_id = row['riot_id'].upper()
            tier = row['tier']
            rank = row['rank']
            lp = row['lp']
            rank_global = row['rank_global']
            wins = row['wins']
            losses = row['losses']
            wr = round(wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
            
            # Pourcentage top
            top_percent = round(rank_global / total_players * 100, 2)
            
            emote = emote_rank_discord.get(tier, "")
            
            leaderboard_text += (
                f"{position} **{riot_id}** - #{rank_global:,} (top {top_percent}%)\n"
                f"　　{emote} {tier} {rank} • {lp} LP • {wr}% WR\n"
            )
        
        embed.add_field(name="Classement", value=leaderboard_text or "Aucun joueur", inline=False)
        embed.set_footer(text="Mis à jour quotidiennement à 3h00")
        
        await ctx.send(embeds=embed)
    
    # ==========================================================================
    # COLLECTE DU LADDER
    # ==========================================================================
    
    async def collect_and_store_ladder(self, queue: str = "RANKED_SOLO_5x5"):
        """Collecte le ladder complet et le stocke en BDD."""
        
        if self.is_collecting:
            print(":warning: Collecte déjà en cours, abandon.")
            return
        
        self.is_collecting = True
        self.progress = {"current": 0, "total": 0, "tier": "Initialisation", "errors": 0}
        start_time = datetime.now()
        
        tiers = ["DIAMOND", "EMERALD", "PLATINUM", "GOLD", "SILVER", "BRONZE", "IRON"]
        divisions = ["I", "II", "III", "IV"]
        
        # Dictionnaire pour dédupliquer par puuid
        players_dict = {}
        request_count = 0
        
        try:
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                headers = {"X-Riot-Token": api_key_lol}
                
                # 1. High elo
                for tier, endpoint in [
                    ("CHALLENGER", "challengerleagues"),
                    ("GRANDMASTER", "grandmasterleagues"),
                    ("MASTER", "masterleagues")
                ]:
                    self.progress["tier"] = tier
                    await self.rate_limiter.wait()
                    url = f"https://euw1.api.riotgames.com/lol/league/v4/{endpoint}/by-queue/{queue}"
                    
                    try:
                        async with session.get(url, headers=headers) as resp:
                            request_count += 1
                            
                            if resp.status != 200:
                                print(f":warning: Erreur {resp.status} pour {tier}")
                                self.progress["errors"] += 1
                                continue
                            
                            data = await resp.json()
                            
                            for entry in data.get("entries", []):
                                puuid = entry["puuid"]
                                # Garde le meilleur LP si doublon
                                if puuid not in players_dict or entry["leaguePoints"] > players_dict[puuid]["lp"]:
                                    players_dict[puuid] = {
                                        "puuid": puuid,
                                        "tier": tier,
                                        "rank": entry["rank"],
                                        "lp": entry["leaguePoints"],
                                        "wins": entry["wins"],
                                        "losses": entry["losses"]
                                    }
                            
                            self.progress["current"] = len(players_dict)
                        
                        print(f":white_check_mark: {tier}: {len(data.get('entries', []))} joueurs")
                    
                    except asyncio.TimeoutError:
                        print(f":timer: Timeout pour {tier}")
                        self.progress["errors"] += 1
                        continue
                    
                    except Exception as e:
                        print(f":x: Erreur {tier}: {e}")
                        self.progress["errors"] += 1
                        continue
                
                # 2. Diamond à Iron
                for tier in tiers:
                    self.progress["tier"] = tier
                    tier_count = 0
                    
                    for division in divisions:
                        page = 1
                        consecutive_errors = 0
                        
                        while True:
                            if consecutive_errors >= 3:
                                print(f":warning: Trop d'erreurs pour {tier} {division}, passage au suivant")
                                break
                            
                            await self.rate_limiter.wait()
                            url = f"https://euw1.api.riotgames.com/lol/league/v4/entries/{queue}/{tier}/{division}?page={page}"
                            
                            try:
                                async with session.get(url, headers=headers) as resp:
                                    request_count += 1
                                    
                                    if resp.status == 429:
                                        retry_after = int(resp.headers.get("Retry-After", 10))
                                        print(f":timer: Rate limit, attente {retry_after}s...")
                                        await asyncio.sleep(retry_after)
                                        continue
                                    
                                    if resp.status != 200:
                                        print(f":warning: Erreur {resp.status} pour {tier} {division} page {page}")
                                        self.progress["errors"] += 1
                                        consecutive_errors += 1
                                        break
                                    
                                    entries = await resp.json()
                                    
                                    if not entries:
                                        break
                                    
                                    for entry in entries:
                                        puuid = entry["puuid"]
                                        # Garde le meilleur LP si doublon
                                        if puuid not in players_dict or entry["leaguePoints"] > players_dict[puuid]["lp"]:
                                            players_dict[puuid] = {
                                                "puuid": puuid,
                                                "tier": tier,
                                                "rank": division,
                                                "lp": entry["leaguePoints"],
                                                "wins": entry["wins"],
                                                "losses": entry["losses"]
                                            }
                                    
                                    tier_count += len(entries)
                                    self.progress["current"] = len(players_dict)
                                    page += 1
                                    consecutive_errors = 0
                            
                            except asyncio.TimeoutError:
                                print(f"⏱️ Timeout {tier} {division} page {page}, retry...")
                                self.progress["errors"] += 1
                                consecutive_errors += 1
                                await asyncio.sleep(5)
                                continue
                            
                            except Exception as e:
                                print(f":x: Erreur {tier} {division} page {page}: {e}")
                                self.progress["errors"] += 1
                                consecutive_errors += 1
                                break
                    
                    print(f":white_check_mark: {tier}: {tier_count} joueurs ({request_count} requêtes)")
            
            # 3. Convertir en liste et trier
            if players_dict:
                self.progress["tier"] = "Tri et sauvegarde..."
                all_players = list(players_dict.values())
                print(f":arrows_counterclockwise: Tri de {len(all_players):,} joueurs uniques...")
                
                all_players.sort(key=lambda x: calculate_rank_score(x["tier"], x["rank"], x["lp"]), reverse=True)
                
                for i, player in enumerate(all_players):
                    player["rank_global"] = i + 1
                
                # 4. Sauvegarder en BDD
                await self.save_ladder_to_db(all_players)
                
                elapsed = datetime.now() - start_time
                print(f":white_check_mark: Collecte terminée: {len(all_players):,} joueurs en {elapsed} ({request_count} requêtes, {self.progress['errors']} erreurs)")
            else:
                print(":x: Aucun joueur collecté!")
        
        except Exception as e:
            print(f":x: ERREUR FATALE dans collect_and_store_ladder: {e}")
            traceback.print_exc()
        
        finally:
            self.is_collecting = False
            self.progress["tier"] = "Terminé"
    
    async def save_ladder_to_db(self, players: list):
        """Sauvegarde le ladder en BDD."""
        
        print(f":floppy_disk: Sauvegarde de {len(players):,} joueurs en BDD...")
        
        try:
            # Vider la table
            requete_perso_bdd('TRUNCATE TABLE ladder_euw')
            
            # Insert par batch
            batch_size = 5000
            for i in range(0, len(players), batch_size):
                batch = players[i:i + batch_size]
                
                # Escape les puuid pour éviter les injections SQL
                values = ", ".join([
                    f"($${p['puuid']}$$, '{p['tier']}', '{p['rank']}', {p['lp']}, {p['wins']}, {p['losses']}, {p['rank_global']}, NOW())"
                    for p in batch
                ])
                
                requete_perso_bdd(f'''
                    INSERT INTO ladder_euw (puuid, tier, rank, lp, wins, losses, rank_global, updated_at)
                    VALUES {values}
                ''')
                
                print(f"  :floppy_disk: Batch {i // batch_size + 1}/{(len(players) // batch_size) + 1}: {len(batch)} joueurs insérés")
            
            print(f":white_check_mark: Sauvegarde terminée")
        
        except Exception as e:
            print(f":x: Erreur lors de la sauvegarde: {e}")
            traceback.print_exc()


def setup(bot):
    LadderCollector(bot)