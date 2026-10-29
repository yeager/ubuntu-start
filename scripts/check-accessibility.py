#!/usr/bin/env python3
"""Smoke-test the running GTK app's AT-SPI navigation tree."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

import gi

gi.require_version("Atspi", "2.0")
from gi.repository import Atspi


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_PAGES = {
    "Welcome",
    "Get started",
    "Tips and tricks",
    "Fix a device",
    "System guides",
    "Network and hardware",
    "Drivers",
    "Help and support",
}


def accessible_names(node, *, depth: int = 0, remaining: list[int] | None = None) -> set[str]:
    """Collect accessible names while bounding traversal of a malformed tree."""
    if remaining is None:
        remaining = [4096]
    if depth > 16 or remaining[0] <= 0:
        return set()
    remaining[0] -= 1

    names: set[str] = set()
    try:
        name = node.get_name()
        if name:
            names.add(name)
        for index in range(node.get_child_count()):
            child = node.get_child_at_index(index)
            if child:
                names.update(accessible_names(child, depth=depth + 1, remaining=remaining))
    except Exception:
        return names
    return names


def main() -> int:
    if not os.environ.get("DISPLAY") or not os.environ.get("DBUS_SESSION_BUS_ADDRESS"):
        print("Run this check inside xvfb-run and dbus-run-session.", file=sys.stderr)
        return 2

    environment = os.environ.copy()
    environment.update({"GTK_A11Y": "atspi", "GSK_RENDERER": "cairo", "LANGUAGE": "en"})
    log = tempfile.TemporaryFile(mode="w+t", encoding="utf-8")
    process = subprocess.Popen(
        [sys.executable, "src/ubuntu_start.py"],
        cwd=ROOT,
        env=environment,
        stdout=log,
        stderr=subprocess.STDOUT,
        text=True,
    )

    try:
        Atspi.init()
        deadline = time.monotonic() + 15
        found: set[str] = set()
        while time.monotonic() < deadline:
            if process.poll() is not None:
                break
            desktop = Atspi.get_desktop(0)
            for index in range(desktop.get_child_count()):
                app = desktop.get_child_at_index(index)
                if app and "Ubuntu Start" in accessible_names(app):
                    found = accessible_names(app)
                    break
            if EXPECTED_PAGES.issubset(found):
                print(f"AT-SPI exposed all {len(EXPECTED_PAGES)} guide pages by name.")
                return 0
            time.sleep(0.25)

        missing = sorted(EXPECTED_PAGES - found)
        log.seek(0)
        details = log.read().strip()
        print(f"AT-SPI did not expose the expected guide pages: {', '.join(missing)}", file=sys.stderr)
        if details:
            print(details, file=sys.stderr)
        return 1
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        log.close()


if __name__ == "__main__":
    raise SystemExit(main())
