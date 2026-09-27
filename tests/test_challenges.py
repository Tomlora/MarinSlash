"""Calculs, vrais composants interactions.py et parcours sans tokens ni réseau."""
import asyncio
import copy
import inspect
import functools
from types import SimpleNamespace
from unittest.mock import AsyncMock

import interactions
import pytest

from fonctions import challenge_progress as model
from fonctions import challenge_ui as ui
from fonctions import gestion_challenge as service
from cogs import challenges as cog


def entry(cid=101001, **kw):
    return dict({'id': cid, 'name': 'Chasseur de défis', 'description': 'Accomplis des objectifs.',
        'level': 'IRON', 'value': 47, 'position': 0, 'percentile': 0.2,
        'state': 'ENABLED', 'thresholds': {'IRON': 10, 'BRONZE': 50, 'GOLD': 100},
        'aggregate': False}, **kw)


def observation(entries=None, **kw):
    return dict({'version': 1, 'observed_at': '2026-09-27T18:00:00+00:00',
        'entries': entries if entries is not None else [entry()],
        'total': {'current': 1200, 'level': 'GOLD'}, 'categories': {}}, **kw)


PREFS = {'favorites': [], 'excluded': []}


def test_explicit_tiers_and_unranked_first_step():
    assert model.next_goal(entry(level='NONE', value=3)) == {
        'tier': 'IRON', 'target': 10, 'remaining': 7, 'ratio': .3}
    assert model.next_goal(entry(level='BRONZE', value=65))['tier'] == 'GOLD'
    assert model.next_goal(entry(level='CHALLENGER')) is None
    assert model.next_goal(entry(thresholds={})) is None
    assert model.next_goal(entry(value=50))['tier'] == 'GOLD'


def test_normalize_optional_fields_duplicate_ids_and_localization():
    raw = {'totalPoints': {}, 'challenges': [{'challengeId': 101001, 'value': 4},
        {'challengeId': 101001, 'value': 5, 'position': -10}]}
    config = [{'id': 101001, 'state': 'ENABLED', 'thresholds': {'IRON': 10},
               'localizedNames': {'en_US': {'name': '<em>Hello</em> @everyone'}}}]
    result = model.normalize(raw, config, 'now')
    assert len(result['entries']) == 1
    assert result['entries'][0]['value'] == 5
    assert result['entries'][0]['position'] == 0
    assert result['entries'][0]['name'] == 'Hello everyone'
    assert model.next_goal(result['entries'][0])['remaining'] == 5


@pytest.mark.parametrize('raw', [{}, {'status': {'status_code': 429}}, {'challenges': []}])
def test_reject_invalid_api_responses(raw):
    with pytest.raises(ValueError):
        model.normalize(raw, [], 'now')


def test_baseline_and_new_challenge_do_not_invent_gains():
    current = observation()
    result = model.compare(None, current, PREFS)
    assert result['baseline'] and result['points_delta'] is None and not result['changes']
    previous = observation([])
    assert not model.compare(previous, current, PREFS)['changes']


def test_zero_progress_and_no_rank_still_appear():
    old = observation([entry(value=0)])
    new = observation([entry(value=1)])
    result = model.compare(old, new, PREFS)
    assert result['changes'][0]['delta'] == 1
    assert result['changes'][0]['position'] == 0
    assert '1' in ui.match_pages(result, 'EUW1_123')[1].fields[0].value


def test_up_down_ranks_missing_position_and_exclusions():
    old = observation([entry(value=49, position=100), entry(101002, value=100, level='GOLD'), entry(101003)])
    new = observation([entry(value=51, position=80, level='BRONZE'), entry(101002, value=10, level='IRON'), entry(101003, value=50)])
    result = model.compare(old, new, {'favorites': [], 'excluded': [101003]})
    assert len(result['changes']) == 2
    assert result['changes'][0]['level_delta'] == 1
    assert result['changes'][0]['rank_delta'] == 20
    assert result['changes'][1]['level_delta'] < 0
    assert result['changes'][1]['delta'] == -90
    missing_rank = model.compare(observation([entry(position=100)]), observation(), PREFS)
    assert not missing_rank['changes']


