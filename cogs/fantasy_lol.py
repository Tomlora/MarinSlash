from __future__ import annotations

import asyncio
from collections import defaultdict

import interactions
from interactions import (
    Extension,
    OptionType,
    SlashCommandChoice,
    SlashCommandOption,
    SlashContext,
    slash_command,
)

from fonctions.fantasy.database import active_competitions, schema_is_ready
from fonctions.fantasy.lineup import LineupView, get_lineup, set_starter
from fonctions.fantasy.models import Competition, PlayerRole, RosterSlot, STARTER_SLOTS
from fonctions.fantasy.market import claim_free_agent, list_free_agents, list_trades, offer_trade, respond_trade
from fonctions.fantasy.service import (
    FantasyServiceError,
    create_league,
    get_draft_board,
    get_league,
    join_league,
    pick_asset,
    start_draft,
)


STATUS_LABELS = {
    "registration": "Inscriptions",
    "draft": "Draft",
    "active": "Active",
    "finished": "Terminée",
    "cancelled": "Annulée",
}

TRADE_STATUS_LABELS = {
    'pending': 'En attente', 'accepted': 'Accepté', 'declined': 'Refusé',
    'cancelled': 'Annulé', 'invalidated': 'Invalidé',
}


def _integer_option(name, description, required=True):
    return SlashCommandOption(name=name, description=description, type=OptionType.INTEGER,
                              required=required, min_value=1)


def _league_option():
    return _integer_option('league_id', 'ID de la Fantasy')


def _asset_type_option():
    return SlashCommandOption(name='type', description="Joueur ou équipe professionnelle", type=OptionType.STRING,
                              required=True, choices=[SlashCommandChoice(name='Joueur', value='player'),
                                                      SlashCommandChoice(name='Équipe', value='team')])


def format_trade(trade):
    kind = 'Joueurs' if trade.asset_type == 'player' else 'Équipes'
    return (f"**#{trade.trade_id} — {TRADE_STATUS_LABELS[trade.status]}** ({kind})\n"
            f"<@{trade.proposer_discord_id}> : {trade.offered_name[:40]} (`{trade.offered_id}`) ↔ "
            f"<@{trade.recipient_discord_id}> : {trade.requested_name[:40]} (`{trade.requested_id}`)")


def format_lineup(view: LineupView) -> str:
    lines = [f"🏆 **{view.league_name[:80]} — {view.season_name[:80]}**", "**Titulaires**"]
    order = {slot: index for index, slot in enumerate((*STARTER_SLOTS, RosterSlot.BENCH, RosterSlot.TEAM))}
    for entry in sorted(view.entries, key=lambda item: order[item.slot]):
        asset = entry.player or entry.team
        label = entry.player.handle if entry.player else entry.team.name
        asset_id = entry.player.player_id if entry.player else entry.team.team_id
        locked = " 🔒" if asset.competition in view.locked else ""
        if asset.competition in view.stale:
            locked += " ⚠️ calendrier non vérifié"
        unavailable = " ⚠️ indisponible" if entry.player and asset_id in view.unavailable_players else ""
        slot = "Banc" if entry.slot == RosterSlot.BENCH else entry.slot.value
        role = f" / {entry.player.role.value}" if entry.slot == RosterSlot.BENCH else ""
        lines.append(f"• **{slot}{role}** : {label[:60]} (`{asset_id}`) — {asset.competition.value}{locked}{unavailable}")
    lines.append("\n`/fantasy lineup league_id:… joueur_id:…` pour titulariser un joueur du banc.")
    lines.append("🔒 Verrouillage toute la journée à Paris, selon le calendrier synchronisé.")
    return "\n".join(lines)


