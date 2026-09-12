import unittest
from datetime import datetime, timezone

from fonctions.fantasy.draft import draft_turns, snake_order
from fonctions.fantasy.locks import ScheduledMatch, locked_competitions
from fonctions.fantasy.matchups import round_robin
from fonctions.fantasy.models import (
    Competition,
    PlayerAsset,
    PlayerRole,
    RosterEntry,
    RosterSlot,
    TeamAsset,
)
from fonctions.fantasy.roster import (
    RosterValidationError,
    choose_initial_roster,
    validate_final_roster,
)
from fonctions.fantasy.scoring import (
    PlayerGameStats,
    TeamGameStats,
    score_player,
    score_team,
)


class DraftTests(unittest.TestCase):
    def test_four_manager_snake(self):
        self.assertEqual(
            snake_order([1, 2, 3, 4], rounds=2),
            [1, 2, 3, 4, 4, 3, 2, 1],
        )

    def test_odd_manager_snake(self):
        self.assertEqual(
            snake_order([1, 2, 3, 4, 5], rounds=2),
            [1, 2, 3, 4, 5, 5, 4, 3, 2, 1],
        )

    def test_nine_rounds_give_nine_picks_per_manager(self):
        turns = draft_turns([10, 20, 30, 40, 50])
        for manager_id in [10, 20, 30, 40, 50]:
            self.assertEqual(
                sum(turn.manager_id == manager_id for turn in turns),
                9,
            )


class RosterTests(unittest.TestCase):
    @staticmethod
    def _player(player_id, role, competition):
        return PlayerAsset(
            player_id=player_id,
            handle=f"P{player_id}",
            role=role,
            competition=competition,
        )

    def _valid_roster(self):
        return [
            RosterEntry(RosterSlot.TOP, player=self._player(1, PlayerRole.TOP, Competition.LEC)),
            RosterEntry(RosterSlot.JUNGLE, player=self._player(2, PlayerRole.JUNGLE, Competition.LEC)),
            RosterEntry(RosterSlot.MID, player=self._player(3, PlayerRole.MID, Competition.LFL)),
            RosterEntry(RosterSlot.ADC, player=self._player(4, PlayerRole.ADC, Competition.LEC)),
            RosterEntry(RosterSlot.SUPPORT, player=self._player(5, PlayerRole.SUPPORT, Competition.LEC)),
            RosterEntry(RosterSlot.BENCH, player=self._player(6, PlayerRole.TOP, Competition.LCS)),
            RosterEntry(RosterSlot.BENCH, player=self._player(7, PlayerRole.MID, Competition.LEC)),
            RosterEntry(RosterSlot.BENCH, player=self._player(8, PlayerRole.ADC, Competition.LFL)),
            RosterEntry(
                RosterSlot.TEAM,
                team=TeamAsset(1, "G2", Competition.LEC),
            ),
        ]

    def test_valid_roster(self):
        validate_final_roster(self._valid_roster())

    def test_starters_must_use_two_competitions(self):
        roster = self._valid_roster()
        roster[2] = RosterEntry(
            RosterSlot.MID,
            player=self._player(30, PlayerRole.MID, Competition.LEC),
        )
        with self.assertRaises(RosterValidationError):
            validate_final_roster(roster)

    def test_starter_role_must_match_slot(self):
        roster = self._valid_roster()
        roster[0] = RosterEntry(
            RosterSlot.TOP,
            player=self._player(40, PlayerRole.MID, Competition.LFL),
        )
        with self.assertRaises(RosterValidationError):
            validate_final_roster(roster)

    def test_initial_roster_can_promote_second_competition_from_bench_pool(self):
        players = [
            self._player(1, PlayerRole.TOP, Competition.LEC),
            self._player(2, PlayerRole.JUNGLE, Competition.LEC),
            self._player(3, PlayerRole.MID, Competition.LEC),
            self._player(4, PlayerRole.ADC, Competition.LEC),
            self._player(5, PlayerRole.SUPPORT, Competition.LEC),
            self._player(6, PlayerRole.MID, Competition.LFL),
            self._player(7, PlayerRole.TOP, Competition.LEC),
            self._player(8, PlayerRole.ADC, Competition.LEC),
        ]
        roster = choose_initial_roster(
            players,
            TeamAsset(1, "G2", Competition.LEC),
        )
        validate_final_roster(roster)
        starters = [entry.player for entry in roster if entry.slot in {
            RosterSlot.TOP,
            RosterSlot.JUNGLE,
            RosterSlot.MID,
            RosterSlot.ADC,
            RosterSlot.SUPPORT,
        }]
        self.assertIn(Competition.LFL, {player.competition for player in starters})

    def test_initial_roster_rejects_single_competition_player_pool(self):
        players = [
            self._player(1, PlayerRole.TOP, Competition.LEC),
            self._player(2, PlayerRole.JUNGLE, Competition.LEC),
            self._player(3, PlayerRole.MID, Competition.LEC),
            self._player(4, PlayerRole.ADC, Competition.LEC),
            self._player(5, PlayerRole.SUPPORT, Competition.LEC),
            self._player(6, PlayerRole.MID, Competition.LEC),
            self._player(7, PlayerRole.TOP, Competition.LEC),
            self._player(8, PlayerRole.ADC, Competition.LEC),
        ]
        with self.assertRaises(RosterValidationError):
            choose_initial_roster(players, TeamAsset(1, "G2", Competition.LEC))


