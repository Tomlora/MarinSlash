from __future__ import annotations

import os
from contextlib import contextmanager
from functools import lru_cache
from typing import Iterator

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import Connection


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
