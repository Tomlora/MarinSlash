"""Derniers correctifs d'alignement du récapitulatif LoL moderne."""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Mapping

from PIL import Image, ImageDraw

from . import image_modern_renderer as _renderer
from . import image_modern_renderer_polish as _polish
from .image_modern_common import (
    MARGIN,
    PALETTE,
    WIDTH,
    _as_float,
    _as_int,
    _draw_text,
    _fit_text,
    _font,
    _format_compact,
    _format_duration,
    _metric_color,
    _paste_with_alpha,
    _rounded_panel,
    _safe_get,
)
from .image_modern_data import _get_player_local_index, _team_dragon_types


_ORIGINAL_DRAW_HEADER = _renderer._draw_header
_ORIGINAL_DRAW_TEAM_PANEL = _renderer._draw_team_panel

_DRAGON_BADGE_COLORS = {
    "fire": ((66, 23, 18, 245), (241, 111, 57, 255)),
    "water": ((8, 43, 55, 245), (68, 211, 224, 255)),
    "earth": ((49, 39, 21, 245), (210, 170, 78, 255)),
    "air": ((16, 39, 60, 245), (121, 197, 247, 255)),
    "hextech": ((26, 26, 64, 245), (105, 178, 255, 255)),
    "chemtech": ((20, 51, 32, 245), (104, 218, 116, 255)),
}


@lru_cache(maxsize=12)
def _dragon_badge(dragon_type: str, size: int = 18) -> Image.Image:
    """Construit une petite icône vectorielle lisible sans asset externe."""
    scale = 4
    high_size = size * scale
    badge = Image.new("RGBA", (high_size, high_size), (0, 0, 0, 0))
    badge_draw = ImageDraw.Draw(badge)

    background, accent = _DRAGON_BADGE_COLORS.get(
        dragon_type,
        ((26, 39, 55, 245), (168, 184, 203, 255)),
    )
    pad = scale
    badge_draw.ellipse(
        (pad, pad, high_size - pad - 1, high_size - pad - 1),
        fill=background,
        outline=accent,
        width=scale,
    )

    cx = high_size / 2
    cy = high_size / 2
    unit = high_size / 18

    if dragon_type == "fire":
        badge_draw.polygon(
            [
                (cx, cy + 5.5 * unit),
                (cx - 4.2 * unit, cy + 1.8 * unit),
                (cx - 1.8 * unit, cy - 2.2 * unit),
                (cx - 0.7 * unit, cy - 6.0 * unit),
                (cx + 2.2 * unit, cy - 2.8 * unit),
                (cx + 4.0 * unit, cy + 1.0 * unit),
            ],
            fill=accent,
        )
        badge_draw.polygon(
            [
                (cx, cy + 4.0 * unit),
                (cx - 1.8 * unit, cy + 0.9 * unit),
                (cx + 0.7 * unit, cy - 2.3 * unit),
                (cx + 2.0 * unit, cy + 1.7 * unit),
            ],
            fill=(255, 226, 148, 255),
        )
    elif dragon_type == "water":
        for offset in (-2.2, 1.3):
            y = cy + offset * unit
            badge_draw.arc(
                (
                    cx - 6.0 * unit,
                    y - 2.3 * unit,
                    cx + 1.5 * unit,
                    y + 2.3 * unit,
                ),
                start=195,
                end=355,
                fill=accent,
                width=scale,
            )
            badge_draw.arc(
                (
                    cx - 1.5 * unit,
                    y - 2.3 * unit,
                    cx + 6.0 * unit,
                    y + 2.3 * unit,
                ),
                start=15,
                end=175,
                fill=accent,
                width=scale,
            )
    elif dragon_type == "earth":
        badge_draw.polygon(
            [
                (cx - 5.8 * unit, cy + 4.8 * unit),
                (cx, cy - 5.8 * unit),
                (cx + 5.8 * unit, cy + 4.8 * unit),
            ],
            fill=accent,
        )
        badge_draw.polygon(
            [
                (cx - 2.0 * unit, cy - 2.0 * unit),
                (cx, cy - 5.8 * unit),
                (cx + 2.2 * unit, cy - 1.8 * unit),
                (cx + 0.4 * unit, cy - 2.4 * unit),
            ],
            fill=(247, 232, 189, 255),
        )
    elif dragon_type == "air":
        badge_draw.arc(
            (
                cx - 6.2 * unit,
                cy - 5.2 * unit,
                cx + 4.0 * unit,
                cy + 2.2 * unit,
            ),
            start=205,
            end=355,
            fill=accent,
            width=scale,
        )
        badge_draw.arc(
            (
                cx - 3.7 * unit,
                cy - 0.5 * unit,
                cx + 5.5 * unit,
                cy + 5.2 * unit,
            ),
            start=20,
            end=175,
            fill=accent,
            width=scale,
        )
        badge_draw.line(
            (cx - 5.5 * unit, cy + 2.0 * unit, cx + 2.8 * unit, cy + 2.0 * unit),
            fill=accent,
            width=scale,
        )
    elif dragon_type == "hextech":
        badge_draw.polygon(
            [
                (cx + 0.5 * unit, cy - 6.0 * unit),
                (cx - 4.2 * unit, cy + 0.7 * unit),
                (cx - 0.8 * unit, cy + 0.7 * unit),
                (cx - 2.0 * unit, cy + 6.0 * unit),
                (cx + 4.5 * unit, cy - 1.3 * unit),
                (cx + 1.0 * unit, cy - 1.3 * unit),
            ],
            fill=accent,
        )
    elif dragon_type == "chemtech":
        badge_draw.line(
            (
                cx - 2.4 * unit,
                cy - 5.0 * unit,
                cx + 2.4 * unit,
                cy - 5.0 * unit,
            ),
            fill=accent,
            width=scale,
        )
        badge_draw.line(
            (
                cx - 1.4 * unit,
                cy - 5.0 * unit,
                cx - 1.4 * unit,
                cy - 1.5 * unit,
                cx - 4.5 * unit,
                cy + 4.8 * unit,
                cx + 4.5 * unit,
                cy + 4.8 * unit,
                cx + 1.4 * unit,
                cy - 1.5 * unit,
                cx + 1.4 * unit,
                cy - 5.0 * unit,
            ),
            fill=accent,
            width=scale,
            joint="curve",
        )
        badge_draw.polygon(
            [
                (cx - 3.5 * unit, cy + 1.6 * unit),
                (cx + 3.5 * unit, cy + 1.6 * unit),
                (cx + 4.5 * unit, cy + 4.8 * unit),
                (cx - 4.5 * unit, cy + 4.8 * unit),
            ],
            fill=accent,
        )
        badge_draw.ellipse(
            (
                cx + 1.7 * unit,
                cy - 0.8 * unit,
                cx + 3.3 * unit,
                cy + 0.8 * unit,
            ),
            fill=(204, 255, 194, 255),
        )

    return badge.resize((size, size), Image.Resampling.LANCZOS)


