from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlayerScoringRules:
    kill: float = 2.0
    death: float = -0.5
    assist: float = 1.5
    cs: float = 0.01
    triple: float = 2.0
    quadra: float = 5.0
    penta: float = 10.0
    ten_kill_or_assist: float = 2.0


@dataclass(frozen=True)
class TeamScoringRules:
    win: float = 2.0
    baron: float = 2.0
    dragon: float = 1.0
    first_blood: float = 2.0
    tower: float = 1.0
    win_under_30: float = 2.0


@dataclass(frozen=True)
class PlayerGameStats:
    kills: int = 0
    deaths: int = 0
    assists: int = 0
    cs: int = 0
    triple_kills: int = 0
    quadra_kills: int = 0
    penta_kills: int = 0


@dataclass(frozen=True)
class TeamGameStats:
    won: bool = False
    barons: int = 0
    dragons: int = 0
    towers: int = 0
    first_blood: bool = False
    duration_seconds: int | None = None


def score_player(
    stats: PlayerGameStats,
    rules: PlayerScoringRules = PlayerScoringRules(),
) -> float:
    score = (
        stats.kills * rules.kill
        + stats.deaths * rules.death
        + stats.assists * rules.assist
        + stats.cs * rules.cs
        + stats.triple_kills * rules.triple
        + stats.quadra_kills * rules.quadra
        + stats.penta_kills * rules.penta
    )
    if stats.kills >= 10 or stats.assists >= 10:
        score += rules.ten_kill_or_assist
    return round(score, 3)


def score_team(
    stats: TeamGameStats,
    rules: TeamScoringRules = TeamScoringRules(),
) -> float:
    score = (
        stats.barons * rules.baron
        + stats.dragons * rules.dragon
        + stats.towers * rules.tower
    )
    if stats.won:
        score += rules.win
    if stats.first_blood:
        score += rules.first_blood
    if stats.won and stats.duration_seconds is not None and stats.duration_seconds < 1800:
        score += rules.win_under_30
    return round(score, 3)
