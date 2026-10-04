"""Profils complets du lobby, acquisition existante et pagination sans réseau."""
import ast
import asyncio
import importlib.util
import json
import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('fonctions.match.player_profiles', ROOT / 'fonctions/match/player_profiles.py')
PROFILES = importlib.util.module_from_spec(spec)
spec.loader.exec_module(PROFILES)


def profile_match():
    from test_match_records_ui import sample_details_match
    match = sample_details_match()
    roles = ['TOP', 'JUNGLE', 'MIDDLE', 'BOTTOM', 'UTILITY']
    for i, player in enumerate(match.match_detail['info']['participants']):
        player.update(riotIdGameName='Même nom' if i in (0, 5) else f'Joueur {i}',
                      riotIdTagline=f'T{i}', championName='Ahri', teamPosition=roles[i % 5])
    match.match_detail = pd.DataFrame(match.match_detail)
    return match


def filled_match():
    match = profile_match()
    for index in range(10):
        PROFILES.capture_global(match, index, {'wins': 30, 'losses': 30}, 'Mobalytics')
        PROFILES.capture_champions(match, index, pd.DataFrame([
            {'championId': 'Ahri', 'wins': 30, 'looses': 70, 'totalMatches': 100},
            {'championId': 'Viktor', 'wins': 5, 'looses': 5, 'totalMatches': 10},
        ]), 'Mobalytics')
        PROFILES.capture_roles(match, index, pd.DataFrame([
            {'role': 'adc', 'nbgames': 90}, {'role': 'mid', 'nbgames': 10},
        ]), 'Mobalytics')
    return match


def test_exact_counts_low_samples_and_champion_roles_are_aggregated():
    match = profile_match()
    PROFILES.capture_global(match, 0, {'wins': 1, 'losses': 2, 'winrate': 33}, 'U.GG')
    PROFILES.capture_champions(match, 0, pd.DataFrame([
        {'championId': 'Ahri', 'wins': 1, 'totalMatches': 2},
        {'championId': 'Ahri', 'wins': 0, 'totalMatches': 1},
        {'championId': 'Viktor', 'wins': 1, 'totalMatches': 1},
    ]), 'U.GG')
    raw = match.player_profiles_raw['p5']
    assert raw['global']['wins'] == 1 and raw['global']['losses'] == 2
    assert raw['champion'] == {'wins': 1, 'losses': 2, 'games': 3, 'winrate': 33.3}
    assert raw['champion_share'] == 75
    assert PROFILES.results({'winrate': 50, 'nbgames': 60}) is None
    assert PROFILES.results({'wins': 3, 'totalMatches': 2}) is None
    assert PROFILES.results({'wins': float('nan'), 'losses': 2}) is None


def test_champion_absent_from_known_history_differs_from_unavailable_history():
    match = profile_match()
    PROFILES.capture_champions(match, 0, pd.DataFrame([{'championId': 'Viktor', 'wins': 1, 'totalMatches': 1}]), 'U.GG')
    assert match.player_profiles_raw['p5']['champion']['games'] == 0
    PROFILES.capture_champions(match, 1, pd.DataFrame(), 'Mobalytics')
    assert match.player_profiles_raw['p6']['champion'] is None


def test_snapshots_keep_ten_players_puuid_identity_red_allies_and_missing_data():
    match = filled_match()
    match.player_profiles_raw['p0']['global'] = None
    match.player_profiles_raw['p5']['global'] = PROFILES.results({'wins': 0, 'losses': 10})
    data = PROFILES.snapshot_players(match)
    assert data['allied_team'] == 200
    assert len(data['players']) == 10
    assert data['players'][0]['name'] == data['players'][5]['name']
    assert data['players'][0]['global'] is None
    assert data['players'][5]['global']['winrate'] == 0
    assert json.loads(json.dumps(data, allow_nan=False)) == data
    # Le compte du récap lui-même n'est pas exclu comme dans les insights.
    assert next(p for p in data['players'] if p['id'] == 8)['global']['games'] == 60


