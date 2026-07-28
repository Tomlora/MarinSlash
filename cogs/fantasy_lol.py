from __future__ import annotations

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


class FantasyLoL(Extension):
    def __init__(self, bot):
        self.bot: interactions.Client = bot

    @staticmethod
    def _guild_id(ctx: SlashContext) -> int:
        if ctx.guild_id is None:
            raise FantasyServiceError("Les commandes Fantasy doivent être utilisées sur un serveur.")
        return int(ctx.guild_id)

    @staticmethod
    async def _error(ctx: SlashContext, exc: Exception):
        if isinstance(exc, FantasyServiceError):
            message = str(exc)
        else:
            message = f"Erreur Fantasy inattendue : `{type(exc).__name__}`."
        await ctx.send(f"❌ {message}", ephemeral=True)

    @slash_command(name="fantasy", description="Fantasy League of Legends")
    async def fantasy(self, ctx: SlashContext):
        pass

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
            return await self._error(ctx, exc)

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
            return await self._error(ctx, exc)

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
