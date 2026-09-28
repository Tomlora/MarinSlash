"""Exercise the real worker and cog methods without a Discord/Riot connection."""
import ast
import asyncio
from collections import Counter
import importlib.util
import io
import logging
from pathlib import Path
import threading
from types import SimpleNamespace

import aiohttp
import interactions
import pandas as pd
from PIL import Image
import pytest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("match_worker_test", ROOT / "fonctions/match_worker.py")
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)


def method(name, **dependencies):
    """Load an actual handler while avoiding bot startup and production secrets."""
    tree = ast.parse((ROOT / "cogs/leagueoflegends.py").read_text(encoding="utf-8"))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "LeagueofLegends")
    node = next(n for n in cls.body if isinstance(n, ast.AsyncFunctionDef) and n.name == name)
    node.decorator_list = []
    namespace = dict(asyncio=asyncio, io=io, interactions=interactions, logging=logging,
                     run_match_job=worker.run_match_job, Path=Path, pd=pd,
                     SlashContext=object, chan_discord=object, aiohttp=aiohttp)
    namespace.update(dependencies)
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(ROOT / "cogs/leagueoflegends.py"), "exec"), namespace)
    return namespace[name]


async def wait_until(predicate):
    async with asyncio.timeout(4):
        while not predicate():
            await asyncio.sleep(0.005)


def test_blocking_job_keeps_heartbeat_responsive_and_owns_its_http_session():
    async def scenario():
        loop = asyncio.get_running_loop()
        main_thread = threading.get_ident()
        entered, release = threading.Event(), threading.Event()
        paths, sessions = [], []

        async def build(*, image_path):
            assert threading.get_ident() != main_thread
            assert asyncio.get_running_loop() is not loop
            async with aiohttp.ClientSession() as session:
                sessions.append(session)
                entered.set()
                # Models a slow synchronous SQL/Pillow call; only the bot can release it.
                assert release.wait(3), "Discord loop was blocked by generation"
                path = Path(image_path + ".png")
                paths.append(path)
                Image.new("RGB", (16, 16), "blue").save(path)
                return path.read_bytes()

        task = asyncio.create_task(worker.run_match_job(build))
        try:
            await wait_until(entered.is_set)
            for _ in range(10):
                await asyncio.sleep(0.005)  # Simulated Discord heartbeat.
                assert not task.done()
        finally:
            release.set()
        png = await task
        assert Image.open(io.BytesIO(png)).size == (16, 16)
        assert sessions[0].closed
        assert not paths[0].parent.exists()

    asyncio.run(scenario())


def test_cancelled_worker_does_not_overlap_next_job_or_leave_temp_files():
    async def scenario():
        entered, release = threading.Event(), threading.Event()
        order, paths = [], []

        async def build(label, *, image_path):
            paths.append(Path(image_path))
            order.append(label + " start")
            if label == "one":
                entered.set()
                assert release.wait(3)
            order.append(label + " end")
            return label

        first = asyncio.create_task(worker.run_match_job(build, "one"))
        await wait_until(entered.is_set)
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
        second = asyncio.create_task(worker.run_match_job(build, "two"))
        try:
            await asyncio.sleep(0.03)
            assert order == ["one start"]
        finally:
            release.set()
        assert await second == "two"
        assert order == ["one start", "one end", "two start", "two end"]
        assert paths[0] != paths[1]
        assert all(not path.parent.exists() for path in paths)

    asyncio.run(scenario())


def test_failed_job_cleans_files_propagates_error_and_releases_queue():
    async def scenario():
        directories = []

        async def fail(*, image_path):
            path = Path(image_path + ".png")
            path.write_bytes(b"partial PNG")
            directories.append(path.parent)
            raise ValueError("database unavailable")

        with pytest.raises(ValueError, match="database unavailable"):
            await worker.run_match_job(fail)
        assert not directories[0].exists()

        async def good(*, image_path):
            return 42

        assert await worker.run_match_job(good) == 42

    asyncio.run(scenario())


