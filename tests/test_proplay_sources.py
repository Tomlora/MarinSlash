import unittest
from datetime import datetime, timezone

import pandas as pd

from fonctions.proplay_sources import (
    merge_proplayer_sources,
    parse_trackingthepros_accounts,
)


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


if __name__ == "__main__":
    unittest.main()
