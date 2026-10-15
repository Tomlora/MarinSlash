import csv
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from cogs.fantasy_admin import FantasyAdmin
from cogs.fantasy_lol import FantasyLoL
from fonctions.fantasy import automation
from fonctions.fantasy.providers.results import parse_results, result_window, ResultImportError
from fonctions.fantasy.results import ImportSummary, _rules
from fonctions.fantasy.scoring import PlayerGameStats, TeamGameStats, score_player, score_team
from fonctions.fantasy.service import FantasyServiceError

START = datetime(2026, 8, 1, 12, tzinfo=timezone.utc)


def rows(start=START, gameid='game-1'):
    result = []
    for side, teamid, first in (('Blue', 'lec', 1), ('Red', 'opponent', 6)):
        base = dict(gameid=gameid, league='LEC', date=start.isoformat(), gamelength='1500', datacompleteness='complete',
                    teamid=teamid, teamname=teamid, side=side, result=str(int(side == 'Blue')), playername='', playerid='',
                    kills='0', deaths='0', assists='0', triplekills='0', quadrakills='0', pentakills='0',
                    barons='1', dragons='2', towers='8', firstblood=str(int(side == 'Blue')))
        base['total cs'] = '0'
        result.append(dict(base, position='team'))
        for number, position in enumerate(('top', 'jng', 'mid', 'bot', 'sup'), first):
            row = dict(base, position=position, playerid=str(number), playername=f'Player{number}')
            if number == 1:
                row.update(kills='10', deaths='2', assists='10', triplekills='1')
                row['total cs'] = '200'
            if number == 6:
                row['kills'] = '1'
            result.append(row)
    return result


def parse_fixture(data=None, start=START, end=None):
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / 'games.csv'
        data = rows(start) if data is None else data
        with path.open('w', newline='', encoding='utf-8') as output:
            writer = csv.DictWriter(output, fieldnames=list(data[0]))
            writer.writeheader()
            writer.writerows(data)
        return parse_results(path, start=start, end=end or start+timedelta(days=1), now=start+timedelta(days=2))


class ResultsParsingTests(unittest.TestCase):
    def test_complete_modern_game_and_exact_formula(self):
        game, = parse_fixture()
        self.assertEqual(game['external_id'], 'oe:LEC:2026:game-1')
        self.assertEqual(len(game['players']), 10)
        self.assertEqual(len(game['teams']), 2)
        self.assertEqual(game['duration_seconds'], 1500)
        self.assertEqual(score_player(PlayerGameStats(10, 2, 10, 200, 1)), 40)
        self.assertEqual(score_team(TeamGameStats(True, 1, 2, 8, True, 1500)), 18)
        self.assertEqual(score_team(TeamGameStats(True, 1, 2, 8, True, 1800)), 16)
        self.assertEqual(score_player(PlayerGameStats(deaths=4)), -2)

    def test_missing_nonfinite_negative_fractional_stats_are_not_zero(self):
        for field in ('kills', 'deaths', 'assists', 'total cs', 'triplekills', 'quadrakills', 'pentakills'):
            for bad in ('', 'NaN', 'Infinity', '-1', '1.5'):
                with self.subTest(field=field, value=bad):
                    data = rows()
                    data[1][field] = bad
                    with self.assertRaises(ResultImportError):
                        parse_fixture(data)
        for field in ('barons', 'dragons', 'towers', 'firstblood'):
            data = rows()
            data[0][field] = ''
            with self.assertRaises(ResultImportError):
                parse_fixture(data)

    def test_partial_duplicate_and_inconsistent_games_rejected(self):
        mutations = [lambda r: r.pop(), lambda r: r.append(r[0]),
                     lambda r: r[1].update(datacompleteness='partial'),
                     lambda r: r[1].update(position='mid'), lambda r: r[1].update(result='0'),
                     lambda r: r[1].update(date=(START+timedelta(minutes=1)).isoformat()),
                     lambda r: r[1].update(gamelength='30.5'), lambda r: r[7].update(playerid='1')]
        for mutate in mutations:
            data = rows()
            mutate(data)
            with self.assertRaises(ResultImportError):
                parse_fixture(data)

    def test_utc_window_is_half_open_and_same_year(self):
        later = START+timedelta(days=1)
        games = parse_fixture(rows()+rows(later, 'next'), end=later)
        self.assertEqual(len(games), 1)
        for start, end in ((START, START), (START, START+timedelta(days=32)),
                           (START.replace(tzinfo=None), START),
                           (datetime(2026, 12, 31, tzinfo=timezone.utc), datetime(2027, 1, 2, tzinfo=timezone.utc))):
            with self.assertRaises(ResultImportError):
                result_window(start, end)

    def test_empty_and_future_games_rejected(self):
        with self.assertRaises(ResultImportError):
            parse_fixture(rows(START-timedelta(days=1)))
        data = rows(START+timedelta(days=3))
        with self.assertRaises(ResultImportError):
            parse_fixture(data, end=START+timedelta(days=4))

    def test_canonical_snapshot_is_independent_of_csv_order(self):
        self.assertEqual(parse_fixture(rows()), parse_fixture(list(reversed(rows()))))

    def test_invalid_rules_are_rejected_instead_of_using_defaults(self):
        for value in ({}, {'player': {}, 'team': {}}, {'extra': {}}):
            with self.assertRaises(FantasyServiceError):
                _rules(value)


