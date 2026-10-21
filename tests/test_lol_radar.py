import asyncio
import copy
import importlib.util
import json
import os
from pathlib import Path
import sys
import types
from unittest.mock import AsyncMock

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fonctions import lol_radar as radar


def fixture():
    players = []
    for i in range(1, 11):
        players.append(dict(participantId=i, teamId=100 if i <= 5 else 200,
                            puuid=f"p{i}", teamPosition=("TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY")[(i-1) % 5],
                            kills=2, assists=3, deaths=0, visionScore=60,
                            firstBloodKill=False, firstBloodAssist=i == 5))
    frames = [dict(timestamp=t*60000, events=[], participantFrames={str(i): {
        "position": {"x": 5000 if i != 2 else 7000, "y": 5000},
        "championStats": {"health": 500}} for i in range(1, 11)}) for t in range(16)]
    frames[5]["events"] = [dict(type="CHAMPION_KILL", timestamp=299000, killerId=1, victimId=6, assistingParticipantIds=[5])]
    frames[15]["events"] = [dict(type="CHAMPION_KILL", timestamp=900000, killerId=5, victimId=7, assistingParticipantIds=[]),
                             dict(type="CHAMPION_KILL", timestamp=900001, killerId=2, victimId=8, assistingParticipantIds=[]),
                             dict(type="CHAMPION_KILL", timestamp=899000, killerId=0, victimId=9, assistingParticipantIds=[])]
    return {"info": {"mapId": 11, "gameDuration": 1800, "participants": players[::-1]}}, {"info": {"frames": frames}}


def test_snapshot_exact_values_and_dataframe_puuid_identity():
    detail, timeline = fixture()
    original = copy.deepcopy((detail, timeline))
    result = radar.build_snapshot(detail, timeline, "p5")
    assert result["metrics"] == {"kda": 5, "kp": 50, "vspm": 2, "fb": 100,
                                  "ka15": 2, "kp15": 100, "prox_adc": 100, "prox_jg": 100}
    assert result["coverage"]["prox_jg"] == {"near": 12, "valid": 12}
    assert result == radar.build_snapshot(pd.DataFrame(detail), timeline, "p5")
    assert (detail, timeline) == original
    assert json.loads(json.dumps(result, allow_nan=False)) == result
    assert radar.build_snapshot(detail, timeline, "missing") is None
    assert radar.build_snapshot(detail, timeline, "p4")["metrics"]["prox_adc"] is None
    assert radar.build_snapshot(detail, timeline, "p2")["metrics"]["prox_jg"] is None


def test_deduplicate_events_frames_and_boundary():
    detail, timeline = fixture()
    expected = radar.build_snapshot(detail, timeline, "p5")
    timeline["info"]["frames"].append(copy.deepcopy(timeline["info"]["frames"][5]))
    assert radar.build_snapshot(detail, timeline, "p5") == expected
    timeline["info"]["frames"][2]["participantFrames"]["2"]["position"]["x"] = 7001
    result = radar.build_snapshot(detail, timeline, "p5")
    assert result["coverage"]["prox_jg"] == {"near": 11, "valid": 12}


@pytest.mark.parametrize("kind", ["dead", "health", "base", "missing", "nan"])
def test_proximity_missing_values_never_count_as_far(kind):
    detail, timeline = fixture()
    for f in timeline["info"]["frames"]:
        s = f["participantFrames"]["2"]
        if kind == "dead": s["championStats"]["health"] = 0
        if kind == "health": s["championStats"] = {}
        if kind == "base": s["position"] = {"x": 100, "y": 100}
        if kind == "missing": del f["participantFrames"]["2"]
        if kind == "nan": s["position"]["x"] = float("nan")
    assert radar.build_snapshot(detail, timeline, "p5")["metrics"]["prox_jg"] is None


@pytest.mark.parametrize("kind", ["short", "gap", "late_start", "no_events", "empty"])
def test_incomplete_timeline_is_not_zero(kind):
    detail, timeline = fixture()
    frames = timeline["info"]["frames"]
    if kind == "short": detail["info"]["gameDuration"] = 899
    if kind == "gap": del frames[8]
    if kind == "late_start": del frames[0]
    if kind == "no_events": del frames[8]["events"]
    if kind == "empty": timeline = {}
    result = radar.build_snapshot(detail, timeline, "p5")["metrics"]
    assert result["ka15"] is None and result["kp15"] is None
    assert result["kda"] == 5


