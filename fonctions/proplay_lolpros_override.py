from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlparse, urlunparse

import pandas as pd
from aiohttp import ClientError, ClientSession, ClientTimeout
from sqlalchemy import text

from fonctions.gestion_bdd import engine
from fonctions.lolpros import (
    ACCOUNT_COLUMNS,
    DEFAULT_HTTP_HEADERS,
    parse_lolpros_accounts,
    parse_lolpros_profile_metadata,
)
from fonctions.proplay_manual import ManualProplayError, PlayerNotFoundError, normalize_player


PROFILE_CACHE_COLUMNS = (
    "joueur",
    "lolpros_url",
    "team_plug",
    "role",
    "Pays",
    "last_verified",
    "manual_override",
    "manual_updated_at",
)


class LolprosManualRefreshError(ManualProplayError):
    """L'URL est enregistrée, mais son rafraîchissement immédiat a échoué."""


@dataclass(frozen=True)
class ManualLolprosUrlResult:
    player: str
    url: str
    previous_url: str | None
    changed: bool
    updated_at: datetime


def is_manual_override(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if value is None or pd.isna(value):
        return False
    return str(value).strip().casefold() in {"1", "true", "t", "yes", "y", "oui"}


def normalize_lolpros_profile_url(value: object) -> str:
    if value is None:
        raise ManualProplayError("L'URL LoLPros est obligatoire.")

    raw_url = str(value).strip()
    if not raw_url:
        raise ManualProplayError("L'URL LoLPros est obligatoire.")
    if any(character in raw_url for character in "\r\n\t"):
        raise ManualProplayError("L'URL LoLPros contient un caractère interdit.")
    if "://" not in raw_url:
        raw_url = f"https://{raw_url}"

    parsed = urlparse(raw_url)
    hostname = (parsed.hostname or "").lower()
    if hostname == "www.lolpros.gg":
        hostname = "lolpros.gg"
    if hostname != "lolpros.gg":
        raise ManualProplayError("L'URL doit pointer vers le domaine `lolpros.gg`.")

    parts = [part for part in parsed.path.rstrip("/").split("/") if part]
    if len(parts) != 2 or parts[0].casefold() != "player" or not parts[1]:
        raise ManualProplayError(
            "L'URL doit être une fiche joueur, par exemple "
            "`https://lolpros.gg/player/paduck`."
        )

    return urlunparse(("https", "lolpros.gg", f"/player/{parts[1]}", "", "", ""))


def ensure_profile_cache_table(conn) -> None:
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS public.data_proplayer_lolpros_profiles (
                joueur TEXT,
                lolpros_url TEXT,
                team_plug TEXT,
                role TEXT,
                "Pays" TEXT,
                last_verified TIMESTAMP WITH TIME ZONE,
                manual_override BOOLEAN NOT NULL DEFAULT FALSE,
                manual_updated_at TIMESTAMP WITH TIME ZONE
            )
            """
        )
    )
    conn.execute(
        text(
            "ALTER TABLE public.data_proplayer_lolpros_profiles "
            "ADD COLUMN IF NOT EXISTS manual_override BOOLEAN NOT NULL DEFAULT FALSE"
        )
    )
    conn.execute(
        text(
            "ALTER TABLE public.data_proplayer_lolpros_profiles "
            "ADD COLUMN IF NOT EXISTS manual_updated_at TIMESTAMP WITH TIME ZONE"
        )
    )


def canonical_player(conn, requested_player: str) -> str:
    matches = [
        str(value)
        for value in conn.execute(
            text(
                "SELECT plug FROM public.data_proplayers "
                "WHERE LOWER(plug) = LOWER(:player) ORDER BY plug"
            ),
            {"player": requested_player},
        ).scalars()
    ]
    if not matches:
        raise PlayerNotFoundError(f"Joueur introuvable : {requested_player}.")
    if len(matches) > 1:
        raise ManualProplayError(
            "Plusieurs joueurs ne diffèrent que par la casse : " + ", ".join(matches)
        )
    return matches[0]


def set_manual_lolpros_url(player: object, url: object) -> ManualLolprosUrlResult:
    requested_player = normalize_player(player)
    normalized_url = normalize_lolpros_profile_url(url)
    updated_at = datetime.now(timezone.utc)

    with engine.begin() as conn:
        ensure_profile_cache_table(conn)
        conn.execute(
            text(
                "LOCK TABLE public.data_proplayers, "
                "public.data_proplayer_lolpros_profiles IN SHARE ROW EXCLUSIVE MODE"
            )
        )
        player_name = canonical_player(conn, requested_player)
        previous = conn.execute(
            text(
                """
                SELECT lolpros_url, team_plug, role, "Pays", last_verified
                FROM public.data_proplayer_lolpros_profiles
                WHERE LOWER(joueur) = LOWER(:player)
                ORDER BY manual_override DESC, last_verified DESC NULLS LAST
                LIMIT 1
                """
            ),
            {"player": player_name},
        ).mappings().first()

        previous_url = str(previous["lolpros_url"]) if previous and previous["lolpros_url"] else None
        conn.execute(
            text(
                "DELETE FROM public.data_proplayer_lolpros_profiles "
                "WHERE LOWER(joueur) = LOWER(:player)"
            ),
            {"player": player_name},
        )
        conn.execute(
            text(
                """
                INSERT INTO public.data_proplayer_lolpros_profiles (
                    joueur, lolpros_url, team_plug, role, "Pays", last_verified,
                    manual_override, manual_updated_at
                ) VALUES (
                    :player, :url, :team, :role, :country, :last_verified,
                    TRUE, :updated_at
                )
                """
            ),
            {
                "player": player_name,
                "url": normalized_url,
                "team": previous["team_plug"] if previous else None,
                "role": previous["role"] if previous else None,
                "country": previous["Pays"] if previous else None,
                "last_verified": previous["last_verified"] if previous else None,
                "updated_at": updated_at,
            },
        )

    return ManualLolprosUrlResult(
        player=player_name,
        url=normalized_url,
        previous_url=previous_url,
        changed=previous_url != normalized_url,
        updated_at=updated_at,
    )


def manual_profile_rows(cache: pd.DataFrame | None) -> pd.DataFrame:
    if cache is None or cache.empty:
        return pd.DataFrame(columns=PROFILE_CACHE_COLUMNS)
    if not {"joueur", "lolpros_url", "manual_override"}.issubset(cache.columns):
        return pd.DataFrame(columns=PROFILE_CACHE_COLUMNS)

    frame = cache.copy()
    frame = frame[frame["manual_override"].map(is_manual_override)]
    frame = frame[
        frame["joueur"].notna()
        & frame["lolpros_url"].notna()
        & frame["joueur"].astype(str).str.strip().ne("")
        & frame["lolpros_url"].astype(str).str.strip().ne("")
    ]
    return frame.reset_index(drop=True)


def apply_manual_profile_overrides(
    leaguepedia_profiles: pd.DataFrame | None,
    cache: pd.DataFrame | None,
) -> pd.DataFrame:
    """Place les URLs manuelles devant Leaguepedia pour la collecte nocturne."""

    if leaguepedia_profiles is None or leaguepedia_profiles.empty:
        effective = pd.DataFrame(columns=["plug", "Lolpros"])
    else:
        effective = leaguepedia_profiles.copy()
        if "plug" not in effective.columns:
            effective["plug"] = None
        if "Lolpros" not in effective.columns:
            effective["Lolpros"] = None

    for _, row in manual_profile_rows(cache).iterrows():
        player = str(row["joueur"]).strip()
        url = normalize_lolpros_profile_url(row["lolpros_url"])
        matches = effective["plug"].astype("string").str.strip().str.casefold().eq(player.casefold())
        if matches.any():
            effective.loc[matches, "Lolpros"] = url
        else:
            new_row = {column: None for column in effective.columns}
            new_row.update({"plug": player, "Lolpros": url})
            effective = pd.concat([effective, pd.DataFrame([new_row])], ignore_index=True)

    return effective


def merge_profile_cache_preserving_manual(
    existing: pd.DataFrame | None,
    resolved_profiles: pd.DataFrame | None,
    *,
    verified_at: datetime,
) -> pd.DataFrame:
    """Actualise le cache sans jamais remplacer une URL marquée manuelle."""

    by_key: dict[str, dict[str, object]] = {}
    if existing is not None and not existing.empty and "joueur" in existing.columns:
        for _, row in existing.iterrows():
            player = row.get("joueur")
            if player is None or pd.isna(player) or not str(player).strip():
                continue
            record = {column: row.get(column) for column in PROFILE_CACHE_COLUMNS}
            record["joueur"] = str(player).strip()
            record["manual_override"] = is_manual_override(record.get("manual_override"))
            key = record["joueur"].casefold()
            previous = by_key.get(key)
            if previous is None or (
                record["manual_override"] and not is_manual_override(previous.get("manual_override"))
            ):
                by_key[key] = record

    if resolved_profiles is not None and not resolved_profiles.empty:
        for _, row in resolved_profiles.iterrows():
            player = row.get("joueur")
            if player is None or pd.isna(player) or not str(player).strip():
                continue
            player_name = str(player).strip()
            key = player_name.casefold()
            previous = by_key.get(key, {})
            manual = is_manual_override(previous.get("manual_override"))
            record = {column: previous.get(column) for column in PROFILE_CACHE_COLUMNS}
            record["joueur"] = player_name

            discovered_url = row.get("lolpros_url")
            if not manual and discovered_url is not None and not pd.isna(discovered_url):
                record["lolpros_url"] = str(discovered_url).strip()
            for column in ("team_plug", "role", "Pays"):
                value = row.get(column)
                if value is not None and not pd.isna(value) and str(value).strip():
                    record[column] = value

            record["last_verified"] = verified_at
            record["manual_override"] = manual
            if not manual:
                record["manual_updated_at"] = None
            by_key[key] = record

    if not by_key:
        return pd.DataFrame(columns=PROFILE_CACHE_COLUMNS)

    result = pd.DataFrame(by_key.values())
    for column in PROFILE_CACHE_COLUMNS:
        if column not in result.columns:
            result[column] = None
    result["manual_override"] = result["manual_override"].map(is_manual_override)
    return result[list(PROFILE_CACHE_COLUMNS)].reset_index(drop=True)


async def fetch_exact_lolpros_profile(
    session: ClientSession,
    player: str,
    url: str,
    *,
    timeout_seconds: int = 20,
    region: str = "EUW",
) -> tuple[pd.DataFrame, dict[str, object] | None]:
    """Télécharge uniquement l'URL manuelle, sans fallback vers un slug deviné."""

    normalized_url = normalize_lolpros_profile_url(url)
    try:
        async with session.get(
            normalized_url,
            timeout=ClientTimeout(total=timeout_seconds),
            headers=DEFAULT_HTTP_HEADERS,
        ) as response:
            if response.status == 429:
                retry_after = response.headers.get("Retry-After")
                suffix = f" Réessaie dans environ {retry_after} s." if retry_after else ""
                raise LolprosManualRefreshError("LoLPros est temporairement rate-limité." + suffix)
            if response.status == 404:
                raise LolprosManualRefreshError(
                    "La fiche LoLPros renvoie HTTP 404. Vérifie l'URL saisie."
                )
            response.raise_for_status()
            html = await response.text()
    except LolprosManualRefreshError:
        raise
    except (ClientError, TimeoutError) as exc:
        raise LolprosManualRefreshError(
            f"Impossible de télécharger la fiche LoLPros : {exc}"
        ) from exc

    accounts = parse_lolpros_accounts(html, player, region=region)
    metadata = parse_lolpros_profile_metadata(html)
    if accounts.empty and not any(metadata.values()):
        return pd.DataFrame(columns=ACCOUNT_COLUMNS), None

    return accounts, {
        "joueur": player,
        "lolpros_url": normalized_url,
        "team_plug": metadata.get("team_plug"),
        "role": metadata.get("role"),
        "Pays": metadata.get("Pays"),
    }
