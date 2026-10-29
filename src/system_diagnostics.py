"""Read-only system diagnostics used by Ubuntu Start."""
from __future__ import annotations

import os
import ipaddress
import json
import platform
from pathlib import Path
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.request


def parse_nmcli_device_status(output: str) -> list[tuple[str, str, str]]:
    """Parse `nmcli -t -f DEVICE,TYPE,STATE device status` output."""
    devices = []
    for line in output.splitlines():
        fields = line.split(":", 2)
        if len(fields) != 3:
            continue
        device, device_type, state = (field.strip() for field in fields)
        if not device or not device_type or not state:
            continue
        if device.casefold() == "device":
            continue
        if device == "lo" or device_type.casefold() == "loopback":
            continue
        devices.append((device, device_type.casefold(), state.casefold()))
    return devices


def parse_iw_link_status(output: str) -> dict[str, float | int]:
    """Extract signal and link rates without retaining SSID or access-point MAC."""
    details: dict[str, float | int] = {}
    signal = re.search(r"^\s*signal:\s*(-?\d+)\s*dBm\s*$", output, re.IGNORECASE | re.MULTILINE)
    if signal:
        details["signal_dbm"] = int(signal.group(1))
    for direction in ("rx", "tx"):
        match = re.search(
            rf"^\s*{direction} bitrate:\s*([0-9]+(?:\.[0-9]+)?)\s*MBit/s\s*$",
            output,
            re.IGNORECASE | re.MULTILINE,
        )
        if match:
            details[f"{direction}_bitrate_mbps"] = float(match.group(1))
    return details


def read_wifi_link_status(interface: str, timeout: float = 2.0) -> dict[str, float | int] | None:
    """Read active Wi-Fi link metrics only; do not scan or expose network identifiers."""
    if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,64}", interface):
        return None
    iw = shutil.which("iw")
    if not iw:
        return None
    result = _run_local([iw, "dev", interface, "link"], timeout)
    if result is None or result.returncode != 0:
        return None
    details = parse_iw_link_status(result.stdout)
    return details or None


