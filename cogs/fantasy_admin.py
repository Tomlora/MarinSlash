from __future__ import annotations

from datetime import datetime, timedelta, timezone

import interactions
from interactions import (
    Extension,
    OptionType,
    SlashCommandChoice,
    SlashCommandOption,
    SlashContext,
    slash_command,
)
from sqlalchemy import text

from fonctions.fantasy.database import get_engine, schema_issues
from fonctions.fantasy.providers.leaguepedia import (
    LeaguepediaPlayerProvider,
    LeaguepediaProviderError,
)
from fonctions.fantasy.providers.oracles_elixir import (
    OracleElixirPlayerProvider,
    OracleElixirProviderError,
)
from fonctions.fantasy.providers.schedule import (
    FallbackScheduleProvider,
    LeaguepediaScheduleProvider,
    RiotEsportsScheduleProvider,
    ScheduleProviderError,
)
from fonctions.fantasy.schedule_sync import FantasyScheduleSyncError, sync_schedule
from fonctions.fantasy.sync import FantasySyncError, sync_player_pool


class FantasyAdmin(Extension):
    def __init__(self, bot):
        self.bot: interactions.Client = bot
        self.sync_running = False
        self.schedule_sync_running = False

    @slash_command(
        name="fantasy_update_db",
        description="[Admin] Met à jour les joueurs et équipes Fantasy LEC/LCS/LFL",
        default_member_permissions=interactions.Permissions.ADMINISTRATOR,
        options=[
            SlashCommandOption(
                name="source",
                description="Source du pool joueurs/équipes",
                type=OptionType.STRING,
                required=False,
                choices=[
                    SlashCommandChoice(name="Oracle's Elixir", value="oracle_elixir"),
                    SlashCommandChoice(name="Leaguepedia", value="leaguepedia"),
                ],
            )
        ],
    )
    async def fantasy_update_db(self, ctx: SlashContext, source: str = "oracle_elixir"):
        if self.sync_running:
            return await ctx.send(
                "Une synchronisation Fantasy est déjà en cours.", ephemeral=True
            )

        await ctx.defer(ephemeral=True)
        self.sync_running = True
        try:
            if source == "leaguepedia":
                provider = LeaguepediaPlayerProvider()
                source_label = "Leaguepedia"
            else:
                provider = OracleElixirPlayerProvider()
                source_label = "Oracle's Elixir"

            result = await sync_player_pool(provider)
        except (
            LeaguepediaProviderError,
            OracleElixirProviderError,
            FantasySyncError,
        ) as exc:
            return await ctx.send(f"❌ Synchronisation annulée : {exc}", ephemeral=True)
        except Exception as exc:
            return await ctx.send(
                f"❌ Erreur inattendue pendant la synchronisation : `{type(exc).__name__}`.",
                ephemeral=True,
            )
        finally:
            self.sync_running = False

        await ctx.send(
            f"✅ **Base Fantasy mise à jour depuis {source_label}**\n"
            f"• équipes trouvées : **{result.teams_seen}**\n"
            f"• joueurs trouvés : **{result.players_seen}**\n"
            f"• nouvelles affectations joueur→équipe : **{result.histories_opened}**\n"
            f"• anciennes affectations clôturées : **{result.histories_closed}**\n"
            f"• équipes désactivées : **{result.teams_deactivated}**\n"
            f"• joueurs désactivés : **{result.players_deactivated}**",
            ephemeral=True,
        )

    @slash_command(
        name="fantasy_update_schedule",
        description="[Admin] Met à jour le calendrier Fantasy avec fallback automatique",
        default_member_permissions=interactions.Permissions.ADMINISTRATOR,
    )
    async def fantasy_update_schedule(self, ctx: SlashContext):
        if self.schedule_sync_running:
            return await ctx.send(
                "Une synchronisation du calendrier Fantasy est déjà en cours.",
                ephemeral=True,
            )

        await ctx.defer(ephemeral=True)
        self.schedule_sync_running = True
        provider = FallbackScheduleProvider(
            LeaguepediaScheduleProvider(),
            RiotEsportsScheduleProvider(),
        )
        now = datetime.now(timezone.utc)
        try:
            result = await sync_schedule(
                provider,
                start=now - timedelta(hours=12),
                end=now + timedelta(days=21),
            )
        except (ScheduleProviderError, FantasyScheduleSyncError) as exc:
            return await ctx.send(f"❌ Synchronisation calendrier annulée : {exc}", ephemeral=True)
        except Exception as exc:
            return await ctx.send(
                f"❌ Erreur inattendue pendant la synchro calendrier : `{type(exc).__name__}`.",
                ephemeral=True,
            )
        finally:
            self.schedule_sync_running = False

        provider_label = {
            "LeaguepediaScheduleProvider": "Leaguepedia Cargo",
            "RiotEsportsScheduleProvider": "LoL Esports",
        }.get(provider.last_provider_name or "", provider.last_provider_name or "inconnu")
        fallback_note = ""
        if provider.errors:
            fallback_note = "\n⚠️ Source primaire indisponible, fallback utilisé."

        await ctx.send(
            f"✅ **Calendrier Fantasy mis à jour via {provider_label}**\n"
            f"• matchs : **{result.matches_seen}**\n"
            f"• championnats : **{', '.join(c.value for c in result.competitions_updated)}**\n"
            f"• références équipes résolues : **{result.teams_resolved}**\n"
            f"• références équipes non résolues : **{result.teams_unresolved}**"
            f"{fallback_note}",
            ephemeral=True,
        )

    @slash_command(
        name="fantasy_db_status",
        description="[Admin] Diagnostique le schéma PostgreSQL Fantasy",
        default_member_permissions=interactions.Permissions.ADMINISTRATOR,
    )
    async def fantasy_db_status(self, ctx: SlashContext):
        await ctx.defer(ephemeral=True)
        try:
            issues = schema_issues()
            if issues:
                details = "\n".join(f"• {issue}" for issue in issues[:15])
                if len(issues) > 15:
                    details += f"\n• … et {len(issues) - 15} autre(s) problème(s)"
                return await ctx.send(
                    "❌ **Schéma Fantasy incomplet ou incompatible**\n" + details,
                    ephemeral=True,
                )

            with get_engine().connect() as connection:
                counts = connection.execute(
                    text(
                        """
                        SELECT
                            (SELECT COUNT(*) FROM fantasy.league) AS leagues,
                            (SELECT COUNT(*) FROM fantasy.season) AS seasons,
                            (SELECT COUNT(*) FROM fantasy.manager) AS managers,
                            (SELECT COUNT(*) FROM fantasy.pro_team WHERE active = TRUE) AS teams,
                            (SELECT COUNT(*) FROM fantasy.pro_player WHERE active = TRUE) AS players
                        """
                    )
                ).one()
        except Exception as exc:
            original = getattr(exc, "orig", None)
            diag = getattr(original, "diag", None) if original is not None else None
            primary = getattr(diag, "message_primary", None) if diag is not None else None
            sqlstate = getattr(original, "pgcode", None) if original is not None else None
            detail = primary or str(original or exc).strip().splitlines()[0]
            prefix = f"SQLSTATE {sqlstate} — " if sqlstate else ""
            return await ctx.send(
                f"❌ **Diagnostic PostgreSQL impossible**\n`{prefix}{detail}`",
                ephemeral=True,
            )

        await ctx.send(
            "✅ **Schéma Fantasy compatible**\n"
            f"• ligues : **{counts.leagues}**\n"
            f"• saisons : **{counts.seasons}**\n"
            f"• managers : **{counts.managers}**\n"
            f"• équipes actives : **{counts.teams}**\n"
            f"• joueurs actifs : **{counts.players}**",
            ephemeral=True,
        )


def setup(bot):
    FantasyAdmin(bot)
