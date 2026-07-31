import unittest
from datetime import datetime, timezone

import pandas as pd

from fonctions.proplay_lolpros_override import (
    apply_manual_profile_overrides,
    merge_profile_cache_preserving_manual,
    normalize_lolpros_profile_url,
)
from fonctions.proplay_manual import ManualProplayError


class LolprosUrlValidationTests(unittest.TestCase):
    def test_normalizes_profile_url(self):
        self.assertEqual(
            normalize_lolpros_profile_url("www.lolpros.gg/player/Paduck/"),
            "https://lolpros.gg/player/Paduck",
        )

    def test_rejects_non_profile_url(self):
        with self.assertRaises(ManualProplayError):
            normalize_lolpros_profile_url("https://lolpros.gg/leagues")

    def test_rejects_foreign_domain(self):
        with self.assertRaises(ManualProplayError):
            normalize_lolpros_profile_url("https://example.com/player/paduck")


class LolprosManualPriorityTests(unittest.TestCase):
    def test_manual_url_replaces_leaguepedia_url_and_adds_missing_player(self):
        leaguepedia = pd.DataFrame(
            [
                {
                    "plug": "Caps",
                    "Lolpros": "https://lolpros.gg/player/caps-old",
                    "team_plug": "G2 Esports",
                }
            ]
        )
        cache = pd.DataFrame(
            [
                {
                    "joueur": "caps",
                    "lolpros_url": "https://lolpros.gg/player/caps-manual",
                    "manual_override": True,
                },
                {
                    "joueur": "Paduck",
                    "lolpros_url": "https://lolpros.gg/player/paduck",
                    "manual_override": True,
                },
            ]
        )

        effective = apply_manual_profile_overrides(leaguepedia, cache)
        by_player = effective.set_index(effective["plug"].str.casefold())

        self.assertEqual(
            by_player.loc["caps", "Lolpros"],
            "https://lolpros.gg/player/caps-manual",
        )
        self.assertEqual(
            by_player.loc["paduck", "Lolpros"],
            "https://lolpros.gg/player/paduck",
        )

    def test_automatic_cache_refresh_cannot_replace_manual_url(self):
        verified_at = datetime(2026, 8, 1, 1, 0, tzinfo=timezone.utc)
        existing = pd.DataFrame(
            [
                {
                    "joueur": "Paduck",
                    "lolpros_url": "https://lolpros.gg/player/paduck-manual",
                    "team_plug": "Old Team",
                    "role": "ADC",
                    "Pays": "South Korea",
                    "last_verified": None,
                    "manual_override": True,
                    "manual_updated_at": verified_at,
                }
            ]
        )
        resolved = pd.DataFrame(
            [
                {
                    "joueur": "Paduck",
                    "lolpros_url": "https://lolpros.gg/player/wrong-auto-url",
                    "team_plug": "Shifters",
                    "role": "ADC",
                    "Pays": "South Korea",
                }
            ]
        )

        merged = merge_profile_cache_preserving_manual(
            existing,
            resolved,
            verified_at=verified_at,
        )
        row = merged.iloc[0]

        self.assertEqual(
            row["lolpros_url"],
            "https://lolpros.gg/player/paduck-manual",
        )
        self.assertTrue(row["manual_override"])
        self.assertEqual(row["team_plug"], "Shifters")
        self.assertEqual(row["last_verified"], verified_at)


if __name__ == "__main__":
    unittest.main()
