"""Pagination or : mesures individuelles, graphes lisibles, pièces jointes remplacées."""
import asyncio
import copy
import inspect
import json
import math
import sys
import types
from io import BytesIO
from unittest.mock import AsyncMock

import interactions
import pandas as pd
import pytest
from PIL import Image

from test_match_records_ui import DETAILS

GOLD = sys.modules['fonctions.match.gold_player_views']


def fixture(minutes=46):
    roles = ['TOP', 'JUNGLE', 'MIDDLE', 'BOTTOM', 'UTILITY']
    champs = ['Ornn', 'Viego', 'Ahri', 'Jinx', 'Leona', 'Garen', 'LeeSin', 'Syndra', 'Ezreal', 'Nautilus']
    players = [{'participantId': i, 'teamId': 100 if i <= 5 else 200, 'puuid': f'p{i}',
                'teamPosition': roles[(i - 1) % 5], 'championName': champs[i - 1],
                'riotIdGameName': f'Joueur {i} au nom très long pour vérifier la lisibilité'} for i in range(1, 11)]
    frames = []
    for m in range(minutes):
        samples = {}
        for i in range(1, 11):
            rate = [390, 340, 420, 440, 270][(i - 1) % 5]
            difference = (m * 25 - 400) * (1 if i % 2 else -1) if i > 5 else 0
            samples[str(i)] = {'totalGold': max(0, 500 + m * rate + difference)}
        frames.append({'timestamp': m * 60_000, 'participantFrames': samples})
    return {'info': {'mapId': 11, 'participants': players[::-1]}}, {'info': {'frames': frames}}


def data(minutes=46):
    return GOLD.build_snapshot(*fixture(minutes), 'p8')


def test_snapshot_keeps_native_identity_dataframe_and_per_player_gaps():
    detail, timeline = fixture(5)
    timeline['info']['frames'][2]['participantFrames']['1']['totalGold'] = float('nan')
    timeline['info']['frames'][3]['participantFrames'].pop('2')
    timeline['info']['frames'][4]['participantFrames']['3']['totalGold'] = -1
    original = copy.deepcopy(detail)
    snapshot = GOLD.build_snapshot(pd.DataFrame(detail), timeline, 'p8')
    assert snapshot['tracked_team'] == 200
    assert snapshot['tracked_player'] == 8
    assert [p['id'] for p in snapshot['players']] == list(range(1, 11))
    assert [m for m, _ in snapshot['players'][0]['points']] == [0, 1, 3, 4]
    assert [m for m, _ in snapshot['players'][1]['points']] == [0, 1, 2, 4]
    assert [m for m, _ in snapshot['players'][2]['points']] == [0, 1, 2, 3]
    assert len(snapshot['players'][9]['points']) == 5
    assert json.loads(json.dumps(snapshot, allow_nan=False)) == snapshot
    assert detail == original
    match = types.SimpleNamespace(match_detail=pd.DataFrame(detail), data_timeline=timeline, puuid='p8')
    assert GOLD.snapshot_for_match(match) == snapshot


def test_minute_sampling_prefers_closest_frame_ignores_partial_and_keeps_zero():
    detail, timeline = fixture(2)
    drift = copy.deepcopy(timeline['info']['frames'][1])
    drift['timestamp'] = 60700
    drift['participantFrames']['1']['totalGold'] = 99999
    partial = copy.deepcopy(drift)
    partial['timestamp'] = 119000
    timeline['info']['frames'] = [drift, *timeline['info']['frames'], partial]
    timeline['info']['frames'][1]['participantFrames']['1']['totalGold'] = 0
    snapshot = GOLD.build_snapshot(detail, timeline, 'p1')
    assert snapshot['players'][0]['points'] == [[0, 0], [1, 890]]
    assert GOLD.build_snapshot(detail, {}, 'p1') is None
    detail['info']['participants'].pop()
    assert GOLD.build_snapshot(detail, timeline, 'p1') is None


