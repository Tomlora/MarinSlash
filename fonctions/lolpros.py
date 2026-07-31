from __future__ import annotations

import asyncio
import logging
import re
from html.parser import HTMLParser
from typing import Iterable
from urllib.parse import urlparse

import pandas as pd
from aiohttp import ClientError, ClientSession, ClientTimeout

LOGGER = logging.getLogger(__name__)
LEAGUEPEDIA_API_URL = "https://lol.fandom.com/api.php"
ACCOUNT_COLUMNS = ("joueur", "compte", "region")
DEFAULT_HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
    )
}
RIOT_ID_RE = re.compile(r"^[^#\r\n]{1,32}#[A-Za-z0-9]{2,8}$")
META_DESCRIPTION_NAMES = {"description", "og:description", "twitter:description"}
LOLPROS_ROLE_MAP = {
    "top": "Top",
    "jungle": "Jungle",
    "mid": "Mid",
    "bot": "ADC",
    "adc": "ADC",
    "support": "Support",
}


def _normalize_riot_id(value: object) -> str | None:
    if value is None:
        return None
    candidate = " ".join(str(value).split()).strip()
    if RIOT_ID_RE.fullmatch(candidate):
        return candidate
    return None


def _riot_ids_from_description(value: object) -> list[str]:
    """Extrait les Riot IDs présents dans une meta description LOLPros.

    Exemple réel : ``Bot | South Korea | Player for Shifters |
    Right Hand#korea [Grandmaster 1936LP]``.
    """

    if value is None:
        return []

    result: list[str] = []
    for part in re.split(r"[|,\[\]<>]", str(value)):
        riot_id = _normalize_riot_id(part)
        if riot_id and riot_id not in result:
            result.append(riot_id)
    return result


