import interactions
from interactions import Extension, SlashContext, slash_command

from fonctions.fantasy.database import active_competitions, schema_is_ready


class FantasyLoL(Extension):
    def __init__(self, bot):
        self.bot: interactions.Client = bot

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
            return await ctx.send(
                f"Fantasy LoL n'est pas prêt : `{type(exc).__name__}`.",
                ephemeral=True,
            )

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


def setup(bot):
    FantasyLoL(bot)