def test_zero_kills_zero_deaths_missing_and_nonfinite():
    detail, timeline = fixture()
    for p in detail["info"]["participants"]:
        p.update(kills=0, assists=0, visionScore=float("nan"))
    for f in timeline["info"]["frames"]: f["events"] = []
    result = radar.build_snapshot(detail, timeline, "p5")["metrics"]
    assert result["kp"] is None and result["kp15"] is None
    assert result["kda"] == 0 and result["ka15"] == 0 and result["vspm"] is None


def test_legacy_duration_and_aggregation_raw_values_not_clipped():
    row = {"match": {"kills": 5, "assists": 15, "deaths": 0, "team_kills": 25,
                     "vision_score": 61, "time": 30.30}, "details": None}
    data = radar.aggregate([row, {"match": {}}])
    assert data["kda"] == {"value": 20, "n": 1, "score": 100}
    assert data["vspm"]["value"] == 2
    assert data["kp"]["value"] == 80
    assert data["fb"] == {"value": None, "n": 0, "score": None}
    row["details"] = json.dumps({"radar": {"version": 1, "metrics": {"fb": 0}}})
    assert radar.aggregate([row])["fb"]["n"] == 1
    assert radar.aggregate([row])["kda"]["value"] is None


def test_query_forces_ranked_and_full_seasons_with_optional_table():
    sql, params = radar.radar_query("A'B", "#euw", 123, 16, role_filter="SUPPORT", champion="Kai'Sa")
    assert "A'B" not in sql and params["riot_id"] == "a'b"
    assert params["champion"] == "kaisa" and params["tag"] == "EUW"
    assert params["season"] == 16 and params["previous_season"] == 15
    assert "t.server_id = :guild" in sql
    assert "m.mode = 'RANKED'" in sql and "mode" not in params
    assert "m.season IN (:season, :previous_season)" in sql and "LIMIT" not in sql
    assert "PARTITION BY m.match_id" in sql and "d.joueur = m.joueur" in sql
    assert "match_recap_details" not in radar.radar_query("a", "b", 1, 16, has_details=False)[0]
    for season in (0, -1, None, True, 1.5):
        with pytest.raises(ValueError): radar.radar_query("a", "b", 1, season)
    with pytest.raises(TypeError): radar.radar_query("a", "b", 1, 16, mode="FLEX")


def test_loader_uses_complete_seasons_and_respects_search_path(monkeypatch):
    calls = []
    def read(sql, **kwargs):
        calls.append(sql)
        if "to_regclass" in sql:
            return pd.DataFrame([{"relation": None}]).T
        # Deliberately interleaved: assignment must depend on season, not row position.
        return pd.DataFrame([{"match": {"kills": v, "assists": 0, "deaths": 1, "season": s}, "details": None}
                             for v, s in [(10, 16), (2, 15), (8, 16)] * 60]).T
    monkeypatch.setitem(sys.modules, "fonctions.gestion_bdd", types.SimpleNamespace(lire_bdd_perso=read))
    data = radar.load_radar("a", "b", 1, 16)
    assert data["games"] == 120 and data["previous_games"] == 60
    assert data['season'] == 16 and data['previous_season'] == 15
    assert data["current"]["kda"]["value"] == 9 and data["previous"]["kda"]["value"] == 2
    assert "public." not in calls[0] and "match_recap_details" not in calls[1]


