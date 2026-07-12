"""Correctifs visuels ciblés pour les titres du tableau moderne."""

from __future__ import annotations

from typing import Any, Mapping, Tuple

from PIL import Image, ImageDraw

# L'import applique d'abord tous les correctifs précédents du renderer final.
from . import image_modern_renderer_final as _final  # noqa: F401
from . import image_modern_renderer as _renderer
from .image_modern_common import PALETTE, _draw_text, _font


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
    """Aligne KDA et uniformise le titre de la colonne de tanking."""
    _FINAL_DRAW_TEAM_PANEL(
        canvas,
        draw,
        match,
        assets,
        start_index=start_index,
        y=y,
        ally=ally,
    )

    # Le contenu KDA reste centré en x=827, mais le rendu du libellé paraissait
    # visuellement trop à gauche. On efface l'ancien titre et on le décale de 15 px.
    _restore_header_background(
        canvas,
        (790, y + 1, 875, y + 44),
        (880, y + 5),
    )
    _draw_text(
        draw,
        (842, y + 14),
        "KDA",
        _font(14),
        PALETTE.muted,
        anchor="ma",
    )

    # Le précédent masque utilisait un aplat opaque différent du reste du header.
    # On restaure ici la couleur réellement composée, puis on redessine le titre
    # avec exactement la même police et la même couleur que les autres colonnes.
    _restore_header_background(
        canvas,
        (1330, y + 1, 1534, y + 44),
        (1318, y + 5),
    )
    _draw_text(
        draw,
        (1405, y + 14),
        "TANK TOTAL (RÉDUIT)",
        _font(14),
        PALETTE.muted,
        anchor="ma",
    )


_renderer._draw_team_panel = _draw_team_panel

build_modern_recap = _renderer.build_modern_recap

__all__ = ["build_modern_recap"]
