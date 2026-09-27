"""Intégration SQL sur la base PostgreSQL jetable du workflow (aucune base du bot)."""
import os
import re
from itertools import product

import pandas as pd
import pytest

from test_match_records_ui import PREFS, VIEWS

DSN = os.environ.get("TEST_POSTGRES_DSN")
pytestmark = pytest.mark.skipif(not DSN, reason="PostgreSQL de test non configuré")


@pytest.fixture
def database(monkeypatch):
    import psycopg

    with psycopg.connect(DSN, autocommit=True) as conn:
        assert conn.execute("SELECT current_database()").fetchone()[0] == "records_test"
        conn.execute("DROP TABLE IF EXISTS records_preferences, match_teamfight_damage, matchs, tracker")
        conn.execute("""CREATE TABLE tracker (
            id_compte BIGINT PRIMARY KEY, discord BIGINT, riot_id TEXT, riot_tagline TEXT, puuid TEXT
        )""")
        conn.execute("""CREATE TABLE matchs (
            match_id TEXT, joueur BIGINT, mode TEXT, date BIGINT,
            dmg_min DOUBLE PRECISION, victoire BOOLEAN, champion TEXT
        )""")

        def execute(sql, params=None):
            # Adapter uniquement le style de paramètres, sans réécrire la requête testée.
            sql = re.sub(r"(?<!:):([a-z_]+)", r"%(\1)s", sql)
            return conn.execute(sql, params or {})

        def read(sql, index_col=None, params=None):
            cursor = execute(sql, params)
            return pd.DataFrame(cursor.fetchall(), columns=[col.name for col in cursor.description]).T

        monkeypatch.setattr(PREFS, "lire_bdd_perso", read)
        monkeypatch.setattr(PREFS, "requete_perso_bdd", execute)
        monkeypatch.setattr(VIEWS, "lire_bdd_perso", read)
        yield conn


def test_preferences_roundtrip_partial_updates_and_account_ownership(database):
    # La table n'existe pas encore : défaut PR42 avec tous les scopes.
    assert PREFS.load_preferences(123, strict=True) == PREFS.RecordPreferences()
    for layout in PREFS.LAYOUTS:
        for enabled in product((False, True), repeat=3):
            PREFS.save_preferences(123, layout, *enabled)
            actual = PREFS.load_preferences(123, strict=True)
            assert actual.layout == layout
            assert actual.scopes == tuple(s for s, show in zip(PREFS.SCOPES, enabled) if show)
    PREFS.save_preferences(123, "sections", False, False, False)
    PREFS.save_preferences(123, perso=True)
    assert PREFS.load_preferences(123, strict=True) == PREFS.RecordPreferences("sections", ("perso",))
    assert PREFS.load_preferences(456, strict=True) == PREFS.RecordPreferences()
    database.execute("INSERT INTO tracker VALUES (1,123,'Marin','TEST','puuid1'), (2,456,'Autre','TEST','puuid2')")
    assert PREFS.load_account_preferences(1).layout == "sections"
    assert PREFS.load_account_preferences(2).layout == "compact"


def test_progression_uses_only_ten_earlier_matches_same_account_and_mode(database):
    database.execute("INSERT INTO tracker VALUES (1,123,'Marin','TEST','puuid1')")
    for index in range(15):
        database.execute("INSERT INTO matchs VALUES (%s,1,'RANKED',%s,800,TRUE,'Ahri')", (f"EUW1_{index}", index))
    database.execute("INSERT INTO matchs VALUES ('EUW1_100',1,'RANKED',100,900,TRUE,'Ahri')")
    database.execute("INSERT INTO matchs VALUES ('EUW1_101',1,'RANKED',101,9999,TRUE,'Ahri')")
    database.execute("INSERT INTO matchs VALUES ('EUW1_102',1,'ARAM',99,9999,TRUE,'Ahri')")
    database.execute("INSERT INTO matchs VALUES ('EUW1_103',2,'RANKED',99,9999,TRUE,'Ahri')")
    current, history = VIEWS.load_progress("EUW1_100", 1)
    assert current["player_name"] == "Marin#TEST"
    assert [row["date"] for row in history] == list(range(14, 4, -1))
    assert len(history) == 10
    assert all(row["mode"] == "RANKED" and row["joueur"] == 1 for row in history)
    assert "+100" in VIEWS.comparison(current, history, "dmg_min")
    assert VIEWS.load_progress("EUW1_100", 2) is None


def test_teamfight_query_keeps_only_the_tracked_player_and_perspective(database):
    database.execute("INSERT INTO tracker VALUES (1,123,'Marin','TEST','puuid1')")
    database.execute("INSERT INTO matchs VALUES ('EUW1_100',1,'RANKED',100,900,TRUE,'Ahri')")
    _, fights, available = VIEWS.load_analysis("EUW1_100", 1)
    assert fights == [] and not available
    database.execute("""CREATE TABLE match_teamfight_damage (
        match_id TEXT, analyzed_puuid TEXT, puuid TEXT, is_teamfight BOOLEAN,
        start_ms INTEGER, fight_id INTEGER, damage_window_estimated INTEGER
    )""")
    database.execute("""INSERT INTO match_teamfight_damage VALUES
        ('EUW1_100','puuid1','puuid1',TRUE,1000,1,500),
        ('EUW1_100','puuid1','other',TRUE,1000,1,9999),
        ('EUW1_100','other','puuid1',TRUE,1000,1,9999),
        ('EUW1_100','puuid1','puuid1',FALSE,2000,2,9999),
        ('EUW1_999','puuid1','puuid1',TRUE,1000,1,9999)
    """)
    _, fights, available = VIEWS.load_analysis("EUW1_100", 1)
    assert available and len(fights) == 1
    assert fights[0]["damage_window_estimated"] == 500
