"""Sélection SQL réelle et commande Discord, sans accès aux données du bot."""
import asyncio
from datetime import datetime, timedelta, timezone
import importlib.util
import os
from pathlib import Path
import re
import sqlite3
import sys
import threading
import types
from unittest.mock import AsyncMock, Mock

import pandas as pd
import pytest

from fonctions.recap_filters import GAME_COUNTS, recap_query


NOW = datetime(2026, 10, 11, 12, tzinfo=timezone.utc)
COLUMNS = ('id', 'match_id', 'joueur', 'champion', 'datetime', 'mode',
           'id_participant', 'mvp', 'time', 'kills', 'deaths', 'assists',
           'quadra', 'penta', 'tier', 'rank', 'kp', 'kda', 'victoire',
           'ecart_lp', 'ecart_gold', 'solokills')


@pytest.fixture(params=['sqlite', 'postgres'])
def database(request, tmp_path):
    postgres = request.param == 'postgres'
    if postgres:
        dsn = os.environ.get('RECAP_TEST_DSN')
        if not dsn:
            pytest.skip('RECAP_TEST_DSN absent : PostgreSQL jetable utilisé en CI')
        import psycopg
        conn = psycopg.connect(dsn, autocommit=True)
        conn.execute('DROP SCHEMA IF EXISTS recap_test CASCADE')
        conn.execute('CREATE SCHEMA recap_test')
        conn.execute('SET search_path TO recap_test')
    else:
        conn = sqlite3.connect(tmp_path / 'recap.sqlite', check_same_thread=False)
        conn.create_function('REGEXP_REPLACE', 4, lambda value, pattern, sub, flags: re.sub(pattern, sub, value))

    def execute(sql, params=None):
        if postgres:
            sql = re.sub(r':(\w+)', r'%(\1)s', sql)
        return conn.execute(sql, params or {})

    execute('CREATE TABLE tracker (id_compte INTEGER, riot_id TEXT, riot_tagline TEXT)')
    execute("INSERT INTO tracker VALUES (1, 'joueur', 'EUW'), (2, 'joueur', 'OTHER'), (3, 'autre', 'EUW')")
    types_by_name = dict.fromkeys(COLUMNS, 'INTEGER')
    types_by_name.update({name: 'TEXT' for name in ['match_id', 'champion', 'mode', 'tier', 'rank']})
    types_by_name['datetime'] = 'TIMESTAMPTZ' if postgres else 'TEXT'
    types_by_name['victoire'] = 'BOOLEAN'
    execute('CREATE TABLE matchs (' + ', '.join(f'{name} {kind}' for name, kind in types_by_name.items()) + ')')
    execute('CREATE TABLE prev_lol (riot_id TEXT, riot_tag TEXT, match_id TEXT, win INTEGER, lose INTEGER, team TEXT, victory_predicted BOOLEAN)')

    def insert(number, **overrides):
        row = dict(zip(COLUMNS, [number, f'EUW1_{number}', 1, 'Ahri', NOW - timedelta(days=number),
                               'RANKED', 0, 2, 30, 5, 2, 8, 0, 0, 'GOLD', 'IV', 60, 6,
                               True, 20, 100, 1]))
        row.update(overrides)
        if not postgres:
            row['datetime'] = row['datetime'].isoformat()
        execute('INSERT INTO matchs VALUES (' + ', '.join(':' + name for name in COLUMNS) + ')', row)

    def read(sql, *, params, index_col):
        if not postgres:
            params = {k: v.isoformat() if isinstance(v, datetime) else v for k, v in params.items()}
        cursor = execute(sql, params)
        df = pd.DataFrame(cursor.fetchall(), columns=[col[0] for col in cursor.description])
        if index_col:
            df.set_index(index_col, inplace=True)
        return df.T

    def query(**kwargs):
        sql, params, _ = recap_query('Jou eur', 'euw', now=NOW, **kwargs)
        return read(sql, params=params, index_col='id').T.drop_duplicates('match_id')

    yield types.SimpleNamespace(insert=insert, query=query, read=read, execute=execute)
    conn.close()


