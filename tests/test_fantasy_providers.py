import csv
import os
import tempfile
import unittest
from datetime import datetime, timezone

from fonctions.fantasy.models import Competition
from fonctions.fantasy.providers.base import ProviderMatch, ScheduleProvider
from fonctions.fantasy.providers.oracles_elixir import OracleElixirPlayerProvider
from fonctions.fantasy.providers.schedule import FallbackScheduleProvider


class OracleElixirProviderTests(unittest.TestCase):
    def test_parse_uses_recent_player_appearances(self):
        fd, path = tempfile.mkstemp(suffix=".csv")
        os.close(fd)
        try:
            with open(path, "w", encoding="utf-8", newline="") as output:
                writer = csv.DictWriter(
                    output,
                    fieldnames=[
                        "league",
                        "date",
                        "position",
                        "playername",
                        "playerid",
                        "teamname",
                        "teamid",
                    ],
                )
                writer.writeheader()
                writer.writerows(
                    [
                        {
                            "league": "LEC",
                            "date": "2026-07-20 18:00:00",
                            "position": "mid",
                            "playername": "CurrentMid",
                            "playerid": "p-current",
                            "teamname": "Example Team",
                            "teamid": "team-1",
                        },
                        {
                            "league": "LEC",
                            "date": "2026-06-01 18:00:00",
                            "position": "mid",
                            "playername": "OldMid",
                            "playerid": "p-old",
                            "teamname": "Example Team",
                            "teamid": "team-1",
                        },
                    ]
                )

            teams, players = OracleElixirPlayerProvider._parse_file(
                path, (Competition.LEC,)
            )
            self.assertEqual(len(teams), 1)
            self.assertEqual([player.handle for player in players], ["CurrentMid"])
            self.assertEqual(players[0].team_external_id, "team-1")
        finally:
            os.remove(path)

    def test_latest_appearance_moves_player_to_new_team(self):
        fd, path = tempfile.mkstemp(suffix=".csv")
        os.close(fd)
        try:
            with open(path, "w", encoding="utf-8", newline="") as output:
                writer = csv.DictWriter(
                    output,
                    fieldnames=[
                        "league",
                        "date",
                        "position",
                        "playername",
                        "playerid",
                        "teamname",
                        "teamid",
                    ],
                )
                writer.writeheader()
                writer.writerows(
                    [
                        {
                            "league": "LFL",
                            "date": "2026-07-01 18:00:00",
                            "position": "jng",
                            "playername": "Jungler",
                            "playerid": "p1",
                            "teamname": "Old Team",
                            "teamid": "old-team",
                        },
                        {
                            "league": "LFL",
                            "date": "2026-07-20 18:00:00",
                            "position": "jng",
                            "playername": "Jungler",
                            "playerid": "p1",
                            "teamname": "New Team",
                            "teamid": "new-team",
                        },
                    ]
                )

            _, players = OracleElixirPlayerProvider._parse_file(
                path, (Competition.LFL,)
            )
            self.assertEqual(len(players), 1)
            self.assertEqual(players[0].team_external_id, "new-team")
        finally:
            os.remove(path)


class _FailingScheduleProvider(ScheduleProvider):
    async def fetch_schedule(self, competitions, start, end):
        raise RuntimeError("ratelimited")


class _WorkingScheduleProvider(ScheduleProvider):
    async def fetch_schedule(self, competitions, start, end):
        return [
            ProviderMatch(
                external_id="match-1",
                competition=Competition.LEC,
                tournament="LEC",
                scheduled_at_utc=datetime(2026, 7, 30, 18, 0, tzinfo=timezone.utc),
                team1_external_id="G2 Esports",
                team2_external_id="Fnatic",
            )
        ]


class ScheduleFallbackTests(unittest.IsolatedAsyncioTestCase):
    async def test_second_provider_is_used_when_primary_fails(self):
        provider = FallbackScheduleProvider(
            _FailingScheduleProvider(),
            _WorkingScheduleProvider(),
        )
        matches = await provider.fetch_schedule(
            (Competition.LEC,),
            datetime(2026, 7, 29, tzinfo=timezone.utc),
            datetime(2026, 8, 5, tzinfo=timezone.utc),
        )
        self.assertEqual(len(matches), 1)
        self.assertEqual(provider.last_provider_name, "_WorkingScheduleProvider")
        self.assertEqual(len(provider.errors), 1)


if __name__ == "__main__":
    unittest.main()
