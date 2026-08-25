"""Ajout optionnel du focus des junglers dans les Insights du récap de game."""

from __future__ import annotations

from typing import Any, Dict, Optional


LANE_LABELS = {
    "top": "TOP",
    "mid": "MID",
    "bot": "BOT",
}


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _clear_focus_lane(
    by_lane: Dict[str, Dict[str, Any]],
    metric: str,
) -> Optional[tuple[str, int, int]]:
    """Retourne une lane seulement si le focus est assez net pour le récap.

    Règles :
    - au moins deux tentatives sur la lane principale ;
    - aucune égalité au maximum ;
    - la lane principale représente au moins 50 % des tentatives concernées.
    """

    counts = {
        lane: _safe_int((by_lane.get(lane) or {}).get(metric))
        for lane in ("top", "mid", "bot")
    }
    total = sum(counts.values())
    if total <= 0:
        return None

    max_count = max(counts.values())
    if max_count < 2:
        return None

    leaders = [lane for lane, count in counts.items() if count == max_count]
    if len(leaders) != 1:
        return None

    if max_count / total < 0.50:
        return None

    return leaders[0], max_count, total


def build_gank_pressure_insight(gank_stats: Any) -> str:
    """Construit une seule ligne d'Insight, ou une chaîne vide si non pertinente."""

    if not isinstance(gank_stats, dict) or gank_stats.get("error"):
        return ""

    by_lane = gank_stats.get("by_lane") or {}
    if not by_lane:
        return ""

    ally = _clear_focus_lane(by_lane, "ganks_made")
    enemy = _clear_focus_lane(by_lane, "ganks_received")
    if ally is None and enemy is None:
        return ""

    parts = []
    if ally is not None:
        lane, count, total = ally
        parts.append(
            f"🔵 Jungle alliée : appui **{LANE_LABELS.get(lane, lane.upper())}** "
            f"(**{count}/{total}** tentatives)"
        )
    if enemy is not None:
        lane, count, total = enemy
        parts.append(
            f"🔴 Jungle ennemie : appui **{LANE_LABELS.get(lane, lane.upper())}** "
            f"(**{count}/{total}** tentatives)"
        )

    return "\n🗺️ " + " · ".join(parts)


def install_gank_recap(match_class) -> None:
    """Ajoute l'insight après calcul_badges sans toucher au gros Cog principal."""

    original = match_class.calcul_badges
    if getattr(original, "_gank_recap_installed", False):
        return

    async def calcul_badges_with_gank_recap(self, sauvegarder):
        await original(self, sauvegarder)

        # analyze_ganks n'est exécuté que sur les modes compatibles et les games
        # suffisamment longues. L'absence de gank_stats est donc normale ailleurs.
        insight = build_gank_pressure_insight(getattr(self, "gank_stats", None))
        if not insight:
            return

        current = (
            str(getattr(self, "observations", "") or "")
            + str(getattr(self, "observations2", "") or "")
        )
        if insight.strip() in current:
            return

        current += insight
        # leagueoflegends.py fusionne ensuite observations + observations2 puis
        # redécoupe proprement ses fields à 1024 caractères.
        self.observations = current[:1000]
        self.observations2 = current[1000:]

    calcul_badges_with_gank_recap._gank_recap_installed = True
    match_class.calcul_badges = calcul_badges_with_gank_recap
