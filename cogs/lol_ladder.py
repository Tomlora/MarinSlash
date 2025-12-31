import asyncio
from datetime import datetime
import interactions
from interactions import Extension, listen, slash_command, SlashContext, SlashCommandOption, OptionType, Permissions, Task, TimeTrigger
import aiohttp

from fonctions.gestion_bdd import requete_perso_bdd, lire_bdd_perso
from utils.params import api_key_lol, region, my_region


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
        
        if elapsed < self.interval:
            await asyncio.sleep(self.interval - elapsed)
        
        self.last_call = asyncio.get_event_loop().time()


class LadderCollector(Extension):
    
    def __init__(self, bot):
        self.bot = bot
        self.rate_limiter = RateLimiter(calls_per_minute=55)
        self.is_collecting = False
        self.progress = {"current": 0, "total": 0, "tier": ""}
    
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
        print("✅ Tâche de collecte du ladder planifiée à 3h00")
    
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
                f"⚠️ Collecte déjà en cours...\n"
                f"Progression: **{self.progress['tier']}** - {self.progress['current']:,} joueurs collectés",
                ephemeral=True
            )
        
        await ctx.send(
            "🚀 **Lancement de la collecte du ladder EUW**\n"
            "⏱️ Durée estimée: ~50 minutes\n"
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
                f"🔄 **Collecte en cours**\n"
                f"Tier actuel: **{self.progress['tier']}**\n"
                f"Joueurs collectés: **{self.progress['current']:,}**",
                ephemeral=True
            )
        else:
            # Récupérer les stats de la dernière collecte
            df = lire_bdd_perso('''
                SELECT COUNT(*) as total, MAX(updated_at) as last_update
                FROM ladder_euw
            ''', index_col=None)
            
            if df.empty or df.iloc[0]['total'] == 0:
                return await ctx.send("❌ Aucune donnée de ladder disponible.", ephemeral=True)
            
            total = df.iloc[0]['total']
            last_update = df.iloc[0]['last_update']
            
            await ctx.send(
                f"✅ **Ladder à jour**\n"
                f"Joueurs indexés: **{total:,}**\n"
                f"Dernière mise à jour: **{last_update}**",
                ephemeral=True
            )
    
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
        ''', params={'server_id': int(ctx.guild_id)}, index_col=None)
        
        if df.empty:
            return await ctx.send("❌ Aucun joueur suivi trouvé dans le ladder EUW.")
        
        total_players = df.iloc[0]['total_players']
        
        # Emotes pour le podium
        podium = {0: "🥇", 1: "🥈", 2: "🥉"}
        
        # Emotes pour les tiers
        tier_emotes = {
            "CHALLENGER": "<:challenger:1234>",
            "GRANDMASTER": "<:grandmaster:1234>",
            "MASTER": "<:master:1234>",
            "DIAMOND": "<:diamond:1234>",
            "EMERALD": "<:emerald:1234>",
            "PLATINUM": "<:platinum:1234>",
            "GOLD": "<:gold:1234>",
            "SILVER": "<:silver:1234>",
            "BRONZE": "<:bronze:1234>",
            "IRON": "<:iron:1234>"
        }
        
        embed = interactions.Embed(
            title="🌍 Classement EUW Global",
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
            
            emote = tier_emotes.get(tier, "")
            
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
            return
        
        self.is_collecting = True
        self.progress = {"current": 0, "total": 0, "tier": "Initialisation"}
        start_time = datetime.now()
        
        tiers = ["DIAMOND", "EMERALD", "PLATINUM", "GOLD", "SILVER", "BRONZE", "IRON"]
        divisions = ["I", "II", "III", "IV"]
        
        all_players = []
        request_count = 0
        
        async with aiohttp.ClientSession() as session:
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
                
                async with session.get(url, headers=headers) as resp:
                    request_count += 1
                    
                    if resp.status != 200:
                        print(f"⚠️ Erreur {resp.status} pour {tier}")
                        continue
                    
                    data = await resp.json()
                    
                    for entry in data.get("entries", []):
                        all_players.append({
                            "puuid": entry["puuid"],
                            "tier": tier,
                            "rank": entry["rank"],
                            "lp": entry["leaguePoints"],
                            "wins": entry["wins"],
                            "losses": entry["losses"]
                        })
                    
                    self.progress["current"] = len(all_players)
                
                print(f"✅ {tier}: {len(data.get('entries', []))} joueurs")
            
            # 2. Diamond à Iron
            for tier in tiers:
                self.progress["tier"] = tier
                tier_count = 0
                
                for division in divisions:
                    page = 1
                    
                    while True:
                        await self.rate_limiter.wait()
                        url = f"https://euw1.api.riotgames.com/lol/league/v4/entries/{queue}/{tier}/{division}?page={page}"
                        
                        async with session.get(url, headers=headers) as resp:
                            request_count += 1
                            
                            if resp.status != 200:
                                print(f"⚠️ Erreur {resp.status} pour {tier} {division} page {page}")
                                break
                            
                            entries = await resp.json()
                            
                            if not entries:
                                break
                            
                            for entry in entries:
                                all_players.append({
                                    "puuid": entry["puuid"],
                                    "tier": tier,
                                    "rank": division,
                                    "lp": entry["leaguePoints"],
                                    "wins": entry["wins"],
                                    "losses": entry["losses"]
                                })
                            
                            tier_count += len(entries)
                            self.progress["current"] = len(all_players)
                            page += 1
                
                print(f"✅ {tier}: {tier_count} joueurs ({request_count} requêtes)")
        
        # 3. Trier et attribuer les rangs
        self.progress["tier"] = "Tri et sauvegarde..."
        all_players.sort(key=lambda x: calculate_rank_score(x["tier"], x["rank"], x["lp"]), reverse=True)
        
        for i, player in enumerate(all_players):
            player["rank_global"] = i + 1
        
        # 4. Sauvegarder en BDD
        await self.save_ladder_to_db(all_players)
        
        elapsed = datetime.now() - start_time
        print(f"✅ Collecte terminée: {len(all_players):,} joueurs en {elapsed} ({request_count} requêtes)")
        
        self.is_collecting = False
        return all_players
    
    async def save_ladder_to_db(self, players: list):
        """Sauvegarde le ladder en BDD."""
        
        requete_perso_bdd('TRUNCATE TABLE ladder_euw')
        
        batch_size = 10000
        for i in range(0, len(players), batch_size):
            batch = players[i:i + batch_size]
            
            values = ", ".join([
                f"('{p['puuid']}', '{p['tier']}', '{p['rank']}', {p['lp']}, {p['wins']}, {p['losses']}, {p['rank_global']}, NOW())"
                for p in batch
            ])
            
            requete_perso_bdd(f'''
                INSERT INTO ladder_euw (puuid, tier, rank, lp, wins, losses, rank_global, updated_at)
                VALUES {values}
            ''')
            
            print(f"  💾 Batch {i // batch_size + 1}: {len(batch)} joueurs insérés")


def setup(bot):
    LadderCollector(bot)