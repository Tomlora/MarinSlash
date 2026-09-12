from __future__ import annotations

import os
from contextlib import contextmanager
from functools import lru_cache
from typing import Iterator

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import Connection


REQUIRED_SCHEMA_COLUMNS = {
    "competition": {"code", "display_name", "timezone", "active"},
    "league": {
        "id",
        "guild_id",
        "name",
        "owner_discord_id",
        "status",
        "scoring_mode",
        "max_managers",
    },
    "season": {"id", "league_id", "name", "scoring_rule_version"},
    "manager": {"id", "league_id", "discord_user_id", "draft_position"},
    "pro_team": {"id", "competition_code", "external_id", "name", "active"},
    "pro_player": {"id", "external_id", "handle", "role", "active"},
    "pro_player_team_history": {
        "id",
        "player_id",
        "team_id",
        "valid_from",
        "valid_until",
    },
    "draft": {"id", "season_id", "status", "rounds"},
    "draft_pick": {
        "id",
        "draft_id",
        "overall_pick",
        "round_number",
        "manager_id",
        "player_id",
        "team_id",
    },
    "roster_asset": {
        "id",
        "season_id",
        "manager_id",
        "player_id",
        "team_id",
        "slot",
    },
    "roster_history": {
        "id",
        "season_id",
        "manager_id",
        "player_id",
        "team_id",
        "slot",
        "valid_from",
        "valid_until",
    },
}


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Return the Fantasy database engine using MarinSlash's PostgreSQL DSN.

    The connection setting is shared with the bot, but Fantasy data access is
    intentionally isolated from the historical DataFrame-based DB helpers.
    """
    dsn = os.environ.get("API_SQL")
    if not dsn:
        raise RuntimeError("API_SQL is not configured")
    return create_engine(dsn, echo=False, pool_pre_ping=True)


@contextmanager
def transaction() -> Iterator[Connection]:
    with get_engine().begin() as connection:
        yield connection


def schema_is_ready() -> bool:
    with get_engine().connect() as connection:
        return bool(
            connection.execute(
                text(
                    """
                    SELECT EXISTS (
                        SELECT 1
                        FROM information_schema.schemata
                        WHERE schema_name = 'fantasy'
                    )
                    """
                )
            ).scalar_one()
        )


def schema_issues() -> list[str]:
    """Return missing Fantasy tables/columns without mutating the database."""
    with get_engine().connect() as connection:
        rows = connection.execute(
            text(
                """
                SELECT table_name, column_name
                FROM information_schema.columns
                WHERE table_schema = 'fantasy'
                """
            )
        ).all()

    actual: dict[str, set[str]] = {}
    for row in rows:
        actual.setdefault(str(row.table_name), set()).add(str(row.column_name))

    issues: list[str] = []
    for table_name, required_columns in REQUIRED_SCHEMA_COLUMNS.items():
        if table_name not in actual:
            issues.append(f"table manquante: fantasy.{table_name}")
            continue
        missing_columns = sorted(required_columns - actual[table_name])
        if missing_columns:
            issues.append(
                f"colonnes manquantes dans fantasy.{table_name}: "
                + ", ".join(missing_columns)
            )
    return issues


def postgres_error_summary(exc: Exception) -> str:
    """Extract a concise PostgreSQL error without leaking connection details."""
    original = getattr(exc, "orig", None)
    if original is None:
        return type(exc).__name__

    sqlstate = getattr(original, "pgcode", None)
    diag = getattr(original, "diag", None)
    primary = getattr(diag, "message_primary", None) if diag is not None else None
    if not primary:
        primary = str(original).strip().splitlines()[0] if str(original).strip() else type(original).__name__

    if sqlstate:
        return f"SQLSTATE {sqlstate}: {primary}"
    return primary


def active_competitions() -> list[str]:
    with get_engine().connect() as connection:
        rows = connection.execute(
            text(
                """
                SELECT code
                FROM fantasy.competition
                WHERE active = TRUE
                ORDER BY code
                """
            )
        )
        return [row.code for row in rows]