@pytest.mark.parametrize("capture", [False, True])
def test_actual_printinfo_preserves_buttons_and_challenge_loop(capture):
    async def scenario():
        main_thread = threading.get_ident()
        main_loop = asyncio.get_running_loop()
        original = [interactions.ActionRow(*[
            interactions.Button(style=1, label=label, custom_id=label)
            for label in ["Records", "Teamfight", "Ganks", "Détail du score", "Différentiel d'or"]
        ])]

        async def build(*args, image_path, **kwargs):
            assert threading.get_ident() != main_thread
            assert kwargs["check_records"] is False
            return interactions.Embed(title="Match"), "RANKED", b"PNG", original, "EUW1_1", "puuid"

        async def snapshot(joueur, puuid, match_id, **kwargs):
            assert asyncio.get_running_loop() is main_loop
            assert (joueur, puuid, match_id, kwargs["capture"]) == (1, "puuid", "EUW1_1", capture)
            return {}

        # Load the actual component composer (no DB imports).
        ui_spec = importlib.util.spec_from_file_location("challenge_ui_test", ROOT / "fonctions/challenge_ui.py")
        ui = importlib.util.module_from_spec(ui_spec)
        ui_spec.loader.exec_module(ui)
        handler = method("printInfo", recap_snapshot=snapshot, recap_components=ui.recap_components)
        owner = SimpleNamespace(_build_recap=build, _recap_counts=Counter(), _recap_tasks=set(), compte_loading=set())
        result = await handler(owner, 1, "Player", "EUW", 0, True, capture_challenges=capture, check_records=False)
        embed, mode, file, components = result
        assert mode == "RANKED" and file.open_file().read() == b"PNG"
        assert file.file_name == "resume.png"
        assert [b.label for row in components for b in row.components] == [
            "Records", "Teamfight", "Ganks", "Détail du score", "Différentiel d'or", "Challenges",
        ]
        assert not owner.compte_loading and not owner._recap_counts

    asyncio.run(scenario())


def test_actual_printinfo_cancellation_keeps_account_busy_until_cleanup():
    async def scenario():
        entered, release = threading.Event(), threading.Event()

        async def build(*args, image_path, **kwargs):
            entered.set()
            assert release.wait(3)
            return {}, "Doublon", None, None, None, None

        owner = SimpleNamespace(_build_recap=build, _recap_counts=Counter(), _recap_tasks=set(), compte_loading=set())
        handler = method("printInfo")
        task = asyncio.create_task(handler(owner, 1, "Player", "EUW", 0, True))
        await wait_until(entered.is_set)
        try:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert "player" in owner.compte_loading
            assert len(owner._recap_tasks) == 1
        finally:
            release.set()
        await wait_until(lambda: not owner._recap_tasks)
        assert not owner.compte_loading

    asyncio.run(scenario())


@pytest.mark.parametrize("fail", [False, True])
def test_actual_pipeline_closes_session_on_duplicate_or_error(fail):
    sessions = []

    class FakeMatch:
        def __init__(self, **kwargs):
            self.session = None
            self.thisQId = 420
            self.thisQ = "RANKED"
            self.season = 16
            self.last_match = "EUW1_1"
            self.id_compte = 1

        async def get_data_riot(self):
            self.session = aiohttp.ClientSession()
            sessions.append(self.session)
            if fail:
                raise RuntimeError("Riot unavailable")

        async def run(self, **kwargs):
            pass

    def read(sql, **kwargs):
        if sql.startswith('SELECT tracker.discord'):
            return {0: {"discord": 1}}
        return pd.DataFrame({"season": [16], "discord": [1]}).T

    handler = method("_build_recap", MatchLol=FakeMatch, timer=lambda fn: fn,
                     get_stat_null_rules=lambda: {}, lire_bdd_perso=read)

    async def scenario():
        if fail:
            with pytest.raises(RuntimeError, match="Riot unavailable"):
                await worker.run_match_job(handler, None, 1, "Player", "EUW", 0, True)
        else:
            result = await worker.run_match_job(handler, None, 1, "Player", "EUW", 0, True)
            assert result[1] == "Doublon"
        assert sessions[0].closed

    asyncio.run(scenario())


