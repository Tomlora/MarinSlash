"""Régressions hors ligne : vraies bibliothèques, API/BDD simulées."""
import asyncio
import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import numpy as np
import pandas as pd
import pytest
import scipy.stats

ROOT = Path(__file__).resolve().parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def modules(monkeypatch):
    # Aucun import de MatchLol (qui charge les modèles et la BDD au démarrage).
    fonctions = types.ModuleType('fonctions')
    fonctions.__path__ = [str(ROOT / 'fonctions')]
    utils = types.ModuleType('utils')
    utils.__path__ = [str(ROOT / 'utils')]
    match = types.ModuleType('fonctions.match')
    match.get_version = AsyncMock(return_value={})
    match.get_champ_list = AsyncMock(return_value={'data': {'X': {'key': '1', 'id': 'Annie'}}})
    db = types.ModuleType('fonctions.gestion_bdd')
    for name in ('sauvegarde_bdd', 'get_data_bdd', 'lire_bdd_perso'):
        setattr(db, name, Mock())
    params = types.ModuleType('utils.params')
    params.api_key_lol, params.my_region, params.region = 'unused', 'euw1', 'europe'
    emoji = types.ModuleType('utils.emoji')
    emoji.emote_champ_discord = {}
    for module in (fonctions, utils, match, db, params, emoji):
        monkeypatch.setitem(sys.modules, module.__name__, module)
    api = load_module('fonctions.api_calls', ROOT / 'fonctions/api_calls.py')
    monkeypatch.setitem(sys.modules, 'fonctions.api_calls', api)
    fonctions.api_calls = api
    cog = load_module('prediction_tests', ROOT / 'cogs/predict.py')
    return cog, api


@pytest.mark.parametrize('values', [[0] * 5, [0.5] * 5, [1234] * 5])
def test_constant_features_are_finite(modules, values):
    result = asyncio.run(modules[0].add_stats(values))
    assert len(result) == 11
    assert result[:5] == values
    assert result[7:] == [0, 0, 0, 0]
    assert np.isfinite(result).all()


def test_variable_features_keep_training_order(modules):
    values = [0, 1, 3, 7, 12]
    expected = values + [np.mean(values), np.median(values),
                         scipy.stats.kurtosis(values, bias=False),
                         scipy.stats.skew(values, bias=False), np.std(values), np.var(values)]
    assert asyncio.run(modules[0].add_stats(values)) == expected


@pytest.mark.parametrize('values', [[], [1] * 4, [float('nan')] * 5, [float('inf')] * 5])
def test_invalid_features_rejected(modules, values):
    with pytest.raises(ValueError):
        asyncio.run(modules[0].add_stats(values))


def lobby():
    return {'gameType': 'normal_aram', 'participants': [
        {'championId': 1, 'team': 'BLUE' if i < 5 else 'RED',
         'summonerName': f'Player {i}#EUW', 'currentRole': None}
        for i in range(10)
    ]}


def test_predict_resets_mastery_level_and_keeps_44_features(modules, monkeypatch):
    cog, api = modules
    api.get_winrates = AsyncMock(return_value=None)
    api.get_masteries = AsyncMock(side_effect=[
        [{'championId': '1', 'mastery': 100, 'level': 7}], *([[]] * 9)
    ])
    model = Mock()
    model.predict.return_value = np.array([1])
    model.predict_proba.return_value = np.array([[0.2, 0.8]])
    monkeypatch.setattr(cog.joblib, 'load', Mock(return_value=model))
    prediction, proba, recap, data = asyncio.run(cog.predict_match('live', lobby(), {'1': 'Annie'}, object()))
    assert len(data) == 44 and np.isfinite(data).all()
    assert 'Player 0#EUW**  : WR **0%** | Pts : **100** | Lvl : **7**' in recap['blueside']
    assert 'Player 1#EUW**  : WR **0%** | Pts : **0** | Lvl : **0**' in recap['blueside']
    assert cog.joblib.load.call_args.args[0].is_absolute()
    model.predict.assert_called_once_with([data])


def test_non_5v5_rejected_before_api_calls(modules):
    cog, api = modules
    api.get_winrates = AsyncMock()
    game = lobby()
    game['participants'].pop()
    with pytest.raises(ValueError, match='5 contre 5'):
        asyncio.run(cog.predict_match('live', game, {}, object()))
    api.get_winrates.assert_not_awaited()


@pytest.mark.parametrize('player,expected', [('player0#euw', True), ('PLAYER 5#EUW', False)])
def test_manual_and_auto_identify_player_and_team(modules, player, expected):
    cog, api = modules
    api.get_live_match = AsyncMock(return_value=lobby())
    cog.predict_match = AsyncMock(return_value=(np.array([1]), np.array([[.2, .8]]), {}, [0] * 44))
    manual, _ = asyncio.run(cog.get_current_match_prediction(None, player, 'live', object()))
    auto, _, _ = asyncio.run(cog.get_current_match_prediction_auto(player, 'live', object()))
    assert manual['victory_predicted'] is expected
    assert auto['victory_predicted'] is expected
    assert manual['role'] == 'aram'