def test_goals_prefer_favorites_and_filter_aggregate_disabled_excluded():
    rows = [entry(101001), entry(101002, value=20), entry(101003, state='DISABLED'),
            entry(101004, aggregate=True), entry(101005)]
    result = model.objectives(rows, {'favorites': [101002], 'excluded': [101005]})
    assert [e['id'] for e in result] == [101002, 101001]


def test_compare_does_not_modify_inputs():
    old, new = observation(), observation([entry(value=60)])
    before = copy.deepcopy((old, new))
    model.compare(old, new, PREFS)
    assert (old, new) == before


def assert_embed_limits(pages):
    for page in pages:
        assert isinstance(page, interactions.Embed)
        serialized = page.to_dict()
        assert len(serialized['title']) <= 256
        assert len(serialized['description']) <= 4096
        assert len(serialized.get('fields', [])) <= 25
        assert all(len(f['name']) <= 256 and len(f['value']) <= 1024 for f in serialized.get('fields', []))
        assert len(page) <= 6000


def test_large_snapshots_fit_real_discord_limits_and_no_truncation_of_entries():
    old = observation([entry(i, name='N' * 400, description='D' * 2000, value=20) for i in range(100000, 100230)])
    new = observation([dict(e, value=48) for e in old['entries']])
    pages = ui.match_pages(model.compare(old, new, PREFS), 'EUW1_1234567890')
    assert len(pages) == 48
    assert sum(len(p.fields) for p in pages[1:-1]) == 230
    assert_embed_limits(pages)
    assert_embed_limits(ui.profile_pages(new, PREFS, 'Marin#EUW'))


def test_native_buttons_coexist_with_records_and_remain_stable():
    records = interactions.Button(style=1, label='Records', custom_id='records')
    for available in (True, False):
        rows = ui.recap_components(records, 'EUW1_123', 45, available)
        buttons = rows[0].to_dict()['components']
        assert [b['label'] for b in buttons] == ['Records', 'Challenges']
        assert buttons[1]['disabled'] is not available
        assert cog.OPEN_RE.fullmatch(buttons[1]['custom_id']).groups() == ('EUW1_123', '45')
    for page in (0, 1, 2):
        buttons = ui.page_components('EUW1_123', 45, page, 3)[0].to_dict()['components']
        assert buttons[0]['disabled'] == (page == 0)
        assert buttons[2]['disabled'] == (page == 2)
        assert cog.PAGE_RE.fullmatch(buttons[2]['custom_id'])
        assert all(len(b['custom_id']) <= 100 for b in buttons)


def test_cog_registers_real_commands_and_callbacks():
    client = interactions.Client(sync_interactions=False)
    extension = cog.Challenges(client)
    names = {str(cmd.sub_cmd_name) for cmd in extension.commands if isinstance(cmd, interactions.SlashCommand) and str(cmd.name) == 'lol_challenges'}
    assert {'profil', 'objectifs', 'catalogue', 'suivre', 'historique', 'preferences', 'manage'} <= names
    extension.drop()


class Context:
    def __init__(self, custom_id='', author=1, guild=2):
        self.custom_id = custom_id
        self.author = SimpleNamespace(id=author)
        self.guild_id = guild
        self.defer = AsyncMock()
        self.send = AsyncMock()
        self.edit_origin = AsyncMock()


def callback(method):
    function = method.callback if hasattr(method, 'callback') else method
    while isinstance(function, functools.partial):
        function = function.func
    return function.__func__ if inspect.ismethod(function) else function


