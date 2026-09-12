"""Ajout optionnel du focus des junglers dans les Insights du récap de game."""

from __future__ import annotations

from typing import Any, Dict, Optional

try:
    from .gank_laning_rules import is_laning_gank_timestamp
except ImportError:  # Chargement direct par importlib dans les tests unitaires.
    def is_laning_gank_timestamp(timestamp_ms: Any) -> bool:
        try:
            timestamp = int(float(timestamp_ms))
        except (TypeError, ValueError):
            return False
        return 0 <= timestamp < 14 * 60 * 1000


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


def _event_timestamp(event: Dict[str, Any]) -> Any:
    return event.get("timestamp", event.get("timestamp_ms"))


def _by_lane_from_events(gank_stats: Dict[str, Any]) -> Dict[str, Dict[str, int]]:
    """Reconstruit les appuis <14 min depuis les événements si disponibles.

    Cette seconde barrière rend l'insight indépendant des agrégats ``by_lane`` :
    même si ceux-ci étaient un jour calculés sur une fenêtre plus large, le récap
    resterait strictement limité à la phase de lane.
    """

    events = gank_stats.get("events")
    if not isinstance(events, dict):
        return {}

    by_lane = {
        lane: {"ganks_made": 0, "ganks_received": 0}
        for lane in ("top", "mid", "bot")
    }
    has_event_payload = False

    for side, metric in (("ally", "ganks_made"), ("enemy", "ganks_received")):
        side_events = events.get(side)
        if not isinstance(side_events, list):
            continue
        has_event_payload = True
        for event in side_events:
            if not isinstance(event, dict):
                continue
            if not is_laning_gank_timestamp(_event_timestamp(event)):
                continue
            lane = str(event.get("lane") or "").lower()
            if lane in by_lane:
                by_lane[lane][metric] += 1

    return by_lane if has_event_payload else {}


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

    # Priorité aux événements : ils permettent d'appliquer explicitement <14:00.
    # Fallback sur by_lane pour les tests/anciens payloads sans liste d'événements.
    by_lane = _by_lane_from_events(gank_stats) or (gank_stats.get("by_lane") or {})
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

        # analyze_ganks est exécuté avant calcul_badges dans MatchLol.run().
        # En V3 ses événements sont déjà filtrés <14:00 ; build_gank_pressure_insight
        # réapplique malgré tout la fenêtre pour éviter toute régression future.
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
