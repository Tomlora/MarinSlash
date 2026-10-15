from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Competition(str, Enum):
    LEC = "LEC"
    LCS = "LCS"
    LFL = "LFL"


class PlayerRole(str, Enum):
    TOP = "TOP"
    JUNGLE = "JUNGLE"
    MID = "MID"
    ADC = "ADC"
    SUPPORT = "SUPPORT"


class RosterSlot(str, Enum):
    TOP = "TOP"
    JUNGLE = "JUNGLE"
    MID = "MID"
    ADC = "ADC"
    SUPPORT = "SUPPORT"
    BENCH = "BENCH"
    TEAM = "TEAM"


STARTER_SLOTS = (
    RosterSlot.TOP,
    RosterSlot.JUNGLE,
    RosterSlot.MID,
    RosterSlot.ADC,
    RosterSlot.SUPPORT,
)


@dataclass(frozen=True)
class PlayerAsset:
    player_id: int
    handle: str
    role: PlayerRole
    competition: Competition


@dataclass(frozen=True)
class TeamAsset:
    team_id: int
    name: str
    competition: Competition


@dataclass(frozen=True)
class RosterEntry:
    slot: RosterSlot
    player: Optional[PlayerAsset] = None
    team: Optional[TeamAsset] = None

    def __post_init__(self) -> None:
        asset_count = int(self.player is not None) + int(self.team is not None)
        if asset_count != 1:
            raise ValueError("A roster entry must contain exactly one asset")
        if self.slot == RosterSlot.TEAM and self.team is None:
            raise ValueError("TEAM slot requires a team asset")
        if self.slot != RosterSlot.TEAM and self.player is None:
            raise ValueError("Player slots require a player asset")
