"""Ajustements visuels du récapitulatif moderne.

Ce module conserve le renderer principal intact et surcharge uniquement les
zones concernées : résultat du match, espacement du header, écarts d'or par
poste, ordre visuel des objets et rang moyen des équipes.
"""

from __future__ import annotations

from typing import Any, Mapping, Tuple

from PIL import Image, ImageDraw

from . import image_modern_renderer as _renderer
from .image_modern_common import (
    PALETTE,
    _as_float,
    _as_int,
    _draw_text,
    _fit_text,
    _font,
    _format_compact,
    _paste_with_alpha,
    _rounded_icon,
    _safe_get,
)
from .image_modern_data import _get_player_local_index


_ORIGINAL_DRAW_HEADER = _renderer._draw_header
_ORIGINAL_DRAW_MATCH_SUMMARY = _renderer._draw_match_summary
_ORIGINAL_DRAW_TEAM_PANEL = _renderer._draw_team_panel

_GOLD_DIFF_ATTRS = (
    "ecart_top_gold",
    "ecart_jgl_gold",
    "ecart_mid_gold",
    "ecart_adc_gold",
    "ecart_supp_gold",
)

_TIER_ORDER = (
    "IRON",
    "BRONZE",
    "SILVER",
    "GOLD",
    "PLATINUM",
    "EMERALD",
    "DIAMOND",
    "MASTER",
    "GRANDMASTER",
    "CHALLENGER",
)
_DIVISION_TO_VALUE = {"IV": 0, "III": 1, "II": 2, "I": 3}
_VALUE_TO_DIVISION = {value: division for division, value in _DIVISION_TO_VALUE.items()}
_APEX_TIERS = {"MASTER", "GRANDMASTER", "CHALLENGER"}


def _gold_diff_for_index(match: Any, player_index: int) -> float:
    """Retourne l'écart d'or du poste depuis le point de vue de la ligne."""
    role_index = player_index % 5
    ally_diff = _as_float(getattr(match, _GOLD_DIFF_ATTRS[role_index], 0))
    return ally_diff if player_index < 5 else -ally_diff


def _format_signed_gold(value: float) -> str:
    if abs(value) < 0.5:
        return "0"
    sign = "+" if value > 0 else "-"
    return f"{sign}{_format_compact(abs(value))}"


def _team_average_rank(match: Any, start_index: int, ally: bool) -> Tuple[str, str]:
    """Retourne le rang moyen fourni par Mobalytics ou le recalcule via Riot.

    Le calcul de secours transforme les rangs en une échelle continue afin que,
    par exemple, Emerald I et Diamond IV restent voisins lors de la moyenne.
    Les joueurs non classés sont ignorés.
    """
    suffix = "ally" if ally else "enemy"
    tier = str(getattr(match, f"avgtier_{suffix}", "") or "").strip().upper()
    division = str(getattr(match, f"avgrank_{suffix}", "") or "").strip().upper()

    if tier in _TIER_ORDER:
        return tier, "" if tier in _APEX_TIERS else division

    scores = []
    end_index = min(start_index + 5, getattr(match, "nb_joueur", 10))
    tiers = getattr(match, "liste_tier", [])
    divisions = getattr(match, "liste_rank", [])

    for index in range(start_index, end_index):
        player_tier = str(_safe_get(tiers, index, "") or "").strip().upper()
        if player_tier not in _TIER_ORDER:
            continue

        tier_value = _TIER_ORDER.index(player_tier) * 4
        if player_tier in _APEX_TIERS:
            division_value = 3
        else:
            player_division = str(_safe_get(divisions, index, "IV") or "IV").strip().upper()
            division_value = _DIVISION_TO_VALUE.get(player_division, 0)
        scores.append(tier_value + division_value)

    if not scores:
        return "", ""

    average_value = int(round(sum(scores) / len(scores)))
    max_value = len(_TIER_ORDER) * 4 - 1
    average_value = max(0, min(max_value, average_value))
    tier_index, division_value = divmod(average_value, 4)
    average_tier = _TIER_ORDER[tier_index]
    average_division = "" if average_tier in _APEX_TIERS else _VALUE_TO_DIVISION[division_value]
    return average_tier, average_division


