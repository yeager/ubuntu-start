"""Private local persistence for the optional first-run checklist."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile


SCHEMA_VERSION = 1
TASK_IDS = frozenset({
    "language-keyboard",
    "network",
    "updates",
    "sound-display",
    "privacy",
    "accessibility",
})


def _state_path(path: str | Path | None = None) -> Path:
    if path is not None:
        return Path(path)
    state_home = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
    if not state_home.is_absolute():
        state_home = Path.home() / ".local/state"
    return state_home / "ubuntu-start" / "first-run.json"


def load_completed_tasks(path: str | Path | None = None) -> set[str]:
    """Load recognized completed task IDs; malformed or old state is ignored."""
    try:
        with _state_path(path).open(encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError, TypeError):
        return set()
    if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
        return set()
    completed = payload.get("completed")
    if not isinstance(completed, list):
        return set()
    return {
        task_id for task_id in completed
        if isinstance(task_id, str) and task_id in TASK_IDS
    }


def save_completed_tasks(
    completed: set[str] | list[str] | tuple[str, ...],
    path: str | Path | None = None,
) -> bool:
    """Atomically save recognized task IDs in a user-private state file."""
    if not isinstance(completed, (set, list, tuple)):
        return False
    values = sorted({task_id for task_id in completed if isinstance(task_id, str) and task_id in TASK_IDS})
    destination = _state_path(path)
    descriptor = None
    temporary_path = None
    try:
        destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        descriptor, temporary_path = tempfile.mkstemp(prefix="first-run-", dir=destination.parent)
        os.fchmod(descriptor, 0o600)
        handle = os.fdopen(descriptor, "w", encoding="utf-8")
        descriptor = None
        with handle:
            json.dump({"schema_version": SCHEMA_VERSION, "completed": values}, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, destination)
        temporary_path = None
        return True
    except OSError:
        return False
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass
        if temporary_path:
            try:
                os.unlink(temporary_path)
            except OSError:
                pass
