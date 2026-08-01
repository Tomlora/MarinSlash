from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import pandas as pd
from sqlalchemy import text

from fonctions.gestion_bdd import engine
from fonctions.proplay_lolpros_override import canonical_player, ensure_profile_cache_table


@dataclass(frozen=True)
class TargetedLolprosRefreshResult:
    player: str
    discovered_accounts: int
    inserted_accounts: int
    total_accounts: int
    team: str | None
    role: str | None
    country: str | None


def apply_targeted_lolpros_refresh(
    player: str,
    accounts: pd.DataFrame,
    profile: dict[str, object],
    *,
    verified_at: datetime,
) -> TargetedLolprosRefreshResult:
    """Applique uniquement les données du joueur ciblé, dans une transaction."""

    with engine.begin() as conn:
        ensure_profile_cache_table(conn)
        conn.execute(
            text(
                "LOCK TABLE public.data_proplayers, public.data_acc_proplayers, "
                "public.data_proplayer_lolpros_profiles IN SHARE ROW EXCLUSIVE MODE"
            )
        )
        player_name = canonical_player(conn, player)

        next_index = int(
            conn.execute(
                text(
                    'SELECT COALESCE(MAX("index"), -1) + 1 '
                    'FROM public.data_acc_proplayers'
                )
            ).scalar_one()
        )
        inserted_accounts = 0

        for _, row in accounts.iterrows():
            riot_id = str(row.get("compte") or "").strip()
            region = str(row.get("region") or "EUW").strip().upper()
            if not riot_id:
                continue

            exists = conn.execute(
                text(
                    """
                    SELECT 1
                    FROM public.data_acc_proplayers
                    WHERE LOWER(joueur) = LOWER(:player)
                      AND LOWER(compte) = LOWER(:riot_id)
                      AND UPPER(region) = :region
                    LIMIT 1
                    """
                ),
                {"player": player_name, "riot_id": riot_id, "region": region},
            ).scalar_one_or_none()
            if exists is not None:
                continue

            conn.execute(
                text(
                    """
                    INSERT INTO public.data_acc_proplayers
                        ("index", joueur, compte, region)
                    VALUES
                        (:row_index, :player, :riot_id, :region)
                    """
                ),
                {
                    "row_index": next_index,
                    "player": player_name,
                    "riot_id": riot_id,
                    "region": region,
                },
            )
            next_index += 1
            inserted_accounts += 1

        team = profile.get("team_plug")
        role = profile.get("role")
        country = profile.get("Pays")
        conn.execute(
            text(
                """
                UPDATE public.data_proplayers
                SET team_plug = CASE
                        WHEN :team IS NOT NULL AND :team <> '' THEN :team
                        ELSE team_plug
                    END,
                    role = CASE
                        WHEN :role IS NOT NULL AND :role <> '' THEN :role
                        ELSE role
                    END,
                    "Pays" = CASE
                        WHEN :country IS NOT NULL AND :country <> '' THEN :country
                        ELSE "Pays"
                    END,
                    "update" = :verified_at
                WHERE LOWER(plug) = LOWER(:player)
                """
            ),
            {
                "team": team,
                "role": role,
                "country": country,
                "verified_at": verified_at,
                "player": player_name,
            },
        )

        total_accounts = int(
            conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM (
                        SELECT DISTINCT LOWER(compte), UPPER(region)
                        FROM public.data_acc_proplayers
                        WHERE LOWER(joueur) = LOWER(:player)
                    ) AS comptes_uniques
                    """
                ),
                {"player": player_name},
            ).scalar_one()
        )
        conn.execute(
            text(
                "UPDATE public.data_proplayers SET accounts = :count "
                "WHERE LOWER(plug) = LOWER(:player)"
            ),
            {"count": total_accounts, "player": player_name},
        )

        conn.execute(
            text(
                """
                UPDATE public.data_proplayer_lolpros_profiles
                SET team_plug = CASE
                        WHEN :team IS NOT NULL AND :team <> '' THEN :team
                        ELSE team_plug
                    END,
                    role = CASE
                        WHEN :role IS NOT NULL AND :role <> '' THEN :role
                        ELSE role
                    END,
                    "Pays" = CASE
                        WHEN :country IS NOT NULL AND :country <> '' THEN :country
                        ELSE "Pays"
                    END,
                    last_verified = :verified_at,
                    manual_override = TRUE
                WHERE LOWER(joueur) = LOWER(:player)
                """
            ),
            {
                "team": team,
                "role": role,
                "country": country,
                "verified_at": verified_at,
                "player": player_name,
            },
        )

    return TargetedLolprosRefreshResult(
        player=player_name,
        discovered_accounts=len(accounts),
        inserted_accounts=inserted_accounts,
        total_accounts=total_accounts,
        team=str(team).strip() if team is not None and str(team).strip() else None,
        role=str(role).strip() if role is not None and str(role).strip() else None,
        country=str(country).strip() if country is not None and str(country).strip() else None,
    )