class _LolprosAccountParser(HTMLParser):
    """Parse le panneau Accounts et les métadonnées du joueur courant.

    Scanner tous les Riot IDs de la page provoquerait des faux positifs car la fiche
    contient aussi les comptes de coéquipiers dans certains liens OP.GG. Les comptes
    sont donc limités à ``section#accounts``. Les meta descriptions, elles, décrivent
    le joueur courant et servent aussi à extraire rôle/pays/équipe sans requête réseau
    supplémentaire.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.accounts: list[str] = []
        self.meta_accounts: list[str] = []
        self.meta_descriptions: list[str] = []
        self.in_accounts_section = False
        self.accounts_section_depth = 0

    def _add_account(self, value: object) -> None:
        riot_id = _normalize_riot_id(value)
        if riot_id and riot_id not in self.accounts:
            self.accounts.append(riot_id)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)

        if tag == "section":
            if self.in_accounts_section:
                self.accounts_section_depth += 1
            elif attributes.get("id") == "accounts":
                self.in_accounts_section = True
                self.accounts_section_depth = 1

        if self.in_accounts_section:
            # Le compte sélectionné peut n'apparaître que dans le title du bouton OP.GG.
            self._add_account(attributes.get("title"))
            self._add_account(attributes.get("aria-label"))

        if tag == "meta":
            meta_name = attributes.get("name") or attributes.get("property")
            if meta_name in META_DESCRIPTION_NAMES:
                content = attributes.get("content")
                if content:
                    description = " ".join(content.split()).strip()
                    if description and description not in self.meta_descriptions:
                        self.meta_descriptions.append(description)
                for riot_id in _riot_ids_from_description(content):
                    if riot_id not in self.meta_accounts:
                        self.meta_accounts.append(riot_id)

    def handle_endtag(self, tag: str) -> None:
        if tag == "section" and self.in_accounts_section:
            self.accounts_section_depth -= 1
            if self.accounts_section_depth <= 0:
                self.in_accounts_section = False
                self.accounts_section_depth = 0

    def handle_data(self, data: str) -> None:
        if self.in_accounts_section:
            self._add_account(data)


def _empty_accounts() -> pd.DataFrame:
    return pd.DataFrame(columns=ACCOUNT_COLUMNS)


def _cargo_escape(value: str) -> str:
    return value.replace("'", "''")


def _normalize_lolpros_url(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    url = str(value).strip()
    if not url:
        return None
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"}:
        return None
    if hostname != "lolpros.gg" and not hostname.endswith(".lolpros.gg"):
        return None
    return url


def _parse_lolpros_description(description: str) -> dict[str, str | None]:
    """Transforme la description SSR LoLPros en métadonnées roster prudentes.

    Format observé : ``Bot | South Korea | Player for Shifters | Riot ID [...]``.
    Si le format change ou si l'équipe n'est pas explicitement présente, on retourne
    ``None`` pour ne jamais écraser une valeur BDD avec une supposition.
    """

    parts = [part.strip() for part in description.split("|") if part.strip()]
    role = None
    country = None
    team = None

    if parts:
        role = LOLPROS_ROLE_MAP.get(parts[0].casefold())
    if len(parts) >= 2 and not _normalize_riot_id(parts[1]):
        country = parts[1]

    for part in parts:
        match = re.fullmatch(r"Player\s+for\s+(.+)", part, flags=re.IGNORECASE)
        if match:
            candidate = match.group(1).strip()
            if candidate:
                team = candidate
            break

    return {"role": role, "Pays": country, "team_plug": team}


def parse_lolpros_profile_metadata(html: str) -> dict[str, str | None]:
    """Extrait rôle, pays et équipe du joueur depuis la fiche LOLPros.

    Aucune information n'est inventée : si aucune meta description au format attendu
    n'est disponible, les champs restent à ``None`` et la BDD existante est conservée.
    """

    parser = _LolprosAccountParser()
    parser.feed(html)

    for description in parser.meta_descriptions:
        metadata = _parse_lolpros_description(description)
        if any(metadata.values()):
            return metadata

    return {"role": None, "Pays": None, "team_plug": None}


def parse_lolpros_accounts(
    html: str,
    player: str,
    *,
    region: str = "EUW",
) -> pd.DataFrame:
    """Extrait tous les Riot IDs attribués au joueur sur sa fiche LOLPros.

    On conserve volontairement :
    - les comptes affichés dans le sélecteur Accounts ;
    - le compte actuellement sélectionné (notamment via le lien OP.GG) ;
    - tous les Riot IDs de ``Summoner Names``, même anciens.

    Le but est de maximiser la couverture de ``data_acc_proplayers`` : un ancien nom
    reste utile et il vaut mieux le conserver que considérer à tort le compte comme
    inactif. Les IDs des coéquipiers, présents ailleurs dans la page, sont exclus car
    le parsing principal est limité au ``section#accounts``.
    """

    parser = _LolprosAccountParser()
    parser.feed(html)

    accounts = list(parser.accounts)
    for riot_id in parser.meta_accounts:
        if riot_id not in accounts:
            accounts.append(riot_id)

    if not accounts:
        return _empty_accounts()

    return pd.DataFrame({"joueur": player, "compte": accounts, "region": region})


async def fetch_lolpros_urls(
    session: ClientSession,
    players: Iterable[str],
    *,
    timeout_seconds: int = 30,
    chunk_size: int = 50,
    strict: bool = False,
) -> pd.DataFrame:
    """Résout les URLs LoLPros via le champ ``Players.Lolpros`` de Leaguepedia."""

    unique_players = [
        player.strip()
        for player in dict.fromkeys(players)
        if isinstance(player, str) and player.strip()
    ]
    if not unique_players:
        return pd.DataFrame(columns=["plug", "Lolpros"])

    frames: list[pd.DataFrame] = []
    timeout = ClientTimeout(total=timeout_seconds)

    for start in range(0, len(unique_players), chunk_size):
        chunk = unique_players[start:start + chunk_size]
        quoted = ",".join(f"'{_cargo_escape(player)}'" for player in chunk)
        params = {
            "action": "cargoquery",
            "tables": "Players",
            "fields": "Players.Player,Players.Lolpros",
            "where": f"Players.Player IN ({quoted})",
            "format": "json",
            "limit": str(max(100, len(chunk) * 2)),
        }

        try:
            async with session.get(
                LEAGUEPEDIA_API_URL,
                params=params,
                timeout=timeout,
            ) as response:
                response.raise_for_status()
                payload = await response.json(content_type=None)

            rows = [entry["title"] for entry in payload.get("cargoquery", [])]
            if rows:
                frame = pd.DataFrame(rows).rename(
                    columns={"Player": "plug", "Lolpros": "Lolpros"}
                )
                frames.append(frame.reindex(columns=["plug", "Lolpros"]))
        except (ClientError, asyncio.TimeoutError, ValueError, KeyError) as exc:
            LOGGER.warning("Leaguepedia URLs LoLPros KO: %s", exc)
            if strict:
                raise

    if not frames:
        return pd.DataFrame(columns=["plug", "Lolpros"])

    result = pd.concat(frames, ignore_index=True)
    result["plug"] = result["plug"].astype("string").str.strip()
    result["Lolpros"] = result["Lolpros"].apply(_normalize_lolpros_url)
    result = result[result["plug"].notna() & result["Lolpros"].notna()]
    return result.drop_duplicates(subset="plug", keep="last").reset_index(drop=True)


async def fetch_lolpros_accounts(
    session: ClientSession,
    players: Iterable[str],
    *,
    timeout_seconds: int = 20,
    concurrency: int = 5,
    region: str = "EUW",
    strict: bool = False,
) -> pd.DataFrame:
    """Récupère les comptes LoLPros sans aucun appel à l'API Riot."""

    urls = await fetch_lolpros_urls(session, players, strict=strict)
    if urls.empty:
        return _empty_accounts()

    semaphore = asyncio.Semaphore(concurrency)
    timeout = ClientTimeout(total=timeout_seconds)

    async def fetch_one(player: str, url: str) -> pd.DataFrame:
        async with semaphore:
            try:
                async with session.get(
                    url,
                    timeout=timeout,
                    headers=DEFAULT_HTTP_HEADERS,
                ) as response:
                    response.raise_for_status()
                    html = await response.text()
                result = parse_lolpros_accounts(html, player, region=region)
                if result.empty:
                    LOGGER.warning("LoLPros: aucun Riot ID détecté pour %s", player)
                return result
            except (ClientError, asyncio.TimeoutError, ValueError) as exc:
                LOGGER.warning("LoLPros comptes KO pour %s: %s", player, exc)
                if strict:
                    raise
                return _empty_accounts()

    frames = await asyncio.gather(*(
        fetch_one(row["plug"], row["Lolpros"])
        for _, row in urls.iterrows()
    ))
    frames = [frame for frame in frames if not frame.empty]
    if not frames:
        return _empty_accounts()
    return pd.concat(frames, ignore_index=True).drop_duplicates()


def merge_account_sources(*sources: pd.DataFrame) -> pd.DataFrame:
    """Fusionne LoLPros/TTP sans modifier le schéma historique de la table."""

    frames: list[pd.DataFrame] = []
    for source in sources:
        if source is None or source.empty:
            continue
        frame = source.copy().reindex(columns=ACCOUNT_COLUMNS)
        frame = frame[frame["joueur"].notna() & frame["compte"].notna()]
        frame["joueur"] = frame["joueur"].astype(str).str.strip()
        frame["compte"] = frame["compte"].astype(str).str.strip()
        frame["region"] = frame["region"].fillna("EUW").astype(str).str.strip().str.upper()
        frame = frame[frame["joueur"].ne("") & frame["compte"].ne("")]
        frames.append(frame)

    if not frames:
        return _empty_accounts()

    return (
        pd.concat(frames, ignore_index=True)
        .drop_duplicates(subset=list(ACCOUNT_COLUMNS), keep="first")
        .reset_index(drop=True)
    )