class ResultsCommandTests(unittest.IsolatedAsyncioTestCase):
    async def test_read_and_calculate_commands_defer_and_run_off_loop(self):
        main_thread = threading.get_ident()
        for method, service, value in (
            ('fantasy_calculate', 'calculate_scores', dict(calculated=1, has_more=True, version='v1')),
            ('fantasy_standings', 'standings', dict(rows=[dict(discord_user_id=20, score=Decimal('2.500'), contributions=2)], calculated=1, imported=2)),
            ('fantasy_scores', 'score_details', ([dict(game_id=1, started_at=START, slot='TOP', asset_name='x'*80, score=Decimal('40'), rule_version='v1')]*10, True)),
        ):
            ctx = SimpleNamespace(guild_id=10, author_id=20, defer=AsyncMock(), send=AsyncMock())
            def work(**kwargs):
                ctx.defer.assert_awaited_once_with(ephemeral=True)
                self.assertNotEqual(threading.get_ident(), main_thread)
                return value
            with patch(f'cogs.fantasy_lol.{service}', side_effect=work):
                await getattr(FantasyLoL, method).callback(object.__new__(FantasyLoL), ctx, league_id=1)
            self.assertTrue(ctx.send.call_args.kwargs['ephemeral'])
            self.assertLessEqual(len(ctx.send.call_args.args[0]), 2000)

    async def test_admin_import_checks_runtime_permission_and_date_format(self):
        ctx = SimpleNamespace(guild_id=10, author=SimpleNamespace(has_permission=Mock(return_value=False)), defer=AsyncMock(), send=AsyncMock())
        with patch('cogs.fantasy_admin.run_sync', new=AsyncMock()) as sync:
            await FantasyAdmin.fantasy_import_results.callback(object.__new__(FantasyAdmin), ctx, '2026-08-01', '2026-08-02')
            sync.assert_not_awaited()
            ctx.author.has_permission.return_value = True
            await FantasyAdmin.fantasy_import_results.callback(object.__new__(FantasyAdmin), ctx, 'invalid', '2026-08-02')
            sync.assert_not_awaited()
            sync.return_value = SimpleNamespace(result=ImportSummary(1, 0))
            await FantasyAdmin.fantasy_import_results.callback(object.__new__(FantasyAdmin), ctx, '2026-08-01', '2026-08-02')
            self.assertEqual(sync.call_args.args, ('results',))
            self.assertEqual(sync.call_args.kwargs['window'][0].tzinfo, timezone.utc)

    async def test_results_use_shared_worker_and_remain_manual(self):
        def worker(*args, **kwargs):
            self.assertEqual(args, ('results', 'oracle_elixir', False))
            self.assertEqual(kwargs['window'], (START, START+timedelta(days=1)))
            return threading.get_ident()
        with patch.object(automation, '_run_job', side_effect=worker):
            self.assertNotEqual(await automation.run_sync('results', window=(START, START+timedelta(days=1))), threading.get_ident())
        with self.assertRaises(ValueError):
            await automation.run_sync('results', automatic=True, window=(START, START+timedelta(days=1)))
