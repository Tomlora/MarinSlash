"""Run against the same disposable PostgreSQL database as lineup integration tests."""
import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from sqlalchemy import text

import test_fantasy_lineup_database as fixtures
from test_fantasy_lineup import roster
from fonctions.fantasy.lineup import get_lineup
from fonctions.fantasy.market import claim_free_agent, list_free_agents, list_trades, offer_trade, respond_trade
from fonctions.fantasy.service import FantasyServiceError


@unittest.skipUnless(os.environ.get('FANTASY_TEST_DSN'), 'Set FANTASY_TEST_DSN to a disposable PostgreSQL database')
class MarketDatabaseTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.LineupDatabaseTests.setUpClass.__func__)
    tearDownClass = classmethod(fixtures.LineupDatabaseTests.tearDownClass.__func__)
    snapshot = fixtures.LineupDatabaseTests.snapshot

    def setUp(self):
        fixtures.LineupDatabaseTests.setUp(self)
        patch('fonctions.fantasy.market.transaction', self.engine.begin).start()
        with self.engine.begin() as c:
            for entry in roster():
                player = entry.player
                if player:
                    self._insert_player(c, player.player_id + 10, player.role.value, player.competition.value)
                params = {'player': player.player_id + 10 if player else None,
                          'team': 2 if entry.team else None, 'slot': entry.slot.value}
                c.execute(text('''INSERT INTO fantasy.roster_asset (season_id, manager_id, player_id, team_id, slot)
                    VALUES (1, 2, :player, :team, :slot);
                    INSERT INTO fantasy.roster_history
                        (season_id, manager_id, player_id, team_id, slot, valid_from, reason)
                    VALUES (1, 2, :player, :team, :slot, NOW() - INTERVAL '1 hour', 'draft');'''), params)
            self._insert_player(c, 90, 'TOP', 'LEC')
            self._insert_player(c, 91, 'MID', 'LEC')
            self._insert_player(c, 92, 'TOP', 'LCS')
        self.recipient = dict(self.args, discord_user_id=21)

    @staticmethod
    def _insert_player(c, player_id, role, competition):
        c.execute(text('''INSERT INTO fantasy.pro_player (id, external_id, handle, role)
            VALUES (:id, :external, :name, :role);
            INSERT INTO fantasy.pro_player_team_history (player_id, team_id, valid_from)
            VALUES (:id, :team, NOW() - INTERVAL '1 day');'''),
            {'id': player_id, 'external': str(player_id), 'name': f'Player{player_id}', 'role': role,
             'team': {'LEC': 1, 'LCS': 2, 'LFL': 3}[competition]})

    def offer(self, offered=6, requested=16, kind='player'):
        return offer_trade(**self.args, recipient_discord_id=21, asset_type=kind,
                           offered_id=offered, requested_id=requested)

    def claim(self, released=6, incoming=90, kind='player', **overrides):
        return claim_free_agent(**(self.args | overrides), asset_type=kind, released_id=released, incoming_id=incoming)

    def statuses(self):
        with self.engine.connect() as c:
            return dict(c.execute(text('SELECT id, status FROM fantasy.trade')).all())

    def test_market_filters_owned_inactive_and_role_and_paginates(self):
        page = list_free_agents(**self.args, role='TOP', competition='LEC')
        self.assertEqual([p.player_id for p in page.assets], [90])
        with self.engine.begin() as c:
            for player_id in range(100, 126):
                self._insert_player(c, player_id, 'TOP', 'LEC')
            c.execute(text('UPDATE fantasy.pro_player SET active = FALSE WHERE id = 90'))
        first = list_free_agents(**self.args, role='TOP', competition='LEC')
        second = list_free_agents(**self.args, role='TOP', competition='LEC', page=2)
        self.assertEqual(len(first.assets), 20)
        self.assertTrue(first.has_more)
        self.assertEqual(len(second.assets), 6)
        self.assertFalse(second.has_more)
        self.assertFalse({p.player_id for p in first.assets} & {p.player_id for p in second.assets})
        teams = list_free_agents(**self.args, asset_type='team')
        self.assertEqual([t.team_id for t in teams.assets], [3])

    def test_claim_is_atomic_and_writes_history_without_touching_other_manager(self):
        before_other = get_lineup(**self.recipient)
        self.claim()
        self.assertEqual(get_lineup(**self.recipient), before_other)
        with self.engine.connect() as c:
            self.assertIsNone(c.execute(text('SELECT id FROM fantasy.roster_asset WHERE player_id = 6')).first())
            row = c.execute(text('SELECT manager_id, slot FROM fantasy.roster_asset WHERE player_id = 90')).one()
            self.assertEqual((row.manager_id, row.slot), (1, 'BENCH'))
            closed = c.execute(text('SELECT valid_until FROM fantasy.roster_history WHERE player_id = 6')).scalar_one()
            opened = c.execute(text("SELECT valid_from FROM fantasy.roster_history WHERE player_id = 90 AND reason = 'free_agency'")).scalar_one()
            self.assertEqual(closed, opened)

    def test_claim_checks_membership_ownership_roles_and_competitions(self):
        cases = [dict(guild_id=99), dict(discord_user_id=99), dict(released=16),
                 dict(incoming=16), dict(released=1, incoming=91), dict(released=3, incoming=91)]
        for kwargs in cases:
            before = self.snapshot()
            with self.subTest(kwargs=kwargs), self.assertRaises(FantasyServiceError):
                self.claim(**kwargs)
            self.assertEqual(before, self.snapshot())

    def test_claim_rejects_stale_and_locked_incoming_or_outgoing(self):
        for competition in ('LEC', 'LCS'):
            with self.engine.begin() as c:
                c.execute(text('DELETE FROM fantasy.match_schedule'))
                c.execute(text('''INSERT INTO fantasy.match_schedule (external_id, competition_code, scheduled_at_utc)
                    VALUES ('today', :competition, NOW())'''), {'competition': competition})
            before = self.snapshot()
            with self.assertRaisesRegex(FantasyServiceError, 'verrouillé'):
                self.claim(released=1, incoming=92)
            self.assertEqual(before, self.snapshot())
        with self.engine.begin() as c:
            c.execute(text('DELETE FROM fantasy.match_schedule'))
            c.execute(text('DELETE FROM fantasy.schedule_coverage'))
        with self.assertRaisesRegex(FantasyServiceError, 'Calendrier'):
            self.claim()

    def test_only_one_manager_can_claim_same_free_agent(self):
        def attempt(user, old):
            try:
                self.claim(released=old, discord_user_id=user)
                return 'saved'
            except FantasyServiceError:
                return 'rejected'
        with ThreadPoolExecutor(max_workers=2) as executor:
            calls = [executor.submit(attempt, 20, 6), executor.submit(attempt, 21, 16)]
            self.assertCountEqual([f.result() for f in calls], ['saved', 'rejected'])

    def test_team_claim_preserves_team_slot_and_player_roster(self):
        self.claim(released=1, incoming=3, kind='team')
        view = get_lineup(**self.args)
        self.assertEqual([e.team.team_id for e in view.entries if e.team], [3])
        self.assertEqual(len([e for e in view.entries if e.player]), 8)

    def test_offer_is_idempotent_and_does_not_transfer_assets(self):
        before = self.snapshot()
        first, again = self.offer(), self.offer()
        self.assertEqual(first.trade_id, again.trade_id)
        self.assertEqual(first.status, 'pending')
        self.assertEqual(before, self.snapshot())
        self.assertEqual(list_trades(**self.recipient)[0], (first,))

    def test_accept_swaps_both_owners_and_preserves_history_boundaries(self):
        trade = self.offer()
        accepted = respond_trade(**self.recipient, trade_id=trade.trade_id, action='accept')
        self.assertEqual(accepted.status, 'accepted')
        with self.engine.connect() as c:
            owners = dict(c.execute(text('SELECT player_id, manager_id FROM fantasy.roster_asset WHERE player_id IN (6,16)')).all())
            self.assertEqual(owners, {6: 2, 16: 1})
            closed = c.execute(text('SELECT valid_until FROM fantasy.roster_history WHERE valid_until IS NOT NULL')).scalars().all()
            opened = c.execute(text("SELECT valid_from FROM fantasy.roster_history WHERE reason LIKE 'trade:%'")).scalars().all()
            self.assertEqual(len(closed), 2)
            self.assertEqual(closed, opened)
        with self.assertRaisesRegex(FantasyServiceError, 'terminé'):
            respond_trade(**self.recipient, trade_id=trade.trade_id, action='accept')

    def test_only_recipient_can_accept_and_only_proposer_can_cancel(self):
        trade = self.offer()
        for args, action in ((self.args, 'accept'), (self.args, 'decline'), (self.recipient, 'cancel'),
                             (dict(self.recipient, guild_id=99), 'accept'), (dict(self.recipient, discord_user_id=99), 'accept')):
            before = self.snapshot()
            with self.subTest(args=args, action=action), self.assertRaises(FantasyServiceError):
                respond_trade(**args, trade_id=trade.trade_id, action=action)
            self.assertEqual(before, self.snapshot())
        self.assertEqual(self.statuses()[trade.trade_id], 'pending')

    def test_decline_and_cancel_work_even_when_calendar_is_stale(self):
        first = self.offer()
        second = self.offer(offered=1, requested=11)
        before = self.snapshot()
        with self.engine.begin() as c:
            c.execute(text('DELETE FROM fantasy.schedule_coverage'))
            c.execute(text("UPDATE fantasy.league SET status = 'finished'"))
        self.assertEqual(respond_trade(**self.recipient, trade_id=first.trade_id, action='decline').status, 'declined')
        self.assertEqual(respond_trade(**self.args, trade_id=second.trade_id, action='cancel').status, 'cancelled')
        self.assertEqual(before, self.snapshot())

    def test_accept_revalidates_calendar_player_activity_and_role(self):
        trade = self.offer(offered=1, requested=11)
        for change, undo in (
            ("UPDATE fantasy.pro_player SET active = FALSE WHERE id = 11", "UPDATE fantasy.pro_player SET active = TRUE WHERE id = 11"),
            ("UPDATE fantasy.pro_player SET role = 'MID' WHERE id = 11", "UPDATE fantasy.pro_player SET role = 'TOP' WHERE id = 11"),
            ("UPDATE fantasy.schedule_coverage SET refreshed_at = NOW() - INTERVAL '4 hours'", "UPDATE fantasy.schedule_coverage SET refreshed_at = NOW()"),
        ):
            with self.engine.begin() as c:
                c.execute(text(change))
            before = self.snapshot()
            with self.assertRaises(FantasyServiceError):
                respond_trade(**self.recipient, trade_id=trade.trade_id, action='accept')
            self.assertEqual(before, self.snapshot())
            self.assertEqual(self.statuses()[trade.trade_id], 'pending')
            with self.engine.begin() as c:
                c.execute(text(undo))

    def test_moving_an_asset_invalidates_other_offers_even_if_later_reacquired(self):
        trade = self.offer()
        self.claim()
        self.assertEqual(self.statuses()[trade.trade_id], 'invalidated')
        self.claim(released=90, incoming=6)
        with self.assertRaises(FantasyServiceError):
            respond_trade(**self.recipient, trade_id=trade.trade_id, action='accept')

    def test_accept_invalidates_competing_offers(self):
        first, second = self.offer(), self.offer(requested=11)
        respond_trade(**self.recipient, trade_id=first.trade_id, action='accept')
        self.assertEqual(self.statuses(), {first.trade_id: 'accepted', second.trade_id: 'invalidated'})

    def test_trade_error_rolls_back_both_managers_and_status(self):
        trade = self.offer()
        with self.engine.begin() as c:
            c.execute(text('DELETE FROM fantasy.roster_history WHERE player_id = 16'))
        before = self.snapshot()
        with self.assertRaisesRegex(FantasyServiceError, 'Historique'):
            respond_trade(**self.recipient, trade_id=trade.trade_id, action='accept')
        self.assertEqual(before, self.snapshot())
        self.assertEqual(self.statuses()[trade.trade_id], 'pending')

    def test_concurrent_acceptance_only_applies_once(self):
        trade = self.offer()
        def attempt():
            try:
                return respond_trade(**self.recipient, trade_id=trade.trade_id, action='accept').status
            except FantasyServiceError:
                return 'rejected'
        with ThreadPoolExecutor(max_workers=2) as executor:
            self.assertCountEqual(list(executor.map(lambda _: attempt(), range(2))), ['accepted', 'rejected'])

    def test_team_trade(self):
        trade = self.offer(offered=1, requested=2, kind='team')
        respond_trade(**self.recipient, trade_id=trade.trade_id, action='accept')
        with self.engine.connect() as c:
            owners = dict(c.execute(text('SELECT team_id, manager_id FROM fantasy.roster_asset WHERE team_id IS NOT NULL')).all())
        self.assertEqual(owners, {1: 2, 2: 1})

    def test_reading_opponent_roster_still_requires_league_membership(self):
        self.assertEqual(get_lineup(**self.args, target_discord_id=21), get_lineup(**self.recipient))
        with self.assertRaises(FantasyServiceError):
            get_lineup(**dict(self.args, discord_user_id=99), target_discord_id=21)


if __name__ == '__main__':
    unittest.main()
