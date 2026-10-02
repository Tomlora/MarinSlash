"""Integration tests require an isolated PostgreSQL database named marin_fantasy_test."""
import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine, text

from fonctions.fantasy.lineup import get_lineup, set_starter
from fonctions.fantasy.service import FantasyServiceError
from test_fantasy_lineup import roster


@unittest.skipUnless(os.environ.get("FANTASY_TEST_DSN"), "Set FANTASY_TEST_DSN to a disposable PostgreSQL database")
class LineupDatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(os.environ["FANTASY_TEST_DSN"])
        with cls.engine.connect() as connection:
            if connection.execute(text("SELECT current_database()")).scalar_one() != "marin_fantasy_test":
                raise RuntimeError("Refusing to reset a database not named marin_fantasy_test")
        raw = cls.engine.raw_connection()
        try:
            cursor = raw.cursor()
            cursor.execute("DROP SCHEMA IF EXISTS fantasy CASCADE")
            cursor.execute((Path(__file__).parents[1] / "sql/migrations/20260725_fantasy_initial.sql").read_text())
            raw.commit()
        finally:
            raw.close()

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()

    def setUp(self):
        self.addCleanup(patch.stopall)
        patch("fonctions.fantasy.lineup.transaction", self.engine.begin).start()
        with self.engine.begin() as c:
            c.execute(text("""
                TRUNCATE fantasy.league, fantasy.pro_team, fantasy.pro_player,
                         fantasy.match_schedule RESTART IDENTITY CASCADE
            """))
            c.execute(text("""
                INSERT INTO fantasy.league (guild_id, name, owner_discord_id, status)
                VALUES (10, 'Test League', 20, 'active');
                INSERT INTO fantasy.season (league_id, name) VALUES (1, 'Season');
                INSERT INTO fantasy.manager (league_id, discord_user_id) VALUES (1, 20), (1, 21);
                INSERT INTO fantasy.pro_team (competition_code, external_id, name)
                VALUES ('LEC', 'lec', 'LEC Team'), ('LCS', 'lcs', 'LCS Team'), ('LFL', 'lfl', 'LFL Team');
            """))
            for entry in roster():
                if entry.player:
                    player = entry.player
                    c.execute(text("""
                        INSERT INTO fantasy.pro_player (id, external_id, handle, role)
                        VALUES (:id, :external, :handle, :role);
                        INSERT INTO fantasy.pro_player_team_history (player_id, team_id, valid_from)
                        VALUES (:id, :team, NOW() - INTERVAL '1 day');
                    """), {"id": player.player_id, "external": str(player.player_id),
                           "handle": player.handle, "role": player.role.value,
                           "team": {"LEC": 1, "LCS": 2, "LFL": 3}[player.competition.value]})
                params = {"player": entry.player.player_id if entry.player else None,
                          "team": entry.team.team_id if entry.team else None, "slot": entry.slot.value}
                c.execute(text("""
                    INSERT INTO fantasy.roster_asset (season_id, manager_id, player_id, team_id, slot)
                    VALUES (1, 1, :player, :team, :slot);
                    INSERT INTO fantasy.roster_history
                        (season_id, manager_id, player_id, team_id, slot, valid_from, reason)
                    VALUES (1, 1, :player, :team, :slot, NOW() - INTERVAL '1 hour', 'draft');
                """), params)
        self.args = {"league_id": 1, "guild_id": 10, "discord_user_id": 20}

    def snapshot(self):
        with self.engine.connect() as c:
            return tuple(tuple(c.execute(text(f"SELECT * FROM fantasy.{table} ORDER BY id")).all())
                         for table in ("roster_asset", "roster_history"))

    def test_swap_persists_history_and_survives_new_connection(self):
        set_starter(**self.args, player_id=6)
        view = get_lineup(**self.args)
        slots = {e.player.player_id: e.slot.value for e in view.entries if e.player}
        self.assertEqual((slots[1], slots[6]), ("BENCH", "TOP"))
        with self.engine.connect() as c:
            history = c.execute(text("SELECT * FROM fantasy.roster_history ORDER BY id")).all()
        self.assertEqual(len(history), 11)
        closed = [r for r in history if r.valid_until is not None]
        new = [r for r in history if r.reason == "lineup"]
        self.assertEqual(len(closed), 2)
        self.assertEqual(len(new), 2)
        self.assertEqual({r.valid_until for r in closed}, {r.valid_from for r in new})
        self.assertEqual(sum(r.valid_until is None for r in history), 9)

    def test_wrong_guild_or_manager_cannot_edit(self):
        for overrides in ({"guild_id": 99}, {"discord_user_id": 99}, {"discord_user_id": 21}):
            before = self.snapshot()
            with self.subTest(overrides=overrides), self.assertRaises(FantasyServiceError):
                set_starter(**(self.args | overrides), player_id=6)
            self.assertEqual(before, self.snapshot())

    def test_non_active_states_cannot_edit(self):
        for status in ("registration", "draft", "finished", "cancelled"):
            with self.engine.begin() as c:
                c.execute(text("UPDATE fantasy.league SET status = :status"), {"status": status})
            before = self.snapshot()
            with self.subTest(status=status), self.assertRaises(FantasyServiceError):
                set_starter(**self.args, player_id=6)
            self.assertEqual(before, self.snapshot())

    def test_both_competitions_lock_from_database(self):
        for competition in ("LEC", "LCS"):
            with self.engine.begin() as c:
                c.execute(text("DELETE FROM fantasy.match_schedule"))
                c.execute(text("""
                    INSERT INTO fantasy.match_schedule (external_id, competition_code, scheduled_at_utc)
                    VALUES ('match', :competition, clock_timestamp())
                """), {"competition": competition})
            before = self.snapshot()
            with self.subTest(competition=competition), self.assertRaisesRegex(FantasyServiceError, "verrouillé"):
                set_starter(**self.args, player_id=6)
            self.assertEqual(before, self.snapshot())
        with self.engine.begin() as c:
            c.execute(text("UPDATE fantasy.match_schedule SET status = 'cancelled'"))
        set_starter(**self.args, player_id=6)

    def test_invalid_lineup_changes_nothing(self):
        before = self.snapshot()
        with self.assertRaises(FantasyServiceError):
            set_starter(**self.args, player_id=7)
        self.assertEqual(before, self.snapshot())

    def test_missing_history_rolls_back_first_player_too(self):
        with self.engine.begin() as c:
            c.execute(text("DELETE FROM fantasy.roster_history WHERE player_id = 6"))
        before = self.snapshot()
        with self.assertRaisesRegex(FantasyServiceError, "Historique"):
            set_starter(**self.args, player_id=6)
        self.assertEqual(before, self.snapshot())

    def test_inactive_bench_player_is_visible_but_cannot_start(self):
        with self.engine.begin() as c:
            c.execute(text("UPDATE fantasy.pro_player SET active = FALSE WHERE id = 6"))
        self.assertIn(6, get_lineup(**self.args).unavailable_players)
        before = self.snapshot()
        with self.assertRaises(FantasyServiceError):
            set_starter(**self.args, player_id=6)
        self.assertEqual(before, self.snapshot())

    def test_former_starter_without_current_team_can_be_benched(self):
        with self.engine.begin() as c:
            c.execute(text("UPDATE fantasy.pro_player_team_history SET valid_until = NOW() WHERE player_id = 1"))
        self.assertIn(1, get_lineup(**self.args).unavailable_players)
        set_starter(**self.args, player_id=6)

    def test_duplicate_concurrent_requests_only_apply_once(self):
        def attempt():
            try:
                set_starter(**self.args, player_id=6)
                return "saved"
            except FantasyServiceError:
                return "rejected"
        with ThreadPoolExecutor(max_workers=2) as executor:
            self.assertCountEqual(list(executor.map(lambda _: attempt(), range(2))), ["saved", "rejected"])
        self.assertEqual(len(self.snapshot()[1]), 11)


if __name__ == "__main__":
    unittest.main()