def test_open_acknowledges_before_loading_and_survives_restart(monkeypatch):
    ctx = Context('lolchal_open_EUW1_123_45')
    snapshot = model.compare(None, observation(), PREFS)
    async def load(*args):
        assert ctx.defer.await_count == 1
        return snapshot
    extension = object.__new__(cog.Challenges)
    extension.account = AsyncMock(return_value={'id_compte': 45})
    monkeypatch.setattr(cog, 'db', load)
    asyncio.run(callback(cog.Challenges.on_open)(extension, ctx))
    assert ctx.send.call_args.kwargs['ephemeral'] is True
    assert ctx.send.call_args.kwargs['components']


def test_match_pagination_edits_origin_and_clamps_page(monkeypatch):
    ctx = Context('lolchal_page_match_EUW1_123_45_999')
    extension = object.__new__(cog.Challenges)
    extension.account = AsyncMock()
    monkeypatch.setattr(cog, 'db', AsyncMock(return_value=model.compare(None, observation(), PREFS)))
    asyncio.run(callback(cog.Challenges.on_page)(extension, ctx))
    ctx.defer.assert_awaited_once_with(edit_origin=True)
    assert 'objectifs' in ctx.edit_origin.call_args.kwargs['embeds'].title
    assert not ctx.send.called


def test_expired_session_has_actionable_response():
    extension = object.__new__(cog.Challenges)
    extension.sessions = {}
    ctx = Context('lolchal_page_session_deadbeef_0_1')
    asyncio.run(callback(cog.Challenges.on_page)(extension, ctx))
    assert 'expiré' in ctx.edit_origin.call_args.kwargs['content']


def test_preferences_cannot_be_modified_by_another_user(monkeypatch):
    extension = object.__new__(cog.Challenges)
    extension.account = AsyncMock(return_value={'id_compte': 45, 'discord': '99'})
    save = AsyncMock()
    monkeypatch.setattr(cog, 'db', save)
    ctx = Context()
    asyncio.run(callback(cog.Challenges.challenges_suivre)(extension, ctx, 'Marin', '101001', 'suivre'))
    assert not save.called
    assert 'propriétaire' in ctx.send.call_args.args[0]


def test_replay_never_requests_riot(monkeypatch):
    snapshot = {'version': 1}
    monkeypatch.setattr(service.store, 'load_match', lambda *args: snapshot)
    fetch = AsyncMock()
    monkeypatch.setattr(service, 'request', fetch)
    assert asyncio.run(service.recap_snapshot(45, 'puuid', 'EUW1_123')) == snapshot
    assert asyncio.run(service.observe(45, 'puuid', 'EUW1_123')) == snapshot
    fetch.assert_not_called()


def test_riot_failure_never_saves_or_prevents_recap(monkeypatch):
    monkeypatch.setattr(service.store, 'load_match', lambda *args: None)
    monkeypatch.setattr(service.store, 'profile', lambda *args: (observation(), PREFS))
    monkeypatch.setattr(service, 'catalog', AsyncMock(return_value=[]))
    monkeypatch.setattr(service, 'request', AsyncMock(side_effect=RuntimeError('HTTP 429')))
    saved = []
    monkeypatch.setattr(service.store, 'save_observation', lambda *args: saved.append(args))
    assert asyncio.run(service.recap_snapshot(45, 'puuid', 'EUW1_123', capture=True)) is None
    assert not saved


def test_empty_response_never_erases_existing_baseline(monkeypatch):
    monkeypatch.setattr(service.store, 'profile', lambda *args: (observation(), PREFS))
    monkeypatch.setattr(service, 'catalog', AsyncMock(return_value=[]))
    monkeypatch.setattr(service, 'request', AsyncMock(return_value={'totalPoints': {}, 'challenges': []}))
    with pytest.raises(ValueError, match='vide'):
        asyncio.run(service.observe(45, 'puuid'))


def test_profile_consultation_does_not_consume_pending_progress(monkeypatch):
    current = observation()
    monkeypatch.setattr(service.store, 'profile', lambda *args: (current, PREFS))
    request = AsyncMock()
    monkeypatch.setattr(service, 'request', request)
    assert asyncio.run(service.observe(45, 'puuid', initialize_only=True)) == current
    request.assert_not_called()
