from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from io import StringIO
from typing import Iterable, Sequence

import pandas as pd
from aiohttp import ClientError, ClientSession, ClientTimeout

LOGGER = logging.getLogger(__name__)

LEAGUEPEDIA_API_URL = "https://lol.fandom.com/api.php"
TRACKINGTHEPROS_PLAYERS_URL = (
    "https://www.trackingthepros.com/d/list_players?filter_region=ALL&"
)
TRACKINGTHEPROS_PLAYER_URL = "https://www.trackingthepros.com/player/{player}/"

DEFAULT_PRO_LEAGUES = (
    "LoL EMEA Championship",
    "La Ligue Française",
    "La Ligue Française Division 2",
    "Iberian Cup",
    "Prime League 1st Division",
    "Prime League Pro Division",  # Ancien nom, conservé pour l'historique.
    "Turkish Championship League",
    "Ultraliga",
    "Arabian League",
    "Northern League of Legends Championship",
    "Esports Balkan League",
)

PROPLAYER_CORE_COLUMNS = (
    "current",
    "home",
    "role",
    "accounts",
    "team_plug",
    "plug",
    "rankHigh",
    "rankHighNum",
    "rankHighLP",
    "rankHighLPNum",
)

LEAGUEPEDIA_COLUMNS = ("plug", "Nom", "Pays", "Rôle", "Ligue", "team_plug")


def _clean_plug(series: pd.Series) -> pd.Series:
    return (
        series.astype("string")
        .str.replace(r"\s*\(.*?\)", "", regex=True)
        .str.strip()
    )


def _cargo_escape(value: str) -> str:
    return value.replace("'", "''")


async def fetch_leaguepedia_players(
    session: ClientSession,
    leagues: Sequence[str] = DEFAULT_PRO_LEAGUES,
    *,
    timeout_seconds: int = 30,
    strict: bool = False,
) -> pd.DataFrame:
    """Récupère les joueurs Leaguepedia championnat par championnat.

    Une erreur sur un championnat n'empêche pas les autres de remonter. Avec
    ``strict=True``, la première erreur est relancée, ce qui est pratique pour
    diagnostiquer une source depuis le script de test.
    """

    frames: list[pd.DataFrame] = []
    timeout = ClientTimeout(total=timeout_seconds)

    for league in leagues:
        params = {
            "action": "cargoquery",
            "tables": "Tournaments,TournamentPlayers,PlayerRedirects,Players",
            "fields": (
                "Players.Player,Players.Name,Players.Country,Players.Role,"
                "Tournaments.League,Players.Team"
            ),
            "where": (
                f"Tournaments.League in ('{_cargo_escape(league)}') "
                "and Players.Role in ('Top', 'Jungle', 'Mid', 'Bot', 'Support')"
            ),
            "join_on": (
                "Tournaments.OverviewPage=TournamentPlayers.OverviewPage,"
                "TournamentPlayers.Player=PlayerRedirects.AllName,"
                "PlayerRedirects.OverviewPage=Players.OverviewPage"
            ),
            "group_by": "Players.OverviewPage",
            "format": "json",
            "limit": "1000",
        }

        try:
            async with session.get(
                LEAGUEPEDIA_API_URL, params=params, timeout=timeout
            ) as response:
                response.raise_for_status()
                payload = await response.json(content_type=None)

            rows = [entry["title"] for entry in payload.get("cargoquery", [])]
            if not rows:
                LOGGER.warning("Leaguepedia: aucun joueur pour %s", league)
                continue

            frame = pd.DataFrame(rows)
            frame.rename(
                columns={
                    "Player": "plug",
                    "Name": "Nom",
                    "Country": "Pays",
                    "Role": "Rôle",
                    "League": "Ligue",
                    "Team": "team_plug",
                },
                inplace=True,
            )

            # Certains retours Cargo peuvent omettre une clé entièrement vide.
            frame = frame.reindex(columns=LEAGUEPEDIA_COLUMNS)
            frame["Ligue"] = frame["Ligue"].fillna(league)
            frames.append(frame)
        except (ClientError, asyncio.TimeoutError, ValueError, KeyError) as exc:
            LOGGER.warning("Leaguepedia KO pour %s: %s", league, exc)
            if strict:
                raise

    if not frames:
        return pd.DataFrame(columns=LEAGUEPEDIA_COLUMNS)

    result = pd.concat(frames, ignore_index=True)
    result["plug"] = _clean_plug(result["plug"])
    result["Rôle"] = result["Rôle"].replace({"Bot": "ADC"})
    result = result[result["plug"].notna() & result["plug"].ne("")]
    return result.drop_duplicates(subset="plug", keep="first").reset_index(drop=True)


