import unittest

import pandas as pd

from fonctions.lolpros_profiles import fetch_lolpros_accounts_for_players


class _FakeHtmlResponse:
    status = 200
    headers = {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def raise_for_status(self):
        return None

    async def text(self):
        return """
        <html><head>
          <meta name="description" content="Mid | France | Player for Test Team | Test Account#EUW [Challenger]">
        </head><body>
          <section id="accounts"><div>Test Account#EUW</div></section>
        </body></html>
        """


class _FakeSession:
    def get(self, url, **kwargs):
        return _FakeHtmlResponse()


class LolprosBatchDurationTests(unittest.IsolatedAsyncioTestCase):
    async def test_progress_reports_real_last_batch_duration(self):
        events = []

        async def progress(state):
            events.append(state.copy())

        await fetch_lolpros_accounts_for_players(
            _FakeSession(),
            ["Player1", "Player2", "Player3"],
            leaguepedia_profiles=pd.DataFrame(),
            cached_profiles=pd.DataFrame(),
            batch_size=2,
            request_interval_seconds=0,
            batch_pause_seconds=0,
            progress_callback=progress,
        )

        self.assertIsNone(events[0]["last_batch_duration_seconds"])

        batch_events = [event for event in events if event["event"] == "batch_end"]
        self.assertEqual(len(batch_events), 2)
        self.assertTrue(all(event["last_batch_duration_seconds"] >= 0 for event in batch_events))
        self.assertEqual(
            events[-1]["last_batch_duration_seconds"],
            batch_events[-1]["last_batch_duration_seconds"],
        )


if __name__ == "__main__":
    unittest.main()
