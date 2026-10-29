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

    def test_returns_steps_when_query_terms_span_one_guide(self):
        entries = [
            ("device", 4, "Network", "Check DNS", "Review the configured resolver."),
            ("device", 4, "Network", "Check the gateway", "Ping the local gateway."),
            ("device", 5, "Bluetooth", "Pair a device", "Check pairing mode."),
        ]

        self.assertEqual(
            find_guide_matches("DNS gateway", entries),
            entries[:2],
        )

    def test_guide_title_search_returns_its_steps(self):
        entries = [
            ("device", 4, "Wi-Fi", "Check the password", "Enter the password carefully."),
            ("device", 4, "Wi-Fi", "Move closer", "Reduce distance from the router."),
        ]

        self.assertEqual(find_guide_matches("Wi-Fi", entries), entries)

    def test_does_not_match_a_query_inside_the_middle_of_a_word(self):
        self.assertEqual(find_guide_matches("sual alert", self.entries), [])

    def test_matches_word_prefixes(self):
        self.assertEqual(find_guide_matches("notific", self.entries), [self.entries[2]])

    def test_matches_keyboard_shortcuts_with_punctuation(self):
        entries = [
            ("system", 0, "Use the Terminal", "Copy and paste", "Copy with Ctrl+Shift+C and paste with Ctrl+Shift+V."),
            ("system", 0, "Use the Terminal", "Stop a command", "Press Ctrl+C."),
        ]

        self.assertEqual(find_guide_matches("Ctrl+Shift+C", entries), [entries[0]])
        self.assertEqual(find_guide_matches("Ctrl+C", entries), [entries[1]])

    def test_duplicate_guide_entries_are_returned_once(self):
        entry = (
            "device", 7, "Network", "Check DNS", "Review the configured resolver.",
        )

        self.assertEqual(find_guide_matches("DNS", [entry, entry]), [entry])

    def test_empty_query_has_no_results(self):
        self.assertEqual(find_guide_matches("  \t ", self.entries), [])


if __name__ == "__main__":
    unittest.main()
