import asyncio
from datetime import datetime
import interactions
from interactions import Extension, listen, slash_command, SlashContext, SlashCommandOption, OptionType, Permissions, Task, TimeTrigger, ActionRow, Button, ButtonStyle, Embed, ComponentContext
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
            return await ctx.send(":x: Aucun joueur suivi trouve dans le ladder EUW.")
        
        total_players = df.iloc[0]['total_players']
        total_tracked = len(df)
        
        # Emotes pour le podium
        podium = {0: ":first_place:", 1: ":second_place:", 2: ":third_place:"}
        
        # Construire la liste des joueurs formatés
        players_lines = []
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
            
            top_percent = round(rank_global / total_players * 100, 2)
            emote = emote_rank_discord.get(tier, "")
            
            line = (
                f"{position} **{riot_id}** - #{rank_global:,} (top {top_percent}%)\n"
                f"   {emote} {tier} {rank} | {lp} LP | {wr}% WR"
            )
            players_lines.append(line)
        
        # Pagination - 10 joueurs par page
        players_per_page = 5
        pages = []
        
        for i in range(0, len(players_lines), players_per_page):
            page_lines = players_lines[i:i + players_per_page]
            pages.append("\n".join(page_lines))
        
        total_pages = len(pages)
        current_page = 0
        
        def create_embed(page_num: int) -> Embed:
            embed = Embed(
                title="<:world_emoji:1333120623613841489> Classement EUW Global",
                description=f"Position des **{total_tracked}** joueurs parmi **{total_players:,}** joueurs ranked ({emote_rank_discord['CHALLENGER']} - {emote_rank_discord['GOLD']})",
                color=0xFFD700
            )
            embed.add_field(name="Classement", value=pages[page_num], inline=False)
            embed.set_footer(text=f"Page {page_num + 1}/{total_pages} | Mis a jour quotidiennement a 3h00")
            return embed
        
        def create_buttons(page_num: int) -> list[ActionRow]:
            return [
                ActionRow(
                    Button(
                        style=ButtonStyle.SECONDARY,
                        label="<<",
                        custom_id="ladder_first",
                        disabled=(page_num == 0)
                    ),
                    Button(
                        style=ButtonStyle.PRIMARY,
                        label="<",
                        custom_id="ladder_prev",
                        disabled=(page_num == 0)
                    ),
                    Button(
                        style=ButtonStyle.SECONDARY,
                        label=f"{page_num + 1}/{total_pages}",
                        custom_id="ladder_page",
                        disabled=True
                    ),
                    Button(
                        style=ButtonStyle.PRIMARY,
                        label=">",
                        custom_id="ladder_next",
                        disabled=(page_num >= total_pages - 1)
                    ),
                    Button(
                        style=ButtonStyle.SECONDARY,
                        label=">>",
                        custom_id="ladder_last",
                        disabled=(page_num >= total_pages - 1)
                    )
                )
            ]
        
        # Envoyer la première page
        if total_pages == 1:
            # Pas besoin de pagination
            await ctx.send(embeds=create_embed(0))
        else:
            msg = await ctx.send(embeds=create_embed(0), components=create_buttons(0))
            
            # Gérer les interactions (timeout 5 minutes)
            while True:
                try:
                    button_ctx: ComponentContext = await self.bot.wait_for_component(
                        components=["ladder_first", "ladder_prev", "ladder_next", "ladder_last"],
                        messages=msg,
                        timeout=300
                    )
                    
                    # Vérifier que c'est le même utilisateur
                    if button_ctx.ctx.author.id != ctx.author.id:
                        await button_ctx.send("Ce n'est pas ton classement !", ephemeral=True)
                        continue
                    
                    if button_ctx.ctx.custom_id == "ladder_first":
                        current_page = 0
                    elif button_ctx.ctx.custom_id == "ladder_prev":
                        current_page = max(0, current_page - 1)
                    elif button_ctx.ctx.custom_id == "ladder_next":
                        current_page = min(total_pages - 1, current_page + 1)
                    elif button_ctx.ctx.custom_id == "ladder_last":
                        current_page = total_pages - 1
                    
                    await button_ctx.ctx.edit_origin(
                        embeds=create_embed(current_page),
                        components=create_buttons(current_page)
                    )
                
                except asyncio.TimeoutError:
                    # Désactiver les boutons après timeout
                    disabled_buttons = [
                        ActionRow(
                            Button(style=ButtonStyle.SECONDARY, label="<<", custom_id="ladder_first", disabled=True),
                            Button(style=ButtonStyle.PRIMARY, label="<", custom_id="ladder_prev", disabled=True),
                            Button(style=ButtonStyle.SECONDARY, label=f"{current_page + 1}/{total_pages}", custom_id="ladder_page", disabled=True),
                            Button(style=ButtonStyle.PRIMARY, label=">", custom_id="ladder_next", disabled=True),
                            Button(style=ButtonStyle.SECONDARY, label=">>", custom_id="ladder_last", disabled=True)
                        )
                    ]
                    try:
                        await msg.edit(components=disabled_buttons)
                    except:
                        pass
                    break
    
    # ==========================================================================
    # COLLECTE DU LADDER
    # ==========================================================================
    
    async def collect_and_store_ladder(self, queue: str = "RANKED_SOLO_5x5"):
        """Collecte le ladder complet et le stocke en BDD avec sauvegardes intermédiaires."""
        
        if self.is_collecting:
            print("Collecte deja en cours, abandon.")
            return
        
        self.is_collecting = True
        self.progress = {"current": 0, "total": 0, "tier": "Initialisation", "errors": 0}
        start_time = datetime.now()
        
        # tiers_low = ["DIAMOND", "EMERALD", "PLATINUM", "GOLD", "SILVER", "BRONZE", "IRON"]
        tiers_low = ["DIAMOND", "EMERALD", "PLATINUM", "GOLD"]
        divisions = ["I", "II", "III", "IV"]
        
        request_count = 0
        total_players = 0
        
        try:
            # Vider la table au début
            print("[INIT] Vidage de la table ladder_euw...")
            requete_perso_bdd('TRUNCATE TABLE ladder_euw')
            
            timeout = aiohttp.ClientTimeout(total=60)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                headers = {"X-Riot-Token": api_key_lol}
                
                # =================================================================
                # 1. HIGH ELO (Challenger, Grandmaster, Master)
                # =================================================================
                high_elo_players = {}
                
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
                                print(f"[WARN] Erreur {resp.status} pour {tier}")
                                self.progress["errors"] += 1
                                continue
                            
                            data = await resp.json()
                            
                            for entry in data.get("entries", []):
                                puuid = entry["puuid"]
                                if puuid not in high_elo_players or entry["leaguePoints"] > high_elo_players[puuid]["lp"]:
                                    high_elo_players[puuid] = {
                                        "puuid": puuid,
                                        "tier": tier,
                                        "rank": entry["rank"],
                                        "lp": entry["leaguePoints"],
                                        "wins": entry["wins"],
                                        "losses": entry["losses"]
                                    }
                            
                            self.progress["current"] = len(high_elo_players)
                            print(f"[OK] {tier}: {len(data.get('entries', []))} joueurs")
                    
                    except Exception as e:
                        print(f"[ERR] {tier}: {e}")
                        self.progress["errors"] += 1
                        continue
                
                # Sauvegarde high elo
                if high_elo_players:
                    await self.save_batch_to_db(high_elo_players)
                    total_players += len(high_elo_players)
                    print(f"[SAVE] High elo sauvegarde: {len(high_elo_players):,} joueurs")
                
                # =================================================================
                # 2. DIAMOND A IRON (avec sauvegarde par tier)
                # =================================================================
                for tier in tiers_low:
                    self.progress["tier"] = tier
                    tier_players = {}
                    tier_count = 0
                    
                    for division in divisions:
                        page = 1
                        consecutive_errors = 0
                        max_retries = 5
                        
                        while True:
                            if consecutive_errors >= max_retries:
                                print(f"[WARN] Trop d'erreurs pour {tier} {division}, passage au suivant")
                                break
                            
                            await self.rate_limiter.wait()
                            url = f"https://euw1.api.riotgames.com/lol/league/v4/entries/{queue}/{tier}/{division}?page={page}"
                            
                            try:
                                async with session.get(url, headers=headers) as resp:
                                    request_count += 1
                                    
                                    # Rate limit
                                    if resp.status == 429:
                                        retry_after = int(resp.headers.get("Retry-After", 30))
                                        print(f"[RATE] Rate limit, attente {retry_after}s...")
                                        await asyncio.sleep(retry_after)
                                        continue
                                    
                                    # Gateway timeout - retry avec délai
                                    if resp.status == 504:
                                        consecutive_errors += 1
                                        wait_time = 10 * consecutive_errors
                                        print(f"[504] Timeout Riot {tier} {division} p{page}, retry {wait_time}s ({consecutive_errors}/{max_retries})")
                                        await asyncio.sleep(wait_time)
                                        continue
                                    
                                    # Autres erreurs serveur
                                    if resp.status >= 500:
                                        consecutive_errors += 1
                                        wait_time = 5 * consecutive_errors
                                        print(f"[{resp.status}] Erreur serveur {tier} {division} p{page}, retry {wait_time}s")
                                        await asyncio.sleep(wait_time)
                                        continue
                                    
                                    if resp.status != 200:
                                        print(f"[WARN] Erreur {resp.status} pour {tier} {division} page {page}")
                                        self.progress["errors"] += 1
                                        break
                                    
                                    entries = await resp.json()
                                    
                                    if not entries:
                                        break
                                    
                                    for entry in entries:
                                        puuid = entry["puuid"]
                                        if puuid not in tier_players or entry["leaguePoints"] > tier_players[puuid]["lp"]:
                                            tier_players[puuid] = {
                                                "puuid": puuid,
                                                "tier": tier,
                                                "rank": division,
                                                "lp": entry["leaguePoints"],
                                                "wins": entry["wins"],
                                                "losses": entry["losses"]
                                            }
                                    
                                    tier_count += len(entries)
                                    self.progress["current"] = total_players + len(tier_players)
                                    page += 1
                                    consecutive_errors = 0
                            
                            except asyncio.TimeoutError:
                                consecutive_errors += 1
                                wait_time = 10 * consecutive_errors
                                print(f"[TIMEOUT] {tier} {division} p{page}, retry {wait_time}s ({consecutive_errors}/{max_retries})")
                                await asyncio.sleep(wait_time)
                                continue
                            
                            except Exception as e:
                                print(f"[ERR] {tier} {division} p{page}: {e}")
                                self.progress["errors"] += 1
                                consecutive_errors += 1
                                await asyncio.sleep(5)
                                continue
                    
                    # Sauvegarde après chaque tier
                    if tier_players:
                        await self.save_batch_to_db(tier_players)
                        total_players += len(tier_players)
                        print(f"[SAVE] {tier}: {len(tier_players):,} joueurs (total: {total_players:,}, {request_count} req)")
                    else:
                        print(f"[WARN] {tier}: aucun joueur collecte")
            
            # =================================================================
            # 3. CALCUL DES RANGS GLOBAUX
            # =================================================================
            if total_players > 0:
                self.progress["tier"] = "Calcul des rangs..."
                await self.update_global_ranks()
                
                elapsed = datetime.now() - start_time
                print(f"[DONE] Collecte terminee: {total_players:,} joueurs en {elapsed} ({request_count} req, {self.progress['errors']} err)")
            else:
                print("[ERR] Aucun joueur collecte!")
        
        except Exception as e:
            print(f"[FATAL] Erreur dans collect_and_store_ladder: {e}")
            traceback.print_exc()
        
        finally:
            self.is_collecting = False
            self.progress["tier"] = "Termine"


    async def save_batch_to_db(self, players_dict: dict):
        """Sauvegarde un batch de joueurs avec gestion des doublons."""
        players = list(players_dict.values())
        batch_size = 5000
        
        for i in range(0, len(players), batch_size):
            batch = players[i:i + batch_size]
            values = ", ".join([
                f"($${p['puuid']}$$, '{p['tier']}', '{p['rank']}', {p['lp']}, {p['wins']}, {p['losses']}, 0, NOW())"
                for p in batch
            ])
            
            requete_perso_bdd(f'''
                INSERT INTO ladder_euw (puuid, tier, rank, lp, wins, losses, rank_global, updated_at)
                VALUES {values}
                ON CONFLICT (puuid) DO UPDATE SET
                    tier = EXCLUDED.tier,
                    rank = EXCLUDED.rank,
                    lp = EXCLUDED.lp,
                    wins = EXCLUDED.wins,
                    losses = EXCLUDED.losses,
                    updated_at = NOW()
            ''')


    async def update_global_ranks(self):
        """Met à jour les rangs globaux en SQL (beaucoup plus rapide)."""
        print("[RANK] Calcul des rangs globaux...")
        
        requete_perso_bdd('''
            WITH ranked AS (
                SELECT puuid,
                    ROW_NUMBER() OVER (
                        ORDER BY 
                            CASE tier 
                                WHEN 'CHALLENGER' THEN 2800
                                WHEN 'GRANDMASTER' THEN 2400
                                WHEN 'MASTER' THEN 2000
                                WHEN 'DIAMOND' THEN 1600
                                WHEN 'EMERALD' THEN 1200
                                WHEN 'PLATINUM' THEN 800
                                WHEN 'GOLD' THEN 400
                                WHEN 'SILVER' THEN 0
                                WHEN 'BRONZE' THEN -400
                                WHEN 'IRON' THEN -800
                            END +
                            CASE rank
                                WHEN 'I' THEN 300
                                WHEN 'II' THEN 200
                                WHEN 'III' THEN 100
                                WHEN 'IV' THEN 0
                            END +
                            lp DESC
                    ) as new_rank
                FROM ladder_euw
            )
            UPDATE ladder_euw l
            SET rank_global = r.new_rank
            FROM ranked r
            WHERE l.puuid = r.puuid
        ''')
        
        print("[RANK] Rangs globaux mis a jour")


def setup(bot):
    LadderCollector(bot)