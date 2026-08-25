"""Règles communes pour les statistiques de gank en phase de lane.

Un gank Marin est désormais une tentative détectée avant 14:00. Les événements
postérieurs restent des combats/rotations mais ne sont plus comptés dans les
statistiques de gank.
"""

from __future__ import annotations

from typing import Any

GANK_WINDOW_START_MS = 0
GANK_WINDOW_END_MS = 14 * 60 * 1000
GANK_ALGORITHM_VERSION = 3

STRICT_SUCCESS_OUTCOME = "success"
TRADE_OUTCOME = "trade"
FAILED_OUTCOMES = {"failed", "jungler_death"}


def is_laning_gank_timestamp(timestamp_ms: Any) -> bool:
    """Retourne True pour une tentative située dans [0:00, 14:00[."""
    try:
        timestamp = int(float(timestamp_ms))
    except (TypeError, ValueError):
        return False
    return GANK_WINDOW_START_MS <= timestamp < GANK_WINDOW_END_MS


def is_strict_gank_success(outcome: Any) -> bool:
    """Un trade ne compte pas comme un gank réussi."""
    return str(outcome or "").lower() == STRICT_SUCCESS_OUTCOME


def install_gank_laning_rules(match_class) -> None:
    """Applique les règles V3 à la détection hybride déjà installée sur MatchLol.

    La V2 détectait bien des tentatives sans kill, mais exigeait au moins 120
    dégâts du jungler entre deux frames. Cela sous-détectait les passages qui
    forcent un flash / une retraite avec peu de dégâts et gonflait le taux de
    succès. On abaisse modérément ce seuil tout en conservant les contraintes
    d'activité de lane et de confiance déjà présentes dans le détecteur.
    """

    original_collect = getattr(match_class, "_collect_observed_ganks", None)
    if original_collect is None:
        return
    if getattr(original_collect, "_laning_rules_installed", False):
        return

    # Les méthodes de la détection hybride lisent ces seuils sur self.
    match_class.MIN_JUNGLER_DAMAGE_DELTA = min(
        int(getattr(match_class, "MIN_JUNGLER_DAMAGE_DELTA", 120) or 120), 60
    )
    match_class.MIN_LANE_ACTIVITY_WITH_POSITION = min(
        int(getattr(match_class, "MIN_LANE_ACTIVITY_WITH_POSITION", 150) or 150),
        100,
    )

    # Les méthodes copiées dynamiquement depuis ganks_hybrid continuent de lire
    # le global du module d'origine pour l'algorithm_version sauvegardé.
    try:
        from . import ganks_hybrid

        ganks_hybrid.ALGORITHM_VERSION = GANK_ALGORITHM_VERSION
    except Exception:
        pass

    # Le résumé V2 assimilait `not successful` à `failed`. Avec le succès strict,
    # un trade ne doit devenir ni un succès ni un échec.
    def strict_detection_counts(ganks):
        exact = sum(
            str(getattr(gank, "detection_source", "")) == "exact_event"
            for gank in ganks
        )
        return {
            "exact": exact,
            "inferred": len(ganks) - exact,
            "failed": sum(
                str(getattr(gank, "outcome", "")).lower() in FAILED_OUTCOMES
                for gank in ganks
            ),
            "high_confidence": sum(
                float(getattr(gank, "confidence", 0.0) or 0.0) >= 0.80
                for gank in ganks
            ),
        }

    match_class._hybrid_detection_counts = staticmethod(strict_detection_counts)

    def collect_laning_ganks(self, jungler_id, team_id, enemy_jungler_id):
        ganks = original_collect(self, jungler_id, team_id, enemy_jungler_id)
        filtered = []
        for gank in ganks:
            if not is_laning_gank_timestamp(getattr(gank, "timestamp", None)):
                continue

            # V2 utilisait kills_for > 0 : un trade 1 pour 1 devenait donc un
            # succès. En V3 seul outcome == success est un succès strict.
            gank.successful = is_strict_gank_success(getattr(gank, "outcome", None))
            filtered.append(gank)

        filtered.sort(key=lambda event: (event.timestamp, event.lane.value))
        for index, gank in enumerate(filtered, start=1):
            gank.gank_id = index
        return filtered

    collect_laning_ganks._laning_rules_installed = True
    collect_laning_ganks._original_collect_observed_ganks = original_collect
    match_class._collect_observed_ganks = collect_laning_ganks
