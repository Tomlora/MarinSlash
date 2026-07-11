"""Collecte et normalisation des données du récapitulatif moderne."""

from typing import Any, Dict, Mapping, Tuple

from fonctions.gestion_bdd import lire_bdd, lire_bdd_perso
from .image_modern_common import _as_float, _as_int, _safe_get


def _get_player_local_index(match: Any) -> int:
    this_id = _as_int(getattr(match, "thisId", 0))
    return this_id - 5 if this_id > 4 else this_id


def _get_rank(match: Any, index: int) -> int:
    try:
        return _as_int(match._get_player_rank(index), 5)
    except Exception:
        scores = list(getattr(match, "scores_liste", []) or [])
        if not scores or index >= len(scores):
            return 5
        sorted_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        return sorted_indices.index(index) + 1


def _get_player_summary(match: Any) -> Dict[str, Any]:
    """Charge les moyennes du joueur sur le champion/split actuel.

    La requête est volontairement indépendante de la table ``match_scoring`` pour
    éviter les duplications de lignes. Le MVP moyen vient de ``matchs.mvp`` qui
    reste renseigné par le rendu historique et par le pipeline de scoring.
    """
    time_min = 10 if getattr(match, "thisQ", "") == "ARAM" else 15
    query = """
        SELECT
            COUNT(*) AS nb_games,
            AVG(kills) AS kills,
            AVG(deaths) AS deaths,
            AVG(assists) AS assists,
            AVG(kp) AS kp,
            AVG(NULLIF(mvp, 0)) AS mvp,
            100.0 * AVG(CASE WHEN victoire THEN 1.0 ELSE 0.0 END) AS winrate
        FROM matchs
        WHERE joueur = :id_compte
          AND champion = :champion
          AND season = :season
          AND mode = :mode
          AND time > :time_min
          AND split = :split
    """
    try:
        data = lire_bdd_perso(
            query,
            format="dict",
            index_col=None,
            params={
                "id_compte": match.id_compte,
                "champion": match.thisChampName,
                "season": match.season,
                "mode": match.thisQ,
                "time_min": time_min,
                "split": match.split,
            },
        )
        row = data.get(0, {}) if isinstance(data, dict) else {}
    except Exception:
        row = {}

    kills = _as_float(row.get("kills"))
    deaths = _as_float(row.get("deaths"))
    assists = _as_float(row.get("assists"))
    kda = kills + assists if deaths <= 0 else (kills + assists) / deaths
    return {
        "games": _as_int(row.get("nb_games")),
        "kills": kills,
        "deaths": deaths,
        "assists": assists,
        "kp": _as_float(row.get("kp")),
        "mvp": _as_float(row.get("mvp")),
        "winrate": _as_float(row.get("winrate")),
        "kda": kda,
    }


def _get_daily_stats(match: Any) -> Tuple[int, int, int]:
    """Retourne les victoires, défaites et LP nets des dernières 24 heures."""
    table_name = f"ranked_aram_s{match.season}" if match.thisQ in ("ARAM", "CLASH ARAM") else f"suivi_s{match.season}"
    try:
        suivi = lire_bdd(table_name, "dict")
        row = suivi[match.id_compte]
        wins = _as_int(match.thisVictory) - _as_int(row.get("wins_jour"))
        losses = _as_int(match.thisLoose) - _as_int(row.get("losses_jour"))
    except Exception:
        wins, losses = 0, 0

    # ``ecart_lp`` est déjà enregistré pour chaque partie. Sa somme sur les
    # dernières 24 heures reste correcte même lors d'un changement de division.
    try:
        data = lire_bdd_perso(
            """
            SELECT COALESCE(SUM(ecart_lp), 0) AS lp_24h
            FROM matchs
            WHERE joueur = :id_compte
              AND mode = :mode
              AND datetime >= NOW() - INTERVAL '24 hours'
            """,
            format="dict",
            index_col=None,
            params={"id_compte": match.id_compte, "mode": match.thisQ},
        )
        lp_24h = _as_int(data.get(0, {}).get("lp_24h")) if isinstance(data, dict) else 0
    except Exception:
        lp_24h = 0

    return max(0, wins), max(0, losses), lp_24h


def _team_objectives(match: Any) -> Dict[str, int]:
    teams = getattr(match, "match_detail", {}).get("info", {}).get("teams", [])
    team_id = _as_int(getattr(match, "teamId", 100), 100)
    selected: Mapping[str, Any] = {}
    for team in teams:
        if _as_int(team.get("teamId")) == team_id:
            selected = team.get("objectives", {}) or {}
            break

    def count(name: str, fallback: int = 0) -> int:
        entry = selected.get(name, {}) if isinstance(selected, Mapping) else {}
        return _as_int(entry.get("kills"), fallback) if isinstance(entry, Mapping) else fallback

    return {
        "tower": count("tower", _as_int(getattr(match, "thisTowerTeam", 0))),
        "inhibitor": count("inhibitor", _as_int(getattr(match, "thisInhibTeam", 0))),
        "dragon": count("dragon", _as_int(getattr(match, "thisDragonTeam", 0))),
        "riftHerald": count("riftHerald", _as_int(getattr(match, "thisHeraldTeam", 0))),
        "baron": count("baron", _as_int(getattr(match, "thisBaronTeam", 0))),
        "horde": count("horde", _as_int(getattr(match, "thisHordeTeam", 0))),
        "elder": _as_int(getattr(match, "thisElderPerso", 0)),
    }


def _team_totals(match: Any, start: int) -> Dict[str, float]:
    indices = range(start, min(start + 5, getattr(match, "nb_joueur", 10)))
    damage = sum(_as_float(_safe_get(match.thisDamageListe, i)) for i in indices)
    tank = sum(
        _as_float(_safe_get(match.thisDamageTakenListe, i))
        + _as_float(_safe_get(match.thisDamageSelfMitigatedListe, i))
        for i in indices
    )
    vision = sum(_as_float(_safe_get(match.thisVisionListe, i)) for i in indices)
    kp_values = [_as_float(_safe_get(match.thisKPListe, i)) for i in indices]
    gold = sum(_as_float(_safe_get(match.thisGoldListe, i)) for i in indices)
    return {
        "gold": gold,
        "damage": damage,
        "vision": vision,
        "kp": sum(kp_values) / len(kp_values) if kp_values else 0,
        "tank": tank,
    }


def _participant_rank_text(match: Any, index: int) -> str:
    tier = str(_safe_get(getattr(match, "liste_tier", []), index, "UNRANKED") or "UNRANKED").upper()
    division = _safe_get(getattr(match, "liste_rank", []), index, "")
    lp = _as_int(_safe_get(getattr(match, "liste_lp", []), index, 0))
    if tier in ("MASTER", "GRANDMASTER", "CHALLENGER"):
        return f"{tier.title()} {lp} LP"
    if tier == "UNRANKED":
        return "Non classé"
    return f"{tier.title()} {division or ''}".strip()
