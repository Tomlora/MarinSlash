from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import text

from fonctions.gestion_bdd import engine


ROLE_VALUES = ("Top", "Jungle", "Mid", "ADC", "Support")
ROLE_ALIASES = {
    "top": "Top",
    "jungle": "Jungle",
    "jg": "Jungle",
    "mid": "Mid",
    "middle": "Mid",
    "adc": "ADC",
    "bot": "ADC",
    "support": "Support",
    "supp": "Support",
}

_REGION_PATTERN = re.compile(r"^[A-Z0-9]{2,6}$")
_EMPTY_VALUES = {"", "-", "none", "null", "n/a", "aucun", "aucune"}


class ManualProplayError(ValueError):
    """Erreur fonctionnelle affichable à l'utilisateur Discord."""


class PlayerNotFoundError(ManualProplayError):
    pass


class PlayerAlreadyExistsError(ManualProplayError):
    def __init__(self, player: str):
        super().__init__(f"Le joueur {player} existe déjà.")
        self.player = player


class AccountConflictError(ManualProplayError):
    def __init__(self, riot_id: str, region: str, owners: list[str]):
        owners_text = ", ".join(owners)
        super().__init__(
            f"Le Riot ID {riot_id} ({region}) est déjà associé à : {owners_text}."
        )
        self.riot_id = riot_id
        self.region = region
        self.owners = owners


@dataclass(frozen=True)
class ManualAccountResult:
    created: bool
    player: str
    riot_id: str
    region: str
    row_index: int
    account_count: int


@dataclass(frozen=True)
class ManualPlayerResult:
    player: str
    role: str
    team: str | None
    country: str | None
    riot_id: str | None
    region: str | None
    player_index: int
    account_index: int | None


def _normalize_required_text(value: object, *, label: str, max_length: int) -> str:
    if value is None:
        raise ManualProplayError(f"Le champ {label} est obligatoire.")

    normalized = str(value).strip()
    if not normalized:
        raise ManualProplayError(f"Le champ {label} est obligatoire.")
    if any(character in normalized for character in "\r\n\t"):
        raise ManualProplayError(f"Le champ {label} contient un caractère interdit.")
    if len(normalized) > max_length:
        raise ManualProplayError(
            f"Le champ {label} est trop long ({len(normalized)}/{max_length})."
        )
    return normalized


def normalize_player(value: object) -> str:
    return _normalize_required_text(value, label="joueur", max_length=64)


def normalize_optional_text(
    value: object,
    *,
    label: str,
    max_length: int = 100,
) -> str | None:
    if value is None:
        return None

    normalized = str(value).strip()
    if normalized.casefold() in _EMPTY_VALUES:
        return None
    if any(character in normalized for character in "\r\n\t"):
        raise ManualProplayError(f"Le champ {label} contient un caractère interdit.")
    if len(normalized) > max_length:
        raise ManualProplayError(
            f"Le champ {label} est trop long ({len(normalized)}/{max_length})."
        )
    return normalized


def normalize_role(value: object) -> str:
    raw_role = _normalize_required_text(value, label="rôle", max_length=20)
    role = ROLE_ALIASES.get(raw_role.casefold())
    if role is None:
        raise ManualProplayError(
            "Rôle invalide. Valeurs acceptées : Top, Jungle, Mid, ADC, Support."
        )
    return role


def normalize_region(value: object = "EUW") -> str:
    region = _normalize_required_text(value or "EUW", label="région", max_length=6).upper()
    if not _REGION_PATTERN.fullmatch(region):
        raise ManualProplayError(
            "Région invalide. Utilise un code de 2 à 6 caractères, par exemple EUW, KR ou NA."
        )
    return region


