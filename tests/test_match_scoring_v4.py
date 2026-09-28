"""V4 behavioral regressions, including duration and kit applicability."""
import copy
import importlib
import json
import math

import pytest
from test_match_scoring import modules, match_fixture, calculate, by_id, PROFILE_CASES


def engine():
    return importlib.import_module('fonctions.match.scoring_v4')


@pytest.mark.parametrize('role,profile', PROFILE_CASES)
@pytest.mark.parametrize('minutes', [20, 30, 40])
def test_expected_rates_are_neutral_at_each_duration(modules, monkeypatch, role, profile, minutes):
    profiles = modules[1]
    original = profiles.get_profile_for_champion
    monkeypatch.setattr(profiles, 'get_profile_for_champion', lambda c,r:
        profiles.ChampionProfile(profile) if r == role else original(c,r))
    match = calculate(match_fixture(modules, duration=minutes*60))
    m = next(m for m in match.player_metrics_liste if m.role == role)
    refs = engine().references(m)
    m.damage_per_min, m.gold_per_min = refs['damage'], refs['gold']
    m.cs_per_min, m.vision_per_min = refs['cs'], refs['vision']
    m.kda, m.kp = refs['kda'], refs['kp']
    m.deaths = refs['deaths']
    m.damage, m.gold = m.damage_per_min*minutes, m.gold_per_min*minutes
    m.dpg = m.damage/m.gold
    match._calculate_zscores(m)
    match._calculate_breakdown_scores(m)
    assert m.zscore_score == pytest.approx(5)
    assert m.dpg_score == pytest.approx(5)
    assert m.cs_score == m.vision_score == m.gpm_relative_score == pytest.approx(5)
    assert m.death_score == pytest.approx(5)
    assert m.explanation_context['duration_minutes'] == minutes
    for dimension in m.explanation_context['dimensions']:
        assert sum(p['points'] for p in dimension['components']) == pytest.approx(dimension['score'])
    json.dumps(m.explanation_context, allow_nan=False)


def test_phase_curves_are_continuous_and_distinct(modules):
    v4 = engine()
    for kind in v4.RATE_ANCHORS:
        for minute in (10,20,30,40,60):
            assert abs(v4.duration_factor(kind,minute-.0001)-v4.duration_factor(kind,minute+.0001)) < .0001
        assert v4.duration_factor(kind,1000) == v4.duration_factor(kind,60)
    assert v4.duration_factor('damage',20) < v4.duration_factor('damage',40)
    assert v4.duration_factor('vision',20) < v4.duration_factor('vision',40)
    assert v4.duration_factor('cs',20) == v4.duration_factor('cs',40)
    assert v4.relative_score(.9,1) > 4
    assert v4.relative_score(1,1) == 5
    assert v4.relative_score(2,1) == 8
    assert v4.relative_score(0,1) == 0
    assert v4.relative_score(.001,1) > 0


def test_same_production_is_not_more_valuable_just_because_match_is_longer(modules):
    short = by_id(calculate(match_fixture(modules,duration=1200)))[3]
    long = by_id(calculate(match_fixture(modules,duration=2400)))[3]
    # Identical totals spread over twice the time, against later-game references.
    assert short.dpm_relative_score > long.dpm_relative_score
    assert short.vision_score > long.vision_score
    assert short.gpm_relative_score > long.gpm_relative_score
    assert short.explanation_context['references']['damage'] < long.explanation_context['references']['damage']


def test_neutral_early_game_does_not_require_rare_events(modules):
    match = calculate(match_fixture(modules))
    for m in match.player_metrics_liste:
        m.gold_diff_15 = m.cs_diff_15 = 0
        m.has_first_blood = m.has_first_blood_assist = False
        m.has_first_tower = m.has_first_tower_assist = False
        m.early_solo_kills = 0
        match._calculate_breakdown_scores(m)
        assert m.pace_rating == 5
        m.has_first_blood_assist = True
        match._calculate_breakdown_scores(m)
        assert m.pace_rating == 5.25


def test_support_does_not_gain_tempo_by_taking_cs(modules):
    match = calculate(match_fixture(modules))
    m = by_id(match)[5]
    before = m.pace_rating
    m.cs_diff_15 += 300
    match._calculate_breakdown_scores(m)
    assert m.pace_rating == before
    assert all(p['label'] != 'Avance en sbires à 15 minutes' for p in m.explanation_context['dimensions'][3]['components'])


