import copy
import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from zoneinfo import ZoneInfo

from sqlalchemy import text

from fonctions.fantasy import confrontations as h2h, results
from fonctions.fantasy.service import FantasyServiceError
import test_fantasy_results_database as fixtures
from test_fantasy_results import START


@unittest.skipUnless(os.environ.get('FANTASY_TEST_DSN'), 'Set FANTASY_TEST_DSN to a disposable PostgreSQL database')
class ConfrontationDatabaseTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.ResultsDatabaseTests.setUpClass.__func__)
    tearDownClass = classmethod(fixtures.ResultsDatabaseTests.tearDownClass.__func__)
    count = fixtures.ResultsDatabaseTests.count

    def setUp(self):
        fixtures.ResultsDatabaseTests.setUp(self)
        patch.object(h2h, 'transaction', self.engine.begin).start()
        self.future = (datetime.now(ZoneInfo('Europe/Paris'))+timedelta(days=2)).date().isoformat()

    def seed_round(self, number=1, start=None, end=None, left=1, right=2):
        with self.engine.begin() as c:
            return c.execute(text('''INSERT INTO fantasy.matchup
                (season_id, round_number, manager1_id, manager2_id, starts_at, ends_at)
                VALUES (1, :number, :left, :right, :start, :end) RETURNING id'''),
                {'number': number, 'left': left, 'right': right, 'start': start or START-timedelta(minutes=30),
                 'end': end or START+timedelta(hours=1)}).scalar_one()

    def close(self, **overrides):
        return h2h.resolve_round(**{**self.args, 'round_number': 1, 'action': 'close', 'confirm_complete': True, **overrides})

    def test_create_round_robin_idempotent_and_cannot_overwrite(self):
        with self.engine.begin() as c:
            c.execute(text('INSERT INTO fantasy.manager (league_id, discord_user_id) VALUES (1, 22), (1, 23), (1, 24)'))
        out = h2h.create_schedule(**self.args, start_date=self.future)
        self.assertEqual(out, {'created': True, 'rounds': 5})
        self.assertFalse(h2h.create_schedule(**self.args, start_date=self.future)['created'])
        self.assertEqual(self.count('matchup'), 15)
        with self.assertRaises(FantasyServiceError):
            h2h.create_schedule(**self.args, start_date=self.future, days=6)
        view = h2h.view_round(**self.args)
        self.assertEqual((view['round'], view['state']), (1, 'scheduled'))
        self.assertEqual(sum(m['user1'] is None or m['user2'] is None for m in view['matches']), 1)

    def test_concurrent_schedule_creation_does_not_duplicate(self):
        with ThreadPoolExecutor(max_workers=2) as executor:
            outs = list(executor.map(lambda _: h2h.create_schedule(**self.args, start_date=self.future), range(2)))
        self.assertEqual(sum(r['created'] for r in outs), 1)
        self.assertEqual(self.count('matchup'), 1)

    def test_dates_are_checked_against_now_and_season_bounds(self):
        with self.assertRaises(FantasyServiceError):
            h2h.create_schedule(**self.args, start_date='2026-08-01')
        with self.engine.begin() as c:
            c.execute(text('UPDATE fantasy.season SET ends_at = :end'), {'end': datetime.now(timezone.utc)+timedelta(days=3)})
        with self.assertRaises(FantasyServiceError):
            h2h.create_schedule(**self.args, start_date=self.future)
        self.assertEqual(self.count('matchup'), 0)

    def test_owner_membership_guild_and_mode_checks(self):
        self.seed_round()
        for overrides in ({'discord_user_id': 21}, {'discord_user_id': 999}, {'guild_id': 999}):
            with self.assertRaises(FantasyServiceError):
                self.close(**overrides)
            with self.assertRaises(FantasyServiceError):
                h2h.create_schedule(**{**self.args, **overrides}, start_date=self.future)
        for reader in (h2h.view_round, h2h.league_ranking):
            with self.assertRaises(FantasyServiceError):
                reader(**{**self.args, 'discord_user_id': 999})
            reader(**{**self.args, 'discord_user_id': 21})
        with self.engine.begin() as c:
            c.execute(text("UPDATE fantasy.league SET scoring_mode = 'normalized'"))
        with self.assertRaises(FantasyServiceError):
            self.close()

    def test_close_requires_ended_period_attestation_and_calculated_imports(self):
        self.seed_round()
        with self.assertRaises(FantasyServiceError):
            self.close(confirm_complete=False)
        results.import_results(self.games)
        with self.assertRaises(FantasyServiceError):
            self.close()
        self.assertEqual(self.count('manager_period_score'), 0)
        results.calculate_scores(**self.args)
        with self.engine.begin() as c:
            c.execute(text('UPDATE fantasy.matchup SET ends_at = :end'), {'end': datetime.now(timezone.utc)+timedelta(days=1)})
        with self.assertRaises(FantasyServiceError):
            self.close()

    def test_closed_scores_persist_and_count_wins_once(self):
        self.seed_round()
        results.import_results(self.games)
        results.calculate_scores(**self.args)
        live = h2h.view_round(**self.args)
        self.assertEqual(live['state'], 'awaiting_close')
        self.assertEqual(live['matches'][0]['score1'], 58)
        self.assertEqual(h2h.league_ranking(**self.args)['rows'][0]['wins'], 0)
        self.assertTrue(self.close()['changed'])
        self.assertFalse(self.close()['changed'])
        self.assertEqual(self.count('manager_period_score'), 2)
        row = h2h.league_ranking(**self.args)['rows'][0]
        self.assertEqual((row['wins'], row['points'], row['for']), (1, 3, 58))
        self.assertEqual(h2h.view_round(**self.args)['state'], 'closed')

    def test_reopen_then_calculate_late_import_and_refinalize(self):
        self.seed_round()
        results.import_results(self.games)
        results.calculate_scores(**self.args)
        self.close()
        late = copy.deepcopy(self.games[0])
        late['external_id'] = 'late'
        late['started_at'] = (START+timedelta(minutes=1)).isoformat()
        results.import_results([late])
        self.assertEqual(h2h.league_ranking(**self.args)['pending'], 1)
        with self.assertRaisesRegex(FantasyServiceError, 'réouvre'):
            results.calculate_scores(**self.args)
        self.assertEqual(h2h.view_round(**self.args)['matches'][0]['score1'], 58)
        self.assertEqual(self.count('season_game_scored'), 1)
        self.assertFalse(self.close()['changed'])  # never implicitly changes a closed result
        self.close(action='reopen')
        self.assertEqual(h2h.league_ranking(**self.args)['closed'], 0)
        self.assertEqual(self.count('manager_game_score'), 6)
        self.assertFalse(self.close(action='reopen')['changed'])
        results.calculate_scores(**self.args)
        self.close()
        row = h2h.league_ranking(**self.args)['rows'][0]
        self.assertEqual((row['points'], row['wins'], row['for']), (3, 1, 116))

    def test_period_end_is_exclusive(self):
        self.seed_round(end=START)
        self.seed_round(2, start=START, end=START+timedelta(hours=1))
        results.import_results(self.games)
        results.calculate_scores(**self.args)
        self.close()
        self.close(round_number=2)
        self.assertEqual(h2h.view_round(**self.args, round_number=1)['matches'][0]['score1'], 0)
        self.assertEqual(h2h.view_round(**self.args, round_number=2)['matches'][0]['score1'], 58)
        self.assertEqual(h2h.league_ranking(**self.args)['rows'][0]['points'], 4)

    def test_empty_round_and_bye_are_explicit_without_automatic_win(self):
        with self.engine.begin() as c:
            c.execute(text('INSERT INTO fantasy.manager (league_id, discord_user_id) VALUES (1, 22)'))
        self.seed_round()
        self.seed_round(left=3, right=None)
        self.close()
        rows = {r['user']: r for r in h2h.league_ranking(**self.args)['rows']}
        self.assertEqual((rows[20]['points'], rows[21]['points']), (1, 1))
        self.assertEqual((rows[22]['byes'], rows[22]['wins'], rows[22]['points']), (1, 0, 0))

    def test_concurrent_close_counts_only_one_snapshot(self):
        self.seed_round()
        with ThreadPoolExecutor(max_workers=2) as executor:
            outs = list(executor.map(lambda _: self.close(), range(2)))
        self.assertEqual(sum(r['changed'] for r in outs), 1)
        self.assertEqual(self.count('manager_period_score'), 2)

    def test_partial_snapshot_is_rejected(self):
        mid = self.seed_round()
        with self.engine.begin() as c:
            c.execute(text('INSERT INTO fantasy.manager_period_score (matchup_id, manager_id, score) VALUES (:id, 1, 99)'), {'id': mid})
        with self.assertRaises(FantasyServiceError):
            self.close()
        with self.assertRaises(FantasyServiceError):
            h2h.league_ranking(**self.args)
        self.assertEqual(self.count('manager_period_score'), 1)

    def test_snapshot_write_failure_rolls_back_entire_round(self):
        self.seed_round()
        with self.engine.begin() as c:
            c.execute(text('ALTER TABLE fantasy.manager_period_score ADD CONSTRAINT reject_test CHECK (manager_id <> 2)'))
        try:
            from sqlalchemy.exc import IntegrityError
            with self.assertRaises(IntegrityError):
                self.close()
            self.assertEqual(self.count('manager_period_score'), 0)
        finally:
            with self.engine.begin() as c:
                c.execute(text('ALTER TABLE fantasy.manager_period_score DROP CONSTRAINT reject_test'))
