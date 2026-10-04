"""Intégration SQL sur la base PostgreSQL jetable du workflow (aucune base du bot)."""
import os
import re
from itertools import product

import pandas as pd
import pytest

from test_match_records_ui import PREFS, VIEWS, DETAILS
from test_match_scoring import modules as scoring_modules, match_fixture, calculate

DSN = os.environ.get("TEST_POSTGRES_DSN")
pytestmark = pytest.mark.skipif(not DSN, reason="PostgreSQL de test non configuré")


@pytest.fixture
def database(monkeypatch):
    import psycopg

    with psycopg.connect(DSN, autocommit=True) as conn:
        assert conn.execute("SELECT current_database()").fetchone()[0] == "records_test"
        conn.execute("DROP TABLE IF EXISTS records_preferences, match_teamfight_damage, match_gank_summary, match_gank_events, match_recap_details, match_scoring, matchs_timestamp_gold, matchs, tracker")
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
        monkeypatch.setattr(DETAILS, "lire_bdd_perso", read)
        monkeypatch.setattr(DETAILS, "requete_perso_bdd", execute)
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


def test_new_teamfight_loader_keeps_teammates_but_excludes_other_perspectives(database):
    database.execute("INSERT INTO tracker VALUES (1,123,'Marin','TEST','puuid1')")
    database.execute("INSERT INTO matchs VALUES ('EUW1_100',1,'RANKED',100,900,TRUE,'Ahri')")
    assert VIEWS.load_teamfights("EUW1_100", 1)[2] is False
    database.execute("""CREATE TABLE match_teamfight_damage (
        match_id TEXT, analyzed_puuid TEXT, puuid TEXT, start_ms INTEGER, fight_id INTEGER,
        team INTEGER, damage_frame_window INTEGER, is_teamfight BOOLEAN
    )""")
    database.execute("""INSERT INTO match_teamfight_damage VALUES
        ('EUW1_100','puuid1','puuid1',1000,1,100,1000,TRUE),
        ('EUW1_100','puuid1','teammate',1000,1,100,3000,TRUE),
        ('EUW1_100','other','puuid1',1000,1,100,9999,TRUE),
        ('EUW1_100','puuid1','puuid1',2000,2,100,200,FALSE),
        ('EUW1_999','puuid1','puuid1',1000,1,100,9999,TRUE)
    """)
    match, rows, available = VIEWS.load_teamfights("EUW1_100", 1)
    assert available and len(rows) == 3
    assert sum(row["tracked"] for row in rows) == 2
    pages = VIEWS.build_teamfight_pages(match, rows, available)
    assert "25 % équipe" in pages[-1].fields[0].value
    assert VIEWS.load_teamfights("EUW1_100", 2) is None


def test_gank_loader_matches_account_team_and_filters_boundary_on_old_schema(database):
    database.execute("INSERT INTO tracker VALUES (1,123,'Marin','TEST','puuid1')")
    database.execute("INSERT INTO matchs VALUES ('EUW1_100',1,'RANKED',100,900,TRUE,'Ahri')")
    database.execute("ALTER TABLE matchs ADD COLUMN id_participant INTEGER")
    database.execute("UPDATE matchs SET id_participant = 7")
    assert VIEWS.load_ganks("EUW1_100", 1)[3] is False
    # Pas de colonnes hybrides : lecture compatible avec les données anciennes.
    database.execute("""CREATE TABLE match_gank_summary (
        match_id TEXT, team_id INTEGER, ally_jungler_champion TEXT
    )""")
    database.execute("""CREATE TABLE match_gank_events (
        match_id TEXT, team_id INTEGER, timestamp_ms INTEGER, successful BOOLEAN
    )""")
    database.execute("""INSERT INTO match_gank_summary VALUES
        ('EUW1_100',100,'LeeSin'), ('EUW1_100',200,'Viego')
    """)
    database.execute("""INSERT INTO match_gank_events VALUES
        ('EUW1_100',200,0,TRUE), ('EUW1_100',100,839999,FALSE),
        ('EUW1_100',200,840000,TRUE), ('EUW1_100',200,-1,TRUE),
        ('EUW1_999',200,1000,TRUE)
    """)
    match, summary, events, available = VIEWS.load_ganks("EUW1_100", 1)
    assert summary["ally_jungler_champion"] == "Viego"
    assert available and [e["timestamp_ms"] for e in events] == [0, 839999]
    assert "issues inconnues" in VIEWS.build_gank_pages(match, summary, events, available)[0].fields[0].value
    assert VIEWS.load_ganks("EUW1_100", 2) is None
    database.execute("UPDATE matchs SET mode = 'ARAM'")
    assert VIEWS.load_ganks("EUW1_100", 1)[3] is False