def _format_average_rank(tier: str, division: str) -> str:
    if not tier:
        return "Non classé"
    return f"{tier.title()} {division}".strip()


def _draw_header(
    canvas: Image.Image,
    draw: ImageDraw.ImageDraw,
    match: Any,
    assets: Mapping[str, Image.Image],
    profile_summary: Mapping[str, Any],
    daily_stats,
    dif_lp: Any,
) -> None:
    """Redessine le bloc identité avec davantage d'air entre les deux icônes."""
    _ORIGINAL_DRAW_HEADER(canvas, draw, match, assets, profile_summary, daily_stats, dif_lp)

    # Nettoyage local du bloc identité uniquement. Les cartes WR/KDA restent intactes.
    draw.rectangle((31, 29, 574, 145), fill=PALETTE.panel_alt)

    avatar = _rounded_icon(assets["avatar"], 82, 41)
    champion = _rounded_icon(assets["player_champion"], 82, 12)
    _paste_with_alpha(canvas, avatar, (43, 45))
    _paste_with_alpha(canvas, champion, (138, 45))
    draw.ellipse((40, 42, 128, 130), outline=PALETTE.border, width=2)
    draw.rounded_rectangle(
        (135, 42, 223, 130),
        radius=14,
        outline=PALETTE.ally + (210,),
        width=2,
    )

    text_x = 244
    player_name = _fit_text(draw, getattr(match, "riot_id", ""), _font(31), 245)
    _draw_text(
        draw,
        (text_x, 38),
        player_name,
        _font(31),
        PALETTE.text,
        stroke_width=1,
        stroke_fill=(0, 0, 0),
    )
    _draw_text(draw, (text_x, 76), getattr(match, "thisChampName", ""), _font(19), PALETTE.ally)

    games = int(_as_float(profile_summary.get("games")))
    mvp = _as_float(profile_summary.get("mvp"))
    _draw_text(draw, (text_x, 105), f"{games} parties  •  {mvp:.1f} MVP", _font(18), PALETTE.muted)

    kills = _as_float(profile_summary.get("kills"))
    deaths = _as_float(profile_summary.get("deaths"))
    assists = _as_float(profile_summary.get("assists"))
    kda = _as_float(profile_summary.get("kda"))
    _draw_text(
        draw,
        (text_x, 128),
        f"{kda:.2f} KDA  ({kills:.1f} / {deaths:.1f} / {assists:.1f})",
        _font(17),
        PALETTE.text,
    )


