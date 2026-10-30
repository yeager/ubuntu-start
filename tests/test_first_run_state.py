import json
import os
import tempfile
import unittest
from pathlib import Path

from first_run_state import TASK_IDS, load_completed_tasks, save_completed_tasks


class FirstRunStateTests(unittest.TestCase):
    def test_missing_state_starts_with_an_empty_checklist(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(load_completed_tasks(Path(directory) / "first-run.json"), set())

    def test_completed_tasks_round_trip_with_private_file_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state" / "first-run.json"

            self.assertTrue(save_completed_tasks({"network", "backups", "security", "accessibility"}, path))

            self.assertEqual(load_completed_tasks(path), {"network", "backups", "security", "accessibility"})
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(path.parent.stat().st_mode & 0o777, 0o700)

    def test_unknown_task_ids_are_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "first-run.json"
            path.write_text(json.dumps({
                "schema_version": 1,
                "completed": ["network", "unknown", None, 4],
            }), encoding="utf-8")

            self.assertEqual(load_completed_tasks(path), {"network"})
            self.assertLessEqual(load_completed_tasks(path), TASK_IDS)

    def test_corrupt_or_unsupported_state_is_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "first-run.json"
            path.write_text("not json", encoding="utf-8")
            self.assertEqual(load_completed_tasks(path), set())

            path.write_text(json.dumps({"schema_version": 2, "completed": ["network"]}), encoding="utf-8")
            self.assertEqual(load_completed_tasks(path), set())

    def test_save_replaces_previous_progress_and_discards_unknown_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "first-run.json"
            self.assertTrue(save_completed_tasks({"network", "updates"}, path))
            self.assertTrue(save_completed_tasks({"privacy", "unknown"}, path))

            self.assertEqual(load_completed_tasks(path), {"privacy"})

    def test_save_reports_an_unwritable_state_location(self):
        with tempfile.TemporaryDirectory() as directory:
            blocker = Path(directory) / "not-a-directory"
            blocker.write_text("", encoding="utf-8")

            self.assertFalse(save_completed_tasks({"network"}, blocker / "first-run.json"))

    def test_default_state_path_respects_absolute_xdg_state_home(self):
        with tempfile.TemporaryDirectory() as directory:
            state_home = Path(directory) / "state"
            previous = os.environ.get("XDG_STATE_HOME")
            os.environ["XDG_STATE_HOME"] = str(state_home)
            try:
                self.assertTrue(save_completed_tasks({"network"}))
                self.assertEqual(
                    load_completed_tasks(), {"network"},
                )
                self.assertTrue((state_home / "ubuntu-start" / "first-run.json").is_file())
            finally:
                if previous is None:
                    os.environ.pop("XDG_STATE_HOME", None)
                else:
                    os.environ["XDG_STATE_HOME"] = previous


if __name__ == "__main__":
    unittest.main()
