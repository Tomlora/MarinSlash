from __future__ import annotations

import interactions
from interactions import Extension, SlashContext, slash_command

from fonctions.fantasy.providers.leaguepedia import (
    LeaguepediaPlayerProvider,
    LeaguepediaProviderError,
)
from fonctions.fantasy.sync import FantasySyncError, sync_player_pool


class FantasyAdmin(Extension):
    def __init__(self, bot):
        self.bot: interactions.Client = bot
        self.sync_running = False

    @slash_command(
        name="fantasy_update_db",
        description="[Admin] Met à jour les joueurs et équipes Fantasy LEC/LCS/LFL",
        default_member_permissions=interactions.Permissions.ADMINISTRATOR,
    )
    async def fantasy_update_db(self, ctx: SlashContext):
        if self.sync_running:
            return await ctx.send(
                "Une synchronisation Fantasy est déjà en cours.", ephemeral=True
            )

        await ctx.defer(ephemeral=True)
        self.sync_running = True
        try:
            provider = LeaguepediaPlayerProvider()
            result = await sync_player_pool(provider)
        except (LeaguepediaProviderError, FantasySyncError) as exc:
            return await ctx.send(f"❌ Synchronisation annulée : {exc}", ephemeral=True)
        except Exception as exc:
            return await ctx.send(
                f"❌ Erreur inattendue pendant la synchronisation : `{type(exc).__name__}`.",
                ephemeral=True,
            )
        finally:
            self.sync_running = False

        await ctx.send(
            "✅ **Base Fantasy mise à jour depuis Leaguepedia**\n"
            f"• équipes trouvées : **{result.teams_seen}**\n"
            f"• joueurs trouvés : **{result.players_seen}**\n"
            f"• nouvelles affectations joueur→équipe : **{result.histories_opened}**\n"
            f"• anciennes affectations clôturées : **{result.histories_closed}**\n"
            f"• équipes désactivées : **{result.teams_deactivated}**\n"
            f"• joueurs désactivés : **{result.players_deactivated}**",
            ephemeral=True,
        )


def setup(bot):
    FantasyAdmin(bot)