def _draw_match_summary(
    canvas: Image.Image,
    draw: ImageDraw.ImageDraw,
    match: Any,
    assets: Mapping[str, Image.Image],
    objectives,
) -> None:
    """Affiche un check vert en victoire et conserve la croix rouge en défaite."""
    _ORIGINAL_DRAW_MATCH_SUMMARY(canvas, draw, match, assets, objectives)

    victory = bool(getattr(match, "thisWinBool", False))
    result_color = PALETTE.positive if victory else PALETTE.enemy

    # Recouvre complètement l'ancien pictogramme.
    draw.ellipse((45, 182, 107, 244), fill=PALETTE.panel)
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

    # Le libellé d'origine était bleu en victoire : on le repeint en vert.
    if victory:
        draw.rectangle((118, 180, 260, 218), fill=PALETTE.panel)
        _draw_text(draw, (123, 185), "VICTOIRE", _font(27), result_color)


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
    """Ajoute l'écart d'or, le rang moyen et l'ordre historique des objets."""
    _ORIGINAL_DRAW_TEAM_PANEL(
        canvas,
        draw,
        match,
        assets,
        start_index=start_index,
        y=y,
        ally=ally,
    )

    row_h = 52
    header_h = 45
    player_index = _get_player_local_index(match)
    team_indices = list(range(start_index, min(start_index + 5, getattr(match, "nb_joueur", 10))))
    accent = PALETTE.ally if ally else PALETTE.enemy

    # Le total d'or est déjà présent dans le footer : on utilise cet espace pour
    # le rang moyen de l'équipe. Le fond sombre masque complètement l'ancien texte.
    rank_tier, rank_division = _team_average_rank(match, start_index, ally)
    rank_text = _format_average_rank(rank_tier, rank_division)
    rank_box = (226, y + 6, 505, y + 39)
    draw.rounded_rectangle(
        rank_box,
        radius=9,
        fill=(5, 18, 34, 235),
        outline=accent + (90,),
        width=1,
    )

    rank_icon = assets.get(f"tier_name_{rank_tier}") if rank_tier else None
    text_x = 241
    if rank_icon is not None:
        icon = _rounded_icon(rank_icon, 28, 5)
        _paste_with_alpha(canvas, icon, (234, y + 8))
        text_x = 270

    _draw_text(
        draw,
        (text_x, y + 23),
        f"RANG MOYEN  {rank_text}",
        _font(14),
        PALETTE.text,
        anchor="lm",
    )

    # Petit repère de colonne, discret pour ne pas alourdir le header.
    _draw_text(draw, (119, y + 14), "Δ OR", _font(12), PALETTE.muted, anchor="ma")

    for row, i in enumerate(team_indices):
        row_y = y + header_h + row * row_h
        center_y = row_y + row_h // 2
        is_player = i == player_index

        if is_player:
            row_fill = (17, 72, 119, 255)
        elif row % 2 == 1:
            row_fill = (12, 38, 67, 255) if ally else (53, 20, 32, 255)
        else:
            row_fill = (7, 30, 57, 255) if ally else (45, 15, 28, 255)

        # Ne touche ni au portrait du champion ni à l'icône de rang.
        draw.rectangle((82, row_y + 3, 324, row_y + row_h - 3), fill=row_fill)

        gold_diff = _gold_diff_for_index(match, i)
        diff_color = (
            PALETTE.positive
            if gold_diff > 0
            else PALETTE.negative
            if gold_diff < 0
            else PALETTE.muted
        )
        _draw_text(
            draw,
            (119, center_y),
            _format_signed_gold(gold_diff),
            _font(16),
            diff_color,
            anchor="mm",
        )

        player_name = _safe_get(match.thisRiotIdListe, i, "") or _safe_get(
            match.thisPseudoListe,
            i,
            "Inconnu",
        )
        name_color = PALETTE.ally if is_player else PALETTE.text
        rendered_name = _fit_text(draw, player_name, _font(18), 160)
        _draw_text(draw, (158, center_y - 2), rendered_name, _font(18), name_color, anchor="lm")

        # L'ancien rendu compactait les slots vides : les objets non nuls restent
        # dans l'ordre item0 -> item5 mais sont rapprochés vers la gauche.
        item_x = 1540
        item_size = 38
        item_gap = 47
        draw.rectangle((1535, row_y + 3, 1830, row_y + row_h - 3), fill=row_fill)

        source_items = list(_safe_get(getattr(match, "allitems", []), i, []) or [])
        ordered_slots = [
            slot
            for slot, item_id in enumerate(source_items[:6])
            if _as_int(item_id) > 0
        ]

        for display_slot, source_slot in enumerate(ordered_slots):
            key = f"item_{i}_{source_slot}"
            item = assets.get(key)
            destination_x = item_x + display_slot * item_gap
            if item is not None:
                rendered_item = _rounded_icon(item, item_size, 5)
                _paste_with_alpha(canvas, rendered_item, (destination_x, row_y + 7))
            else:
                draw.rounded_rectangle(
                    (destination_x, row_y + 7, destination_x + item_size, row_y + 45),
                    radius=5,
                    fill=(7, 15, 27, 170),
                    outline=(43, 62, 82, 110),
                )

        for display_slot in range(len(ordered_slots), 6):
            destination_x = item_x + display_slot * item_gap
            draw.rounded_rectangle(
                (destination_x, row_y + 7, destination_x + item_size, row_y + 45),
                radius=5,
                fill=(7, 15, 27, 170),
                outline=(43, 62, 82, 110),
            )


# Le renderer principal résout ces fonctions dans son espace global au moment
# de l'appel. Les surcharges restent donc localisées et le reste du rendu ne
# change pas.
_renderer._draw_header = _draw_header
_renderer._draw_match_summary = _draw_match_summary
_renderer._draw_team_panel = _draw_team_panel

build_modern_recap = _renderer.build_modern_recap

__all__ = ["build_modern_recap"]
