import unittest
from unittest.mock import Mock, call, patch

from ubuntu_start import (
    Adw, Gdk, GLib, Gtk, GUIDES, SYSTEM_GUIDES, UbuntuStart, format_milliseconds,
)
from guide_search import find_guide_matches


class AccessibilityAnnouncementTests(unittest.TestCase):
    def test_pci_status_lists_ids_and_driver_and_announces_summary(self):
        button = Mock()
        status = Mock()
        rows = Mock()
        rows.get_first_child.return_value = None

        UbuntuStart.show_pci_status(
            self.app, button, status, rows,
            [{"id": "1234:5678", "name": "Example Adapter", "driver": "example"}],
            announce=True,
        )

        self.app.row.assert_called_once_with(
            rows, "Example Adapter [1234:5678]", "Kernel driver: example",
        )
        message = "PCI device list updated: 1 device found."
        status.set_text.assert_called_once_with(message)
        self.app.announce_to_screen_reader.assert_called_once_with(status, message)

    def test_pci_status_explains_device_without_driver(self):
        rows = Mock()
        rows.get_first_child.return_value = None
        status = Mock()

        UbuntuStart.show_pci_status(
            self.app, Mock(), status, rows,
            [{"id": "1234:5678", "name": None, "driver": None}],
        )

        self.app.row.assert_called_once_with(
            rows, "PCI device [1234:5678]", "No kernel driver is currently attached.",
        )
        status.set_text.assert_called_once_with("PCI device list updated: 1 device found.")

    def test_temperature_status_lists_sensor_values_and_announces_count(self):
        button = Mock()
        status_label = Mock()
        rows = Mock()
        rows.get_first_child.return_value = None

        UbuntuStart.show_temperature_status(
            self.app, button, status_label, rows,
            [{"name": "CPU Package", "temperature_c": 48.6, "critical_c": 100.0}],
            announce=True,
        )

        self.app.row.assert_called_once_with(
            rows, "CPU Package", "48.6 °C · critical threshold 100.0 °C",
        )
        message = "Temperature status updated: 1 sensors found."
        status_label.set_text.assert_called_once_with(message)
        self.app.announce_to_screen_reader.assert_called_once_with(status_label, message)

    def test_temperature_status_explains_when_no_sensors_are_available(self):
        status_label = Mock()
        rows = Mock()
        rows.get_first_child.return_value = None

        UbuntuStart.show_temperature_status(self.app, Mock(), status_label, rows, [])

        status_label.set_text.assert_called_once_with(
            "No temperature sensors are exposed by Linux on this system.",
        )

    def test_failed_services_are_shown_and_summary_is_announced(self):
        button = Mock()
        status_label = Mock()
        rows = Mock()
        rows.get_first_child.return_value = None

        UbuntuStart.show_failed_services(
            self.app, button, status_label, rows,
            [("geoclue.service", "Location Lookup Service")], None,
            announce=True,
        )

        self.app.row.assert_called_once_with(rows, "geoclue.service", "Location Lookup Service")
        status_label.set_text.assert_called_once_with("1 service units are marked as failed.")
        self.app.announce_to_screen_reader.assert_called_once_with(
            status_label, "1 service units are marked as failed.",
        )

    def test_failed_services_explain_empty_status(self):
        status_label = Mock()
        rows = Mock()
        rows.get_first_child.return_value = None

        UbuntuStart.show_failed_services(self.app, Mock(), status_label, rows, [], None)

        status_label.set_text.assert_called_once_with("No failed system services are reported.")

    def test_resource_pressure_refresh_announces_all_readings(self):
        button = Mock()
        status_label = Mock()
        rows = Mock()
        rows.get_first_child.return_value = None
        status = {
            "cpu": {"some": 2.5},
            "memory": {"some": 1.0},
            "io": {"some": 0.0},
        }

        UbuntuStart.show_resource_pressure(
            self.app, button, status_label, rows, status, announce=True,
        )

        self.app.row.assert_any_call(rows, "Tasks waiting on CPU", "2.5% in the last 10 seconds")
        self.app.row.assert_any_call(rows, "Tasks waiting on memory", "1.0% in the last 10 seconds")
        self.app.row.assert_any_call(rows, "Tasks waiting on storage I/O", "0.0% in the last 10 seconds")
        message = (
            "System pressure updated: Tasks waiting on CPU: 2.5% in the last 10 seconds; "
            "Tasks waiting on memory: 1.0% in the last 10 seconds; "
            "Tasks waiting on storage I/O: 0.0% in the last 10 seconds"
        )
        status_label.set_text.assert_called_once_with(message)
        self.app.announce_to_screen_reader.assert_called_once_with(status_label, message)

    def test_slow_computer_memory_troubleshooting_is_searchable(self):
        entries = [
            ("device", index, guide_title, step_title, description)
            for index, (guide_title, _panel, steps) in enumerate(GUIDES)
            for step_title, description in steps
        ]

        matches = find_guide_matches("slow computer RAM", entries)

        self.assertTrue(matches)
        self.assertTrue(all(match[2] == "Computer feels slow" for match in matches))

    def test_failed_service_help_is_searchable(self):
        entries = [
            ("device", index, guide_title, step_title, description)
            for index, (guide_title, _panel, steps) in enumerate(GUIDES)
            for step_title, description in steps
        ]

        matches = find_guide_matches("failed service systemd", entries)

        self.assertTrue(matches)
        self.assertTrue(all(match[2] == "A system service is marked failed" for match in matches))

    def test_hot_computer_temperature_help_is_searchable(self):
        entries = [
            ("device", index, guide_title, step_title, description)
            for index, (guide_title, _panel, steps) in enumerate(GUIDES)
            for step_title, description in steps
        ]

        matches = find_guide_matches("hot fan sensor", entries)

        self.assertTrue(matches)
        self.assertTrue(all(match[2] == "Computer gets hot or the fan is loud" for match in matches))

    def test_slow_or_unstable_wifi_help_is_searchable(self):
        entries = [
            ("device", index, guide_title, step_title, description)
            for index, (guide_title, _panel, steps) in enumerate(GUIDES)
            for step_title, description in steps
        ]

        matches = find_guide_matches("slow Wi-Fi disconnecting signal channel", entries)

        self.assertTrue(matches)
        self.assertTrue(all(match[2] == "Wi-Fi is slow or keeps disconnecting" for match in matches))

    def test_pci_device_help_is_searchable(self):
        entries = [
            ("device", index, guide_title, step_title, description)
            for index, (guide_title, _panel, steps) in enumerate(GUIDES)
            for step_title, description in steps
        ]

        matches = find_guide_matches("PCI device driver hardware ID", entries)

        self.assertTrue(matches)
        self.assertTrue(all(match[2] == "PCI device is missing or not working" for match in matches))

    def test_package_installation_help_is_searchable(self):
        entries = [
            ("system", index, guide_title, step_title, description)
            for index, (guide_title, _target, _action, steps) in enumerate(SYSTEM_GUIDES)
            for step_title, description in steps
        ]

        matches = find_guide_matches("dpkg incomplete package", entries)

        self.assertTrue(matches)
        self.assertTrue(all(match[2] == "Install Ubuntu updates" for match in matches))

    def test_mouse_keys_accessibility_help_is_searchable(self):
        entries = [
            ("system", index, guide_title, step_title, description)
            for index, (guide_title, _target, _action, steps) in enumerate(SYSTEM_GUIDES)
            for step_title, description in steps
        ]

        matches = find_guide_matches("mouse keys numeric keypad pointer", entries)

        self.assertTrue(matches)
        self.assertTrue(all(match[2] == "Use Mouse Keys" for match in matches))

    def test_manual_memory_refresh_announces_ram_and_swap_status(self):
        button = Mock()
        status_label = Mock()
        rows = Mock()
        rows.get_first_child.return_value = None
        status = {
            "total": 1024,
            "available": 512,
            "used": 512,
            "swap_total": 0,
            "swap_used": 0,
        }

        UbuntuStart.show_memory_status(
            self.app, button, status_label, rows, status, announce=True,
        )

        self.app.row.assert_any_call(rows, "Total RAM", GLib.format_size(1024))
        self.app.row.assert_any_call(rows, "Available RAM", GLib.format_size(512))
        self.app.row.assert_any_call(
            rows,
            "Estimated RAM in use",
            "{size} (50%)".format(size=GLib.format_size(512)),
        )
        self.app.row.assert_any_call(rows, "Swap in use", "No swap space is configured")
        self.app.announce_to_screen_reader.assert_called_once_with(
            status_label,
            "Memory status updated. Available RAM: {available}. Swap: No swap space is configured.".format(
                available=GLib.format_size(512),
            ),
        )

    def test_memory_status_reports_unavailable_procfs(self):
        status_label = Mock()
        rows = Mock()
        rows.get_first_child.return_value = None

        UbuntuStart.show_memory_status(self.app, Mock(), status_label, rows, None)

        status_label.set_text.assert_called_once_with("Memory status is not available from this system.")
        self.app.announce_to_screen_reader.assert_not_called()

    def test_manual_apt_update_check_announces_cached_results(self):
        button = Mock()
        status_label = Mock()
        rows = Mock()
        rows.get_first_child.return_value = None

        UbuntuStart.show_apt_update_status(
            self.app, button, status_label, rows,
            {"upgradeable": 4, "held_back": 2, "last_updated": None}, None,
            announce=True,
        )

        button.set_sensitive.assert_called_once_with(True)
        self.app.row.assert_any_call(rows, "Packages ready to upgrade", "4")
        self.app.row.assert_any_call(rows, "Packages kept back", "2")
        self.app.row.assert_any_call(rows, "Package lists last updated", "Not available")
        status_label.set_text.assert_called_once_with(
            "Local package update check complete. No packages were changed.",
        )
        self.app.announce_to_screen_reader.assert_called_once_with(
            status_label, "Local package update check complete. No packages were changed.",
        )

    def test_background_apt_update_check_does_not_announce(self):
        button = Mock()
        status_label = Mock()
        rows = Mock()
        rows.get_first_child.return_value = None

        UbuntuStart.show_apt_update_status(
            self.app, button, status_label, rows, None, "timeout",
        )

        status_label.set_text.assert_called_once_with(
            "The local package check took too long. Try again later.",
        )
        self.app.announce_to_screen_reader.assert_not_called()

    def test_package_health_lists_findings_and_announces_summary(self):
        button = Mock()
        status_label = Mock()
        rows = Mock()
        rows.get_first_child.return_value = None

        UbuntuStart.show_package_health(
            self.app, button, status_label, rows, ["broken-app", "browser"], None,
            announce=True,
        )

        button.set_sensitive.assert_called_once_with(True)
        self.app.row.assert_any_call(
            rows, "broken-app", "dpkg reports an incomplete or inconsistent installation.",
        )
        self.app.row.assert_any_call(
            rows, "browser", "dpkg reports an incomplete or inconsistent installation.",
        )
        message = "Package check found 2 package entries to review."
        status_label.set_text.assert_called_once_with(message)
        self.app.announce_to_screen_reader.assert_called_once_with(status_label, message)

    def test_package_health_reports_a_clean_audit(self):
        status_label = Mock()
        rows = Mock()
        rows.get_first_child.return_value = None

        UbuntuStart.show_package_health(self.app, Mock(), status_label, rows, [], None)

        status_label.set_text.assert_called_once_with(
            "dpkg reported no incomplete package installations.",
        )
        self.app.row.assert_not_called()

    def test_package_health_handles_unavailable_database(self):
        status_label = Mock()
        rows = Mock()
        rows.get_first_child.return_value = None

        UbuntuStart.show_package_health(
            self.app, Mock(), status_label, rows, None, "unavailable",
        )

        status_label.set_text.assert_called_once_with(
            "Could not read the local package database.",
        )

    def setUp(self):
        self.app = Mock()

    def test_control_f_opens_device_guides_and_focuses_search(self):
        self.app.main_stack = Mock()
        self.app.device_search = Mock()

        handled = UbuntuStart.on_key_pressed(
            self.app, Mock(), Gdk.KEY_f, 0, Gdk.ModifierType.CONTROL_MASK,
        )

        self.assertTrue(handled)
        self.app.main_stack.set_visible_child_name.assert_called_once_with("Fix a device")
        self.app.device_search.grab_focus.assert_called_once_with()

    def test_open_time_guide_selects_date_and_time_instructions(self):
        self.app.system_guide_chooser = Mock()
        self.app.main_stack = Mock()

        UbuntuStart.open_time_guide(self.app)

        expected_index = next(
            index for index, (title, _target, _action, _steps) in enumerate(SYSTEM_GUIDES)
            if title == "Check date and time"
        )
        self.app.system_guide_chooser.set_selected.assert_called_once_with(expected_index)
        self.app.main_stack.set_visible_child_name.assert_called_once_with("System guides")

    def test_open_bluetooth_guide_selects_pairing_instructions(self):
        self.app.system_guide_chooser = Mock()
        self.app.main_stack = Mock()

        UbuntuStart.open_bluetooth_guide(self.app)

        expected_index = next(
            index for index, (title, _target, _action, _steps) in enumerate(SYSTEM_GUIDES)
            if title == "Pair a Bluetooth device"
        )
        self.app.system_guide_chooser.set_selected.assert_called_once_with(expected_index)
        self.app.main_stack.set_visible_child_name.assert_called_once_with("System guides")

    def test_unrelated_key_is_not_consumed(self):
        self.app.main_stack = Mock()
        self.app.device_search = Mock()

        handled = UbuntuStart.on_key_pressed(self.app, Mock(), Gdk.KEY_a, 0, Gdk.ModifierType.CONTROL_MASK)

        self.assertFalse(handled)
        self.app.main_stack.set_visible_child_name.assert_not_called()
        self.app.device_search.grab_focus.assert_not_called()

    def test_background_bluetooth_refresh_does_not_interrupt_other_page(self):
        row = Mock()
        row.get_title.return_value = "Bluetooth controller"

        UbuntuStart.show_bluetooth_status(self.app, row, "powered")

        row.set_subtitle.assert_called_once_with("On")
        self.app.announce_to_screen_reader.assert_not_called()

    def test_manual_bluetooth_refresh_announces_result(self):
        row = Mock()
        row.get_title.return_value = "Bluetooth controller"

        UbuntuStart.show_bluetooth_status(self.app, row, "powered", announce=True)

        self.app.announce_to_screen_reader.assert_called_once_with(
            row, "Bluetooth controller: On",
        )

    def test_bluetooth_service_status_explains_where_to_check_next(self):
        row = Mock()
        row.get_title.return_value = "Bluetooth controller"

        UbuntuStart.show_bluetooth_status(self.app, row, "service-inactive", announce=True)

        message = "Bluetooth service is not running. Refresh System service status for details."
        row.set_subtitle.assert_called_once_with(message)
        self.app.announce_to_screen_reader.assert_called_once_with(
            row, f"Bluetooth controller: {message}",
        )

    def test_network_refresh_only_announces_when_requested(self):
        status = Mock()
        rows = Mock()
        rows.get_first_child.return_value = None

        UbuntuStart.show_network_status(self.app, status, rows, [], "timeout")
        self.app.announce_to_screen_reader.assert_not_called()

        UbuntuStart.show_network_status(self.app, status, rows, [], "timeout", announce=True)
        self.app.announce_to_screen_reader.assert_called_once_with(
            status,
            "NetworkManager did not respond in time. Try refreshing again.",
        )

    def test_network_status_shows_local_wifi_signal_and_link_rates(self):
        status = Mock()
        rows = Mock()
        self.app.row = Mock()

        UbuntuStart.show_network_status(
            self.app, status, rows,
            [("wlp2s0", "wifi", "connected")], None,
            announce=True,
            wifi_details={"wlp2s0": {
                "signal_dbm": -53,
                "rx_bitrate_mbps": 780.0,
                "tx_bitrate_mbps": 650.5,
            }},
            interface_ips={"wlp2s0": {"ipv4": True, "ipv6": False, "link_local": False}},
            adapter_details={"wlp2s0": {
                "bus": "PCI", "id": "8086:1234", "name": "Example Wi-Fi Adapter",
                "driver": "iwlwifi",
            }},
        )

        self.app.row.assert_called_once_with(
            rows,
            "Wi-Fi · wlp2s0",
            "Connected · Example Wi-Fi Adapter · Hardware ID: PCI 8086:1234 · Kernel driver: iwlwifi · Signal: -53 dBm · Receive rate: 780.0 Mbit/s · Transmit rate: 650.5 Mbit/s · IPv4 address assigned",
        )
        self.app.announce_to_screen_reader.assert_called_once_with(
            status,
            "Network status updated: Wi-Fi · wlp2s0: Connected · Example Wi-Fi Adapter · Hardware ID: PCI 8086:1234 · Kernel driver: iwlwifi · Signal: -53 dBm · Receive rate: 780.0 Mbit/s · Transmit rate: 650.5 Mbit/s · IPv4 address assigned",
        )

    def test_network_status_shows_address_families_for_unmanaged_interfaces(self):
        status = Mock()
        rows = Mock()
        self.app.row = Mock()

        UbuntuStart.show_network_status(
            self.app, status, rows,
            [("eth0", "ethernet", "unmanaged")], None,
            interface_ips={"eth0": {"ipv4": True, "ipv6": True, "link_local": True}},
        )

        self.app.row.assert_called_once_with(
            rows,
            "Wired · eth0",
            "Not managed by NetworkManager · IPv4 and IPv6 addresses assigned",
        )

    def test_missing_gateway_result_includes_and_announces_next_step(self):
        button = Mock()
        status = Mock()

        UbuntuStart.show_network_diagnostic_result(
            self.app, button, status,
            {"dns_latency_ms": 14.2, "gateway": None, "gateway_latency_ms": None},
        )

        message = status.set_text.call_args.args[0]
        self.assertIn("No default gateway was found.", message)
        self.assertIn(
            "Next step: check Wi-Fi or wired connection in Settings. On a managed network, ask the administrator before changing route settings.",
            message,
        )
        button.set_sensitive.assert_called_once_with(True)
        self.app.announce_to_screen_reader.assert_called_once_with(status, message)

    def test_manual_audio_refresh_announces_both_endpoints_once(self):
        output = Mock()
        output.get_title.return_value = "Speaker output"
        input_device = Mock()
        input_device.get_title.return_value = "Microphone input"

        UbuntuStart.show_audio_status(
            self.app,
            output,
            input_device,
            {
                "output": (65, False), "input": (20, True),
                "output_name": "USB speakers", "input_name": "Built-in microphone",
                "error": None,
            },
            announce=True,
        )

        output.set_subtitle.assert_called_once_with("USB speakers · 65% · Not muted")
        input_device.set_subtitle.assert_called_once_with("Built-in microphone · 20% · Muted")
        self.app.announce_to_screen_reader.assert_called_once_with(
            output,
            "Speaker output: USB speakers · 65% · Not muted Microphone input: Built-in microphone · 20% · Muted",
        )

    def test_manual_battery_refresh_announces_charge_and_state(self):
        button = Mock()
        status = Mock()
        rows = Mock()
        rows.get_first_child.return_value = None

        UbuntuStart.show_battery_status(
            self.app, button, status, rows,
            [{"capacity": 82, "status": "Charging", "design_capacity_percent": 91, "cycle_count": 348, "state_of_health_percent": 87}],
            announce=True,
        )

        button.set_sensitive.assert_called_once_with(True)
        self.app.row.assert_any_call(rows, "Battery 1", "Charge: 82% · Charging")
        self.app.row.assert_any_call(rows, "Estimated capacity vs. design", "91% of original design capacity")
        self.app.row.assert_any_call(rows, "Reported charge cycles", "348")
        self.app.row.assert_any_call(rows, "Reported battery health", "87%")
        status.set_text.assert_called_once_with(
            "Battery status updated: 82% · Charging · Charge cycles: 348 · Battery-reported health: 87%",
        )
        self.app.announce_to_screen_reader.assert_called_once_with(
            status,
            "Battery status updated: 82% · Charging · Charge cycles: 348 · Battery-reported health: 87%",
        )

    def test_background_battery_refresh_does_not_announce(self):
        button = Mock()
        status = Mock()
        rows = Mock()
        rows.get_first_child.return_value = None

        UbuntuStart.show_battery_status(
            self.app, button, status, rows, [],
        )

        self.app.row.assert_any_call(
            rows, "No battery information",
            "No battery information found. This computer may not have a battery, or the system does not expose battery data.",
        )
        self.app.row.assert_any_call(
            rows, "Active power profile",
            "Power profile information is not available on this system.",
        )
        self.app.announce_to_screen_reader.assert_not_called()

    def test_battery_status_shows_active_power_profile(self):
        button = Mock()
        status = Mock()
        rows = Mock()
        rows.get_first_child.return_value = None

        UbuntuStart.show_battery_status(
            self.app, button, status, rows, [], power_profile="balanced",
        )

        self.app.row.assert_any_call(rows, "Active power profile", "Balanced")

