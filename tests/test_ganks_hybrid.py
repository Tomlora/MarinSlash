import importlib.util
import sys
import types
from pathlib import Path


MODULE_DIR = Path(__file__).resolve().parents[1] / "fonctions" / "match"
PACKAGE_NAME = "ganks_hybrid_test_pkg"


def _load_modules():
    # ganks.py importe uniquement ces fonctions BDD au chargement. Les neutraliser
    # permet de tester l'algorithme sans ouvrir de connexion PostgreSQL.
    old_fonctions = sys.modules.get("fonctions")
    old_gestion_bdd = sys.modules.get("fonctions.gestion_bdd")

    fake_fonctions = types.ModuleType("fonctions")
    fake_fonctions.__path__ = []
    fake_bdd = types.ModuleType("fonctions.gestion_bdd")
    fake_bdd.lire_bdd_perso = lambda *args, **kwargs: []
    fake_bdd.requete_perso_bdd = lambda *args, **kwargs: None

    sys.modules["fonctions"] = fake_fonctions
    sys.modules["fonctions.gestion_bdd"] = fake_bdd

    package = types.ModuleType(PACKAGE_NAME)
    package.__path__ = [str(MODULE_DIR)]
    sys.modules[PACKAGE_NAME] = package

    try:
        legacy_spec = importlib.util.spec_from_file_location(
            f"{PACKAGE_NAME}.ganks",
            MODULE_DIR / "ganks.py",
        )
        assert legacy_spec and legacy_spec.loader
        legacy = importlib.util.module_from_spec(legacy_spec)
        sys.modules[legacy_spec.name] = legacy
        legacy_spec.loader.exec_module(legacy)

        hybrid_spec = importlib.util.spec_from_file_location(
            f"{PACKAGE_NAME}.ganks_hybrid",
            MODULE_DIR / "ganks_hybrid.py",
        )
        assert hybrid_spec and hybrid_spec.loader
        hybrid = importlib.util.module_from_spec(hybrid_spec)
        sys.modules[hybrid_spec.name] = hybrid
        hybrid_spec.loader.exec_module(hybrid)
        return legacy, hybrid
    finally:
        if old_fonctions is None:
            sys.modules.pop("fonctions", None)
        else:
            sys.modules["fonctions"] = old_fonctions

        if old_gestion_bdd is None:
            sys.modules.pop("fonctions.gestion_bdd", None)
        else:
            sys.modules["fonctions.gestion_bdd"] = old_gestion_bdd


LEGACY, HYBRID = _load_modules()
Lane = LEGACY.Lane
HybridGankAnalysisMixin = HYBRID.HybridGankAnalysisMixin

TOP_POS = {"x": 2000, "y": 12000}
MID_POS = {"x": 7500, "y": 7500}
BOT_POS = {"x": 12000, "y": 2500}
JUNGLE_POS = {"x": 6000, "y": 9500}


def _participants():
    roles = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"] * 2
    return [
        {
            "participantId": participant_id,
            "teamId": 100 if participant_id <= 5 else 200,
            "teamPosition": roles[participant_id - 1],
            "championName": f"C{participant_id}",
            "summonerName": f"P{participant_id}",
        }
        for participant_id in range(1, 11)
    ]


def _frame(timestamp, events=None, damage=None, allied_jungle_position=None):
    damage = damage or {}
    participant_frames = {}

    for participant_id in range(1, 11):
        if participant_id in (1, 6):
            position = TOP_POS
        elif participant_id in (3, 8):
            position = MID_POS
        elif participant_id in (4, 5, 9, 10):
            position = BOT_POS
        else:
            position = JUNGLE_POS

        if participant_id == 2 and allied_jungle_position is not None:
            position = allied_jungle_position

        participant_frames[str(participant_id)] = {
            "position": dict(position),
            "damageStats": {
                "totalDamageDoneToChampions": damage.get(participant_id, 0)
            },
        }

    return {
        "timestamp": timestamp,
        "participantFrames": participant_frames,
        "events": events or [],
    }


def _kill(timestamp, killer, victim, assists=None, position=None):
    return {
        "type": "CHAMPION_KILL",
        "timestamp": timestamp,
        "killerId": killer,
        "victimId": victim,
        "assistingParticipantIds": assists or [],
        "position": position or TOP_POS,
        "victimDamageReceived": [],
    }


def _analyzer(frames):
    analyzer = HybridGankAnalysisMixin()
    analyzer.match_detail = {"info": {"participants": _participants()}}
    analyzer.data_timeline = {"info": {"frames": frames}}
    analyzer.thisId = 0
    analyzer.last_match = "TEST"
    return analyzer


def test_groups_two_kills_into_one_exact_gank_episode():
    first = _kill(250_000, killer=1, victim=6, assists=[2])
    second = _kill(262_000, killer=2, victim=9, assists=[1])
    analyzer = _analyzer([_frame(240_000, [first, second]), _frame(300_000)])

    ganks = analyzer._collect_exact_ganks(2, 100, 7)

    assert len(ganks) == 1
    gank = ganks[0]
    assert gank.lane == Lane.TOP
    assert gank.start_ms == 250_000
    assert gank.end_ms == 262_000
    assert gank.kills_for == 2
    assert gank.kills_against == 0
    assert gank.outcome == "success"
    assert gank.successful is True
    assert gank.detection_source == "exact_event"


def test_jungler_death_on_lane_is_observed_as_failed_attempt():
    death = _kill(250_000, killer=6, victim=2)
    analyzer = _analyzer([_frame(240_000, [death]), _frame(300_000)])

    ganks = analyzer._collect_exact_ganks(2, 100, 7)

    assert len(ganks) == 1
    gank = ganks[0]
    assert gank.successful is False
    assert gank.outcome == "jungler_death"
    assert gank.jungler_deaths == 1


def test_infers_failed_gank_even_when_jungler_is_in_jungle_on_both_frames():
    before = _frame(240_000)
    after = _frame(
        300_000,
        damage={
            1: 500,
            2: 350,
            6: 450,
            3: 50,
            8: 50,
            4: 40,
            5: 40,
            9: 40,
            10: 40,
        },
    )
    analyzer = _analyzer([before, after])

    ganks = analyzer._infer_failed_ganks(2, 100, [])

    assert len(ganks) == 1
    gank = ganks[0]
    assert gank.lane == Lane.TOP
    assert gank.successful is False
    assert gank.outcome == "failed"
    assert gank.detection_source == "inferred_combat"
    assert gank.position_evidence == "none"
    assert gank.confidence >= 0.70
    assert gank.jungler_damage_delta == 350


def test_three_v_three_lane_fight_is_not_counted_as_gank():
    allied_kill = _kill(250_000, killer=1, victim=6, assists=[2, 3])
    enemy_kill = _kill(260_000, killer=7, victim=1, assists=[6, 8])
    analyzer = _analyzer(
        [_frame(240_000, [allied_kill, enemy_kill]), _frame(300_000)]
    )

    assert analyzer._collect_exact_ganks(2, 100, 7) == []


def test_installer_replaces_detection_without_rewriting_matchlol_class():
    class DummyMatch(LEGACY.GankAnalysisMixin):
        pass

    HYBRID.install_hybrid_ganks(DummyMatch)

    assert DummyMatch.analyze_ganks is HYBRID.HybridGankAnalysisMixin.analyze_ganks
    assert DummyMatch.MIN_JUNGLER_DAMAGE_DELTA == 120
