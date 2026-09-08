"""Compatibility layer for TFT recaps across sets/patches.

The historical recap code in :mod:`cogs.tft` resolves translated trait names
against CommunityDragon's PBE snapshot.  That works for the current set, but an
older match can contain trait IDs that no longer exist on PBE and the recap then
fails on ``values[0]``.

This extension is loaded automatically with the other cogs.  It patches only the
two module-level data helpers used by ``stats_tft`` so the existing commands and
DB writes keep their current behaviour.
"""

from contextvars import ContextVar
import re
from typing import Iterable, Optional

import pandas as pd

import cogs.tft as tft_module


_match_context = ContextVar(
    "tft_match_version_context",
    default={"game_version": None, "trait_ids": ()},
)


def _communitydragon_patch(game_version: Optional[str]) -> Optional[str]:
    """Extract the CommunityDragon major.minor patch from Riot game_version."""
    if not game_version:
        return None

    match = re.search(r"(?<!\d)(\d{1,2})\.(\d{1,2})(?:\.|\b)", str(game_version))
    if not match:
        return None

    return f"{int(match.group(1))}.{int(match.group(2))}"


def _fallback_trait_name(trait_id: str) -> str:
    """Build a readable name when archived metadata is unavailable."""
    name = re.sub(
        r"^(?:TFTSet|TFT|Set)\d+[_-]?",
        "",
        str(trait_id),
        flags=re.IGNORECASE,
    )
    name = name.replace("_", " ").replace("-", " ")
    name = re.sub(r"(?<=[a-zà-ÿ])(?=[A-Z])", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name or str(trait_id)


def _extract_match_context(match_detail: pd.DataFrame) -> dict:
    """Collect the patch and every trait ID present in the returned match."""
    game_version = None
    trait_ids = []

    try:
        info = match_detail["info"]
        game_version = info.get("game_version")
        participants = info.get("participants", []) or []

        for participant in participants:
            for trait in participant.get("traits", []) or []:
                trait_id = trait.get("name")
                if trait_id and trait_id not in trait_ids:
                    trait_ids.append(trait_id)
    except (KeyError, TypeError, AttributeError):
        pass

    return {"game_version": game_version, "trait_ids": tuple(trait_ids)}


async def _get_versioned_traits(session, game_version: Optional[str], trait_ids: Iterable[str]):
    """Load trait metadata from the match patch, then fall back safely."""
    patch = _communitydragon_patch(game_version)
    versions = []

    if patch:
        versions.append(patch)

    # ``latest`` covers current live games; ``pbe`` keeps the old behaviour as a
    # final metadata source without making historical games depend on it.
    versions.extend(["latest", "pbe"])

    data = None
    seen_versions = set()

    for version in versions:
        if version in seen_versions:
            continue
        seen_versions.add(version)

        url = (
            f"https://raw.communitydragon.org/{version}/plugins/"
            "rcp-be-lol-game-data/global/fr_fr/v1/tfttraits.json"
        )

        try:
            async with session.get(url) as response:
                if response.status != 200:
                    continue

                candidate = await response.json(content_type=None)
                if isinstance(candidate, list):
                    data = candidate
                    break
        except Exception:
            # Metadata is optional for the recap.  We can still display the raw
            # Riot trait IDs if CommunityDragon is unavailable.
            continue

    if data is None:
        data = []

    known_ids = {
        item.get("trait_id")
        for item in data
        if isinstance(item, dict) and item.get("trait_id")
    }

    # ``stats_tft`` expects every lookup to return at least one row.  Inject a
    # readable local fallback for any trait absent from the archived snapshot.
    for trait_id in trait_ids:
        if trait_id not in known_ids:
            data.append(
                {
                    "trait_id": trait_id,
                    "display_name": _fallback_trait_name(trait_id),
                }
            )
            known_ids.add(trait_id)

    return data


def _apply_patch():
    if getattr(tft_module, "_version_agnostic_recap_patch", False):
        return

    original_matchtft_by_puuid = tft_module.matchtft_by_puuid

    async def matchtft_by_puuid(idgames: int, session, puuid=None):
        result = await original_matchtft_by_puuid(idgames, session, puuid)
        match_detail = result[0]

        if isinstance(match_detail, pd.DataFrame):
            _match_context.set(_extract_match_context(match_detail))
        else:
            _match_context.set({"game_version": None, "trait_ids": ()})

        return result

    async def get_data_trait(session):
        context = _match_context.get()
        return await _get_versioned_traits(
            session,
            context.get("game_version"),
            context.get("trait_ids", ()),
        )

    tft_module.matchtft_by_puuid = matchtft_by_puuid
    tft_module.get_data_trait = get_data_trait
    tft_module._version_agnostic_recap_patch = True


def setup(bot):
    # No extra Discord command is registered: this module only makes the
    # existing TFT recap version-aware.
    _apply_patch()