class AboutDialogTests(unittest.TestCase):
    def test_about_dialog_api_is_available_on_supported_platforms(self):
        properties = {property_.name for property_ in Adw.AboutDialog.list_properties()}
        self.assertTrue({
            "application-name", "application-icon", "developer-name", "developers",
            "website", "issue-url", "license-type", "comments",
        }.issubset(properties))
        self.assertTrue(hasattr(Adw.AboutDialog, "add_link"))
        self.assertTrue(hasattr(Gtk.License, "GPL_3_0_ONLY"))

    @patch("ubuntu_start.Adw.AboutDialog")
    def test_lists_developer_and_links_to_personal_site_and_project(self, about_dialog):
        app = Mock()
        dialog = about_dialog.return_value

        UbuntuStart.show_about(app)

        properties = about_dialog.call_args.kwargs
        self.assertEqual(properties["developer_name"], "Daniel Nylander")
        self.assertEqual(properties["developers"], ["Daniel Nylander"])
        self.assertNotIn("website", properties)
        self.assertEqual(dialog.add_link.call_args_list, [
            call("Daniel Nylander's website", "https://www.danielnylander.se"),
            call("GitHub repository", "https://github.com/yeager/ubuntu-start"),
        ])
        dialog.present.assert_called_once_with(app.get_active_window.return_value)


