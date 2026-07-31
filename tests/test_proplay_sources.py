import unittest
from datetime import datetime, timezone

import pandas as pd

from fonctions.proplay_sources import (
    merge_proplayer_sources,
    parse_trackingthepros_accounts,
)
from fonctions.leaguepedia_pro import (
    LeaguepediaCargoError,
    _raise_for_cargo_error,
    fetch_leaguepedia_players,
    fetch_leaguepedia_players_by_name,
)
from fonctions.lolpros import merge_account_sources, parse_lolpros_accounts
from fonctions.lolpros_profiles import fetch_lolpros_accounts_for_players


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

    def test_lolpros_returns_current_and_historical_riot_ids(self):
        html = """
        <html><body>
          <section id="accounts">
            <div class="account-selector">
              <a>Michiel deRuyter#NLNLN</a>
              <a>ikklapjouwII#EUW</a>
            </div>
            <h4>Current Rank</h4>
            <div>Challenger</div>
            <div id="summoner-names">
              <h4>Summoner Names</h4>
              <div>Barkoon#bark</div>
              <div>Markoon#EUW</div>
              <div>alvarooo#000</div>
            </div>
          </section>
        </body></html>
        """

        result = parse_lolpros_accounts(html, "Markoon")

        self.assertEqual(
            result["compte"].tolist(),
            [
                "Michiel deRuyter#NLNLN",
                "ikklapjouwII#EUW",
                "Barkoon#bark",
                "Markoon#EUW",
                "alvarooo#000",
            ],
        )
        self.assertEqual(result["region"].tolist(), ["EUW"] * 5)

    def test_lolpros_paduck_account_can_only_be_in_current_rank_and_summoner_names(self):
        html = """
        <html><head>
          <meta name="description" content="Bot | South Korea | Player for Shifters | Right Hand#korea [Grandmaster 1936LP]">
        </head><body>
          <section id="accounts">
            <div id="current-elo">
              <h4>Current Rank
                <a href="https://op.gg/lol/summoners/euw/Right%20Hand-korea">
                  <img alt="op.gg" title="Right Hand#korea">
                </a>
              </h4>
            </div>
            <div id="summoner-names">
              <h4>Summoner Names</h4>
              <div><p>Right Hand#korea</p><time>14/01/26</time></div>
            </div>
          </section>
        </body></html>
        """

        result = parse_lolpros_accounts(html, "Paduck")

        self.assertEqual(result["compte"].tolist(), ["Right Hand#korea"])

    def test_lolpros_does_not_import_teammate_ids_outside_accounts_panel(self):
        html = """
        <html><body>
          <section id="accounts">
            <div>PlayerAccount#EUW</div>
          </section>
          <section id="team">
            <a title="TeammateAccount#EUW">Team OP.GG</a>
          </section>
        </body></html>
        """

        result = parse_lolpros_accounts(html, "Player")

        self.assertEqual(result["compte"].tolist(), ["PlayerAccount#EUW"])

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

    def test_fandom_json_error_is_not_silently_treated_as_empty(self):
        payload = {
            "error": {
                "code": "ratelimited",
                "info": "You've exceeded your rate limit.",
            }
        }
        with self.assertRaisesRegex(LeaguepediaCargoError, "ratelimited"):
            _raise_for_cargo_error(payload)


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


class _FakeHtmlResponse:
    def __init__(self, html, status=200):
        self.html = html
        self.status = status

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def raise_for_status(self):
        return None

    async def text(self):
        return self.html


class _FakeHtmlSession:
    def __init__(self, html):
        self.html = html
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return _FakeHtmlResponse(self.html)


class LeaguepediaQueryTests(unittest.IsolatedAsyncioTestCase):
    async def test_direct_player_lookup_uses_players_table_only(self):
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
        self.assertEqual(len(session.calls), 1)
        params = session.calls[0][1]["params"]
        self.assertEqual(params["tables"], "Players")
        self.assertIn("Players.Player IN ('Caps')", params["where"])

    async def test_roster_query_batches_multiple_leagues_into_one_request(self):
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
            ["Prime League Pro Division", "LoL EMEA Championship"],
        )

        self.assertEqual(result.iloc[0]["plug"], "Markoon")
        self.assertEqual(len(session.calls), 1)
        params = session.calls[0][1]["params"]
        self.assertIn(
            "TournamentPlayers.Link=PlayerRedirects.AllName",
            params["join_on"],
        )
        self.assertIn("Prime League Pro Division", params["where"])
        self.assertIn("LoL EMEA Championship", params["where"])

    async def test_lolpros_can_refresh_known_player_without_leaguepedia(self):
        html = """
        <html><body>
          <section id="accounts">
            <a>G2 Caps#1323</a>
            <a>A 99 mid laner#EUW</a>
            <h4>Current Rank</h4>
          </section>
        </body></html>
        """
        session = _FakeHtmlSession(html)

        accounts, profiles = await fetch_lolpros_accounts_for_players(
            session,
            ["Caps"],
            leaguepedia_profiles=pd.DataFrame(),
            cached_profiles=pd.DataFrame(),
        )

        self.assertEqual(
            accounts["compte"].tolist(),
            ["G2 Caps#1323", "A 99 mid laner#EUW"],
        )
        self.assertEqual(profiles.iloc[0]["lolpros_url"], "https://lolpros.gg/player/caps")
        self.assertEqual(session.calls[0][0], "https://lolpros.gg/player/caps")


if __name__ == "__main__":
    unittest.main()