def normalize_riot_id(value: object) -> str:
    riot_id = _normalize_required_text(value, label="Riot ID", max_length=81)
    if riot_id.count("#") != 1:
        raise ManualProplayError(
            "Le Riot ID doit être complet et contenir un seul #, par exemple `Kiki#mates`."
        )

    game_name, tag_line = (part.strip() for part in riot_id.rsplit("#", 1))
    if not game_name or not tag_line:
        raise ManualProplayError(
            "Le Riot ID doit contenir un nom et un tag, par exemple `Kiki#mates`."
        )
    if len(game_name) > 64 or len(tag_line) > 16:
        raise ManualProplayError("Le nom ou le tag du Riot ID est anormalement long.")
    return f"{game_name}#{tag_line}"


def get_player_names() -> list[str]:
    with engine.connect() as conn:
        return [
            str(value)
            for value in conn.execute(
                text(
                    'SELECT plug FROM public.data_proplayers '
                    'WHERE plug IS NOT NULL ORDER BY LOWER(plug)'
                )
            ).scalars()
            if value is not None
        ]


def _canonical_player(conn, player: str) -> str:
    matches = [
        str(value)
        for value in conn.execute(
            text(
                'SELECT plug FROM public.data_proplayers '
                'WHERE LOWER(plug) = LOWER(:player) ORDER BY plug'
            ),
            {"player": player},
        ).scalars()
    ]
    if not matches:
        raise PlayerNotFoundError(f"Joueur introuvable : {player}.")
    if len(matches) > 1:
        raise ManualProplayError(
            "Plusieurs joueurs ne diffèrent que par la casse : " + ", ".join(matches)
        )
    return matches[0]


def _account_count(conn, player: str) -> int:
    value = conn.execute(
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
        {"player": player},
    ).scalar_one()
    return int(value)


def _account_owners(conn, riot_id: str, region: str) -> list[str]:
    return [
        str(value)
        for value in conn.execute(
            text(
                """
                SELECT DISTINCT joueur
                FROM public.data_acc_proplayers
                WHERE LOWER(compte) = LOWER(:riot_id)
                  AND UPPER(region) = :region
                ORDER BY joueur
                """
            ),
            {"riot_id": riot_id, "region": region},
        ).scalars()
    ]


def add_manual_account(player: object, riot_id: object, region: object = "EUW") -> ManualAccountResult:
    requested_player = normalize_player(player)
    normalized_riot_id = normalize_riot_id(riot_id)
    normalized_region = normalize_region(region)

    with engine.begin() as conn:
        conn.execute(
            text(
                "LOCK TABLE public.data_proplayers, public.data_acc_proplayers "
                "IN SHARE ROW EXCLUSIVE MODE"
            )
        )
        canonical_player = _canonical_player(conn, requested_player)

        existing = conn.execute(
            text(
                """
                SELECT "index"
                FROM public.data_acc_proplayers
                WHERE LOWER(joueur) = LOWER(:player)
                  AND LOWER(compte) = LOWER(:riot_id)
                  AND UPPER(region) = :region
                ORDER BY "index"
                LIMIT 1
                """
            ),
            {
                "player": canonical_player,
                "riot_id": normalized_riot_id,
                "region": normalized_region,
            },
        ).scalar_one_or_none()

        if existing is not None:
            account_count = _account_count(conn, canonical_player)
            return ManualAccountResult(
                created=False,
                player=canonical_player,
                riot_id=normalized_riot_id,
                region=normalized_region,
                row_index=int(existing),
                account_count=account_count,
            )

        owners = _account_owners(conn, normalized_riot_id, normalized_region)
        foreign_owners = [
            owner for owner in owners if owner.casefold() != canonical_player.casefold()
        ]
        if foreign_owners:
            raise AccountConflictError(
                normalized_riot_id,
                normalized_region,
                foreign_owners,
            )

        row_index = int(
            conn.execute(
                text(
                    'SELECT COALESCE(MAX("index"), -1) + 1 '
                    'FROM public.data_acc_proplayers'
                )
            ).scalar_one()
        )
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
                "row_index": row_index,
                "player": canonical_player,
                "riot_id": normalized_riot_id,
                "region": normalized_region,
            },
        )

        account_count = _account_count(conn, canonical_player)
        conn.execute(
            text(
                """
                UPDATE public.data_proplayers
                SET accounts = :account_count,
                    current = CASE
                        WHEN current IS NULL OR current = '' OR LOWER(current) = 'none'
                        THEN :region
                        ELSE current
                    END
                WHERE LOWER(plug) = LOWER(:player)
                """
            ),
            {
                "account_count": account_count,
                "region": normalized_region,
                "player": canonical_player,
            },
        )

    return ManualAccountResult(
        created=True,
        player=canonical_player,
        riot_id=normalized_riot_id,
        region=normalized_region,
        row_index=row_index,
        account_count=account_count,
    )


