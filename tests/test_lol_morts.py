"""Timeline enregistrée, filtrage SQL et paginator interactions.py réel."""

import asyncio
import importlib.util
import sqlite3
import sys
import threading
import types
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pandas as pd
import pytest


@pytest.fixture
def module(monkeypatch, tmp_path):
    database = tmp_path / "timeline.sqlite"
    with sqlite3.connect(database) as connection:
        connection.executescript('''
            CREATE TABLE tracker (id_compte INTEGER, riot_id TEXT, riot_tagline TEXT);
            INSERT INTO tracker VALUES (1, 'joueur', 'EUW'), (2, 'joueur', 'OTHER');
            CREATE TABLE data_timeline_events (
                match_id TEXT, riot_id INTEGER, type TEXT, timestamp REAL,
                killerId INTEGER, victimId INTEGER, assistingParticipantIds TEXT
            );
        ''')

    def read(sql, *, params, index_col):
        with sqlite3.connect(database) as connection:
            return pd.read_sql_query(sql, connection, params=params, index_col=index_col).T

    monkeypatch.setitem(sys.modules, "fonctions.gestion_bdd", types.SimpleNamespace(lire_bdd_perso=read))
    monkeypatch.setitem(sys.modules, "fonctions.autocomplete", types.SimpleNamespace(autocomplete_riotid=AsyncMock()))
    path = Path(__file__).resolve().parents[1] / "cogs/lol_morts.py"
    spec = importlib.util.spec_from_file_location("lol_morts_under_test", path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)

    def insert(*rows):
        with sqlite3.connect(database) as connection:
            connection.executemany("INSERT INTO data_timeline_events VALUES (?, ?, ?, ?, ?, ?, ?)", rows)

    result.insert = insert
    return result


def event(time=5.30, killer=7, assists="[]", account=1, match="EUW1_123", kind="DEATHS"):
    return (match, account, kind, time, killer, 2, assists)


def test_sql_filters_player_tag_match_and_deaths_and_deduplicates(module):
    module.insert(event(12.05, assists="[8]"), event(5.30), event(5.30),
                  event(2, account=2), event(1, match="EUW1_456"), event(3, kind="CHAMPION_KILL"))
    deaths = module.load_deaths("EUW1_123", "joueur", "EUW")
    assert deaths["timestamp"].tolist() == [5.30, 12.05]
    assert module.load_deaths("EUW1_123", "joueur' OR 1=1 --", "EUW") is None
    assert module.load_deaths("EUW1_123", "joueur", "OTHER")["timestamp"].tolist() == [2]


@pytest.mark.parametrize("killer,assists,expected", [
    (7, [], "Oui"), (7, "[]", "Oui"), (7, "[8]", "Non"), (7, [8, 9], "Non"),
    (0, "[]", "Non"), (0, None, "Non"), (7, None, "Oui"), (7, float("nan"), "Oui"),
    (7, "null", "Oui"), (7, "invalid", "Indéterminé"), (None, "[]", "Indéterminé"),
])
def test_solo_assisted_and_execution(module, killer, assists, expected):
    assert module.solokill_label({"killerId": killer, "assistingParticipantIds": assists}) == expected


def test_pages_only_show_timing_and_solokill_without_reconverting_mmss(module):
    module.insert(event(5.30), event(12.05, assists="[8]"), event(60.09, killer=0))
    pages = module.death_pages(module.load_deaths("EUW1_123", "joueur", "EUW"))
    assert [page.description for page in pages] == [
        "**Timing :** 5:30\n**Solokill :** Oui",
        "**Timing :** 12:05\n**Solokill :** Non",
        "**Timing :** 60:09\n**Solokill :** Non",
    ]
    assert all(not page.fields for page in pages)


@pytest.mark.parametrize("count", [1, 3, 30])
def test_command_uses_one_real_paginator_with_one_page_per_death(module, monkeypatch, count):
    module.insert(*(event(time=i + 1.05) for i in range(count)))
    cog = object.__new__(module.LolMorts)
    cog.bot = types.SimpleNamespace(add_component_callback=Mock())
    ctx = types.SimpleNamespace(defer=AsyncMock(), send=AsyncMock(), author=types.SimpleNamespace(id=123))
    paginators = []
    factory = module.Paginator.create_from_embeds

    def create(*args):
        paginator = factory(*args, timeout=0)
        paginators.append(paginator)
        return paginator

    monkeypatch.setattr(module.Paginator, "create_from_embeds", create)
    read = module.lire_bdd_perso
    main_thread = threading.get_ident()

    def acknowledged_read(*args, **kwargs):
        ctx.defer.assert_awaited_once()
        assert threading.get_ident() != main_thread
        return read(*args, **kwargs)

    monkeypatch.setattr(module, "lire_bdd_perso", acknowledged_read)
    asyncio.run(module.LolMorts.lol_morts.callback(cog, ctx, " 123 ", "Jou eur", "#euw"))
    assert len(paginators) == 1
    assert len(paginators[0].pages) == count
    ctx.send.assert_awaited_once()
    cog.bot.add_component_callback.assert_called_once()
    for index in range(count):
        paginators[0].page_index = index
        payload = paginators[0].to_dict()
        assert payload["embeds"][0]["title"] == f"Mort {index + 1}/{count}"
        ids = [component["custom_id"] for row in payload["components"] for component in row["components"]]
        assert len(ids) == len(set(ids))


@pytest.mark.parametrize("has_timeline,expected", [
    (False, "Aucune timeline enregistrée"), (True, "Aucune mort enregistrée"),
])
def test_no_deaths_does_not_send_empty_paginator(module, has_timeline, expected):
    if has_timeline:
        module.insert(event(kind="LEVEL_UP"))
    cog = object.__new__(module.LolMorts)
    cog.bot = types.SimpleNamespace(add_component_callback=Mock())
    ctx = types.SimpleNamespace(defer=AsyncMock(), send=AsyncMock())
    asyncio.run(module.LolMorts.lol_morts.callback(cog, ctx, "euw1-123", "joueur", "EUW"))
    assert ctx.send.call_args.args[0].startswith(expected)
    cog.bot.add_component_callback.assert_not_called()