def load_cog(monkeypatch):
    monkeypatch.setitem(sys.modules, "fonctions.autocomplete", types.SimpleNamespace(autocomplete_riotid=AsyncMock()))
    spec = importlib.util.spec_from_file_location("radar_cog_test", ROOT / "cogs/lol_radar.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("result", [None, b"png", ValueError("Filtre invalide"), RuntimeError("DB")])
def test_real_interactions_command_defers_and_handles_results(monkeypatch, result):
    cog = load_cog(monkeypatch)
    order = []
    ctx = types.SimpleNamespace(guild_id=1, defer=AsyncMock(side_effect=lambda **kw: order.append("defer")), send=AsyncMock())
    def build(*args):
        assert order == ["defer"]
        if isinstance(result, Exception): raise result
        return result
    monkeypatch.setattr(cog, "build_radar", build)
    asyncio.run(cog.LolRadar.lol_radar.callback(None, ctx, "player", "EUW", 16))
    assert ctx.send.await_count == 1
    if result == b"png":
        assert "file" in ctx.send.call_args.kwargs
    elif result is None:
        assert "Aucune partie" in ctx.send.call_args.args[0]
    elif isinstance(result, ValueError):
        assert ctx.send.call_args.args[0] == "Filtre invalide"
    else:
        assert "temporairement indisponible" in ctx.send.call_args.args[0]


def test_discord_requires_season_and_removes_games_and_mode(monkeypatch):
    cog = load_cog(monkeypatch)
    options = [o.to_dict() for o in cog.LolRadar.lol_radar.options]
    assert {o['name'] for o in options if o['required']} == {"riot_id", "riot_tag", "saison"}
    assert {o['name'] for o in options if not o['required']} == {"role", "champion"}


def test_render_full_partial_empty_and_concurrent():
    from concurrent.futures import ThreadPoolExecutor
    from PIL import Image
    from io import BytesIO
    detail, timeline = fixture()
    row = {"match": {}, "details": {"radar": radar.build_snapshot(detail, timeline, "p5")}}
    full = radar.aggregate([row])
    data = {"current": full, "previous": full, "games": 1, "previous_games": 1, "season": 16, "previous_season": 15}
    with ThreadPoolExecutor(max_workers=2) as pool:
        images = list(pool.map(lambda _: radar.render_radar(data, "Test#EUW", "RANKED • SUPPORT"), range(2)))
    assert images[0] == images[1]
    assert Image.open(BytesIO(images[0])).size == (1400, 980)
    data["current"] = radar.aggregate([{"match": {"kills": 5, "assists": 2, "deaths": 2}}])
    data["previous"] = radar.aggregate([])
    assert radar.render_radar(data, "Partiel", "")[:8] == b"\x89PNG\r\n\x1a\n"


@pytest.mark.skipif(not os.environ.get("RADAR_TEST_DSN"), reason="PostgreSQL optionnel")
def test_postgres_query_dedup_guild_filters_and_search_path():
    import psycopg
    from psycopg import sql as pgsql
    import re
    import uuid
    schema = "radar_" + uuid.uuid4().hex
    with psycopg.connect(os.environ["RADAR_TEST_DSN"]) as conn:
        conn.execute(pgsql.SQL("CREATE SCHEMA {}").format(pgsql.Identifier(schema)))
        conn.execute(pgsql.SQL("SET LOCAL search_path TO {}").format(pgsql.Identifier(schema)))
        conn.execute("CREATE TABLE tracker (id_compte int, riot_id text, riot_tagline text, server_id bigint)")
        conn.execute("CREATE TABLE matchs (id int, match_id text, joueur int, datetime timestamp, mode text, role text, champion text, season int)")
        conn.execute("CREATE TABLE match_recap_details (match_id text, joueur int, data jsonb, PRIMARY KEY(match_id,joueur))")
        conn.execute("INSERT INTO tracker VALUES (1,'alice','EUW',123),(2,'alice','EUW',456)")
        for i, mid, who, role in [(1,'a',1,'SUPPORT'),(2,'a',1,'SUPPORT'),(3,'b',1,'SUPPORT'),(4,'c',1,'MID'),(5,'d',2,'SUPPORT')]:
            conn.execute("INSERT INTO matchs VALUES (%s,%s,%s,now(), 'RANKED',%s,'Ahri',16)", (i, mid, who, role))
        for i, mode, season in [(6, 'FLEX', 16), (7, 'NORMAL', 16), (8, 'RANKED', 14), (9, 'RANKED', 15),
                                (10, 'FLEX', 15), (11, 'ARAM', 16), (12, 'SWIFTPLAY', 16)]:
            conn.execute("INSERT INTO matchs VALUES (%s,%s,1,now(),%s,'SUPPORT','Ahri',%s)", (i, str(i), mode, season))
        for i in range(20, 140):
            conn.execute("INSERT INTO matchs VALUES (%s,%s,1,now(),'RANKED','SUPPORT','Ahri',16)", (i, str(i)))
        conn.execute("INSERT INTO match_recap_details VALUES ('b',1,'{\"radar\":{\"version\":1}}')")
        query, params = radar.radar_query("alice", "EUW", 123, 16, role_filter="SUPPORT", champion="Ahri")
        rows = conn.execute(re.sub(r":(\w+)", r"%(\1)s", query), params).fetchall()
        assert len(rows) == 123
        assert {r[0]["match_id"] for r in rows} == {'b', 'a', '9'} | {str(i) for i in range(20, 140)}
        assert all(r[0]['mode'] == 'RANKED' and r[0]['season'] in (15, 16) for r in rows)
        assert next(r for r in rows if r[0]['match_id'] == 'b')[1]["radar"]["version"] == 1
        assert conn.execute("SELECT to_regclass('match_recap_details')").fetchone()[0]
        conn.rollback()