class SystemDetailsTests(unittest.TestCase):
    @patch("ubuntu_start.read_storage_locations")
    @patch("ubuntu_start.read_hardware_details")
    @patch("ubuntu_start.platform.freedesktop_os_release", return_value={"PRETTY_NAME": "Ubuntu Test"})
    def test_system_details_include_separate_filesystem_capacity(self, _os_release, hardware, storage):
        hardware.return_value = {
            "system_model": "Test model", "processor": "Test CPU", "memory": "8 GiB",
            "graphics": [], "architecture": "x86_64", "usb_devices": [],
        }
        storage.return_value = {
            "system": {"total": 1000, "used": 500, "free": 500},
            "home": {"total": 2000, "used": 1800, "free": 200},
        }

        details = UbuntuStart.system_details(Mock())

        details_by_label = dict(details)
        self.assertIn("500", details_by_label["System filesystem"])
        self.assertIn("50% used", details_by_label["System filesystem"])
        self.assertIn("200", details_by_label["Home folder filesystem"])
        self.assertIn("90% used", details_by_label["Home folder filesystem"])

    @patch("ubuntu_start.read_storage_locations", return_value={
        "system": {"total": 1000, "used": 500, "free": 500},
    })
    @patch("ubuntu_start.read_hardware_details", return_value={
        "system_model": None, "processor": None, "memory": None, "graphics": [], "architecture": "x86_64",
    })
    @patch("ubuntu_start.platform.freedesktop_os_release", return_value={"PRETTY_NAME": "Ubuntu Test"})
    def test_system_details_omit_home_when_it_shares_the_system_filesystem(self, *_mocks):
        details = UbuntuStart.system_details(Mock())

        self.assertEqual(sum(label == "System filesystem" for label, _value in details), 1)
        self.assertFalse(any(label == "Home folder filesystem" for label, _value in details))

    @patch("ubuntu_start.read_storage_locations", return_value={})
    @patch("ubuntu_start.read_hardware_details", return_value={
        "system_model": None, "processor": None, "memory": None,
        "graphics": [], "architecture": "x86_64",
        "usb_devices": [{
            "id": "046d:c534", "name": "Logitech USB Receiver", "drivers": ["usbhid"],
        }],
        "pci_devices": [{
            "id": "1234:5678", "name": "Example Network Adapter", "driver": "example_net",
        }],
    })
    @patch("ubuntu_start.platform.freedesktop_os_release", return_value={"PRETTY_NAME": "Ubuntu Test"})
    def test_system_details_include_usb_hardware_id_and_driver_without_serial(self, *_mocks):
        details = dict(UbuntuStart.system_details(Mock()))

        self.assertEqual(
            details["Connected USB devices"],
            "Logitech USB Receiver [046d:c534] (driver: usbhid)",
        )
        self.assertNotIn("serial", details["Connected USB devices"].casefold())
        self.assertEqual(
            details["PCI devices"],
            "Example Network Adapter [1234:5678] (example_net)",
        )


