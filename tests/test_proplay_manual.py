import unittest

from fonctions.proplay_manual import (
    ManualProplayError,
    normalize_optional_text,
    normalize_region,
    normalize_riot_id,
    normalize_role,
)


class ManualProplayValidationTests(unittest.TestCase):
    def test_riot_id_is_trimmed_without_losing_internal_spaces(self):
        self.assertEqual(
            normalize_riot_id("  Right Hand # korea  "),
            "Right Hand#korea",
        )

    def test_riot_id_requires_exactly_one_separator(self):
        for invalid in ("Kiki", "Kiki#mates#EUW", "#mates", "Kiki#"):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ManualProplayError):
                    normalize_riot_id(invalid)

    def test_role_aliases_are_normalized(self):
        self.assertEqual(normalize_role("bot"), "ADC")
        self.assertEqual(normalize_role("jg"), "Jungle")
        self.assertEqual(normalize_role("Support"), "Support")

    def test_region_is_uppercase_and_validated(self):
        self.assertEqual(normalize_region("euw"), "EUW")
        self.assertEqual(normalize_region("kr"), "KR")
        with self.assertRaises(ManualProplayError):
            normalize_region("EU-W")

    def test_optional_fields_accept_explicit_empty_values(self):
        self.assertIsNone(normalize_optional_text("-", label="équipe"))
        self.assertIsNone(normalize_optional_text("Aucune", label="équipe"))
        self.assertEqual(
            normalize_optional_text("  G2 Esports  ", label="équipe"),
            "G2 Esports",
        )


if __name__ == "__main__":
    unittest.main()
