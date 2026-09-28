"""Offline scoring regressions: real calculations, no Riot/Discord/DB calls."""
import ast
import asyncio
import copy
import importlib.util
import json
import math
from pathlib import Path
import sys
import types

import pytest

ROOT = Path(__file__).resolve().parents[1]
MATCH = ROOT / "fonctions" / "match"


@pytest.fixture
def modules(monkeypatch):
    for name, directory in (("fonctions", ROOT / "fonctions"), ("fonctions.match", MATCH)):
        package = types.ModuleType(name)
        package.__path__ = [str(directory)]
        monkeypatch.setitem(sys.modules, name, package)
    def load(name, path):
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, name, module)
        spec.loader.exec_module(module)
        return module
    profiles = load("fonctions.match.champion_profiles", MATCH / "champion_profiles.py")
    inputs = load("fonctions.match.scoring_inputs", MATCH / "scoring_inputs.py")
    scoring = load("fonctions.match.scoring", MATCH / "scoring.py")
    profiles._load_default_profile_adjustments()
    profiles._CHAMPION_TAGS_CACHE = {
        "tank": ["Tank"], "mage": ["Mage"], "marksman": ["Marksman"],
        "utility": ["Support"], "fighter": ["Fighter"]}
    # Execute the actual team extraction class without its unrelated import-time dependencies.
    tree = ast.parse((MATCH / "matchlol_team.py").read_text(encoding="utf-8"))
    klass = next(node for node in tree.body if isinstance(node, ast.ClassDef))
    env = {"game_minutes": inputs.game_minutes}
    exec(compile(ast.Module(body=[klass], type_ignores=[]), str(MATCH / "matchlol_team.py"), "exec"), env)
    cls = type("Match", (scoring.ScoringMixin, env["MatchLolTeamData"]), {})
    return scoring, profiles, inputs, cls


def match_fixture(modules, tracked=1, duration=1800):
    _, _, _, cls = modules
    participants = []
    roles = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]
    champions = ["tank", "fighter", "mage", "marksman", "utility"]
    for i in range(10):
        participants.append({
            "participantId": i + 1, "puuid": f"p{i+1}", "teamId": 100 if i < 5 else 200,
            "teamPosition": roles[i % 5], "championName": champions[i % 5],
            "riotIdGameName": f"Player{i+1}", "riotIdTagline": "TEST",
            "kills": 5, "deaths": 5, "assists": 10, "goldEarned": 12000,
            "totalDamageDealtToChampions": 18000, "totalDamageTaken": 20000,
            "totalMinionsKilled": 180, "neutralMinionsKilled": 0, "visionScore": 30,
            "damageDealtToTurrets": 2000, "damageDealtToObjectives": 4000,
            "visionWardsBoughtInGame": 2, "turretKills": 1,
        })
    objectives = {key: {"kills": 0} for key in ("baron","dragon","horde","riftHerald","tower","inhibitor")}
    match = cls()
    match.match_detail = {"info": {"gameDuration": duration, "participants": participants,
                                  "teams": [{"objectives": objectives}, {"objectives": objectives}]}}
    match.thisId = tracked - 1
    match.puuid = f"p{tracked}"
    match.thisQ = "RANKED"
    match.thisWinBool = tracked <= 5
    match.nb_joueur = 10
    match.thisTime = 30
    match.thisGoldNoFormat = 12000
    match.thisKills = 5
    match.thisDeaths = 5
    match.thisAssists = 10
    match.match_detail_challenges = {"teamBaronKills": 0, "teamElderDragonKills": 0}
    match.data_timeline = {"info": {"frames": [{
        "timestamp": 900000,
        "participantFrames": {str(i): {"totalGold": 4000 if i <= 5 else 6000,
                                      "minionsKilled": 100 if i <= 5 else 130,
                                      "jungleMinionsKilled": 0} for i in range(1, 11)},
        "events": [
            {"type":"ELITE_MONSTER_KILL","monsterType":"DRAGON","killerId":6,"assistingParticipantIds":[7,10]},
            {"type":"CHAMPION_KILL","timestamp":180000,"killerId":6,"assistingParticipantIds":[]},
            {"type":"BUILDING_KILL","buildingType":"TOWER_BUILDING","killerId":6,"assistingParticipantIds":[7]},
        ]
    }]}}
    return match


def calculate(match):
    asyncio.run(match._extract_team_data())
    asyncio.run(match.calculate_all_scores())
    return match


def by_id(match):
    return dict(zip(match.thisParticipantIdListe, match.player_metrics_liste))