class USBStatusTests(unittest.TestCase):
    def setUp(self):
        self.app = Mock()
        self.app.row = Mock()

    def test_shows_detected_device_id_and_bound_driver(self):
        button = Mock()
        status = Mock()
        rows = Mock()
        rows.get_first_child.return_value = None

        UbuntuStart.show_usb_status(self.app, button, status, rows, [{
            "id": "046d:c534", "name": "Logitech USB Receiver", "drivers": ["usbhid"],
        }])

        self.app.row.assert_called_once_with(
            rows, "Logitech USB Receiver [046d:c534]", "Kernel driver: usbhid",
        )
        status.set_text.assert_called_once_with(
            "USB device list updated: Logitech USB Receiver [046d:c534]",
        )
        self.app.announce_to_screen_reader.assert_not_called()

    def test_empty_device_list_explains_how_to_refresh(self):
        button = Mock()
        status = Mock()
        rows = Mock()
        rows.get_first_child.return_value = None

        UbuntuStart.show_usb_status(self.app, button, status, rows, [], announce=True)

        self.app.row.assert_called_once_with(
            rows, "No external USB devices detected", "Connect a USB device and refresh the list.",
        )
        self.app.announce_to_screen_reader.assert_called_once_with(
            status, "No external USB devices detected",
        )

    def test_usb_guide_opens_the_hardware_overview(self):
        app = Mock()
        app.main_stack = Mock()

        UbuntuStart.open_device_target(app, "hardware")

        app.main_stack.set_visible_child_name.assert_called_once_with("Network and hardware")
        app.open_app.assert_not_called()

    def test_other_device_guides_open_their_settings_panel(self):
        app = Mock()

        UbuntuStart.open_device_target(app, "wifi")

        app.open_app.assert_called_once_with("gnome-control-center", "wifi")


