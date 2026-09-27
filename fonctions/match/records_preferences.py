"""Préférences d'affichage par utilisateur Discord, indépendantes des snapshots."""
import logging
from dataclasses import dataclass

from fonctions.gestion_bdd import lire_bdd_perso, requete_perso_bdd
from fonctions.match.records_display import RecordsCollector

log = logging.getLogger(__name__)
SCOPES = ("alltime", "general", "perso")
LAYOUTS = ("compact", "sections")
CREATE_PREFERENCES_SQL = """
CREATE TABLE IF NOT EXISTS records_preferences (
    discord BIGINT PRIMARY KEY,
    layout VARCHAR(16) NOT NULL DEFAULT 'compact'
        CHECK (layout IN ('compact', 'sections')),
    show_alltime BOOLEAN NOT NULL DEFAULT TRUE,
    show_season BOOLEAN NOT NULL DEFAULT TRUE,
    show_personal BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
"""


@dataclass(frozen=True)
class RecordPreferences:
    layout: str = "compact"
    scopes: tuple = SCOPES


def load_preferences(discord_id, strict=False):
    """Sans préférence (ou migration indisponible), conserver PR42 et les 3 scopes."""
    if discord_id is None:
        return RecordPreferences()
    try:
        # Éviter une requête en erreur tant que la table n'a pas été créée.
        exists = lire_bdd_perso(
            "SELECT to_regclass('public.records_preferences') AS table_name",
            index_col=None,
        ).T
        if exists.empty or not exists.iloc[0]["table_name"]:
            return RecordPreferences()
        rows = lire_bdd_perso(
            "SELECT layout, show_alltime, show_season, show_personal "
            "FROM records_preferences WHERE discord = :discord",
            index_col=None, params={"discord": int(discord_id)},
        ).T
        if rows.empty:
            return RecordPreferences()
        row = rows.iloc[0]
        return RecordPreferences(
            layout=row["layout"] if row["layout"] in LAYOUTS else "compact",
            scopes=tuple(scope for scope, column in zip(
                SCOPES, ("show_alltime", "show_season", "show_personal")
            ) if bool(row[column])),
        )
    except Exception as error:
        sqlstate = getattr(getattr(error, "orig", error), "sqlstate", None) or getattr(
            getattr(error, "orig", error), "pgcode", None
        )
        if sqlstate == "42P01":  # Pas encore de préférences créées sur cette installation.
            return RecordPreferences()
        if strict:
            raise
        log.warning("Préférences records indisponibles, valeurs par défaut utilisées", exc_info=True)
        return RecordPreferences()


def load_account_preferences(joueur):
    """Le récap public suit les choix du propriétaire du compte tracker."""
    try:
        rows = lire_bdd_perso(
            "SELECT discord FROM tracker WHERE id_compte = :joueur",
            index_col=None, params={"joueur": int(joueur)},
        ).T
        return load_preferences(int(rows.iloc[0]["discord"])) if not rows.empty else RecordPreferences()
    except Exception:
        log.warning("Propriétaire du compte %s indisponible", joueur, exc_info=True)
        return RecordPreferences()


def save_preferences(discord_id, layout=None, alltime=None, saison=None, perso=None):
    """Modification partielle atomique : un booléen False reste bien désactivé."""
    if layout is not None and layout not in LAYOUTS:
        raise ValueError("Format de records inconnu.")
    for value in (alltime, saison, perso):
        if value is not None and not isinstance(value, bool):
            raise ValueError("Les catégories doivent être activées ou désactivées.")
    requete_perso_bdd(CREATE_PREFERENCES_SQL)
    requete_perso_bdd(
        """
        INSERT INTO records_preferences (discord, layout, show_alltime, show_season, show_personal)
        VALUES (:discord, COALESCE(:layout, 'compact'), COALESCE(:alltime, TRUE),
                COALESCE(:saison, TRUE), COALESCE(:perso, TRUE))
        ON CONFLICT (discord) DO UPDATE SET
            layout = COALESCE(:layout, records_preferences.layout),
            show_alltime = COALESCE(:alltime, records_preferences.show_alltime),
            show_season = COALESCE(:saison, records_preferences.show_season),
            show_personal = COALESCE(:perso, records_preferences.show_personal),
            updated_at = NOW()
        """,
        {"discord": int(discord_id), "layout": layout, "alltime": alltime,
         "saison": saison, "perso": perso},
    )


def filter_records(collector, preferences):
    """Filtrer une copie : le snapshot enregistré conserve toujours tous les scopes."""
    result = RecordsCollector()
    for scope in SCOPES:
        if scope in preferences.scopes:
            for entry in collector.records.get(scope, []):
                result.add(entry)
    return result
