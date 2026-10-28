import subprocess
import tempfile
import unittest
from io import BytesIO
import urllib.error
from pathlib import Path
from unittest.mock import patch

from system_diagnostics import (
    parse_cpu_model,
    parse_bluetooth_controller_status,
    parse_default_route,
    parse_memory_kib,
    parse_neighbor_mac,
    parse_nmcli_device_status,
    lookup_oui_vendor,
    read_battery_status,
    read_bluetooth_status,
    read_hardware_details,
    read_network_devices,
    read_storage_status,
    run_network_diagnostics,
)


class ParseNetworkStatusTests(unittest.TestCase):
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
        self.assertEqual(read_bluetooth_status(), "not-installed")

    @patch("system_diagnostics._run_local")
    @patch("system_diagnostics.shutil.which", return_value="/usr/bin/bluetoothctl")
    def test_reports_absent_controller_without_waiting_on_bluetooth_service(self, _which, run):
        with tempfile.TemporaryDirectory() as temporary:
            self.assertEqual(read_bluetooth_status(controller_path=temporary), "no-controller")
        run.assert_not_called()

    @patch("system_diagnostics._run_local")
    @patch("system_diagnostics.shutil.which", return_value="/usr/bin/bluetoothctl")
    def test_reads_controller_state_without_scanning(self, _which, run):
        run.return_value = subprocess.CompletedProcess(
            ["bluetoothctl", "show"], 0,
            "Controller AA:BB:CC:DD:EE:FF (public)\n\tPowered: yes\n", "",
        )
        with tempfile.TemporaryDirectory() as temporary:
            (Path(temporary) / "hci0").mkdir()
            self.assertEqual(read_bluetooth_status(controller_path=temporary), "powered")
        self.assertEqual(run.call_args.args[0], ["bluetoothctl", "show"])


class ParseHardwareTests(unittest.TestCase):
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

            result = read_hardware_details(cpuinfo, meminfo, sys_root)

        self.assertEqual(result["system_model"], "Test Laptop")
        self.assertEqual(result["processor"], "Example CPU")
        self.assertEqual(result["memory"], "8 GiB")
        self.assertEqual(result["graphics"], ["0x1234:0xabcd (example_gpu)"])
        self.assertNotIn("DO-NOT-READ", repr(result))


class LocalDiagnosticsTests(unittest.TestCase):
    def test_reads_storage_capacity(self):
        result = read_storage_status("/")
        self.assertGreater(result["total"], 0)
        self.assertGreaterEqual(result["free"], 0)
        self.assertGreaterEqual(result["used"], 0)

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

    @patch("system_diagnostics.lookup_oui_vendor", return_value="Example Router Co.")
    @patch("system_diagnostics._run_local")
    @patch("system_diagnostics.time.monotonic", side_effect=[1.0, 2.0, 2.03])
    def test_network_diagnostics_use_default_gateway_and_report_latency(self, _clock, run, _vendor):
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

    @patch("system_diagnostics.lookup_oui_vendor", return_value=None)
    @patch("system_diagnostics._run_local")
    @patch("system_diagnostics.time.monotonic", side_effect=[1.0, 2.0, 2.03])
    def test_uses_ipv6_gateway_when_ipv4_default_is_missing(self, _clock, run, _vendor):
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
        self.assertEqual(run.call_args_list[2].args[0][:2], ["ping", "-6"])
        self.assertEqual(run.call_args_list[2].args[0][2:4], ["-I", "enp1s0"])
        self.assertEqual(run.call_args_list[3].args[0][:3], ["ip", "-6", "neigh"])
        self.assertEqual(run.call_args_list[4].args[0], ["getent", "ahosts", "ubuntu.com"])


def read_internet_check():
    from system_diagnostics import check_internet_connection
    return check_internet_connection()


if __name__ == "__main__":
    unittest.main()