async def fetch_trackingthepros_players(
    session: ClientSession,
    *,
    timeout_seconds: int = 30,
    strict: bool = False,
) -> pd.DataFrame:
    """Récupère la liste TTP sans rendre cette source obligatoire."""

    try:
        async with session.get(
            TRACKINGTHEPROS_PLAYERS_URL,
            timeout=ClientTimeout(total=timeout_seconds),
        ) as response:
            response.raise_for_status()
            payload = await response.json(content_type=None)

        rows = payload.get("data")
        if not isinstance(rows, list):
            raise ValueError("réponse TTP sans liste 'data'")

        frame = pd.DataFrame(rows)
        frame.rename(
            columns={
                "position": "role",
                "name_plug": "plug",
                "current_region": "current",
                "home_region": "home",
                "highest_lp": "rankHighLP",
                "highest_rank": "rankHighLPNum",
                "player_accounts": "accounts",
            },
            inplace=True,
        )
        frame = frame.reindex(columns=PROPLAYER_CORE_COLUMNS)
        frame["plug"] = _clean_plug(frame["plug"])
        frame = frame[frame["plug"].notna() & frame["plug"].ne("")]
        return frame.drop_duplicates(subset="plug", keep="last").reset_index(drop=True)
    except (ClientError, asyncio.TimeoutError, ValueError, KeyError) as exc:
        LOGGER.warning("TrackingThePros liste joueurs KO: %s", exc)
        if strict:
            raise
        return pd.DataFrame(columns=PROPLAYER_CORE_COLUMNS)


def parse_trackingthepros_accounts(html: str, player: str) -> pd.DataFrame:
    """Extrait les comptes TTP sans dépendre de l'index fixe d'une table HTML."""

    try:
        tables = pd.read_html(StringIO(html))
    except ValueError:
        return pd.DataFrame(columns=["joueur", "compte", "region"])

    account_series: pd.Series | None = None
    for table in tables:
        for column in table.columns:
            values = table[column].astype("string")
            if values.str.contains(r"\[[^\]]+\]|Inactive", regex=True, na=False).any():
                account_series = values
                break
        if account_series is not None:
            break

    if account_series is None:
        return pd.DataFrame(columns=["joueur", "compte", "region"])

    frame = pd.DataFrame({"compte": account_series.dropna()})
    frame = frame[~frame["compte"].str.contains("Inactive", case=False, na=False)]
    frame["region"] = frame["compte"].str.extract(r"\[(.*?)\]", expand=False)
    frame["compte"] = (
        frame["compte"]
        .str.replace(r"\[.*?\]", "", regex=True)
        .str.strip()
    )
    frame["joueur"] = player
    frame = frame[frame["compte"].ne("")]
    return frame[["joueur", "compte", "region"]].drop_duplicates()


