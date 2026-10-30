import unittest
import ast
from pathlib import Path

from guide_search import find_guide_matches


def load_system_guides_without_gtk():
    source = Path(__file__).resolve().parents[1] / "src" / "ubuntu_start.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    assignment = next(
        node for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "SYSTEM_GUIDES" for target in node.targets)
    )
    return eval(compile(ast.Expression(assignment.value), str(source), "eval"), {"__builtins__": {}, "_": lambda value: value})


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


class SecurityGuideSearchTests(unittest.TestCase):
    def setUp(self):
        guides = load_system_guides_without_gtk()
        self.guide_index, self.guide = next(
            (index, guide) for index, guide in enumerate(guides)
            if guide[0] == "Improve everyday security"
        )
        self.title, _target, _action, self.steps = self.guide
        self.entries = [
            ("system", self.guide_index, "Security and privacy guide", step_title, description)
            for step_title, description in self.steps
        ]

    def test_core_security_topics_are_searchable(self):
        for query in (
            "security updates", "automatic unattended", "waiting updates",
            "password account", "administrator prompts", "passkey requests",
            "firewall", "backup", "privacy sharing", "Secure Boot",
            "compromised account", "suspicious messages", "computer stolen",
            "malware ransomware", "public Wi-Fi hotspot VPN",
            "unsolicited remote support scam",
        ):
            with self.subTest(query=query):
                self.assertTrue(find_guide_matches(query, self.entries))

    def test_core_security_advice_remains_specific_and_cautious(self):
        text = " ".join(f"{step_title} {description}" for step_title, description in self.steps)
        expected_advice = (
            "Ubuntu Desktop does not always include a firewall management tool",
            "This app checks UFW only; it cannot tell whether another firewall is active",
            "Do not install or enable a firewall blindly",
            "Never share passwords or sign-in codes",
            "Use a standard, non-administrator account for everyday tasks",
            "Cancel unexpected prompts",
            "do not try to enable it on an existing system",
            "Disconnect a backup drive when it is not in use",
            "If it is off, consult your computer manufacturer or administrator",
            "From a trusted device, change the affected account password",
            "Check the address carefully, and never ignore a browser certificate warning",
            "screen locking alone does not encrypt its storage",
            "disconnect it from Wi-Fi or wired networks",
            "Do not delete files, run cleanup tools, pay a ransom or connect backup drives",
            "Restore files only from a known-good backup",
            "Confirm the network name and sign-in steps with the venue",
            "prefer your own mobile hotspot or a VPN from your organization",
            "A VPN does not make a fake hotspot or sign-in page trustworthy",
            "turn off remote desktop or file sharing you do not need",
            "pressure you to install remote-access software, share sign-in codes or run terminal commands",
            "reach support through the organisation’s official website or a phone number you already trust",
            "Never grant remote access or share a one-time code because someone contacted you",
        )
        for advice in expected_advice:
            with self.subTest(advice=advice):
                self.assertIn(advice, text)
        self.assertEqual(self.title, "Improve everyday security")


if __name__ == "__main__":
    unittest.main()
