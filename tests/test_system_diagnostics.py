import subprocess
import tempfile
import unittest
from types import SimpleNamespace
from io import BytesIO
import urllib.error
from pathlib import Path
from unittest.mock import patch

from system_diagnostics import (
    ACCESSIBILITY_SETTINGS,
    parse_accessibility_settings,
    build_support_report,
    parse_cpu_model,
    parse_bluetooth_controller_status,
    parse_default_route,
    parse_memory_kib,
    parse_neighbor_mac,
    parse_nmcli_device_status,
    parse_interface_ip_status,
    parse_pactl_mute,
    parse_pactl_volume,
    parse_printer_status,
    parse_printer_job_counts,
    parse_wpctl_endpoint_name,
    parse_wpctl_volume,
    lookup_oui_vendor,
    lookup_pci_device_name,
    read_pci_devices,
    read_audio_status,
    read_accessibility_settings,
    parse_apt_upgrade_simulation,
    parse_dpkg_audit,
    read_package_health,
    read_battery_status,
    battery_is_discharging,
    battery_power_status_unknown,
    read_apt_update_status,
    read_reboot_required,
    read_power_profile,
    run_cpu_benchmark,
    clear_benchmark_baselines,
    load_benchmark_baselines,
    save_benchmark_baseline,
    find_benchmark_tool,
    benchmark_score_change_percent,
    find_graphics_benchmark_tool,
    parse_glmark2_score,
    parse_secure_boot_status,
    read_secure_boot_status,
    read_memory_status,
    parse_pressure_status,
    pressure_threshold_exceeded,
    read_resource_pressure,
    read_bluetooth_status,
    parse_failed_services,
    read_failed_services,
    read_temperature_sensors,
    sensor_near_critical_limit,
    read_hardware_details,
    read_network_devices,
    read_rfkill_status,
    read_network_adapter_details,
    read_interface_ip_status,
    read_printer_status,
    read_storage_status,
    read_storage_locations,
    read_video_devices,
    read_display_connectors,
    parse_time_status,
    read_time_status,
    read_usb_devices,
    lookup_usb_device_name,
    read_wifi_link_status,
    parse_iw_link_status,
    run_network_diagnostics,
)