@pytest.fixture
def explanations():
    spec = importlib.util.spec_from_file_location('score_explanations_test', MATCH / 'score_explanations.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PROFILE_CASES = [(row['role'], row['profile']) for row in
                 json.loads((MATCH / 'scoring_profile_defaults.json').read_text(encoding='utf-8'))]


@pytest.mark.parametrize('role,profile', PROFILE_CASES)
@pytest.mark.parametrize('data_state', ['complete', 'missing', 'zero'])
def test_explanations_reconcile_all_profiles_and_missing_data(modules, explanations, monkeypatch, role, profile, data_state):
    profiles = modules[1]
    original = profiles.get_profile_for_champion
    monkeypatch.setattr(profiles, 'get_profile_for_champion',
                        lambda champ, r: profiles.ChampionProfile(profile) if r == role else original(champ, r))
    match = match_fixture(modules, tracked=6)
    if data_state == 'missing':
        match.data_timeline = None
    else:
        for p in match.match_detail['info']['participants']:
            p.update(totalHealsOnTeammates=12000 if data_state == 'complete' else 0,
                     totalDamageShieldedOnTeammates=6000 if data_state == 'complete' else 0,
                     timeCCingOthers=45 if data_state == 'complete' else 0)
    calculate(match)
    m = next(m for m in match.player_metrics_liste if m.role == role)
    assert m.profile == profile
    detail = explanations.build_dimension_explanations(m)
    assert detail is not None
    assert len(detail['dimensions']) == 5
    json.dumps(detail, allow_nan=False)
    for dimension in detail['dimensions']:
        parts = dimension['components']
        assert sum(p['weight'] for p in parts) == pytest.approx(1)
        assert sum(p['points'] for p in parts) == pytest.approx(getattr(m, dimension['key']))
        assert all(0 <= p['score'] <= 10 for p in parts)
        fields = explanations.explanation_fields(dimension)
        assert all(len(name) <= 256 and len(value) <= 900 for name, value in fields)
        assert 'Additionne' in fields[-1][1]
    if data_state == 'missing':
        neutral = [p for d in detail['dimensions'] for p in d['components'] if p['neutral']]
        assert neutral and all(p['score'] == 5 for p in neutral)
    if role == 'SUPPORT' and profile in ('TANK', 'SUPPORT_UTILITY'):
        utility = detail['dimensions'][4]['components'][0]
        assert utility['label'] == 'Aide apportée aux alliés'
        if data_state == 'zero':
            assert utility['score'] == 0 and not utility['neutral']
        elif data_state == 'complete':
            assert 'Contrôles' in utility['observation']


def test_explanations_freeze_references_and_refuse_inconsistent_formulas(modules, explanations):
    match = calculate(match_fixture(modules))
    m = by_id(match)[1]
    detail = explanations.build_dimension_explanations(m)
    before = json.dumps(detail, ensure_ascii=False)
    modules[0].BREAKDOWN_BASELINES['kp']['max'] = 1234
    assert json.dumps(explanations.build_dimension_explanations(m), ensure_ascii=False) == before
    assert explanations.build_dimension_explanations(types.SimpleNamespace()) is None
    m.combat_value += 1
    assert explanations.build_dimension_explanations(m) is None


def test_explanations_use_adjusted_thresholds_and_actual_points(modules, explanations):
    match = calculate(match_fixture(modules, tracked=6))
    m = by_id(match)[6]
    detail = explanations.build_dimension_explanations(m)
    kp = detail['dimensions'][0]['components'][1]
    assert '60.00 %' in kp['observation']
    expected = detail['references']['kp']*100
    assert f'{expected:.2f} %' in kp['reference']
    assert kp['points'] == pytest.approx(m.kp_score * .35)


def test_partial_support_data_explains_exclusion_without_neutralizing_observed_zero(modules, explanations):
    match = match_fixture(modules, tracked=10)
    match.match_detail['info']['participants'][9]['timeCCingOthers'] = 0
    calculate(match)
    detail = explanations.build_dimension_explanations(by_id(match)[10])
    utility = detail['dimensions'][4]['components'][0]
    assert utility['score'] == 0 and not utility['neutral']
    assert 'donnée absente' in utility['observation']
    assert 'exclue' in utility['observation']
    assert 'Contrôles (secondes) : 0.00/min' in utility['observation']


