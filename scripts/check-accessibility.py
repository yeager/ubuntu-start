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


def accessible_tree(
    node, *, depth: int = 0, remaining: list[int] | None = None,
) -> list[tuple[str, str, object]]:
    """Collect accessible roles and names while bounding tree traversal."""
    if remaining is None:
        remaining = [4096]
    if depth > 16 or remaining[0] <= 0:
        return []
    remaining[0] -= 1

    try:
        name = node.get_name()
        role = node.get_role_name()
        child_count = node.get_child_count()
    except Exception:
        return []

    entries = [(role, name, node)] if name else []
    for index in range(child_count):
        try:
            child = node.get_child_at_index(index)
        except Exception:
            continue
        if child:
            entries.extend(accessible_tree(child, depth=depth + 1, remaining=remaining))
    return entries


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
        app = None
        entries: list[tuple[str, str, object]] = []
        while time.monotonic() < deadline:
            if process.poll() is not None:
                break
            desktop = Atspi.get_desktop(0)
            for index in range(desktop.get_child_count()):
                candidate = desktop.get_child_at_index(index)
                if not candidate:
                    continue
                candidate_entries = accessible_tree(candidate)
                if ("frame", "Ubuntu Start") in {
                    (role, name) for role, name, _node in candidate_entries
                }:
                    app = candidate
                    entries = candidate_entries
                    break
            names_and_roles = {(role, name) for role, name, _node in entries}
            if app and all(("list item", page) in names_and_roles for page in EXPECTED_PAGES):
                break
            time.sleep(0.25)

        if app is None:
            print("AT-SPI did not expose the Ubuntu Start application window.", file=sys.stderr)
            return 1

        names_and_roles = {(role, name) for role, name, _node in entries}
        missing = sorted(page for page in EXPECTED_PAGES if ("list item", page) not in names_and_roles)
        if not missing:
            about_button = next(
                (node for role, name, node in entries if (role, name) == ("button", "About")),
                None,
            )
            sidebar = next(
                (node for role, name, node in entries if (role, name) == ("list", "Sidebar")),
                None,
            )
            if about_button is None:
                missing.append("button: About")
            if sidebar is None:
                missing.append("sidebar")
            else:
                selection = sidebar.get_selection_iface()
                fix_index = next(
                    (
                        index for index in range(sidebar.get_child_count())
                        if (item := sidebar.get_child_at_index(index))
                        and item.get_name() == "Fix a device"
                    ),
                    None,
                )
                if selection is None or fix_index is None or not selection.select_child(fix_index):
                    missing.append("selectable Fix a device guide")

        if not missing:
            search_deadline = time.monotonic() + 5
            while time.monotonic() < search_deadline:
                entries = accessible_tree(app)
                if ("entry", "Search all guides and steps") in {
                    (role, name) for role, name, _node in entries
                }:
                    print(
                        "AT-SPI exposed all guide names, the About button, "
                        "and the labeled guide-search entry."
                    )
                    return 0
                time.sleep(0.25)
            missing.append("entry: Search all guides and steps")

        log.seek(0)
        details = log.read().strip()
        print(f"AT-SPI did not expose expected controls: {', '.join(missing)}", file=sys.stderr)
        observed_controls = [
            (role, name)
            for role, name, _node in entries
            if name in {"About", "Search all guides and steps"}
        ]
        if observed_controls:
            print(f"Observed accessible roles and names: {observed_controls!r}", file=sys.stderr)
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
