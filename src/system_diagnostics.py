"""Read-only system diagnostics used by Ubuntu Start."""
from __future__ import annotations

import os
import ipaddress
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


def _graphics_adapters(drm_path: Path) -> list[str]:
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
        adapters.append(f"{pci_id} ({driver})" if driver else pci_id)
    return adapters


def read_hardware_details(
    cpuinfo_path: str | Path = "/proc/cpuinfo",
    meminfo_path: str | Path = "/proc/meminfo",
    sys_root: str | Path = "/sys",
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
        "graphics": _graphics_adapters(sys_root / "class/drm"),
        "architecture": platform.machine(),
    }


def read_storage_status(path: str | Path = "/") -> dict[str, int]:
    """Return local filesystem capacity in bytes."""
    usage = shutil.disk_usage(path)
    return {"total": usage.total, "used": usage.used, "free": usage.free}


def read_battery_status(power_supply_path: str | Path = "/sys/class/power_supply") -> list[dict[str, str | int]]:
    """Read battery percentage and state without accessing device identifiers."""
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
            batteries.append({"capacity": capacity, "status": status or "Unknown"})
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
