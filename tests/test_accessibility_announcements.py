import unittest
from unittest.mock import Mock, patch

from ubuntu_start import Adw, Gtk, UbuntuStart


class AccessibilityAnnouncementTests(unittest.TestCase):
    def setUp(self):
        self.app = Mock()

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
        dialog.add_link.assert_called_once_with(
            "GitHub repository", "https://github.com/yeager/ubuntu-start",
        )
        dialog.present.assert_called_once_with(app.get_active_window.return_value)


if __name__ == "__main__":
    unittest.main()
