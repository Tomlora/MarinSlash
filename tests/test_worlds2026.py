import asyncio
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import create_engine

from fonctions.worlds2026.domain import Fixture, WorldsError, points, timestamp
from fonctions.worlds2026.store import Store
from fonctions.worlds2026.sources import (Leaguepedia, LoLEsports, PandaScore, Snapshot, SourceError,
                                         fetch_safely, parse_leaguepedia, parse_lolesports, parse_pandascore)
from fonctions.worlds2026.service import Synchronizer

START = timestamp("2026-10-23T17:00:00Z")


@pytest.fixture
def clock(monkeypatch):
    now = [START - 3600]
    monkeypatch.setattr("fonctions.worlds2026.store.utcnow", lambda: now[0])
    return now


@pytest.fixture
def store(tmp_path, clock):
    engine = create_engine(f"sqlite:///{tmp_path / 'worlds.db'}")
    result = Store(engine)
    result.initialize()
    result.configure(10, True, 99)
    result.register(10, 1)
    yield result
    engine.dispose()


def fixture(**kwargs):
    return replace(Fixture("leaguepedia", "worlds-r1-m1", "T1", "G2 Esports", START, 3), **kwargs)


def add(store, **kwargs):
    assert not store.ingest(10, [fixture(**kwargs)])["errors"]
    return store.list_matches(10)[0]["id"]


@pytest.mark.parametrize("bo", [1, 3, 5])
def test_every_legal_score_and_prediction(bo):
    n = bo // 2 + 1
    scores = [(n, i) for i in range(n)] + [(i, n) for i in range(n)]
    for prediction in scores:
        for result in scores:
            expected = 0 if (prediction[0] > prediction[1]) != (result[0] > result[1]) else (
                3 if bo != 1 and prediction == result else 1)
            assert points(bo, prediction, result) == expected


@pytest.mark.parametrize("bo,score", [(1, (1, 1)), (3, (1, 0)), (5, (3, 3)), (5, (4, 0)),
                                    (3, (-1, 2)), (2, (2, 0)), (3, (True, 2))])
def test_invalid_scores(bo, score):
    with pytest.raises(WorldsError):
        points(bo, score, score)


def test_normalization_aliases_reverses_result():
    f = fixture(state="finished", score1=2, score2=1).normalized()
    assert (f.team1, f.team2, f.score1, f.score2) == ("G2", "T1", 1, 2)
    assert fixture(team1="Gen.G", team2="Team Liquid Alienware").normalized().team2 == "TL"
    with pytest.raises(WorldsError):
        fixture(team1="TBD").normalized()
    with pytest.raises(WorldsError):
        fixture(starts_at=timestamp("2025-10-23T17:00:00Z")).normalized()
    with pytest.raises(WorldsError):
        timestamp("2026-10-23T19:00:00")
    assert timestamp("2026-10-23T19:00:00+02:00") == START


def test_prediction_edit_lock_boundary_and_registration(store, clock):
    mid = add(store)
    store.predict(10, 1, mid, 2, 0)
    store.predict(10, 1, mid, 1, 2)
    assert len(store.predictions(10, 1)) == 1
    with pytest.raises(WorldsError, match="Inscris"):
        store.predict(10, 2, mid, 2, 0)
    clock[0] = START
    with pytest.raises(WorldsError, match="fermés"):
        store.predict(10, 1, mid, 2, 0)


def test_fallback_reversed_order_and_idempotent_scoring(store, clock):
    mid = add(store)
    store.predict(10, 1, mid, 1, 2)
    clock[0] = START + 7200
    fallback = fixture(source="pandascore", source_id="42", team1="G2", team2="T1",
                       state="finished", score1=1, score2=2)
    for _ in range(3):
        assert not store.ingest(10, [fallback])["errors"]
    assert len(store.list_matches(10)) == 1
    assert store.standings(10)[0]["points"] == 3
    # Une source en retard ne remet pas le match à venir.
    store.ingest(10, [fixture()])
    assert store.standings(10)[0]["points"] == 3