def test_role_diffs_use_same_minute_native_teams_and_reject_ambiguity():
    snapshot = data(4)
    red = GOLD.role_series(snapshot, 200)
    blue = GOLD.role_series(snapshot, 100)
    assert red[0][1]['id'] == 6 and red[0][2]['id'] == 1
    assert all(a == b and v == -w for (a, v), (b, w) in zip(red[0][3], blue[0][3]))
    snapshot['players'][0]['points'].pop(1)
    assert [m for m, _ in GOLD.role_series(snapshot, 200)[0][3]] == [0, 2, 3]
    snapshot['players'][1]['role'] = 'TOP'
    assert GOLD.role_series(snapshot, 200)[0][1:] == (None, None, [])
    assert GOLD.role_series(snapshot, 200)[1][1:] == (None, None, [])
    x, y = GOLD.with_gaps([[0, 500], [2, 900]])
    assert x == [0, 1, 2] and math.isnan(y[1])


@pytest.mark.parametrize('kind,charts', [('roles', 5), ('players', 1)])
def test_real_charts_have_expected_panels_common_scales_labels_and_valid_png(kind, charts, monkeypatch):
    figures = []
    original = GOLD._png
    def capture(fig):
        figures.append(fig)
        return original(fig)
    monkeypatch.setattr(GOLD, '_png', capture)
    snapshot = data(61)
    png = (GOLD.render_roles(snapshot, 200, DETAILS.gold_segments) if kind == 'roles'
           else GOLD.render_players(snapshot, 200))
    fig = figures[0]
    assert len(fig.axes) == charts
    assert len({ax.get_ylim() for ax in fig.axes}) == 1
    assert len({ax.get_xlim() for ax in fig.axes}) == 1
    if kind == 'roles':
        assert all(ax.get_title(loc='left') for ax in fig.axes)
    else:
        assert len(fig.axes[0].lines) == 10
        assert len({line.get_color() for line in fig.axes[0].lines}) == 10
        assert [line.get_linestyle() for line in fig.axes[0].lines] == ['-'] * 5 + ['--'] * 5
        legend = [t.get_text() for t in fig.legends[0].get_texts()]
        assert len(legend) == 10 and 'Garen' in legend[0] and 'Ornn' in legend[5]
        assert all('or (60:00)' in text for text in legend)
    assert len(png) < 8 * 1024 * 1024
    with Image.open(BytesIO(png)) as image:
        assert image.width >= 1600 and image.height >= (1700 if kind == 'roles' else 1200)


@pytest.mark.parametrize('end,step', [(25, 5), (30, 6), (60, 12), (3, 1)])
def test_role_annotations_follow_duration_and_never_fill_gaps(end, step, monkeypatch):
    from matplotlib.text import Annotation
    figures = []
    monkeypatch.setattr(GOLD, '_png', lambda fig: figures.append(fig))
    snapshot = data(end + 1)
    # Remove a scheduled point on one side of TOP: no invented annotation.
    snapshot['players'][0]['points'] = [p for p in snapshot['players'][0]['points'] if p[0] != step]
    GOLD.render_roles(snapshot, 200, DETAILS.gold_segments)
    fig = figures[0]
    fig.canvas.draw()
    for index, ax in enumerate(fig.axes):
        annotations = [t for t in ax.texts if isinstance(t, Annotation)]
        expected = [m for m in range(0, end + 1, step) if index != 0 or m != step]
        assert [a.xy[0] for a in annotations] == expected
        assert all(a.get_text() == f'{a.xy[1]:+,.0f}'.replace(',', ' ') for a in annotations)
        for a in annotations:
            box = a.get_window_extent(fig.canvas.get_renderer())
            assert box.y0 >= ax.bbox.y0 and box.y1 <= ax.bbox.y1


def test_single_player_chart_keeps_missing_gold_explicit_and_gaps(monkeypatch):
    figures = []
    monkeypatch.setattr(GOLD, '_png', lambda fig: figures.append(fig))
    snapshot = data(4)
    snapshot['players'][5]['points'].pop(1)
    snapshot['players'][6]['points'] = []
    GOLD.render_players(snapshot, 200)
    fig = figures[0]
    assert len(fig.axes) == 1 and len(fig.axes[0].lines) == 10
    assert math.isnan(fig.axes[0].lines[0].get_ydata()[1])
    assert len(fig.axes[0].lines[1].get_ydata()) == 0
    assert 'non enregistré' in fig.legends[0].get_texts()[1].get_text()