def read_network_devices(timeout: float = 3.0) -> tuple[list[tuple[str, str, str]], str | None]:
    """Read local NetworkManager device state without probing the network."""
    if shutil.which("nmcli") is None:
        return [], "not-installed"

    env = os.environ.copy()
    env.update({"LANG": "C", "LC_ALL": "C"})
    env.pop("LANGUAGE", None)
    try:
        result = subprocess.run(
            ["nmcli", "--terse", "--fields", "DEVICE,TYPE,STATE", "device", "status"],
            capture_output=True,
            check=False,
            text=True,
            timeout=timeout,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return [], "timeout"
    except OSError:
        return [], "unavailable"

    if result.returncode != 0:
        return [], "unavailable"
    return parse_nmcli_device_status(result.stdout), None


def parse_bluetooth_controller_status(output: str) -> str:
    """Parse only controller presence and power state from bluetoothctl output."""
    has_controller = False
    powered = None
    for line in output.splitlines():
        stripped = line.strip()
        if stripped.startswith("Controller "):
            has_controller = True
        key, separator, value = stripped.partition(":")
        if separator and key.casefold() == "powered":
            state = value.strip().casefold()
            if state in {"yes", "no"}:
                powered = state == "yes"
    if not has_controller:
        return "no-controller"
    if powered is None:
        return "unknown"
    return "powered" if powered else "off"


def read_bluetooth_status(
    timeout: float = 3.0,
    controller_path: str | Path = "/sys/class/bluetooth",
) -> str:
    """Read local Bluetooth controller power state without scanning for devices."""
    if shutil.which("bluetoothctl") is None:
        return "not-installed"
    if not any(Path(controller_path).glob("hci*")):
        return "no-controller"
    result = _run_local(["bluetoothctl", "show"], timeout)
    if result is None:
        return "timeout-or-unavailable"
    if result.returncode != 0:
        return "unavailable"
    return parse_bluetooth_controller_status(result.stdout)


def parse_wpctl_volume(output: str) -> tuple[int, bool] | None:
    """Parse a volume percentage and mute flag from `wpctl get-volume`."""
    match = re.search(r"\bVolume:\s*([0-9]+(?:\.[0-9]+)?)", output, re.IGNORECASE)
    if not match:
        return None
    percent = round(float(match.group(1)) * 100)
    muted = bool(re.search(r"\[MUTED\]", output, re.IGNORECASE))
    return percent, muted


def parse_pactl_volume(output: str) -> int | None:
    """Parse the first channel percentage from `pactl get-*-volume`."""
    match = re.search(r"\b([0-9]{1,3})%", output)
    return int(match.group(1)) if match else None


def parse_pactl_mute(output: str) -> bool | None:
    match = re.search(r"\bMute:\s*(yes|no)\b", output, re.IGNORECASE)
    return match.group(1).casefold() == "yes" if match else None


def read_audio_status(timeout: float = 2.0) -> dict[str, tuple[int, bool] | None | str]:
    """Read default speaker and microphone volume/mute state without changing it."""
    wpctl = shutil.which("wpctl")
    pactl = shutil.which("pactl")
    result: dict[str, tuple[int, bool] | None | str] = {
        "output": None, "input": None, "error": None,
    }
    if wpctl:
        for key, endpoint in (("output", "@DEFAULT_AUDIO_SINK@"), ("input", "@DEFAULT_AUDIO_SOURCE@")):
            response = _run_local([wpctl, "get-volume", endpoint], timeout)
            if response and response.returncode == 0:
                result[key] = parse_wpctl_volume(response.stdout)
    if pactl:
        for key, kind, endpoint in (
            ("output", "sink", "@DEFAULT_SINK@"),
            ("input", "source", "@DEFAULT_SOURCE@"),
        ):
            if result[key] is not None:
                continue
            volume = _run_local([pactl, f"get-{kind}-volume", endpoint], timeout)
            mute = _run_local([pactl, f"get-{kind}-mute", endpoint], timeout)
            percent = parse_pactl_volume(volume.stdout) if volume and volume.returncode == 0 else None
            muted = parse_pactl_mute(mute.stdout) if mute and mute.returncode == 0 else None
            if percent is not None and muted is not None:
                result[key] = (percent, muted)
    if not wpctl and not pactl:
        result["error"] = "not-installed"

    if result["output"] is None and result["input"] is None and result["error"] is None:
        result["error"] = "unavailable"
    return result


def parse_cpu_model(cpuinfo: str) -> str | None:
    """Return a useful CPU model from Linux procfs content."""
    for line in cpuinfo.splitlines():
        key, separator, value = line.partition(":")
        if separator and key.strip().casefold() in {"model name", "hardware", "processor"}:
            candidate = value.strip()
            if candidate and candidate.casefold() not in {"unknown", "unknown processor"}:
                if key.strip().casefold() == "processor" and candidate.isdigit():
                    continue
                return candidate
    return None


def parse_memory_kib(meminfo: str) -> int | None:
    """Return MemTotal in KiB from Linux procfs content."""
    for line in meminfo.splitlines():
        key, separator, value = line.partition(":")
        if separator and key.strip() == "MemTotal":
            parts = value.split()
            if parts and parts[0].isdigit():
                return int(parts[0])
    return None


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip() or None
    except OSError:
        return None


def lookup_pci_device_name(
    vendor_id: str,
    device_id: str,
    databases: tuple[str, ...] = (
        "/usr/share/misc/pci.ids", "/usr/share/hwdata/pci.ids", "/usr/share/pci.ids",
    ),
) -> str | None:
    """Resolve a PCI vendor/device pair from an installed pci.ids database only."""
    vendor_match = re.fullmatch(r"(?:0x)?([0-9a-f]{4})", vendor_id.strip(), re.IGNORECASE)
    device_match = re.fullmatch(r"(?:0x)?([0-9a-f]{4})", device_id.strip(), re.IGNORECASE)
    if not vendor_match or not device_match:
        return None
    wanted_vendor = vendor_match.group(1).upper()
    wanted_device = device_match.group(1).upper()

    for database in databases:
        try:
            lines = Path(database).read_text(encoding="ascii", errors="replace").splitlines()
        except OSError:
            continue
        vendor_name = None
        for line in lines:
            vendor = re.match(r"^([0-9A-Fa-f]{4})\s{2,}(.+?)\s*$", line)
            if vendor:
                if vendor.group(1).upper() == wanted_vendor:
                    vendor_name = vendor.group(2).strip()
                    continue
                if vendor_name:
                    break
                continue
            if vendor_name and line.startswith("\t") and not line.startswith("\t\t"):
                device = re.match(r"^\t([0-9A-Fa-f]{4})\s{2,}(.+?)\s*$", line)
                if device and device.group(1).upper() == wanted_device:
                    return f"{vendor_name} {device.group(2).strip()}"
        if vendor_name:
            return vendor_name
    return None


def _graphics_adapters(
    drm_path: Path,
    pci_databases: tuple[str, ...] = (
        "/usr/share/misc/pci.ids", "/usr/share/hwdata/pci.ids", "/usr/share/pci.ids",
    ),
) -> list[str]:
    adapters = []
    for device_path in sorted(drm_path.glob("card[0-9]*/device")):
        vendor = _read(device_path / "vendor")
        device = _read(device_path / "device")
        if not vendor or not device:
            continue
        driver_link = device_path / "driver"
        try:
            driver = driver_link.resolve(strict=True).name
        except OSError:
            driver = None
        pci_id = f"{vendor}:{device}"
        name = lookup_pci_device_name(vendor, device, pci_databases)
        description = f"{name} [{pci_id}]" if name else pci_id
        adapters.append(f"{description} ({driver})" if driver else description)
    return adapters


def read_hardware_details(
    cpuinfo_path: str | Path = "/proc/cpuinfo",
    meminfo_path: str | Path = "/proc/meminfo",
    sys_root: str | Path = "/sys",
    pci_databases: tuple[str, ...] = (
        "/usr/share/misc/pci.ids", "/usr/share/hwdata/pci.ids", "/usr/share/pci.ids",
    ),
) -> dict[str, str | None | list[str]]:
    """Read useful hardware facts while deliberately excluding serial numbers."""
    cpuinfo = _read(Path(cpuinfo_path)) or ""
    meminfo = _read(Path(meminfo_path)) or ""
    sys_root = Path(sys_root)
    product = _read(sys_root / "class/dmi/id/product_name")
    if product and product.casefold() in {"default string", "to be filled by o.e.m.", "not specified"}:
        product = None

    memory_kib = parse_memory_kib(meminfo)
    memory = f"{round(memory_kib / 1_048_576)} GiB" if memory_kib is not None else None
    return {
        "system_model": product,
        "processor": parse_cpu_model(cpuinfo),
        "memory": memory,
        "graphics": _graphics_adapters(sys_root / "class/drm", pci_databases),
        "architecture": platform.machine(),
    }


def read_storage_status(path: str | Path = "/") -> dict[str, int]:
    """Return local filesystem capacity in bytes."""
    usage = shutil.disk_usage(path)
    return {"total": usage.total, "used": usage.used, "free": usage.free}


def read_storage_locations(
    root_path: str | Path = "/", home_path: str | Path | None = None,
) -> dict[str, dict[str, int]]:
    """Read root storage and a separate home filesystem when one is mounted."""
    home_path = Path.home() if home_path is None else Path(home_path)
    locations = {"system": read_storage_status(root_path)}
    try:
        if os.stat(home_path).st_dev != os.stat(root_path).st_dev:
            locations["home"] = read_storage_status(home_path)
    except OSError:
        # Keep the system result useful when the home mount is unavailable.
        pass
    return locations


def read_battery_status(power_supply_path: str | Path = "/sys/class/power_supply") -> list[dict[str, str | int]]:
    """Read charge and optional full-charge capacity estimate without device identifiers."""
    batteries = []
    for battery in sorted(Path(power_supply_path).glob("*") if Path(power_supply_path).exists() else []):
        if _read(battery / "type") != "Battery":
            continue
        try:
            capacity = int(_read(battery / "capacity") or "")
        except ValueError:
            capacity = -1
        status = _read(battery / "status")
        if 0 <= capacity <= 100:
            details: dict[str, str | int] = {"capacity": capacity, "status": status or "Unknown"}
            for full_name, design_name in (("energy_full", "energy_full_design"), ("charge_full", "charge_full_design")):
                try:
                    full = int(_read(battery / full_name) or "")
                    design = int(_read(battery / design_name) or "")
                except ValueError:
                    continue
                if full > 0 and design > 0:
                    details["design_capacity_percent"] = round(full / design * 100)
                    break
            batteries.append(details)
    return batteries


def check_internet_connection(timeout: float = 5.0) -> str:
    """Make a small HTTPS request to Ubuntu; call only after explicit user consent."""
    request = urllib.request.Request("https://ubuntu.com/", method="HEAD", headers={"User-Agent": "Ubuntu-Start-connectivity-check"})
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, request, response, code, message, headers, new_url):
            return None

    opener = urllib.request.build_opener(NoRedirect())
    try:
        with opener.open(request, timeout=timeout) as response:
            return f"reachable:{response.status}"
    except urllib.error.HTTPError as error:
        # An HTTP response, including an error status, proves the host was reached.
        error.close()
        return f"reachable:{error.code}"
    except (OSError, TimeoutError) as error:
        return f"unreachable:{error.__class__.__name__}"