class BenchmarkTests(unittest.TestCase):
    def test_benchmark_baselines_persist_scores_with_private_file_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "benchmarks.json"
            self.assertTrue(save_benchmark_baseline(
                "cpu", 1234, 1.0, path, recorded_at="2026-10-29T10:00:00+00:00",
            ))
            self.assertTrue(save_benchmark_baseline(
                "graphics", 5678, path=path, recorded_at="2026-10-29T10:01:00+00:00",
                session_type="wayland",
            ))

            baselines = load_benchmark_baselines(path, session_type="wayland")
            self.assertEqual(baselines["cpu"]["score"], 1234.0)
            self.assertEqual(baselines["cpu"]["duration_seconds"], 1.0)
            self.assertEqual(baselines["graphics"]["score"], 5678.0)
            self.assertEqual(baselines["graphics"]["session_type"], "wayland")
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertNotIn("hostname", path.read_text(encoding="utf-8"))
            self.assertNotIn("graphics", load_benchmark_baselines(path, session_type="x11"))

    def test_benchmark_baselines_ignore_invalid_scores_and_unknown_methods(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "benchmarks.json"
            path.write_text(
                '{"schema_version":1,"baselines":{'
                '"cpu":{"method":"python-integer-loop-v1","score":NaN},'
                '"graphics":{"method":"unknown","score":500}}}',
                encoding="utf-8",
            )
            self.assertEqual(load_benchmark_baselines(path), {})
            self.assertFalse(save_benchmark_baseline("cpu", float("inf"), path=path))
            self.assertFalse(save_benchmark_baseline("unknown", 10, path=path))

    def test_benchmark_baselines_ignore_unsupported_schema_versions(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "benchmarks.json"
            path.write_text(
                '{"schema_version":2,"baselines":{"cpu":'
                '{"method":"python-integer-loop-v1","score":100}}}',
                encoding="utf-8",
            )
            self.assertEqual(load_benchmark_baselines(path), {})

    def test_benchmark_baselines_can_be_cleared(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "benchmarks.json"
            self.assertTrue(save_benchmark_baseline("cpu", 1234, 1.0, path))
            self.assertTrue(clear_benchmark_baselines(path))
            self.assertFalse(path.exists())
            self.assertEqual(load_benchmark_baselines(path), {})
            self.assertTrue(clear_benchmark_baselines(path))

    def test_battery_readiness_uses_reported_state(self):
        self.assertTrue(battery_is_discharging([{"status": "Discharging"}]))
        self.assertFalse(battery_is_discharging([{"status": "Charging"}]))
        self.assertFalse(battery_power_status_unknown([]))
        self.assertTrue(battery_power_status_unknown([{"status": "Unknown"}]))
        self.assertFalse(battery_power_status_unknown([{"status": "Full"}]))

    def test_temperature_readiness_uses_hottest_sensor_reported_limit(self):
        self.assertTrue(sensor_near_critical_limit([
            {"name": "CPU", "temperature_c": 91.0, "critical_c": 100.0},
        ]))
        self.assertFalse(sensor_near_critical_limit([
            {"name": "CPU", "temperature_c": 80.0, "critical_c": 100.0},
        ]))
        self.assertFalse(sensor_near_critical_limit([
            {"name": "CPU", "temperature_c": 91.0},
        ]))

    def test_cpu_benchmark_returns_positive_metrics(self):
        result = run_cpu_benchmark(0.1)
        self.assertGreater(result["iterations"], 0)
        self.assertGreater(result["duration_seconds"], 0)
        self.assertGreater(result["iterations_per_second"], 0)

    def test_score_change_compares_to_previous_run(self):
        self.assertEqual(benchmark_score_change_percent(110, 100), 10.0)
        self.assertEqual(benchmark_score_change_percent(90, 100), -10.0)

    def test_score_change_rejects_missing_or_invalid_baseline(self):
        self.assertIsNone(benchmark_score_change_percent(110, 0))
        self.assertIsNone(benchmark_score_change_percent(float("inf"), 100))

    @patch("system_diagnostics.shutil.which", return_value="/usr/bin/glmark2")
    def test_benchmark_tool_lookup_is_allowlisted(self, _which):
        self.assertEqual(find_benchmark_tool("glmark2"), "/usr/bin/glmark2")
        self.assertIsNone(find_benchmark_tool("sh"))

    @patch("system_diagnostics.find_benchmark_tool")
    def test_graphics_launcher_follows_session_type(self, find_tool):
        find_tool.side_effect = lambda name: {
            "glmark2": "/usr/bin/glmark2",
            "glmark2-wayland": "/usr/bin/glmark2-wayland",
        }.get(name)

        self.assertEqual(find_graphics_benchmark_tool("x11"), "/usr/bin/glmark2")
        self.assertEqual(find_graphics_benchmark_tool("wayland"), "/usr/bin/glmark2-wayland")
        self.assertEqual(find_tool.call_count, 2)

    def test_parses_glmark2_final_score(self):
        self.assertEqual(
            parse_glmark2_score("[scene] FPS: 120\n    glmark2 Score: 1234 \n"),
            1234,
        )

    def test_rejects_missing_or_malformed_glmark2_score(self):
        self.assertIsNone(parse_glmark2_score("glmark2 Score: 0x10"))
        self.assertIsNone(parse_glmark2_score("no final score"))


class SupportReportTests(unittest.TestCase):
    def test_report_contains_only_reviewable_system_details_and_latency(self):
        report = build_support_report(
            [("Ubuntu version", "Ubuntu 24.04"), ("Architecture", "x86_64")],
            {
                "dns_latency_ms": 12.3,
                "gateway_latency_ms": 0.8,
                "gateway": "192.168.1.1",
                "gateway_interface": "wlan0",
                "gateway_mac": "AA:BB:CC:DD:EE:FF",
                "gateway_vendor": "Example Vendor",
            },
        )
        self.assertIn("Ubuntu 24.04", report)
        self.assertIn('"dns_latency_ms": 12.3', report)
        self.assertIn('"gateway_reachable": true', report)
        for private_value in ("192.168.1.1", "wlan0", "AA:BB:CC:DD:EE:FF", "Example Vendor"):
            self.assertNotIn(private_value, report)

    def test_report_without_network_tests_does_not_claim_a_test_ran(self):
        report = build_support_report([("Architecture", "x86_64")])
        self.assertIn("system", report)
        self.assertNotIn("network_checks", report)

    def test_report_marks_gateway_reachability_unknown_without_a_ping_reply(self):
        for error in ("ping-not-installed", "timeout", "no-response", "no-default-route"):
            with self.subTest(error=error):
                report = build_support_report(
                    [("Architecture", "x86_64")],
                    {"gateway_error": error, "gateway_latency_ms": None},
                )
                self.assertIn('"gateway_reachable": null', report)


class AccessibilitySettingsTests(unittest.TestCase):
    def test_parses_only_allowlisted_gnome_accessibility_values(self):
        outputs = {
            "applications": """org.gnome.desktop.a11y.applications screen-reader-enabled true
org.gnome.desktop.a11y.applications screen-magnifier-enabled false
org.gnome.desktop.a11y.applications screen-keyboard-enabled true
org.gnome.desktop.a11y.applications unrelated-setting 'private value'
""",
            "interface": "org.gnome.desktop.a11y.interface high-contrast true\n",
            "keyboard": """org.gnome.desktop.a11y.keyboard stickykeys-enable true
org.gnome.desktop.a11y.keyboard slowkeys-enable false
org.gnome.desktop.a11y.keyboard bouncekeys-enable true
org.gnome.desktop.a11y.keyboard mousekeys-enable false
""",
            "desktop": """org.gnome.desktop.interface text-scaling-factor 1.25
org.gnome.desktop.interface cursor-size 48
""",
            "window": "org.gnome.desktop.wm.preferences visual-bell false\n",
        }
        self.assertEqual(parse_accessibility_settings(outputs), {
            "screen_reader": True,
            "screen_magnifier": False,
            "screen_keyboard": True,
            "high_contrast": True,
            "sticky_keys": True,
            "slow_keys": False,
            "bounce_keys": True,
            "mouse_keys": False,
            "text_scale": 1.25,
            "cursor_size": 48,
            "visual_bell": False,
        })
        self.assertNotIn("private value", repr(parse_accessibility_settings(outputs)))

    @patch("system_diagnostics.shutil.which", return_value="/usr/bin/gsettings")
    @patch("system_diagnostics.subprocess.run")
    def test_reads_only_allowlisted_gnome_keys_without_writing_settings(self, run, _which):
        run.side_effect = [
            subprocess.CompletedProcess([], 0, "true\n", ""),
            subprocess.CompletedProcess([], 0, "false\n", ""),
            subprocess.CompletedProcess([], 0, "true\n", ""),
            subprocess.CompletedProcess([], 0, "false\n", ""),
            subprocess.CompletedProcess([], 0, "true\n", ""),
            subprocess.CompletedProcess([], 0, "false\n", ""),
            subprocess.CompletedProcess([], 0, "true\n", ""),
            subprocess.CompletedProcess([], 0, "false\n", ""),
            subprocess.CompletedProcess([], 0, "1.0\n", ""),
            subprocess.CompletedProcess([], 0, "32\n", ""),
            subprocess.CompletedProcess([], 0, "false\n", ""),
        ]
        settings, error = read_accessibility_settings()
        self.assertIsNone(error)
        self.assertTrue(settings["screen_reader"])
        self.assertFalse(settings["high_contrast"])
        self.assertTrue(settings["sticky_keys"])
        self.assertFalse(settings["slow_keys"])
        self.assertTrue(settings["bounce_keys"])
        self.assertFalse(settings["mouse_keys"])
        self.assertFalse(settings["visual_bell"])
        self.assertEqual(settings["cursor_size"], 32)
        self.assertEqual(len(run.call_args_list), 11)
        self.assertTrue(all(call.args[0][1] == "get" for call in run.call_args_list))
        self.assertEqual(
            [tuple(call.args[0][2:]) for call in run.call_args_list],
            list(ACCESSIBILITY_SETTINGS),
        )
        self.assertEqual(run.call_args_list[0].kwargs["env"]["LC_ALL"], "C")

    @patch("system_diagnostics.shutil.which", return_value=None)
    def test_handles_missing_gsettings(self, _which):
        settings, error = read_accessibility_settings()
        self.assertEqual(error, "not-installed")
        self.assertTrue(all(value is None for value in settings.values()))


class TimeStatusTests(unittest.TestCase):
    def test_parses_only_allowlisted_timezone_and_sync_values(self):
        status = parse_time_status(
            "Timezone=Europe/Stockholm\nCanNTP=yes\nNTP=no\nNTPSynchronized=yes\n"
            "LocalRTC=no\nSecret=private\n"
        )
        self.assertEqual(status, {
            "timezone": "Europe/Stockholm", "can_ntp": True, "ntp": False, "synchronized": True,
        })
        self.assertNotIn("private", repr(status))

    def test_rejects_invalid_values(self):
        self.assertEqual(parse_time_status("Timezone=Europe/Stockholm; cat /etc/passwd\nNTP=maybe\n"), {
            "timezone": None, "can_ntp": None, "ntp": None, "synchronized": None,
        })

    @patch("system_diagnostics.shutil.which", return_value="/usr/bin/timedatectl")
    @patch("system_diagnostics.subprocess.run")
    def test_reads_only_local_status_and_does_not_trigger_sync(self, run, _which):
        run.return_value = subprocess.CompletedProcess(
            [], 0, "Timezone=Europe/Stockholm\nNTP=yes\nNTPSynchronized=yes\n", "",
        )
        status, error = read_time_status()
        self.assertIsNone(error)
        self.assertEqual(status["timezone"], "Europe/Stockholm")
        self.assertEqual(run.call_args.args[0], [
            "/usr/bin/timedatectl", "show", "--property=Timezone", "--property=CanNTP",
            "--property=NTP", "--property=NTPSynchronized",
        ])
        self.assertEqual(run.call_args.kwargs["env"]["LC_ALL"], "C")

    @patch("system_diagnostics.shutil.which", return_value=None)
    def test_reports_missing_timedatectl(self, _which):
        status, error = read_time_status()
        self.assertEqual(error, "not-installed")
        self.assertTrue(all(value is None for value in status.values()))

    @patch("system_diagnostics.shutil.which", return_value="/usr/bin/timedatectl")
    @patch("system_diagnostics.subprocess.run", side_effect=subprocess.TimeoutExpired("timedatectl", 3))
    def test_reports_timeout(self, _run, _which):
        _status, error = read_time_status()
        self.assertEqual(error, "timeout")


class ParseNetworkStatusTests(unittest.TestCase):
    def test_reads_radio_block_flags_from_allowlisted_sysfs_fields(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            wifi = root / "rfkill0"
            wifi.mkdir()
            (wifi / "type").write_text("wlan\n", encoding="ascii")
            (wifi / "soft").write_text("0\n", encoding="ascii")
            (wifi / "hard").write_text("1\n", encoding="ascii")
            bluetooth = root / "rfkill1"
            bluetooth.mkdir()
            (bluetooth / "type").write_text("bluetooth\n", encoding="ascii")
            (bluetooth / "soft").write_text("0\n", encoding="ascii")
            (bluetooth / "hard").write_text("0\n", encoding="ascii")
            wimax = root / "rfkill2"
            wimax.mkdir()
            (wimax / "type").write_text("wimax\n", encoding="ascii")
            (wimax / "soft").write_text("1\n", encoding="ascii")
            (wimax / "hard").write_text("0\n", encoding="ascii")
            malformed = root / "rfkill3"
            malformed.mkdir()
            (malformed / "type").write_text("unknown-device\n", encoding="ascii")
            (malformed / "soft").write_text("0\n", encoding="ascii")
            (malformed / "hard").write_text("0\n", encoding="ascii")
            (root / "rfkill-not-a-device").mkdir()

            result = read_rfkill_status(root)

        self.assertEqual(result, [
            {"type": "wlan", "soft_blocked": False, "hard_blocked": True},
            {"type": "bluetooth", "soft_blocked": False, "hard_blocked": False},
            {"type": "wimax", "soft_blocked": True, "hard_blocked": False},
        ])

    def test_distinguishes_missing_rfkill_directory_from_no_radios(self):
        with tempfile.TemporaryDirectory() as temporary:
            self.assertIsNone(read_rfkill_status(Path(temporary) / "missing"))
            self.assertEqual(read_rfkill_status(temporary), [])

    def test_reads_pci_network_adapter_name_id_and_driver_from_sysfs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            adapter = root / "bus/pci/devices/0000:00:01.0"
            adapter.mkdir(parents=True)
            (adapter / "vendor").write_text("0x1234\n", encoding="ascii")
            (adapter / "device").write_text("0x5678\n", encoding="ascii")
            (adapter / "serial").write_text("DO-NOT-READ\n", encoding="ascii")
            driver = root / "bus/pci/drivers/example_net"
            driver.mkdir(parents=True)
            (adapter / "driver").symlink_to(driver)
            interface = root / "class/net/enp1s0"
            interface.mkdir(parents=True)
            (interface / "device").symlink_to(adapter)
            database = root / "pci.ids"
            database.write_text(
                "1234  Example Vendor\n\t5678  Example Network Adapter\n",
                encoding="ascii",
            )

            details = read_network_adapter_details(
                "enp1s0", root, pci_databases=(str(database),),
            )

        self.assertEqual(details, {
            "bus": "PCI", "id": "1234:5678",
            "name": "Example Vendor Example Network Adapter", "driver": "example_net",
        })
        self.assertNotIn("DO-NOT-READ", repr(details))

    def test_reads_usb_network_adapter_from_parent_device(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            usb_device = root / "devices/usb1/1-2"
            usb_device.mkdir(parents=True)
            (usb_device / "idVendor").write_text("046d\n", encoding="ascii")
            (usb_device / "idProduct").write_text("c534\n", encoding="ascii")
            (usb_device / "serial").write_text("DO-NOT-READ\n", encoding="ascii")
            interface_device = usb_device / "1-2:1.0"
            interface_device.mkdir()
            driver = root / "drivers/usbnet"
            driver.mkdir(parents=True)
            (interface_device / "driver").symlink_to(driver)
            interface = root / "class/net/enx001"
            interface.mkdir(parents=True)
            (interface / "device").symlink_to(interface_device)
            database = root / "usb.ids"
            database.write_text(
                "046d  Example USB Vendor\n\tc534  Example Ethernet Adapter\n",
                encoding="ascii",
            )

            details = read_network_adapter_details(
                "enx001", root, usb_databases=(str(database),),
            )

        self.assertEqual(details, {
            "bus": "USB", "id": "046d:c534",
            "name": "Example USB Vendor Example Ethernet Adapter", "driver": "usbnet",
        })
        self.assertNotIn("DO-NOT-READ", repr(details))

    def test_parses_address_families_without_returning_private_addresses(self):
        output = '''[{"ifname":"wlan0","addr_info":[
{"family":"inet","local":"192.168.1.24","prefixlen":24},
{"family":"inet6","local":"fe80::1234","prefixlen":64},
{"family":"inet6","local":"fd00::1234","prefixlen":64},
{"family":"inet","local":"127.0.0.1","prefixlen":8}
]}]'''
        status = parse_interface_ip_status(output)
        self.assertEqual(status, {"ipv4": True, "ipv6": True, "link_local": True})
        self.assertNotIn("192.168.1.24", repr(status))

    def test_reports_link_local_only_and_rejects_malformed_json(self):
        output = '[{"addr_info":[{"family":"inet","local":"169.254.2.5","prefixlen":16}]}]'
        self.assertEqual(
            parse_interface_ip_status(output),
            {"ipv4": False, "ipv6": False, "link_local": True},
        )
        self.assertIsNone(parse_interface_ip_status("not json"))

    @patch("system_diagnostics.shutil.which", return_value="/usr/sbin/ip")
    @patch("system_diagnostics._run_local")
    def test_reads_only_local_interface_address_family_status(self, run, _which):
        run.return_value = subprocess.CompletedProcess(
            ["ip"], 0,
            '[{"ifname":"wlan0","addr_info":[{"family":"inet","local":"10.0.0.5","prefixlen":24}]}]',
            "",
        )
        self.assertEqual(
            read_interface_ip_status("wlan0"),
            {"ipv4": True, "ipv6": False, "link_local": False},
        )
        self.assertEqual(run.call_args.args[0], ["/usr/sbin/ip", "-j", "address", "show", "dev", "wlan0"])

    @patch("system_diagnostics.shutil.which")
    @patch("system_diagnostics._run_local")
    def test_rejects_unexpected_interface_names(self, run, which):
        self.assertIsNone(read_interface_ip_status("wlan0; ping example.com"))
        run.assert_not_called()
        which.assert_not_called()

    def test_parses_active_wifi_metrics_without_returning_network_identifiers(self):
        output = """Connected to AA:BB:CC:DD:EE:FF (on wlp2s0)
\tSSID: private-network-name
\tsignal: -53 dBm
\trx bitrate: 780.0 MBit/s
\ttx bitrate: 650.5 MBit/s
"""
        details = parse_iw_link_status(output)
        self.assertEqual(details, {
            "signal_dbm": -53,
            "rx_bitrate_mbps": 780.0,
            "tx_bitrate_mbps": 650.5,
        })
        self.assertNotIn("private-network-name", repr(details))
        self.assertNotIn("AA:BB:CC:DD:EE:FF", repr(details))

    @patch("system_diagnostics.shutil.which", return_value="/usr/sbin/iw")
    @patch("system_diagnostics._run_local")
    def test_reads_current_wifi_link_without_scanning(self, run, _which):
        run.return_value = subprocess.CompletedProcess(
            ["iw", "dev", "wlp2s0", "link"], 0, "signal: -62 dBm\n", "",
        )
        self.assertEqual(read_wifi_link_status("wlp2s0"), {"signal_dbm": -62})
        self.assertEqual(run.call_args.args[0], ["/usr/sbin/iw", "dev", "wlp2s0", "link"])

    @patch("system_diagnostics.shutil.which", return_value="/usr/sbin/iw")
    @patch("system_diagnostics._run_local")
    def test_rejects_unexpected_interface_values(self, run, _which):
        self.assertIsNone(read_wifi_link_status("wlan0; reboot"))
        run.assert_not_called()

    def test_parses_devices_and_skips_loopback(self):
        output = """DEVICE:TYPE:STATE
wlp2s0:wifi:connected
eth0:ethernet:disconnected
lo:loopback:unmanaged
"""
        self.assertEqual(
            parse_nmcli_device_status(output),
            [("wlp2s0", "wifi", "connected"), ("eth0", "ethernet", "disconnected")],
        )

    def test_ignores_incomplete_rows(self):
        self.assertEqual(parse_nmcli_device_status("\nmalformed\neth0:ethernet:\n"), [])

    @patch("system_diagnostics.shutil.which", return_value=None)
    def test_reports_missing_network_manager_without_running_a_probe(self, _which):
        self.assertEqual(read_network_devices(), ([], "not-installed"))

    @patch("system_diagnostics.subprocess.run")
    @patch("system_diagnostics.shutil.which", return_value="/usr/bin/nmcli")
    def test_reads_local_device_status_only(self, _which, run):
        run.return_value.returncode = 0
        run.return_value.stdout = "wlp2s0:wifi:connected\n"
        devices, error = read_network_devices()
        self.assertEqual(devices, [("wlp2s0", "wifi", "connected")])
        self.assertIsNone(error)
        command = run.call_args.args[0]
        self.assertEqual(
            command,
            ["nmcli", "--terse", "--fields", "DEVICE,TYPE,STATE", "device", "status"],
        )
        self.assertEqual(run.call_args.kwargs["env"]["LC_ALL"], "C")

    @patch("system_diagnostics.subprocess.run", side_effect=subprocess.TimeoutExpired("nmcli", 3))
    @patch("system_diagnostics.shutil.which", return_value="/usr/bin/nmcli")
    def test_reports_network_manager_timeout(self, _which, _run):
        self.assertEqual(read_network_devices(), ([], "timeout"))


class PrinterStatusTests(unittest.TestCase):
    def test_parses_queue_names_and_only_allowlisted_states(self):
        output = """printer Office_Laser is idle. enabled since Wed Oct 29 10:00:00 2026
printer Old_Printer disabled since Wed Oct 29 10:00:00 2026 - paused by administrator
printer Label_Printer is printing. enabled since Wed Oct 29 10:00:00 2026
printer Queue_Printer is processing job 12. enabled since Wed Oct 29 10:00:00 2026
printer Stopped_Printer stopped since Wed Oct 29 10:00:00 2026 - stopped
job user-secret is printing on Office_Laser
"""
        self.assertEqual(parse_printer_status(output), [
            ("Office_Laser", "idle"),
            ("Old_Printer", "disabled"),
            ("Label_Printer", "printing"),
            ("Queue_Printer", "processing"),
            ("Stopped_Printer", "stopped"),
        ])
        self.assertNotIn("user-secret", repr(parse_printer_status(output)))

    def test_counts_only_jobs_for_known_queues(self):
        output = """Office_Laser-100 alice 1024 confidential-report.pdf
Office_Laser-101 bob 2048 private-document.pdf
Office_Laser-extra unknown
Other_Queue-4 user 10 secret.txt
"""
        counts = parse_printer_job_counts(output, ["Office_Laser"])
        self.assertEqual(counts, {"Office_Laser": 2})
        self.assertNotIn("alice", repr(counts))
        self.assertNotIn("confidential-report", repr(counts))

    @patch("system_diagnostics.shutil.which", return_value="/usr/bin/lpstat")
    @patch("system_diagnostics.subprocess.run")
    def test_queries_local_cups_only_with_stable_locale(self, run, _which):
        run.side_effect = [
            subprocess.CompletedProcess([], 0, "printer Office_Laser is idle. enabled since now\n", ""),
            subprocess.CompletedProcess([], 0, "Office_Laser-100 alice 1024 private.pdf\n", ""),
        ]
        self.assertEqual(read_printer_status(), ([("Office_Laser", "idle", 1)], None))
        self.assertEqual(run.call_args_list[0].args[0], ["/usr/bin/lpstat", "-h", "localhost", "-p"])
        self.assertEqual(run.call_args_list[1].args[0], [
            "/usr/bin/lpstat", "-h", "localhost", "-W", "not-completed", "-o",
        ])
        self.assertEqual(run.call_args.kwargs["env"]["LC_ALL"], "C")

    @patch("system_diagnostics._run_local")
    @patch("system_diagnostics.subprocess.run")
    @patch("system_diagnostics.shutil.which", return_value="/usr/bin/lpstat")
    def test_job_count_failure_preserves_queue_state(self, _which, run, run_local):
        run.return_value = subprocess.CompletedProcess(
            [], 0, "printer Office_Laser is idle. enabled since now\n", "",
        )
        run_local.return_value = None
        self.assertEqual(read_printer_status(), ([("Office_Laser", "idle", None)], None))

    @patch("system_diagnostics.shutil.which", return_value=None)
    def test_reports_missing_cups_tools(self, _which):
        self.assertEqual(read_printer_status(), ([], "not-installed"))

    @patch("system_diagnostics.subprocess.run", side_effect=subprocess.TimeoutExpired("lpstat", 3))
    @patch("system_diagnostics.shutil.which", return_value="/usr/bin/lpstat")
    def test_reports_local_cups_timeout(self, _which, _run):
        self.assertEqual(read_printer_status(), ([], "timeout"))


class FailedServiceTests(unittest.TestCase):
    def test_parses_failed_service_units_and_skips_non_service_rows(self):
        output = """alpha.service loaded failed failed The first service
some.socket loaded failed failed Not a service
good.service loaded active running Should not be marked failed
bad@device\\x20name.service loaded failed failed Device service description
"""
        self.assertEqual(parse_failed_services(output), [
            ("alpha.service", "The first service"),
            ("bad@device\\x20name.service", "Device service description"),
        ])

    @patch("system_diagnostics._run_local")
    @patch("system_diagnostics.shutil.which", return_value="/usr/bin/systemctl")
    def test_reads_failed_service_summary_without_privileged_changes(self, _which, run_local):
        run_local.return_value = subprocess.CompletedProcess(
            [], 0, "alpha.service loaded failed failed Example service\n", "",
        )
        self.assertEqual(read_failed_services(), ([
            ("alpha.service", "Example service"),
        ], None))
        self.assertEqual(run_local.call_args.args[0], [
            "/usr/bin/systemctl", "--failed", "--type=service", "--no-legend", "--plain", "--no-pager",
        ])
        self.assertEqual(run_local.call_args.kwargs["env"]["LC_ALL"], "C")

    @patch("system_diagnostics.shutil.which", return_value=None)
    def test_handles_missing_systemctl(self, _which):
        self.assertEqual(read_failed_services(), ([], "not-installed"))


class BluetoothStatusTests(unittest.TestCase):
    def test_parses_controller_power_without_exposing_mac_address(self):
        output = "Controller AA:BB:CC:DD:EE:FF (public)\n\tPowered: yes\n"
        self.assertEqual(parse_bluetooth_controller_status(output), "powered")
        self.assertNotIn("AA:BB:CC:DD:EE:FF", parse_bluetooth_controller_status(output))
        self.assertEqual(parse_bluetooth_controller_status(output.replace("yes", "no")), "off")
        self.assertEqual(parse_bluetooth_controller_status(""), "no-controller")
        self.assertEqual(parse_bluetooth_controller_status("Controller AA:BB:CC:DD:EE:FF\n"), "unknown")

    @patch("system_diagnostics.shutil.which", return_value=None)
    def test_handles_missing_bluetooth_command(self, _which):
        with tempfile.TemporaryDirectory() as temporary:
            (Path(temporary) / "hci0").mkdir()
            self.assertEqual(read_bluetooth_status(controller_path=temporary), "not-installed")

    @patch("system_diagnostics._run_local")
    @patch("system_diagnostics.shutil.which")
    def test_reports_absent_controller_without_waiting_on_bluetooth_service(self, which, run):
        with tempfile.TemporaryDirectory() as temporary:
            self.assertEqual(read_bluetooth_status(controller_path=temporary), "no-controller")
        which.assert_not_called()
        run.assert_not_called()

    @patch("system_diagnostics._run_local")
    @patch("system_diagnostics.shutil.which")
    def test_reads_service_and_controller_state_without_scanning(self, which, run):
        which.side_effect = lambda command: {
            "systemctl": "/usr/bin/systemctl", "bluetoothctl": "/usr/bin/bluetoothctl",
        }.get(command)
        run.side_effect = [
            subprocess.CompletedProcess(["systemctl", "is-active", "bluetooth.service"], 0, "active\n", ""),
            subprocess.CompletedProcess(
                ["bluetoothctl", "show"], 0,
                "Controller AA:BB:CC:DD:EE:FF (public)\n\tPowered: yes\n", "",
            ),
        ]
        with tempfile.TemporaryDirectory() as temporary:
            (Path(temporary) / "hci0").mkdir()
            self.assertEqual(read_bluetooth_status(controller_path=temporary), "powered")
        self.assertEqual(run.call_args_list[0].args[0], [
            "/usr/bin/systemctl", "is-active", "bluetooth.service",
        ])
        self.assertEqual(run.call_args_list[0].kwargs["env"]["LC_ALL"], "C")
        self.assertEqual(run.call_args_list[1].args[0], ["/usr/bin/bluetoothctl", "show"])

    @patch("system_diagnostics._run_local")
    @patch("system_diagnostics.shutil.which")
    def test_distinguishes_inactive_bluetooth_service(self, which, run):
        which.side_effect = lambda command: {
            "systemctl": "/usr/bin/systemctl", "bluetoothctl": "/usr/bin/bluetoothctl",
        }.get(command)
        run.return_value = subprocess.CompletedProcess(
            ["systemctl", "is-active", "bluetooth.service"], 3, "inactive\n", "",
        )
        with tempfile.TemporaryDirectory() as temporary:
            (Path(temporary) / "hci0").mkdir()
            self.assertEqual(read_bluetooth_status(controller_path=temporary), "service-inactive")
        run.assert_called_once()
        self.assertEqual(run.call_args.args[0], [
            "/usr/bin/systemctl", "is-active", "bluetooth.service",
        ])
        self.assertEqual(run.call_args.kwargs["env"]["LC_ALL"], "C")


class AudioStatusTests(unittest.TestCase):
    def test_parses_wpctl_volume_and_mute_state(self):
        self.assertEqual(parse_wpctl_volume("Volume: 0.45 [MUTED]\n"), (45, True))
        self.assertEqual(parse_wpctl_volume("Volume: 1.20\n"), (120, False))
        self.assertIsNone(parse_wpctl_volume("No default node"))

    def test_rejects_wpctl_volume_that_overflows_when_converted_to_percent(self):
        self.assertIsNone(parse_wpctl_volume(f"Volume: {'9' * 400}\n"))

    def test_parses_only_sanitized_human_facing_wpctl_endpoint_name(self):
        output = '''id 47, type PipeWire:Interface:Node
  * node.description = "USB headphones\\\" Left"
    device.serial = "DO-NOT-INCLUDE"
'''

        self.assertEqual(parse_wpctl_endpoint_name(output), 'USB headphones" Left')
        self.assertIsNone(parse_wpctl_endpoint_name('node.name = "alsa_output.card"'))

    def test_parses_pactl_volume_and_mute_state(self):
        self.assertEqual(parse_pactl_volume("Volume: front-left: 65536 / 75% / -7.50 dB"), 75)
        self.assertEqual(parse_pactl_mute("Mute: yes\n"), True)
        self.assertEqual(parse_pactl_mute("Mute: no\n"), False)
        self.assertIsNone(parse_pactl_mute("Unavailable"))

    @patch("system_diagnostics.shutil.which", side_effect=lambda name: "/usr/bin/wpctl" if name == "wpctl" else None)
    @patch("system_diagnostics._run_local")
    def test_reads_wpctl_defaults_without_playing_audio(self, run, _which):
        run.side_effect = [
            subprocess.CompletedProcess([], 0, "Volume: 0.60\n", ""),
            subprocess.CompletedProcess([], 0, '  * node.description = "USB speakers"\n', ""),
            subprocess.CompletedProcess([], 0, "Volume: 0.25 [MUTED]\n", ""),
            subprocess.CompletedProcess([], 0, '  * node.description = "Built-in microphone"\n', ""),
        ]
        self.assertEqual(
            read_audio_status(),
            {
                "output": (60, False), "input": (25, True),
                "output_name": "USB speakers", "input_name": "Built-in microphone",
                "error": None,
            },
        )
        self.assertEqual(run.call_args_list[0].args[0], ["/usr/bin/wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"])
        self.assertEqual(run.call_args_list[1].args[0], ["/usr/bin/wpctl", "inspect", "@DEFAULT_AUDIO_SINK@"])
        self.assertEqual(run.call_args_list[2].args[0], ["/usr/bin/wpctl", "get-volume", "@DEFAULT_AUDIO_SOURCE@"])

    @patch("system_diagnostics.shutil.which", side_effect=lambda name: "/usr/bin/pactl" if name == "pactl" else None)
    @patch("system_diagnostics._run_local")
    def test_falls_back_to_pactl(self, run, _which):
        run.side_effect = [
            subprocess.CompletedProcess([], 0, "Volume: front-left: 65536 / 80%", ""),
            subprocess.CompletedProcess([], 0, "Mute: no", ""),
            subprocess.CompletedProcess([], 0, "Volume: front-left: 65536 / 40%", ""),
            subprocess.CompletedProcess([], 0, "Mute: yes", ""),
        ]
        self.assertEqual(
            read_audio_status(),
            {
                "output": (80, False), "input": (40, True),
                "output_name": None, "input_name": None, "error": None,
            },
        )

    @patch(
        "system_diagnostics.shutil.which",
        side_effect=lambda name: f"/usr/bin/{name}" if name in {"wpctl", "pactl"} else None,
    )
    @patch("system_diagnostics._run_local")
    def test_falls_back_per_endpoint_when_wpctl_has_no_default_source(self, run, _which):
        run.side_effect = [
            subprocess.CompletedProcess([], 0, "Volume: 0.60\n", ""),
            subprocess.CompletedProcess([], 0, 'node.description = "USB speakers"\n', ""),
            subprocess.CompletedProcess([], 1, "", "No default source"),
            subprocess.CompletedProcess([], 0, "Volume: front-left: 65536 / 35%", ""),
            subprocess.CompletedProcess([], 0, "Mute: no", ""),
        ]
        self.assertEqual(
            read_audio_status(),
            {
                "output": (60, False), "input": (35, False),
                "output_name": "USB speakers", "input_name": None, "error": None,
            },
        )
        self.assertEqual(len(run.call_args_list), 5)
        self.assertEqual(
            run.call_args_list[3].args[0],
            ["/usr/bin/pactl", "get-source-volume", "@DEFAULT_SOURCE@"],
        )

    @patch("system_diagnostics.shutil.which", return_value=None)
    def test_reports_missing_audio_tools(self, _which):
        self.assertEqual(read_audio_status(), {
            "output": None, "input": None, "output_name": None,
            "input_name": None, "error": "not-installed",
        })


class ParseHardwareTests(unittest.TestCase):
    def test_reads_hwmon_temperature_and_critical_threshold(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            hwmon = root / "hwmon/hwmon0"
            hwmon.mkdir(parents=True)
            (hwmon / "name").write_text("coretemp\n", encoding="ascii")
            (hwmon / "temp1_label").write_text("Package id 0\n", encoding="ascii")
            (hwmon / "temp1_input").write_text("48625\n", encoding="ascii")
            (hwmon / "temp1_crit").write_text("100000\n", encoding="ascii")
            (hwmon / "temp2_input").write_text("invalid\n", encoding="ascii")
            result = read_temperature_sensors(root / "hwmon", root / "thermal")
        self.assertEqual(result, [{
            "name": "coretemp · Package id 0",
            "temperature_c": 48.6,
            "critical_c": 100.0,
        }])

    def test_falls_back_to_thermal_zones_when_hwmon_has_no_temperatures(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            zone = root / "thermal/thermal_zone0"
            zone.mkdir(parents=True)
            (zone / "type").write_text("acpitz\n", encoding="ascii")
            (zone / "temp").write_text("42000\n", encoding="ascii")
            result = read_temperature_sensors(root / "hwmon", root / "thermal")
        self.assertEqual(result, [{"name": "acpitz", "temperature_c": 42.0}])

    @patch("system_diagnostics.platform.release", return_value="6.14.0-test")
    @patch("system_diagnostics.platform.freedesktop_os_release", return_value={"PRETTY_NAME": "Ubuntu test"})
    def test_hardware_overview_includes_os_and_kernel_versions(self, _os_release, _release):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result = read_hardware_details(
                root / "cpuinfo", root / "meminfo", root / "sys", pci_databases=(),
            )
        self.assertEqual(result["operating_system"], "Ubuntu test")
        self.assertEqual(result["kernel"], "6.14.0-test")

    def test_parses_pressure_stall_average_percentages(self):
        output = "some avg10=12.34 avg60=2.00 avg300=0.10 total=100\nfull avg10=1.5 avg60=0.2 avg300=0.0 total=10\n"
        self.assertEqual(parse_pressure_status(output), {"some": 12.34, "full": 1.5})

    def test_rejects_invalid_pressure_percentages(self):
        self.assertIsNone(parse_pressure_status("some avg10=101.0 avg60=1 total=0\n"))
        self.assertIsNone(parse_pressure_status("some avg60=1 total=0\n"))

    def test_pressure_threshold_preserves_unavailable_state(self):
        self.assertIsNone(pressure_threshold_exceeded(None, "cpu", "some", 20))
        self.assertIsNone(pressure_threshold_exceeded({"cpu": {}}, "cpu", "some", 20))
        self.assertFalse(pressure_threshold_exceeded({"cpu": {"some": 5.0}}, "cpu", "some", 20))
        self.assertTrue(pressure_threshold_exceeded({"cpu": {"some": 20.0}}, "cpu", "some", 20))

    def test_reads_available_system_resource_pressure_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "cpu").write_text("some avg10=1.0 avg60=1 total=0\nfull avg10=0 avg60=0 total=0\n", encoding="ascii")
            (root / "memory").write_text("some avg10=2.0 avg60=1 total=0\nfull avg10=0.1 avg60=0 total=0\n", encoding="ascii")
            result = read_resource_pressure(root)
        self.assertEqual(result, {
            "cpu": {"some": 1.0, "full": 0.0},
            "memory": {"some": 2.0, "full": 0.1},
        })

    def test_reads_ram_and_swap_status_from_meminfo(self):
        with tempfile.TemporaryDirectory() as temporary:
            meminfo = Path(temporary) / "meminfo"
            meminfo.write_text(
                "MemTotal: 1024 kB\nMemAvailable: 256 kB\nSwapTotal: 512 kB\nSwapFree: 128 kB\n",
                encoding="ascii",
            )
            result = read_memory_status(meminfo)
        self.assertEqual(result, {
            "total": 1_048_576,
            "available": 262_144,
            "used": 786_432,
            "swap_total": 524_288,
            "swap_used": 393_216,
        })

    def test_rejects_inconsistent_memory_values(self):
        with tempfile.TemporaryDirectory() as temporary:
            meminfo = Path(temporary) / "meminfo"
            meminfo.write_text("MemTotal: 100 kB\nMemAvailable: 101 kB\n", encoding="ascii")
            self.assertIsNone(read_memory_status(meminfo))

    def test_resolves_graphics_name_from_local_pci_database(self):
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "pci.ids"
            database.write_text(
                """1234  Example Graphics Corp
\t5678  Fast Display 9000
\t\t1234 0001  Example board
ABCD  Another Vendor
\t5678  Different device
""",
                encoding="ascii",
            )
            self.assertEqual(
                lookup_pci_device_name("0x1234", "0xabcd", (str(database),)),
                "Example Graphics Corp",
            )
            self.assertEqual(
                lookup_pci_device_name("1234", "5678", (str(database),)),
                "Example Graphics Corp Fast Display 9000",
            )
            self.assertIsNone(lookup_pci_device_name("invalid", "5678", (str(database),)))

    def test_sanitizes_and_limits_local_pci_database_names(self):
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "pci.ids"
            database.write_text(
                "1234  Vendor\x01" + "V" * 150 + "\n\t5678  Device\x02" + "D" * 150 + "\n",
                encoding="ascii",
            )
            name = lookup_pci_device_name("1234", "5678", (str(database),))
        self.assertEqual(len(name), 120)
        self.assertTrue(name.startswith("Vendor"))
        self.assertTrue(name.isprintable())

    def test_reads_pci_devices_and_driver_without_listing_bridges(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "devices"
            root.mkdir()
            database = Path(temporary) / "pci.ids"
            database.write_text(
                "1234  Example Vendor\n\t5678  Example Network Adapter\n",
                encoding="ascii",
            )
            adapter = root / "0000:00:01.0"
            adapter.mkdir()
            (adapter / "vendor").write_text("0x1234\n", encoding="ascii")
            (adapter / "device").write_text("0x5678\n", encoding="ascii")
            (adapter / "class").write_text("0x020000\n", encoding="ascii")
            driver = Path(temporary) / "drivers" / "e1000e"
            driver.mkdir(parents=True)
            (adapter / "driver").symlink_to(driver)

            bridge = root / "0000:00:02.0"
            bridge.mkdir()
            (bridge / "vendor").write_text("0x1234\n", encoding="ascii")
            (bridge / "device").write_text("0x5678\n", encoding="ascii")
            (bridge / "class").write_text("0x060400\n", encoding="ascii")

            missing_driver = root / "0000:00:03.0"
            missing_driver.mkdir()
            (missing_driver / "vendor").write_text("0xabcd\n", encoding="ascii")
            (missing_driver / "device").write_text("0x0001\n", encoding="ascii")
            (missing_driver / "class").write_text("0x010600\n", encoding="ascii")
            (missing_driver / "serial").write_text("private-serial", encoding="ascii")

            self.assertEqual(read_pci_devices(root, (str(database),)), [
                {"id": "1234:5678", "name": "Example Vendor Example Network Adapter", "driver": "e1000e"},
                {"id": "abcd:0001", "name": None, "driver": None},
            ])

    def test_extracts_cpu_model(self):
        self.assertEqual(
            parse_cpu_model("processor : 0\nmodel name : Example CPU 9000\n"),
            "Example CPU 9000",
        )

    def test_returns_none_for_unavailable_cpu_model(self):
        self.assertIsNone(parse_cpu_model("processor : unknown\n"))

    def test_extracts_memory_total(self):
        self.assertEqual(parse_memory_kib("MemFree: 4 kB\nMemTotal: 16777216 kB\n"), 16777216)
        self.assertIsNone(parse_memory_kib("MemFree: 4 kB\n"))

    def test_reads_hardware_without_serial_number(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sys_root = root / "sys"
            dmi = sys_root / "class/dmi/id"
            dmi.mkdir(parents=True)
            (dmi / "product_name").write_text("Test Laptop", encoding="utf-8")
            (dmi / "product_serial").write_text("DO-NOT-READ", encoding="utf-8")
            drm = sys_root / "class/drm/card0/device"
            drm.mkdir(parents=True)
            (drm / "vendor").write_text("0x1234", encoding="utf-8")
            (drm / "device").write_text("0xabcd", encoding="utf-8")
            driver = sys_root / "drivers/example_gpu"
            driver.mkdir(parents=True)
            (drm / "driver").symlink_to(driver)
            cpuinfo = root / "cpuinfo"
            cpuinfo.write_text("model name : Example CPU\n", encoding="utf-8")
            meminfo = root / "meminfo"
            meminfo.write_text("MemTotal: 8388608 kB\n", encoding="utf-8")

            pci_ids = root / "pci.ids"
            pci_ids.write_text(
                "1234  Example Graphics Corp\n\tABCD  Example Adapter\n",
                encoding="ascii",
            )
            result = read_hardware_details(
                cpuinfo, meminfo, sys_root, pci_databases=(str(pci_ids),),
            )

        self.assertEqual(result["system_model"], "Test Laptop")
        self.assertEqual(result["processor"], "Example CPU")
        self.assertEqual(result["memory"], "8 GiB")
        self.assertEqual(result["graphics"], [
            "Example Graphics Corp Example Adapter [0x1234:0xabcd] (example_gpu)",
        ])
        self.assertEqual(result["usb_devices"], [])
        self.assertEqual(result["pci_devices"], [])
        self.assertNotIn("DO-NOT-READ", repr(result))

    def test_reads_usb_descriptors_and_interface_driver_without_serial_numbers(self):
        with tempfile.TemporaryDirectory() as temporary:
            devices_root = Path(temporary)
            device = devices_root / "1-2"
            device.mkdir()
            (device / "idVendor").write_text("046d\n", encoding="ascii")
            (device / "idProduct").write_text("c534\n", encoding="ascii")
            (device / "bDeviceClass").write_text("00\n", encoding="ascii")
            (device / "manufacturer").write_text("Logitech\n", encoding="utf-8")
            (device / "product").write_text("USB Receiver\n", encoding="utf-8")
            (device / "serial").write_text("DO-NOT-READ\n", encoding="ascii")
            interface = devices_root / "1-2:1.0"
            interface.mkdir()
            driver = devices_root / "drivers" / "usbhid"
            driver.mkdir(parents=True)
            (interface / "driver").symlink_to(driver)

            root_hub = devices_root / "usb1"
            root_hub.mkdir()
            (root_hub / "idVendor").write_text("1d6b\n", encoding="ascii")
            (root_hub / "idProduct").write_text("0002\n", encoding="ascii")
            (root_hub / "bDeviceClass").write_text("09\n", encoding="ascii")
            (root_hub / "serial").write_text("ROOT-HUB-SERIAL\n", encoding="ascii")

            result = read_usb_devices(devices_root, usb_databases=())

        self.assertEqual(result, [{
            "id": "046d:c534",
            "name": "Logitech USB Receiver",
            "drivers": ["usbhid"],
        }])
        self.assertNotIn("DO-NOT-READ", repr(result))
        self.assertNotIn("ROOT-HUB-SERIAL", repr(result))

    def test_ignores_malformed_usb_hardware_ids(self):
        with tempfile.TemporaryDirectory() as temporary:
            device = Path(temporary) / "1-1"
            device.mkdir()
            (device / "idVendor").write_text("not-an-id\n", encoding="ascii")
            (device / "idProduct").write_text("0001\n", encoding="ascii")

            self.assertEqual(read_usb_devices(temporary), [])

    def test_avoids_repeating_manufacturer_in_usb_product_name(self):
        with tempfile.TemporaryDirectory() as temporary:
            device = Path(temporary) / "1-1"
            device.mkdir()
            (device / "idVendor").write_text("0627\n", encoding="ascii")
            (device / "idProduct").write_text("0001\n", encoding="ascii")
            (device / "manufacturer").write_text("QEMU\n", encoding="utf-8")
            (device / "product").write_text("QEMU USB Tablet\n", encoding="utf-8")

            result = read_usb_devices(temporary, usb_databases=())

        self.assertEqual(result[0]["name"], "QEMU USB Tablet")

    def test_matches_usb_vendor_and_product_in_local_database(self):
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "usb.ids"
            database.write_text(
                """0627  Adomax Technology Co., Ltd
\t0001  QEMU Tablet
0628  Another Vendor
\t0001  Different Device
""",
                encoding="ascii",
            )
            self.assertEqual(
                lookup_usb_device_name("0627", "0001", (str(database),)),
                ("Adomax Technology Co., Ltd", "QEMU Tablet"),
            )
            self.assertIsNone(lookup_usb_device_name("invalid", "0001", (str(database),)))

    def test_sanitizes_and_limits_local_usb_database_names(self):
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "usb.ids"
            database.write_text(
                "0627  Vendor\x01" + "V" * 150 + "\n\t0001  Device\x02" + "D" * 150 + "\n",
                encoding="ascii",
            )
            names = lookup_usb_device_name("0627", "0001", (str(database),))
        self.assertIsNotNone(names)
        self.assertTrue(all(len(name) <= 120 and name.isprintable() for name in names))

    def test_enriches_usb_device_with_vendor_from_local_database(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            device = root / "1-1"
            device.mkdir()
            (device / "idVendor").write_text("0627\n", encoding="ascii")
            (device / "idProduct").write_text("0001\n", encoding="ascii")
            (device / "manufacturer").write_text("QEMU\n", encoding="ascii")
            (device / "product").write_text("QEMU USB Tablet\n", encoding="ascii")
            database = root / "usb.ids"
            database.write_text("0627  Adomax Technology Co., Ltd\n\t0001  QEMU Tablet\n", encoding="ascii")
            result = read_usb_devices(root, usb_databases=(str(database),))
        self.assertEqual(
            result[0]["name"],
            "Adomax Technology Co., Ltd · QEMU USB Tablet",
        )


class VideoDeviceTests(unittest.TestCase):
    def test_reads_only_video_nodes_and_sanitizes_names(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = root / "video0"
            second = root / "video2"
            ignored = root / "media0"
            first.mkdir()
            second.mkdir()
            ignored.mkdir()
            (first / "name").write_text("Integrated Camera\n", encoding="utf-8")
            (second / "name").write_text("USB\n Camera\tUnit", encoding="utf-8")
            (ignored / "name").write_text("Unrelated", encoding="utf-8")

            devices = read_video_devices(root)

        self.assertEqual(devices, ["Integrated Camera", "USB Camera Unit"])

    def test_handles_missing_video_subsystem_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            self.assertEqual(read_video_devices(Path(temporary) / "missing"), [])


class DisplayConnectorTests(unittest.TestCase):
    def test_reads_only_valid_connector_states_without_monitor_identifiers(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name, status, enabled in (
                ("card0-HDMI-A-1", "connected", "enabled"),
                ("card0-DP-1", "disconnected", "disabled"),
                ("card1-Virtual-1", "unknown", None),
                ("card0-connector;bad", "connected", "enabled"),
                ("card0-HDMI-A-2", "faulty", "enabled"),
            ):
                connector = root / name
                connector.mkdir()
                (connector / "status").write_text(f"{status}\n", encoding="utf-8")
                if enabled:
                    (connector / "enabled").write_text(f"{enabled}\n", encoding="utf-8")
            (root / "card0").mkdir()
            (root / "renderD128").mkdir()

            result = read_display_connectors(root)

        self.assertEqual(result, [
            {"name": "card0-DP-1", "status": "disconnected", "enabled": "disabled"},
            {"name": "card0-HDMI-A-1", "status": "connected", "enabled": "enabled"},
            {"name": "card1-Virtual-1", "status": "unknown", "enabled": None},
        ])

    def test_handles_missing_drm_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            self.assertEqual(read_display_connectors(Path(temporary) / "missing"), [])


class LocalDiagnosticsTests(unittest.TestCase):
    def test_parses_upgrade_and_held_back_counts_from_apt_simulation(self):
        output = """NOTE: This is only a simulation!
Inst package-one [1.0] (1.1 repo [amd64])
Inst package-two [2.0] (2.1 repo [amd64])
2 upgraded, 0 newly installed, 0 to remove and 3 not upgraded.
"""
        self.assertEqual(parse_apt_upgrade_simulation(output), (2, 3))

    def test_apt_simulation_parser_rejects_unexpected_output(self):
        self.assertIsNone(parse_apt_upgrade_simulation("Listing...\n"))

    def test_reads_local_reboot_required_marker(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / "reboot-required"
            self.assertFalse(read_reboot_required(marker))
            marker.touch()
            self.assertTrue(read_reboot_required(marker))

    @patch("system_diagnostics.Path.stat", side_effect=PermissionError)
    def test_reports_unknown_when_reboot_marker_cannot_be_read(self, _stat):
        self.assertIsNone(read_reboot_required("/restricted/reboot-required"))

    @patch("system_diagnostics.Path.stat")
    @patch("system_diagnostics._run_local")
    @patch("system_diagnostics.shutil.which", return_value="/usr/bin/apt-get")
    def test_reads_apt_update_status_using_offline_simulation(self, _which, run_local, stat):
        run_local.return_value = SimpleNamespace(
            returncode=0,
            stdout="Inst package-one [1.0] (1.1 repo [amd64])\n1 upgraded, 0 newly installed, 0 to remove and 2 not upgraded.\n",
        )
        stat.return_value = SimpleNamespace(st_mtime_ns=1_234_000_000)
        status, error = read_apt_update_status(update_stamp="/tmp/update-stamp")
        self.assertIsNone(error)
        self.assertEqual(status, {"upgradeable": 1, "held_back": 2, "last_updated": 1})
        self.assertEqual(run_local.call_args.args[:2], (["/usr/bin/apt-get", "-s", "upgrade"], 15.0))
        self.assertEqual(run_local.call_args.kwargs["env"]["LC_ALL"], "C")

    def test_reads_storage_capacity(self):
        result = read_storage_status("/")
        self.assertGreater(result["total"], 0)
        self.assertGreaterEqual(result["free"], 0)
        self.assertGreaterEqual(result["used"], 0)
        self.assertIsInstance(result["read_only"], bool)

    @patch("system_diagnostics.os.statvfs", return_value=SimpleNamespace(f_flag=1))
    @patch("system_diagnostics.shutil.disk_usage", return_value=SimpleNamespace(total=1000, used=700, free=300))
    def test_reports_read_only_filesystem(self, _disk_usage, _statvfs):
        self.assertTrue(read_storage_status("/system")["read_only"])

    @patch("system_diagnostics.os.statvfs", return_value=SimpleNamespace(f_flag=0))
    @patch("system_diagnostics.shutil.disk_usage", return_value=SimpleNamespace(total=1000, used=700, free=300))
    def test_reports_writable_filesystem(self, _disk_usage, _statvfs):
        self.assertFalse(read_storage_status("/system")["read_only"])

    @patch("system_diagnostics.os.statvfs", side_effect=OSError("unavailable"))
    @patch("system_diagnostics.shutil.disk_usage", return_value=SimpleNamespace(total=1000, used=700, free=300))
    def test_handles_unavailable_mount_flags(self, _disk_usage, _statvfs):
        self.assertIsNone(read_storage_status("/system")["read_only"])

    @patch("system_diagnostics.shutil.disk_usage")
    @patch("system_diagnostics.os.stat")
    @patch("system_diagnostics.os.statvfs", return_value=SimpleNamespace(f_flag=0))
    def test_reads_separate_home_filesystem_only_when_mount_differs(self, _statvfs, stat, disk_usage):
        stat.side_effect = [SimpleNamespace(st_dev=1), SimpleNamespace(st_dev=2)]
        disk_usage.side_effect = [
            SimpleNamespace(total=1000, used=700, free=300),
            SimpleNamespace(total=2000, used=1900, free=100),
        ]

        locations = read_storage_locations("/system", "/home/user")

        self.assertEqual(locations, {
            "system": {"total": 1000, "used": 700, "free": 300, "read_only": False},
            "home": {"total": 2000, "used": 1900, "free": 100, "read_only": False},
        })
        self.assertEqual(disk_usage.call_args_list[1].args, (Path("/home/user"),))

    @patch("system_diagnostics.shutil.disk_usage")
    @patch("system_diagnostics.os.stat")
    @patch("system_diagnostics.os.statvfs", return_value=SimpleNamespace(f_flag=0))
    def test_does_not_duplicate_home_when_it_shares_system_filesystem(self, _statvfs, stat, disk_usage):
        stat.side_effect = [SimpleNamespace(st_dev=1), SimpleNamespace(st_dev=1)]
        disk_usage.return_value = SimpleNamespace(total=1000, used=700, free=300)

        locations = read_storage_locations("/system", "/home/user")

        self.assertEqual(locations, {"system": {"total": 1000, "used": 700, "free": 300, "read_only": False}})
        self.assertEqual(disk_usage.call_count, 1)

    def test_reads_battery_capacity_without_device_name(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            battery = root / "BAT0"
            battery.mkdir()
            (battery / "type").write_text("Battery\n", encoding="utf-8")
            (battery / "capacity").write_text("72\n", encoding="utf-8")
            (battery / "status").write_text("Discharging\n", encoding="utf-8")
            result = read_battery_status(root)
        self.assertEqual(result, [{"capacity": 72, "status": "Discharging"}])

    def test_reads_optional_battery_cycle_count(self):
        with tempfile.TemporaryDirectory() as temporary:
            battery = Path(temporary) / "BAT0"
            battery.mkdir()
            (battery / "type").write_text("Battery\n", encoding="utf-8")
            (battery / "capacity").write_text("72\n", encoding="utf-8")
            (battery / "status").write_text("Discharging\n", encoding="utf-8")
            (battery / "cycle_count").write_text("348\n", encoding="utf-8")
            result = read_battery_status(temporary)

        self.assertEqual(result, [{
            "capacity": 72, "status": "Discharging", "cycle_count": 348,
        }])

    def test_ignores_negative_battery_cycle_count(self):
        with tempfile.TemporaryDirectory() as temporary:
            battery = Path(temporary) / "BAT0"
            battery.mkdir()
            (battery / "type").write_text("Battery\n", encoding="utf-8")
            (battery / "capacity").write_text("72\n", encoding="utf-8")
            (battery / "cycle_count").write_text("-1\n", encoding="utf-8")
            result = read_battery_status(temporary)

        self.assertNotIn("cycle_count", result[0])

    def test_reads_optional_vendor_reported_battery_health(self):
        with tempfile.TemporaryDirectory() as temporary:
            battery = Path(temporary) / "BAT0"
            battery.mkdir()
            (battery / "type").write_text("Battery\n", encoding="utf-8")
            (battery / "capacity").write_text("72\n", encoding="utf-8")
            (battery / "state_of_health").write_text("87\n", encoding="utf-8")
            result = read_battery_status(temporary)

        self.assertEqual(result[0]["state_of_health_percent"], 87)

    def test_ignores_out_of_range_vendor_reported_battery_health(self):
        with tempfile.TemporaryDirectory() as temporary:
            battery = Path(temporary) / "BAT0"
            battery.mkdir()
            (battery / "type").write_text("Battery\n", encoding="utf-8")
            (battery / "capacity").write_text("72\n", encoding="utf-8")
            (battery / "state_of_health").write_text("101\n", encoding="utf-8")
            result = read_battery_status(temporary)

        self.assertNotIn("state_of_health_percent", result[0])

    @patch("system_diagnostics._run_local")
    @patch("system_diagnostics.shutil.which", return_value="/usr/bin/powerprofilesctl")
    def test_reads_allowlisted_power_profile(self, _which, run_local):
        run_local.return_value = SimpleNamespace(returncode=0, stdout="balanced\n")
        self.assertEqual(read_power_profile(), "balanced")
        run_local.assert_called_once_with(["/usr/bin/powerprofilesctl", "get"], 2.0)

    @patch("system_diagnostics._run_local")
    @patch("system_diagnostics.shutil.which", return_value="/usr/bin/powerprofilesctl")
    def test_rejects_unexpected_power_profile_output(self, _which, run_local):
        run_local.return_value = SimpleNamespace(returncode=0, stdout="unexpected text\n")
        self.assertEqual(read_power_profile(), "unavailable")

    def test_parses_secure_boot_states_and_setup_mode(self):
        self.assertEqual(parse_secure_boot_status("SecureBoot enabled\n"), "enabled")
        self.assertEqual(parse_secure_boot_status("SecureBoot disabled\n"), "disabled")
        self.assertEqual(parse_secure_boot_status("Platform is in Setup Mode\n"), "setup-mode")
        self.assertEqual(
            parse_secure_boot_status("EFI variables are not supported on this system\n"),
            "unsupported",
        )
        self.assertIsNone(parse_secure_boot_status("unrecognized output\n"))

    @patch("system_diagnostics._run_local")
    @patch("system_diagnostics.shutil.which", return_value="/usr/bin/mokutil")
    def test_reads_secure_boot_state_without_changing_firmware(self, _which, run_local):
        run_local.return_value = SimpleNamespace(
            returncode=0, stdout="SecureBoot enabled\n", stderr="",
        )
        self.assertEqual(read_secure_boot_status(), ("enabled", None))
        run_local.assert_called_once()
        self.assertEqual(run_local.call_args.args[0], ["/usr/bin/mokutil", "--sb-state"])
        self.assertEqual(run_local.call_args.kwargs["env"]["LC_ALL"], "C")

    @patch("system_diagnostics._run_local")
    @patch("system_diagnostics.shutil.which", return_value="/usr/bin/mokutil")
    def test_reads_efi_unsupported_state_written_to_stderr(self, _which, run_local):
        run_local.return_value = SimpleNamespace(
            returncode=1, stdout="", stderr="EFI variables are not supported on this system\n",
        )
        self.assertEqual(read_secure_boot_status(), ("unsupported", None))

    @patch("system_diagnostics.shutil.which", return_value=None)
    def test_reports_missing_mokutil(self, _which):
        self.assertEqual(read_secure_boot_status(), (None, "not-installed"))

    @patch("system_diagnostics._run_local", return_value=None)
    @patch("system_diagnostics.shutil.which", return_value="/usr/bin/mokutil")
    def test_reports_secure_boot_timeout(self, _which, _run_local):
        self.assertEqual(read_secure_boot_status(), (None, "timeout-or-unavailable"))

    @patch("system_diagnostics.shutil.which", return_value=None)
    def test_handles_missing_power_profile_tool(self, _which):
        self.assertEqual(read_power_profile(), "unavailable")

    def test_estimates_battery_capacity_against_design_when_available(self):
        with tempfile.TemporaryDirectory() as temporary:
            battery = Path(temporary) / "BAT0"
            battery.mkdir()
            (battery / "type").write_text("Battery\n", encoding="utf-8")
            (battery / "capacity").write_text("55\n", encoding="utf-8")
            (battery / "status").write_text("Charging\n", encoding="utf-8")
            (battery / "energy_full").write_text("42000000\n", encoding="utf-8")
            (battery / "energy_full_design").write_text("50000000\n", encoding="utf-8")
            result = read_battery_status(temporary)
        self.assertEqual(result[0]["design_capacity_percent"], 84)

    def test_uses_charge_capacity_fallback_and_ignores_invalid_design_values(self):
        with tempfile.TemporaryDirectory() as temporary:
            battery = Path(temporary) / "BAT0"
            battery.mkdir()
            (battery / "type").write_text("Battery\n", encoding="utf-8")
            (battery / "capacity").write_text("55\n", encoding="utf-8")
            (battery / "charge_full").write_text("4200\n", encoding="utf-8")
            (battery / "charge_full_design").write_text("5000\n", encoding="utf-8")
            result = read_battery_status(temporary)
        self.assertEqual(result[0]["design_capacity_percent"], 84)

    @patch("system_diagnostics.urllib.request.build_opener")
    def test_explicit_internet_check_uses_ubuntu_https_without_following_redirects(self, build_opener):
        response = build_opener.return_value.open.return_value.__enter__.return_value
        response.status = 204
        self.assertEqual(read_internet_check(), "reachable:204")
        request = build_opener.return_value.open.call_args.args[0]
        self.assertEqual(request.full_url, "https://ubuntu.com/")
        self.assertEqual(request.get_method(), "HEAD")
        redirect_handler = build_opener.call_args.args[0]
        self.assertIsNone(redirect_handler.redirect_request(None, None, 302, "Found", {}, "https://other.example/"))

    @patch("system_diagnostics.urllib.request.build_opener")
    def test_http_error_still_proves_internet_host_was_reached(self, build_opener):
        build_opener.return_value.open.side_effect = urllib.error.HTTPError(
            "https://ubuntu.com/", 403, "Forbidden", {}, BytesIO(b""),
        )
        self.assertEqual(read_internet_check(), "reachable:403")

    def test_parses_only_valid_default_ipv4_route(self):
        self.assertEqual(
            parse_default_route("default via 192.168.1.1 dev wlp2s0 proto dhcp metric 600\n"),
            ("192.168.1.1", "wlp2s0"),
        )
        self.assertIsNone(parse_default_route("default via not-an-ip dev eth0\n"))

    def test_validates_gateway_mac(self):
        self.assertEqual(
            parse_neighbor_mac("192.168.1.1 dev wlp2s0 lladdr 00:11:22:33:44:55 REACHABLE"),
            "00:11:22:33:44:55",
        )
        self.assertIsNone(parse_neighbor_mac("192.168.1.1 dev wlp2s0 FAILED"))
        self.assertIsNone(parse_neighbor_mac("lladdr invalid"))

    def test_matches_vendor_from_local_database(self):
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "oui.txt"
            database.write_text("00-11-22   (hex)\tExample Network Devices\n", encoding="utf-8")
            self.assertEqual(lookup_oui_vendor("00:11:22:33:44:55", (str(database),)), "Example Network Devices")
            self.assertIsNone(lookup_oui_vendor("AA:BB:CC:DD:EE:FF", (str(database),)))

    @patch("system_diagnostics.shutil.which", return_value="/usr/bin/ping")
    @patch("system_diagnostics.lookup_oui_vendor", return_value="Example Router Co.")
    @patch("system_diagnostics._run_local")
    @patch("system_diagnostics.time.monotonic", side_effect=[1.0, 2.0, 2.03])
    def test_network_diagnostics_use_default_gateway_and_report_latency(self, _clock, run, _vendor, _which):
        run.side_effect = [
            subprocess.CompletedProcess([], 0, "default via 192.168.1.1 dev wlp2s0\n", ""),
            subprocess.CompletedProcess([], 0, "64 bytes from 192.168.1.1: time=0.42 ms\n", ""),
            subprocess.CompletedProcess([], 0, "192.168.1.1 dev wlp2s0 lladdr 00:11:22:33:44:55 REACHABLE\n", ""),
            subprocess.CompletedProcess([], 0, "93.184.216.34 STREAM ubuntu.com\n", ""),
        ]
        result = run_network_diagnostics()
        self.assertEqual(result["gateway"], "192.168.1.1")
        self.assertEqual(result["gateway_latency_ms"], 0.42)
        self.assertEqual(result["gateway_mac"], "00:11:22:33:44:55")
        self.assertEqual(result["gateway_vendor"], "Example Router Co.")
        self.assertEqual(result["dns_latency_ms"], 30.0)
        self.assertEqual(run.call_args_list[1].args[0][-1], "192.168.1.1")
        self.assertEqual(run.call_args_list[2].args[0], ["ip", "-4", "neigh", "show", "to", "192.168.1.1", "dev", "wlp2s0"])
        self.assertEqual(run.call_args_list[3].args[0], ["getent", "ahosts", "ubuntu.com"])

    @patch("system_diagnostics.shutil.which", return_value=None)
    @patch("system_diagnostics.lookup_oui_vendor", return_value=None)
    @patch("system_diagnostics._run_local")
    @patch("system_diagnostics.time.monotonic", side_effect=[5.0, 5.075])
    def test_reports_elapsed_time_when_dns_lookup_fails(self, _clock, run, _vendor, _which):
        run.side_effect = [
            subprocess.CompletedProcess([], 0, "default via 192.168.1.1 dev eth0\n", ""),
            subprocess.CompletedProcess([], 0, "192.168.1.1 dev eth0 lladdr 00:11:22:33:44:55 REACHABLE\n", ""),
            subprocess.CompletedProcess([], 2, "", "temporary failure in name resolution\n"),
        ]

        result = run_network_diagnostics()

        self.assertEqual(result["dns_error"], "lookup-failed")
        self.assertIsNone(result["dns_latency_ms"])
        self.assertEqual(result["dns_test_duration_ms"], 75.0)
        self.assertEqual(run.call_args_list[-1].args[0], ["getent", "ahosts", "ubuntu.com"])

    @patch("system_diagnostics.shutil.which", return_value="/usr/bin/ping")
    @patch("system_diagnostics.lookup_oui_vendor", return_value=None)
    @patch("system_diagnostics._run_local")
    @patch("system_diagnostics.time.monotonic", side_effect=[1.0, 2.0, 2.03])
    def test_uses_ipv6_gateway_when_ipv4_default_is_missing(self, _clock, run, _vendor, _which):
        run.side_effect = [
            subprocess.CompletedProcess([], 0, "", ""),
            subprocess.CompletedProcess([], 0, "default via fe80::1 dev enp1s0 proto ra\n", ""),
            subprocess.CompletedProcess([], 0, "64 bytes from fe80::1: time=1.2 ms\n", ""),
            subprocess.CompletedProcess([], 0, "fe80::1 dev enp1s0 lladdr aa:bb:cc:dd:ee:ff router REACHABLE\n", ""),
            subprocess.CompletedProcess([], 0, "2001:db8::1 STREAM ubuntu.com\n", ""),
        ]
        result = run_network_diagnostics()
        self.assertEqual(result["gateway"], "fe80::1")
        self.assertEqual(result["gateway_latency_ms"], 1.2)
        self.assertEqual(run.call_args_list[2].args[0][:2], ["/usr/bin/ping", "-6"])
        self.assertEqual(run.call_args_list[2].args[0][2:4], ["-I", "enp1s0"])
        self.assertEqual(run.call_args_list[3].args[0][:3], ["ip", "-6", "neigh"])
        self.assertEqual(run.call_args_list[4].args[0], ["getent", "ahosts", "ubuntu.com"])

    @patch("system_diagnostics.shutil.which", return_value=None)
    @patch("system_diagnostics.lookup_oui_vendor", return_value=None)
    @patch("system_diagnostics._run_local")
    @patch("system_diagnostics.time.monotonic", side_effect=[1.0, 1.03])
    def test_reports_missing_ping_without_claiming_gateway_failure(self, _clock, run, _vendor, _which):
        run.side_effect = [
            subprocess.CompletedProcess([], 0, "default via 192.168.1.1 dev eth0\n", ""),
            subprocess.CompletedProcess([], 0, "192.168.1.1 dev eth0 lladdr 00:11:22:33:44:55 REACHABLE\n", ""),
            subprocess.CompletedProcess([], 0, "93.184.216.34 STREAM ubuntu.com\n", ""),
        ]

        result = run_network_diagnostics()

        self.assertEqual(result["gateway_error"], "ping-not-installed")
        self.assertIsNone(result["gateway_latency_ms"])
        self.assertEqual(run.call_args_list[1].args[0], ["ip", "-4", "neigh", "show", "to", "192.168.1.1", "dev", "eth0"])

    @patch("system_diagnostics.shutil.which", return_value="/usr/bin/ping")
    @patch("system_diagnostics.lookup_oui_vendor", return_value=None)
    @patch("system_diagnostics._run_local")
    @patch("system_diagnostics.time.monotonic", side_effect=[1.0, 2.5, 4.0, 4.03])
    def test_reports_ping_timeout_separately(self, _clock, run, _vendor, _which):
        run.side_effect = [
            subprocess.CompletedProcess([], 0, "default via 192.168.1.1 dev eth0\n", ""),
            None,
            subprocess.CompletedProcess([], 0, "192.168.1.1 dev eth0 lladdr 00:11:22:33:44:55 REACHABLE\n", ""),
            subprocess.CompletedProcess([], 0, "93.184.216.34 STREAM ubuntu.com\n", ""),
        ]

        result = run_network_diagnostics()

        self.assertEqual(result["gateway_error"], "timeout")
        self.assertIsNone(result["gateway_latency_ms"])
        self.assertEqual(result["gateway_test_duration_ms"], 1500.0)

    @patch("system_diagnostics.shutil.which", return_value="/usr/bin/ping")
    @patch("system_diagnostics.lookup_oui_vendor", return_value=None)
    @patch("system_diagnostics._run_local")
    @patch("system_diagnostics.time.monotonic", side_effect=[1.0, 2.5, 4.0, 4.03])
    def test_reports_nonzero_ping_result_as_no_response(self, _clock, run, _vendor, _which):
        run.side_effect = [
            subprocess.CompletedProcess([], 0, "default via 192.168.1.1 dev eth0\n", ""),
            subprocess.CompletedProcess([], 1, "", "100% packet loss\n"),
            subprocess.CompletedProcess([], 0, "192.168.1.1 dev eth0 lladdr 00:11:22:33:44:55 REACHABLE\n", ""),
            subprocess.CompletedProcess([], 0, "93.184.216.34 STREAM ubuntu.com\n", ""),
        ]

        result = run_network_diagnostics()

        self.assertEqual(result["gateway_error"], "no-response")
        self.assertIsNone(result["gateway_latency_ms"])
        self.assertEqual(result["gateway_test_duration_ms"], 1500.0)


class DpkgAuditTests(unittest.TestCase):
    def test_empty_audit_means_no_reported_issues(self):
        self.assertEqual(parse_dpkg_audit(""), [])
        self.assertEqual(parse_dpkg_audit("\n"), [])

    def test_audit_extracts_package_names_without_heading_text(self):
        output = (
            "The following packages have been unpacked but not yet configured:\n"
            " browser:amd64      A web browser\n"
            " broken-app          An example package\n"
            " browser:amd64      A web browser\n"
        )
        self.assertEqual(parse_dpkg_audit(output), ["broken-app", "browser:amd64"])

    def test_unrecognized_nonempty_audit_output_is_unknown(self):
        self.assertIsNone(parse_dpkg_audit("dpkg: error: database unavailable\n"))

    def test_wrapped_database_lock_notice_is_not_a_package_name(self):
        output = (
            "Another process has locked the database for writing, and might currently be\n"
            "modifying it; some reported problems might be due to that.\n"
        )
        self.assertIsNone(parse_dpkg_audit(output))

    @patch("system_diagnostics.shutil.which", return_value="/usr/bin/dpkg")
    @patch("system_diagnostics._run_local")
    def test_runs_dpkg_audit_without_changing_packages(self, run, _which):
        run.return_value = subprocess.CompletedProcess([], 0, "", "")

        packages, error = read_package_health()

        self.assertEqual((packages, error), ([], None))
        self.assertEqual(run.call_args.args[0], ["/usr/bin/dpkg", "--audit"])
        self.assertEqual(run.call_args.kwargs["env"]["LC_ALL"], "C")

    @patch("system_diagnostics.shutil.which", return_value=None)
    def test_reports_missing_dpkg(self, _which):
        self.assertEqual(read_package_health(), (None, "not-installed"))

    @patch("system_diagnostics.shutil.which", return_value="/usr/bin/dpkg")
    @patch("system_diagnostics._run_local", return_value=None)
    def test_reports_unavailable_audit(self, _run, _which):
        self.assertEqual(read_package_health(), (None, "timeout-or-unavailable"))


def read_internet_check():
    from system_diagnostics import check_internet_connection
    return check_internet_connection()


if __name__ == "__main__":
    unittest.main()