def test_page_one_reuses_original_graph_unchanged_and_clamps_page(monkeypatch):
    match = {'match_id': 'EUW1_123', 'mode': 'RANKED', 'id_participant': 7}
    points = [{'minute': 0, 'blue': 2500, 'red': 2500}, {'minute': 1, 'blue': 5000, 'red': 4000}]
    expected = DETAILS.render_gold(match, points)
    monkeypatch.setattr(DETAILS, 'load_gold', lambda *args: (match, points))
    embed, png = DETAILS.gold_response('EUW1_123', 5, -1)
    assert png == expected
    assert embed.image.url == 'attachment://gold_diff.png'
    assert 'Page 1/3' in str(embed.footer)


def test_relative_gold_exact_differences_reference_and_missing_minutes():
    snapshot = data(5)
    original = copy.deepcopy(snapshot)
    reference = GOLD.reference_player(snapshot, 200, 0)
    assert reference['id'] == 8  # Saved PUUID wins over any legacy index.
    relative = GOLD.player_series(snapshot, 8)
    base = dict(reference['points'])
    assert all(v == 0 for _, v in relative[8])
    for player in snapshot['players']:
        assert relative[player['id']] == [(m, g - base[m]) for m, g in player['points']]
    assert snapshot == original
    snapshot['players'][7]['points'].pop(2)
    assert all(2 not in dict(points) for points in GOLD.player_series(snapshot, 8).values())
    snapshot.pop('tracked_player')
    assert GOLD.reference_player(snapshot, 200, 7)['id'] == 8
    assert GOLD.reference_player(snapshot, 200, 0) is None
    assert GOLD.reference_player(snapshot, 200, None) is None
    assert GOLD.player_series(snapshot, 99) == {}


def test_relative_graph_shows_ten_curves_one_zero_reference_and_signed_legend(monkeypatch):
    figures = []
    monkeypatch.setattr(GOLD, '_png', lambda fig: figures.append(fig))
    snapshot = data(31)
    GOLD.render_players(snapshot, 200, 8)
    fig = figures[0]
    assert len(fig.axes) == 1 and len(fig.axes[0].lines) == 10
    ax = fig.axes[0]
    assert ax.get_ylim()[0] < 0 < ax.get_ylim()[1]
    assert ax.get_ylabel() == "Écart d'or au joueur suivi"
    assert set(ax.lines[2].get_ydata()) == {0}
    assert ax.lines[2].get_color() == '#111827'
    texts = [t.get_text() for t in fig.legends[0].get_texts()]
    assert 'Référence (0)' in texts[2]
    assert any(' — +' in t for t in texts) and any(' — -' in t for t in texts)
    assert any('Syndra' in t.get_text() and 'Zéro' in t.get_text() for t in fig.texts)


def test_relative_page_can_switch_to_total_without_known_reference(monkeypatch):
    from test_match_records_interactions import DETAILS as real
    snapshot = data(3)
    snapshot['tracked_player'] = None
    match = {'match_id': 'EUW1_123', 'mode': 'RANKED'}
    monkeypatch.setattr(real, 'load_details', lambda *args: (match, {'gold_players': snapshot}, {}))
    embed, png = real.gold_response('EUW1_123', 5, 2)
    assert png is None and embed.fields[0].name == 'Référence inconnue'
    embed, png = real.gold_response('EUW1_123', 5, 2, 'total')
    assert png and embed.title == '💰 Or de chaque joueur'


def test_relative_total_controls_acknowledge_replace_image_and_keep_three_pages(monkeypatch):
    from test_match_records_interactions import VIEW_COG as module
    acknowledgements, loads = [], []
    async def defer(**kwargs):
        acknowledgements.append(kwargs)
    def load(match_id, joueur, page, mode):
        assert acknowledgements[-1] == {'edit_origin': True}
        loads.append((match_id, joueur, page, mode))
        return interactions.Embed(title=mode), b'png'
    monkeypatch.setattr(module, 'gold_response', load)
    cog = object.__new__(module.LolMatchViews)
    ctx = types.SimpleNamespace(custom_id='lolview_page_gold_EUW1_123_5_2_next',
                                defer=defer, send=AsyncMock(), edit=AsyncMock())
    asyncio.run(module.LolMatchViews.on_page.callback(cog, ctx))
    for current, target in [('relative', 'total'), ('total', 'relative')]:
        result = ctx.edit.call_args.kwargs
        assert result['attachments'] == [] and result['file'].file_name == 'gold_players.png'
        rows = [row.to_dict()['components'] for row in result['components']]
        assert len(rows) == 2 and rows[0][1]['disabled']
        ids = [b['custom_id'] for row in rows for b in row]
        assert len(ids) == len(set(ids)) and all(len(i) <= 100 for i in ids)
        buttons = {b['custom_id'].split('_')[1]: b for b in rows[1]}
        assert buttons[current]['disabled'] and not buttons[target]['disabled']
        ctx.custom_id = buttons[target]['custom_id']
        asyncio.run(module.LolMatchViews.on_gold_mode.callback(cog, ctx))
        assert loads[-1] == ('EUW1_123', 5, 2, target)