class InternetTestResultTests(unittest.TestCase):
    def test_formats_milliseconds_with_the_active_decimal_separator(self):
        with patch("ubuntu_start.locale.localeconv", return_value={"decimal_point": ","}):
            self.assertEqual(format_milliseconds(123.4), "123,4")
            self.assertEqual(format_milliseconds(5000.0), "5000")

    def test_network_diagnostic_timings_use_localized_decimal_separator(self):
        app = Mock()
        button = Mock()
        status = Mock()
        result = {
            "dns_latency_ms": 12.3,
            "gateway": "192.168.1.1",
            "gateway_latency_ms": 1.2,
            "gateway_mac": None,
            "gateway_vendor": None,
        }

        with patch("ubuntu_start.locale.localeconv", return_value={"decimal_point": ","}):
            UbuntuStart.show_network_diagnostic_result(app, button, status, result)

        message = status.set_text.call_args.args[0]
        self.assertIn("DNS lookup: 12,3 ms", message)
        self.assertIn("Gateway response: 1,2 ms", message)

    def test_missing_ping_tool_recommends_package_without_blaming_gateway(self):
        app = Mock()
        button = Mock()
        status = Mock()
        result = {
            "dns_latency_ms": 12.3,
            "gateway": "192.168.1.1",
            "gateway_latency_ms": None,
            "gateway_error": "ping-not-installed",
            "gateway_mac": None,
            "gateway_vendor": None,
        }

        UbuntuStart.show_network_diagnostic_result(app, button, status, result)

        message = status.set_text.call_args.args[0]
        self.assertIn("The ping tool is not installed.", message)
        self.assertIn("iputils-ping", message)
        self.assertNotIn("Gateway did not answer the ping.", message)
        self.assertNotIn("Next step: check the local connection.", message)

    def test_ping_timeout_is_explained_without_claiming_network_is_down(self):
        app = Mock()
        button = Mock()
        status = Mock()
        result = {
            "dns_latency_ms": 12.3,
            "gateway": "192.168.1.1",
            "gateway_latency_ms": None,
            "gateway_test_duration_ms": 1500.0,
            "gateway_error": "timeout",
            "gateway_mac": None,
            "gateway_vendor": None,
        }

        UbuntuStart.show_network_diagnostic_result(app, button, status, result)

        message = status.set_text.call_args.args[0]
        self.assertIn("The gateway ping timed out after 1500 ms.", message)
        self.assertIn("Some gateways block ping", message)

    def test_unanswered_ping_includes_elapsed_time(self):
        app = Mock()
        button = Mock()
        status = Mock()
        result = {
            "dns_latency_ms": 12.3,
            "gateway": "192.168.1.1",
            "gateway_latency_ms": None,
            "gateway_test_duration_ms": 14.6,
            "gateway_error": "no-response",
            "gateway_mac": None,
            "gateway_vendor": None,
        }

        with patch("ubuntu_start.locale.localeconv", return_value={"decimal_point": ","}):
            UbuntuStart.show_network_diagnostic_result(app, button, status, result)

        message = status.set_text.call_args.args[0]
        self.assertIn("The gateway did not answer the ping after 14,6 ms.", message)
        self.assertIn("Some routers block ping requests.", message)

    def test_confirmed_internet_check_passes_elapsed_https_time(self):
        app = Mock()
        button = Mock()
        status = Mock()
        dialog = Mock()

        with patch("ubuntu_start.Adw.AlertDialog", return_value=dialog), \
                patch("ubuntu_start.threading.Thread") as thread, \
                patch("ubuntu_start.check_internet_connection", return_value="reachable:204"), \
                patch("ubuntu_start.time.monotonic", side_effect=[1.0, 1.1234]), \
                patch("ubuntu_start.GLib.idle_add") as idle_add:
            UbuntuStart.confirm_internet_test(app, button, status)
            on_response = dialog.connect.call_args.args[1]

            on_response(dialog, "cancel")
            thread.assert_not_called()

            on_response(dialog, "test")
            button.set_sensitive.assert_called_once_with(False)
            status.set_text.assert_called_once_with("Checking connection to ubuntu.com…")
            thread.return_value.start.assert_called_once_with()
            thread.call_args.kwargs["target"]()

        idle_add.assert_called_once_with(
            app.show_internet_result, button, status, "reachable:204", 123.4,
        )

    def test_reachable_result_includes_https_response_time(self):
        app = Mock()
        button = Mock()
        status = Mock()

        UbuntuStart.show_internet_result(app, button, status, "reachable:204", 123.4)

        button.set_sensitive.assert_called_once_with(True)
        status.set_text.assert_called_once_with(
            "ubuntu.com responded in 123.4 ms. Internet access is available.",
        )
        app.announce_to_screen_reader.assert_called_once_with(
            status, "ubuntu.com responded in 123.4 ms. Internet access is available.",
        )

    def test_internet_result_uses_localized_decimal_separator(self):
        app = Mock()
        button = Mock()
        status = Mock()

        with patch("ubuntu_start.locale.localeconv", return_value={"decimal_point": ","}):
            UbuntuStart.show_internet_result(app, button, status, "reachable:204", 123.4)

        status.set_text.assert_called_once_with(
            "ubuntu.com responded in 123,4 ms. Internet access is available.",
        )

    def test_failed_result_includes_elapsed_time_and_next_steps(self):
        app = Mock()
        button = Mock()
        status = Mock()

        UbuntuStart.show_internet_result(app, button, status, "unreachable:TimeoutError", 5000.0)

        status.set_text.assert_called_once_with(
            "Could not reach ubuntu.com after 5000 ms. Check the router, "
            "network sign-in page, DNS settings or firewall.",
        )


