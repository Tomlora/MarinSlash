import importlib.util
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "fonctions"
    / "match"
    / "gank_laning_rules.py"
)
SPEC = importlib.util.spec_from_file_location("gank_laning_rules_under_test", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

is_laning_gank_timestamp = MODULE.is_laning_gank_timestamp
is_strict_gank_success = MODULE.is_strict_gank_success
GANK_WINDOW_END_MS = MODULE.GANK_WINDOW_END_MS


def test_gank_window_stops_exactly_at_fourteen_minutes():
    assert is_laning_gank_timestamp(0)
    assert is_laning_gank_timestamp(GANK_WINDOW_END_MS - 1)
    assert not is_laning_gank_timestamp(GANK_WINDOW_END_MS)
    assert not is_laning_gank_timestamp(GANK_WINDOW_END_MS + 1)


def test_negative_or_invalid_timestamps_are_rejected():
    assert not is_laning_gank_timestamp(-1)
    assert not is_laning_gank_timestamp(None)
    assert not is_laning_gank_timestamp("invalid")


def test_only_clean_success_counts_as_success():
    assert is_strict_gank_success("success")
    assert not is_strict_gank_success("trade")
    assert not is_strict_gank_success("failed")
    assert not is_strict_gank_success("jungler_death")
