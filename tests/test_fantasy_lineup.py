import unittest
from datetime import datetime, timezone

from fonctions.fantasy.locks import ScheduledMatch, locked_competitions
from fonctions.fantasy.models import Competition, PlayerAsset, PlayerRole, RosterEntry, RosterSlot, TeamAsset
from fonctions.fantasy.roster import RosterValidationError, choose_initial_roster, promote_bench_player


def roster():
    players = [PlayerAsset(i, f"Player{i}", role, Competition.LFL if i == 3 else Competition.LEC)
               for i, role in enumerate(PlayerRole, 1)]
    players.extend([PlayerAsset(6, "BenchTop", PlayerRole.TOP, Competition.LCS),
                    PlayerAsset(7, "BenchMid", PlayerRole.MID, Competition.LEC),
                    PlayerAsset(8, "BenchADC", PlayerRole.ADC, Competition.LFL)])
    return choose_initial_roster(players, TeamAsset(1, "Team", Competition.LEC))


class LineupRulesTests(unittest.TestCase):
    def test_swap_preserves_ownership_and_original(self):
        original = roster()
        updated = promote_bench_player(original, 6)
        self.assertEqual(next(e.slot for e in updated if e.player and e.player.player_id == 6), RosterSlot.TOP)
        self.assertEqual(next(e.slot for e in updated if e.player and e.player.player_id == 1), RosterSlot.BENCH)
        self.assertEqual(next(e.slot for e in original if e.player and e.player.player_id == 6), RosterSlot.BENCH)
        self.assertCountEqual([e.player for e in original], [e.player for e in updated])
        self.assertEqual(original[-1], updated[-1])

    def test_unknown_and_already_starting_players_rejected(self):
        for player_id in (99, 1):
            with self.subTest(player_id=player_id), self.assertRaises(RosterValidationError):
                promote_bench_player(roster(), player_id)

    def test_incoming_and_outgoing_competition_locks(self):
        for competition in (Competition.LEC, Competition.LCS):
            with self.subTest(competition=competition), self.assertRaisesRegex(RosterValidationError, "verrouillé"):
                promote_bench_player(roster(), 6, {competition})
        promote_bench_player(roster(), 6, {Competition.LFL})

    def test_cannot_remove_only_second_competition(self):
        with self.assertRaisesRegex(RosterValidationError, "deux championnats"):
            promote_bench_player(roster(), 7)

    def test_paris_midnight_and_cancelled_match(self):
        match = ScheduledMatch(Competition.LEC, datetime(2026, 7, 26, 18, tzinfo=timezone.utc))
        before = datetime(2026, 7, 25, 21, 59, tzinfo=timezone.utc)
        after = datetime(2026, 7, 25, 22, 0, tzinfo=timezone.utc)
        self.assertEqual(locked_competitions([match], before), set())
        self.assertEqual(locked_competitions([match], after), {Competition.LEC})
        for status in ("cancelled", "postponed"):
            self.assertEqual(locked_competitions([ScheduledMatch(match.competition, match.scheduled_at, status)], after), set())


if __name__ == "__main__":
    unittest.main()
