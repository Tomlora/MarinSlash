import importlib.util
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "fonctions"
    / "match"
    / "gank_recap.py"
)
SPEC = importlib.util.spec_from_file_location("gank_recap_under_test", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

build_gank_pressure_insight = MODULE.build_gank_pressure_insight


def _stats(ally, enemy):
    return {
        "by_lane": {
            lane: {
                "ganks_made": ally[index],
                "ganks_received": enemy[index],
            }
            for index, lane in enumerate(("top", "mid", "bot"))
        }
    }


def test_no_recap_for_single_attempt():
    assert build_gank_pressure_insight(_stats((1, 0, 0), (0, 0, 0))) == ""


def test_no_recap_when_top_focus_is_tied():
    assert build_gank_pressure_insight(_stats((2, 2, 0), (0, 0, 0))) == ""


def test_clear_ally_focus_is_displayed():
    insight = build_gank_pressure_insight(_stats((1, 0, 3), (1, 1, 0)))
    assert "Jungle alliée" in insight
    assert "BOT" in insight
    assert "3/4" in insight
    assert "Jungle ennemie" not in insight


def test_both_clear_focuses_are_displayed():
    insight = build_gank_pressure_insight(_stats((3, 1, 0), (0, 1, 3)))
    assert "Jungle alliée" in insight
    assert "TOP" in insight
    assert "Jungle ennemie" in insight
    assert "BOT" in insight


def test_recap_ignores_events_at_or_after_fourteen_minutes():
    stats = _stats((3, 0, 0), (0, 0, 0))
    stats["events"] = {
        "ally": [
            {"timestamp": 5 * 60 * 1000, "lane": "top"},
            {"timestamp": 14 * 60 * 1000, "lane": "top"},
            {"timestamp": 18 * 60 * 1000, "lane": "top"},
        ],
        "enemy": [],
    }
    # by_lane prétend 3 ganks TOP, mais seul celui à 5:00 est éligible :
    # l'insight doit donc rester vide (minimum 2 tentatives).
    assert build_gank_pressure_insight(stats) == ""


def test_recap_uses_only_pre_fourteen_events_for_focus_share():
    stats = _stats((0, 0, 0), (0, 0, 0))
    stats["events"] = {
        "ally": [
            {"timestamp": 4 * 60 * 1000, "lane": "bot"},
            {"timestamp": 9 * 60 * 1000, "lane": "bot"},
            {"timestamp": 16 * 60 * 1000, "lane": "mid"},
        ],
        "enemy": [],
    }
    insight = build_gank_pressure_insight(stats)
    assert "Jungle alliée" in insight
    assert "BOT" in insight
    assert "2/2" in insight
