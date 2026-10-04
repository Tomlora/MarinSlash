"""Calcul, sauvegarde et pagination de la proximité, sans API Riot/Discord."""
import asyncio
import copy
import json
import sys
import types
from unittest.mock import AsyncMock

import pandas as pd
import pytest

from test_match_records_ui import DETAILS, VIEWS

PROX = sys.modules['fonctions.match.jungle_proximity']


def proximity_fixture():
    roles = ['TOP', 'JUNGLE', 'MIDDLE', 'BOTTOM', 'UTILITY']
    players = [{'participantId': i, 'teamId': 100 if i <= 5 else 200,
                'puuid': f'p{i}', 'riotIdGameName': f'Player{i}', 'championName': 'Ahri',
                'teamPosition': roles[(i - 1) % 5]} for i in range(1, 11)]
    frames = []
    for minute in (1, 2, 3, 13, 14):
        samples = {str(i): {'position': {'x': 5000, 'y': 5000},
                           'championStats': {'health': 500}} for i in range(1, 11)}
        # Own jungler exactly on radius for two samples, outside for one.
        samples['2']['position']['x'] = 7001 if minute == 13 else 7000
        samples['7']['position']['x'] = 10000
        frames.append({'timestamp': minute * 60_000, 'participantFrames': samples})
    return {'info': {'mapId': 11, 'participants': players[::-1]}}, {'info': {'frames': frames}}


def player(data, pid=1):
    return next(p for p in data['players'] if p['id'] == pid)


def test_radius_time_boundaries_gaps_teams_and_exact_counts():
    detail, timeline = proximity_fixture()
    before = copy.deepcopy((detail, timeline))
    data = PROX.build_snapshot(detail, timeline, 'p8')
    assert data['tracked_team'] == 200 and data['samples'] == 3
    assert len(data['players']) == 8
    assert player(data)['own'] == {'jungler': 2, 'near': 2, 'valid': 3, 'percent': 66.7}
    assert player(data)['opponent']['percent'] == 0
    assert player(data, 6)['own']['percent'] == 0
    assert player(data, 6)['opponent']['percent'] == 66.7
    assert json.loads(json.dumps(data, allow_nan=False)) == data
    assert (detail, timeline) == before
    timeline['info']['frames'].append(copy.deepcopy(timeline['info']['frames'][1]))
    assert PROX.build_snapshot(detail, timeline, 'p8') == data


@pytest.mark.parametrize('change', ['dead', 'unknown_health', 'nan_health', 'base_blue', 'base_red',
                                   'missing', 'origin', 'nan_position', 'invalid_position'])
@pytest.mark.parametrize('pid', ['1', '2'])
def test_unusable_laner_or_jungler_is_excluded_from_denominator(change, pid):
    detail, timeline = proximity_fixture()
    for frame in timeline['info']['frames']:
        sample = frame['participantFrames'][pid]
        if change == 'dead':
            sample['championStats']['health'] = 0
        elif change == 'unknown_health':
            sample.pop('championStats')
        elif change == 'nan_health':
            sample['championStats']['health'] = float('nan')
        elif change == 'missing':
            frame['participantFrames'].pop(pid)
        else:
            xy = {'base_blue': (500, 500), 'base_red': (14500, 14500), 'origin': (0, 0),
                  'nan_position': (float('nan'), 5000), 'invalid_position': (-1, 5000)}[change]
            sample['position'] = dict(zip(('x', 'y'), xy))
    data = PROX.build_snapshot(detail, timeline, 'p1')
    assert player(data)['own']['percent'] is None
    assert player(data)['own']['valid'] == 0
    if pid == '2':
        assert player(data)['opponent']['percent'] == 0


def test_missing_samples_do_not_count_as_far_and_short_match_has_no_fake_zero():
    detail, timeline = proximity_fixture()
    timeline['info']['frames'][2]['participantFrames'].pop('2')
    assert player(PROX.build_snapshot(detail, timeline, 'p1'))['own']['percent'] == 50
    timeline['info']['frames'] = timeline['info']['frames'][:1]
    data = PROX.build_snapshot(detail, timeline, 'p1')
    assert data['samples'] == 0 and player(data)['own']['percent'] is None


