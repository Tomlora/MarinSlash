from __future__ import annotations

import asyncio
import logging
import os

import interactions
from interactions import (
    Extension,
    OptionType,
    SlashCommandChoice,
    SlashCommandOption,
    SlashContext,
    slash_command,
    listen,
)
from sqlalchemy import text

from fonctions.fantasy.database import get_engine, schema_issues
from fonctions.fantasy.automation import run_sync, read_sync_status, SyncBusyError



class FantasyAdmin(Extension):
    def __init__(self, bot):
        self.bot: interactions.Client = bot
        self._sync_task = None
        self._last_errors = {}
        if bot.is_ready:
            self._start_sync_loop()

    def _start_sync_loop(self):
        if os.environ.get("FANTASY_AUTO_SYNC_ENABLED", "0").lower() not in {"1", "true", "yes"}:
            return
        if self._sync_task is None or self._sync_task.done():
            self._sync_task = asyncio.create_task(self._sync_loop())

    @listen()
    async def on_ready(self):
        self._start_sync_loop()

    async def _sync_loop(self):
        while True:
            for kind in ("schedule", "pool"):
                try:
                    await run_sync(kind, automatic=True)
                except SyncBusyError:
                    pass
                except Exception as exc:
                    error = type(exc).__name__
                    if self._last_errors.get(kind) != error:
                        logging.getLogger(__name__).warning("Fantasy %s sync failed: %s", kind, error)
                    self._last_errors[kind] = error
                else:
                    self._last_errors.pop(kind, None)
            await asyncio.sleep(900)

    def drop(self):
        if self._sync_task is not None:
            self._sync_task.cancel()
        super().drop()

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
        await ctx.defer(ephemeral=True)
        try:
            outcome = await run_sync("pool", source=source)
            result, source_label = outcome.result, outcome.source
        except SyncBusyError as exc:
            return await ctx.send(str(exc), ephemeral=True)
        except Exception as exc:
            return await ctx.send(
                f"❌ Synchronisation annulée : `{type(exc).__name__}`. "
                "Consulte /fantasy_sync_status.",
                ephemeral=True,
            )

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
        await ctx.defer(ephemeral=True)
        try:
            outcome = await run_sync("schedule")
            result, provider_label = outcome.result, outcome.source
        except SyncBusyError as exc:
            return await ctx.send(str(exc), ephemeral=True)
        except Exception as exc:
            return await ctx.send(
                f"❌ Synchronisation calendrier annulée : `{type(exc).__name__}`. "
                "Consulte /fantasy_sync_status et vérifie la migration 20261002_fantasy_sync.sql.",
                ephemeral=True,
            )
        fallback_note = "\n⚠️ Source primaire indisponible, fallback utilisé." if outcome.fallback else ""

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
        name="fantasy_sync_status",
        description="[Admin] Affiche la fraîcheur et les erreurs des synchronisations Fantasy",
        default_member_permissions=interactions.Permissions.ADMINISTRATOR,
    )
    async def fantasy_sync_status(self, ctx: SlashContext):
        await ctx.defer(ephemeral=True)
        try:
            status = await asyncio.to_thread(read_sync_status)
            rows = status['jobs']
        except Exception:
            return await ctx.send(
                "Diagnostic indisponible : vérifie PostgreSQL et applique la migration "
                "`20261002_fantasy_sync.sql`.", ephemeral=True,
            )
        enabled = os.environ.get("FANTASY_AUTO_SYNC_ENABLED", "0").lower() in {"1", "true", "yes"}
        lines = ["**Synchronisations Fantasy**", "Automatisation : " + ("activée" if enabled else "désactivée")]
        for row in rows:
            success = row["last_success_at"]
            attempt = row["last_attempt_at"]
            lines.append(f"• **{row['kind']}** — succès : " + (f"<t:{int(success.timestamp())}:R>" if success else "jamais"))
            if attempt:
                lines.append(f"  Dernière tentative : <t:{int(attempt.timestamp())}:R>")
            if row["last_error"]:
                lines.append(f"  Erreur : `{row['last_error']}`")
        if not rows:
            lines.append("Aucune synchronisation enregistrée.")
        lines.append("Calendrier non vérifié : " + (", ".join(status['stale']) or "aucun championnat"))
        lines.append("Calendrier : toutes les heures ; pool : toutes les 24 h. "
                     "Les championnats non vérifiés depuis 3 h bloquent les remplacements.")
        await ctx.send("\n".join(lines), ephemeral=True)

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
