"""Indice lisible de domination de lane.

Le score est volontairement borné et interprétable plutôt qu'entraîné :
50 représente une lane globalement neutre. Les écarts de gold/CS à 15 minutes
constituent l'essentiel du score ; les pics d'avance et les solokills n'apportent
qu'un bonus limité afin de ne pas survaloriser un événement tardif.
"""

from __future__ import annotations

from typing import Any


LANE_DOMINATION_VERSION = 1


def _number(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def calculate_lane_domination_score(
    gold_diff_15: Any,
    cs_diff_15: Any,
    cs_max_advantage: Any = 0,
    level_max_advantage: Any = 0,
    solo_kills: Any = 0,
) -> float:
    """Retourne un indice 0-100 de domination de lane.

    Pondération :
    - base neutre : 50 points ;
    - gold diff @15 : -25 à +25 points (1 500 gold = plafond) ;
    - CS diff @15 : -15 à +15 points (25 CS = plafond) ;
    - meilleur pic de CS : jusqu'à +5 ;
    - meilleur pic de niveau : jusqu'à +5 ;
    - solokills : jusqu'à +5.

    Les trois derniers termes sont uniquement des bonus. Ils servent de signal
    secondaire et ne peuvent pas masquer une grosse lane perdue à 15 minutes.
    """

    gold = _number(gold_diff_15)
    cs_15 = _number(cs_diff_15)
    cs_peak = max(0.0, _number(cs_max_advantage))
    level_peak = max(0.0, _number(level_max_advantage))
    solos = max(0.0, _number(solo_kills))

    score = 50.0
    score += _clip(gold / 60.0, -25.0, 25.0)
    score += _clip(cs_15 * 0.6, -15.0, 15.0)
    score += _clip(cs_peak * 0.10, 0.0, 5.0)
    score += _clip(level_peak * 2.5, 0.0, 5.0)
    score += _clip(solos * 2.5, 0.0, 5.0)

    return round(_clip(score, 0.0, 100.0), 1)


def lane_domination_label(score: Any) -> str:
    """Libellé court associé au score."""
    value = _number(score, 50.0)
    if value >= 80:
        return "Domination totale"
    if value >= 70:
        return "Lane dominante"
    if value >= 60:
        return "Avantage net"
    if value >= 45:
        return "Lane équilibrée"
    if value >= 30:
        return "En difficulté"
    return "Lane dominée"


def lane_domination_sql(
    scoring_alias: str = "mps",
    match_alias: str = "matchs",
) -> str:
    """Expression PostgreSQL strictement équivalente au calcul Python."""

    gold = f"COALESCE({scoring_alias}.gold_diff_15, 0)::DOUBLE PRECISION"
    cs15 = f"COALESCE({scoring_alias}.cs_diff_15, 0)::DOUBLE PRECISION"
    cs_peak = f"COALESCE({match_alias}.cs_max_avantage, 0)::DOUBLE PRECISION"
    level_peak = f"COALESCE({match_alias}.level_max_avantage, 0)::DOUBLE PRECISION"
    solos = f"COALESCE({match_alias}.solokills, 0)::DOUBLE PRECISION"

    return (
        "ROUND(LEAST(100.0, GREATEST(0.0, "
        "50.0 "
        f"+ LEAST(25.0, GREATEST(-25.0, ({gold}) / 60.0)) "
        f"+ LEAST(15.0, GREATEST(-15.0, ({cs15}) * 0.6)) "
        f"+ LEAST(5.0, GREATEST(0.0, ({cs_peak}) * 0.10)) "
        f"+ LEAST(5.0, GREATEST(0.0, ({level_peak}) * 2.5)) "
        f"+ LEAST(5.0, GREATEST(0.0, ({solos}) * 2.5))"
        "))::NUMERIC, 1)"
    )