@pytest.mark.parametrize('count', GAME_COUNTS)
def test_latest_distinct_matches_after_champion_mode_account_filters(database, count):
    for number in range(1, 111):
        database.insert(number)
    database.insert(500, match_id='EUW1_1', datetime=NOW - timedelta(days=1))
    database.insert(501, champion='Lux', datetime=NOW)
    database.insert(502, mode='ARAM', datetime=NOW)
    database.insert(503, joueur=2, datetime=NOW)
    database.insert(504, joueur=3, datetime=NOW)
    for _ in range(2):
        database.execute("INSERT INTO prev_lol VALUES ('joueur', 'EUW', 'EUW1_1', 40, 60, 'BLUE', TRUE)")
    result = database.query(champion=' aHRI ', mode='RANKED', observation_parties=count)
    assert result['match_id'].tolist() == [f'EUW1_{i}' for i in range(1, count + 1)]
    assert result.iloc[0].name == 500


@pytest.mark.parametrize('duration,hours', [('24h', 24), ('48h', 48), ('72h', 72), ('96h', 96), ('Semaine', 168), ('Mois', 720)])
def test_duration_boundaries_and_future_exclusion(database, duration, hours):
    start = NOW - timedelta(hours=hours)
    database.insert(1, datetime=start)
    database.insert(2, datetime=start - timedelta(seconds=1))
    database.insert(3, datetime=NOW)
    database.insert(4, datetime=NOW + timedelta(seconds=1))
    assert database.query(observation=duration)['match_id'].tolist() == ['EUW1_3', 'EUW1_1']


def test_today_uses_paris_midnight_and_default_is_24h(database):
    database.insert(1, datetime=datetime(2026, 10, 10, 22, tzinfo=timezone.utc))
    database.insert(2, datetime=datetime(2026, 10, 10, 21, 59, tzinfo=timezone.utc))
    assert database.query(observation='today')['match_id'].tolist() == ['EUW1_1']
    assert len(database.query()) == 2


@pytest.mark.parametrize('champion,typed', [('Kaisa', "Kai'Sa"), ('DrMundo', ' Dr. Mundo '), ('MissFortune', 'miss fortune')])
def test_champion_names_ignore_case_spaces_and_punctuation(database, champion, typed):
    database.insert(1, champion=champion)
    assert len(database.query(champion=typed, observation_parties=10)) == 1
    assert database.query(champion="Ahri' OR 1=1 --", observation_parties=10).empty


def test_fewer_matches_and_no_mode_filter(database):
    database.insert(1)
    database.insert(2, mode='ARAM')
    assert len(database.query(observation_parties=10)) == 2
    assert database.query(champion='Lux', observation_parties=10).empty


@pytest.mark.parametrize('now,start', [
    ('2026-03-29T12:00:00+00:00', '2026-03-28T23:00:00+00:00'),
    ('2026-10-25T12:00:00+00:00', '2026-10-24T22:00:00+00:00'),
])
def test_today_and_rolling_duration_at_dst_changes(now, start):
    now = datetime.fromisoformat(now)
    _, params, _ = recap_query('x', 'EUW', observation='today', now=now)
    assert params['date_start'] == datetime.fromisoformat(start)
    _, params, _ = recap_query('x', 'EUW', observation='24h', now=now)
    assert params['date_end'] - params['date_start'] == timedelta(hours=24)


@pytest.fixture
def module(monkeypatch, database):
    monkeypatch.setitem(sys.modules, 'fonctions.gestion_bdd', types.SimpleNamespace(
        lire_bdd_perso=database.read, get_tag=Mock(return_value='EUW'),
        get_data_bdd=Mock(return_value=types.SimpleNamespace(fetchall=lambda: [(30, 40, 50)]))))
    monkeypatch.setitem(sys.modules, 'fonctions.autocomplete', types.SimpleNamespace(autocomplete_riotid=AsyncMock()))
    monkeypatch.setitem(sys.modules, 'fonctions.match.riot_api', types.SimpleNamespace(get_version=AsyncMock()))
    monkeypatch.setitem(sys.modules, 'fonctions.match.timeline', types.SimpleNamespace(fix_temps=lambda value: value))
    monkeypatch.setitem(sys.modules, 'utils.emoji', types.SimpleNamespace(
        emote_champ_discord={'Ahri': '<:Ahri:123456789012345678>', 'Kaisa': '<:Kaisa:123456789012345679>'},
        emote_rank_discord={'GOLD': '<:gold:123456789012345680>'}))
    spec = importlib.util.spec_from_file_location('recap_under_test', Path(__file__).resolve().parents[1] / 'cogs/lol_recap.py')
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def invoke(module, **kwargs):
    cog = object.__new__(module.LoLRecap)
    cog.bot = types.SimpleNamespace(add_component_callback=Mock())
    ctx = types.SimpleNamespace(defer=AsyncMock(), send=AsyncMock(), author=types.SimpleNamespace(id=123))
    asyncio.run(module.LoLRecap.my_recap.callback(cog, ctx, 'joueur', **kwargs))
    return ctx


