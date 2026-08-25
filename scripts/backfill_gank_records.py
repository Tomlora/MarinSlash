"""Backfill des données de gank avec les règles V3 de phase de lane.

Le script :
- sélectionne les matchs Summoner's Rift éligibles dans ``matchs`` ;
- récupère le détail du match et la timeline complète via Riot Match-V5 ;
- rejoue le détecteur hybride avec les règles V3 : 0:00-13:59, succès strict,
  rappel amélioré des tentatives ratées ;
- reconstruit les deux perspectives (team 100 et team 200) ;
- remplace ``match_gank_events`` et met à jour/ajoute :
  ``match_gank_lane_stats``, ``match_gank_phase_stats`` et
  ``match_gank_summary`` via les méthodes de sauvegarde du détecteur.

Aucune migration dédiée au backfill n'est nécessaire. Les tables gank V2 doivent
cependant déjà posséder les colonnes enrichies utilisées par ``ganks_hybrid.py``.

Exemples :
    python scripts/backfill_gank_records.py --dry-run --season 15
    python scripts/backfill_gank_records.py --season 15 --limit 100
    python scripts/backfill_gank_records.py --match-id 1234567890 --force
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Iterable

import aiohttp
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fonctions.gestion_bdd import lire_bdd_perso
from fonctions.match import ganks_hybrid as ganks_hybrid_module
from fonctions.match.gank_laning_rules import (
    GANK_ALGORITHM_VERSION,
    GANK_WINDOW_END_MS,
    apply_laning_gank_rules,
    strict_detection_counts,
)
from fonctions.match.ganks_hybrid import HybridGankAnalysisMixin
from utils.params import api_key_lol, region


BACKFILL_VERSION = GANK_ALGORITHM_VERSION
DEFAULT_MODES = ("RANKED", "FLEX", "SWIFTPLAY")

# Les méthodes V2 sérialisent ``algorithm_version`` depuis le global du module.
ganks_hybrid_module.ALGORITHM_VERSION = GANK_ALGORITHM_VERSION


class BackfillGankAnalyzer(HybridGankAnalysisMixin):
    """Shim minimal permettant de rejouer le détecteur sans instancier MatchLol."""

    MIN_JUNGLER_DAMAGE_DELTA = 60
    MIN_LANE_ACTIVITY_WITH_POSITION = 100

    def __init__(self, match_id: str, match_detail: dict, timeline: dict, team_id: int):
        self.last_match = str(match_id)
        self.match_detail = match_detail
        self.data_timeline = timeline
        # ``analyze_ganks`` ne l'utilise qu'en fallback si team_id n'est pas fourni.
        self.thisId = 0 if int(team_id) == 100 else 5

    @staticmethod
    def _hybrid_detection_counts(ganks):
        return strict_detection_counts(ganks)

    def _collect_observed_ganks(self, jungler_id, team_id, enemy_jungler_id):
        raw = super()._collect_observed_ganks(
            jungler_id,
            team_id,
            enemy_jungler_id,
        )
        return apply_laning_gank_rules(raw)


def _as_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Normalise la forme historique renvoyée par ``lire_bdd_perso``."""
    if df is None or df.empty:
        return pd.DataFrame()
    if "match_id" in df.columns:
        return df.reset_index(drop=True)
    if "match_id" in df.index:
        return df.T.reset_index(drop=True)
    return df.reset_index(drop=True)


