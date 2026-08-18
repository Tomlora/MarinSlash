import importlib.util
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "fonctions"
    / "match"
    / "teamfight_damage.py"
)
SPEC = importlib.util.spec_from_file_location("teamfight_damage_under_test", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
calculate_teamfight_damage = MODULE.calculate_teamfight_damage


def _participants():
    return [
        {
            "participantId": pid,
            "teamId": 100 if pid <= 5 else 200,
            "championName": f"C{pid}",
            "riotIdGameName": f"P{pid}",
            "puuid": f"u{pid}",
        }
        for pid in range(1, 11)
    ]


def _frame(timestamp, events, damage_after=False):
    participant_frames = {}
    for pid in range(1, 11):
        base = pid * 10
        participant_frames[str(pid)] = {
            "position": {"x": 1000 + pid * 1000, "y": 1000 + pid * 700},
            "damageStats": {
                "totalDamageDoneToChampions": base + (1000 if damage_after else 0),
                "physicalDamageDoneToChampions": base + (600 if damage_after else 0),
                "magicDamageDoneToChampions": base + (300 if damage_after else 0),
                "trueDamageDoneToChampions": base + (100 if damage_after else 0),
            },
        }
    return {
        "timestamp": timestamp,
        "participantFrames": participant_frames,
        "events": events,
    }


def test_detects_1v2_from_victim_damage_source():
    event = {
        "type": "CHAMPION_KILL",
        "timestamp": 610_000,
        "killerId": 6,
        "victimId": 4,
        "assistingParticipantIds": [],
        "position": {"x": 8000, "y": 3000},
        "victimDamageReceived": [
            {
                "participantId": 6,
                "physicalDamage": 1182,
                "magicDamage": 0,
                "trueDamage": 0,
            },
            {
                "participantId": 7,
                "physicalDamage": 0,
                "magicDamage": 439,
                "trueDamage": 0,
            },
        ],
    }
    timeline = {
        "info": {
            "frames": [
                _frame(600_000, [event]),
                _frame(660_000, [], damage_after=True),
            ]
        }
    }
    match = {"info": {"participants": _participants()}}

    fights = calculate_teamfight_damage(match, timeline, allied_team_id=100)

    assert len(fights) == 1
    fight = fights[0]
    assert fight["fight_type"] == "1v2"
    assert fight["fight_category"] == "outnumbered"
    assert fight["core_allies"] == 1
    assert fight["core_enemies"] == 2
    assert fight["outnumbered_team"] == "Allié"

    damage_only = next(player for player in fight["players"] if player["participant_id"] == 7)
    assert damage_only["participation_source"] == "damage"
    assert damage_only["was_damage_source"] is True
    assert damage_only["fight_assists"] == 0
    assert damage_only["damage_on_dead_targets"] == 439
    assert damage_only["damage_window_estimated"] == 1000
    assert damage_only["physical_damage_window_estimated"] == 600
    assert damage_only["magic_damage_window_estimated"] == 300
    assert damage_only["true_damage_window_estimated"] == 100


def test_duel_exposes_winner_and_core_players():
    event = {
        "type": "CHAMPION_KILL",
        "timestamp": 610_000,
        "killerId": 1,
        "victimId": 6,
        "assistingParticipantIds": [],
        "position": {"x": 3000, "y": 2000},
        "victimDamageReceived": [
            {
                "participantId": 1,
                "physicalDamage": 500,
                "magicDamage": 0,
                "trueDamage": 0,
            }
        ],
    }
    timeline = {
        "info": {
            "frames": [
                _frame(600_000, [event]),
                _frame(660_000, [], damage_after=True),
            ]
        }
    }
    match = {"info": {"participants": _participants()}}

    fights = calculate_teamfight_damage(match, timeline, allied_team_id=100)

    assert len(fights) == 1
    fight = fights[0]
    assert fight["fight_type"] == "1v1"
    assert fight["fight_category"] == "duel"
    assert fight["winner"] == "Allié"

    killer = next(player for player in fight["players"] if player["participant_id"] == 1)
    victim = next(player for player in fight["players"] if player["participant_id"] == 6)
    assert killer["is_core_participant"] is True
    assert killer["team"] == fight["winner"]
    assert victim["is_core_participant"] is True
    assert victim["team"] != fight["winner"]


def test_marks_damage_window_shared_between_distinct_fights():
    first = {
        "type": "CHAMPION_KILL",
        "timestamp": 610_000,
        "killerId": 6,
        "victimId": 4,
        "assistingParticipantIds": [],
        "position": {"x": 8000, "y": 3000},
        "victimDamageReceived": [],
    }
    second = {
        "type": "CHAMPION_KILL",
        "timestamp": 630_500,
        "killerId": 1,
        "victimId": 7,
        "assistingParticipantIds": [],
        "position": {"x": 8000, "y": 3000},
        "victimDamageReceived": [],
    }
    timeline = {
        "info": {
            "frames": [
                _frame(600_000, [first, second]),
                _frame(660_000, [], damage_after=True),
            ]
        }
    }
    match = {"info": {"participants": _participants()}}

    fights = calculate_teamfight_damage(match, timeline, allied_team_id=100)

    assert len(fights) == 2
    assert all(fight["shared_damage_window"] for fight in fights)
    assert all(fight["shared_window_fight_count"] == 2 for fight in fights)
