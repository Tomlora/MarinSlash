import copy
import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import text

from fonctions.fantasy import results
from fonctions.fantasy.service import FantasyServiceError
import test_fantasy_lineup_database as fixtures
from test_fantasy_results import START, parse_fixture


@unittest.skipUnless(os.environ.get('FANTASY_TEST_DSN'), 'Set FANTASY_TEST_DSN to a disposable PostgreSQL database')
class ResultsDatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.LineupDatabaseTests.setUpClass.__func__(cls)
        with cls.engine.begin() as c:
            migration = (Path(__file__).parents[1] / 'sql/migrations/20261003_fantasy_results.sql').read_text()
            c.exec_driver_sql(migration)
            c.exec_driver_sql(migration)  # additive migration is repeatable

    tearDownClass = classmethod(fixtures.LineupDatabaseTests.tearDownClass.__func__)

    def setUp(self):
        fixtures.LineupDatabaseTests.setUp(self)
        patch.object(results, 'transaction', self.engine.begin).start()
        self.games = parse_fixture()
        with self.engine.begin() as c:
            c.execute(text("SELECT setval(pg_get_serial_sequence('fantasy.pro_player', 'id'), (SELECT MAX(id) FROM fantasy.pro_player))"))
            c.execute(text('UPDATE fantasy.season SET starts_at = :start'), {'start': START-timedelta(hours=1)})
            c.execute(text('UPDATE fantasy.roster_history SET valid_from = :start'), {'start': START-timedelta(hours=1)})

    def count(self, table):
        with self.engine.connect() as c:
            return c.execute(text(f'SELECT COUNT(*) FROM fantasy.{table}')).scalar_one()

    def test_import_is_idempotent_and_does_not_mutate_pool_or_history(self):
        with self.engine.connect() as c:
            players = c.execute(text('SELECT * FROM fantasy.pro_player ORDER BY id')).all()
            histories = c.execute(text('SELECT * FROM fantasy.pro_player_team_history ORDER BY id')).all()
        self.assertEqual(results.import_results(self.games), results.ImportSummary(1, 0))
        self.assertEqual(results.import_results(self.games), results.ImportSummary(0, 1))
        self.assertEqual(self.count('player_game_stats'), 10)
        self.assertEqual(self.count('team_game_stats'), 2)
        with self.engine.connect() as c:
            self.assertEqual(players, c.execute(text('SELECT * FROM fantasy.pro_player WHERE id <= 8 ORDER BY id')).all())
            self.assertEqual(histories, c.execute(text('SELECT * FROM fantasy.pro_player_team_history ORDER BY id')).all())
            self.assertFalse(c.execute(text("SELECT active FROM fantasy.pro_team WHERE external_id = 'opponent'")).scalar_one())

    def test_changed_import_rolls_back_entire_batch(self):
        results.import_results(self.games)
        new, changed = copy.deepcopy(self.games[0]), copy.deepcopy(self.games[0])
        new['external_id'] = 'new-game'
        changed['players'][0]['kills'] += 1
        with self.assertRaises(FantasyServiceError):
            results.import_results([new, changed])
        self.assertEqual(self.count('game'), 1)
        self.assertEqual(self.count('result_snapshot'), 1)

    def test_concurrent_import_only_inserts_once(self):
        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(lambda _: results.import_results(self.games), range(2)))
        self.assertEqual(sum(o.imported for o in outcomes), 1)
        self.assertEqual(sum(o.unchanged for o in outcomes), 1)

    def test_scores_use_historical_starters_not_current_roster(self):
        results.import_results(self.games)
        with self.engine.begin() as c:
            # Current roster differs from the game's roster; only historical slots count.
            c.execute(text("UPDATE fantasy.roster_asset SET slot = 'BENCH' WHERE player_id = 1"))
            c.execute(text("UPDATE fantasy.roster_asset SET slot = 'TOP' WHERE player_id = 6"))
        self.assertEqual(results.calculate_scores(**self.args)['calculated'], 1)
        self.assertEqual(results.calculate_scores(**self.args)['calculated'], 0)
        view = results.standings(**self.args)
        self.assertEqual(view['rows'][0]['score'], Decimal('58'))
        self.assertEqual(view['rows'][0]['contributions'], 6)
        self.assertEqual(view['rows'][1]['score'], 0)
        details, more = results.score_details(**self.args)
        self.assertFalse(more)
        self.assertEqual(len(details), 6)
        self.assertNotIn(6, [r['player_id'] for r in details])
        self.assertEqual(self.count('player_game_score'), 10)
        self.assertEqual(self.count('team_game_score'), 2)

    def test_exact_transfer_boundary_counts_new_owner(self):
        results.import_results(self.games)
        with self.engine.begin() as c:
            c.execute(text('UPDATE fantasy.roster_history SET valid_until = :start WHERE player_id = 1'), {'start': START})
            c.execute(text("INSERT INTO fantasy.roster_history (season_id, manager_id, player_id, slot, valid_from, reason) VALUES (1, 2, 1, 'TOP', :start, 'trade')"), {'start': START})
        results.calculate_scores(**self.args)
        rows = {r['discord_user_id']: r['score'] for r in results.standings(**self.args)['rows']}
        self.assertEqual(rows, {20: Decimal('18'), 21: Decimal('40')})

    def test_overlapping_history_rolls_back_all_scores(self):
        results.import_results(self.games)
        with self.engine.begin() as c:
            c.execute(text("INSERT INTO fantasy.roster_history (season_id, manager_id, player_id, slot, valid_from, reason) VALUES (1, 2, 1, 'TOP', :start, 'bad')"), {'start': START})
        with self.assertRaises(FantasyServiceError):
            results.calculate_scores(**self.args)
        for table in ('player_game_score', 'team_game_score', 'manager_game_score', 'season_game_scored', 'season_scoring_snapshot'):
            self.assertEqual(self.count(table), 0)

    def test_calculations_are_serialized_and_snapshots_stay_stable(self):
        results.import_results(self.games)
        with ThreadPoolExecutor(max_workers=2) as executor:
            outputs = list(executor.map(lambda _: results.calculate_scores(**self.args), range(2)))
        self.assertEqual(sum(o['calculated'] for o in outputs), 1)
        with self.engine.begin() as c:
            c.execute(text("UPDATE fantasy.player_game_stats SET kills = 99"))
            c.execute(text("UPDATE fantasy.pro_player SET handle = 'Renamed'"))
        results.calculate_scores(**self.args)
        self.assertEqual(results.standings(**self.args)['rows'][0]['score'], 58)
        self.assertNotIn('Renamed', [r['asset_name'] for r in results.score_details(**self.args)[0]])

    def test_rules_freeze_and_refuse_changes(self):
        results.import_results(self.games)
        results.calculate_scores(**self.args)
        with self.engine.begin() as c:
            c.execute(text("UPDATE fantasy.season SET scoring_rule_version = 'missing'"))
        with self.assertRaises(FantasyServiceError):
            results.calculate_scores(**self.args)
        self.assertEqual(results.standings(**self.args)['rows'][0]['score'], 58)

    def test_uses_configured_rules_not_python_defaults(self):
        results.import_results(self.games)
        with self.engine.begin() as c:
            c.execute(text("INSERT INTO fantasy.scoring_rule (version, rules) SELECT 'custom', jsonb_set(rules, '{player,kill}', '3') FROM fantasy.scoring_rule WHERE version = 'riot_classic_v1' ON CONFLICT (version) DO NOTHING"))
            c.execute(text("UPDATE fantasy.season SET scoring_rule_version = 'custom'"))
        results.calculate_scores(**self.args)
        self.assertEqual(results.standings(**self.args)['rows'][0]['score'], 68)

    def test_requires_owner_membership_server_and_supported_mode(self):
        results.import_results(self.games)
        for overrides in ({'discord_user_id': 21}, {'discord_user_id': 999}, {'guild_id': 999}):
            with self.assertRaises(FantasyServiceError):
                results.calculate_scores(**{**self.args, **overrides})
        with self.assertRaises(FantasyServiceError):
            results.standings(**{**self.args, 'discord_user_id': 999})
        with self.engine.begin() as c:
            c.execute(text("UPDATE fantasy.league SET scoring_mode = 'normalized'"))
        with self.assertRaises(FantasyServiceError):
            results.calculate_scores(**self.args)
        self.assertEqual(self.count('season_game_scored'), 0)

    def test_season_end_is_exclusive_and_preseason_excluded(self):
        games = [copy.deepcopy(self.games[0]) for _ in range(3)]
        for index, game in enumerate(games):
            game['external_id'] = f'window-{index}'
            game['started_at'] = (START + timedelta(hours=index-1)).isoformat()
        results.import_results(games)
        with self.engine.begin() as c:
            c.execute(text('UPDATE fantasy.season SET starts_at = :start, ends_at = :end'), {'start': START, 'end': START+timedelta(hours=1)})
        self.assertEqual(results.calculate_scores(**self.args)['calculated'], 1)
        self.assertEqual(results.standings(**self.args)['imported'], 1)
