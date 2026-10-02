"""Carte privée et persistante du récap ; chaque message porte ses filtres."""
import asyncio
import logging
import re
from io import BytesIO

import interactions
from interactions import Extension, component_callback
from fonctions.match.map_view import ALL_PLAYERS, map_response

log = logging.getLogger(__name__)
OPEN_RE = re.compile(r"^lolview_open_map_([A-Z0-9]+_[0-9]+)_([0-9]+)$")
ACTION_RE = re.compile(
    r"^lolmap_(mode|players|all|blue|red|prev|next|close)_([A-Z0-9]+_[0-9]+)_([0-9]+)_(deaths|moves)_([0-9]+)_([0-9]+)$"
)
LOAD_TIMEOUT = 15


class LolMatchMap(Extension):
    def __init__(self, bot):
        self.bot = bot
        # Au plus un rendu en cours, y compris après le timeout d'une interaction.
        self._render_task = None

    async def _show(self, ctx, match_id, joueur, mode="deaths", page=0, mask=ALL_PLAYERS, edit=False):
        if edit:
            await ctx.defer(edit_origin=True)
        else:
            await ctx.defer(ephemeral=True)

        async def reply(**kwargs):
            if edit:
                # interactions.py 5.13.2 : attachments est accepté par edit, pas edit_origin.
                return await ctx.edit(attachments=[], **kwargs)
            return await ctx.send(ephemeral=True, **kwargs)

        if self._render_task is not None and not self._render_task.done():
            # Conserver les contrôles du message pour que l'utilisateur puisse réessayer.
            return await ctx.send(content="Une carte est en cours de préparation. Réessaie dans quelques secondes.", ephemeral=True)
        task = asyncio.create_task(asyncio.to_thread(map_response, match_id, int(joueur), mode, int(page), int(mask)))
        self._render_task = task

        def finished(done):
            # Récupérer aussi les exceptions d'un thread terminé après le timeout.
            if not done.cancelled():
                done.exception()

        task.add_done_callback(finished)
        try:
            response = await asyncio.wait_for(asyncio.shield(task), timeout=LOAD_TIMEOUT)
            if response is None:
                return await reply(content="La carte des dix joueurs n'est pas enregistrée pour cette partie. "
                                   "Elle est disponible pour les nouveaux récaps sauvegardés sur la Faille de l'invocateur, avec une timeline exploitable.",
                                   embeds=[], components=[])
            embed, png, controls = response
            return await reply(content="", embeds=embed, components=controls,
                               file=interactions.File(BytesIO(png), file_name="match_map.png"))
        except asyncio.TimeoutError:
            await ctx.send(content="La préparation de la carte prend trop de temps. Réessaie dans quelques instants.", ephemeral=True)
        except Exception:
            log.exception("Carte impossible pour %s / %s", match_id, joueur)
            await ctx.send(content="Impossible de préparer la carte. Réessaie plus tard.", ephemeral=True)

    @component_callback(OPEN_RE)
    async def on_open(self, ctx):
        found = OPEN_RE.fullmatch(ctx.custom_id)
        if found:
            await self._show(ctx, *found.groups())

    @component_callback(ACTION_RE)
    async def on_action(self, ctx):
        found = ACTION_RE.fullmatch(ctx.custom_id)
        if not found:
            return
        action, match_id, joueur, mode, page, mask = found.groups()
        if action == "close":
            await ctx.defer(edit_origin=True)
            return await ctx.edit(content="Consultation terminée.", embeds=[], components=[], attachments=[])
        if action == "players":
            try:
                ids = {int(value) for value in ctx.values}
                if not ids or not ids.issubset(set(range(1, 11))):
                    raise ValueError("Sélection invalide")
                mask = sum(1 << (pid - 1) for pid in ids)
            except (TypeError, ValueError):
                return await ctx.send(content="Sélectionne entre un et dix joueurs.", ephemeral=True)
        await self._show(ctx, match_id, joueur, mode, int(page), int(mask), edit=True)


def setup(bot):
    LolMatchMap(bot)
