from fonctions.match.teamfight_damage import calculate_teamfight_damage


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
        participant_frames[str(pid)] = {
            "position": {"x": 1000 + pid * 1000, "y": 1000 + pid * 700},
            "damageStats": {
                "totalDamageDoneToChampions": (
                    (1000 if damage_after else 0) + pid * 10
                )
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
