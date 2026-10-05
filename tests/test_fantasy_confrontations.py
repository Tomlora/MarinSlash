import threading
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from itertools import combinations
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from cogs.fantasy_lol import FantasyLoL
from fonctions.fantasy.confrontations import period_schedule, ranking_rows
from fonctions.fantasy.service import FantasyServiceError


class ConfrontationRulesTests(unittest.TestCase):
    def test_all_counts_have_every_pair_once_and_one_match_per_round(self):
        for count in range(2, 9):
            managers = list(range(1, count+1))
            schedule = period_schedule(managers, '2026-10-05')
            self.assertEqual({frozenset((a, b)) for _, a, b, _, _ in schedule if a and b},
                             {frozenset(pair) for pair in combinations(managers, 2)})
            for number in {r[0] for r in schedule}:
                self.assertCountEqual([m for n, a, b, _, _ in schedule if n == number for m in (a, b) if m], managers)
            if count % 2:
                self.assertCountEqual([a or b for _, a, b, _, _ in schedule if not a or not b], managers)

    def test_paris_midnights_follow_both_dst_changes(self):
        for start, expected_hours in (('2026-03-23', 167), ('2026-10-19', 169), ('2026-10-05', 168)):
            first = period_schedule([1, 2, 3, 4], start)[0]
            self.assertEqual((first[4] - first[3]).total_seconds()/3600, expected_hours)
            next_round = next(row for row in period_schedule([1, 2, 3, 4], start) if row[0] == 2)
            self.assertEqual(first[4], next_round[3])

    def test_bad_dates_durations_and_participants_rejected(self):
        for ids, start, days in (([1], '2026-10-05', 7), ([1, 1], '2026-10-05', 7),
                                 ([1, 2], '2026-2-1', 7), ([1, 2], 'bad', 7),
                                 ([1, 2], '2026-10-05', 0), ([1, 2], '2026-10-05', 29),
                                 ([1, 2], '2026-10-05', True)):
            with self.assertRaises(FantasyServiceError):
                period_schedule(ids, start, days)

    def test_wins_draws_negative_scores_and_byes(self):
        rows = ranking_rows([(1, 20), (2, 21), (3, 22)], [
            (1, 2, Decimal('-1'), Decimal('-2')), (1, 3, Decimal('2.5'), Decimal('2.5')),
            (None, 2, None, Decimal('999'))])
        by_id = {r['manager_id']: r for r in rows}
        self.assertEqual((by_id[1]['points'], by_id[1]['wins'], by_id[1]['draws']), (4, 1, 1))
        self.assertEqual((by_id[2]['points'], by_id[2]['byes'], by_id[2]['for']), (0, 1, -2))
        self.assertEqual(by_id[2]['losses'], 1)

    def test_tiebreakers_and_shared_ranks(self):
        rows = ranking_rows([(1, 20), (2, 21), (3, 22), (4, 23)], [
            (1, 3, Decimal(10), Decimal(5)), (2, 4, Decimal(10), Decimal(5))])
        self.assertEqual([r['rank'] for r in rows], [1, 1, 3, 3])
        rows = ranking_rows([(1, 20), (2, 21), (3, 22), (4, 23)], [
            (1, 3, Decimal(10), Decimal(5)), (2, 4, Decimal(12), Decimal(7))])
        self.assertEqual(rows[0]['manager_id'], 2)  # same differential, more points for


class ConfrontationCommandTests(unittest.IsolatedAsyncioTestCase):
    async def test_commands_acknowledge_then_use_worker_and_private_bounded_messages(self):
        now = datetime.now(timezone.utc)
        cases = [
            ('fantasy_fixtures', 'create_schedule', {'debut': '2026-12-01'}, {'created': True, 'rounds': 7}),
            ('fantasy_round', 'resolve_round', {'tour': 1, 'action': 'close', 'confirmer_complet': True}, {'changed': True, 'closed': True}),
            ('fantasy_matchups', 'view_round', {'tour': 1}, {'round': 1, 'state': 'closed', 'start': now, 'end': now+timedelta(days=7),
             'imported': 2, 'calculated': 1, 'matches': [{'user1': 20, 'user2': 21, 'score1': Decimal(10), 'score2': Decimal(5)},
                                                       {'user1': 22, 'user2': None, 'score1': Decimal(8), 'score2': None}]}),
            ('fantasy_ranking', 'league_ranking', {}, {'rows': ranking_rows([(i, 123456789012345678+i) for i in range(8)], []),
                                                     'closed': 1, 'rounds': 7, 'pending': 2}),
        ]
        main = threading.get_ident()
        for method, service, kwargs, value in cases:
            ctx = SimpleNamespace(guild_id=10, author_id=20, defer=AsyncMock(), send=AsyncMock())
            def work(**params):
                ctx.defer.assert_awaited_once_with(ephemeral=True)
                self.assertNotEqual(main, threading.get_ident())
                self.assertEqual(params['guild_id'], 10)
                self.assertEqual(params['discord_user_id'], 20)
                return value
            with patch(f'cogs.fantasy_lol.{service}', side_effect=work):
                await getattr(FantasyLoL, method).callback(object.__new__(FantasyLoL), ctx, league_id=1, **kwargs)
            self.assertTrue(ctx.send.call_args.kwargs['ephemeral'])
            self.assertLessEqual(len(ctx.send.call_args.args[0]), 2000)

    async def test_dm_rejected_before_database_access(self):
        ctx = SimpleNamespace(guild_id=None, author_id=20, defer=AsyncMock(), send=AsyncMock())
        with patch('cogs.fantasy_lol.create_schedule') as worker:
            await FantasyLoL.fantasy_fixtures.callback(object.__new__(FantasyLoL), ctx, 1, '2026-12-01')
        worker.assert_not_called()

    def test_discord_subcommand_limit(self):
        commands = [value for value in FantasyLoL.__dict__.values() if getattr(value, 'sub_cmd_name', None)]
        self.assertLessEqual(len(commands), 25)
