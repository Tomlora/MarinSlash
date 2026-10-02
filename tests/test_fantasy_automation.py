import asyncio
import os
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fonctions.fantasy import automation
from fonctions.fantasy.models import Competition
from fonctions.fantasy.providers.oracles_elixir import OracleElixirPlayerProvider
from fonctions.fantasy.providers.schedule import FallbackScheduleProvider, RiotEsportsScheduleProvider, ScheduleProviderError


class DueTests(unittest.TestCase):
    def test_success_intervals_and_error_backoff(self):
        now = datetime.now(timezone.utc)
        self.assertTrue(automation.is_due('pool', None, now))
        for kind, age, failed, due in (
            ('pool', 23, False, False), ('pool', 24, False, True),
            ('pool', 5, True, False), ('pool', 6, True, True),
            ('schedule', .9, False, False), ('schedule', 1, False, True),
            ('schedule', .9, True, False), ('schedule', 1, True, True),
        ):
            row = SimpleNamespace(last_attempt_at=now-timedelta(hours=age), last_error='error' if failed else None)
            self.assertEqual(automation.is_due(kind, row, now), due)


class WorkerTests(unittest.IsolatedAsyncioTestCase):
    async def test_worker_runs_outside_discord_loop(self):
        thread = threading.get_ident()
        with patch.object(automation, '_run_job', side_effect=lambda *args: threading.get_ident()):
            self.assertNotEqual(await automation.run_sync('pool'), thread)

    async def test_cancellation_does_not_allow_second_writer(self):
        entered, release = threading.Event(), threading.Event()
        def work(*args):
            entered.set()
            if not release.wait(5):
                raise RuntimeError('Test worker timed out')
        with patch.object(automation, '_run_job', side_effect=work):
            task = asyncio.create_task(automation.run_sync('pool'))
            try:
                self.assertTrue(await asyncio.to_thread(entered.wait, 2))
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await task
                with self.assertRaises(automation.SyncBusyError):
                    await automation.run_sync('schedule')
            finally:
                release.set()
                await asyncio.wrap_future(automation._executor.submit(lambda: None))
        self.assertFalse(automation._busy.locked())


class AdminLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_ready_and_reload_start_only_one_loop_and_drop_cancels_it(self):
        from cogs.fantasy_admin import FantasyAdmin
        cog = object.__new__(FantasyAdmin)
        finished = asyncio.Event()
        async def loop():
            try:
                await asyncio.Event().wait()
            finally:
                finished.set()
        with patch.dict(os.environ, {'FANTASY_AUTO_SYNC_ENABLED': '1'}), patch.object(FantasyAdmin, '_sync_loop', side_effect=loop):
            FantasyAdmin.__init__(cog, SimpleNamespace(is_ready=True))
            task = cog._sync_task
            cog._start_sync_loop()
            self.assertIs(cog._sync_task, task)
            await asyncio.sleep(0)
            with patch('interactions.Extension.drop'):
                cog.drop()
            with self.assertRaises(asyncio.CancelledError):
                await task
        self.assertTrue(finished.is_set())

    async def test_automation_is_opt_in(self):
        from cogs.fantasy_admin import FantasyAdmin
        cog = object.__new__(FantasyAdmin)
        with patch.dict(os.environ, {'FANTASY_AUTO_SYNC_ENABLED': '0'}):
            FantasyAdmin.__init__(cog, SimpleNamespace(is_ready=True))
            self.assertIsNone(cog._sync_task)

    async def test_status_defers_and_reads_off_loop(self):
        from cogs.fantasy_admin import FantasyAdmin
        ctx = SimpleNamespace(defer=AsyncMock(), send=AsyncMock())
        thread = threading.get_ident()
        def status():
            ctx.defer.assert_awaited_once_with(ephemeral=True)
            self.assertNotEqual(thread, threading.get_ident())
            return {'jobs': [], 'stale': ['LCS']}
        with patch('cogs.fantasy_admin.read_sync_status', side_effect=status):
            await FantasyAdmin.fantasy_sync_status.callback(object.__new__(FantasyAdmin), ctx)
        self.assertIn('LCS', ctx.send.call_args.args[0])

    async def test_error_releases_worker_gate(self):
        with patch.object(automation, '_run_job', side_effect=RuntimeError('error')):
            with self.assertRaises(RuntimeError):
                await automation.run_sync('pool')
        self.assertFalse(automation._busy.locked())


