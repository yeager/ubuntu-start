from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ReadmeHistoryTests(unittest.TestCase):
    def test_validation_notes_are_in_descending_version_order(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        validation = readme.split("## Validation\n\n", 1)[1].split("\nThe CI workflow", 1)[0]
        versions = re.findall(r"^Version `(\d+\.\d+\.\d+)`", validation, re.MULTILINE)
        numeric_versions = [tuple(map(int, version.split("."))) for version in versions]

        self.assertTrue(versions)
        self.assertEqual(numeric_versions, sorted(numeric_versions, reverse=True))
        self.assertIn("0.3.48", versions)
        following_sections = readme.split("## Localization", 1)[1]
        self.assertIsNone(re.search(r"(?m)^Version `\d+\.\d+\.\d+`", following_sections))


if __name__ == "__main__":
    unittest.main()
