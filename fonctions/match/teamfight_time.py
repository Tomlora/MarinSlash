"""Utilitaires de représentation temporelle pour les combats."""

from __future__ import annotations


def timestamp_ms_to_mmss_decimal(timestamp_ms: int) -> float:
    """Encode un timestamp en ``MM.SS`` dans une colonne numérique.

    Ce n'est volontairement pas une minute décimale :
    ``658_000 ms`` devient ``10.58`` (10 min 58 s), et non ``10.97``.

    Les millisecondes sont tronquées à la seconde, comme l'affichage du chrono
    en jeu. Le format numérique existant de ``start_minute`` / ``end_minute``
    est ainsi conservé sans migration de type.
    """
    total_seconds = max(0, int(timestamp_ms)) // 1000
    minutes, seconds = divmod(total_seconds, 60)
    return round(minutes + seconds / 100, 2)