class ProviderBoundsTests(unittest.IsolatedAsyncioTestCase):
    async def test_empty_primary_tries_fallback(self):
        primary = SimpleNamespace(fetch_schedule=AsyncMock(return_value=[]))
        fallback = SimpleNamespace(fetch_schedule=AsyncMock(return_value=['match']))
        provider = FallbackScheduleProvider(primary, fallback)
        now = datetime.now(timezone.utc)
        self.assertEqual(await provider.fetch_schedule(tuple(Competition), now, now+timedelta(days=1)), ['match'])
        fallback.fetch_schedule.assert_awaited_once()

    def _event(self, number, date):
        return {'id': str(number), 'type': 'match', 'startTime': date,
                'league': {'id': 'lec'}, 'match': {'teams': []}}

    async def test_esports_reads_older_and_newer_pages(self):
        provider = RiotEsportsScheduleProvider()
        responses = {
            None: {'events': [self._event(1, '2026-10-02T12:00:00Z')], 'pages': {'older': 'old', 'newer': 'new'}},
            'old': {'events': [self._event(2, '2026-10-01T12:00:00Z')], 'pages': {}},
            'new': {'events': [self._event(3, '2026-10-03T12:00:00Z')], 'pages': {}},
        }
        calls = []
        async def get_json(session, endpoint, params):
            if endpoint == 'getLeagues':
                return {'data': {'leagues': [{'slug': 'lec', 'id': 'lec'}]}}
            token = dict(params).get('pageToken')
            calls.append(token)
            return {'data': {'schedule': responses[token]}}
        with patch.object(provider, '_get_json', side_effect=get_json):
            matches = await provider.fetch_schedule((Competition.LEC,), datetime(2026, 10, 1, tzinfo=timezone.utc), datetime(2026, 10, 4, tzinfo=timezone.utc))
        self.assertEqual(calls, [None, 'old', 'new'])
        self.assertEqual(len(matches), 3)

    async def test_esports_page_budget_rejects_truncated_window(self):
        provider = RiotEsportsScheduleProvider()
        count = 0
        async def get_json(session, endpoint, params):
            nonlocal count
            if endpoint == 'getLeagues':
                return {'data': {'leagues': [{'slug': 'lec', 'id': 'lec'}]}}
            count += 1
            return {'data': {'schedule': {'events': [self._event(count, '2026-10-02T12:00:00Z')],
                                         'pages': {'older': str(count)}}}}
        with patch.object(provider, '_get_json', side_effect=get_json):
            with self.assertRaisesRegex(ScheduleProviderError, 'budget'):
                await provider.fetch_schedule((Competition.LEC,), datetime(2026, 10, 1, tzinfo=timezone.utc), datetime(2026, 10, 4, tzinfo=timezone.utc))
        self.assertEqual(count, 6)

    async def test_failed_oe_download_removes_temporary_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / 'download.csv')
            fd = os.open(path, os.O_CREAT | os.O_RDWR)
            session = AsyncMock()
            session.__aenter__.return_value.get = lambda *args, **kwargs: (_ for _ in ()).throw(asyncio.TimeoutError())
            with patch('fonctions.fantasy.providers.oracles_elixir.tempfile.mkstemp', return_value=(fd, path)), patch('aiohttp.ClientSession', return_value=session):
                with self.assertRaises(asyncio.TimeoutError):
                    await OracleElixirPlayerProvider()._download()
            self.assertFalse(Path(path).exists())


if __name__ == '__main__':
    unittest.main()
