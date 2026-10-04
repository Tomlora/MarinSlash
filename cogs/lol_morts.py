"""Listing des morts à partir de la timeline déjà enregistrée par le bot."""

import asyncio
import json

import interactions
import pandas as pd
from interactions import Extension, SlashCommandOption, SlashContext, slash_command
from interactions.ext.paginators import Paginator

from fonctions.autocomplete import autocomplete_riotid
from fonctions.gestion_bdd import lire_bdd_perso


def load_deaths(match_id, riot_id, riot_tag):
    events = lire_bdd_perso(
        '''SELECT e.type, e.timestamp, e."killerId", e."victimId",
                  e."assistingParticipantIds"
           FROM data_timeline_events e
           WHERE e.match_id = :match_id AND e.riot_id IN (
               SELECT id_compte FROM tracker
               WHERE riot_id = :riot_id AND riot_tagline = :riot_tag
           )
           ORDER BY e.timestamp''',
        index_col=None,
        params={"match_id": match_id, "riot_id": riot_id, "riot_tag": riot_tag},
    ).T
    if events.empty:
        return None
    # Les morts sont déjà renommées DEATHS par TimelineMixin.
    # Les anciens imports peuvent contenir plusieurs copies du même événement.
    return events.loc[events["type"] == "DEATHS"].drop_duplicates(
        subset=["timestamp", "killerId", "victimId"]
    ).sort_values("timestamp")


def solokill_label(death):
    killer = death["killerId"]
    if pd.isna(killer):
        return "Indéterminé"
    if int(killer) == 0:  # Exécution par une tour, un sbire ou un monstre.
        return "Non"
    assists = death["assistingParticipantIds"]
    if isinstance(assists, str):
        try:
            assists = json.loads(assists)
        except (TypeError, ValueError):
            return "Indéterminé"
    # Comme dans TimelineMixin : une liste absente signifie aucune assistance.
    if assists is None or (not isinstance(assists, list) and pd.isna(assists)):
        assists = []
    if not isinstance(assists, list):
        return "Indéterminé"
    return "Non" if assists else "Oui"


def death_pages(deaths):
    pages = []
    for number, (_, death) in enumerate(deaths.iterrows(), start=1):
        # La BDD contient déjà du mm.ss (fix_temps appliqué à l'enregistrement).
        # Une seconde conversion donnerait un timing incorrect.
        timing = f"{float(death['timestamp']):.2f}".replace(".", ":")
        pages.append(interactions.Embed(
            title=f"Mort {number}/{len(deaths)}",
            description=f"**Timing :** {timing}\n**Solokill :** {solokill_label(death)}",
        ))
    return pages


class LolMorts(Extension):
    def __init__(self, bot):
        self.bot = bot

    @slash_command(
        name="lol_morts",
        description="Affiche chaque mort d'un joueur dans un match enregistré",
        options=[
            SlashCommandOption(name="match_id", description="ID du match (EUW1_1234567890 ou numéro seul)",
                               type=interactions.OptionType.STRING, required=True),
            SlashCommandOption(name="riot_id", description="Pseudo LoL du joueur",
                               type=interactions.OptionType.STRING, required=True, autocomplete=True),
            SlashCommandOption(name="riot_tag", description="Tag Riot du joueur",
                               type=interactions.OptionType.STRING, required=True),
        ],
    )
    async def lol_morts(self, ctx: SlashContext, match_id: str, riot_id: str, riot_tag: str):
        await ctx.defer(ephemeral=False)
        match_id = match_id.strip().upper().replace("EUW1-", "EUW1_", 1)
        if match_id.isdigit():
            match_id = f"EUW1_{match_id}"
        riot_id = riot_id.lower().replace(" ", "")
        riot_tag = riot_tag.strip().lstrip("#").upper()
        deaths = await asyncio.to_thread(load_deaths, match_id, riot_id, riot_tag)
        if deaths is None:
            await ctx.send("Aucune timeline enregistrée pour ce joueur et ce match.")
            return
        if deaths.empty:
            await ctx.send("Aucune mort enregistrée pour ce joueur dans ce match.")
            return

        paginator = Paginator.create_from_embeds(self.bot, *death_pages(deaths))
        await paginator.send(ctx)

    @lol_morts.autocomplete("riot_id")
    async def autocomplete_morts(self, ctx):
        await ctx.send(choices=await autocomplete_riotid(int(ctx.guild_id), ctx.input_text))