def test_same_match_from_both_sides_has_identical_metrics_and_rank(modules):
    blue = calculate(match_fixture(modules, 1))
    red = calculate(match_fixture(modules, 6))
    for pid in range(1, 11):
        a, b = by_id(blue)[pid], by_id(red)[pid]
        for field in ("performance_score", "gold_diff_15", "cs_diff_15", "dragon_participation",
                      "has_first_blood", "solo_kills", "objective_contribution", "pace_rating"):
            assert getattr(a, field) == pytest.approx(getattr(b, field)), (pid, field)
        assert blue._get_player_rank(blue.thisParticipantIdListe.index(pid)) == red._get_player_rank(red.thisParticipantIdListe.index(pid))
    assert by_id(red)[6].gold_diff_15 == 2000
    assert by_id(red)[6].has_first_blood
    assert by_id(red)[6].dragon_participation == 1
    assert by_id(red)[1].gold_diff_15 == -2000


def test_roles_follow_participants_not_array_position(modules):
    match = match_fixture(modules)
    participants = match.match_detail["info"]["participants"]
    participants[0], participants[4] = participants[4], participants[0]
    match.thisId = 4
    calculate(match)
    assert match.thisPositionListe[0] == "SUPPORT"
    assert by_id(match)[5].role == "SUPPORT"
    assert by_id(match)[1].opponent_index == 5


def test_duration_uses_seconds_not_display_or_divided_minutes(modules):
    match = calculate(match_fixture(modules, duration=1830))
    assert by_id(match)[1].game_minutes == 30.5
    assert by_id(match)[1].damage_per_min == pytest.approx(18000 / 30.5)
    assert match.thisDamagePerMinuteListe[0] == round(18000 / 30.5, 1)
    assert match.thisMinionPerMinListe[0] == round(180 / 30.5, 1)


@pytest.mark.parametrize("timeline", [None, "", {}, {"info": {"frames": []}}])
def test_missing_timeline_is_neutral_and_finite(modules, timeline):
    match = match_fixture(modules)
    match.data_timeline = timeline
    calculate(match)
    for m in match.player_metrics_liste:
        assert not m.timeline_available
        assert m.obj_participation_score == 5
        assert m.gold_15_score == m.cs_15_score == 5
        assert m.fb_score == m.ft_score == 5
        assert 1 <= m.performance_score <= 10


def test_short_game_does_not_pretend_to_have_stats_at_15(modules):
    match = match_fixture(modules, duration=600)
    match.data_timeline["info"]["frames"][0]["timestamp"] = 600000
    calculate(match)
    assert not by_id(match)[1].gold_15_available
    assert by_id(match)[1].gold_15_score == 5


def test_partial_frame_does_not_create_fake_lane_advantage(modules):
    match = match_fixture(modules)
    del match.data_timeline["info"]["frames"][0]["participantFrames"]["6"]
    calculate(match)
    assert not by_id(match)[1].gold_15_available
    assert not by_id(match)[6].gold_15_available


def test_grubs_denominator_and_duplicate_assists(modules):
    match = match_fixture(modules)
    frame = match.data_timeline["info"]["frames"][0]
    frame["events"] = [{"type":"ELITE_MONSTER_KILL","monsterType":"HORDE","killerId":1,
                        "assistingParticipantIds":[1,2,2]} for _ in range(6)]
    calculate(match)
    assert match.thisTotalObjectives == 3
    assert by_id(match)[1].objectives_participated == 3
    assert by_id(match)[2].objectives_participated == 3


def test_tower_assist_is_not_half_a_kill(modules):
    match = calculate(match_fixture(modules))
    assert by_id(match)[6].tower_participation == by_id(match)[7].tower_participation == 1


def test_objectives_now_increase_final_score(modules):
    without = match_fixture(modules)
    with_objectives = copy.deepcopy(without)
    with_objectives.data_timeline["info"]["frames"][0]["events"].append(
        {"type":"ELITE_MONSTER_KILL","monsterType":"BARON_NASHOR","killerId":2})
    without = calculate(without)
    with_objectives = calculate(with_objectives)
    assert by_id(with_objectives)[2].zscore_score == by_id(without)[2].zscore_score
    assert by_id(with_objectives)[2].performance_score > by_id(without)[2].performance_score


