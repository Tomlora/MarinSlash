"""Vraies transactions concurrentes PostgreSQL, activées dans la CI dédiée."""
from concurrent.futures import ThreadPoolExecutor
import os
import threading
import uuid

import pytest
from sqlalchemy import create_engine, text

from fonctions.worlds2026.domain import Fixture, WorldsError, timestamp
from fonctions.worlds2026.store import Store

URL = os.getenv("WORLDS_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="PostgreSQL de test non configuré")
START = timestamp("2026-10-23T17:00:00Z")


@pytest.fixture
def db(monkeypatch):
    admin = create_engine(URL)
    schema = "worlds_test_" + uuid.uuid4().hex
    with admin.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(URL, connect_args={"options": f"-csearch_path={schema}"})
    store = Store(engine)
    store.initialize()
    now = [START - 3600]
    monkeypatch.setattr("fonctions.worlds2026.store.utcnow", lambda: now[0])
    store.configure(10, True, 99)
    store.register(10, 1)
    fixture = Fixture("leaguepedia", "M1", "G2", "T1", START, 5)
    store.ingest(10, [fixture])
    mid = store.list_matches(10)[0]["id"]
    yield store, mid, now
    engine.dispose()
    with admin.begin() as conn:
        conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
    admin.dispose()


def test_concurrent_predictions_one_record_and_concurrent_results_one_score(db):
    store, mid, now = db
    def predict(_):
        store.predict(10, 1, mid, 3, 1)
    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(predict, range(16)))
    assert len(store.predictions(10, 1)) == 1
    now[0] = START + 7200
    fixture = Fixture("leaguepedia", "M1", "G2", "T1", START, 5, "finished", 3, 1)
    with ThreadPoolExecutor(max_workers=8) as executor:
        reports = list(executor.map(lambda _: store.ingest(10, [fixture]), range(16)))
    assert all(not r["errors"] for r in reports)
    assert store.standings(10)[0]["points"] == 3
    assert len(store.list_matches(10)) == 1


def test_waiting_prediction_rechecks_clock_after_database_lock(db):
    store, mid, now = db
    entered = threading.Event()
    def blocked_prediction():
        entered.set()
        with pytest.raises(WorldsError, match="fermés"):
            store.predict(10, 1, mid, 3, 0)
    with ThreadPoolExecutor(max_workers=1) as executor:
        with store.transaction():
            future = executor.submit(blocked_prediction)
            assert entered.wait(5)
            now[0] = START
        future.result(timeout=10)
    assert store.predictions(10, 1) == []


def test_rollback_and_new_store_preserve_data(db):
    store, mid, now = db
    store.predict(10, 1, mid, 3, 2)
    with pytest.raises(WorldsError):
        store.predict(10, 1, mid, 3, 3)
    fresh = Store(store.engine)
    fresh.initialize()
    assert fresh.predictions(10, 1)[0]["score2"] == 2
    now[0] = START + 7200
    fresh.resolve(10, mid, "finished", 3, 2, "VOD", 99)
    assert fresh.standings(10)[0]["points"] == 3
