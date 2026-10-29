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
CHECKBOX_ROLES = {"check box", "checkbutton"}
ENTRY_ROLES = {"entry", "text"}


def accessible_tree(
    node, *, depth: int = 0, remaining: list[int] | None = None,
    include_unnamed: bool = False,
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


def main() -> int:
    if not os.environ.get("DISPLAY") or not os.environ.get("DBUS_SESSION_BUS_ADDRESS"):
        print("Run this check inside xvfb-run and dbus-run-session.", file=sys.stderr)
        return 2

    environment = os.environ.copy()
    environment.update({"GTK_A11Y": "atspi", "GSK_RENDERER": "cairo", "LANGUAGE": "en"})
    benchmark_tools = tempfile.TemporaryDirectory(prefix="ubuntu-start-benchmark-tools-")
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

                if not select_page("Get started"):
                    missing.append("selectable Get started page")
                else:
                    checklist_deadline = time.monotonic() + 5
                    checklist_tasks = {
                        "Language and keyboard",
                        "Internet connection",
                        "Updates",
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
                    for task in sorted(checklist_tasks - checklist_controls):
                        missing.append(f"accessible checklist checkbox: {task}")

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
                        "Open Sound Settings",
                        "Refresh display status", "Open external display guide",
                    ):
                        if not any(
                            role in BUTTON_ROLES and name == control
                            for role, name, _node in entries
                        ):
                            missing.append(f"button: {control} on Network and hardware")
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
                        "AT-SPI verified guide names, About, Mouse Keys, Accessibility Settings, USB, PCI, Bluetooth, wireless-radio, Wi-Fi, sound, battery, date/time, video, displays, printer queue guide, memory, benchmark readiness, graphics benchmark result and cancellation, system-pressure, service-status, temperature, package-health and Secure Boot controls, and the labeled search entry; "
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
            if name in {"About", "Mouse Keys", "Open Accessibility Settings", "Refresh USB device list", "Refresh PCI device list", "Open Bluetooth pairing guide", "Open date and time guide", "Refresh radio status", "Open Wi-Fi troubleshooting guide", "Open sound and microphone guide", "Open battery and charging guide", "Refresh video device status", "Open camera guide", "Refresh display status", "Open external display guide", "Refresh printer status", "Open print queue guide", "Refresh memory status", "Check benchmark readiness", "Run CPU benchmark", "Run graphics benchmark", "Cancel graphics benchmark", "Open disk read benchmark", "Open GNOME disk benchmark guide", "Open optional disk write benchmark…", "Refresh system pressure", "Refresh system service status", "Refresh temperature status", "Check package health", "Check Secure Boot status", "Search all guides and steps"}
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
