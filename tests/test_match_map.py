"""Carte dix joueurs : données Riot synthétiques, SDK réel, aucun service externe."""
import asyncio
import copy
import importlib.util
import json
import sys
import threading
import types
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock

import interactions
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("map_under_test", ROOT / "fonctions/match/map_view.py")
MAP = importlib.util.module_from_spec(spec)
spec.loader.exec_module(MAP)


def riot_fixture():
    champions = ["Ornn", "Viego", "Ahri", "Jinx", "Leona", "Garen", "LeeSin", "Syndra", "Ezreal", "Nautilus"]
    players = [{"participantId": i, "teamId": 100 if i <= 5 else 200,
                "riotIdGameName": f"Joueur {i}", "championName": champions[i - 1]}
               for i in range(1, 11)]
    frames = []
    for minute in range(12):
        samples = {str(i): {"position": {"x": 1000 + (i * 1100 + minute * 600) % 12500,
                                        "y": 1200 + (i * 800 + minute * 1100) % 12000}}
                   for i in range(1, 11)}
        events = [{"type": "CHAMPION_KILL", "victimId": i, "killerId": (i + 4) % 10 + 1,
                   "timestamp": minute * 60_000 - 8000 + i * 100,
                   "position": samples[str(i)]["position"]}
                  for i in range(1, 11) if minute in (2, 4, 7)]
        frames.append({"timestamp": minute * 60_000, "participantFrames": samples, "events": events})
    frames.append({"timestamp": 692_000, "participantFrames": {}, "events": [
        {"type": "CHAMPION_KILL", "victimId": 10, "killerId": 0, "timestamp": 691_000, "position": {"x": 13000, "y": 13000}}]})
    return {"info": {"mapId": 11, "participants": players[::-1]}}, {"info": {"frames": frames}}


def sample_map():
    return MAP.build_map_snapshot(*riot_fixture())


def test_all_ten_native_ids_teams_and_last_partial_frame_are_preserved():
    detail, timeline = riot_fixture()
    before = copy.deepcopy((detail, timeline))
    data = MAP.build_map_snapshot(detail, timeline)
    assert [p["id"] for p in data["players"]] == list(range(1, 11))
    assert [p["team"] for p in data["players"]] == [100] * 5 + [200] * 5
    assert {p[0] for p in data["positions"]} == set(range(1, 11))
    assert data["deaths"][-1] == {"id": 10, "t": 691000, "xy": [13000, 13000], "killer": 0}
    assert data["end"] == 692000
    assert json.loads(json.dumps(data, allow_nan=False)) == data
    assert (detail, timeline) == before


def test_missing_positions_are_gaps_and_invalid_death_positions_remain_explicit():
    detail, timeline = riot_fixture()
    frames = timeline["info"]["frames"]
    del frames[1]["participantFrames"]["7"]
    frames[2]["participantFrames"]["7"]["position"]["x"] = float("nan")
    frames[3]["participantFrames"]["7"]["position"] = {"x": 0, "y": 0}
    frames[-1]["events"][0]["position"]["x"] = -1
    frames[-1]["events"].append(copy.deepcopy(frames[-1]["events"][0]))
    data = MAP.build_map_snapshot(detail, timeline)
    assert [e["t"] for e in MAP.player_events(data, 7, 0, "moves")] == [0, 240000, 300000]
    assert data["deaths"][-1]["xy"] is None
    assert len([d for d in data["deaths"] if d["t"] == 691000]) == 1
    json.dumps(data, allow_nan=False)


@pytest.mark.parametrize("map_id,players", [(12, 10), (11, 8)])
def test_unsupported_maps_or_rosters_are_not_projected_on_summoners_rift(map_id, players):
    detail, timeline = riot_fixture()
    detail["info"]["mapId"] = map_id
    detail["info"]["participants"] = detail["info"]["participants"][:players]
    assert MAP.build_map_snapshot(detail, timeline) is None


