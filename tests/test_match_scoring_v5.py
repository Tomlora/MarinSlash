"""Attainable scales, monotonicity, coherent totals and reported Tristana case."""
import copy
import importlib
import json
import pytest
from test_match_scoring import modules, match_fixture, calculate, by_id, PROFILE_CASES


def curves():
    return importlib.import_module('fonctions.match.scoring_curves')


def engine():
    return importlib.import_module('fonctions.match.scoring_v5')


@pytest.mark.parametrize('kind', ['kda','cs','gold','damage','dpg','vision','utility','cc','pinks'])
def test_rate_scales_are_continuous_monotone_and_reach_ten(modules, kind):
    c = curves()
    anchors = c.rate_anchors(kind, 100)
    for value, score in anchors:
        assert c.rate_score(kind,value,100) == pytest.approx(score)
        assert abs(c.rate_score(kind,value+.00001,100)-c.rate_score(kind,value-.00001,100)) < .001
    values = [c.rate_score(kind,x,100) for x in range(401)]
    assert values == sorted(values)
    assert min(values) == 0 and max(values) == 10
    assert c.rate_score(kind,.001,100) > 0


@pytest.mark.parametrize('reference', [35,45,50,55,60,66,70,75,90])
@pytest.mark.parametrize('minimum', [3,8])
def test_percentages_reach_ten_without_more_than_100_percent(modules, reference, minimum):
    c = curves()
    assert c.participation_score(0,reference,minimum,minimum) == 0
    assert c.participation_score(reference,reference,minimum,minimum) == 5
    assert c.participation_score((reference+100)/2,reference,minimum,minimum) == 8
    assert c.participation_score(100,reference,minimum,minimum) == 10
    assert c.participation_score(100,reference,1,minimum) < 10
    assert c.participation_score(0,reference,0,minimum) == 5
    values = [c.participation_score(x,reference,minimum,minimum) for x in range(101)]
    assert values == sorted(values)


def test_survival_and_lane_advantage_have_explicit_reachable_bounds(modules):
    c = curves()
    deaths = [c.survival_score(n/10,5) for n in range(1000)]
    assert deaths == sorted(deaths,reverse=True)
    assert deaths[0] == 10 and deaths[-1] > 0
    assert c.survival_score(2.5,5) == 8
    assert c.survival_score(5,5) == 5
    for value,score in [(-3000,0),(-1500,2),(0,5),(1500,8),(3000,10)]:
        assert c.advantage_score(value,1500) == score


@pytest.mark.parametrize('role,profile', PROFILE_CASES)
@pytest.mark.parametrize('minutes', [10,20,30,40,60])
def test_all_profiles_and_durations_keep_same_eight_and_ten_anchors(modules, monkeypatch, role, profile, minutes):
    original = modules[1].get_profile_for_champion
    monkeypatch.setattr(modules[1], 'get_profile_for_champion',
        lambda c,r: modules[1].ChampionProfile(profile) if r == role else original(c,r))
    match = calculate(match_fixture(modules,duration=minutes*60))
    m = next(m for m in match.player_metrics_liste if m.role == role)
    refs = engine().references(m)
    for name,field in [('cs','cs_per_min'),('gold','gold_per_min'),('damage','damage_per_min'),('vision','vision_per_min'),('kda','kda')]:
        good,excellent = curves().RATE_TARGETS[name]
        for ratio,expected in [(1,5),(good,8),(excellent,10)]:
            setattr(m,field,refs[name]*ratio)
            parts,_ = engine().build_parts(m)
            assert parts[name]['score'] == pytest.approx(expected)
    engine().statistical_score(m)
    engine().contribution_score(m)
    assert 0 <= m.zscore_score <= 10
    assert sum(p['points'] for p in m.statistical_components) == pytest.approx(m.zscore_score)
    for dimension in m.explanation_context['dimensions']:
        assert sum(p['points'] for p in dimension['components']) == pytest.approx(dimension['score'])
    weights = [m.final_combat_weight,m.final_economic_weight,m.final_objective_weight,m.final_tempo_weight,m.final_impact_weight]
    assert sum(d['score']*w for d,w in zip(m.explanation_context['dimensions'],weights)) == pytest.approx(m.breakdown_score)
    json.dumps(m.explanation_context,allow_nan=False)


