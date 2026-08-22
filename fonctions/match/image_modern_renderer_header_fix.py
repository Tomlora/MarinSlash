"""Correctifs visuels ciblés pour les titres du tableau moderne."""

from __future__ import annotations

from typing import Any, Mapping, Tuple

from PIL import Image, ImageDraw

# L'import applique d'abord tous les correctifs précédents du renderer final.
from . import image_modern_renderer_final as _final  # noqa: F401
from . import image_modern_renderer as _renderer
from .image_modern_common import PALETTE, _as_float, _draw_text, _font, _format_compact, _safe_get


_FINAL_DRAW_TEAM_PANEL = _renderer._draw_team_panel


def _restore_header_background(
    canvas: Image.Image,
    box: Tuple[int, int, int, int],
    sample_at: Tuple[int, int],
) -> None:
    """Recopie la couleur réelle du header sans créer une zone plus sombre."""
    canvas.paste(canvas.getpixel(sample_at), box)


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
    """Centre les titres K/D/A et KDA et uniformise le titre de tanking."""
    _FINAL_DRAW_TEAM_PANEL(
        canvas,
        draw,
        match,
        assets,
        start_index=start_index,
        y=y,
        ally=ally,
    )

    _restore_header_background(canvas, (610, y + 1, 785, y + 44), (785, y + 5))
    _draw_text(draw, (706, y + 14), "K / D / A", _font(14), PALETTE.muted, anchor="ma")

    _restore_header_background(canvas, (790, y + 1, 875, y + 44), (880, y + 5))
    _draw_text(draw, (827, y + 14), "KDA", _font(14), PALETTE.muted, anchor="ma")

    _restore_header_background(canvas, (1330, y + 1, 1534, y + 44), (1318, y + 5))
    _draw_text(
        draw,
        (1405, y + 14),
        "TANK TOTAL (RÉDUIT)",
        _font(14),
        PALETTE.muted,
        anchor="ma",
    )

    header_h = 45
    row_h = 52
    team_indices = list(range(start_index, min(start_index + 5, getattr(match, "nb_joueur", 10))))
    for row, i in enumerate(team_indices):
        row_y = y + header_h + row * row_h
        center_y = row_y + row_h // 2
        draw.rectangle(
            (1330, row_y + 3, 1534, row_y + row_h - 3),
            fill=canvas.getpixel((1320, center_y)),
        )
        taken = _as_float(_safe_get(match.thisDamageTakenListe, i))
        reduced = _as_float(_safe_get(match.thisDamageSelfMitigatedListe, i))
        tank_text = f"{_format_compact(taken + reduced)} ({_format_compact(reduced)})"
        _draw_text(draw, (1405, center_y), tank_text, _font(15), PALETTE.text, anchor="mm")


_renderer._draw_team_panel = _draw_team_panel

build_modern_recap = _renderer.build_modern_recap

__all__ = ["build_modern_recap"]