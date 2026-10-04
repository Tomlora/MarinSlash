"""Vues persistantes Teamfight / Ganks et compatibilité des anciens boutons."""
import asyncio
import logging
import re
from io import BytesIO

import interactions
from interactions import Extension, component_callback

from fonctions.match.match_views import (
    load_analysis, load_progress, build_analysis_pages, build_progress_pages,
    load_teamfights, load_ganks, build_teamfight_pages, build_gank_pages,
)

from fonctions.match.recap_details import load_score, build_score_pages, gold_response
from fonctions.match.player_profiles import load_players, build_player_pages

log = logging.getLogger(__name__)
OPEN_RE = re.compile(r"^lolview_open_(teamfight|ganks|score|gold|analysis|progress|players)_([A-Z0-9]+_[0-9]+)_([0-9]+)$")
PAGE_RE = re.compile(
    r"^lolview_page_(teamfight|ganks|score|gold|analysis|progress|players)_([A-Z0-9]+_[0-9]+)_([0-9]+)_([0-9]+)_(?:prev|next)$"
)
LOAD_TIMEOUT = 8
GOLD_MODE_RE = re.compile(r"^lolgold_(relative|total)_([A-Z0-9]+_[0-9]+)_([0-9]+)$")


def page_components(kind, match_id, joueur, index, total):
    token = f"{kind}_{match_id}_{joueur}"
    return [interactions.ActionRow(
        interactions.Button(
            style=interactions.ButtonStyle.SECONDARY, label="◀ Précédent",
            custom_id=f"lolview_page_{token}_{max(0, index - 1)}_prev", disabled=index == 0,
        ),
        interactions.Button(
            style=interactions.ButtonStyle.PRIMARY, label="Suivant ▶",
            custom_id=f"lolview_page_{token}_{min(total - 1, index + 1)}_next", disabled=index >= total - 1,
        ),
        interactions.Button(
            style=interactions.ButtonStyle.DANGER, label="Fermer", custom_id="lolview_close",
        ),
    )]


def load_pages(kind, match_id, joueur):
    loaders = {
        "players": (load_players, build_player_pages),
        "score": (load_score, build_score_pages),
        "teamfight": (load_teamfights, build_teamfight_pages),
        "ganks": (load_ganks, build_gank_pages),
        "analysis": (load_analysis, build_analysis_pages),
        "progress": (load_progress, build_progress_pages),
    }
    loader, builder = loaders[kind]
    data = loader(match_id, joueur)
    return None if data is None else builder(*data)


class LolMatchViews(Extension):
    def __init__(self, bot):
        self.bot = bot

    async def _show(self, ctx, kind, match_id, joueur, target=0, edit=False, gold_mode="relative"):
        # L'ACK précède toute requête SQL. Le message public n'est jamais modifié.
        if edit:
            await ctx.defer(edit_origin=True)
        else:
            await ctx.defer(ephemeral=True)

        async def reply(**kwargs):
            if edit:
                if kind == "gold":
                    return await ctx.edit(attachments=[], **kwargs)
                return await ctx.edit_origin(**kwargs)
            return await ctx.send(**kwargs, ephemeral=True)

        try:
            if kind == "gold":
                index = max(0, min(int(target), 2))
                data = await asyncio.wait_for(
                    asyncio.to_thread(gold_response, match_id, int(joueur), index, gold_mode), timeout=LOAD_TIMEOUT,
                )
                if data is None:
                    return await reply(content="Les données sauvegardées de cette partie ne sont plus disponibles.",
                                       embeds=[], components=[])
                embed, png = data
                filename = ("gold_diff.png", "gold_roles.png", "gold_players.png")[index]
                kwargs = {"file": interactions.File(BytesIO(png), file_name=filename)} if png else {}
                controls = page_components(kind, match_id, joueur, index, 3)
                if index == 2:
                    controls.append(interactions.ActionRow(*[
                        interactions.Button(style=interactions.ButtonStyle.PRIMARY if mode == gold_mode else interactions.ButtonStyle.SECONDARY,
                                            label=label, custom_id=f"lolgold_{mode}_{match_id}_{joueur}", disabled=mode == gold_mode)
                        for mode, label in (("relative", "Écart au joueur suivi"), ("total", "Or total"))
                    ]))
                return await reply(content="", embeds=embed,
                                   components=controls, **kwargs)
            pages = await asyncio.wait_for(
                asyncio.to_thread(load_pages, kind, match_id, int(joueur)), timeout=LOAD_TIMEOUT,
            )
            if not pages:
                return await reply(
                    content="Les données sauvegardées de cette partie ne sont plus disponibles.",
                    embeds=[], components=[],
                )
            index = max(0, min(int(target), len(pages) - 1))
            await reply(
                content="", embeds=pages[index],
                components=page_components(kind, match_id, joueur, index, len(pages)),
            )
        except asyncio.TimeoutError:
            await reply(
                content="La lecture prend trop de temps. Rouvre le bouton dans quelques instants.",
                embeds=[], components=[],
            )
        except Exception:
            log.exception("Consultation %s impossible pour %s / %s", kind, match_id, joueur)
            await reply(
                content="Impossible de charger ces données. Réessaie plus tard.",
                embeds=[], components=[],
            )

    @component_callback(OPEN_RE)
    async def on_open(self, ctx):
        match = OPEN_RE.fullmatch(ctx.custom_id)
        if match:
            await self._show(ctx, *match.groups())

    @component_callback(PAGE_RE)
    async def on_page(self, ctx):
        match = PAGE_RE.fullmatch(ctx.custom_id)
        if match:
            await self._show(ctx, *match.groups(), edit=True)

    @component_callback("lolview_close")
    async def on_close(self, ctx):
        await ctx.defer(edit_origin=True)
        await ctx.edit(content="Consultation terminée.", embeds=[], components=[], attachments=[])

    @component_callback(GOLD_MODE_RE)
    async def on_gold_mode(self, ctx):
        match = GOLD_MODE_RE.fullmatch(ctx.custom_id)
        if match:
            mode, match_id, joueur = match.groups()
            await self._show(ctx, "gold", match_id, joueur, target=2, edit=True, gold_mode=mode)


def setup(bot):
    LolMatchViews(bot)
