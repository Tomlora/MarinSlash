"""External data providers for Fantasy LoL."""

from .base import PlayerProvider, ResultProvider, ScheduleProvider
from .oracles_elixir import OracleElixirPlayerProvider
from .schedule import (
    FallbackScheduleProvider,
    LeaguepediaScheduleProvider,
    RiotEsportsScheduleProvider,
)

__all__ = [
    "PlayerProvider",
    "ResultProvider",
    "ScheduleProvider",
    "OracleElixirPlayerProvider",
    "FallbackScheduleProvider",
    "LeaguepediaScheduleProvider",
    "RiotEsportsScheduleProvider",
]
