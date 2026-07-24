"""Primitives graphiques du récapitulatif LoL moderne."""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Dict, Optional, Sequence, Tuple, Union

from PIL import Image, ImageDraw, ImageFilter

from .riot_api import get_image
from .utils import charger_font

Color = Tuple[int, int, int]
RGBA = Tuple[int, int, int, int]


@dataclass(frozen=True)
class ModernPalette:
    background_top: Color = (5, 14, 29)
    background_bottom: Color = (1, 6, 16)
    panel: RGBA = (9, 23, 42, 235)
    panel_alt: RGBA = (12, 30, 53, 235)
    panel_soft: RGBA = (15, 35, 59, 205)
    border: RGBA = (47, 78, 111, 150)
    divider: RGBA = (56, 84, 112, 100)
    text: Color = (236, 242, 250)
    muted: Color = (151, 168, 188)
    subtle: Color = (100, 122, 148)
    ally: Color = (49, 142, 255)
    ally_soft: RGBA = (24, 93, 174, 135)
    ally_row: RGBA = (22, 87, 145, 105)
    enemy: Color = (246, 72, 89)
    enemy_soft: RGBA = (145, 36, 53, 125)
    positive: Color = (89, 220, 126)
    negative: Color = (255, 91, 91)
    warning: Color = (250, 190, 74)
    purple: Color = (157, 118, 255)
    track: RGBA = (51, 69, 91, 160)


PALETTE = ModernPalette()
WIDTH = 1920
HEIGHT = 1080
MARGIN = 24


# ---------------------------------------------------------------------------
# Helpers généraux
# ---------------------------------------------------------------------------


@lru_cache(maxsize=64)
def _font(size: int):
    """Charge la police utilisée par le projet."""
    return charger_font(size)


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_get(seq: Sequence[Any], index: int, default: Any = 0) -> Any:
    try:
        return seq[index]
    except (IndexError, TypeError):
        return default


def _format_compact(value: Any, decimals: int = 1) -> str:
    number = _as_float(value)
    abs_number = abs(number)
    if abs_number >= 1_000_000:
        rendered = f"{number / 1_000_000:.{decimals}f}M"
    elif abs_number >= 1_000:
        rendered = f"{number / 1_000:.{decimals}f}k"
    else:
        rendered = f"{number:.0f}"
    return rendered.replace(".0k", "k").replace(".0M", "M")


def _format_duration(minutes_value: Any) -> str:
    minutes_float = max(0.0, _as_float(minutes_value))
    total_seconds = int(round(minutes_float * 60))
    minutes, seconds = divmod(total_seconds, 60)
    return f"{minutes}:{seconds:02d}"


def _normalize_name(value: Any) -> str:
    return str(value or "").lower().replace(" ", "")


def _grade_from_rank(rank: int) -> str:
    if rank <= 2:
        return "S"
    if rank <= 5:
        return "A"
    if rank <= 7:
        return "B"
    return "C"


def _grade_color(rank: int) -> Color:
    if rank <= 2:
        return PALETTE.warning
    if rank <= 5:
        return PALETTE.ally
    if rank <= 7:
        return PALETTE.purple
    return (224, 137, 70)


def _kda_color(kda: float) -> Color:
    if kda >= 5:
        return PALETTE.positive
    if kda < 1:
        return PALETTE.negative
    if kda < 2:
        return (244, 143, 91)
    return PALETTE.text


def _metric_color(value: float, team_values: Sequence[float], higher_is_better: bool = True) -> Color:
    clean_values = [_as_float(v) for v in team_values]
    if not clean_values:
        return PALETTE.text
    best = max(clean_values) if higher_is_better else min(clean_values)
    worst = min(clean_values) if higher_is_better else max(clean_values)
    if math.isclose(value, best, rel_tol=1e-9, abs_tol=1e-9):
        return PALETTE.positive
    if not math.isclose(best, worst, rel_tol=1e-9, abs_tol=1e-9) and math.isclose(
        value, worst, rel_tol=1e-9, abs_tol=1e-9
    ):
        return PALETTE.negative
    return PALETTE.text


def _draw_text(
    draw: ImageDraw.ImageDraw,
    xy: Tuple[int, int],
    text: Any,
    font,
    fill: Union[Color, RGBA] = PALETTE.text,
    *,
    anchor: Optional[str] = None,
    stroke_width: int = 0,
    stroke_fill: Optional[Union[Color, RGBA]] = None,
) -> None:
    draw.text(
        xy,
        str(text),
        font=font,
        fill=fill,
        anchor=anchor,
        stroke_width=stroke_width,
        stroke_fill=stroke_fill,
    )


def _text_width(draw: ImageDraw.ImageDraw, text: Any, font) -> int:
    box = draw.textbbox((0, 0), str(text), font=font)
    return box[2] - box[0]


