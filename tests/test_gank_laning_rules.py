import importlib.util
from dataclasses import dataclass
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
apply_laning_gank_rules = MODULE.apply_laning_gank_rules
strict_detection_counts = MODULE.strict_detection_counts
GANK_WINDOW_END_MS = MODULE.GANK_WINDOW_END_MS


@dataclass
class _Lane:
    value: str


@dataclass
class _Event:
    timestamp: int
    lane: _Lane
    outcome: str
    successful: bool
    detection_source: str = "exact_event"
    confidence: float = 1.0
    gank_id: int = 0


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


def test_apply_rules_filters_post_14_and_reclassifies_trade():
    lane = _Lane("top")
    events = [
        _Event(5 * 60 * 1000, lane, "success", True),
        _Event(8 * 60 * 1000, lane, "trade", True),
        _Event(14 * 60 * 1000, lane, "success", True),
    ]
    filtered = apply_laning_gank_rules(events)
    assert len(filtered) == 2
    assert filtered[0].successful is True
    assert filtered[1].successful is False
    assert [event.gank_id for event in filtered] == [1, 2]


def test_trade_is_neither_success_nor_failed_detection():
    lane = _Lane("mid")
    events = [
        _Event(4 * 60 * 1000, lane, "trade", False),
        _Event(7 * 60 * 1000, lane, "failed", False, "inferred_combat", 0.7),
    ]
    counts = strict_detection_counts(events)
    assert counts["exact"] == 1
    assert counts["inferred"] == 1
    assert counts["failed"] == 1
