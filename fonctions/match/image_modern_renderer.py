"""Composition des panneaux du récapitulatif LoL moderne."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Mapping, Tuple

from PIL import Image, ImageDraw

from .image_modern_common import (
    MARGIN, PALETTE, WIDTH, _as_float, _as_int, _draw_badge,
    _draw_progress_bar, _draw_text, _fit_text, _font, _format_compact,
    _format_duration, _grade_color, _grade_from_rank, _gradient_background,
    _kda_color, _load_image_safe, _metric_color, _paste_with_alpha,
    _rounded_icon, _rounded_panel, _safe_get,
)
from .image_modern_data import (
    _get_daily_stats, _get_player_local_index, _get_player_summary, _get_rank,
    _participant_rank_text, _team_objectives, _team_totals,
)


async def _preload_assets(match: Any) -> Dict[str, Any]:
    champion_version = match.version.get("n", {}).get("champion", match.version.get("n", {}).get("profileicon", ""))
    profile_version = match.version.get("n", {}).get("profileicon", champion_version)
    item_version = match.version.get("n", {}).get("item", champion_version)

    tasks: Dict[str, Any] = {
        "avatar": _load_image_safe(match, "avatar", match.avatar, 88, 88, profile_version),
        "player_champion": _load_image_safe(match, "champion", match.thisChampName, 88, 88, champion_version),
        "player_tier": _load_image_safe(match, "tier", str(match.thisTier).upper(), 112, 112),
    }
    aliases: Dict[str, str] = {}

    for i in range(min(10, getattr(match, "nb_joueur", 10))):
        champion_name = _safe_get(match.thisChampNameListe, i, "")
        champion_key = f"champion_name_{champion_name}"
        if champion_key not in tasks:
            tasks[champion_key] = _load_image_safe(
                match, "champion", champion_name, 42, 42, champion_version
            )
        aliases[f"champ_{i}"] = champion_key

        tier = str(_safe_get(getattr(match, "liste_tier", []), i, "UNRANKED") or "UNRANKED").upper()
        tier_key = f"tier_name_{tier}"
        if tier_key not in tasks:
            tasks[tier_key] = _load_image_safe(match, "tier", tier, 34, 34)
        aliases[f"tier_{i}"] = tier_key

        for slot, item_id in enumerate(_safe_get(getattr(match, "allitems", []), i, []) or []):
            if _as_int(item_id) <= 0:
                continue
            item_key = f"item_id_{item_id}"
            if item_key not in tasks:
                tasks[item_key] = _load_image_safe(
                    match, "items", item_id, 38, 38, item_version
                )
            aliases[f"item_{i}_{slot}"] = item_key

    objective_names = {
        "obj_tower": "tower",
        "obj_dragon": "dragon",
        "obj_herald": "herald",
        "obj_baron": "nashor",
        "obj_horde": "horde",
        "obj_inhibitor": "inhibitor",
        "obj_elder": "elder",
    }
    for key, name in objective_names.items():
        tasks[key] = _load_image_safe(match, "monsters", name, 44, 44)

    keys = list(tasks.keys())
    values = await asyncio.gather(*tasks.values())
    assets = dict(zip(keys, values))
    for alias, source_key in aliases.items():
        assets[alias] = assets[source_key]
    return assets


# ---------------------------------------------------------------------------
# Dessin des différentes zones
# ---------------------------------------------------------------------------


def _draw_header(
    canvas: Image.Image,
    draw: ImageDraw.ImageDraw,
    match: Any,
    assets: Mapping[str, Image.Image],
    profile_summary: Mapping[str, Any],
    daily_stats: Tuple[int, int],
    dif_lp: Any,
) -> None:
    y1, y2 = 20, 154
    left = (MARGIN, y1, 840, y2)
    center = (852, y1, 1370, y2)
    right = (1382, y1, WIDTH - MARGIN, y2)
    _rounded_panel(canvas, left, fill=PALETTE.panel_alt)
    _rounded_panel(canvas, center, fill=PALETTE.panel)
    _rounded_panel(canvas, right, fill=PALETTE.panel)

    avatar = _rounded_icon(assets["avatar"], 82, 41)
    champion = _rounded_icon(assets["player_champion"], 82, 12)
    _paste_with_alpha(canvas, avatar, (43, 45))
    _paste_with_alpha(canvas, champion, (113, 45))
    draw.ellipse((40, 42, 128, 130), outline=PALETTE.border, width=2)
    draw.rounded_rectangle((110, 42, 198, 130), radius=14, outline=PALETTE.ally + (210,), width=2)

    player_name = _fit_text(draw, getattr(match, "riot_id", ""), _font(31), 260)
    _draw_text(draw, (220, 38), player_name, _font(31), PALETTE.text, stroke_width=1, stroke_fill=(0, 0, 0))
    _draw_text(draw, (220, 76), getattr(match, "thisChampName", ""), _font(19), PALETTE.ally)

    games = _as_int(profile_summary.get("games"))
    mvp = _as_float(profile_summary.get("mvp"))
    _draw_text(draw, (220, 105), f"{games} parties  •  {mvp:.1f} MVP", _font(18), PALETTE.muted)
    k = _as_float(profile_summary.get("kills"))
    d = _as_float(profile_summary.get("deaths"))
    a = _as_float(profile_summary.get("assists"))
    _draw_text(
        draw,
        (220, 128),
        f"{_as_float(profile_summary.get('kda')):.2f} KDA  ({k:.1f} / {d:.1f} / {a:.1f})",
        _font(17),
        PALETTE.text,
    )

    # Mini cartes WR / KDA
    for box, value, label, color in (
        ((590, 37, 700, 136), f"{_as_float(profile_summary.get('winrate')):.0f}%", "Win rate", PALETTE.ally),
        ((710, 37, 820, 136), f"{_as_float(profile_summary.get('kda')):.2f}", "KDA", PALETTE.text),
    ):
        draw.rounded_rectangle(box, radius=12, fill=(5, 18, 34, 190), outline=PALETTE.border, width=1)
        _draw_text(draw, ((box[0] + box[2]) // 2, box[1] + 35), value, _font(27), color, anchor="mm")
        _draw_text(draw, ((box[0] + box[2]) // 2, box[1] + 69), label, _font(15), PALETTE.muted, anchor="mm")

    # Rang principal
    _paste_with_alpha(canvas, assets["player_tier"], (873, 31))
    tier = str(getattr(match, "thisTier", "") or "Non classé").title()
    division = str(getattr(match, "thisRank", "") or "")
    _draw_text(draw, (1000, 40), f"{tier} {division}".strip(), _font(28), PALETTE.text)
    lp_text = f"{getattr(match, 'thisLP', 0)} LP ({dif_lp})"
    _draw_text(draw, (1000, 77), lp_text, _font(20), PALETTE.muted)
    wins = _as_int(getattr(match, "thisVictory", 0))
    losses = _as_int(getattr(match, "thisLoose", 0))
    total = wins + losses
    wr = round(100 * wins / total) if total else 0
    _draw_text(draw, (1000, 108), f"{wins}W {losses}L  ({wr}%)", _font(18), PALETTE.muted)

    # Compte et score
    _draw_text(draw, (1408, 38), f"Niveau {getattr(match, 'level_summoner', 0)}", _font(25), PALETTE.text)
    _draw_text(draw, (1408, 76), f"Victoires 24h : {daily_stats[0]}", _font(18), PALETTE.muted)
    _draw_text(draw, (1408, 104), f"Défaites 24h : {daily_stats[1]}", _font(18), PALETTE.muted)

    score = _as_float(getattr(match, "player_score", 0))
    score_box = (1690, 37, 1874, 137)
    draw.rounded_rectangle(score_box, radius=13, fill=(5, 19, 36, 205), outline=PALETTE.ally + (120,), width=1)
    _draw_text(draw, (1782, 54), "MVP SCORE", _font(16), PALETTE.ally, anchor="mm")
    _draw_text(draw, (1782, 88), f"{score:.1f}", _font(34), PALETTE.text, anchor="mm")
    player_rank = _get_rank(match, _get_player_local_index(match))
    _draw_text(draw, (1782, 119), f"#{player_rank} sur 10", _font(15), PALETTE.muted, anchor="mm")


def _draw_match_summary(
    canvas: Image.Image,
    draw: ImageDraw.ImageDraw,
    match: Any,
    assets: Mapping[str, Image.Image],
    objectives: Mapping[str, int],
) -> None:
    box = (MARGIN, 166, WIDTH - MARGIN, 264)
    _rounded_panel(canvas, box, fill=PALETTE.panel)
    victory = bool(getattr(match, "thisWinBool", False))
    result_color = PALETTE.ally if victory else PALETTE.enemy
    result_label = "VICTOIRE" if victory else "DÉFAITE"

    draw.ellipse((47, 184, 105, 242), fill=result_color + (28,), outline=result_color + (220,), width=2)
    # Symbole simple, indépendant d'un asset local.
    draw.line((62, 224, 91, 195), fill=result_color, width=5)
    draw.line((64, 195, 91, 223), fill=result_color, width=5)
    _draw_text(draw, (123, 185), result_label, _font(27), result_color)
    _draw_text(draw, (123, 220), "Équipe alliée", _font(17), PALETTE.muted)

    summary_stats = [
        ("Durée", _format_duration(getattr(match, "thisTime", 0)), (350, 214)),
        ("Kills", _as_int(getattr(match, "thisTeamKills", 0)), (500, 214)),
        ("Morts", _as_int(getattr(match, "thisTeamKillsOp", 0)), (640, 214)),
    ]
    for label, value, center in summary_stats:
        _draw_text(draw, (center[0], 192), value, _font(27), PALETTE.text, anchor="mm")
        _draw_text(draw, (center[0], 232), label, _font(15), PALETTE.muted, anchor="mm")

    draw.line((710, 183, 710, 246), fill=PALETTE.divider, width=1)

    objective_order = [
        ("obj_tower", "tower", "Tours"),
        ("obj_inhibitor", "inhibitor", "Inhibs"),
        ("obj_dragon", "dragon", "Dragons"),
        ("obj_herald", "riftHerald", "Hérauts"),
        ("obj_baron", "baron", "Barons"),
        ("obj_horde", "horde", "Voidgrubs"),
        ("obj_elder", "elder", "Elders"),
    ]
    start_x = 746
    cell_width = 164
    for pos, (asset_key, stat_key, label) in enumerate(objective_order):
        x = start_x + pos * cell_width
        icon = assets.get(asset_key)
        if icon:
            _paste_with_alpha(canvas, icon, (x, 184))
        _draw_text(draw, (x + 53, 192), objectives.get(stat_key, 0), _font(24), PALETTE.text)
        _draw_text(draw, (x + 53, 225), label, _font(14), PALETTE.muted)


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
    panel_height = 310
    x1, x2 = MARGIN, WIDTH - MARGIN
    accent = PALETTE.ally if ally else PALETTE.enemy
    fill = (7, 30, 57, 230) if ally else (45, 15, 28, 225)
    outline = accent + (175,)
    _rounded_panel(canvas, (x1, y, x2, y + panel_height), fill=fill, outline=outline, radius=15)

    header_h = 45
    header_fill = accent + (38,)
    header_overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    header_draw = ImageDraw.Draw(header_overlay)
    header_draw.rounded_rectangle((x1, y, x2, y + header_h), radius=15, fill=header_fill)
    header_draw.rectangle((x1, y + header_h - 15, x2, y + header_h), fill=header_fill)
    canvas.alpha_composite(header_overlay)

    team_name = "ÉQUIPE ALLIÉE" if ally else "ÉQUIPE ADVERSE"
    gold = getattr(match, "thisGold_team1", 0) if ally else getattr(match, "thisGold_team2", 0)
    _draw_text(draw, (43, y + 12), team_name, _font(20), accent)
    _draw_text(draw, (250, y + 12), f"OR  {_format_compact(gold)}", _font(18), PALETTE.text)

    # Colonnes : les positions sont fixes pour garantir l'alignement.
    headers = [
        (486, "LVL"),
        (558, "MVP"),
        (655, "K / D / A"),
        (827, "KDA"),
        (928, "KP"),
        (1030, "CS"),
        (1125, "VISION"),
        (1255, "DMG (PART)"),
        (1450, "TANK"),
        (1684, "ITEMS"),
    ]
    for x, label in headers:
        _draw_text(draw, (x, y + 14), label, _font(14), PALETTE.muted, anchor="ma")

    row_h = 52
    player_index = _get_player_local_index(match)
    team_indices = list(range(start_index, min(start_index + 5, getattr(match, "nb_joueur", 10))))
    team_kp = [_as_float(_safe_get(match.thisKPListe, i)) for i in team_indices]
    team_cs = [
        _as_float(_safe_get(match.thisMinionListe, i)) + _as_float(_safe_get(match.thisJungleMonsterKilledListe, i))
        for i in team_indices
    ]
    team_vision = [_as_float(_safe_get(match.thisVisionListe, i)) for i in team_indices]
    team_damage = [_as_float(_safe_get(match.thisDamageListe, i)) for i in team_indices]
    team_tank = [
        _as_float(_safe_get(match.thisDamageTakenListe, i))
        + _as_float(_safe_get(match.thisDamageSelfMitigatedListe, i))
        for i in team_indices
    ]

    for row, i in enumerate(team_indices):
        row_y = y + header_h + row * row_h
        center_y = row_y + row_h // 2
        is_player = i == player_index

        if row % 2 == 1:
            alternate_fill = (12, 38, 67, 255) if ally else (53, 20, 32, 255)
            draw.rectangle((x1 + 1, row_y, x2 - 1, row_y + row_h), fill=alternate_fill)
        if is_player:
            draw.rounded_rectangle(
                (x1 + 4, row_y + 2, x2 - 4, row_y + row_h - 2),
                radius=9,
                fill=(17, 72, 119, 255),
                outline=PALETTE.ally + (210,),
                width=1,
            )

        champ = _rounded_icon(assets[f"champ_{i}"], 42, 8)
        _paste_with_alpha(canvas, champ, (43, row_y + 5))

        player_name = _safe_get(match.thisRiotIdListe, i, "") or _safe_get(match.thisPseudoListe, i, "Inconnu")
        name_color = PALETTE.ally if is_player else PALETTE.text
        rendered_name = _fit_text(draw, player_name, _font(19), 205)
        _draw_text(draw, (101, center_y - 2), rendered_name, _font(19), name_color, anchor="lm")

        tier_icon = _rounded_icon(assets[f"tier_{i}"], 32, 6)
        _paste_with_alpha(canvas, tier_icon, (329, row_y + 10))
        rank_text = _fit_text(draw, _participant_rank_text(match, i), _font(14), 115)
        _draw_text(draw, (368, center_y - 1), rank_text, _font(14), PALETTE.muted, anchor="lm")

        _draw_text(draw, (486, center_y), _as_int(_safe_get(match.thisLevelListe, i)), _font(19), PALETTE.text, anchor="mm")

        rank = _get_rank(match, i)
        _draw_badge(draw, (558, center_y), _grade_from_rank(rank), _grade_color(rank))
        _draw_text(draw, (585, center_y + 1), f"#{rank}", _font(12), PALETTE.muted, anchor="lm")

        kills = _as_int(_safe_get(match.thisKillsListe, i))
        deaths = _as_int(_safe_get(match.thisDeathsListe, i))
        assists = _as_int(_safe_get(match.thisAssistsListe, i))
        _draw_text(draw, (655, center_y), kills, _font(19), PALETTE.positive, anchor="mm")
        _draw_text(draw, (680, center_y), "/", _font(17), PALETTE.muted, anchor="mm")
        _draw_text(draw, (705, center_y), deaths, _font(19), PALETTE.negative, anchor="mm")
        _draw_text(draw, (730, center_y), "/", _font(17), PALETTE.muted, anchor="mm")
        _draw_text(draw, (758, center_y), assists, _font(19), PALETTE.text, anchor="mm")

        kda = _as_float(_safe_get(match.thisKDAListe, i))
        _draw_text(draw, (827, center_y), f"{kda:.2f}", _font(18), _kda_color(kda), anchor="mm")

        kp = _as_float(_safe_get(match.thisKPListe, i))
        _draw_text(draw, (928, center_y - 8), f"{kp:.0f}%", _font(16), _metric_color(kp, team_kp), anchor="mm")
        _draw_progress_bar(draw, (893, center_y + 10, 963, center_y + 15), kp / 100.0, accent)

        cs = _as_float(_safe_get(match.thisMinionListe, i)) + _as_float(_safe_get(match.thisJungleMonsterKilledListe, i))
        _draw_text(draw, (1030, center_y), f"{cs:.0f}", _font(18), _metric_color(cs, team_cs), anchor="mm")

        vision = _as_float(_safe_get(match.thisVisionListe, i))
        _draw_text(draw, (1125, center_y), f"{vision:.0f}", _font(18), _metric_color(vision, team_vision), anchor="mm")

        damage = _as_float(_safe_get(match.thisDamageListe, i))
        share = 100 * _as_float(_safe_get(match.thisDamageRatioListe, i))
        _draw_text(draw, (1255, center_y - 8), f"{_format_compact(damage)} ({share:.0f}%)", _font(16), _metric_color(damage, team_damage), anchor="mm")
        _draw_progress_bar(draw, (1198, center_y + 10, 1312, center_y + 15), share / 100.0, accent)

        tank = _as_float(_safe_get(match.thisDamageTakenListe, i)) + _as_float(_safe_get(match.thisDamageSelfMitigatedListe, i))
        _draw_text(draw, (1450, center_y), _format_compact(tank), _font(18), _metric_color(tank, team_tank), anchor="mm")

        item_x = 1540
        for slot in range(6):
            key = f"item_{i}_{slot}"
            if key in assets:
                item = _rounded_icon(assets[key], 38, 5)
                _paste_with_alpha(canvas, item, (item_x + slot * 47, row_y + 7))
            else:
                draw.rounded_rectangle(
                    (item_x + slot * 47, row_y + 7, item_x + slot * 47 + 38, row_y + 45),
                    radius=5,
                    fill=(7, 15, 27, 170),
                    outline=(43, 62, 82, 110),
                )

        if row < len(team_indices) - 1:
            draw.line((x1 + 20, row_y + row_h, x2 - 20, row_y + row_h), fill=PALETTE.divider, width=1)


def _draw_comparison_card(
    draw: ImageDraw.ImageDraw,
    box: Tuple[int, int, int, int],
    title: str,
    ally_value: float,
    enemy_value: float,
    formatter,
) -> None:
    x1, y1, x2, y2 = box
    draw.rounded_rectangle(box, radius=14, fill=PALETTE.panel_soft, outline=PALETTE.border, width=1)
    _draw_text(draw, (x1 + 18, y1 + 15), title, _font(15), PALETTE.muted)
    _draw_text(draw, (x1 + 18, y1 + 43), formatter(ally_value), _font(19), PALETTE.ally)
    _draw_text(draw, (x1 + 18, y1 + 72), formatter(enemy_value), _font(19), PALETTE.enemy)

    max_value = max(abs(ally_value), abs(enemy_value), 1)
    bar_x1, bar_x2 = x1 + 105, x2 - 18
    _draw_progress_bar(draw, (bar_x1, y1 + 47, bar_x2, y1 + 54), ally_value / max_value, PALETTE.ally)
    _draw_progress_bar(draw, (bar_x1, y1 + 76, bar_x2, y1 + 83), enemy_value / max_value, PALETTE.enemy)


def _draw_footer(draw: ImageDraw.ImageDraw, ally_totals: Mapping[str, float], enemy_totals: Mapping[str, float]) -> None:
    y1, y2 = 951, 1055
    gap = 12
    total_width = WIDTH - 2 * MARGIN
    card_width = (total_width - 4 * gap) // 5
    cards = [
        ("OR", "gold", lambda v: _format_compact(v)),
        ("DÉGÂTS INFLIGÉS", "damage", lambda v: _format_compact(v)),
        ("VISION", "vision", lambda v: f"{v:.0f}"),
        ("PARTICIPATION", "kp", lambda v: f"{v:.0f}%"),
        ("DÉGÂTS ABSORBÉS", "tank", lambda v: _format_compact(v)),
    ]
    for i, (title, key, formatter) in enumerate(cards):
        x1 = MARGIN + i * (card_width + gap)
        x2 = x1 + card_width
        _draw_comparison_card(
            draw,
            (x1, y1, x2, y2),
            title,
            _as_float(ally_totals.get(key)),
            _as_float(enemy_totals.get(key)),
            formatter,
        )


# ---------------------------------------------------------------------------
# API publique
# ---------------------------------------------------------------------------


async def build_modern_recap(match: Any, dif_lp: Any = 0) -> Image.Image:
    """Construit le récapitulatif moderne et retourne une image PIL RGBA."""
    canvas = _gradient_background()
    draw = ImageDraw.Draw(canvas, "RGBA")

    profile_summary = _get_player_summary(match)
    daily_stats = _get_daily_stats(match)
    objectives = _team_objectives(match)
    ally_totals = _team_totals(match, 0)
    enemy_totals = _team_totals(match, 5)
    assets = await _preload_assets(match)

    _draw_header(canvas, draw, match, assets, profile_summary, daily_stats, dif_lp)
    _draw_match_summary(canvas, draw, match, assets, objectives)
    _draw_team_panel(canvas, draw, match, assets, start_index=0, y=278, ally=True)
    _draw_team_panel(canvas, draw, match, assets, start_index=5, y=608, ally=False)
    _draw_footer(draw, ally_totals, enemy_totals)

    # Aplatit les quelques calques semi-transparents afin que Discord affiche
    # exactement les mêmes couleurs, quel que soit son fond d'interface.
    flattened = Image.new("RGBA", canvas.size, PALETTE.background_bottom + (255,))
    flattened.alpha_composite(canvas)
    return flattened