def _draw_header(
    canvas: Image.Image,
    draw: ImageDraw.ImageDraw,
    match: Any,
    assets: Mapping[str, Image.Image],
    profile_summary: Mapping[str, Any],
    daily_stats,
    dif_lp: Any,
) -> None:
    """Complète le bloc 24 h avec le bilan net de LP."""
    _ORIGINAL_DRAW_HEADER(canvas, draw, match, assets, profile_summary, daily_stats, dif_lp)

    lp_24h = _as_int(daily_stats[2] if len(daily_stats) > 2 else 0)
    lp_color = PALETTE.positive if lp_24h > 0 else PALETTE.negative if lp_24h < 0 else PALETTE.muted
    lp_text = f"{lp_24h:+d} LP" if lp_24h else "0 LP"

    card = (1562, 55, 1678, 121)
    draw.rounded_rectangle(
        card,
        radius=11,
        fill=(5, 18, 34, 190),
        outline=PALETTE.border,
        width=1,
    )
    _draw_text(draw, ((card[0] + card[2]) // 2, 72), "LP 24h", _font(14), PALETTE.muted, anchor="mm")
    _draw_text(draw, ((card[0] + card[2]) // 2, 100), lp_text, _font(21), lp_color, anchor="mm")


def _draw_match_summary(
    canvas: Image.Image,
    draw: ImageDraw.ImageDraw,
    match: Any,
    assets: Mapping[str, Image.Image],
    objectives,
) -> None:
    """Dessine le résumé avec une grille visuelle homogène."""
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

    # L'ancrage centré des trois métriques les fait paraître plus hautes que les
    # objectifs : elles sont volontairement descendues de quelques pixels.
    summary_value_y = 204
    summary_label_y = 237
    summary_stats = [
        ("Durée", _format_duration(getattr(match, "thisTime", 0)), 350),
        ("Kills", _as_int(getattr(match, "thisTeamKills", 0)), 500),
        ("Morts", _as_int(getattr(match, "thisTeamKillsOp", 0)), 640),
    ]
    for label, value, center_x in summary_stats:
        _draw_text(draw, (center_x, summary_value_y), value, _font(27), PALETTE.text, anchor="mm")
        _draw_text(draw, (center_x, summary_label_y), label, _font(15), PALETTE.muted, anchor="mm")

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
    objective_value_y = 196
    objective_label_y = 229
    start_x = 746
    cell_width = 164
    for pos, (asset_key, stat_key, label) in enumerate(objective_order):
        x = start_x + pos * cell_width
        icon = assets.get(asset_key)
        if icon is not None:
            _paste_with_alpha(canvas, icon, (x, 184))
        _draw_text(draw, (x + 53, objective_value_y), objectives.get(stat_key, 0), _font(24), PALETTE.text)
        _draw_text(draw, (x + 53, objective_label_y), label, _font(14), PALETTE.muted)

    dragon_types = _team_dragon_types(match)[:4]
    if dragon_types:
        badge_size = 18
        badge_gap = 3
        dragon_center_x = start_x + 2 * cell_width + 53
        total_width = len(dragon_types) * badge_size + (len(dragon_types) - 1) * badge_gap
        first_x = round(dragon_center_x - total_width / 2)
        badge_y = 244
        for index, dragon_type in enumerate(dragon_types):
            badge_x = first_x + index * (badge_size + badge_gap)
            _paste_with_alpha(canvas, _dragon_badge(dragon_type, badge_size), (badge_x, badge_y))


def _row_fill(ally: bool, row: int, is_player: bool):
    if is_player:
        return (17, 72, 119, 255)
    if row % 2 == 1:
        return (12, 38, 67, 255) if ally else (53, 20, 32, 255)
    return (7, 30, 57, 255) if ally else (45, 15, 28, 255)


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
    """Ajuste l'en-tête, l'écart d'or adverse et la colonne de tanking."""
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
    header_h = 45
    row_h = 52
    player_index = _get_player_local_index(match)
    team_indices = list(range(start_index, min(start_index + 5, getattr(match, "nb_joueur", 10))))

    # Le fond est redessiné dans une forme arrondie, en laissant le contour du
    # panneau visible : aucun pixel ne dépasse plus dans le coin supérieur gauche.
    header_overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    header_draw = ImageDraw.Draw(header_overlay)
    header_draw.rounded_rectangle((25, y + 1, 515, y + 44), radius=14, fill=header_fill)
    header_draw.rectangle((25, y + 15, 515, y + 44), fill=header_fill)
    canvas.alpha_composite(header_overlay)

    team_name = "ÉQUIPE ALLIÉE" if ally else "ÉQUIPE ADVERSE"
    _draw_text(draw, (43, y + 12), team_name, _font(20), accent)

    rank_tier, rank_division = _polish._team_average_rank(match, start_index, ally)
    rank_text = _polish._format_average_rank(rank_tier, rank_division)
    rank_icon = assets.get(f"tier_name_{rank_tier}") if rank_tier else None

    text_x = 272
    if rank_icon is not None:
        icon = rank_icon.resize((28, 28))
        _paste_with_alpha(canvas, icon, (236, y + 8))
    _draw_text(draw, (text_x, y + 23), rank_text, _font(15), PALETTE.text, anchor="lm")

    # Déplace la colonne TANK vers la gauche et explicite la valeur entre
    # parenthèses : total absorbé (dégâts réduits/mitigés).
    tank_x = 1405
    draw.rectangle((1330, y + 1, 1534, y + 44), fill=header_fill)
    _draw_text(draw, (tank_x, y + 14), "TANK TOTAL (RÉDUIT)", _font(12), PALETTE.muted, anchor="ma")

    team_tank_totals = [
        _as_float(_safe_get(match.thisDamageTakenListe, i))
        + _as_float(_safe_get(match.thisDamageSelfMitigatedListe, i))
        for i in team_indices
    ]

    for row, i in enumerate(team_indices):
        row_y = y + header_h + row * row_h
        center_y = row_y + row_h // 2
        is_player = i == player_index
        row_fill = _row_fill(ally, row, is_player)

        # L'écart d'or est conservé uniquement côté allié. Côté adverse, la zone
        # est nettoyée et le nom reprend sa position historique.
        if not ally:
            draw.rectangle((82, row_y + 3, 324, row_y + row_h - 3), fill=row_fill)
            player_name = _safe_get(match.thisRiotIdListe, i, "") or _safe_get(
                match.thisPseudoListe, i, "Inconnu"
            )
            rendered_name = _fit_text(draw, player_name, _font(19), 205)
            _draw_text(draw, (101, center_y - 2), rendered_name, _font(19), PALETTE.text, anchor="lm")

        # Masque l'ancienne valeur de tanking à x=1450 puis redessine la nouvelle.
        draw.rectangle((1330, row_y + 3, 1534, row_y + row_h - 3), fill=row_fill)
        taken = _as_float(_safe_get(match.thisDamageTakenListe, i))
        reduced = _as_float(_safe_get(match.thisDamageSelfMitigatedListe, i))
        total = taken + reduced
        tank_text = f"{_format_compact(total)} ({_format_compact(reduced)})"
        _draw_text(
            draw,
            (tank_x, center_y),
            tank_text,
            _font(15),
            _metric_color(total, team_tank_totals),
            anchor="mm",
        )


_renderer._draw_header = _draw_header
_renderer._draw_match_summary = _draw_match_summary
_renderer._draw_team_panel = _draw_team_panel

build_modern_recap = _renderer.build_modern_recap

__all__ = ["build_modern_recap"]