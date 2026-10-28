import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "scripts" / "check-staged-install.sh"
DESKTOP_FILE = "usr/share/applications/se.nylander.UbuntuStart.desktop"
LAUNCHER = "Exec=python3 /usr/libexec/ubuntu-start/ubuntu_start.py"
SWEDISH_COMMENT = "Comment[sv]=Kom igång med Ubuntu och felsök anslutna enheter"
REQUIRED_FILES = (
    "usr/libexec/ubuntu-start/ubuntu_start.py",
    "usr/libexec/ubuntu-start/system_diagnostics.py",
    "usr/libexec/ubuntu-start/guide_search.py",
    DESKTOP_FILE,
    "usr/share/metainfo/se.nylander.UbuntuStart.metainfo.xml",
    "usr/share/icons/hicolor/scalable/apps/se.nylander.UbuntuStart.svg",
    "usr/share/locale/sv/LC_MESSAGES/ubuntu-start.mo",
)


class StagedInstallTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.stage = Path(self.temporary.name)
        for relative_path in REQUIRED_FILES:
            path = self.stage / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("", encoding="utf-8")
        (self.stage / DESKTOP_FILE).write_text(
            f"[Desktop Entry]\n{LAUNCHER}\n{SWEDISH_COMMENT}\n", encoding="utf-8"
        )

    def tearDown(self):
        self.temporary.cleanup()

    def run_checker(self):
        return subprocess.run(
            ["sh", str(CHECKER), str(self.stage)],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_accepts_complete_install_with_matching_launcher(self):
        result = self.run_checker()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_reports_missing_installed_file(self):
        (self.stage / REQUIRED_FILES[-1]).unlink()
        result = self.run_checker()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(REQUIRED_FILES[-1], result.stderr)

    def test_rejects_launcher_with_wrong_application_path(self):
        (self.stage / DESKTOP_FILE).write_text(
            f"[Desktop Entry]\nExec=python3 /wrong/path.py\n{SWEDISH_COMMENT}\n",
            encoding="utf-8",
        )
        result = self.run_checker()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("does not point to the installed application", result.stderr)

    def test_rejects_desktop_file_without_swedish_description(self):
        (self.stage / DESKTOP_FILE).write_text(
            f"[Desktop Entry]\n{LAUNCHER}\n", encoding="utf-8"
        )
        result = self.run_checker()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing its Swedish description", result.stderr)


if __name__ == "__main__":
    unittest.main()
