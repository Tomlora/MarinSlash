"""Derniers correctifs d'alignement du récapitulatif LoL moderne."""

from __future__ import annotations

from typing import Any, Mapping

from PIL import Image, ImageDraw

from . import image_modern_renderer as _renderer
from . import image_modern_renderer_polish as _polish
from .image_modern_common import (
    MARGIN,
    PALETTE,
    WIDTH,
    _as_int,
    _draw_text,
    _font,
    _format_duration,
    _paste_with_alpha,
    _rounded_panel,
)


_ORIGINAL_DRAW_TEAM_PANEL = _renderer._draw_team_panel


def _draw_match_summary(
    canvas: Image.Image,
    draw: ImageDraw.ImageDraw,
    match: Any,
    assets: Mapping[str, Image.Image],
    objectives,
) -> None:
    """Dessine le résumé avec toutes les métriques sur une même grille."""
    box = (MARGIN, 166, WIDTH - MARGIN, 264)
    _rounded_panel(canvas, box, fill=PALETTE.panel)

    victory = bool(getattr(match, "thisWinBool", False))
    result_color = PALETTE.positive if victory else PALETTE.enemy
    result_label = "VICTOIRE" if victory else "DÉFAITE"

    draw.ellipse(
        (47, 184, 105, 242),
        fill=result_color + (28,),
        outline=result_color + (220,),
        width=2,
    )
    if victory:
        draw.line((60, 211, 73, 224), fill=result_color, width=5)
        draw.line((73, 224, 94, 198), fill=result_color, width=5)
    else:
        draw.line((62, 224, 91, 195), fill=result_color, width=5)
        draw.line((64, 195, 91, 223), fill=result_color, width=5)

    _draw_text(draw, (123, 185), result_label, _font(27), result_color)
    _draw_text(draw, (123, 220), "Équipe alliée", _font(17), PALETTE.muted)

    # Toutes les métriques partagent désormais exactement les mêmes ordonnées.
    value_y = 196
    label_y = 229
    summary_stats = [
        ("Durée", _format_duration(getattr(match, "thisTime", 0)), 350),
        ("Kills", _as_int(getattr(match, "thisTeamKills", 0)), 500),
        ("Morts", _as_int(getattr(match, "thisTeamKillsOp", 0)), 640),
    ]
    for label, value, center_x in summary_stats:
        _draw_text(draw, (center_x, value_y), value, _font(27), PALETTE.text, anchor="mm")
        _draw_text(draw, (center_x, label_y), label, _font(15), PALETTE.muted, anchor="mm")

    draw.line((710, 183, 710, 246), fill=PALETTE.divider, width=1)

    objective_order = [
        ("obj_tower", "tower", "Tours"),
        ("obj_inhibitor", "inhibitor", "Inhibs"),
        ("obj_dragon", "dragon", "Dragons"),
        ("obj_herald", "riftHerald", "Herald"),
        ("obj_baron", "baron", "Barons"),
        ("obj_horde", "horde", "Voidgrubs"),
        ("obj_elder", "elder", "Elders"),
    ]
    start_x = 746
    cell_width = 164
    for pos, (asset_key, stat_key, label) in enumerate(objective_order):
        x = start_x + pos * cell_width
        icon = assets.get(asset_key)
        if icon is not None:
            _paste_with_alpha(canvas, icon, (x, 184))
        _draw_text(draw, (x + 53, value_y), objectives.get(stat_key, 0), _font(24), PALETTE.text)
        _draw_text(draw, (x + 53, label_y), label, _font(14), PALETTE.muted)


def _draw_team_panel(
    canvas: Image.Image,
    draw: ImageDraw.ImageDraw,
    match: Any,
    assets: Mapping[str, Image.Image],
    *,
    start_index: int,
    y: int,
    ally: bool,
) -> None:
    """Nettoie l'en-tête et n'affiche que la valeur du rang moyen."""
    _ORIGINAL_DRAW_TEAM_PANEL(
        canvas,
        draw,
        match,
        assets,
        start_index=start_index,
        y=y,
        ally=ally,
    )

    accent = PALETTE.ally if ally else PALETTE.enemy
    header_fill = (19, 58, 99, 255) if ally else (86, 27, 43, 255)

    # Recouvre la zone gauche de l'en-tête pour supprimer l'ancien OR et le
    # libellé "RANG MOYEN", puis redessine les informations sans chevauchement.
    draw.rectangle((25, y + 1, 515, y + 44), fill=header_fill)

    team_name = "ÉQUIPE ALLIÉE" if ally else "ÉQUIPE ADVERSE"
    _draw_text(draw, (43, y + 12), team_name, _font(20), accent)

    # Le repère de l'écart d'or est placé après le nom d'équipe.
    _draw_text(draw, (205, y + 14), "Δ OR", _font(12), PALETTE.muted, anchor="ma")

    rank_tier, rank_division = _polish._team_average_rank(match, start_index, ally)
    rank_text = _polish._format_average_rank(rank_tier, rank_division)
    rank_icon = assets.get(f"tier_name_{rank_tier}") if rank_tier else None

    text_x = 250
    if rank_icon is not None:
        icon = rank_icon.resize((28, 28))
        _paste_with_alpha(canvas, icon, (230, y + 8))
        text_x = 266

    _draw_text(draw, (text_x, y + 23), rank_text, _font(15), PALETTE.text, anchor="lm")


_renderer._draw_match_summary = _draw_match_summary
_renderer._draw_team_panel = _draw_team_panel

build_modern_recap = _renderer.build_modern_recap

__all__ = ["build_modern_recap"]