def test_absent_game_skips_data_dragon(modules):
    cog, api = modules
    api.get_live_match = AsyncMock(return_value='Aucun')
    assert asyncio.run(cog.get_current_match_prediction_auto('a#b', 'live', object())) == ('Aucun',) * 3
    cog.get_version.assert_not_awaited()


def test_absent_player_has_explicit_error(modules):
    cog, api = modules
    api.get_live_match = AsyncMock(return_value=lobby())
    with pytest.raises(ValueError, match='absent'):
        asyncio.run(cog.get_current_match_prediction_auto('missing#EUW', 'live', object()))


class FakeSession:
    def __init__(self, **kwargs):
        self.closed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        self.closed = True


def test_mastery_scraping_failure_uses_open_caller_session(modules, monkeypatch):
    _, api = modules
    session = FakeSession()
    response = FakeSession()
    response.raise_for_status = Mock()
    response.text = AsyncMock(return_value='broken HTML')
    session.get = Mock(return_value=response)
    monkeypatch.setattr(api.pd, 'read_html', Mock(side_effect=ValueError('no table')))

    async def account(received, *args):
        assert received is session and not received.closed
        return {'puuid': 'id'}

    api.get_summoner_by_riot_id = AsyncMock(side_effect=account)
    api.get_champion_masteries = AsyncMock(return_value=[{'championId': 1, 'championPoints': 50, 'championLevel': 2}])
    assert asyncio.run(api.get_masteries('Player Name#EUW', {'1': 'Annie'}, session)) == [
        {'championId': 1, 'mastery': 50, 'level': 2}
    ]
    assert not session.closed


@pytest.mark.parametrize('response', ['', {'errors': [{}]}, {'data': None}, {'data': {}}])
def test_api_errors_are_not_reported_as_no_game(modules, response):
    api = modules[1]
    api.getLiveGame = AsyncMock(return_value=response)
    with pytest.raises(ValueError):
        asyncio.run(api.get_live_match('a#EUW', object()))


def test_no_live_game(modules):
    api = modules[1]
    api.getLiveGame = AsyncMock(return_value={'data': {'getLiveGame': None}})
    assert asyncio.run(api.get_live_match('a#EUW', object())) == 'Aucun'


def test_batch_uses_account_pairs_and_continues_after_error(modules, monkeypatch):
    cog, _ = modules
    cog.get_data_bdd.return_value.fetchall.return_value = [('same', 'NEW'), ('other', 'TAG'), ('last', 'EUW')]
    cog.lire_bdd_perso.return_value = pd.DataFrame(
        [{'riot_id': 'same', 'riot_tag': 'TAG'}, {'riot_id': 'someone', 'riot_tag': 'NEW'}]
    ).T
    session = FakeSession()
    monkeypatch.setattr(cog.aiohttp, 'ClientSession', Mock(return_value=session))
    instance = types.SimpleNamespace(predict_probability_auto=AsyncMock(side_effect=[RuntimeError('offline'), None, None]))
    asyncio.run(cog.predict.update_predict.callback(instance))
    assert [call.args[1:] for call in instance.predict_probability_auto.await_args_list] == [
        ('same', 'NEW'), ('other', 'TAG'), ('last', 'EUW')]
    assert session.closed


def test_direct_no_game_closes_session(modules, monkeypatch):
    cog, _ = modules
    session = FakeSession()
    monkeypatch.setattr(cog.aiohttp, 'ClientSession', Mock(return_value=session))
    cog.get_current_match_prediction = AsyncMock(return_value=('Aucun', 'Aucun'))
    ctx = types.SimpleNamespace(defer=AsyncMock(), send=AsyncMock())
    asyncio.run(cog.predict.predict_probability_direct.callback(None, ctx, 'name', 'EUW'))
    assert session.closed
    ctx.send.assert_awaited_once_with('Pas de game en cours')


def test_missing_saved_prediction_is_not_generic_error(modules):
    cog, _ = modules
    cog.lire_bdd_perso.return_value = pd.DataFrame()
    ctx = types.SimpleNamespace(defer=AsyncMock(), send=AsyncMock())
    asyncio.run(cog.predict.predict_probability.callback(None, ctx, "O'Name", 'euw', 'EUW1_1'))
    assert 'Aucune prédiction' in ctx.send.call_args.args[0]
    assert cog.lire_bdd_perso.call_args.kwargs['params']['riot_id'] == "o'name"
    assert "o'name" not in cog.lire_bdd_perso.call_args.args[0]