@pytest.mark.parametrize('options,message', [
    ({'observation': '24h', 'observation_parties': 10}, 'pas les deux'),
    ({'observation_parties': 0}, '10 et 100'),
    ({'observation': 'invalid'}, 'inconnue'),
    ({'champion': '  '}, 'nom de champion'),
])
def test_invalid_options_before_database(module, monkeypatch, options, message):
    read = Mock(side_effect=AssertionError('Database must not be read'))
    monkeypatch.setattr(module, 'lire_bdd_perso', read)
    ctx = invoke(module, **options)
    assert message in ctx.send.call_args.args[0]
    module.get_tag.assert_not_called()
    read.assert_not_called()


@pytest.mark.parametrize('count', [1, 10, 20, 30, 40, 100])
def test_command_statistics_selection_pagination_and_discord_limits(module, database, monkeypatch, count):
    for i in range(1, count + 1):
        database.insert(i)
    database.insert(501, champion='Kaisa', kills=1000)
    paginators = []
    factory = module.Paginator.create_from_embeds
    def create(*args):
        paginator = factory(*args, timeout=0)
        paginators.append(paginator)
        return paginator
    monkeypatch.setattr(module.Paginator, 'create_from_embeds', create)
    main_thread = threading.get_ident()
    def read(*args, **kwargs):
        assert threading.get_ident() != main_thread
        return database.read(*args, **kwargs)
    monkeypatch.setattr(module, 'lire_bdd_perso', read)
    requested = max(10, count)
    ctx = invoke(module, champion='Ahri', observation_parties=requested)
    ctx.defer.assert_awaited_once()
    if paginators:
        embeds = paginators[0].pages
    else:
        embeds = [ctx.send.call_args.kwargs['embeds']]
    assert f'{count} parties disponibles sur {requested}' in embeds[0].description
    assert 'Ahri' in embeds[0].title and f'{requested} dernières parties' in embeds[0].title
    fields = [field for embed in embeds for field in embed.fields]
    assert f'**{count * 5}**' in next(field.value for field in fields if field.name == 'KDA')
    history = ''.join(field.value for field in fields if field.name.startswith('Historique'))
    assert history.count('leagueofgraphs.com') == count
    assert 'P : ' not in history  # Aucune prédiction disponible : pas de pourcentage NaN/None.
    for embed in embeds:
        assert len(embed.title) <= 256
        assert len(embed.fields) <= 25
        assert all(len(field.value) <= 1024 for field in embed.fields)
        assert len(embed) <= 6000


def test_empty_message_describes_selected_filters(module):
    ctx = invoke(module, champion='Ahri', observation_parties=20, mode='RANKED')
    assert '20 dernières parties · Champion : Ahri · RANKED' in ctx.send.call_args.args[0]
    assert '24h' not in ctx.send.call_args.args[0]


def test_champion_autocomplete_and_slash_registration(module):
    ctx = types.SimpleNamespace(input_text=" kai's ", send=AsyncMock())
    asyncio.run(module.LoLRecap.autocomplete_recap_champion(None, ctx))
    assert ctx.send.call_args.kwargs['choices'] == [{'name': 'Kaisa', 'value': 'Kaisa'}]
    options = {str(option.name): option for option in module.LoLRecap.my_recap.options}
    assert options['champion'].autocomplete
    assert [choice.value for choice in options['observation_parties'].choices] == list(GAME_COUNTS)
    assert len(module.LoLRecap.my_recap.to_dict()['description']) <= 100


def test_many_champions_and_long_history_fit_discord(module):
    champions = ' | '.join(f'<:Champion{i}:123456789012345678> : **1** (20 LP)' for i in range(100))
    line = '[11/10 12:00](https://www.leagueofgraphs.com/fr/match/euw/123456789012#participant10) ' + 'x' * 200 + '\n'
    fields = [('Champions', champions), ('Historique (100 parties)', line * 100)]
    pages = module.recap_pages('Recap', 0, '100 parties', fields)
    assert ''.join(field.value for page in pages for field in page.fields if field.name == 'Champions') == champions
    assert ''.join(field.value for page in pages for field in page.fields if field.name.startswith('Historique')) == line * 100
    for page in pages:
        assert len(page) <= 6000
        assert len(page.fields) <= 25
        assert all(len(field.value) <= 1024 for field in page.fields)
        page.to_dict()
