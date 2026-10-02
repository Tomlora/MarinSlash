import asyncio
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from cogs.fantasy_lol import FantasyLoL, format_lineup
from fonctions.fantasy.lineup import LineupView
from fonctions.fantasy.models import Competition
from fonctions.fantasy.service import FantasyServiceError
from test_fantasy_lineup import roster


class LineupCommandTests(unittest.IsolatedAsyncioTestCase):
    async def test_commands_defer_then_run_database_off_event_loop(self):
        for name, service, options in (
            ("fantasy_roster", "get_lineup", {}),
            ("fantasy_lineup", "set_starter", {"joueur_id": 6}),
        ):
            with self.subTest(command=name):
                ctx = SimpleNamespace(guild_id=10, author_id=20, defer=AsyncMock(), send=AsyncMock())
                cog = object.__new__(FantasyLoL)
                loop_thread = threading.get_ident()
                view = LineupView("League", "Season", tuple(roster()), frozenset({Competition.LEC}), frozenset())

                def database(**kwargs):
                    ctx.defer.assert_awaited_once_with(ephemeral=True)
                    self.assertNotEqual(loop_thread, threading.get_ident())
                    self.assertEqual(kwargs["guild_id"], 10)
                    self.assertEqual(kwargs["discord_user_id"], 20)
                    return view

                with patch(f"cogs.fantasy_lol.{service}", side_effect=database):
                    await getattr(FantasyLoL, name).callback(cog, ctx, league_id=1, **options)
                ctx.send.assert_awaited_once()
                self.assertTrue(ctx.send.call_args.kwargs["ephemeral"])
                self.assertIn("BenchTop", ctx.send.call_args.args[0])

    async def test_service_failure_returns_private_error(self):
        ctx = SimpleNamespace(guild_id=10, author_id=20, defer=AsyncMock(), send=AsyncMock())
        with patch("cogs.fantasy_lol.set_starter", side_effect=FantasyServiceError("Verrouillé")):
            await FantasyLoL.fantasy_lineup.callback(object.__new__(FantasyLoL), ctx, 1, 6)
        ctx.send.assert_awaited_once_with("❌ Verrouillé", ephemeral=True)

    async def test_direct_messages_never_query_database(self):
        ctx = SimpleNamespace(guild_id=None, author_id=20, defer=AsyncMock(), send=AsyncMock())
        with patch("cogs.fantasy_lol.get_lineup") as database:
            await FantasyLoL.fantasy_roster.callback(object.__new__(FantasyLoL), ctx, 1)
        database.assert_not_called()
        self.assertIn("serveur", ctx.send.call_args.args[0])

    def test_view_shows_roles_locks_unavailable_and_fits_discord(self):
        view = LineupView("L" * 80, "S" * 80, tuple(roster()), frozenset({Competition.LEC}), frozenset({7}))
        message = format_lineup(view)
        self.assertLess(len(message), 1900)
        self.assertIn("Banc / MID", message)
        self.assertIn("🔒", message)
        self.assertIn("indisponible", message)


if __name__ == "__main__":
    unittest.main()