def test_new_pages_handle_missing_and_ambiguous_roles_and_keep_individual_curves(monkeypatch):
    from test_match_records_interactions import DETAILS as real
    match = {'match_id': 'EUW1_123', 'mode': 'RANKED', 'id_participant': 7}
    stored = {}
    monkeypatch.setattr(real, 'load_details', lambda *args: (match, stored, {}))
    for page in (1, 2):
        embed, png = real.gold_response('EUW1_123', 5, page)
        assert png is None and 'Données indisponibles' in embed.fields[0].name
        assert f'Page {page + 1}/3' in embed.footer.text
    snapshot = data(2)
    for p in snapshot['players']:
        p['role'] = None
    stored['gold_players'] = snapshot
    embed, png = real.gold_response('EUW1_123', 5, 1)
    assert png is None and 'Données insuffisantes' in embed.fields[1].name
    embed, png = real.gold_response('EUW1_123', 5, 999)
    assert png and embed.image.url == 'attachment://gold_players.png'


def test_save_keeps_gold_players_alongside_map_profiles_and_proximity(monkeypatch):
    from test_player_profiles import filled_match
    match = filled_match()
    match.match_detail.loc['mapId', 'info'] = 11
    match.data_timeline = fixture(3)[1]
    queries = []
    monkeypatch.setattr(DETAILS, 'requete_perso_bdd', lambda sql, params=None: queries.append(params))
    assert DETAILS.save_recap_details(match)
    payload = json.loads(queries[-1]['data'])
    assert payload['gold_players'] == GOLD.snapshot_for_match(match)
    assert all(key in payload for key in ('map', 'players', 'jungle_proximity', 'gold', 'scores'))


def test_real_callbacks_page_forward_back_replace_files_and_clear_on_empty_or_error(monkeypatch):
    from test_match_records_interactions import VIEW_COG as module
    calls = []
    async def defer(**kw):
        calls.append(kw)
    def load(match_id, joueur, page, mode="relative"):
        assert calls
        embed = interactions.Embed(title=f'Page {page + 1}')
        return embed, b'png' if page != 2 else None
    monkeypatch.setattr(module, 'gold_response', load)
    cog = object.__new__(module.LolMatchViews)
    ctx = types.SimpleNamespace(custom_id='lolview_open_gold_EUW1_123_5', defer=defer,
                                send=AsyncMock(), edit=AsyncMock(), edit_origin=AsyncMock())
    asyncio.run(module.LolMatchViews.on_open.callback(cog, ctx))
    assert calls[0] == {'ephemeral': True}
    response = ctx.send.call_args.kwargs
    assert response['file'].file_name == 'gold_diff.png'
    for page, direction in ((1, 1), (2, 1), (1, 0), (0, 0)):
        buttons = response['components'][0].to_dict()['components']
        assert len({b['custom_id'] for b in buttons}) == 3
        ctx.custom_id = buttons[direction]['custom_id']
        asyncio.run(module.LolMatchViews.on_page.callback(cog, ctx))
        response = ctx.edit.call_args.kwargs
        assert response['attachments'] == []
        inspect.signature(interactions.ComponentContext.edit).bind(ctx, **response)
        assert response['embeds'].title == f'Page {page + 1}'
        assert ('file' in response) == (page != 2)
        if page != 2:
            assert response['file'].file_name == ('gold_diff.png', 'gold_roles.png')[page]
    assert calls[-1] == {'edit_origin': True}
    ctx.edit_origin.assert_not_awaited()
    def fail(*args):
        raise RuntimeError('test failure')
    monkeypatch.setattr(module, 'gold_response', fail)
    asyncio.run(module.LolMatchViews.on_page.callback(cog, ctx))
    assert ctx.edit.call_args.kwargs['attachments'] == []
    assert ctx.edit.call_args.kwargs['embeds'] == []