def test_same_observation_has_same_grade_in_statistics_and_dimensions(modules):
    match = calculate(match_fixture(modules))
    for m in match.player_metrics_liste:
        parts,_ = engine().build_parts(m)
        scores = {p['label']:p['score'] for p in parts.values()}
        assert all(p['score'] == scores[p['label']] for p in m.statistical_components)
        assert sum(p['weight'] for p in m.statistical_components) == pytest.approx(1)


def test_absent_kills_are_excluded_and_absent_objectives_cannot_penalize(modules):
    match = calculate(match_fixture(modules))
    m = by_id(match)[1]
    m.observed_team_kills = 0
    m.objective_opportunities = {'epic':0,'tower':0}
    engine().statistical_score(m)
    engine().contribution_score(m)
    kp = m.explanation_context['dimensions'][0]['components'][1]
    assert kp['neutral'] and kp['weight'] == 0
    assert all(p['label'] != kp['label'] for p in m.statistical_components)


def test_low_contribution_has_no_hidden_floor_and_bonus_cannot_exceed_ten(modules):
    match = calculate(match_fixture(modules, tracked=4))
    m = by_id(match)[4]
    m.combat_weight_adj,m.objective_weight_adj,m.tempo_weight_adj,m.impact_weight_adj = -.2,-.1,-.15,-.25
    m.dpg,m.cs_per_min,m.gold_per_min = 0,0,0
    engine().contribution_score(m)
    assert m.economic_efficiency == m.breakdown_score == 0
    m.gold_diff_15,m.cs_diff_15 = 10000,1000
    m.has_first_blood = m.has_first_tower = True
    engine().contribution_score(m)
    assert m.pace_rating == 10
    assert m.explanation_context['dimensions'][3]['components'][-1]['points'] == 0


def tristana_case(modules):
    match = match_fixture(modules,tracked=4,duration=1880)
    modules[1]._CHAMPION_TAGS_CACHE['tristana'] = ['Marksman']
    players = match.match_detail['info']['participants']
    for p,kills in zip(players[:5],[4,4,4,17,3]):
        p['kills'] = kills
    players[3].update(championName='Tristana',deaths=3,assists=8,goldEarned=22459,
        totalDamageDealtToChampions=51624,totalMinionsKilled=296,visionScore=41,visionWardsBoughtInGame=3)
    calculate(match)
    m = by_id(match)[4]
    # Freeze the adjustments implied by the user's saved references, rather
    # than guessing the live champion-tag/BDD state of that historical match.
    m.dpm_mult, m.cs_mult, m.kp_mult = 1.05, .95, 1.1
    m.gold_diff_15,m.cs_diff_15 = 1945,16
    m.objective_opportunities = {'epic':7,'tower':10}
    m.objective_presence = {'epic':3,'tower':7}
    m.early_solo_kills = 1
    engine().statistical_score(m)
    engine().contribution_score(m)
    return match,m


def test_tristana_reported_case_and_honest_positive_summaries(modules):
    _,m = tristana_case(modules)
    old = copy.deepcopy(m)
    legacy = importlib.import_module('fonctions.match.scoring_v4')
    legacy.statistical_score(old)
    legacy.contribution_score(old)
    assert old.kp_score == pytest.approx(5.64,abs=.01)
    assert old.cs_score == pytest.approx(6.10,abs=.02)
    assert old.economic_efficiency == pytest.approx(6.69,abs=.02)
    assert 7 < m.kp_score < 8
    assert 7.9 < m.cs_score < 8.1
    assert m.economic_efficiency > 8
    assert m.combat_value > old.combat_value
    assert m.win_impact > old.win_impact
    for index in (0,1,3,4):
        text = m.explanation_context['dimensions'][index]['summary']
        assert 'limite' not in text and 'Sous le repère' not in text
    assert 'Sous le repère' in m.explanation_context['dimensions'][2]['summary']
    tempo = m.explanation_context['dimensions'][3]['components']
    assert '+1 945 or' in tempo[0]['observation']
    assert 'ne s’applique pas au rôle ADC' in tempo[-1]['observation']