class DriverGuideTests(unittest.TestCase):
    def test_unknown_adapter_help_links_to_hardware_overview(self):
        app = Mock()
        app.page.return_value = (Mock(), Mock())
        app.main_stack = Mock()

        UbuntuStart.make_drivers(app)

        calls = [call_args for call_args in app.row.call_args_list
                 if call_args.args[1] == "If the graphics adapter has no name"]
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].args[3], "Open hardware overview")
        calls[0].args[4]()
        app.main_stack.set_visible_child_name.assert_called_once_with("Network and hardware")


class SystemGuideTests(unittest.TestCase):
    def test_backup_guide_covers_destination_encryption_and_restore_verification(self):
        guide = next(
            guide for guide in SYSTEM_GUIDES if guide[0] == "Set up backups"
        )
        title, target, action, steps = guide

        self.assertEqual(
            target,
            ("external", "https://help.ubuntu.com/stable/ubuntu-help/backup-why.html.en"),
        )
        self.assertEqual(action, "Open Ubuntu backup help")
        step_text = " ".join(f"{step} {description}" for step, description in steps)
        self.assertIn("external drive", step_text)
        self.assertIn("Backups app", step_text)
        self.assertIn("recovery password", step_text)
        self.assertIn("restore", step_text)

    def test_backup_guide_requires_confirmation_before_opening_external_help(self):
        app = Mock()

        UbuntuStart.open_target(
            app,
            ("external", "https://help.ubuntu.com/stable/ubuntu-help/backup-why.html.en"),
        )

        app.confirm_external_link.assert_called_once_with(
            "https://help.ubuntu.com/stable/ubuntu-help/backup-why.html.en",
            "Open Ubuntu help?",
            "This opens Ubuntu Desktop documentation in your browser. The website will receive a normal web request and can see your IP address.",
        )
        app.open_uri.assert_not_called()

    def test_vpn_guide_opens_network_settings_and_protects_credentials(self):
        guide = next(guide for guide in SYSTEM_GUIDES if guide[0] == "Connect to a VPN")
        _title, target, action, steps = guide
        step_text = " ".join(f"{step} {description}" for step, description in steps)

        self.assertEqual(target, ("settings", "network"))
        self.assertEqual(action, "Open Network Settings")
        self.assertIn("Never share passwords", step_text)
        self.assertIn("private keys", step_text)
        self.assertIn("does not make all online activity anonymous", step_text)

        app = Mock()
        UbuntuStart.open_target(app, target)

        app.open_app.assert_called_once_with("gnome-control-center", "network")

    @patch("ubuntu_start.GLib.timeout_add")
    def test_storage_guide_opens_and_schedules_the_storage_overview(self, timeout_add):
        app = Mock()
        app.scroll_to_storage_overview = UbuntuStart.scroll_to_storage_overview.__get__(app)

        UbuntuStart.open_target(app, ("overview", "storage"))

        app.main_stack.set_visible_child_name.assert_called_once_with("Network and hardware")
        callback = timeout_add.call_args.args[1]
        self.assertIs(callback.__self__, app)
        self.assertEqual(callback.__func__, UbuntuStart.scroll_to_storage_overview)
        self.assertEqual(timeout_add.call_args.args[0], 50)
        app.open_app.assert_not_called()

    def test_storage_overview_scrolls_to_the_storage_card(self):
        app = Mock()
        scroller = Mock()
        bounds = Mock()
        bounds.get_y.return_value = 420.0
        app.main_stack.get_visible_child.return_value = scroller
        app.storage_box.get_mapped.return_value = True
        app.storage_box.compute_bounds.return_value = (True, bounds)

        result = UbuntuStart.scroll_to_storage_overview(app)

        app.storage_box.compute_bounds.assert_called_once_with(scroller.get_child.return_value)
        scroller.get_vadjustment().set_value.assert_called_once_with(420.0)
        self.assertEqual(result, GLib.SOURCE_REMOVE)

    @patch("ubuntu_start.GLib.timeout_add")
    def test_printer_guide_opens_and_schedules_the_local_printer_status(self, timeout_add):
        app = Mock()
        app.scroll_to_printer_status = UbuntuStart.scroll_to_printer_status.__get__(app)

        UbuntuStart.open_target(app, ("overview", "printer"))

        app.main_stack.set_visible_child_name.assert_called_once_with("Network and hardware")
        callback = timeout_add.call_args.args[1]
        self.assertIs(callback.__self__, app)
        self.assertEqual(callback.__func__, UbuntuStart.scroll_to_printer_status)
        self.assertEqual(timeout_add.call_args.args[0], 50)

    def test_printer_status_navigation_scrolls_to_the_printer_card(self):
        app = Mock()
        scroller = Mock()
        bounds = Mock()
        bounds.get_y.return_value = 880.0
        app.main_stack.get_visible_child.return_value = scroller
        app.printer_box.get_mapped.return_value = True
        app.printer_box.compute_bounds.return_value = (True, bounds)

        result = UbuntuStart.scroll_to_printer_status(app)

        app.printer_box.compute_bounds.assert_called_once_with(scroller.get_child.return_value)
        scroller.get_vadjustment().set_value.assert_called_once_with(880.0)
        self.assertEqual(result, GLib.SOURCE_REMOVE)


