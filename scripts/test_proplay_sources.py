#!/usr/bin/env python3
"""Inspection manuelle des sources utilisées par data_proplayers.

Exemples :
    python scripts/test_proplay_sources.py --player Markoon
    python scripts/test_proplay_sources.py --league "Prime League 1st Division"
    python scripts/test_proplay_sources.py --league "La Ligue Française" --player Caliste
    python scripts/test_proplay_sources.py --player Markoon --accounts
    python scripts/test_proplay_sources.py --player Markoon --source lolpros --accounts
    python scripts/test_proplay_sources.py --player Markoon --source trackingthepros --accounts
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import re
import sys
from pathlib import Path

import pandas as pd
from aiohttp import ClientSession

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fonctions.proplay_sources import (  # noqa: E402
    DEFAULT_PRO_LEAGUES,
    fetch_leaguepedia_players,
    fetch_trackingthepros_accounts,
    fetch_trackingthepros_players,
)
from fonctions.lolpros import fetch_lolpros_accounts, merge_account_sources  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Teste Leaguepedia, LoLPros et TrackingThePros sans toucher à la BDD ni à l'API Riot."
    )
    parser.add_argument(
        "--league",
        action="append",
        dest="leagues",
        help="Championnat Leaguepedia. Répéter l'option pour en tester plusieurs.",
    )
    parser.add_argument(
        "--player",
        action="append",
        dest="players",
        help="Filtre joueur insensible à la casse. Répéter pour plusieurs joueurs.",
    )
    parser.add_argument(
        "--source",
        choices=("all", "leaguepedia", "lolpros", "trackingthepros"),
        default="all",
    )
    parser.add_argument(
        "--accounts",
        action="store_true",
        help="Teste les comptes LoLPros/TTP des joueurs affichés. Aucun appel Riot.",
    )
    parser.add_argument("--limit", type=int, default=50, help="Nombre max de lignes affichées.")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Relève immédiatement les erreurs HTTP/JSON au lieu de continuer.",
    )
    parser.add_argument(
        "--list-leagues",
        action="store_true",
        help="Affiche les championnats utilisés par le job puis quitte.",
    )
    return parser.parse_args()


def filter_players(frame: pd.DataFrame, players: list[str] | None) -> pd.DataFrame:
    if frame.empty or not players or "plug" not in frame.columns:
        return frame
    pattern = "|".join(re.escape(value) for value in players)
    return frame[frame["plug"].astype(str).str.contains(pattern, case=False, na=False, regex=True)]


def print_frame(title: str, frame: pd.DataFrame, limit: int) -> None:
    print(f"\n=== {title} ({len(frame)} ligne(s)) ===")
    if frame.empty:
        print("Aucune donnée.")
        return
    with pd.option_context("display.max_columns", None, "display.width", 240):
        print(frame.head(limit).to_string(index=False))


async def main() -> None:
    args = parse_args()

    if args.list_leagues:
        print("\n".join(DEFAULT_PRO_LEAGUES))
        return

    leagues = tuple(args.leagues) if args.leagues else DEFAULT_PRO_LEAGUES
    need_leaguepedia = args.source in ("all", "leaguepedia", "lolpros") or args.accounts
    leaguepedia = pd.DataFrame()
    matched_leaguepedia = pd.DataFrame()
    matched_ttp = pd.DataFrame()

    async with ClientSession() as session:
        if need_leaguepedia:
            leaguepedia = await fetch_leaguepedia_players(
                session, leagues, strict=args.strict
            )
            matched_leaguepedia = filter_players(leaguepedia, args.players)
            if args.source in ("all", "leaguepedia"):
                print_frame("Leaguepedia", matched_leaguepedia, args.limit)

        if args.source in ("all", "trackingthepros"):
            tracking = await fetch_trackingthepros_players(session, strict=args.strict)
            matched_ttp = filter_players(tracking, args.players)
            print_frame("TrackingThePros", matched_ttp, args.limit)

        if args.accounts or args.source == "lolpros":
            lolpros_targets = matched_leaguepedia.head(args.limit)
            lolpros_accounts = await fetch_lolpros_accounts(
                session,
                lolpros_targets["plug"].tolist() if not lolpros_targets.empty else [],
                strict=args.strict,
            )
            print_frame("Comptes LoLPros", lolpros_accounts, args.limit)
        else:
            lolpros_accounts = pd.DataFrame()

        if args.accounts and args.source in ("all", "trackingthepros"):
            if matched_ttp.empty:
                ttp_accounts = pd.DataFrame()
                print("\n=== Comptes TrackingThePros ===\nAucun joueur TTP à tester.")
            else:
                ttp_accounts = await fetch_trackingthepros_accounts(
                    session, matched_ttp["plug"].head(args.limit).tolist()
                )
                print_frame("Comptes TrackingThePros", ttp_accounts, args.limit)
        else:
            ttp_accounts = pd.DataFrame()

        if args.accounts and args.source == "all":
            combined = merge_account_sources(lolpros_accounts, ttp_accounts)
            print_frame("Comptes fusionnés", combined, args.limit)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    asyncio.run(main())
