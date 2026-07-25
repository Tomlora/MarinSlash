import importlib.util
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "fonctions"
    / "match"
    / "teamfight_time.py"
)
SPEC = importlib.util.spec_from_file_location("teamfight_time_under_test", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
timestamp_ms_to_mmss_decimal = MODULE.timestamp_ms_to_mmss_decimal


def test_timestamp_is_encoded_as_mmss_not_decimal_minutes():
    # 10 min 58 s : l'ancien calcul donnait round(658000 / 60000, 2) = 10.97.
    assert timestamp_ms_to_mmss_decimal(658_000) == 10.58


def test_seconds_are_truncated_from_milliseconds():
    assert timestamp_ms_to_mmss_decimal(658_999) == 10.58
    assert timestamp_ms_to_mmss_decimal(659_000) == 10.59


def test_minute_rollover_and_leading_second_zero():
    assert timestamp_ms_to_mmss_decimal(660_000) == 11.0
    assert timestamp_ms_to_mmss_decimal(605_000) == 10.05