def test_roles_and_otp_autofill_boundaries_are_explained():
    player = PROFILES.snapshot_players(filled_match())['players'][7]  # MID, main ADC
    text = PROFILES.profile_text(player)
    assert 'ADC (90 %)' in text and '30 V / 70 D' in text
    assert '**OTP :** Détecté' in text and '**Autofill :** Probable' in text
    player['champion_share'] = 70
    player['roles']['games'] = 30
    text = PROFILES.profile_text(player)
    assert '**OTP :** Non détecté' in text and 'Historique insuffisant' in text
    data = PROFILES.snapshot_players(profile_match())
    assert len(data['players']) == 10 and 'Données indisponibles' in PROFILES.profile_text(data['players'][0])


@pytest.fixture
def render_modules(monkeypatch):
    from test_match_records_interactions import VIEWS, VIEW_COG, DETAILS
    monkeypatch.setitem(sys.modules, 'fonctions.match.match_views', VIEWS)
    monkeypatch.setitem(sys.modules, 'fonctions.match.recap_details', DETAILS)
    monkeypatch.setattr(VIEW_COG, 'build_player_pages', PROFILES.build_player_pages)
    monkeypatch.setattr(VIEW_COG, 'load_players', PROFILES.load_players)
    return VIEWS, VIEW_COG, DETAILS


def test_two_real_embeds_allies_first_and_five_fields_each(render_modules, monkeypatch):
    views, _, _ = render_modules
    monkeypatch.setattr(views, '_champion_icon', lambda champ: '<:Ahri:234567890123456789>')
    match = {'match_id': 'EUW1_123', 'player_name': 'Joueur 7#T7', 'mode': 'RANKED'}
    pages = PROFILES.build_player_pages(match, PROFILES.snapshot_players(filled_match()))
    assert len(pages) == 2
    assert pages[0].title.endswith('Alliés') and pages[1].title.endswith('Adversaires')
    assert all(len(page.fields) == 5 and len(page) < 6000 for page in pages)
    assert '#T5' in pages[0].fields[0].name and '#T0' in pages[1].fields[0].name
    assert all('<:Ahri:' in field.name and len(field.value) <= 1024 for page in pages for field in page.fields)
    assert '50 %' in pages[0].fields[0].value
    assert len(PROFILES.build_player_pages(match, None)) == 1


def test_storage_is_persistent_and_loader_handles_legacy(render_modules, monkeypatch):
    _, cog, details = render_modules
    queries = []
    monkeypatch.setattr(details, 'requete_perso_bdd', lambda sql, params=None: queries.append((sql, params)))
    match = filled_match()
    assert details.save_recap_details(match)
    data = json.loads(queries[-1][1]['data'])
    assert len(data['players']['players']) == 10
    monkeypatch.setattr(details, 'load_details', lambda *args: ({'match_id': 'EUW1_123', 'mode': 'RANKED'}, data, {}))
    assert len(cog.load_pages('players', 'EUW1_123', 5)) == 2
    monkeypatch.setattr(details, 'load_details', lambda *args: ({'match_id': 'EUW1_123'}, {}, {}))
    assert 'ancien récap' in cog.load_pages('players', 'EUW1_123', 5)[0].fields[0].value


def test_private_callback_acknowledges_before_load_and_paginates(render_modules, monkeypatch):
    _, module, _ = render_modules
    events = []
    async def defer(**kwargs):
        events.append(('ack', kwargs))
    pages = PROFILES.build_player_pages({'mode': 'RANKED', 'match_id': 'EUW1_123'}, PROFILES.snapshot_players(filled_match()))
    def load(*args):
        assert events and events[-1][0] == 'ack'
        return pages
    monkeypatch.setattr(module, 'load_pages', load)
    cog = object.__new__(module.LolMatchViews)
    ctx = types.SimpleNamespace(custom_id='lolview_open_players_EUW1_123_5', defer=defer, send=AsyncMock(), edit_origin=AsyncMock())
    asyncio.run(module.LolMatchViews.on_open.callback(cog, ctx))
    assert events[0] == ('ack', {'ephemeral': True})
    assert ctx.send.call_args.kwargs['ephemeral'] is True
    assert ctx.send.call_args.kwargs['embeds'].title.endswith('Alliés')
    controls = ctx.send.call_args.kwargs['components'][0].to_dict()['components']
    assert controls[0]['disabled'] and not controls[1]['disabled']
    assert len({c['custom_id'] for c in controls}) == 3
    ctx.custom_id = controls[1]['custom_id']
    asyncio.run(module.LolMatchViews.on_page.callback(cog, ctx))
    assert events[-1] == ('ack', {'edit_origin': True})
    assert ctx.edit_origin.call_args.kwargs['embeds'].title.endswith('Adversaires')