def test_jungle_proximity_persists_with_other_snapshots_and_loads_without_gank_tables(database):
    from test_player_profiles import filled_match
    from test_jungle_proximity import proximity_fixture
    database.execute("INSERT INTO tracker VALUES (5,123,'Marin','TEST','p7'), (6,456,'Autre','TEST','p0')")
    database.execute("INSERT INTO matchs VALUES ('EUW1_123',5,'RANKED',100,900,TRUE,'Ahri'), ('EUW1_123',6,'RANKED',100,900,TRUE,'Ahri')")
    match = filled_match()
    match.match_detail.loc['mapId', 'info'] = 11
    match.data_timeline = proximity_fixture()[1]
    for _ in range(2):
        assert DETAILS.save_recap_details(match)
        loaded, summary, events, available = VIEWS.load_ganks('EUW1_123', 5)
        assert loaded['jungle_proximity']['tracked_team'] == 200
        assert not available and summary == {} and events == []
        assert VIEWS.build_gank_pages(loaded, summary, events, available)[1].title.endswith('Alliés')
    payload = database.execute("SELECT data FROM match_recap_details WHERE joueur=5").fetchone()[0]
    assert payload['map'] and payload['scores'] and len(payload['players']['players']) == 10
    assert payload['jungle_proximity']['players'][0]['own']['percent'] == 66.7
    assert database.execute("SELECT count(*) FROM match_recap_details").fetchone()[0] == 1
    other = VIEWS.load_ganks('EUW1_123', 6)[0]
    assert other.get('jungle_proximity') is None


def test_recap_details_roundtrip_is_per_account_and_keeps_true_team_colors(database):
    from test_match_records_ui import sample_details_match
    database.execute("INSERT INTO tracker VALUES (5,123,'Renamed','TEST','p7'), (6,456,'Other','TEST','p1')")
    database.execute("INSERT INTO matchs VALUES ('EUW1_123',5,'RANKED',100,900,TRUE,'Ahri'), ('EUW1_123',6,'RANKED',100,800,TRUE,'Ahri')")
    assert DETAILS.load_score("EUW1_123", 5)[1] == []
    assert DETAILS.load_gold("EUW1_123", 5)[1] == []
    assert DETAILS.save_recap_details(sample_details_match())
    match, scores = DETAILS.load_score("EUW1_123", 5)
    assert match["player_name"] == "Renamed#TEST"
    tracked = next(p for p in scores if p["tracked"])
    assert tracked["riot_id"] == "Player7" and tracked["team"] == 200
    points = DETAILS.load_gold("EUW1_123", 5)[1]
    assert [p["minute"] for p in points] == [0, 1, 2, 4]
    assert points[1]["blue"] - points[1]["red"] == 500
    assert DETAILS.load_score("EUW1_123", 6)[1] == []
    assert DETAILS.load_gold("EUW1_123", 999) is None
    # La réanalyse remplace le même snapshot sans créer de doublon.
    assert DETAILS.save_recap_details(sample_details_match())
    assert database.execute("SELECT COUNT(*) FROM match_recap_details").fetchone()[0] == 1


def test_player_profiles_roundtrip_keeps_ten_players_and_red_allies(database):
    from test_player_profiles import filled_match, PROFILES
    database.execute("INSERT INTO tracker VALUES (5,123,'Player7','TEST','p7'), (6,456,'Other','TEST','p1')")
    database.execute("INSERT INTO matchs VALUES ('EUW1_123',5,'RANKED',100,900,TRUE,'Ahri'), ('EUW1_123',6,'RANKED',100,800,TRUE,'Ahri')")
    match = filled_match()
    assert DETAILS.save_recap_details(match)
    saved = DETAILS.load_details('EUW1_123', 5)[1]['players']
    assert saved == PROFILES.snapshot_players(match)
    assert saved['allied_team'] == 200 and len(saved['players']) == 10
    assert saved['players'][7]['global']['wins'] == 30
    assert 'players' not in DETAILS.load_details('EUW1_123', 6)[1]
    assert DETAILS.save_recap_details(match)
    assert database.execute('SELECT COUNT(*) FROM match_recap_details').fetchone()[0] == 1