def add_manual_player(
    player: object,
    role: object,
    *,
    team: object = None,
    riot_id: object = None,
    region: object = "EUW",
    country: object = None,
) -> ManualPlayerResult:
    normalized_player = normalize_player(player)
    normalized_role = normalize_role(role)
    normalized_team = normalize_optional_text(team, label="équipe")
    normalized_country = normalize_optional_text(country, label="pays")
    normalized_riot_id = normalize_riot_id(riot_id) if riot_id is not None else None
    normalized_region = normalize_region(region) if normalized_riot_id else None

    with engine.begin() as conn:
        conn.execute(
            text(
                "LOCK TABLE public.data_proplayers, public.data_acc_proplayers "
                "IN SHARE ROW EXCLUSIVE MODE"
            )
        )

        existing_player = conn.execute(
            text(
                'SELECT plug FROM public.data_proplayers '
                'WHERE LOWER(plug) = LOWER(:player) LIMIT 1'
            ),
            {"player": normalized_player},
        ).scalar_one_or_none()
        if existing_player is not None:
            raise PlayerAlreadyExistsError(str(existing_player))

        if normalized_riot_id and normalized_region:
            owners = _account_owners(conn, normalized_riot_id, normalized_region)
            if owners:
                raise AccountConflictError(
                    normalized_riot_id,
                    normalized_region,
                    owners,
                )

        player_index = int(
            conn.execute(
                text(
                    'SELECT COALESCE(MAX("index"), -1) + 1 '
                    'FROM public.data_proplayers'
                )
            ).scalar_one()
        )
        account_index: int | None = None
        account_count = 1 if normalized_riot_id else 0

        conn.execute(
            text(
                """
                INSERT INTO public.data_proplayers (
                    "index", current, home, role, accounts, team_plug, plug,
                    "rankHigh", "rankHighNum", "rankHighLP", "rankHighLPNum",
                    "Pays", "update"
                )
                VALUES (
                    :player_index, :current, 'None', :role, :accounts, :team, :player,
                    'Challenger', 999999, 999999, 999999,
                    :country, :updated_at
                )
                """
            ),
            {
                "player_index": player_index,
                "current": normalized_region or "None",
                "role": normalized_role,
                "accounts": account_count,
                "team": normalized_team,
                "player": normalized_player,
                "country": normalized_country,
                "updated_at": datetime.now(timezone.utc),
            },
        )

        if normalized_riot_id and normalized_region:
            account_index = int(
                conn.execute(
                    text(
                        'SELECT COALESCE(MAX("index"), -1) + 1 '
                        'FROM public.data_acc_proplayers'
                    )
                ).scalar_one()
            )
            conn.execute(
                text(
                    """
                    INSERT INTO public.data_acc_proplayers
                        ("index", joueur, compte, region)
                    VALUES
                        (:account_index, :player, :riot_id, :region)
                    """
                ),
                {
                    "account_index": account_index,
                    "player": normalized_player,
                    "riot_id": normalized_riot_id,
                    "region": normalized_region,
                },
            )

    return ManualPlayerResult(
        player=normalized_player,
        role=normalized_role,
        team=normalized_team,
        country=normalized_country,
        riot_id=normalized_riot_id,
        region=normalized_region,
        player_index=player_index,
        account_index=account_index,
    )
