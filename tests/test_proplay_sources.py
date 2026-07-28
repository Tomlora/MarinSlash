import unittest
from datetime import datetime, timezone

import pandas as pd

from fonctions.proplay_sources import (
    merge_proplayer_sources,
    parse_trackingthepros_accounts,
)
from fonctions.leaguepedia_pro import (
    fetch_leaguepedia_players,
    fetch_leaguepedia_players_by_name,
)
from fonctions.lolpros import merge_account_sources, parse_lolpros_accounts


class ProplaySourceTests(unittest.TestCase):
    def test_leaguepedia_overrides_team_without_trackingthepros(self):
        existing = pd.DataFrame([
            {
                "plug": "Markoon",
                "current": "EUW",
                "home": "EUW",
                "role": "Jungle",
                "accounts": 2,
                "team_plug": "Solary",
                "rankHigh": "Challenger",
                "rankHighNum": 1,
                "rankHighLP": 1000,
                "rankHighLPNum": 1,
                "Pays": "Netherlands",
                "update": datetime(2025, 1, 1, tzinfo=timezone.utc),
            }
        ]).set_index("plug")
        leaguepedia = pd.DataFrame([
            {
                "plug": "Markoon",
                "Nom": "Mark van Woensel",
                "Pays": "Netherlands",
                "Rôle": "Jungle",
                "Ligue": "Prime League 1st Division",
                "team_plug": "G2 NORD",
                "SoloqueueIds": "Markoon, ikklapjouwII",
                "Lolpros": "https://lolpros.gg/player/markoon",
            }
        ])

        result = merge_proplayer_sources(
            existing,
            pd.DataFrame(),
            leaguepedia,
            updated_at=datetime(2026, 7, 26, tzinfo=timezone.utc),
        )

        markoon = result.loc[result["plug"] == "Markoon"].iloc[0]
        self.assertEqual(markoon["team_plug"], "G2 NORD")
        self.assertEqual(markoon["role"], "Jungle")
        self.assertEqual(markoon["accounts"], 2)

    def test_leaguepedia_can_add_player_absent_from_trackingthepros(self):
        leaguepedia = pd.DataFrame([
            {
                "plug": "NewPlayer",
                "Nom": "New Player",
                "Pays": "France",
                "Rôle": "ADC",
                "Ligue": "La Ligue Française",
                "team_plug": "New Team",
            }
        ])

        result = merge_proplayer_sources(
            pd.DataFrame(),
            pd.DataFrame(),
            leaguepedia,
            updated_at=datetime(2026, 7, 26, tzinfo=timezone.utc),
        )

        player = result.loc[result["plug"] == "NewPlayer"].iloc[0]
        self.assertEqual(player["team_plug"], "New Team")
        self.assertEqual(player["Pays"], "France")

    def test_account_parser_does_not_depend_on_second_html_table(self):
        html = """
        <table>
          <tr><th>Accounts</th></tr>
          <tr><td>[EUW] Markoon#EUW</td></tr>
          <tr><td>[KR] Inactive old-account</td></tr>
        </table>
        """

        result = parse_trackingthepros_accounts(html, "Markoon")

        self.assertEqual(len(result), 1)
        self.assertEqual(result.iloc[0]["joueur"], "Markoon")
        self.assertEqual(result.iloc[0]["compte"], "Markoon#EUW")
        self.assertEqual(result.iloc[0]["region"], "EUW")

    def test_lolpros_only_returns_current_accounts(self):
        html = """
        <html><body>
          <h1>Markoon</h1>
          <div>Netherlands</div>
          <a>Michiel deRuyter#NLNLN</a>
          <a>ikklapjouwII#EUW</a>
          <h4>Current Rank</h4>
          <div>Challenger</div>
          <h4>Summoner Names</h4>
          <div>Barkoon#bark</div>
          <div>Markoon#EUW</div>
        </body></html>
        """

        result = parse_lolpros_accounts(html, "Markoon")

        self.assertEqual(
            result["compte"].tolist(),
            ["Michiel deRuyter#NLNLN", "ikklapjouwII#EUW"],
        )
        self.assertEqual(result["region"].tolist(), ["EUW", "EUW"])

    def test_account_sources_are_deduplicated(self):
        lolpros = pd.DataFrame([
            {"joueur": "Markoon", "compte": "Michiel deRuyter#NLNLN", "region": "EUW"},
            {"joueur": "Markoon", "compte": "ikklapjouwII#EUW", "region": "EUW"},
        ])
        tracking = pd.DataFrame([
            {"joueur": "Markoon", "compte": "Michiel deRuyter#NLNLN", "region": "euw"},
        ])

        result = merge_account_sources(lolpros, tracking)

        self.assertEqual(len(result), 2)
        self.assertEqual(set(result["region"]), {"EUW"})


class _FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def raise_for_status(self):
        return None

    async def json(self, content_type=None):
        return self.payload


class _FakeSession:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return _FakeResponse(self.payload)


class LeaguepediaQueryTests(unittest.IsolatedAsyncioTestCase):
    async def test_direct_player_lookup_does_not_depend_on_tournaments(self):
        session = _FakeSession({
            "cargoquery": [{
                "title": {
                    "Player": "Caps",
                    "Name": "Rasmus Borregaard Winther",
                    "Country": "Denmark",
                    "Role": "Mid",
                    "Team": "G2 Esports",
                    "Lolpros": "https://lolpros.gg/player/caps",
                }
            }]
        })

        result = await fetch_leaguepedia_players_by_name(session, ["Caps"])

        self.assertEqual(result.iloc[0]["plug"], "Caps")
        self.assertEqual(result.iloc[0]["team_plug"], "G2 Esports")
        params = session.calls[0][1]["params"]
        self.assertEqual(params["tables"], "PlayerRedirects,Players")
        self.assertIn("PlayerRedirects.AllName='Caps'", params["where"])

    async def test_roster_query_uses_current_leaguepedia_redirect_join(self):
        session = _FakeSession({
            "cargoquery": [{
                "title": {
                    "Player": "Markoon",
                    "Name": "Mark van Woensel",
                    "Country": "Netherlands",
                    "Role": "Jungle",
                    "League": "Prime League Pro Division",
                    "Team": "G2 NORD",
                    "Lolpros": "https://lolpros.gg/player/markoon",
                }
            }]
        })

        result = await fetch_leaguepedia_players(
            session,
            ["Prime League Pro Division"],
        )

        self.assertEqual(result.iloc[0]["plug"], "Markoon")
        params = session.calls[0][1]["params"]
        self.assertIn(
            "TournamentPlayers.Link=PlayerRedirects.AllName",
            params["join_on"],
        )


if __name__ == "__main__":
    unittest.main()
