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
BUTTON_ROLES = {"button", "push button"}
ENTRY_ROLES = {"entry", "text"}


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
                (
                    node for role, name, node in entries
                    if role in BUTTON_ROLES and name == "About"
                ),
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
                def select_page(page_name: str) -> bool:
                    page_index = next(
                        (
                            index for index in range(sidebar.get_child_count())
                            if (item := sidebar.get_child_at_index(index))
                            and item.get_name() == page_name
                        ),
                        None,
                    )
                    return bool(
                        selection and page_index is not None and selection.select_child(page_index)
                    )

                if not select_page("Network and hardware"):
                    missing.append("selectable Network and hardware guide")
                else:
                    usb_deadline = time.monotonic() + 5
                    usb_refresh_button = None
                    while time.monotonic() < usb_deadline:
                        entries = accessible_tree(app)
                        usb_refresh_button = next(
                            (
                                node for role, name, node in entries
                                if role in BUTTON_ROLES and name == "Refresh USB device list"
                            ),
                            None,
                        )
                        if usb_refresh_button:
                            break
                        time.sleep(0.25)
                    if usb_refresh_button is None:
                        missing.append("button: Refresh USB device list on Network and hardware")
                    video_deadline = time.monotonic() + 5
                    camera_guide_button = None
                    while time.monotonic() < video_deadline:
                        entries = accessible_tree(app)
                        video_refresh_button = next(
                            (
                                node for role, name, node in entries
                                if role in BUTTON_ROLES and name == "Refresh video device status"
                            ),
                            None,
                        )
                        camera_guide_button = next(
                            (
                                node for role, name, node in entries
                                if role in BUTTON_ROLES and name == "Open camera guide"
                            ),
                            None,
                        )
                        if video_refresh_button and camera_guide_button:
                            break
                        time.sleep(0.25)
                    if video_refresh_button is None:
                        missing.append("button: Refresh video device status on Network and hardware")
                    if camera_guide_button is None:
                        missing.append("button: Open camera guide on Network and hardware")
                    memory_deadline = time.monotonic() + 5
                    memory_refresh_button = None
                    while time.monotonic() < memory_deadline:
                        entries = accessible_tree(app)
                        memory_refresh_button = next(
                            (
                                node for role, name, node in entries
                                if role in BUTTON_ROLES and name == "Refresh memory status"
                            ),
                            None,
                        )
                        if memory_refresh_button:
                            break
                        time.sleep(0.25)
                    if memory_refresh_button is None:
                        missing.append("button: Refresh memory status on Network and hardware")
                    pressure_deadline = time.monotonic() + 5
                    pressure_refresh_button = None
                    while time.monotonic() < pressure_deadline:
                        entries = accessible_tree(app)
                        pressure_refresh_button = next(
                            (
                                node for role, name, node in entries
                                if role in BUTTON_ROLES and name == "Refresh system pressure"
                            ),
                            None,
                        )
                        if pressure_refresh_button:
                            break
                        time.sleep(0.25)
                    if pressure_refresh_button is None:
                        missing.append("button: Refresh system pressure on Network and hardware")
                if not select_page("Welcome"):
                    missing.append("selectable Welcome guide before Ctrl+F")

        if not missing:
            try:
                window_search = subprocess.run(
                    ["xdotool", "search", "--onlyvisible", "--name", "^Ubuntu Start$"],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=3,
                )
                window_id = window_search.stdout.splitlines()[0]
                subprocess.run(["xdotool", "windowfocus", window_id], check=True, timeout=3)
                subprocess.run(["xdotool", "key", "ctrl+f"], check=True, timeout=3)
            except (OSError, subprocess.SubprocessError, IndexError) as error:
                missing.append(f"Ctrl+F could not be sent to the application window: {error}")

        if not missing:
            focus_deadline = time.monotonic() + 5
            while time.monotonic() < focus_deadline:
                entries = accessible_tree(app)
                search_entry = next(
                    (
                        node for role, name, node in entries
                        if role in ENTRY_ROLES and name == "Search all guides and steps"
                    ),
                    None,
                )
                if search_entry and search_entry.get_state_set().contains(Atspi.StateType.FOCUSED):
                    print(
                        "AT-SPI verified guide names, About, USB, video, memory and system-pressure controls, and the labeled search entry; "
                        "Ctrl+F moved focus to search."
                    )
                    return 0
                time.sleep(0.25)
            missing.append("focused search entry after Ctrl+F")

        log.seek(0)
        details = log.read().strip()
        print(f"AT-SPI did not expose expected controls: {', '.join(missing)}", file=sys.stderr)
        observed_controls = [
            (role, name)
            for role, name, _node in entries
            if name in {"About", "Refresh USB device list", "Refresh video device status", "Open camera guide", "Refresh memory status", "Refresh system pressure", "Search all guides and steps"}
        ]
        if observed_controls:
            print(f"Observed accessible roles and names: {observed_controls!r}", file=sys.stderr)
        relevant_controls = [
            (role, name)
            for role, name, _node in entries
            if any(term in name.casefold() for term in ("camera", "video device"))
        ]
        if relevant_controls:
            print(f"Observed camera/video controls: {relevant_controls!r}", file=sys.stderr)
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