def test_time_boundaries_selection_and_coordinate_orientation():
    data = sample_map()
    data["deaths"] += [{"id": 1, "t": 300000, "xy": [500, 700], "killer": 0}]
    assert not any(d["t"] == 300000 for d in MAP.player_events(data, 1, 0, "deaths"))
    assert any(d["t"] == 300000 for d in MAP.player_events(data, 1, 1, "deaths"))
    assert MAP.window(data, 999) == (600000, 692000)
    assert MAP.last_page({"end": 600000}) == 1
    assert [p["id"] for p in MAP.selection(data, (1 << 1) | (1 << 9))] == [2, 10]
    assert MAP.map_pixel([0, 15000], 301) == (0, 0)
    assert MAP.map_pixel([15000, 0], 301) == (300, 300)


@pytest.mark.parametrize("mask", [1, 513, 31, 1023])
@pytest.mark.parametrize("mode", ["deaths", "moves"])
def test_native_controls_render_and_discord_limits(mask, mode, monkeypatch):
    data = sample_map()
    monkeypatch.setattr(MAP, "load_map", lambda *args: data)
    embed, png, rows = MAP.map_response("EUW1_1234567890", 999999999, mode, 99, mask)
    payload = [row.to_dict() for row in rows]
    assert len(payload) <= 5
    ids = [c["custom_id"] for row in payload for c in row["components"]]
    assert len(ids) == len(set(ids)) and all(len(i) <= 100 for i in ids)
    menu = payload[1]["components"][0]
    assert len(menu["options"]) == 10 and menu["max_values"] == 10
    assert sum(o.get("default", False) for o in menu["options"]) == mask.bit_count()
    assert payload[-1]["components"][1]["disabled"] is True
    assert len(embed) < 6000
    assert all(len(f.value) <= 1024 for f in embed.fields)
    with Image.open(BytesIO(png)) as image:
        assert image.width >= 700 and image.height > 500
    assert len(png) < 8 * 1024 * 1024


