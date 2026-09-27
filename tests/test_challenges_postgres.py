"""Transactions PostgreSQL réelles, uniquement sur une base de test dédiée."""
import os
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import make_url

from fonctions import challenge_store as store

URL = os.environ.get('CHALLENGES_TEST_DATABASE_URL')
pytestmark = pytest.mark.skipif(not URL, reason='Base PostgreSQL de test non configurée')


def observation(value, at='2026-09-27T18:00:00+00:00'):
    return {'observed_at': at, 'total': {'current': value}, 'entries': [{
        'id': 101001, 'name': 'Défi', 'description': '', 'level': 'IRON',
        'value': value, 'position': 0, 'state': 'ENABLED', 'aggregate': False,
        'thresholds': {'IRON': 0, 'BRONZE': 100}}]}


@pytest.fixture
def database(monkeypatch):
    assert make_url(URL).database == 'challenges_test', 'Refus de modifier une base non dédiée aux tests'
    engine = create_engine(URL)
    monkeypatch.setattr(store, 'engine', lambda: engine)
    monkeypatch.setattr(store, '_ready', False)
    with engine.begin() as conn:
        for table in ('match_challenges', 'challenge_accounts', 'challenge_preferences', 'challenge_exclusion'):
            conn.execute(text(f'DROP TABLE IF EXISTS {table}'))
        conn.execute(text('CREATE TABLE challenge_exclusion ("index" BIGINT, "challengeId" BIGINT)'))
        conn.execute(text('INSERT INTO challenge_exclusion VALUES (42, 101002), (-1, 101003)'))
    yield engine
    engine.dispose()


def test_atomic_snapshot_idempotence_and_real_jsonb(database):
    store.save_observation(42, observation(10))
    first = store.save_observation(42, observation(12), 'EUW1_123')
    assert first['changes'][0]['delta'] == 2
    assert store.load_match('EUW1_123', 42) == first
    assert store.save_observation(42, observation(99), 'EUW1_123') == first
    assert store.profile(42)[0]['total']['current'] == 12
    assert store.history(42)[0] == ('EUW1_123', first)


def test_migration_and_preferences_survive_restart(database):
    assert set(store.profile(42)[1]['excluded']) == {101002, 101003}
    store.set_preference(42, 101002, 'inclure')
    store.set_preference(42, 101001, 'suivre')
    store._ready = False
    prefs = store.profile(42)[1]
    assert prefs == {'favorites': [101001], 'excluded': [101003]}
    store.set_preference(-1, 101003, 'inclure')
    assert store.profile(42)[1]['excluded'] == []


def test_failure_rolls_back_both_baseline_and_snapshot(database):
    store.save_observation(42, observation(10))
    def fail(conn, cursor, statement, parameters, context, executemany):
        if 'INSERT INTO challenge_accounts' in statement:
            raise RuntimeError('Simulated write failure')
    event.listen(database, 'before_cursor_execute', fail)
    try:
        with pytest.raises(RuntimeError):
            store.save_observation(42, observation(12), 'EUW1_123')
    finally:
        event.remove(database, 'before_cursor_execute', fail)
    assert store.load_match('EUW1_123', 42) is None
    assert store.profile(42)[0]['total']['current'] == 10


def test_concurrent_retries_do_not_erase_evolution(database):
    store.save_observation(42, observation(10))
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: store.save_observation(42, observation(12), 'EUW1_123'), range(4)))
    assert all(r['changes'][0]['delta'] == 2 for r in results)
    assert len(store.history(42)) == 1


def test_stale_observation_cannot_replace_current(database):
    store.save_observation(42, observation(10))
    with pytest.raises(ValueError):
        store.save_observation(42, observation(20, '2026-09-26T18:00:00+00:00'), 'EUW1_123')
    assert store.load_match('EUW1_123', 42) is None
    assert store.profile(42)[0]['total']['current'] == 10