def test_conflicting_result_suspends_until_manual_resolution(store, clock):
    mid = add(store)
    store.predict(10, 1, mid, 1, 2)
    clock[0] = START + 7200
    store.ingest(10, [fixture(state="finished", score1=2, score2=1)])
    bad = fixture(source="pandascore", source_id="42", state="finished", score1=1, score2=2)
    assert store.ingest(10, [bad])["errors"]
    assert store.list_matches(10)[0]["state"] == "disputed"
    assert store.standings(10)[0]["points"] == 0
    store.resolve(10, mid, "finished", 1, 2, "VOD officielle", 99)
    store.ingest(10, [bad])
    assert store.standings(10)[0]["points"] == 3
    store.resolve(10, mid, "finished", 2, 1, "Correction", 99)
    assert store.standings(10)[0]["points"] == 0
    assert store.status(10)[1][0]["actor"] == 99


def test_cancel_withdraw_disable_restart_and_guild_isolation(store, clock):
    mid = add(store)
    store.predict(10, 1, mid, 2, 0)
    store.register(10, 1, False)
    with pytest.raises(WorldsError):
        store.predict(10, 1, mid, 2, 1)
    store.register(10, 1)
    store.configure(20, True, 99)
    store.register(20, 1)
    with pytest.raises(WorldsError, match="introuvable"):
        store.predict(20, 1, mid, 2, 0)
    with pytest.raises(WorldsError):
        store.resolve(20, mid, "cancelled", None, None, "test", 99)
    assert not store.list_matches(20)
    clock[0] = START + 7200
    store.resolve(10, mid, "finished", 2, 0, "résultat", 99)
    assert store.standings(10)[0]["points"] == 3
    store.resolve(10, mid, "cancelled", None, None, "forfait", 99)
    assert store.standings(10)[0]["points"] == 0
    restarted = Store(store.engine)
    restarted.initialize()
    assert len(restarted.predictions(10, 1)) == 1
    store.configure(10, False, 99)
    with pytest.raises(WorldsError, match="désactivés"):
        store.register(10, 3)
    assert store.enabled_guilds() == [20]


def test_postponement_never_reopens_and_earlier_start_invalidates_late_pick(store, clock):
    mid = add(store)
    store.predict(10, 1, mid, 2, 0)
    store.ingest(10, [fixture(starts_at=START + 3600)])
    assert store.list_matches(10)[0]["lock_at"] == START
    clock[0] = START
    with pytest.raises(WorldsError):
        store.predict(10, 1, mid, 1, 2)
    # Le fournisseur révèle que le match a commencé avant le pari.
    store.ingest(10, [fixture(starts_at=START - 4000, state="finished", score1=0, score2=2)])
    assert store.standings(10)[0]["points"] == 0


def test_ambiguous_fallback_does_not_create_duplicate_and_can_be_linked(store):
    mid = add(store)
    delayed = fixture(source="pandascore", source_id="42", starts_at=START + 86400)
    assert store.ingest(10, [delayed])["errors"]
    assert len(store.list_matches(10)) == 1
    store.associate(10, mid, "pandascore", "42", 99)
    assert not store.ingest(10, [delayed])["errors"]
    assert len(store.list_matches(10)) == 1


def test_manual_match_and_invalid_result(store, clock):
    f = fixture(source="manual", source_id="manual-1")
    mid = store.manual_match(10, f, 99)
    with pytest.raises(WorldsError):
        store.manual_match(10, f, 99)
    with pytest.raises(WorldsError, match="avant"):
        store.resolve(10, mid, "finished", 2, 0, "test", 99)
    store.reschedule(10, mid, START + 3600, 99)
    assert store.list_matches(10)[0]["lock_at"] == START
    clock[0] = START + 7200
    with pytest.raises(WorldsError):
        store.resolve(10, mid, "finished", 1, 0, "test", 99)
    with pytest.raises(WorldsError):
        store.resolve(10, mid, "finished", 2, 0, " ", 99)


def cargo_row(**kwargs):
    return dict({"OverviewPage": "2026 Season World Championship/Main Event", "MatchId": "M1",
        "Team1": "G2 Esports", "Team2": "T1", "BestOf": "3", "DateTime UTC": "2026-10-23 17:00:00",
        "HasTime": "1", "Team1Score": "2", "Team2Score": "1", "Winner": "1"}, **kwargs)


