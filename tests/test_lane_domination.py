import importlib.util
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "fonctions"
    / "match"
    / "lane_domination.py"
)
SPEC = importlib.util.spec_from_file_location("lane_domination_under_test", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

calculate_lane_domination_score = MODULE.calculate_lane_domination_score
lane_domination_label = MODULE.lane_domination_label


def test_even_lane_starts_at_neutral_50():
    assert calculate_lane_domination_score(0, 0, 0, 0, 0) == 50.0
    assert lane_domination_label(50) == "Lane équilibrée"


def test_strong_lane_is_capped_at_100():
    score = calculate_lane_domination_score(
        gold_diff_15=2500,
        cs_diff_15=60,
        cs_max_advantage=100,
        level_max_advantage=4,
        solo_kills=5,
    )
    assert score == 100.0
    assert lane_domination_label(score) == "Domination totale"


def test_large_15_min_deficit_cannot_be_hidden_by_small_bonus():
    score = calculate_lane_domination_score(
        gold_diff_15=-1500,
        cs_diff_15=-25,
        cs_max_advantage=10,
        level_max_advantage=1,
        solo_kills=1,
    )
    assert score < 30
    assert lane_domination_label(score) == "Lane dominée"


def test_invalid_or_missing_values_are_safe():
    assert calculate_lane_domination_score(None, "bad", None, None, None) == 50.0
