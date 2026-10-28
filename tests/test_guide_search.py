import unittest

from guide_search import find_guide_matches


class GuideSearchTests(unittest.TestCase):
    def setUp(self):
        self.entries = [
            ("device", 0, "Wi-Fi", "Reconnect to the network", "Enter the network password carefully."),
            ("system", 0, "Use the screen reader", "Turn on the screen reader", "Enable Orca in Accessibility settings."),
            ("system", 1, "Use visual sound alerts", "Turn on Visual Alerts", "The screen flashes for a sound notification."),
            ("system", 2, "Hjälpmedel", "Förstora text", "Öka textstorleken i Inställningar."),
        ]

    def test_matches_terms_across_guide_and_step_text(self):
        matches = find_guide_matches("WIFI password", self.entries)
        self.assertEqual(matches, [self.entries[0]])

    def test_finds_step_by_instruction_text(self):
        matches = find_guide_matches("enable Orca", self.entries)
        self.assertEqual(matches, [self.entries[1]])

    def test_matches_any_guide_category(self):
        matches = find_guide_matches("visual notification", self.entries)
        self.assertEqual(matches, [self.entries[2]])

    def test_ignores_diacritics_in_swedish_search(self):
        matches = find_guide_matches("hjalpmedel forstora", self.entries)
        self.assertEqual(matches, [self.entries[3]])

    def test_requires_every_search_term(self):
        self.assertEqual(find_guide_matches("wifi Orca", self.entries), [])

    def test_empty_query_has_no_results(self):
        self.assertEqual(find_guide_matches("  \t ", self.entries), [])


if __name__ == "__main__":
    unittest.main()
