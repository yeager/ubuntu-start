from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from shutil import copyfile

from scripts.check_release_tag import expected_versions, validate_tag


ROOT = Path(__file__).resolve().parents[1]


class ReleaseTagTests(unittest.TestCase):
    def test_current_release_tag_matches_all_version_sources(self):
        version = expected_versions(ROOT)[0]
        valid, message = validate_tag(f"v{version}", ROOT)
        self.assertTrue(valid, message)

    def test_rejects_tag_with_wrong_version(self):
        valid, message = validate_tag("v0.0.0", ROOT)
        self.assertFalse(valid)
        self.assertIn("does not match project version", message)

    def test_rejects_non_semver_tag(self):
        valid, message = validate_tag("vlatest", ROOT)
        self.assertFalse(valid)
        self.assertIn("vMAJOR.MINOR.PATCH", message)

    def test_rejects_disagreement_between_project_versions(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            for relative in (
                "pyproject.toml",
                "meson.build",
                "data/se.danielnylander.UbuntuStart.metainfo.xml",
            ):
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                copyfile(ROOT / relative, target)
            meson = root / "meson.build"
            current_version = expected_versions(ROOT)[0]
            meson.write_text(
                meson.read_text(encoding="utf-8").replace(current_version, "0.0.1", 1),
                encoding="utf-8",
            )
            valid, message = validate_tag(f"v{current_version}", root)
        self.assertFalse(valid)
        self.assertIn("metadata disagrees", message)


if __name__ == "__main__":
    unittest.main()