def _sql_list(values: Iterable[str]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def _riot_match_id(match_id: str) -> str:
    match_id = str(match_id)
    return match_id if "_" in match_id else f"EUW1_{match_id}"


async def _riot_get(
    session: aiohttp.ClientSession,
    path: str,
    retries: int = 3,
) -> dict:
    url = f"https://{str(region).lower()}.api.riotgames.com{path}"

    for attempt in range(retries):
        async with session.get(url, params={"api_key": api_key_lol}) as response:
            payload = await response.json(content_type=None)
            if response.status == 200:
                if not isinstance(payload, dict):
                    raise RuntimeError(f"Réponse Riot invalide sur {path}")
                return payload

            if response.status == 429 and attempt + 1 < retries:
                retry_after = response.headers.get("Retry-After", "2")
                try:
                    delay = max(1.0, float(retry_after))
                except (TypeError, ValueError):
                    delay = 2.0
                await asyncio.sleep(delay)
                continue

            raise RuntimeError(
                f"Riot HTTP {response.status} sur {path}: {payload}"
            )

    raise RuntimeError(f"Échec Riot après {retries} tentative(s) sur {path}")


async def get_match_detail(session: aiohttp.ClientSession, match_id: str) -> dict:
    riot_id = _riot_match_id(match_id)
    return await _riot_get(session, f"/lol/match/v5/matches/{riot_id}")


async def get_match_timeline(session: aiohttp.ClientSession, match_id: str) -> dict:
    riot_id = _riot_match_id(match_id)
    return await _riot_get(session, f"/lol/match/v5/matches/{riot_id}/timeline")


def load_matches(
    modes: list[str],
    seasons: list[int] | None,
    limit: int | None,
    force: bool,
    match_id: str | None,
) -> pd.DataFrame:
    season_filter = ""
    if seasons:
        season_filter = f"AND m.season IN ({', '.join(str(int(s)) for s in seasons)})"

    match_filter = ""
    if match_id:
        raw = str(match_id).replace("EUW1_", "")
        safe = raw.replace("'", "''")
        match_filter = f"AND CAST(m.match_id AS TEXT) = '{safe}'"

    limit_sql = f"LIMIT {int(limit)}" if limit else ""

    # Une perspective V3 par équipe, 3 lanes par perspective et 3 phases x
    # ally/enemy par perspective. Les événements peuvent légitimement être vides,
    # donc leur absence seule ne suffit pas à considérer un match incomplet.
    stale_filter = ""
    if not force:
        stale_filter = f"""
          AND (
                (
                    SELECT COUNT(DISTINCT s.team_id)
                    FROM match_gank_summary AS s
                    WHERE s.match_id = m.match_id
                      AND COALESCE(s.algorithm_version, 0) >= {BACKFILL_VERSION}
                ) < 2
                OR (
                    SELECT COUNT(*)
                    FROM match_gank_lane_stats AS l
                    WHERE l.match_id = m.match_id
                ) < 6
                OR (
                    SELECT COUNT(*)
                    FROM match_gank_phase_stats AS p
                    WHERE p.match_id = m.match_id
                ) < 12
                OR EXISTS (
                    SELECT 1
                    FROM match_gank_events AS e
                    WHERE e.match_id = m.match_id
                      AND (
                            COALESCE(e.algorithm_version, 0) < {BACKFILL_VERSION}
                            OR e.timestamp_ms >= {GANK_WINDOW_END_MS}
                      )
                )
          )
        """

    query = f"""
        SELECT
            m.match_id,
            MAX(m.mode) AS mode,
            MAX(m.season) AS season,
            COUNT(DISTINCT m.joueur) AS tracked_perspectives
        FROM matchs AS m
        INNER JOIN tracker AS t
            ON t.id_compte = m.joueur
        WHERE m.mode IN ({_sql_list(modes)})
          AND m.time >= 15
          AND m.records = TRUE
          AND t.save_records = TRUE
          AND t.banned = FALSE
          {season_filter}
          {match_filter}
          {stale_filter}
        GROUP BY m.match_id
        ORDER BY m.match_id
        {limit_sql}
    """
    return _as_rows(lire_bdd_perso(query, index_col=None))


def _validate_match_payload(match_detail: dict, timeline: dict) -> None:
    detail_participants = match_detail.get("info", {}).get("participants", [])
    timeline_frames = timeline.get("info", {}).get("frames", [])
    if len(detail_participants) != 10:
        raise ValueError(
            f"Détail Riot incomplet : {len(detail_participants)} participant(s)"
        )
    if len(timeline_frames) < 2:
        raise ValueError("Timeline Riot vide ou incomplète")

    junglers = [
        participant
        for participant in detail_participants
        if (
            participant.get("teamPosition")
            or participant.get("individualPosition")
        ) == "JUNGLE"
    ]
    teams = {int(player.get("teamId", 0)) for player in junglers}
    if teams != {100, 200}:
        raise ValueError("Impossible d'identifier les deux junglers Riot")


async def _analyze_perspective(
    match_id: str,
    match_detail: dict,
    timeline: dict,
    team_id: int,
) -> BackfillGankAnalyzer:
    analyzer = BackfillGankAnalyzer(match_id, match_detail, timeline, team_id)
    stats = await analyzer.analyze_ganks(team_id=team_id)
    if not isinstance(stats, dict) or stats.get("error"):
        raise RuntimeError(str(stats.get("error", "Analyse gank invalide")))
    return analyzer


async def recalculate_match(
    match_id: str,
    match_detail: dict,
    timeline: dict,
) -> tuple[int, int]:
    """Recalcule et persiste les quatre familles de tables gank pour un match."""
    _validate_match_payload(match_detail, timeline)

    # On calcule les deux perspectives avant toute écriture. Cela évite de
    # commencer le remplacement si l'analyse d'une des équipes échoue.
    perspective_100 = await _analyze_perspective(
        match_id, match_detail, timeline, 100
    )
    perspective_200 = await _analyze_perspective(
        match_id, match_detail, timeline, 200
    )

    # save_gank_data appelle successivement : summary, events, lane_stats,
    # phase_stats. ``events`` est global au match ; le second passage le remplace
    # avec la même détection mais vue depuis l'autre équipe, puis laisse les deux
    # équipes présentes dans la table.
    if not await perspective_100.save_gank_data():
        raise RuntimeError("Échec de sauvegarde de la perspective team 100")
    if not await perspective_200.save_gank_data():
        raise RuntimeError("Échec de sauvegarde de la perspective team 200")

    events_100 = len(perspective_100.ally_ganks)
    events_200 = len(perspective_100.enemy_ganks)
    return events_100, events_200


async def backfill(args: argparse.Namespace) -> None:
    matches = load_matches(
        args.modes,
        args.season,
        args.limit,
        args.force,
        args.match_id,
    )
    if matches.empty:
        print("Aucun match à retraiter.")
        return

    print(
        f"{len(matches)} match(s) à retraiter avec les règles gank V{BACKFILL_VERSION} "
        f"(<14:00)."
    )

    if args.dry_run:
        columns = ["match_id", "mode", "season", "tracked_perspectives"]
        print(matches[columns].to_string(index=False))
        return

    success = 0
    errors = 0
    total_events = 0
    timeout = aiohttp.ClientTimeout(total=120)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        for position, row in matches.iterrows():
            match_id = str(row["match_id"])
            print(
                f"[{position + 1}/{len(matches)}] {match_id} "
                f"({row.get('mode')} S{row.get('season')})"
            )

            try:
                match_detail = await get_match_detail(session, match_id)
                timeline = await get_match_timeline(session, match_id)
                blue_count, red_count = await recalculate_match(
                    match_id,
                    match_detail,
                    timeline,
                )
                event_count = blue_count + red_count
                total_events += event_count
                success += 1
                print(
                    f"  OK - {event_count} tentative(s) <14 min "
                    f"(blue {blue_count}, red {red_count})"
                )
            except Exception as error:
                errors += 1
                print(f"  ERREUR - {type(error).__name__}: {error}")

            if args.delay > 0 and position + 1 < len(matches):
                await asyncio.sleep(args.delay)

    print(
        f"Terminé : {success} succès, {errors} erreur(s), "
        f"{total_events} tentative(s) V{BACKFILL_VERSION} enregistrée(s)."
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Rejoue les timelines Riot et reconstruit les tables de ganks "
            "avec les règles V3 de phase de lane."
        )
    )
    parser.add_argument(
        "--modes",
        nargs="+",
        choices=DEFAULT_MODES,
        default=list(DEFAULT_MODES),
        help="Modes à retraiter.",
    )
    parser.add_argument(
        "--season",
        nargs="*",
        type=int,
        default=None,
        help="Saisons à retraiter. Sans option : toutes les saisons éligibles.",
    )
    parser.add_argument(
        "--match-id",
        type=str,
        default=None,
        help="Retraite un match précis (avec ou sans préfixe EUW1_).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Nombre maximal de matchs à traiter.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=3.0,
        help="Pause entre deux matchs, en secondes.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Retraite les matchs même si les quatre familles de tables semblent V3.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Affiche la sélection sans appeler Riot ni écrire en BDD.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    asyncio.run(backfill(parse_args()))