class PrinterStatusAnnouncementTests(unittest.TestCase):
    def test_printer_refresh_displays_only_queue_name_and_safe_state(self):
        app = Mock()
        button = Mock()
        status_label = Mock()
        rows = Mock()

        UbuntuStart.show_printer_status(
            app, button, status_label, rows,
            [("Office_Laser", "idle")], None, announce=True,
        )

        button.set_sensitive.assert_called_once_with(True)
        app.row.assert_called_once_with(rows, "Office_Laser", "Ready")
        app.announce_to_screen_reader.assert_called_once_with(
            status_label, "Printer status updated: 1 printer queues found.",
        )

    def test_no_printer_queues_reports_missing_cups_tools(self):
        app = Mock()
        status_label = Mock()

        UbuntuStart.show_printer_status(app, Mock(), status_label, Mock(), [], "not-installed")

        status_label.set_text.assert_called_once_with("CUPS printer tools are not installed.")


class AccessibilityStatusAnnouncementTests(unittest.TestCase):
    def test_accessibility_status_lists_local_values_and_announces_refresh(self):
        app = Mock()
        status_label = Mock()
        rows = Mock()
        settings = {
            "screen_reader": True,
            "screen_magnifier": False,
            "screen_keyboard": None,
            "high_contrast": True,
            "sticky_keys": False,
            "slow_keys": True,
            "bounce_keys": False,
            "mouse_keys": True,
            "text_scale": 1.25,
            "cursor_size": 48,
            "visual_bell": True,
        }

        UbuntuStart.show_accessibility_status(app, Mock(), status_label, rows, settings, None, announce=True)

        self.assertEqual(
            [call_args.args[1:] for call_args in app.row.call_args_list],
            [
                ("Screen reader", "On"),
                ("Screen magnifier", "Off"),
                ("On-screen keyboard", "Not available"),
                ("High contrast", "On"),
                ("Sticky Keys", "Off"),
                ("Slow Keys", "On"),
                ("Bounce Keys", "Off"),
                ("Mouse Keys", "On"),
                ("Visual sound alerts", "On"),
                ("Text size", "125%"),
                ("Pointer size", "48 pixels"),
            ],
        )
        status_label.set_text.assert_called_once_with(
            "GNOME accessibility settings read. No settings were changed.",
        )
        app.announce_to_screen_reader.assert_called_once_with(
            status_label, "GNOME accessibility settings read. No settings were changed.",
        )


