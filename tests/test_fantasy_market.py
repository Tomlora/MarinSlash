import threading
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from cogs.fantasy_lol import FantasyLoL
from fonctions.fantasy.lineup import LineupView
from fonctions.fantasy.market import MarketPage, TradeView, replace_asset
from fonctions.fantasy.models import Competition, PlayerAsset, PlayerRole, TeamAsset
from fonctions.fantasy.service import FantasyServiceError
from test_fantasy_lineup import roster


class MarketRulesTests(unittest.TestCase):
    def test_replacement_preserves_slot_and_does_not_mutate_original(self):
        entries = roster()
        updated, new = replace_asset(entries, entries[0], PlayerAsset(99, 'NewTop', PlayerRole.TOP, Competition.LEC))
        self.assertEqual(new.slot, entries[0].slot)
        self.assertEqual(entries[0].player.player_id, 1)
        self.assertEqual(updated[0].player.player_id, 99)
        self.assertEqual(entries[1:], updated[1:])

    def test_wrong_role_and_single_competition_are_rejected(self):
        entries = roster()
        for old, incoming in (
            (entries[0], PlayerAsset(99, 'WrongRole', PlayerRole.MID, Competition.LEC)),
            (entries[2], PlayerAsset(99, 'OnlyLEC', PlayerRole.MID, Competition.LEC)),
            (entries[0], TeamAsset(99, 'WrongType', Competition.LEC)),
        ):
            with self.subTest(incoming=incoming), self.assertRaises(FantasyServiceError):
                replace_asset(entries, old, incoming)


class MarketCommandTests(unittest.IsolatedAsyncioTestCase):
    async def test_commands_defer_before_worker_and_keep_responses_private(self):
        trade = TradeView(1, 'pending', 20, 21, 'player', 6, 'Offered', 16, 'Requested')
        view = LineupView('League', 'Season', tuple(roster()), frozenset(), frozenset())
        cases = [
            ('fantasy_market', 'list_free_agents', {'type': 'player'}, MarketPage((roster()[0].player,), 1, False)),
            ('fantasy_claim', 'claim_free_agent', {'type': 'player', 'libere_id': 1, 'recrute_id': 99}, view),
            ('fantasy_trade_offer', 'offer_trade', {'type': 'player', 'manager': SimpleNamespace(id=21), 'offert_id': 6, 'demande_id': 16}, trade),
            ('fantasy_trades', 'list_trades', {}, ((trade,), False)),
            ('fantasy_trade_reply', 'respond_trade', {'trade_id': 1, 'action': 'accept'}, trade),
        ]
        main_thread = threading.get_ident()
        for method, service, kwargs, result in cases:
            with self.subTest(command=method):
                ctx = SimpleNamespace(guild_id=10, author_id=20, defer=AsyncMock(), send=AsyncMock())
                def worker(**params):
                    ctx.defer.assert_awaited_once_with(ephemeral=True)
                    self.assertNotEqual(main_thread, threading.get_ident())
                    self.assertEqual(params['guild_id'], 10)
                    self.assertEqual(params['discord_user_id'], 20)
                    return result
                with patch(f'cogs.fantasy_lol.{service}', side_effect=worker):
                    await getattr(FantasyLoL, method).callback(object.__new__(FantasyLoL), ctx, league_id=1, **kwargs)
                for call in ctx.send.call_args_list:
                    self.assertTrue(call.kwargs['ephemeral'])
                    self.assertLessEqual(len(call.args[0]), 2000)

    async def test_wrong_server_returns_error_without_calling_market(self):
        ctx = SimpleNamespace(guild_id=None, author_id=20, defer=AsyncMock(), send=AsyncMock())
        with patch('cogs.fantasy_lol.claim_free_agent') as worker:
            await FantasyLoL.fantasy_claim.callback(object.__new__(FantasyLoL), ctx, 1, 'player', 1, 99)
        worker.assert_not_called()
        self.assertIn('serveur', ctx.send.call_args.args[0])

    async def test_roster_lookup_passes_requester_and_target_separately(self):
        ctx = SimpleNamespace(guild_id=10, author_id=20, defer=AsyncMock(), send=AsyncMock())
        view = LineupView('League', 'Season', tuple(roster()), frozenset(), frozenset())
        with patch('cogs.fantasy_lol.get_lineup', return_value=view) as worker:
            await FantasyLoL.fantasy_roster.callback(object.__new__(FantasyLoL), ctx, 1, SimpleNamespace(id=21))
        self.assertEqual(worker.call_args.kwargs['discord_user_id'], 20)
        self.assertEqual(worker.call_args.kwargs['target_discord_id'], 21)


if __name__ == '__main__':
    unittest.main()
