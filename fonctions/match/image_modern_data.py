"""Collecte et normalisation des données du récapitulatif moderne."""

from typing import Any, Dict, List, Mapping, Tuple

from fonctions.gestion_bdd import lire_bdd, lire_bdd_perso
from utils.lol import dict_rankid
from .image_modern_common import _as_float, _as_int, _safe_get


_DRAGON_TYPE_ALIASES = {
    "FIRE_DRAGON": "fire",
    "INFERNAL_DRAGON": "fire",
    "WATER_DRAGON": "water",
    "OCEAN_DRAGON": "water",
    "EARTH_DRAGON": "earth",
    "MOUNTAIN_DRAGON": "earth",
    "AIR_DRAGON": "air",
    "CLOUD_DRAGON": "air",
    "HEXTECH_DRAGON": "hextech",
    "CHEMTECH_DRAGON": "chemtech",
}


_APEX_RANK_ABBREVIATIONS = {
    "MASTER": "M",
    "GRANDMASTER": "GM",
    "CHALLENGER": "C",
}


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
    """Retourne victoires, défaites et variation de LP depuis le snapshot 24 h.

    Le calcul reproduit la logique de ``update_24h`` : comparaison avec
    ``LP_jour`` / ``tier_jour`` / ``rank_jour`` et correction de 100 LP par
    division franchie. Cela évite les erreurs liées à la somme des ``ecart_lp``
    partie par partie, notamment lors des promotions, rétrogradations ou parties
    enregistrées plusieurs fois.
    """
    table_name = (
        f"ranked_aram_s{match.season}"
        if match.thisQ in ("ARAM", "CLASH ARAM")
        else f"suivi_s{match.season}"
    )

    try:
        suivi = lire_bdd(table_name, "dict")
        row = suivi[match.id_compte]

        wins = _as_int(match.thisVictory) - _as_int(row.get("wins_jour"))
        losses = _as_int(match.thisLoose) - _as_int(row.get("losses_jour"))

        lp_old = _as_int(row.get("LP_jour", row.get("lp_jour", 0)))
        lp_new = _as_int(getattr(match, "thisLP", row.get("LP", row.get("lp", 0))))

        tier_old = str(row.get("tier_jour", row.get("tier", "")) or "").upper()
        rank_old = str(row.get("rank_jour", row.get("rank", "")) or "").upper()
        tier_new = str(getattr(match, "thisTier", row.get("tier", "")) or "").upper()
        rank_new = str(getattr(match, "thisRank", row.get("rank", "")) or "").upper()

        classement_old = f"{tier_old} {rank_old}".strip()
        classement_new = f"{tier_new} {rank_new}".strip()
        apex = {"MASTER I", "GRANDMASTER I", "CHALLENGER I"}

        old_rank_id = dict_rankid.get(classement_old)
        new_rank_id = dict_rankid.get(classement_new)

        if old_rank_id is None or new_rank_id is None or old_rank_id == new_rank_id:
            lp_24h = lp_new - lp_old
        elif old_rank_id > new_rank_id:
            # Rétrogradation : valeur nette négative.
            difrank = old_rank_id - new_rank_id
            if classement_old in apex:
                lp_24h = lp_new - lp_old
            else:
                lp_24h = -((100 * difrank) + lp_old - lp_new)
        else:
            # Promotion : valeur nette positive.
            difrank = new_rank_id - old_rank_id
            if classement_old in apex:
                lp_24h = lp_new - lp_old
            else:
                lp_24h = (100 * difrank) - lp_old + lp_new

        return max(0, wins), max(0, losses), lp_24h
    except Exception:
        return 0, 0, 0


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


def _team_dragon_types(match: Any) -> List[str]:
    """Retourne les dragons élémentaires pris par l'équipe, dans l'ordre.

    La timeline brute est utilisée afin que l'information reste disponible pour
    les modes où ``save_timeline_event`` n'est pas exécuté. L'Elder est exclu,
    puisqu'il dispose déjà de son propre compteur dans le résumé.
    """
    data_timeline = getattr(match, "data_timeline", {}) or {}
    if not isinstance(data_timeline, Mapping):
        return []

    info = data_timeline.get("info", {})
    frames = info.get("frames", []) if isinstance(info, Mapping) else []
    if not isinstance(frames, list):
        return []

    this_id = _as_int(getattr(match, "thisId", 0))
    fallback_team_id = 100 if this_id <= 4 else 200
    team_id = _as_int(getattr(match, "teamId", fallback_team_id), fallback_team_id)

    dragon_events = []
    for frame in frames:
        if not isinstance(frame, Mapping):
            continue

        events = frame.get("events", []) or []
        if not isinstance(events, list):
            continue

        for event in events:
            if not isinstance(event, Mapping):
                continue
            if event.get("type") != "ELITE_MONSTER_KILL":
                continue
            if event.get("monsterType") != "DRAGON":
                continue

            event_team_id = _as_int(
                event.get("killerTeamId") or event.get("teamId"),
                0,
            )
            if event_team_id != team_id:
                continue

            subtype = str(event.get("monsterSubType", "") or "").upper()
            dragon_type = _DRAGON_TYPE_ALIASES.get(subtype)
            if dragon_type is None:
                continue

            dragon_events.append((_as_int(event.get("timestamp", 0)), dragon_type))

    dragon_events.sort(key=lambda item: item[0])
    return [dragon_type for _, dragon_type in dragon_events]


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
    if tier in _APEX_RANK_ABBREVIATIONS:
        return f"{_APEX_RANK_ABBREVIATIONS[tier]} {lp} LP"
    if tier == "UNRANKED":
        return "Non classé"
    return f"{tier.title()} {division or ''}".strip()