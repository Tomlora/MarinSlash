from datetime import date

from sqlalchemy import Column, Date, MetaData, Table, inspect, select
from sqlalchemy.dialects.postgresql import insert

from fonctions.gestion_bdd import engine


# Une ligne par semaine dont la collecte a abouti et écrit le roster.
completed_weeks = Table(
    "data_proplayers_completed_weeks",
    MetaData(schema="public"),
    Column("week_start", Date, primary_key=True),
)


def is_proplay_week_complete(week_start: date) -> bool:
    with engine.connect() as conn:
        if not inspect(conn).has_table(completed_weeks.name, schema="public"):
            return False
        query = select(completed_weeks.c.week_start).where(
            completed_weeks.c.week_start == week_start
        )
        return conn.execute(query).scalar_one_or_none() is not None


def record_completed_proplay_week(week_start: date) -> None:
    with engine.begin() as conn:
        completed_weeks.create(conn, checkfirst=True)
        conn.execute(
            insert(completed_weeks).values(week_start=week_start).on_conflict_do_nothing()
        )