@pytest.fixture
def cog_module(monkeypatch):
    monkeypatch.setitem(sys.modules, "fonctions.match.map_view", MAP)
    spec = importlib.util.spec_from_file_location("map_cog_under_test", ROOT / "cogs/lol_match_map.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def cog_instance(module):
    # Contourner seulement l'enregistrement Extension dans un client connecté.
    cog = object.__new__(module.LolMatchMap)
    cog._render_task = None
    return cog


def test_callbacks_preserve_filters_ack_first_and_replace_attachments(cog_module, monkeypatch):
    cog = cog_instance(cog_module)
    calls = []
    async def defer(**kwargs):
        calls.append(("ack", kwargs))
    ctx = types.SimpleNamespace(defer=defer, edit=AsyncMock(), send=AsyncMock(),
                                custom_id="lolmap_players_EUW1_123_7_moves_1_1023", values=["2", "10"])
    def response(*args):
        assert calls[0] == ("ack", {"edit_origin": True})
        calls.append(("render", args))
        return interactions.Embed(title="Carte"), b"png", []
    monkeypatch.setattr(cog_module, "map_response", response)
    asyncio.run(cog_module.LolMatchMap.on_action.callback(cog, ctx))
    assert calls[-1][1] == ("EUW1_123", 7, "moves", 1, 514)
    assert ctx.edit.call_args.kwargs["attachments"] == []
    assert ctx.edit.call_args.kwargs["file"].file_name == "match_map.png"
    ctx.send.assert_not_called()


def test_first_open_is_private_and_old_snapshots_are_explained(cog_module, monkeypatch):
    cog = cog_instance(cog_module)
    ctx = types.SimpleNamespace(defer=AsyncMock(), send=AsyncMock(), custom_id="lolview_open_map_EUW1_123_7")
    monkeypatch.setattr(cog_module, "map_response", lambda *args: None)
    asyncio.run(cog_module.LolMatchMap.on_open.callback(cog, ctx))
    ctx.defer.assert_awaited_once_with(ephemeral=True)
    assert ctx.send.call_args.kwargs["ephemeral"] is True
    assert "n'est pas enregistrée" in ctx.send.call_args.kwargs["content"]


def test_timeout_does_not_enqueue_another_thread_and_allows_retry(cog_module, monkeypatch):
    cog = cog_instance(cog_module)
    release = threading.Event()
    calls = []
    def response(*args):
        calls.append(args)
        release.wait(2)
        return None
    monkeypatch.setattr(cog_module, "map_response", response)
    monkeypatch.setattr(cog_module, "LOAD_TIMEOUT", 0.01)
    async def scenario():
        ctx = types.SimpleNamespace(defer=AsyncMock(), send=AsyncMock())
        try:
            await cog._show(ctx, "EUW1_123", 7)
            assert "trop de temps" in ctx.send.call_args.kwargs["content"]
            await cog._show(ctx, "EUW1_123", 7)
            assert "en cours" in ctx.send.call_args.kwargs["content"]
            assert len(calls) == 1
        finally:
            release.set()
            await cog._render_task
        monkeypatch.setattr(cog_module, "LOAD_TIMEOUT", 1)
        await cog._show(ctx, "EUW1_123", 7)
        assert len(calls) == 2
    asyncio.run(scenario())


def test_close_uses_real_sdk_and_clears_image(cog_module):
    http = types.SimpleNamespace(post_initial_response=AsyncMock(), edit_interaction_message=AsyncMock(return_value=None))
    client = types.SimpleNamespace(http=http, app=types.SimpleNamespace(id=123))
    ctx = types.SimpleNamespace(client=client, token="test", id=456, deferred=False, responded=False,
                                custom_id="lolmap_close_EUW1_123_7_deaths_0_1023")
    for name in ("defer", "_defer", "edit"):
        setattr(ctx, name, types.MethodType(getattr(interactions.ComponentContext, name), ctx))
    asyncio.run(cog_module.LolMatchMap.on_action.callback(cog_instance(cog_module), ctx))
    payload = http.edit_interaction_message.call_args.kwargs["payload"]
    assert payload["attachments"] == payload["components"] == payload["embeds"] == []


def test_filter_update_uploads_new_png_with_real_sdk(cog_module, monkeypatch):
    data = sample_map()
    monkeypatch.setattr(MAP, "load_map", lambda *args: data)
    http = types.SimpleNamespace(post_initial_response=AsyncMock(), edit_interaction_message=AsyncMock(return_value=None))
    client = types.SimpleNamespace(http=http, app=types.SimpleNamespace(id=123))
    ctx = types.SimpleNamespace(client=client, token="test", id=456, deferred=False, responded=False,
                                custom_id="lolmap_mode_EUW1_123_7_moves_1_1023")
    for name in ("defer", "_defer", "edit"):
        setattr(ctx, name, types.MethodType(getattr(interactions.ComponentContext, name), ctx))
    ctx.send = AsyncMock(side_effect=AssertionError("Le changement de filtre doit modifier le message privé"))
    asyncio.run(cog_module.LolMatchMap.on_action.callback(cog_instance(cog_module), ctx))
    kwargs = http.edit_interaction_message.call_args.kwargs
    assert kwargs["payload"]["attachments"] == []
    assert kwargs["payload"]["embeds"][0]["image"]["url"] == "attachment://match_map.png"
    assert len(kwargs["files"]) == 1
    assert kwargs["files"][0].file_name == "match_map.png"


def test_old_snapshot_load_is_empty_without_riot_fallback(monkeypatch):
    details = types.SimpleNamespace(load_details=lambda *args: ({}, {"gold": []}, {}))
    monkeypatch.setitem(sys.modules, "fonctions.match.recap_details", details)
    # L'import relatif doit être résolu sous le nom de package de production.
    monkeypatch.setattr(MAP, "__package__", "fonctions.match")
    assert MAP.load_map("EUW1_123", 7) is None
    details.load_details = lambda *args: ({}, {"map": sample_map()}, {})
    assert len(MAP.load_map("EUW1_123", 7)["players"]) == 10
