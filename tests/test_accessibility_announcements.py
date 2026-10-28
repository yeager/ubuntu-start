import unittest
from unittest.mock import Mock, call, patch

from ubuntu_start import Adw, Gdk, Gtk, UbuntuStart


class AccessibilityAnnouncementTests(unittest.TestCase):
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
            {"output": (65, False), "input": (20, True), "error": None},
            announce=True,
        )

        output.set_subtitle.assert_called_once_with("65% · Not muted")
        input_device.set_subtitle.assert_called_once_with("20% · Muted")
        self.app.announce_to_screen_reader.assert_called_once_with(
            output,
            "Speaker output: 65% · Not muted Microphone input: 20% · Muted",
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

        self.app.row.assert_called_once_with(
            rows, "No battery information",
            "No battery information found. This computer may not have a battery, or the system does not expose battery data.",
        )
        self.app.announce_to_screen_reader.assert_not_called()

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
            call("GitHub repository", "https://github.com/yeager/ubuntu-start"),
            call("Daniel Nylander's website", "https://www.danielnylander.se"),
        ])
        dialog.present.assert_called_once_with(app.get_active_window.return_value)


if __name__ == "__main__":
    unittest.main()