def test_ten_player_map_roundtrip_in_existing_jsonb_snapshot(database):
    from test_match_records_ui import sample_details_match
    from test_match_map import riot_fixture, MAP
    database.execute("INSERT INTO tracker VALUES (5,123,'Player7','TEST','p7')")
    database.execute("INSERT INTO matchs VALUES ('EUW1_123',5,'RANKED',100,900,TRUE,'Ahri')")
    info = sample_details_match()
    info.match_detail, info.data_timeline = riot_fixture()
    expected = MAP.build_map_snapshot(info.match_detail, info.data_timeline)
    info.match_detail = pd.DataFrame(info.match_detail)
    assert DETAILS.save_recap_details(info)
    assert DETAILS.load_details('EUW1_123', 5)[1]['map'] == expected
    assert DETAILS.save_recap_details(info)
    assert database.execute("SELECT COUNT(*) FROM match_recap_details").fetchone()[0] == 1
    assert DETAILS.load_details('EUW1_123', 999) is None


def test_map_and_profiles_share_one_jsonb_row_without_overwriting_each_other(database):
    from test_player_profiles import filled_match, PROFILES
    from test_match_map import riot_fixture, MAP
    database.execute("INSERT INTO tracker VALUES (5,123,'Player7','TEST','p7')")
    database.execute("INSERT INTO matchs VALUES ('EUW1_123',5,'RANKED',100,900,TRUE,'Ahri')")
    match = filled_match()
    match.match_detail.loc['mapId', 'info'] = 11
    match.data_timeline = riot_fixture()[1]
    expected_map = MAP.build_map_snapshot(match.match_detail, match.data_timeline)
    assert expected_map is not None
    for wins in (30, 31):
        PROFILES.capture_global(match, 2, {'wins': wins, 'losses': 30}, 'Mobalytics')
        assert DETAILS.save_recap_details(match)
        data = DETAILS.load_details('EUW1_123', 5)[1]
        assert data['map'] == expected_map
        assert data['players'] == PROFILES.snapshot_players(match)
        assert data['players']['players'][7]['global']['wins'] == wins
        assert database.execute('SELECT COUNT(*) FROM match_recap_details').fetchone()[0] == 1


def test_legacy_scoring_and_gold_use_riot_identity_and_account_perspective(database):
    database.execute("INSERT INTO tracker VALUES (5,123,'Player7','TEST','p7')")
    database.execute("INSERT INTO matchs VALUES ('EUW1_123',5,'RANKED',100,900,TRUE,'Ahri')")
    database.execute("ALTER TABLE matchs ADD COLUMN id_participant INTEGER")
    database.execute("UPDATE matchs SET id_participant = 7")
    database.execute("""CREATE TABLE match_scoring (
        match_id TEXT, player_index INTEGER, riot_id TEXT, riot_tag TEXT, team TEXT,
        score DOUBLE PRECISION, combat_value DOUBLE PRECISION
    )""")
    database.execute("""INSERT INTO match_scoring VALUES
        ('EUW1_123',2,'Player7','TEST','blue',8,7),
        ('EUW1_123',7,'Other','TEST','red',9,8),
        ('EUW1_999',2,'Player7','TEST','blue',1,1)
    """)
    scores = DETAILS.load_score("EUW1_123", 5)[1]
    assert len(scores) == 2
    assert [s["player_index"] for s in scores if s["tracked"]] == [2]
    assert next(s for s in scores if s['tracked'])['explanation_status'] == 'snapshot_unavailable'
    database.execute("""CREATE TABLE matchs_timestamp_gold (
        match_id TEXT, riot_id BIGINT, timestamp DOUBLE PRECISION,
        gold_allie DOUBLE PRECISION, gold_adv DOUBLE PRECISION
    )""")
    database.execute("""INSERT INTO matchs_timestamp_gold VALUES
        ('EUW1_123',5,0,2500,2500), ('EUW1_123',5,1,3000,3500),
        ('EUW1_123',5,1.45,3900,3999), ('EUW1_123',5,2,NULL,4000),
        ('EUW1_123',6,1,99999,0), ('EUW1_999',5,1,99999,0)
    """)
    points = DETAILS.load_gold("EUW1_123", 5)[1]
    assert points == [{"minute": 0, "blue": 2500, "red": 2500},
                      {"minute": 1, "blue": 3500, "red": 3000}]


