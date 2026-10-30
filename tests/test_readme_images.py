from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/check-readme-images.py"


class ReadmeImageCheckTests(unittest.TestCase):
    def run_check(self, markdown: str, *arguments: str) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as directory:
            readme = Path(directory) / "README.md"
            (readme.parent / "image.png").write_bytes(b"image")
            readme.write_text(markdown, encoding="utf-8")
            return subprocess.run(
                [sys.executable, str(SCRIPT), str(readme), *arguments],
                capture_output=True, text=True, check=False,
            )

    def test_allows_six_existing_images_and_ordinary_links(self):
        markdown = "\n".join(f"![Image {index}](image.png)" for index in range(6))
        markdown += "\n[More screenshots](screenshots/)\n"
        result = self.run_check(markdown)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_rejects_more_than_six_embedded_images(self):
        markdown = "\n".join(f"![Image {index}](image.png)" for index in range(7))
        result = self.run_check(markdown)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("maximum is 6", result.stderr)

    def test_rejects_missing_local_image(self):
        result = self.run_check("![Missing](missing.png)\n")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing.png", result.stderr)


if __name__ == "__main__":
    unittest.main()