def riot_event():
    return {"type": "match", "startTime": "2026-10-23T17:00:00Z", "state": "completed",
            "league": {"slug": "worlds"}, "match": {"id": "M2", "strategy": {"count": 3},
            "teams": [{"name": "G2 Esports", "result": {"gameWins": 2, "outcome": "win"}},
                      {"name": "T1", "result": {"gameWins": 1, "outcome": "loss"}}]}}


def panda_row():
    return {"id": 42, "serie": {"id": 2026, "year": 2026}, "status": "finished",
        "opponents": [{"opponent": {"id": 1, "name": "G2"}}, {"opponent": {"id": 2, "name": "T1"}}],
        "results": [{"team_id": 2, "score": 1}, {"team_id": 1, "score": 2}],
        "winner_id": 1, "number_of_games": 3, "begin_at": "2026-10-23T17:00:00Z"}


def test_parsers_filter_tournament_and_validate_final_scores():
    for f in [parse_leaguepedia(cargo_row()), parse_lolesports(riot_event()), parse_pandascore(panda_row(), {2026})]:
        f = f.normalized()
        assert (f.team1, f.team2, f.score1, f.score2, f.state) == ("G2", "T1", 2, 1, "finished")
    assert parse_leaguepedia(cargo_row(OverviewPage="2026 MSI")) is None
    assert parse_pandascore(panda_row(), {5}) is None
    assert parse_leaguepedia(cargo_row(FF="1")).normalized().state == "cancelled"
    assert parse_leaguepedia(cargo_row(Winner="", Team1Score="1")).normalized().score1 is None
    with pytest.raises(WorldsError):
        parse_leaguepedia(cargo_row(Winner="2"))
    with pytest.raises(WorldsError):
        parse_leaguepedia(cargo_row(HasTime="0"))
    with pytest.raises(WorldsError):
        parse_leaguepedia(cargo_row(Team1Score="1")).normalized()
    panda = panda_row()
    panda["forfeit"] = True
    assert parse_pandascore(panda, {2026}).normalized().state == "cancelled"


def test_all_connectors_real_request_shapes_and_pagination(monkeypatch):
    calls = []
    async def fake(session, url, params=None, headers=None):
        calls.append((url, params, headers))
        if "fandom" in url:
            if params["offset"] == "0":
                return {"cargoquery": [{"title": cargo_row(MatchId=str(i))} for i in range(100)]}
            return {"cargoquery": [{"title": cargo_row(HasTime="0")}]}
        if url.endswith("getLeagues"):
            return {"data": {"leagues": [{"slug": "worlds", "id": "1"}]}}
        if url.endswith("getSchedule"):
            return {"data": {"schedule": {"events": [riot_event()], "pages": {"older": None, "newer": None}}}}
        return [panda_row()]
    monkeypatch.setattr("fonctions.worlds2026.sources.get_json", fake)
    async def run():
        a = await Leaguepedia().fetch(None)
        b = await LoLEsports("secret").fetch(None)
        c = await PandaScore("secret", {2026}).fetch(None)
        assert (len(a.fixtures), a.rejected, len(b.fixtures), len(c.fixtures)) == (100, 1, 1, 1)
    asyncio.run(run())
    assert calls[1][1]["offset"] == "100"
    assert calls[-1][1]["filter[serie_id]"] == "2026"
    assert calls[-1][2]["Authorization"] == "Bearer secret"


@pytest.mark.parametrize("failure", [SourceError("HTTP 429"), asyncio.TimeoutError(), KeyError("secret"), ValueError("bad JSON")])
def test_failover_and_no_secret_leak(store, failure):
    failed = SimpleNamespace(name="down", fetch=AsyncMock(side_effect=failure))
    healthy = SimpleNamespace(name="backup", fetch=AsyncMock(return_value=Snapshot([fixture()])))
    sync = Synchronizer(store, [failed, healthy])
    async def run():
        report = await sync.run()
        assert "secret" not in report
        assert len(store.list_matches(10)) == 1
        await sync.run()
        assert failed.fetch.await_count == healthy.fetch.await_count == 1
    asyncio.run(run())
    statuses, _ = store.status(10)
    assert {r["source"]: r["success_at"] is not None for r in statuses} == {"down": False, "backup": True}