class TimeStatusAnnouncementTests(unittest.TestCase):
    def test_time_status_lists_local_values_and_announces_refresh(self):
        app = Mock()
        status_label = Mock()
        rows = Mock()
        UbuntuStart.show_time_status(
            app, Mock(), status_label, rows,
            {"timezone": "Europe/Stockholm", "can_ntp": True, "ntp": True, "synchronized": False},
            None, announce=True,
        )
        self.assertEqual(
            [call_args.args[1:] for call_args in app.row.call_args_list],
            [
                ("Time zone", "Europe/Stockholm"),
                ("Automatic time synchronization available", "Available"),
                ("Automatic time synchronization", "On"),
                ("Clock synchronization", "Not synchronized"),
                (
                    "Next step",
                    "Automatic time synchronization is on, but the clock is not synchronized. "
                    "Check the network connection and Date & Time Settings.",
                ),
            ],
        )
        status_label.set_text.assert_called_once_with(
            "Local date and time status read. No settings were changed.",
        )
        app.announce_to_screen_reader.assert_called_once_with(
            status_label, "Local date and time status read. No settings were changed.",
        )

    def test_time_status_suggests_admin_help_when_automatic_sync_is_unavailable(self):
        app = Mock()
        rows = Mock()
        UbuntuStart.show_time_status(
            app, Mock(), Mock(), rows,
            {"timezone": "Etc/UTC", "can_ntp": False, "ntp": False, "synchronized": False},
            None,
        )
        app.row.assert_any_call(
            rows, "Next step",
            "Automatic time synchronization is unavailable on this system. If this is a managed computer, ask your administrator how its clock is maintained.",
        )

    def test_time_status_reports_unavailable_read(self):
        app = Mock()
        status_label = Mock()
        UbuntuStart.show_time_status(
            app, Mock(), status_label, Mock(),
            {"timezone": None, "ntp": None, "synchronized": None}, "unavailable",
        )
        self.assertEqual(app.row.call_count, 4)
        status_label.set_text.assert_called_once_with("Could not read the local date and time status.")


class VideoStatusAnnouncementTests(unittest.TestCase):
    def test_video_status_lists_local_device_names_and_announces(self):
        app = Mock()
        status_label = Mock()
        rows = Mock()
        rows.get_first_child.return_value = None
        UbuntuStart.show_video_status(
            app, Mock(), status_label, rows, ["Integrated Camera"], announce=True,
        )
        app.row.assert_called_once_with(
            rows, "Integrated Camera", "Reported by Linux",
        )
        status_label.set_text.assert_called_once_with(
            "Video device status updated: 1 device found.",
        )
        app.announce_to_screen_reader.assert_called_once_with(
            status_label, "Video device status updated: 1 device found.",
        )

    def test_video_status_explains_missing_camera_is_not_a_device_test(self):
        app = Mock()
        status_label = Mock()
        rows = Mock()
        rows.get_first_child.return_value = None
        UbuntuStart.show_video_status(app, Mock(), status_label, rows, [])
        app.row.assert_called_once_with(
            rows,
            "No video devices reported by Linux",
            "Connect a camera or check its privacy shutter, then refresh. This status does not test the camera.",
        )

    def test_open_camera_guide_selects_the_camera_steps(self):
        app = Mock()
        UbuntuStart.open_camera_guide(app)
        app.device_search.set_text.assert_called_once_with("")
        app.device_chooser.set_selected.assert_called_once_with(
            next(index for index, (title, _target, _steps) in enumerate(GUIDES) if title == "Camera")
        )
        app.main_stack.set_visible_child_name.assert_called_once_with("Fix a device")


if __name__ == "__main__":
    unittest.main()