def parse_default_route(output: str) -> tuple[str, str] | None:
    """Extract an IP default gateway and interface from `ip route` output."""
    for line in output.splitlines():
        fields = line.split()
        if len(fields) >= 5 and fields[0] == "default" and "via" in fields and "dev" in fields:
            try:
                gateway = str(ipaddress.ip_address(fields[fields.index("via") + 1]))
            except (ValueError, IndexError):
                continue
            interface = fields[fields.index("dev") + 1]
            if interface and interface.replace("_", "").replace("-", "").replace(".", "").isalnum():
                return gateway, interface
    return None


def parse_neighbor_mac(output: str) -> str | None:
    """Return a valid MAC address from `ip neigh` output."""
    fields = output.split()
    if "lladdr" not in fields:
        return None
    try:
        mac = fields[fields.index("lladdr") + 1].upper().replace("-", ":")
    except IndexError:
        return None
    parts = mac.split(":")
    return mac if len(parts) == 6 and all(len(part) == 2 and all(c in "0123456789ABCDEF" for c in part) for part in parts) else None


def lookup_oui_vendor(mac: str | None, databases: tuple[str, ...] = (
    "/usr/share/ieee-data/oui.txt", "/usr/share/hwdata/oui.txt", "/usr/share/misc/oui.txt",
)) -> str | None:
    """Match a MAC prefix against an installed IEEE OUI database; never use a web lookup."""
    if not mac:
        return None
    prefix = mac.upper().replace(":", "-")[:8]
    for database in databases:
        try:
            lines = Path(database).read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for line in lines:
            match = re.match(r"^([0-9A-Fa-f-]{8})\s+\(hex\)\s+(.+?)\s*$", line)
            if match and match.group(1).upper() == prefix:
                vendor = match.group(2).strip()
                return vendor or None
    return None