def _fit_text(draw: ImageDraw.ImageDraw, text: Any, font, max_width: int) -> str:
    value = str(text)
    if _text_width(draw, value, font) <= max_width:
        return value
    ellipsis = "…"
    while value and _text_width(draw, value + ellipsis, font) > max_width:
        value = value[:-1]
    return value + ellipsis


def _rounded_panel(
    canvas: Image.Image,
    box: Tuple[int, int, int, int],
    *,
    fill: RGBA = PALETTE.panel,
    outline: RGBA = PALETTE.border,
    radius: int = 18,
    width: int = 1,
) -> None:
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)
    canvas.alpha_composite(overlay)


def _gradient_background() -> Image.Image:
    image = Image.new("RGBA", (WIDTH, HEIGHT), PALETTE.background_bottom + (255,))
    gradient_draw = ImageDraw.Draw(image)
    top = PALETTE.background_top
    bottom = PALETTE.background_bottom
    for y in range(HEIGHT):
        t = y / max(1, HEIGHT - 1)
        r = int(top[0] * (1 - t) + bottom[0] * t)
        g = int(top[1] * (1 - t) + bottom[1] * t)
        b = int(top[2] * (1 - t) + bottom[2] * t)
        gradient_draw.line((0, y, WIDTH, y), fill=(r, g, b, 255))

    # Halo bleu très discret en haut à gauche et rouge en bas à droite.
    glow = Image.new("RGBA", image.size, (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.ellipse((-280, -330, 880, 700), fill=(25, 112, 255, 42))
    glow_draw.ellipse((1330, 620, 2250, 1450), fill=(224, 48, 82, 22))
    glow = glow.filter(ImageFilter.GaussianBlur(120))
    image.alpha_composite(glow)
    return image


def _paste_with_alpha(canvas: Image.Image, image: Optional[Image.Image], xy: Tuple[int, int]) -> None:
    if image is None:
        return
    converted = image.convert("RGBA")
    canvas.alpha_composite(converted, dest=xy)


def _rounded_icon(image: Image.Image, size: int, radius: int = 10) -> Image.Image:
    resampling = getattr(Image, "Resampling", Image).LANCZOS
    source = image.convert("RGBA").resize((size, size), resampling)
    mask = Image.new("L", (size, size), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=radius, fill=255)
    result = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    result.paste(source, (0, 0), mask)
    return result


def _placeholder(size: Tuple[int, int], text: str = "?") -> Image.Image:
    image = Image.new("RGBA", size, (20, 37, 58, 255))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), radius=8, outline=PALETTE.border)
    _draw_text(draw, (size[0] // 2, size[1] // 2), text, _font(max(14, size[1] // 3)), PALETTE.muted, anchor="mm")
    return image


def _draw_progress_bar(
    draw: ImageDraw.ImageDraw,
    box: Tuple[int, int, int, int],
    ratio: float,
    color: Color,
    *,
    track: RGBA = PALETTE.track,
    radius: int = 4,
) -> None:
    x1, y1, x2, y2 = box
    ratio = max(0.0, min(1.0, ratio))
    draw.rounded_rectangle(box, radius=radius, fill=track)
    fill_width = int((x2 - x1) * ratio)
    if fill_width > 0:
        draw.rounded_rectangle((x1, y1, x1 + fill_width, y2), radius=radius, fill=color + (255,))


def _draw_badge(
    draw: ImageDraw.ImageDraw,
    center: Tuple[int, int],
    label: str,
    color: Color,
    *,
    width: int = 36,
    height: int = 32,
) -> None:
    x, y = center
    box = (x - width // 2, y - height // 2, x + width // 2, y + height // 2)
    draw.rounded_rectangle(box, radius=8, fill=color + (38,), outline=color + (210,), width=1)
    _draw_text(draw, center, label, _font(18), color, anchor="mm", stroke_width=1, stroke_fill=(0, 0, 0))


async def _load_image_safe(
    match: Any,
    image_type: str,
    name: Any,
    width: int,
    height: int,
    version: Optional[str] = None,
) -> Image.Image:
    if name in (None, "", 0, "0"):
        return _placeholder((width, height))
    try:
        kwargs: Dict[str, Any] = {"resize_x": width, "resize_y": height}
        if version is not None:
            kwargs["profil_version"] = version
        return (await get_image(image_type, name, match.session, **kwargs)).convert("RGBA")
    except Exception:
        # Certains champions ont historiquement demandé une capitalisation différente.
        if image_type == "champion":
            try:
                return (
                    await get_image(
                        image_type,
                        str(name).capitalize(),
                        match.session,
                        resize_x=width,
                        resize_y=height,
                        profil_version=version or match.version["n"]["champion"],
                    )
                ).convert("RGBA")
            except Exception:
                pass
        return _placeholder((width, height), "")