def test_empty_primary_and_all_down_keep_cache(store):
    add(store)
    failed = SimpleNamespace(name="down", fetch=AsyncMock(return_value=Snapshot()))
    assert "Aucun match" in asyncio.run(Synchronizer(store, [failed]).run())
    assert len(store.list_matches(10)) == 1
    store.record_health("down", "ok", True)
    old = store.status(10)[0][0]["success_at"]
    store.record_health("down", "HTTP 503", False)
    assert store.status(10)[0][0]["success_at"] == old


def test_actual_discord_cog_registration_permissions_and_pagination(store):
    import interactions as ip
    from cogs.worlds2026 import Worlds2026, pages
    bot = ip.Client()
    cog = Worlds2026(bot)
    cog.store, cog.syncer = store, Synchronizer(store, [])
    assert len(cog._commands) == 19
    for command in cog._commands:
        if str(command.name) == "worlds_admin":
            assert command.default_member_permissions == ip.Permissions.MANAGE_GUILD
    assert all(len(e.description) <= 3500 for e in pages(["x" * 2999] * 120))
    async def run():
        ctx = SimpleNamespace(guild_id=10, author_id=1, defer=AsyncMock(), send=AsyncMock(),
                              author=SimpleNamespace(has_permission=lambda p: False))
        action = lambda db: db.configure(10, False, 1)
        await cog.execute(ctx, action, admin=True)
        assert store.enabled_guilds() == [10]
        assert "permission" in ctx.send.call_args.args[0]
        ctx.guild_id = None
        await cog.execute(ctx, action)
        assert "serveur" in ctx.send.call_args.args[0]
        ctx.guild_id = 10
        await cog.my_predictions.callback(ctx)
        ctx.defer.assert_called_with(ephemeral=True)
    try:
        asyncio.run(run())
    finally:
        cog.drop()


def test_identity_change_closes_predictions_and_requires_review(store):
    mid = add(store)
    report = store.ingest(10, [fixture(best_of=5)])
    assert report["errors"]
    assert store.list_matches(10)[0]["state"] == "disputed"
    with pytest.raises(WorldsError, match="fermés"):
        store.predict(10, 1, mid, 2, 0)


def test_two_ids_same_provider_are_not_silently_merged(store):
    add(store)
    report = store.ingest(10, [fixture(source_id="M2", starts_at=START + 3600)])
    assert report["errors"]
    assert len(store.list_matches(10)) == 1


def test_future_final_result_is_rejected(store):
    report = store.ingest(10, [fixture(state="finished", score1=2, score2=1)])
    assert report["errors"]
    assert store.list_matches(10) == []


def test_supplement_partial_primary_and_recover_failed_source(store):
    first = SimpleNamespace(name="primary", fetch=AsyncMock(return_value=Snapshot([fixture()])))
    second = SimpleNamespace(name="backup", fetch=AsyncMock(return_value=Snapshot([
        fixture(source="pandascore", source_id="42", team1="C9", team2="KC")])))
    sync = Synchronizer(store, [first, second])
    async def run():
        await sync.run()
        assert len(store.list_matches(10)) == 2
        first.fetch.side_effect = SourceError("HTTP 503")
        sync.next_attempt.clear()
        await sync.run()
        assert len(store.list_matches(10)) == 2
        first.fetch.side_effect = None
        sync.next_attempt.clear()
        await sync.run()
        assert sync.failures["primary"] == 0
    asyncio.run(run())


