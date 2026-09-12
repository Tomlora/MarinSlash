from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable, Sequence

from ..models import Competition, PlayerRole


@dataclass(frozen=True)
class ProviderPlayer:
    external_id: str
    handle: str
    role: PlayerRole
    team_external_id: str
    competition: Competition


@dataclass(frozen=True)
class ProviderTeam:
    external_id: str
    name: str
    short_name: str | None
    competition: Competition


@dataclass(frozen=True)
class ProviderMatch:
    external_id: str
    competition: Competition
    tournament: str | None
    scheduled_at_utc: datetime
    team1_external_id: str | None
    team2_external_id: str | None
    status: str = "scheduled"


@dataclass(frozen=True)
class ProviderPlayerGameStats:
    player_external_id: str
    team_external_id: str
    kills: int
    deaths: int
    assists: int
    cs: int
    triple_kills: int = 0
    quadra_kills: int = 0
    penta_kills: int = 0
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderTeamGameStats:
    team_external_id: str
    won: bool
    barons: int = 0
    dragons: int = 0
    towers: int = 0
    first_blood: bool = False
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderGame:
    external_game_id: str
    competition: Competition
    source: str
    schedule_external_id: str | None
    game_number: int | None
    started_at: datetime | None
    ended_at: datetime | None
    duration_seconds: int | None
    winner_team_external_id: str | None
    player_stats: Sequence[ProviderPlayerGameStats]
    team_stats: Sequence[ProviderTeamGameStats]


class ScheduleProvider(ABC):
    @abstractmethod
    async def fetch_schedule(
        self,
        competitions: Iterable[Competition],
        start: datetime,
        end: datetime,
    ) -> Sequence[ProviderMatch]:
        raise NotImplementedError


class PlayerProvider(ABC):
    @abstractmethod
    async def fetch_teams(
        self, competitions: Iterable[Competition]
    ) -> Sequence[ProviderTeam]:
        raise NotImplementedError

    @abstractmethod
    async def fetch_players(
        self, competitions: Iterable[Competition]
    ) -> Sequence[ProviderPlayer]:
        raise NotImplementedError


class ResultProvider(ABC):
    @abstractmethod
    async def fetch_completed_games(
        self,
        competitions: Iterable[Competition],
        since: datetime,
    ) -> Sequence[ProviderGame]:
        raise NotImplementedError