def _run_local(command: list[str], timeout: float = 3.0) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(command, capture_output=True, text=True, check=False, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None


def run_network_diagnostics(timeout: float = 3.0) -> dict[str, str | float | None]:
    """Measure configured DNS and gateway latency; call only after user starts the check."""
    result: dict[str, str | float | None] = {
        "dns_latency_ms": None, "dns_error": None,
        "gateway": None, "gateway_interface": None,
        "gateway_latency_ms": None, "gateway_mac": None, "gateway_vendor": None,
    }
    route = _run_local(["ip", "route", "show", "default"], timeout)
    default = parse_default_route(route.stdout) if route and route.returncode == 0 else None
    if not default:
        route = _run_local(["ip", "-6", "route", "show", "default"], timeout)
        default = parse_default_route(route.stdout) if route and route.returncode == 0 else None
    if default:
        gateway, interface = default
        family = "-6" if ipaddress.ip_address(gateway).version == 6 else "-4"
        result["gateway"] = gateway
        result["gateway_interface"] = interface
        start = time.monotonic()
        ping = _run_local(["ping", family, "-I", interface, "-n", "-c", "1", "-W", str(max(1, int(timeout))), gateway], timeout + 1)
        if ping and ping.returncode == 0:
            timing = re.search(r"time[=<]([0-9.]+)\s*ms", ping.stdout)
            result["gateway_latency_ms"] = float(timing.group(1)) if timing else round((time.monotonic() - start) * 1000, 1)
        neighbor = _run_local(["ip", family, "neigh", "show", "to", gateway, "dev", interface], timeout)
        mac = parse_neighbor_mac(neighbor.stdout) if neighbor and neighbor.returncode == 0 else None
        result["gateway_mac"] = mac
        result["gateway_vendor"] = lookup_oui_vendor(mac)
    else:
        result["gateway_error"] = "no-default-route"

    start = time.monotonic()
    dns = _run_local(["getent", "ahosts", "ubuntu.com"], timeout)
    if dns and dns.returncode == 0 and dns.stdout.strip():
        result["dns_latency_ms"] = round((time.monotonic() - start) * 1000, 1)
    else:
        result["dns_error"] = "lookup-failed"
    return result


def build_support_report(
    system_details: list[tuple[str, str]],
    diagnostics: dict[str, str | float | None] | None = None,
) -> str:
    """Create a local, reviewable support report from explicitly supplied facts."""
    report: dict[str, object] = {
        "report_version": 1,
        "system": {label: value for label, value in system_details},
    }
    if diagnostics is not None:
        # Exclude gateway addresses, interface names and MAC addresses by design.
        report["network_checks"] = {
            "dns_latency_ms": diagnostics.get("dns_latency_ms"),
            "gateway_latency_ms": diagnostics.get("gateway_latency_ms"),
            "gateway_reachable": diagnostics.get("gateway_latency_ms") is not None,
        }
    return json.dumps(report, ensure_ascii=False, indent=2) + "\n"