@pytest.mark.parametrize('tracked,minutes', [(1, 20), (1, 40), (7, 20), (7, 40)])
@pytest.mark.parametrize('existing', [False, True])
def test_calculation_save_data_postgres_and_score_button_keep_five_explanations(
        database, scoring_modules, tracked, minutes, existing):
    """Actual calculation -> save_data -> JSONB -> load_score -> button pagination."""
    import ast
    import asyncio
    from test_match_records_ui import MATCH_DIR, VIEW_COG, RecordingContext

    match = calculate(match_fixture(scoring_modules, tracked=tracked, duration=minutes*60))
    match.last_match, match.id_compte = 'EUW1_123', 5
    database.execute("INSERT INTO tracker VALUES (5,123,'Renamed','TEST',%s)", (match.puuid,))
    def insert_match():
        database.execute("INSERT INTO matchs VALUES ('EUW1_123',5,'RANKED',100,900,TRUE,'Ahri')")
    if existing:
        insert_match()
    match._insert_match_data = insert_match
    match._insert_participant_data = match._insert_other_match_data = match._insert_points_data = lambda: None
    match.thisKDA, match.session, match.version = 3., None, {'n': {'champion': 'test'}}
    tree = ast.parse((MATCH_DIR / 'save_data.py').read_text(encoding='utf-8'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'SaveDataMixin')
    method = next(n for n in cls.body if isinstance(n, ast.AsyncFunctionDef) and n.name == 'save_data')
    async def tags(*args):
        return pd.DataFrame()
    env = dict(asyncio=asyncio, lire_bdd_perso=DETAILS.lire_bdd_perso,
               save_recap_details=DETAILS.save_recap_details, get_data_champ_tags=tags,
               sauvegarde_bdd=lambda *a, **kw: None)
    exec(compile(ast.Module(body=[method], type_ignores=[]), 'save_data.py', 'exec'), env)
    asyncio.run(env['save_data'](match))
    # No live calculation object is available when a user opens the button later.
    match.player_metrics_liste.clear()
    payload = database.execute("SELECT data FROM match_recap_details WHERE joueur=5").fetchone()[0]
    saved = [p for p in payload['scores'] if 'dimension_explanations' in p]
    assert len(saved) == 1 and saved[0]['riot_id'] == f'Player{tracked}'
    assert saved[0]['explanation_status'] == 'available'
    assert saved[0]['dimension_explanations']['duration_minutes'] == minutes
    assert len(saved[0]['dimension_explanations']['dimensions']) == 5
    cog = VIEW_COG.LolMatchViews.__new__(VIEW_COG.LolMatchViews)
    ctx = RecordingContext('lolview_open_score_EUW1_123_5')
    asyncio.run(cog.on_open(ctx))
    pages = []
    for _ in range(25):
        assert ctx.calls[-1][0] in ('send', 'edit_origin')
        response = ctx.calls[-1][-1]
        assert 'embeds' in response and response['embeds']
        pages.append(response['embeds'])
        next_button = response['components'][0].components[1]
        if next_button.disabled:
            break
        ctx = RecordingContext(next_button.custom_id)
        asyncio.run(cog.on_page(ctx))
    else:
        pytest.fail('Pagination does not end')
    assert sum(f.name == 'Comment retrouver la note' for p in pages for f in p.fields) == 5
    explained = [p for p in pages if 'Pourquoi cette note' in p.title]
    assert all(f'Player{tracked}#TEST' in p.description for p in explained)
    assert not any('anomalie' in f.value for p in pages for f in p.fields)