def test_role_fallback_ambiguous_junglers_and_unsupported_maps():
    detail, timeline = proximity_fixture()
    players = detail['info']['participants']
    for p in players:
        if p['participantId'] == 2:
            p['teamPosition'] = ''
            p['summoner1Id'] = 11
    data = PROX.build_snapshot(detail, timeline, 'p1')
    assert player(data)['own']['jungler'] == 2 and len(data['players']) == 8
    next(p for p in players if p['participantId'] == 3)['summoner2Id'] = 11
    assert player(PROX.build_snapshot(detail, timeline, 'p1'))['own']['jungler'] is None
    detail['info']['mapId'] = 12
    assert PROX.build_snapshot(detail, timeline, 'p1') is None
    detail['info']['mapId'] = 11
    players.pop()
    assert PROX.build_snapshot(detail, timeline, 'p1') is None


def test_dataframe_and_list_timeline_and_native_team_from_puuid():
    detail, timeline = proximity_fixture()
    # Identity must not be inferred from index, even in an unusual fixture.
    for p in detail['info']['participants']:
        p['teamId'] = 300 - p['teamId']
    match = types.SimpleNamespace(match_detail=pd.DataFrame(detail),
                                  data_timeline=timeline['info']['frames'], puuid='p1')
    data = PROX.snapshot_for_match(match)
    assert data['tracked_team'] == 200 and player(data)['own']['jungler'] == 2


def test_real_embeds_red_allies_first_old_recaps_and_no_ganks():
    from test_match_records_interactions import VIEWS as real
    data = PROX.build_snapshot(*proximity_fixture(), 'p8')
    match = {'match_id': 'EUW1_123', 'mode': 'RANKED', 'id_participant': 0, 'jungle_proximity': data}
    pages = real.build_gank_pages(match, {}, [], False)
    assert len(pages) == 3
    assert pages[1].title.endswith('Alliés') and pages[2].title.endswith('Adversaires')
    assert 'Player6' in pages[1].fields[0].name and 'Player1' in pages[2].fields[0].name
    assert len(pages[1].fields) == len(pages[2].fields) == 4
    assert all(len(p) < 6000 and all(len(f.value) <= 1024 for f in p.fields) for p in pages)
    assert '0 %' in pages[1].fields[0].value and '66.7 %' in pages[1].fields[0].value
    assert 'pas un temps exact' in pages[1].description
    match.pop('jungle_proximity')
    assert 'non enregistrée' in real.build_gank_pages(match, {}, [], False)[1].fields[0].value
    assert len(real.build_gank_pages({**match, 'mode': 'ARAM'}, {}, [], False)) == 1


def test_snapshot_survives_resave_with_map_and_profiles(monkeypatch):
    from test_player_profiles import filled_match
    match = filled_match()
    match.match_detail.loc['mapId', 'info'] = 11
    match.data_timeline = proximity_fixture()[1]
    queries = []
    monkeypatch.setattr(DETAILS, 'requete_perso_bdd', lambda sql, params=None: queries.append((sql, params)))
    for _ in range(2):
        assert DETAILS.save_recap_details(match)
        data = json.loads(queries[-1][1]['data'])
        assert data['jungle_proximity'] == PROX.snapshot_for_match(match)
        assert data['map'] and len(data['players']['players']) == 10
        assert data['jungle_proximity']['tracked_team'] == 200


def test_private_gank_callback_acknowledges_and_navigates_proximity(monkeypatch):
    from test_match_records_interactions import VIEWS as real, VIEW_COG as module
    data = PROX.build_snapshot(*proximity_fixture(), 'p8')
    match = {'match_id': 'EUW1_123', 'mode': 'RANKED', 'jungle_proximity': data}
    calls = []
    async def defer(**kwargs):
        calls.append(kwargs)
    def load(*args):
        assert calls
        return match, {}, [], False
    monkeypatch.setattr(module, 'load_ganks', load)
    cog = object.__new__(module.LolMatchViews)
    ctx = types.SimpleNamespace(custom_id='lolview_open_ganks_EUW1_123_5', defer=defer,
                                send=AsyncMock(), edit_origin=AsyncMock())
    asyncio.run(module.LolMatchViews.on_open.callback(cog, ctx))
    assert calls[0] == {'ephemeral': True}
    response = ctx.send.call_args.kwargs
    for label in ('Alliés', 'Adversaires'):
        controls = response['components'][0].to_dict()['components']
        assert len({b['custom_id'] for b in controls}) == 3
        ctx.custom_id = controls[1]['custom_id']
        asyncio.run(module.LolMatchViews.on_page.callback(cog, ctx))
        response = ctx.edit_origin.call_args.kwargs
        assert response['embeds'].title.endswith(label)
    assert calls[-1] == {'edit_origin': True}
