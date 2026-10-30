#!/usr/bin/env python3
"""Smoke-test the running GTK app's AT-SPI navigation tree."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
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
SWEDISH_PAGES = {
    "Välkommen",
    "Kom igång",
    "Tips och knep",
    "Felsök en enhet",
    "Systemguider",
    "Nätverk och maskinvara",
    "Drivrutiner",
    "Hjälp och support",
}
BUTTON_ROLES = {"button", "push button"}
CHECKBOX_ROLES = {"check box", "checkbutton"}
ENTRY_ROLES = {"entry", "text"}


def accessible_tree(
    node, *, depth: int = 0, remaining: list[int] | None = None,
    include_unnamed: bool = False,
) -> list[tuple[str, str, object]]:
    """Collect accessible roles and names while bounding tree traversal."""
    if remaining is None:
        remaining = [4096]
    if depth > 24 or remaining[0] <= 0:
        return []
    remaining[0] -= 1

    try:
        name = node.get_name()
        role = node.get_role_name()
        child_count = node.get_child_count()
    except Exception:
        return []

    entries = [(role, name, node)] if name or include_unnamed else []
    for index in range(child_count):
        try:
            child = node.get_child_at_index(index)
        except Exception:
            continue
        if child:
            entries.extend(accessible_tree(
                child, depth=depth + 1, remaining=remaining,
                include_unnamed=include_unnamed,
            ))
    return entries


def version_detail_is_exposed(app, page_name: str, label: str) -> bool:
    entries = accessible_tree(app)
    sidebar = next(
        (node for role, name, node in entries if (role, name) == ("list", "Sidebar")),
        None,
    )
    if sidebar is None:
        return False
    selection = sidebar.get_selection_iface()
    page_index = next(
        (
            index for index in range(sidebar.get_child_count())
            if (item := sidebar.get_child_at_index(index))
            and item.get_name() == page_name
        ),
        None,
    )
    if not selection or page_index is None or not selection.select_child(page_index):
        return False

    try:
        project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    except OSError:
        return False
    version_match = re.search(r'(?m)^version\s*=\s*"([^"\n]+)"\s*$', project)
    if not version_match:
        return False
    expected_version = version_match.group(1)

    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        names = {name for _role, name, _node in accessible_tree(app)}
        if label in names and expected_version in names:
            return True
        time.sleep(0.25)
    return False


def select_sidebar_page(app, page_name: str) -> bool:
    """Select a named page through the exposed sidebar selection interface."""
    entries = accessible_tree(app)
    sidebar = next(
        (node for role, name, node in entries if (role, name) == ("list", "Sidebar")),
        None,
    )
    if sidebar is None:
        return False
    selection = sidebar.get_selection_iface()
    page_index = next(
        (
            index for index in range(sidebar.get_child_count())
            if (item := sidebar.get_child_at_index(index))
            and item.get_name() == page_name
        ),
        None,
    )
    return bool(selection and page_index is not None and selection.select_child(page_index))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--localized-smoke",
        choices=("sv",),
        help="check that a localized UI exposes translated labels through AT-SPI",
    )
    parser.add_argument(
        "--screenshot",
        type=Path,
        help="capture the live Ubuntu Start window after opening Get started",
    )
    args = parser.parse_args()

    if not os.environ.get("DISPLAY") or not os.environ.get("DBUS_SESSION_BUS_ADDRESS"):
        print("Run this check inside xvfb-run and dbus-run-session.", file=sys.stderr)
        return 2

    language = args.localized_smoke or "en"
    localized_smoke = args.localized_smoke is not None
    environment = os.environ.copy()
    benchmark_tools = tempfile.TemporaryDirectory(prefix="ubuntu-start-benchmark-tools-")
    locale_dir = Path(benchmark_tools.name, "locale")
    if language == "sv":
        catalog_dir = locale_dir / "sv" / "LC_MESSAGES"
        catalog_dir.mkdir(parents=True)
        subprocess.run(
            [
                "msgfmt", "--check", "--check-format",
                str(ROOT / "po" / "sv.po"),
                "-o", str(catalog_dir / "ubuntu-start.mo"),
            ],
            check=True,
        )
        environment["UBUNTU_START_LOCALEDIR"] = str(locale_dir)
    environment.update({"GTK_A11Y": "atspi", "GSK_RENDERER": "cairo", "LANGUAGE": language})
    environment["XDG_STATE_HOME"] = str(Path(benchmark_tools.name, "state"))
    delayed_benchmark_marker = Path(benchmark_tools.name, "delay-once")
    environment["UBUNTU_START_BENCHMARK_DELAY_ONCE"] = str(delayed_benchmark_marker)
    for tool_name in ("glmark2", "glmark2-wayland"):
        fake_tool = Path(benchmark_tools.name, tool_name)
        fake_tool.write_text(
            "#!/bin/sh\n"
            "if [ -f \"$UBUNTU_START_BENCHMARK_DELAY_ONCE\" ]; then\n"
            "  rm -f \"$UBUNTU_START_BENCHMARK_DELAY_ONCE\"\n"
            "  exec sleep 30\n"
            "fi\n"
            "printf '%s\\n' 'glmark2 Score: 4242'\n",
            encoding="utf-8",
        )
        fake_tool.chmod(0o755)
    environment["PATH"] = benchmark_tools.name + os.pathsep + environment.get("PATH", "")
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
        expected_pages = SWEDISH_PAGES if language == "sv" else EXPECTED_PAGES
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
            if app and all(("list item", page) in names_and_roles for page in expected_pages):
                break
            time.sleep(0.25)

        if app is None:
            print("AT-SPI did not expose the Ubuntu Start application window.", file=sys.stderr)
            return 1

        names_and_roles = {(role, name) for role, name, _node in entries}
        missing = sorted(page for page in expected_pages if ("list item", page) not in names_and_roles)

        if localized_smoke:
            about_button = next(
                (
                    node for role, name, node in entries
                    if role in BUTTON_ROLES and name == "Om"
                ),
                None,
            )
            if about_button is None:
                missing.append("button: Om")
            if not version_detail_is_exposed(
                app, "Hjälp och support", "Ubuntu Starts version",
            ):
                missing.append("Ubuntu Starts version and value in Swedish system details")
            if not select_sidebar_page(app, "Nätverk och maskinvara"):
                missing.append("selectable Swedish Network and hardware page")
            else:
                encryption_button = False
                encryption_title = False
                encryption_deadline = time.monotonic() + 5
                while time.monotonic() < encryption_deadline:
                    entries = accessible_tree(app)
                    encryption_button = any(
                        role in BUTTON_ROLES and name == "Kontrollera kryptering av rotfilsystemet"
                        for role, name, _node in entries
                    )
                    encryption_title = any(name == "Kryptering av rotfilsystemet" for _role, name, _node in entries)
                    if encryption_button and encryption_title:
                        break
                    time.sleep(0.25)
                if not encryption_button:
                    missing.append("Swedish root filesystem encryption check button")
                if not encryption_title:
                    missing.append("Swedish root filesystem encryption status row")
            if missing:
                print(f"Missing Swedish AT-SPI entries: {missing}", file=sys.stderr)
                return 1
            print("Swedish application labels and the Ubuntu Start version row are exposed through AT-SPI.")
            return 0

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

                if not version_detail_is_exposed(
                    app, "Help and support", "Ubuntu Start version",
                ):
                    missing.append("Ubuntu Start version and value in system details")

                if not select_page("Get started"):
                    missing.append("selectable Get started page")
                else:
                    checklist_deadline = time.monotonic() + 5
                    checklist_tasks = {
                        "Language and keyboard",
                        "Internet connection",
                        "Updates",
                        "Improve everyday security",
                        "Set up backups",
                        "Sound and display",
                        "Privacy and screen lock",
                        "Accessibility",
                    }
                    checklist_controls = set()
                    while time.monotonic() < checklist_deadline:
                        entries = accessible_tree(app, include_unnamed=True)
                        checklist_controls = {
                            name for role, name, _node in entries
                            if role in CHECKBOX_ROLES and name in checklist_tasks
                        }
                        if checklist_controls == checklist_tasks:
                            break
                        time.sleep(0.25)
                    if checklist_controls != checklist_tasks:
                        observed_checklist = [
                            (role, name) for role, name, _node in entries
                            if name in checklist_tasks or "check" in role.casefold()
                        ]
                        print(f"Checklist AT-SPI entries: {observed_checklist!r}", file=sys.stderr)
                        print(
                            f"Get started AT-SPI sample: {[(role, name) for role, name, _node in entries[:100]]!r}",
                            file=sys.stderr,
                        )
                    for task in sorted(checklist_tasks - checklist_controls):
                        missing.append(f"accessible checklist checkbox: {task}")

                    checklist_guide_buttons = {
                        "Open the everyday security guide",
                        "Open the backup setup guide",
                    }
                    checklist_guide_controls = {
                        name for role, name, _node in entries
                        if role in BUTTON_ROLES and name in checklist_guide_buttons
                    }
                    for button_name in sorted(checklist_guide_buttons - checklist_guide_controls):
                        missing.append(f"button: {button_name} on Get started")

                    if args.screenshot:
                        args.screenshot.parent.mkdir(parents=True, exist_ok=True)
                        window_search = subprocess.run(
                            ["xdotool", "search", "--onlyvisible", "--name", "^Ubuntu Start$"],
                            check=True, capture_output=True, text=True,
                        )
                        window_id = window_search.stdout.splitlines()[0]
                        subprocess.run(
                            ["xdotool", "windowsize", "--sync", window_id, "1000", "1050"],
                            check=True,
                        )
                        time.sleep(1)
                        subprocess.run(
                            ["import", "-window", window_id, str(args.screenshot)],
                            check=True,
                        )
                        print(f"Captured live application screenshot: {args.screenshot}")

                    reset_checklist = next(
                        (
                            node for role, name, node in entries
                            if role in BUTTON_ROLES and name == "Reset checklist"
                        ),
                        None,
                    )
                    if reset_checklist is None:
                        missing.append("button: Reset checklist on Get started")

                    accessibility_deadline = time.monotonic() + 5
                    mouse_keys_status = None
                    while time.monotonic() < accessibility_deadline:
                        entries = accessible_tree(app)
                        mouse_keys_status = next(
                            (
                                node for _role, name, node in entries
                                if name == "Mouse Keys"
                            ),
                            None,
                        )
                        if mouse_keys_status:
                            break
                        time.sleep(0.25)
                    if mouse_keys_status is None:
                        missing.append("Mouse Keys status row on Get started")

                    settings_deadline = time.monotonic() + 5
                    accessibility_settings_button = None
                    while time.monotonic() < settings_deadline:
                        entries = accessible_tree(app)
                        accessibility_settings_button = next(
                            (
                                node for role, name, node in entries
                                if role in BUTTON_ROLES and name == "Open Accessibility Settings"
                            ),
                            None,
                        )
                        if accessibility_settings_button:
                            break
                        time.sleep(0.25)
                    if accessibility_settings_button is None:
                        missing.append("button: Open Accessibility Settings on Get started")

                    time_guide_deadline = time.monotonic() + 5
                    time_guide_button = None
                    while time.monotonic() < time_guide_deadline:
                        entries = accessible_tree(app)
                        time_guide_button = next(
                            (
                                node for role, name, node in entries
                                if role in BUTTON_ROLES and name == "Open date and time guide"
                            ),
                            None,
                        )
                        if time_guide_button:
                            break
                        time.sleep(0.25)
                    if time_guide_button is None:
                        missing.append("button: Open date and time guide on Get started")

                if not select_page("Network and hardware"):
                    missing.append("selectable Network and hardware guide")
                else:
                    encryption_button = False
                    encryption_title = False
                    encryption_deadline = time.monotonic() + 5
                    while time.monotonic() < encryption_deadline:
                        entries = accessible_tree(app)
                        encryption_button = any(
                            role in BUTTON_ROLES and name == "Check root filesystem encryption"
                            for role, name, _node in entries
                        )
                        encryption_title = any(name == "Root filesystem encryption" for _role, name, _node in entries)
                        if encryption_button and encryption_title:
                            break
                        time.sleep(0.25)
                    if not encryption_button:
                        missing.append("button: Check root filesystem encryption on Network and hardware")
                    if not encryption_title:
                        missing.append("Root filesystem encryption status row on Network and hardware")
                    benchmark_deadline = time.monotonic() + 5
                    benchmark_names = {
                        "Check benchmark readiness",
                        "Run CPU benchmark",
                        "Run graphics benchmark",
                        "Cancel graphics benchmark",
                        "Open disk read benchmark",
                        "Open GNOME disk benchmark guide",
                        "Open optional disk write benchmark…",
                    }
                    benchmark_buttons = set()
                    readiness_button = None
                    while time.monotonic() < benchmark_deadline:
                        entries = accessible_tree(app)
                        benchmark_buttons = {
                            name for role, name, _node in entries
                            if role in BUTTON_ROLES and name in benchmark_names
                        }
                        readiness_button = next(
                            (
                                node for role, name, node in entries
                                if role in BUTTON_ROLES and name == "Check benchmark readiness"
                            ),
                            None,
                        )
                        if benchmark_buttons == benchmark_names:
                            break
                        time.sleep(0.25)
                    for name in sorted(benchmark_names - benchmark_buttons):
                        missing.append(f"button: {name} on Network and hardware")
                    wifi_check_names = {"Check Wi-Fi connection", "Open Wi-Fi Settings"}
                    wifi_check_buttons = {
                        name for role, name, _node in entries
                        if role in BUTTON_ROLES and name in wifi_check_names
                    }
                    for name in sorted(wifi_check_names - wifi_check_buttons):
                        missing.append(f"button: {name} on Network and hardware")
                    if readiness_button:
                        try:
                            activated = readiness_button.get_n_actions() > 0 and readiness_button.do_action(0)
                        except Exception:
                            activated = False
                        if not activated:
                            missing.append("benchmark readiness button could not be activated")
                        else:
                            readiness_deadline = time.monotonic() + 8
                            readiness_updated = False
                            while time.monotonic() < readiness_deadline:
                                entries = accessible_tree(app)
                                readiness_updated = any(
                                    role == "label" and name.startswith("Power profile:")
                                    for role, name, _node in entries
                                )
                                if readiness_updated:
                                    break
                                time.sleep(0.25)
                            if not readiness_updated:
                                missing.append("benchmark readiness status did not update")
                    graphics_button = next(
                        (
                            node for role, name, node in entries
                            if role in BUTTON_ROLES and name == "Run graphics benchmark"
                        ),
                        None,
                    )
                    if graphics_button:
                        try:
                            graphics_activated = graphics_button.get_n_actions() > 0 and graphics_button.do_action(0)
                        except Exception:
                            graphics_activated = False
                        if not graphics_activated:
                            missing.append("graphics benchmark button could not be activated")
                        else:
                            confirmation_deadline = time.monotonic() + 5
                            run_button = None
                            while time.monotonic() < confirmation_deadline:
                                entries = accessible_tree(app)
                                run_button = next(
                                    (
                                        node for role, name, node in entries
                                        if role in BUTTON_ROLES and name == "Run benchmark"
                                    ),
                                    None,
                                )
                                if run_button:
                                    break
                                time.sleep(0.25)
                            if run_button is None:
                                missing.append("graphics benchmark confirmation was not exposed")
                            else:
                                try:
                                    confirmed = run_button.get_n_actions() > 0 and run_button.do_action(0)
                                except Exception:
                                    confirmed = False
                                if not confirmed:
                                    missing.append("graphics benchmark confirmation could not be activated")
                                else:
                                    score_deadline = time.monotonic() + 5
                                    graphics_score_shown = False
                                    while time.monotonic() < score_deadline:
                                        entries = accessible_tree(app)
                                        graphics_score_shown = any(
                                            role == "label" and name.startswith("Graphics baseline: 4242")
                                            for role, name, _node in entries
                                        )
                                        if graphics_score_shown:
                                            break
                                        time.sleep(0.25)
                                    if not graphics_score_shown:
                                        missing.append("graphics benchmark score was not displayed")
                                    else:
                                        delayed_benchmark_marker.touch()
                                        entries = accessible_tree(app)
                                        graphics_button = next(
                                            (node for role, name, node in entries
                                             if role in BUTTON_ROLES and name == "Run graphics benchmark"),
                                            None,
                                        )
                                        try:
                                            activated = bool(
                                                graphics_button
                                                and graphics_button.get_n_actions() > 0
                                                and graphics_button.do_action(0)
                                            )
                                        except Exception:
                                            activated = False
                                        if not activated:
                                            missing.append("graphics benchmark could not be started for cancellation check")
                                        else:
                                            cancel_run_deadline = time.monotonic() + 5
                                            run_button = None
                                            while time.monotonic() < cancel_run_deadline:
                                                entries = accessible_tree(app)
                                                run_button = next(
                                                    (node for role, name, node in entries
                                                     if role in BUTTON_ROLES and name == "Run benchmark"),
                                                    None,
                                                )
                                                if run_button:
                                                    break
                                                time.sleep(0.1)
                                            if not run_button:
                                                missing.append("second graphics benchmark confirmation was not exposed")
                                            else:
                                                try:
                                                    confirmed = run_button.get_n_actions() > 0 and run_button.do_action(0)
                                                except Exception:
                                                    confirmed = False
                                                if not confirmed:
                                                    missing.append("second graphics benchmark could not be confirmed")
                                                else:
                                                    cancel_deadline = time.monotonic() + 5
                                                    cancel_button = None
                                                    while time.monotonic() < cancel_deadline:
                                                        entries = accessible_tree(app)
                                                        cancel_button = next(
                                                            (node for role, name, node in entries
                                                             if role in BUTTON_ROLES and name == "Cancel graphics benchmark"),
                                                            None,
                                                        )
                                                        if cancel_button and cancel_button.get_state_set().contains(
                                                            Atspi.StateType.SENSITIVE
                                                        ):
                                                            break
                                                        cancel_button = None
                                                        time.sleep(0.1)
                                                    if not cancel_button:
                                                        missing.append("graphics benchmark cancel button did not become available")
                                                    else:
                                                        try:
                                                            cancelled = cancel_button.get_n_actions() > 0 and cancel_button.do_action(0)
                                                        except Exception:
                                                            cancelled = False
                                                        if not cancelled:
                                                            missing.append("graphics benchmark cancel button could not be activated")
                                                        else:
                                                            cancel_result_deadline = time.monotonic() + 5
                                                            cancellation_reported = False
                                                            while time.monotonic() < cancel_result_deadline:
                                                                entries = accessible_tree(app)
                                                                cancellation_reported = any(
                                                                    role == "label" and name == "Graphics benchmark was cancelled."
                                                                    for role, name, _node in entries
                                                                )
                                                                if cancellation_reported:
                                                                    break
                                                                time.sleep(0.1)
                                                            if not cancellation_reported:
                                                                missing.append("graphics benchmark cancellation result was not displayed")
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
                    pci_deadline = time.monotonic() + 5
                    pci_refresh_button = None
                    while time.monotonic() < pci_deadline:
                        entries = accessible_tree(app)
                        pci_refresh_button = next(
                            (
                                node for role, name, node in entries
                                if role in BUTTON_ROLES and name == "Refresh PCI device list"
                            ),
                            None,
                        )
                        if pci_refresh_button:
                            break
                        time.sleep(0.25)
                    if pci_refresh_button is None:
                        missing.append("button: Refresh PCI device list on Network and hardware")
                    bluetooth_guide_button = next(
                        (
                            node for role, name, node in entries
                            if role in BUTTON_ROLES and name == "Open Bluetooth pairing guide"
                        ),
                        None,
                    )
                    if bluetooth_guide_button is None:
                        missing.append("button: Open Bluetooth pairing guide on Network and hardware")
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
                    services_deadline = time.monotonic() + 5
                    services_refresh_button = None
                    while time.monotonic() < services_deadline:
                        entries = accessible_tree(app)
                        services_refresh_button = next(
                            (
                                node for role, name, node in entries
                                if role in BUTTON_ROLES and name == "Refresh system service status"
                            ),
                            None,
                        )
                        if services_refresh_button:
                            break
                        time.sleep(0.25)
                    if services_refresh_button is None:
                        missing.append("button: Refresh system service status on Network and hardware")
                    temperature_deadline = time.monotonic() + 5
                    temperature_refresh_button = None
                    while time.monotonic() < temperature_deadline:
                        entries = accessible_tree(app)
                        temperature_refresh_button = next(
                            (
                                node for role, name, node in entries
                                if role in BUTTON_ROLES and name == "Refresh temperature status"
                            ),
                            None,
                        )
                        if temperature_refresh_button:
                            break
                        time.sleep(0.25)
                    if temperature_refresh_button is None:
                        missing.append("button: Refresh temperature status on Network and hardware")
                    package_health_button = next(
                        (
                            node for role, name, node in entries
                            if role in BUTTON_ROLES and name == "Check package health"
                        ),
                        None,
                    )
                    if package_health_button is None:
                        missing.append("button: Check package health on Network and hardware")
                    for control in (
                        "Refresh radio status", "Open battery and charging guide",
                        "Open Wi-Fi troubleshooting guide", "Open sound and microphone guide",
                        "Open Sound Settings", "Open Bluetooth audio guide",
                        "Check startup time", "Open startup time guide",
                        "Inspect graphical startup chain",
                        "Refresh display status", "Open external display guide",
                        "Check backup app", "Open Backups", "Open Ubuntu App Center",
                    ):
                        if not any(
                            role in BUTTON_ROLES and name == control
                            for role, name, _node in entries
                        ):
                            missing.append(f"button: {control} on Network and hardware")
                    startup_button = next(
                        (
                            node for role, name, node in entries
                            if role in BUTTON_ROLES and name == "Check startup time"
                        ),
                        None,
                    )
                    try:
                        startup_activated = bool(
                            startup_button
                            and startup_button.get_n_actions() > 0
                            and startup_button.do_action(0)
                        )
                    except Exception:
                        startup_activated = False
                    if not startup_activated:
                        missing.append("startup time check could not be activated")
                    else:
                        startup_deadline = time.monotonic() + 5
                        startup_status_updated = False
                        while time.monotonic() < startup_deadline:
                            entries = accessible_tree(app)
                            startup_status_updated = any(
                                role == "label" and name.startswith((
                                    "Systemd reported the startup timing above.",
                                    "systemd-analyze is not installed.",
                                    "Could not read system startup time.",
                                ))
                                for role, name, _node in entries
                            )
                            if startup_status_updated:
                                break
                            time.sleep(0.25)
                        if not startup_status_updated:
                            missing.append("startup time result was not exposed to AT-SPI")
                    chain_button = next(
                        (
                            node for role, name, node in entries
                            if role in BUTTON_ROLES and name == "Inspect graphical startup chain"
                        ),
                        None,
                    )
                    try:
                        chain_activated = bool(
                            chain_button
                            and chain_button.get_n_actions() > 0
                            and chain_button.do_action(0)
                        )
                    except Exception:
                        chain_activated = False
                    if not chain_activated:
                        missing.append("graphical startup chain check could not be activated")
                    else:
                        chain_deadline = time.monotonic() + 7
                        chain_status = None
                        chain_output_visible = False
                        while time.monotonic() < chain_deadline:
                            entries = accessible_tree(app)
                            chain_status = next(
                                (
                                    name for role, name, _node in entries
                                    if role == "label" and name.startswith((
                                        "Systemd's critical chain to graphical.target is shown.",
                                        "systemd-analyze is not installed.",
                                        "Could not read the graphical startup chain.",
                                    ))
                                ),
                                None,
                            )
                            chain_output_visible = any(
                                role in {"label", "text"} and "graphical.target @" in name
                                for role, name, _node in entries
                            )
                            if chain_status and (
                                not chain_status.startswith("Systemd's critical chain")
                                or chain_output_visible
                            ):
                                break
                            time.sleep(0.25)
                        if not chain_status:
                            missing.append("graphical startup chain result was not exposed to AT-SPI")
                        elif chain_status.startswith("Systemd's critical chain") and not chain_output_visible:
                            missing.append("graphical startup chain output was not exposed to AT-SPI")
                            print(
                                "Observed graphical-target accessibility nodes: "
                                f"{[(role, name) for role, name, _node in entries if 'target' in name.casefold()]!r}",
                                file=sys.stderr,
                            )
                if not select_page("Drivers"):
                    missing.append("selectable Drivers page")
                else:
                    secure_boot_deadline = time.monotonic() + 5
                    secure_boot_button = None
                    while time.monotonic() < secure_boot_deadline:
                        entries = accessible_tree(app)
                        secure_boot_button = next(
                            (
                                node for role, name, node in entries
                                if role in BUTTON_ROLES and name == "Check Secure Boot status"
                            ),
                            None,
                        )
                        if secure_boot_button:
                            break
                        time.sleep(0.25)
                    if secure_boot_button is None:
                        missing.append("button: Check Secure Boot status on Drivers")
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
                        "AT-SPI verified guide names, About, the Ubuntu Start version row, Mouse Keys, Accessibility Settings, USB, PCI, Bluetooth pairing and audio, wireless-radio, Wi-Fi, sound, startup timing, startup-chain control and result, battery, backup-app controls, date/time, video, displays, printer queue guide, memory, benchmark readiness, graphics benchmark result and cancellation, system-pressure, service-status, temperature, package-health and Secure Boot controls, and the labeled search entry; "
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
            if name in {"About", "Mouse Keys", "Open Accessibility Settings", "Refresh USB device list", "Refresh PCI device list", "Open Bluetooth pairing guide", "Open Bluetooth audio guide", "Open date and time guide", "Refresh radio status", "Open Wi-Fi troubleshooting guide", "Open sound and microphone guide", "Check startup time", "Open startup time guide", "Open battery and charging guide", "Refresh video device status", "Open camera guide", "Refresh display status", "Open external display guide", "Refresh printer status", "Open print queue guide", "Refresh memory status", "Check benchmark readiness", "Run CPU benchmark", "Run graphics benchmark", "Cancel graphics benchmark", "Open disk read benchmark", "Open GNOME disk benchmark guide", "Open optional disk write benchmark…", "Refresh system pressure", "Refresh system service status", "Refresh temperature status", "Check package health", "Check backup app", "Open Backups", "Open Ubuntu App Center", "Check Secure Boot status", "Search all guides and steps"}
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
        benchmark_tools.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