async def fetch_trackingthepros_accounts(
    session: ClientSession,
    players: Iterable[str],
    *,
    timeout_seconds: int = 20,
    concurrency: int = 5,
) -> pd.DataFrame:
    """Récupère les comptes TTP en parallèle, avec erreurs isolées par joueur."""

    semaphore = asyncio.Semaphore(concurrency)
    timeout = ClientTimeout(total=timeout_seconds)

    async def fetch_one(player: str) -> pd.DataFrame:
        async with semaphore:
            try:
                async with session.get(
                    TRACKINGTHEPROS_PLAYER_URL.format(player=player), timeout=timeout
                ) as response:
                    response.raise_for_status()
                    html = await response.text()
                return parse_trackingthepros_accounts(html, player)
            except (ClientError, asyncio.TimeoutError, ValueError) as exc:
                LOGGER.warning("TrackingThePros comptes KO pour %s: %s", player, exc)
                return pd.DataFrame(columns=["joueur", "compte", "region"])

    unique_players = [
        player for player in dict.fromkeys(players) if isinstance(player, str) and player
    ]
    if not unique_players:
        return pd.DataFrame(columns=["joueur", "compte", "region"])

    frames = await asyncio.gather(*(fetch_one(player) for player in unique_players))
    frames = [frame for frame in frames if not frame.empty]
    if not frames:
        return pd.DataFrame(columns=["joueur", "compte", "region"])
    return pd.concat(frames, ignore_index=True).drop_duplicates()


def merge_proplayer_sources(
    existing: pd.DataFrame,
    tracking: pd.DataFrame,
    leaguepedia: pd.DataFrame,
    *,
    updated_at: datetime,
) -> pd.DataFrame:
    """Fusionne les sources en donnant la priorité roster à Leaguepedia.

    - L'historique BDD est conservé pour les joueurs absents des deux sources.
    - TTP enrichit les régions, comptes et rangs quand il répond.
    - Leaguepedia est prioritaire pour l'équipe, le rôle et le pays, et peut
      créer un joueur même si TTP est indisponible.
    """

    db_columns = list(PROPLAYER_CORE_COLUMNS) + ["Pays", "update"]

    def normalized(frame: pd.DataFrame) -> pd.DataFrame:
        if frame is None or frame.empty:
            return pd.DataFrame(columns=db_columns)
        result = frame.copy()
        if "plug" not in result.columns and result.index.name == "plug":
            result = result.reset_index()
        if "plug" not in result.columns:
            return pd.DataFrame(columns=db_columns)
        result["plug"] = _clean_plug(result["plug"])
        return result[result["plug"].notna() & result["plug"].ne("")]

    old = normalized(existing)
    if old.empty:
        merged = pd.DataFrame(columns=db_columns).set_index("plug")
    else:
        for column in db_columns:
            if column not in old.columns:
                old[column] = None
        merged = old[db_columns].drop_duplicates("plug", keep="last").set_index("plug")

    touched: set[str] = set()

    if tracking is not None and not tracking.empty:
        ttp = tracking.copy()
        ttp["plug"] = _clean_plug(ttp["plug"])
        for _, row in ttp.iterrows():
            plug = row["plug"]
            if pd.isna(plug) or not plug:
                continue
            if plug not in merged.index:
                merged.loc[plug, :] = None
            for column in PROPLAYER_CORE_COLUMNS:
                if column == "plug" or column not in row:
                    continue
                value = row[column]
                if pd.notna(value):
                    merged.at[plug, column] = value
            touched.add(str(plug))

    if leaguepedia is not None and not leaguepedia.empty:
        league = leaguepedia.copy()
        league["plug"] = _clean_plug(league["plug"])
        for _, row in league.iterrows():
            plug = row["plug"]
            if pd.isna(plug) or not plug:
                continue
            if plug not in merged.index:
                merged.loc[plug, :] = None
            mapping = {"Rôle": "role", "team_plug": "team_plug", "Pays": "Pays"}
            for source_column, target_column in mapping.items():
                value = row.get(source_column)
                if pd.notna(value) and value != "":
                    merged.at[plug, target_column] = value
            touched.add(str(plug))

    if merged.empty:
        return pd.DataFrame(columns=db_columns)

    for plug in touched:
        merged.at[plug, "update"] = updated_at

    result = merged.reset_index()
    result.rename(columns={result.columns[0]: "plug"}, inplace=True)
    return result[db_columns].reset_index(drop=True)
