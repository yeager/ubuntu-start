import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ReleaseWorkflowTests(unittest.TestCase):
    def test_pypi_job_has_read_access_for_checkout_and_oidc_for_publishing(self):
        workflow = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
        match = re.search(
            r"(?ms)^  pypi-publish:\n(?P<job>.*?)(?=^  [a-zA-Z0-9_-]+:|\Z)",
            workflow,
        )
        self.assertIsNotNone(match, "PyPI publishing job is missing")
        job = match.group("job")
        self.assertRegex(job, r"(?m)^      contents: read$")
        self.assertRegex(job, r"(?m)^      id-token: write$")


if __name__ == "__main__":
    unittest.main()