def method(name, dependencies):
    tree = ast.parse((ROOT / 'fonctions/match/external_data.py').read_text(encoding='utf-8'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef))
    func = next(n for n in cls.body if isinstance(n, ast.AsyncFunctionDef) and n.name == name)
    namespace = {'pd': pd, 'np': np, **{n: getattr(PROFILES, n) for n in ('capture_global', 'capture_champions', 'capture_roles')}, **dependencies}
    exec(compile(ast.Module(body=[func], type_ignores=[]), '<real external_data>', 'exec'), namespace)
    return namespace[name]


def test_mobalytics_acquisition_captures_small_sample_before_insight_filter():
    match = profile_match()
    match.activate_mobalytics = 'True'
    match.nb_joueur, match.session, match.riot_id, match.riot_tag = 10, None, 'test', 'TEST'
    match.champ_dict, match.thisQ = {'103': 'Ahri'}, 'RANKED'
    champions = pd.DataFrame([{'championId': 103, 'wins': 1, 'looses': 1, 'totalMatches': 2}])
    rank = AsyncMock(return_value={'data': {'lol': {'player': {'queuesStats': {'items': [
        {'virtualQueue': 'RANKED_SOLO', 'wins': 30, 'losses': 30, 'gamesCount': 60, 'winrate': .5}]}}}}})
    champion_api = AsyncMock(side_effect=lambda *a: champions.copy())
    role_api = AsyncMock(return_value=pd.DataFrame([{'role': 'adc', 'nbgames': 50, 'wins': 25, 'poids_role': 100}]))
    run = method('prepare_data_moba', {
        'update_moba': AsyncMock(), 'get_mobalytics': AsyncMock(return_value=None),
        'pickle': types.SimpleNamespace(load=lambda *a: None), 'open': lambda *a: None,
        'get_wr_ranked': rank, 'get_stat_champion_by_player_mobalytics': champion_api,
        'get_role_stats': role_api, 'get_player_match_history_moba': AsyncMock(side_effect=ValueError),
    })
    asyncio.run(run(match))
    assert rank.await_count == champion_api.await_count == role_api.await_count == 10
    assert len(match.player_profiles_raw) == 10
    assert all(p['champion']['games'] == 2 and p['global']['wins'] == 30 for p in match.player_profiles_raw.values())
    assert all(value == '' for value in match.winrate_champ_joueur.values())


def test_ugg_acquisition_does_not_reuse_previous_players_rank():
    match = profile_match()
    match.nb_joueur, match.session, match.ugg = 10, None, 'False'
    match.season_ugg, match.list_season_ugg, match.champ_dict = 26, [26], {}
    rank_api = AsyncMock(side_effect=[{'data': {'fetchProfileRanks': {'rankScores': [
        {'queueType': 'ranked_solo_5x5', 'wins': 10, 'losses': 20}]}}}] + [''] * 9)
    champ_api = AsyncMock(side_effect=lambda *a, **kw: pd.DataFrame([
        {'championId': 'Ahri', 'wins': 1, 'totalMatches': 2, 'kills': 2, 'deaths': 1, 'assists': 1}]))
    roles_api = AsyncMock(return_value={'adc': {'gameCount': 45, 'winCount': 25}, 'supp': {'gameCount': 5, 'winCount': 1}})
    run = method('prepare_data_ugg', {'getRanks': rank_api, 'get_stat_champion_by_player': champ_api,
                                    'get_role': roles_api, 'get_player_match_history': AsyncMock(return_value={})})
    asyncio.run(run(match))
    assert rank_api.await_count == champ_api.await_count == roles_api.await_count == 10
    assert match.player_profiles_raw['p5']['global']['losses'] == 20
    assert all(p.get('global') is None for puuid, p in match.player_profiles_raw.items() if puuid != 'p5')
    assert match.player_profiles_raw['p9']['roles']['main'] == 'ADC'