class FantasyLoL(Extension):
    def __init__(self, bot):
        self.bot: interactions.Client = bot

    @staticmethod
    def _guild_id(ctx: SlashContext) -> int:
        if ctx.guild_id is None:
            raise FantasyServiceError("Les commandes Fantasy doivent être utilisées sur un serveur.")
        return int(ctx.guild_id)

    @staticmethod
    async def _error(ctx: SlashContext, exc: Exception, *, ephemeral: bool = True):
        if isinstance(exc, FantasyServiceError):
            message = str(exc)
        else:
            message = f"Erreur Fantasy inattendue : `{type(exc).__name__}`."
        await ctx.send(f"❌ {message}", ephemeral=ephemeral)

    @slash_command(name="fantasy", description="Fantasy League of Legends")
    async def fantasy(self, ctx: SlashContext):
        pass

    @fantasy.subcommand(
        "roster", sub_cmd_description="Affiche tes titulaires, ton banc et les verrouillages",
        options=[SlashCommandOption(name="league_id", description="ID de la Fantasy",
                                    type=OptionType.INTEGER, required=True, min_value=1),
                 SlashCommandOption(name="manager", description="Consulter le roster d'un autre manager de la ligue",
                                    type=OptionType.USER, required=False)],
    )
    async def fantasy_roster(self, ctx: SlashContext, league_id: int, manager: interactions.User = None):
        await ctx.defer(ephemeral=True)
        try:
            view = await asyncio.to_thread(get_lineup, league_id=int(league_id),
                                           guild_id=self._guild_id(ctx), discord_user_id=int(ctx.author_id),
                                           target_discord_id=int(manager.id) if manager is not None else None)
        except Exception as exc:
            return await self._error(ctx, exc)
        owner = int(manager.id) if manager is not None else int(ctx.author_id)
        await ctx.send(f"Roster de <@{owner}>\n" + format_lineup(view), ephemeral=True)

    @fantasy.subcommand(
        "market", sub_cmd_description="Liste les joueurs ou équipes libres après la draft",
        options=[_league_option(), _asset_type_option(),
                 SlashCommandOption(name='role', description='Filtrer les joueurs par rôle', type=OptionType.STRING,
                                    choices=[SlashCommandChoice(name=r.value, value=r.value) for r in PlayerRole]),
                 SlashCommandOption(name='championnat', description='Filtrer par championnat', type=OptionType.STRING,
                                    choices=[SlashCommandChoice(name=c.value, value=c.value) for c in Competition]),
                 _integer_option('page', 'Page du marché', required=False)],
    )
    async def fantasy_market(self, ctx: SlashContext, league_id: int, type: str,
                             role: str = None, championnat: str = None, page: int = 1):
        await ctx.defer(ephemeral=True)
        try:
            result = await asyncio.to_thread(list_free_agents, league_id=league_id, guild_id=self._guild_id(ctx),
                                            discord_user_id=int(ctx.author_id), asset_type=type,
                                            role=role, competition=championnat, page=page)
        except Exception as exc:
            return await self._error(ctx, exc)
        lines = [f"**Marché — page {result.page}**"]
        for asset in result.assets:
            if type == 'player':
                lines.append(f"• `{asset.player_id}` **{asset.handle[:40]}** — {asset.role.value} / {asset.competition.value}")
            else:
                lines.append(f"• `{asset.team_id}` **{asset.name[:40]}** — {asset.competition.value}")
        if not result.assets:
            lines.append("Aucun résultat sur cette page.")
        if result.has_more:
            lines.append(f"Suite : relance la commande avec `page:{page + 1}`.")
        lines.append("`/fantasy claim` pour recruter en libérant un joueur ou une équipe de ton roster.\n"
                     "Disponibilité et calendrier revérifiés au recrutement.")
        # Max 20 bounded names; split if unusually large IDs exceed Discord's limit.
        message = '\n'.join(lines)
        if len(message) > 1950:
            await ctx.send('\n'.join(lines[:11]), ephemeral=True)
            message = '\n'.join(lines[11:])
        await ctx.send(message, ephemeral=True)

    @fantasy.subcommand(
        "claim", sub_cmd_description="Recrute un agent libre et libère un asset du même type",
        options=[_league_option(), _asset_type_option(),
                 _integer_option('libere_id', 'ID du joueur ou de l’équipe à libérer'),
                 _integer_option('recrute_id', 'ID du joueur ou de l’équipe libre à recruter')],
    )
    async def fantasy_claim(self, ctx: SlashContext, league_id: int, type: str, libere_id: int, recrute_id: int):
        await ctx.defer(ephemeral=True)
        try:
            view = await asyncio.to_thread(claim_free_agent, league_id=league_id, guild_id=self._guild_id(ctx),
                                          discord_user_id=int(ctx.author_id), asset_type=type,
                                          released_id=libere_id, incoming_id=recrute_id)
        except Exception as exc:
            return await self._error(ctx, exc)
        await ctx.send("✅ Recrutement enregistré.\n" + format_lineup(view), ephemeral=True)

    @fantasy.subcommand(
        "trade_offer", sub_cmd_description="Propose un échange à un autre manager",
        options=[_league_option(), _asset_type_option(),
                 SlashCommandOption(name='manager', description='Manager destinataire', type=OptionType.USER, required=True),
                 _integer_option('offert_id', 'ID du joueur ou de l’équipe que tu proposes'),
                 _integer_option('demande_id', 'ID du joueur ou de l’équipe que tu demandes')],
    )
    async def fantasy_trade_offer(self, ctx: SlashContext, league_id: int, type: str,
                                  manager: interactions.User, offert_id: int, demande_id: int):
        await ctx.defer(ephemeral=True)
        try:
            trade = await asyncio.to_thread(offer_trade, league_id=league_id, guild_id=self._guild_id(ctx),
                                           discord_user_id=int(ctx.author_id), recipient_discord_id=int(manager.id),
                                           asset_type=type, offered_id=offert_id, requested_id=demande_id)
        except Exception as exc:
            return await self._error(ctx, exc)
        await ctx.send(format_trade(trade) + "\nLe destinataire retrouve cette offre avec `/fantasy trades`. "
                       "Aucun transfert avant son acceptation.", ephemeral=True)

    @fantasy.subcommand(
        "trades", sub_cmd_description="Consulte tes offres reçues, envoyées et terminées",
        options=[_league_option(), _integer_option('page', 'Page des échanges', required=False)],
    )
    async def fantasy_trades(self, ctx: SlashContext, league_id: int, page: int = 1):
        await ctx.defer(ephemeral=True)
        try:
            trades, more = await asyncio.to_thread(list_trades, league_id=league_id, guild_id=self._guild_id(ctx),
                                                  discord_user_id=int(ctx.author_id), page=page)
        except Exception as exc:
            return await self._error(ctx, exc)
        message = f"**Échanges — page {page}**\n"
        for trade in trades:
            block = format_trade(trade) + '\n'
            if len(message) + len(block) > 1800:
                await ctx.send(message, ephemeral=True)
                message = ''
            message += block
        if not trades:
            message += "Aucun échange sur cette page.\n"
        if more:
            message += f"Suite : `page:{page + 1}`.\n"
        message += "`/fantasy trade_reply` pour accepter, refuser ou annuler une offre."
        await ctx.send(message, ephemeral=True)

    @fantasy.subcommand(
        "trade_reply", sub_cmd_description="Accepte, refuse ou annule un échange",
        options=[_league_option(), _integer_option('trade_id', 'ID de l’échange'),
                 SlashCommandOption(name='action', description='Action à effectuer', type=OptionType.STRING, required=True,
                                    choices=[SlashCommandChoice(name='Accepter', value='accept'),
                                             SlashCommandChoice(name='Refuser', value='decline'),
                                             SlashCommandChoice(name='Annuler mon offre', value='cancel')])],
    )
    async def fantasy_trade_reply(self, ctx: SlashContext, league_id: int, trade_id: int, action: str):
        await ctx.defer(ephemeral=True)
        try:
            trade = await asyncio.to_thread(respond_trade, league_id=league_id, guild_id=self._guild_id(ctx),
                                           discord_user_id=int(ctx.author_id), trade_id=trade_id, action=action)
        except Exception as exc:
            return await self._error(ctx, exc)
        await ctx.send(format_trade(trade), ephemeral=True)

    @fantasy.subcommand(
        "lineup", sub_cmd_description="Titularise un joueur du banc à son rôle",
        options=[
            SlashCommandOption(name="league_id", description="ID de la Fantasy",
                               type=OptionType.INTEGER, required=True, min_value=1),
            SlashCommandOption(name="joueur_id", description="ID du joueur du banc affiché par /fantasy roster",
                               type=OptionType.INTEGER, required=True, min_value=1),
        ],
    )
    async def fantasy_lineup(self, ctx: SlashContext, league_id: int, joueur_id: int):
        await ctx.defer(ephemeral=True)
        try:
            view = await asyncio.to_thread(set_starter, league_id=int(league_id),
                                           guild_id=self._guild_id(ctx), discord_user_id=int(ctx.author_id),
                                           player_id=int(joueur_id))
        except Exception as exc:
            return await self._error(ctx, exc)
        await ctx.send("✅ Remplacement enregistré.\n" + format_lineup(view), ephemeral=True)

    @fantasy.subcommand("status", sub_cmd_description="Vérifie le socle Fantasy LoL")
    async def fantasy_status(self, ctx: SlashContext):
        await ctx.defer(ephemeral=True)
        try:
            if not schema_is_ready():
                return await ctx.send(
                    "Le schéma PostgreSQL `fantasy` n'est pas encore installé.",
                    ephemeral=True,
                )
            competitions = active_competitions()
        except Exception as exc:
            return await self._error(ctx, exc)

        await ctx.send(
            "Fantasy LoL est initialisé. Championnats actifs : "
            + ", ".join(competitions),
            ephemeral=True,
        )

    @fantasy.subcommand("rules", sub_cmd_description="Affiche les règles de roster")
    async def fantasy_rules(self, ctx: SlashContext):
        await ctx.send(
            "**Roster Fantasy LoL**\n"
            "• 5 titulaires : TOP / JUNGLE / MID / ADC / SUPPORT\n"
            "• 1 équipe professionnelle\n"
            "• 3 remplaçants\n"
            "• au moins 2 championnats représentés parmi les 5 titulaires\n"
            "• LEC, LCS et LFL\n"
            "• 2 à 8 managers par ligue",
            ephemeral=True,
        )

    @fantasy.subcommand(
        "create",
        sub_cmd_description="Crée une nouvelle Fantasy et t'y inscrit",
        options=[
            SlashCommandOption(
                name="nom",
                description="Nom de la Fantasy",
                type=OptionType.STRING,
                required=True,
            ),
            SlashCommandOption(
                name="max_managers",
                description="Nombre maximum de managers (2 à 8)",
                type=OptionType.INTEGER,
                required=False,
                min_value=2,
                max_value=8,
            ),
            SlashCommandOption(
                name="saison",
                description="Nom de la saison",
                type=OptionType.STRING,
                required=False,
            ),
            SlashCommandOption(
                name="scoring",
                description="Mode d'agrégation des scores",
                type=OptionType.STRING,
                required=False,
                choices=[
                    SlashCommandChoice(name="Classique", value="classic_sum"),
                    SlashCommandChoice(name="Normalisé", value="normalized"),
                ],
            ),
        ],
    )
    async def fantasy_create(
        self,
        ctx: SlashContext,
        nom: str,
        max_managers: int = 8,
        saison: str = "Saison 1",
        scoring: str = "classic_sum",
    ):
        await ctx.defer(ephemeral=True)
        try:
            league = create_league(
                guild_id=self._guild_id(ctx),
                owner_discord_id=int(ctx.author_id),
                name=nom,
                season_name=saison or "Saison 1",
                max_managers=max_managers or 8,
                scoring_mode=scoring or "classic_sum",
            )
        except Exception as exc:
            return await self._error(ctx, exc)

        await ctx.send(
            f"✅ **{league.name}** créée.\n"
            f"ID : `{league.league_id}`\n"
            f"Saison : **{league.season_name}**\n"
            f"Managers : **1/{league.max_managers}**\n"
            "Tu es automatiquement inscrit comme premier manager.",
            ephemeral=True,
        )

    @fantasy.subcommand(
        "join",
        sub_cmd_description="Rejoint une Fantasy en phase d'inscription",
        options=[
            SlashCommandOption(
                name="league_id",
                description="ID de la Fantasy",
                type=OptionType.INTEGER,
                required=True,
                min_value=1,
            )
        ],
    )
    async def fantasy_join(self, ctx: SlashContext, league_id: int):
        await ctx.defer(ephemeral=True)
        try:
            league = join_league(
                league_id=int(league_id),
                guild_id=self._guild_id(ctx),
                discord_user_id=int(ctx.author_id),
            )
        except Exception as exc:
            return await self._error(ctx, exc)

        await ctx.send(
            f"✅ Tu as rejoint **{league.name}** (`{league.league_id}`).\n"
            f"Managers : **{len(league.managers)}/{league.max_managers}**",
            ephemeral=True,
        )

    @fantasy.subcommand(
        "info",
        sub_cmd_description="Affiche une Fantasy et ses managers",
        options=[
            SlashCommandOption(
                name="league_id",
                description="ID de la Fantasy",
                type=OptionType.INTEGER,
                required=True,
                min_value=1,
            )
        ],
    )
    async def fantasy_info(self, ctx: SlashContext, league_id: int):
        await ctx.defer(ephemeral=True)
        try:
            league = get_league(
                league_id=int(league_id), guild_id=self._guild_id(ctx)
            )
        except Exception as exc:
            return await self._error(ctx, exc)

        manager_lines = []
        for manager in league.managers:
            position = (
                f"#{manager.draft_position}" if manager.draft_position is not None else "—"
            )
            manager_lines.append(f"{position} <@{manager.discord_user_id}>")

        await ctx.send(
            f"🏆 **{league.name}** — `{league.league_id}`\n"
            f"Saison : **{league.season_name}**\n"
            f"État : **{STATUS_LABELS.get(league.status, league.status)}**\n"
            f"Scoring : `{league.scoring_mode}`\n"
            f"Managers : **{len(league.managers)}/{league.max_managers}**\n\n"
            + ("\n".join(manager_lines) if manager_lines else "Aucun manager."),
            ephemeral=True,
        )

    @fantasy.subcommand(
        "draft_start",
        sub_cmd_description="Ferme les inscriptions et lance le snake draft",
        options=[
            SlashCommandOption(
                name="league_id",
                description="ID de la Fantasy",
                type=OptionType.INTEGER,
                required=True,
                min_value=1,
            )
        ],
    )
    async def fantasy_draft_start(self, ctx: SlashContext, league_id: int):
        await ctx.defer(ephemeral=False)
        try:
            board = start_draft(
                league_id=int(league_id),
                guild_id=self._guild_id(ctx),
                requester_discord_id=int(ctx.author_id),
            )
        except Exception as exc:
            return await self._error(ctx, exc, ephemeral=False)

        ordered = [
            manager
            for manager in board.league.managers
            if manager.draft_position is not None
        ]
        ordered.sort(key=lambda manager: int(manager.draft_position))
        order_text = " → ".join(f"<@{manager.discord_user_id}>" for manager in ordered)
        next_text = (
            f"<@{board.next_manager.discord_user_id}>" if board.next_manager else "—"
        )
        await ctx.send(
            f"🐍 **Draft lancé — {board.league.name}**\n"
            f"Ordre du round 1 : {order_text}\n"
            "Le round 2 utilisera l'ordre inverse, puis ainsi de suite.\n\n"
            f"🎯 Premier pick : {next_text}",
            ephemeral=False,
        )

    @fantasy.subcommand(
        "draft_pick",
        sub_cmd_description="Sélectionne un joueur ou une équipe pendant le draft",
        options=[
            SlashCommandOption(
                name="league_id",
                description="ID de la Fantasy",
                type=OptionType.INTEGER,
                required=True,
                min_value=1,
            ),
            SlashCommandOption(
                name="type",
                description="Type d'asset à drafter",
                type=OptionType.STRING,
                required=True,
                choices=[
                    SlashCommandChoice(name="Joueur", value="player"),
                    SlashCommandChoice(name="Équipe", value="team"),
                ],
            ),
            SlashCommandOption(
                name="nom",
                description="Pseudo du joueur ou nom/abréviation de l'équipe",
                type=OptionType.STRING,
                required=True,
            ),
        ],
    )
    async def fantasy_draft_pick(
        self, ctx: SlashContext, league_id: int, type: str, nom: str
    ):
        await ctx.defer(ephemeral=False)
        try:
            result = pick_asset(
                league_id=int(league_id),
                guild_id=self._guild_id(ctx),
                discord_user_id=int(ctx.author_id),
                asset_type=type,
                asset_name=nom,
            )
            board = get_draft_board(
                league_id=int(league_id), guild_id=self._guild_id(ctx)
            )
        except Exception as exc:
            return await self._error(ctx, exc, ephemeral=False)

        asset_icon = "👤" if result.pick.asset_type == "player" else "🛡️"
        if result.draft_completed:
            next_line = "\n🏁 **Draft terminé !** Les rosters initiaux ont été générés."
        elif board.next_manager is not None:
            next_line = f"\n➡️ Prochain pick : <@{board.next_manager.discord_user_id}>"
        else:
            next_line = ""

        await ctx.send(
            f"✅ Pick **#{result.pick.overall_pick}** — round **{result.pick.round_number}**\n"
            f"{asset_icon} <@{result.pick.discord_user_id}> sélectionne "
            f"**{result.pick.asset_name}**.{next_line}",
            ephemeral=False,
        )

    @fantasy.subcommand(
        "draft_board",
        sub_cmd_description="Affiche l'état du draft et les picks effectués",
        options=[
            SlashCommandOption(
                name="league_id",
                description="ID de la Fantasy",
                type=OptionType.INTEGER,
                required=True,
                min_value=1,
            )
        ],
    )
    async def fantasy_draft_board(self, ctx: SlashContext, league_id: int):
        await ctx.defer(ephemeral=True)
        try:
            board = get_draft_board(
                league_id=int(league_id), guild_id=self._guild_id(ctx)
            )
        except Exception as exc:
            return await self._error(ctx, exc)

        if board.draft_id is None:
            return await ctx.send(
                f"Le draft de **{board.league.name}** n'a pas encore commencé.",
                ephemeral=True,
            )

        picks_by_manager = defaultdict(list)
        for pick in board.picks:
            icon = "👤" if pick.asset_type == "player" else "🛡️"
            picks_by_manager[pick.manager_id].append(f"{icon}{pick.asset_name[:24]}")

        managers = [
            manager
            for manager in board.league.managers
            if manager.draft_position is not None
        ]
        managers.sort(key=lambda manager: int(manager.draft_position))
        manager_lines = []
        for manager in managers:
            assets = picks_by_manager.get(manager.manager_id, [])
            asset_text = ", ".join(assets) if assets else "—"
            manager_lines.append(
                f"**#{manager.draft_position}** <@{manager.discord_user_id}> "
                f"({len(assets)}/9) : {asset_text}"
            )

        next_line = (
            f"\n\n➡️ Au tour de <@{board.next_manager.discord_user_id}>"
            if board.next_manager is not None
            else ""
        )
        message = (
            f"🐍 **{board.league.name} — Draft**\n"
            f"Picks : **{board.completed_picks}/{board.total_picks}**\n\n"
            + "\n".join(manager_lines)
            + next_line
        )
        if len(message) > 1950:
            message = message[:1920] + "\n… (board tronqué)"
        await ctx.send(message, ephemeral=True)


def setup(bot):
    FantasyLoL(bot)
