import unittest
from unittest.mock import Mock, call, patch

from ubuntu_start import Adw, Gdk, GLib, Gtk, GUIDES, UbuntuStart


class AccessibilityAnnouncementTests(unittest.TestCase):
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
        )

        self.app.row.assert_called_once_with(
            rows,
            "Wi-Fi · wlp2s0",
            "Connected · Signal: -53 dBm · Receive rate: 780.0 Mbit/s · Transmit rate: 650.5 Mbit/s · IPv4 address assigned",
        )
        self.app.announce_to_screen_reader.assert_called_once_with(
            status,
            "Network status updated: Wi-Fi · wlp2s0: Connected · Signal: -53 dBm · Receive rate: 780.0 Mbit/s · Transmit rate: 650.5 Mbit/s · IPv4 address assigned",
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
            [{"capacity": 82, "status": "Charging", "design_capacity_percent": 91}],
            announce=True,
        )

        button.set_sensitive.assert_called_once_with(True)
        self.app.row.assert_any_call(rows, "Battery 1", "Charge: 82% · Charging")
        self.app.row.assert_any_call(rows, "Estimated capacity vs. design", "91% of original design capacity")
        status.set_text.assert_called_once_with("Battery status updated: 82% · Charging")
        self.app.announce_to_screen_reader.assert_called_once_with(
            status, "Battery status updated: 82% · Charging",
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
    def test_lists_developer_and_both_project_and_personal_sites(self, about_dialog):
        app = Mock()
        dialog = about_dialog.return_value

        UbuntuStart.show_about(app)

        properties = about_dialog.call_args.kwargs
        self.assertEqual(properties["developer_name"], "Daniel Nylander")
        self.assertEqual(properties["developers"], ["Daniel Nylander"])
        self.assertEqual(properties["website"], "https://www.danielnylander.se")
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
    })
    @patch("ubuntu_start.platform.freedesktop_os_release", return_value={"PRETTY_NAME": "Ubuntu Test"})
    def test_system_details_include_usb_hardware_id_and_driver_without_serial(self, *_mocks):
        details = dict(UbuntuStart.system_details(Mock()))

        self.assertEqual(
            details["Connected USB devices"],
            "Logitech USB Receiver [046d:c534] (driver: usbhid)",
        )
        self.assertNotIn("serial", details["Connected USB devices"].casefold())


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
            {"timezone": "Europe/Stockholm", "ntp": True, "synchronized": False},
            None, announce=True,
        )
        self.assertEqual(
            [call_args.args[1:] for call_args in app.row.call_args_list],
            [
                ("Time zone", "Europe/Stockholm"),
                ("Automatic time synchronization", "On"),
                ("Clock synchronization", "Not synchronized"),
            ],
        )
        status_label.set_text.assert_called_once_with(
            "Local date and time status read. No settings were changed.",
        )
        app.announce_to_screen_reader.assert_called_once_with(
            status_label, "Local date and time status read. No settings were changed.",
        )

    def test_time_status_reports_unavailable_read(self):
        app = Mock()
        status_label = Mock()
        UbuntuStart.show_time_status(
            app, Mock(), status_label, Mock(),
            {"timezone": None, "ntp": None, "synchronized": None}, "unavailable",
        )
        self.assertEqual(app.row.call_count, 3)
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