def test_kda_extreme_cannot_dominate_and_deathless_has_no_bonus(modules):
    scoring, _, _, cls = modules
    baseline = scoring.ROLE_BASELINES[scoring.Role.MID]
    m = scoring.PlayerMetrics(0, role_enum=scoring.Role.MID, profile="MAGE", game_minutes=30)
    for target, source in (("kda","kda"),("cs_per_min","cs_per_min"),("damage_per_min","damage_per_min"),
                           ("damage_share","damage_share"),("gold_per_min","gold_per_min"),
                           ("vision_per_min","vision_score_per_min"),("kp","kp"),("damage_taken_share","damage_taken_share")):
        setattr(m, target, getattr(baseline, source)[0])
    calculator = cls()
    m.kda = 30
    calculator._calculate_zscores(m)
    assert m.z_kda == 3
    assert m.zscore_score < 7
    m.kda = 300
    calculator._calculate_zscores(m)
    assert m.zscore_score < 7
    match = match_fixture(modules)
    match.match_detail["info"]["participants"][0]["deaths"] = 0
    calculate(match)
    assert by_id(match)[1].kda == 15


def test_actual_team_deaths_include_executions(modules):
    match = match_fixture(modules)
    match.match_detail["info"]["participants"][0]["deaths"] = 20
    calculate(match)
    assert by_id(match)[1].team_deaths == 40
    assert by_id(match)[1].death_share == 0.5


def test_ally_utility_rewards_support_without_damage_inflation(modules):
    low = match_fixture(modules)
    high = copy.deepcopy(low)
    for obj, value in ((low, 0), (high, 12000)):
        p = obj.match_detail["info"]["participants"][4]
        p.update(totalHealsOnTeammates=value, totalDamageShieldedOnTeammates=value, timeCCingOthers=30)
        calculate(obj)
    assert by_id(high)[5].performance_score > by_id(low)[5].performance_score
    assert by_id(high)[5].utility_available
    assert by_id(high)[5].damage == by_id(low)[5].damage
    missing = calculate(match_fixture(modules))
    assert not by_id(missing)[5].utility_available
    assert by_id(missing)[5].utility_score == 5


def test_no_automatic_bonus_for_winning_team_gold(modules):
    match = calculate(match_fixture(modules))
    m = by_id(match)[1]
    old = m.breakdown_score
    m.enemy_gold *= 0.5
    match._calculate_breakdown_scores(m)
    assert m.breakdown_score == old


def test_ranking_uses_precision_and_shares_exact_ties(modules):
    match = calculate(match_fixture(modules))
    match.raw_scores_liste = [5.51, 5.54] + [5.0] * 8
    match.scores_liste = [5.5, 5.5] + [5.0] * 8
    match._identify_mvp_ace()
    assert match.mvp_index == 1
    assert match._get_player_rank(1) == 1
    assert match._get_player_rank(0) == 2
    assert match._get_player_rank(2) == match._get_player_rank(9) == 3
    match.raw_scores_liste = [5.5] * 10
    match._identify_mvp_ace()
    assert match.mvp_indices == list(range(10))
    assert [match._get_player_rank(i) for i in range(10)] == [1] * 10


def test_red_summary_ace_and_team_colour_use_local_identity(modules):
    match = calculate(match_fixture(modules, tracked=6))
    match.raw_scores_liste = [9.0] + [5.0] * 9
    match.scores_liste = [9.0] + [5.0] * 9
    match._identify_mvp_ace()
    summary = match.get_player_performance_summary()
    assert summary["is_ace"]
    assert summary["team"] == "red"


def test_all_21_fallback_profiles_match_user_snapshot(modules):
    _, profiles, _, _ = modules
    data = json.loads((MATCH / "scoring_profile_defaults.json").read_text())
    assert len(data) == len(profiles._PROFILE_ADJUSTMENTS_CACHE) == 21
    for row in data:
        actual = profiles.get_profile_adjustments(row["role"], profiles.ChampionProfile(row["profile"]))
        for key, value in row.items():
            if key.endswith(("_mult", "_adj")):
                assert getattr(actual, key) == value
    assert profiles.get_profile_adjustments("UTILITY", profiles.ChampionProfile.SUPPORT_UTILITY).gold_per_min_mult == .65
    assert profiles.get_champion_profile(["Support","Assassin"], "UTILITY") == profiles.ChampionProfile.ASSASSIN


def test_database_partial_invalid_values_keep_safe_defaults(modules, monkeypatch):
    _, profiles, _, _ = modules
    class Frame:
        @property
        def T(self):
            return self
        def iterrows(self):
            yield 0, {"role":"SUPPORT","profile":"SUPPORT_UTILITY","gold_per_min_mult":0,
                      "vision_mult":float("nan"),"kp_mult":1.12}
    database = types.ModuleType("fonctions.gestion_bdd")
    database.lire_bdd_perso = lambda *a, **kw: Frame()
    monkeypatch.setitem(sys.modules, database.__name__, database)
    profiles.clear_caches()
    values = profiles.load_profile_adjustments()
    assert len(values) == 21
    adj = profiles.get_profile_adjustments("SUPPORT", profiles.ChampionProfile.SUPPORT_UTILITY)
    assert adj.gold_per_min_mult == .65
    assert adj.vision_mult == 1.15
    assert adj.kp_mult == 1.12


