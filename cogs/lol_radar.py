"""Radar historique par compte suivi, calculé à partir des seules données locales."""
import asyncio
import logging
from io import BytesIO

import interactions
from interactions import Extension, SlashCommandOption, SlashCommandChoice, slash_command

from fonctions.autocomplete import autocomplete_riotid
from fonctions.lol_radar import MODES, load_radar, render_radar

log = logging.getLogger(__name__)


def build_radar(riot_id, riot_tag, guild_id, parties, mode, role, champion, saison):
    data = load_radar(riot_id, riot_tag, guild_id, parties, mode, role, champion, saison)
    if not data["games"]:
        return None
    title = f"{riot_id}#{riot_tag.strip().lstrip('#').upper()}"
    subtitle = " • ".join(str(v) for v in (mode, role or "Tous rôles", champion,
                                            f"Saison {saison}" if saison else "Toutes saisons") if v)
    return render_radar(data, title, subtitle)


class LolRadar(Extension):
    @slash_command(
        name="lol_radar", description="Radar des statistiques d'un compte LoL suivi",
        options=[
            SlashCommandOption(name="riot_id", description="Pseudo LoL du compte suivi",
                               type=interactions.OptionType.STRING, required=True, autocomplete=True),
            SlashCommandOption(name="riot_tag", description="Tag Riot du compte",
                               type=interactions.OptionType.STRING, required=True),
            SlashCommandOption(name="parties", description="Dernières parties comparées aux précédentes (20 par défaut)",
                               type=interactions.OptionType.INTEGER, required=False, min_value=1, max_value=100),
            SlashCommandOption(name="mode", description="File de jeu (RANKED par défaut)",
                               type=interactions.OptionType.STRING, required=False,
                               choices=[SlashCommandChoice(name=m, value=m) for m in MODES]),
            SlashCommandOption(name="role", description="Filtrer un rôle pour une comparaison plus homogène",
                               type=interactions.OptionType.STRING, required=False,
                               choices=[SlashCommandChoice(name=r, value=r) for r in ("TOP", "JUNGLE", "MID", "ADC", "SUPPORT")]),
            SlashCommandOption(name="champion", description="Filtrer un champion",
                               type=interactions.OptionType.STRING, required=False),
            SlashCommandOption(name="saison", description="Filtrer une saison, sinon tout l'historique enregistré",
                               type=interactions.OptionType.INTEGER, required=False, min_value=1),
        ],
    )
    async def lol_radar(self, ctx, riot_id: str, riot_tag: str, parties: int = 20,
                        mode: str = "RANKED", role: str = None, champion: str = None, saison: int = None):
        await ctx.defer(ephemeral=False)
        if not ctx.guild_id:
            await ctx.send("Utilise cette commande sur le serveur où le compte est suivi.")
            return
        try:
            png = await asyncio.to_thread(build_radar, riot_id, riot_tag, int(ctx.guild_id),
                                          parties, mode, role, champion, saison)
        except ValueError as exc:
            await ctx.send(str(exc))
            return
        except Exception:
            log.exception("Impossible de générer le radar LoL")
            await ctx.send("Le radar est temporairement indisponible. Consulte les journaux du bot.")
            return
        if png is None:
            await ctx.send("Aucune partie enregistrée pour ce compte sur ce serveur avec ces filtres.")
            return
        await ctx.send(file=interactions.File(BytesIO(png), file_name="lol-radar.png"))

    @lol_radar.autocomplete("riot_id")
    async def autocomplete_radar(self, ctx):
        choices = await autocomplete_riotid(int(ctx.guild_id), ctx.input_text) if ctx.guild_id else []
        await ctx.send(choices=choices)