def test_tank_without_ally_shields_is_scored_on_controls_only(modules):
    match = match_fixture(modules)
    modules[1]._CHAMPION_TAGS_CACHE['leona'] = ['Tank','Support']
    match.match_detail['info']['participants'][4].update(championName='Leona',
        totalHealsOnTeammates=0,totalDamageShieldedOnTeammates=0,timeCCingOthers=45)
    m = by_id(calculate(match))[5]
    assert m.utility_score == 5
    assert len(m.utility_parts) == 1
    assert m.utility_parts[0]['label'] == 'Contrôles (secondes)'
    assert all(p['label'] != 'Aide apportée aux alliés' for d in m.explanation_context['dimensions'][:4] for p in d['components'])


def test_ivern_and_hybrid_support_have_applicable_utility(modules):
    match = match_fixture(modules)
    modules[1]._CHAMPION_TAGS_CACHE.update(ivern=['Support','Mage'], senna=['Support','Marksman'])
    for index,champ in [(1,'Ivern'),(4,'Senna')]:
        match.match_detail['info']['participants'][index].update(championName=champ,
            totalHealsOnTeammates=0,totalDamageShieldedOnTeammates=0,timeCCingOthers=30)
    calculate(match)
    assert by_id(match)[2].profile == 'SUPPORT_UTILITY'
    assert by_id(match)[2].utility_available
    assert by_id(match)[5].utility_available
    assert by_id(match)[5].utility_parts[0]['score'] == 0  # applicable real zero retained
    assert modules[1].get_profile_for_champion('Samira','ADC').value == 'ASSASSIN'
    fallback = modules[1].get_profile_adjustments('ADC', modules[1].ChampionProfile.FIGHTER)
    assert fallback.damage_per_min_mult != 1


def test_no_baron_and_opponent_objectives_do_not_penalize_individual(modules):
    match = match_fixture(modules, tracked=6)
    frame = match.data_timeline['info']['frames'][0]
    frame['events'] = [{'type':'ELITE_MONSTER_KILL','monsterType':'DRAGON','killerId':7} for _ in range(2)]
    calculate(match)
    jungle = by_id(match)[7]
    assert jungle.objective_opportunities == {'epic':2, 'tower':0}
    assert 5 < jungle.obj_participation_score < 10
    old = jungle.objective_contribution
    frame['events'].append({'type':'ELITE_MONSTER_KILL','monsterType':'BARON_NASHOR','killerId':2})
    calculate(match)
    assert by_id(match)[7].objective_contribution == old
    assert not any('Baron' in p['label'] for p in by_id(match)[7].explanation_context['dimensions'][2]['components'])


def test_last_hit_and_assist_receive_equal_objective_credit(modules):
    match = calculate(match_fixture(modules, tracked=6))
    a,b = by_id(match)[6],by_id(match)[7]
    assert a.objective_presence == b.objective_presence
    assert a.objective_opportunities == b.objective_opportunities


def test_death_score_independent_of_teammate_deaths(modules):
    low = match_fixture(modules)
    high = copy.deepcopy(low)
    high.match_detail['info']['participants'][1]['deaths'] = 50
    a = by_id(calculate(low))[1]
    b = by_id(calculate(high))[1]
    assert a.death_score == b.death_score


@pytest.mark.parametrize('mode', ['ARAM','CLASH ARAM','ARENA 2v2','SWARM','OTHER'])
def test_unsupported_modes_are_explicitly_neutral(modules, mode):
    match = match_fixture(modules)
    match.thisQ = mode
    calculate(match)
    assert match.scores_liste == [5]*10
    assert all(not m.scoring_supported for m in match.player_metrics_liste)
    assert all(m.explanation_context['dimensions'][0]['summary'].startswith('Mode ou rôle') for m in match.player_metrics_liste)


def test_unknown_role_is_not_silently_judged_as_mid(modules):
    match = match_fixture(modules)
    for p in match.match_detail['info']['participants']:
        p['teamPosition'] = ''
    calculate(match)
    assert match.scores_liste == [5]*10


def test_early_advantage_not_rescaled_using_end_of_game_time(modules):
    a = by_id(calculate(match_fixture(modules,tracked=6,duration=1200)))[6]
    b = by_id(calculate(match_fixture(modules,tracked=6,duration=2400)))[6]
    assert a.gold_15_score == b.gold_15_score
    assert a.cs_15_score == b.cs_15_score
    assert a.pace_rating == b.pace_rating