def test_recalculation_is_idempotent_and_components_explain_final(modules):
    match = calculate(match_fixture(modules))
    old = list(match.raw_scores_liste)
    asyncio.run(match.calculate_all_scores())
    assert match.raw_scores_liste == old
    for m in match.player_metrics_liste:
        assert m.performance_score == pytest.approx(.7*m.zscore_score + .3*m.breakdown_score)
        assert math.isfinite(m.performance_score)


def test_shared_sql_rows_have_same_identity_from_both_sides(modules, monkeypatch):
    calls = []
    database = types.ModuleType('fonctions.gestion_bdd')
    database.requete_perso_bdd = lambda query, params: calls.append((query, params))
    monkeypatch.setitem(sys.modules, database.__name__, database)
    saved = []
    for tracked in (1, 6):
        match = calculate(match_fixture(modules, tracked))
        match.last_match = 'EUW1_TEST'
        calls.clear()
        asyncio.run(match.save_player_scoring_data())
        assert len(calls) == 10
        saved.append({p['player_index']: p for _, p in calls})
    assert saved[0] == saved[1]
    assert saved[1][5]['riot_id'] == 'Player6'


def test_score_sql_updates_identity_and_matches_display_rank(modules, monkeypatch):
    calls = []
    database = types.ModuleType('fonctions.gestion_bdd')
    database.requete_perso_bdd = lambda query, params: calls.append((query, params))
    monkeypatch.setitem(sys.modules, database.__name__, database)
    tree = ast.parse((MATCH / 'save_data.py').read_text(encoding='utf-8'))
    method = next(n for n in ast.walk(tree) if isinstance(n, ast.AsyncFunctionDef) and n.name == 'save_scoring_data')
    env = {'storage_index': modules[2].storage_index}
    exec(compile(ast.Module(body=[method], type_ignores=[]), 'save_data.py', 'exec'), env)
    match = calculate(match_fixture(modules, tracked=6))
    match.last_match = 'EUW1_TEST'
    asyncio.run(env['save_scoring_data'](match))
    assert len(calls) == 10
    for query, params in calls:
        local = match.thisParticipantIdListe.index(params['player_index'] + 1)
        assert params['rank'] == match._get_player_rank(local)
        assert params['score'] == match.scores_liste[local]
        assert 'riot_id = EXCLUDED.riot_id' in query
        assert 'team = EXCLUDED.team' in query


def test_early_first_tower_with_minion_kill_does_not_credit_later_tower(modules):
    match = match_fixture(modules)
    frame = match.data_timeline['info']['frames'][0]
    frame['events'].insert(0, {'type':'BUILDING_KILL','buildingType':'TOWER_BUILDING',
                               'killerId':0,'assistingParticipantIds':[2]})
    calculate(match)
    assert not by_id(match)[6].has_first_tower
    assert by_id(match)[2].has_first_tower_assist


def test_missing_role_does_not_invent_a_lane_opponent(modules):
    match = match_fixture(modules)
    for p in match.match_detail['info']['participants']:
        p['teamPosition'] = ''
    calculate(match)
    assert all(m.opponent_index is None for m in match.player_metrics_liste)


def test_late_solo_kills_stay_in_records_without_boosting_early_tempo(modules):
    match = match_fixture(modules)
    match.data_timeline['info']['frames'][0]['events'].append(
        {'type':'CHAMPION_KILL','killerId':6,'timestamp':1200000,'assistingParticipantIds':[]})
    calculate(match)
    assert by_id(match)[6].solo_kills == 2
    assert by_id(match)[6].early_solo_kills == 1


def test_extreme_profile_weights_still_produce_finite_scores(modules):
    _, profiles, _, _ = modules
    for adj in profiles._PROFILE_ADJUSTMENTS_CACHE.values():
        for name in ('combat_weight_adj','economic_weight_adj','objective_weight_adj','tempo_weight_adj','impact_weight_adj'):
            setattr(adj, name, -100)
    match = calculate(match_fixture(modules))
    assert all(1 <= m.performance_score <= 10 for m in match.player_metrics_liste)