def test_http_error_json_error_and_bad_json_are_failures():
    from fonctions.worlds2026.sources import get_json
    class Response:
        def __init__(self, status, payload):
            self.status, self.payload = status, payload
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def json(self, **kwargs):
            if isinstance(self.payload, Exception):
                raise self.payload
            return self.payload
    async def run():
        for status, payload in [(429, {}), (403, {}), (503, {}),
                                (200, {"error": {"code": "ratelimited"}}), (200, ValueError("HTML"))]:
            session = SimpleNamespace(get=lambda *args, **kw: Response(status, payload))
            with pytest.raises((SourceError, ValueError)):
                await get_json(session, "https://test.invalid")
    asyncio.run(run())


def test_leaguepedia_partial_bad_rows_do_not_drop_good_matches(monkeypatch):
    async def fake(*args, **kwargs):
        return {"cargoquery": [{"title": cargo_row()}, {"title": cargo_row(Team1="TBD")},
                               {"title": cargo_row(BestOf="2")}, {"title": cargo_row(MatchId="M3", Winner="")} ]}
    monkeypatch.setattr("fonctions.worlds2026.sources.get_json", fake)
    snapshot = asyncio.run(Leaguepedia().fetch(None))
    assert len(snapshot.fixtures) == 2
    assert snapshot.rejected == 2


def test_pagination_budget_and_missing_pandascore_configuration(monkeypatch):
    async def endless(*args, **kwargs):
        return {"cargoquery": [{"title": cargo_row(MatchId=str(i))} for i in range(100)]}
    fake = AsyncMock(side_effect=endless)
    monkeypatch.setattr("fonctions.worlds2026.sources.get_json", fake)
    snapshot, message = asyncio.run(fetch_safely(Leaguepedia(), None))
    assert snapshot is None and "incomplète" in message
    assert fake.await_count == 10
    snapshot, message = asyncio.run(fetch_safely(PandaScore("key", set()), None))
    assert snapshot is None and "SERIE_IDS" in message


def test_real_command_records_score_and_private_confirmation(store):
    import importlib
    import interactions as ip
    import cogs.worlds2026
    # interactions.py lie les callbacks sur la classe ; recharger comme le bot.
    Worlds2026 = importlib.reload(cogs.worlds2026).Worlds2026
    mid = add(store)
    bot = ip.Client()
    cog = Worlds2026(bot)
    cog.store, cog.syncer = store, Synchronizer(store, [])
    ctx = SimpleNamespace(guild_id=10, author_id=1, defer=AsyncMock(), send=AsyncMock())
    try:
        asyncio.run(cog.predict.callback(ctx, mid, 2, 1))
        ctx.defer.assert_called_with(ephemeral=True)
        assert "G2 2–1 T1" in ctx.send.call_args.kwargs["embeds"].description
        assert store.predictions(10, 1)[0]["score1"] == 2
    finally:
        cog.drop()


def test_cancellation_then_final_from_other_source_is_a_conflict(store, clock):
    add(store)
    clock[0] = START + 7200
    store.ingest(10, [fixture(state="cancelled")])
    report = store.ingest(10, [fixture(source="pandascore", source_id="42", state="finished", score1=2, score2=0)])
    assert report["errors"]
    assert store.list_matches(10)[0]["state"] == "disputed"


def test_riot_pagination_stops_at_season_boundaries(monkeypatch):
    calls = []
    async def fake(session, url, params=None, headers=None):
        if url.endswith("getLeagues"):
            return {"data": {"leagues": [{"slug": "worlds", "id": "1"}]}}
        token = params.get("pageToken")
        calls.append(token)
        event = riot_event()
        if token == "past":
            event["startTime"], event["match"]["id"] = "2025-11-01T17:00:00Z", "past"
            links = {"older": "ancient", "newer": "present"}
        elif token == "future":
            event["startTime"], event["match"]["id"] = "2027-10-01T17:00:00Z", "future"
            links = {"older": "present", "newer": "distant"}
        else:
            assert token in (None, "present")
            links = {"older": "past", "newer": "future"}
        return {"data": {"schedule": {"events": [event], "pages": links}}}
    monkeypatch.setattr("fonctions.worlds2026.sources.get_json", fake)
    result = asyncio.run(LoLEsports("key").fetch(None))
    assert len(result.fixtures) == 1
    assert len(calls) == 4
    assert "ancient" not in calls and "distant" not in calls