def test_actual_game_does_sql_off_loop_and_sends_on_discord_loop():
    async def scenario():
        main_thread = threading.get_ident()
        calls, sent = [], []

        def db(label, result):
            def call(*args, **kwargs):
                assert threading.get_ident() != main_thread, label
                calls.append(label)
                return result
            return call

        def read(sql, **kwargs):
            assert threading.get_ident() != main_thread
            return pd.DataFrame({0: {"save_records": True}}) if "save_records" in sql else pd.DataFrame()

        async def defer(**kwargs):
            assert threading.get_ident() == main_thread

        async def send(**kwargs):
            assert threading.get_ident() == main_thread
            sent.append(kwargs)

        components = [interactions.Button(style=1, label="Challenges", custom_id="test")]

        async def print_info(*args, **kwargs):
            assert kwargs["check_records"] is True
            return interactions.Embed(title="Match"), "RANKED", "file", components

        ctx = SimpleNamespace(guild_id=1, author=SimpleNamespace(id=2), defer=defer, send=send)
        handler = method("game", get_tag=db("tag", "EUW"),
                         chan_discord=db("channels", SimpleNamespace()),
                         get_id_account_bdd=db("account", 1), lire_bdd_perso=read)
        await handler(SimpleNamespace(printInfo=print_info), ctx, "Player", ce_channel=True)
        assert calls == ["tag", "channels", "account"]
        assert sent[0]["components"] is components

    asyncio.run(scenario())


@pytest.mark.parametrize("mode,channel", [("RANKED", 10), ("ARENA 2v2", 20), ("ARAM", 30)])
def test_actual_live_recap_keeps_routing_and_challenge_capture(mode, channel):
    async def scenario():
        thread = threading.get_ident()
        buttons = object()
        events = []

        async def prepare(*args, **kwargs):
            assert kwargs["capture_challenges"] is True
            assert kwargs["check_records"] is False
            return interactions.Embed(title="Match"), mode, "PNG", buttons

        async def send(**kwargs):
            assert threading.get_ident() == thread
            assert kwargs["components"] is buttons
            events.append("sent")

        async def fetch_channel(value):
            assert value == channel
            return SimpleNamespace(send=send)

        owner = SimpleNamespace(printInfo=prepare, bot=SimpleNamespace(fetch_channel=fetch_channel))
        channels = SimpleNamespace(server_id=1, tracklol=10, tft=20, lol_others=30)
        await method("printLive")(owner, 1, "player", "EUW", channels,
                                  tracker_challenges=True, check_records=False)
        assert events == ["sent"]

    asyncio.run(scenario())


def test_actual_tracker_tick_moves_sql_off_loop_and_calls_live_recap():
    async def scenario():
        thread = threading.get_ident()
        events = []

        def rows(*args):
            assert threading.get_ident() != thread
            return [(1, "player", "EUW", "old", 2, False, False, 3, "puuid",
                     True, True, 0, 1, False, "player", "EUW", True)]

        def write(*args):
            assert threading.get_ident() != thread
            events.append("SQL")

        def channels(*args):
            assert threading.get_ident() != thread
            return object()

        async def last_game(*args):
            return "EUW1_1"

        async def account(*args):
            return {"gameName": "player", "tagLine": "EUW"}

        async def live(*args, **kwargs):
            assert threading.get_ident() == thread
            assert kwargs["tracker_challenges"] is True
            assert kwargs["identifiant_game"] == "EUW1_1"
            events.append("live")

        async def rank(*args):
            events.append("rank")

        owner = SimpleNamespace(_update_lock=asyncio.Lock(), printLive=live, updaterank=rank)
        handler = method("update", fetch_rows=rows, requete_perso_bdd=write,
                         chan_discord=channels, getId_with_puuid=last_game,
                         get_summoner_by_puuid=account)
        await handler(owner)
        assert events == ["SQL", "live", "rank"]

    asyncio.run(scenario())


def test_match_run_reuses_session_created_for_riot():
    tree = ast.parse((ROOT / "fonctions/match/matchlol.py").read_text(encoding="utf-8"))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "MatchLol")
    node = next(n for n in cls.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "run")
    node.decorator_list = []
    namespace = {"aiohttp": aiohttp}
    exec(compile(ast.Module(body=[node], type_ignores=[]), "matchlol.py", "exec"), namespace)

    async def scenario():
        async def step(*args, **kwargs):
            pass

        async with aiohttp.ClientSession() as session:
            owner = SimpleNamespace(session=session, thisQ="ARAM", thisId=0, moba_ok=False)
            for name in ("prepare_data", "_extract_team_data", "_extract_comparison_data",
                         "_extract_masteries", "_load_items_data", "_load_rank_data_riot",
                         "calculate_all_scores", "save_player_scoring_data", "detection_gap",
                         "calcul_badges", "traitement_objectif"):
                setattr(owner, name, step)
            await namespace["run"](owner)
            assert owner.session is session

    asyncio.run(scenario())
