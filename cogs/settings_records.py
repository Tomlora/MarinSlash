"""Réglages de records accessibles à chaque utilisateur, sans droit administrateur."""
import asyncio
import logging

import interactions
from interactions import Extension, SlashContext, SlashCommandOption, SlashCommandChoice, slash_command
from fonctions.match.records_preferences import load_preferences, save_preferences

log = logging.getLogger(__name__)


def settings_embed(preferences):
    names = {"alltime": "All-Time", "general": "Saison", "perso": "Personnel"}
    embed = interactions.Embed(
        title="Mes préférences de records",
        description=(
            "Ces réglages s'appliquent aux nouveaux récaps de tes comptes suivis "
            "et aux détails privés que tu consultes.\n"
            "Les anciens messages publics restent inchangés. Les records enregistrés sont conservés."
        ),
        color=0x5865F2,
    )
    embed.add_field(name="Présentation", value=(
        "Compacte par statistique" if preferences.layout == "compact"
        else "Sections All-Time / Saison / Personnel"
    ), inline=False)
    embed.add_field(name="Catégories affichées", value=(
        " · ".join(names[s] for s in preferences.scopes) or "Aucune — records masqués"
    ), inline=False)
    embed.set_footer(text="Sans options : voir mes réglages · Options omises : inchangées")
    return embed


class SettingsRecords(Extension):
    def __init__(self, bot):
        self.bot = bot

    @slash_command(
        name="settings_records",
        description="Choisir ma présentation des records et les catégories affichées",
        options=[
            SlashCommandOption(
                name="format", description="Présentation du récap", type=interactions.OptionType.STRING,
                required=False, choices=[
                    SlashCommandChoice(name="Compact par statistique (défaut)", value="compact"),
                    SlashCommandChoice(name="Sections par catégorie", value="sections"),
                ],
            ),
            *[SlashCommandOption(
                name=name, description=f"Afficher les records {label}",
                type=interactions.OptionType.BOOLEAN, required=False,
            ) for name, label in (("alltime", "All-Time"), ("saison", "de saison"), ("perso", "personnels"))],
        ],
    )
    async def settings_records(self, ctx: SlashContext, format=None, alltime=None, saison=None, perso=None):
        await ctx.defer(ephemeral=True)
        try:
            # Aucune option de destinataire : chacun ne peut modifier que ses choix.
            if any(value is not None for value in (format, alltime, saison, perso)):
                await asyncio.wait_for(
                    asyncio.to_thread(save_preferences, int(ctx.author.id), format, alltime, saison, perso),
                    timeout=8,
                )
            preferences = await asyncio.wait_for(
                asyncio.to_thread(load_preferences, int(ctx.author.id), strict=True), timeout=8,
            )
            await ctx.send(embeds=settings_embed(preferences), ephemeral=True)
        except asyncio.TimeoutError:
            await ctx.send(
                "La base met trop de temps à répondre. Vérifie tes réglages avec /settings_records avant de réessayer.",
                ephemeral=True,
            )
        except Exception:
            log.exception("Enregistrement des préférences de records impossible")
            await ctx.send("Impossible d'enregistrer tes réglages. Réessaie plus tard.", ephemeral=True)


def setup(bot):
    SettingsRecords(bot)
