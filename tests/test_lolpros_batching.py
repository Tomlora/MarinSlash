import unittest

import pandas as pd

from fonctions.lolpros_profiles import (
    _select_players_for_refresh,
    fetch_lolpros_accounts_for_players,
)


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
    def __init__(self):
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return _FakeHtmlResponse()


class LolprosBatchPlanningTests(unittest.TestCase):
    def test_selection_contains_every_player_and_prioritizes_known_urls(self):
        players = ["Legacy", "Caps", "Paduck", "Markoon"]
        leaguepedia = pd.DataFrame([
            {"plug": "Caps", "Lolpros": "https://lolpros.gg/player/caps"},
        ])
        cached = pd.DataFrame([
            {
                "joueur": "Paduck",
                "lolpros_url": "https://lolpros.gg/player/paduck",
                "last_verified": "2026-01-14T00:00:00Z",
            }
        ])

        selected = _select_players_for_refresh(
            players,
            leaguepedia_profiles=leaguepedia,
            cached_profiles=cached,
        )

        self.assertEqual(selected, ["Caps", "Paduck", "Legacy", "Markoon"])
        self.assertEqual(set(selected), set(players))


class LolprosBatchRefreshTests(unittest.IsolatedAsyncioTestCase):
    async def test_refresh_processes_all_players_across_multiple_batches(self):
        session = _FakeSession()
        players = ["Player1", "Player2", "Player3", "Player4", "Player5"]

        accounts, profiles = await fetch_lolpros_accounts_for_players(
            session,
            players,
            leaguepedia_profiles=pd.DataFrame(),
            cached_profiles=pd.DataFrame(),
            batch_size=2,
            request_interval_seconds=0,
            batch_pause_seconds=0,
        )

        self.assertEqual(len(session.calls), 5)
        self.assertEqual(len(profiles), 5)
        self.assertEqual(set(profiles["joueur"]), set(players))
        self.assertEqual(set(accounts["joueur"]), set(players))


if __name__ == "__main__":
    unittest.main()