class LockTests(unittest.TestCase):
    def test_only_competition_playing_today_is_locked(self):
        now = datetime(2026, 7, 25, 12, 0, tzinfo=timezone.utc)
        matches = [
            ScheduledMatch(
                Competition.LEC,
                datetime(2026, 7, 25, 18, 0, tzinfo=timezone.utc),
            ),
            ScheduledMatch(
                Competition.LCS,
                datetime(2026, 7, 26, 18, 0, tzinfo=timezone.utc),
            ),
        ]
        self.assertEqual(locked_competitions(matches, now=now), {Competition.LEC})

    def test_paris_date_is_used_for_late_utc_match(self):
        now = datetime(2026, 7, 26, 0, 30, tzinfo=timezone.utc)
        matches = [
            ScheduledMatch(
                Competition.LCS,
                datetime(2026, 7, 25, 23, 30, tzinfo=timezone.utc),
            )
        ]
        self.assertEqual(locked_competitions(matches, now=now), {Competition.LCS})


class MatchupTests(unittest.TestCase):
    def test_even_round_robin_contains_each_pair_once(self):
        rounds = round_robin([1, 2, 3, 4])
        pairs = {
            frozenset((match.manager1_id, match.manager2_id))
            for round_matches in rounds
            for match in round_matches
            if not match.is_bye
        }
        self.assertEqual(len(rounds), 3)
        self.assertEqual(len(pairs), 6)

    def test_odd_round_robin_gives_one_bye_each(self):
        rounds = round_robin([1, 2, 3, 4, 5])
        bye_managers = [
            match.bye_manager_id
            for round_matches in rounds
            for match in round_matches
            if match.is_bye
        ]
        self.assertEqual(len(rounds), 5)
        self.assertCountEqual(bye_managers, [1, 2, 3, 4, 5])


class ScoringTests(unittest.TestCase):
    def test_player_scoring(self):
        stats = PlayerGameStats(kills=10, deaths=2, assists=12, cs=250, triple_kills=1)
        self.assertEqual(score_player(stats), 43.5)

    def test_team_scoring_with_fast_win(self):
        stats = TeamGameStats(
            won=True,
            barons=1,
            dragons=3,
            towers=8,
            first_blood=True,
            duration_seconds=1700,
        )
        self.assertEqual(score_team(stats), 19.0)


if __name__ == "__main__":
    unittest.main()
