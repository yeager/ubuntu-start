"""System diagnostics and private local benchmark state used by Ubuntu Start."""
from __future__ import annotations

import os
import ipaddress
import json
import math
import platform
from importlib import metadata
from pathlib import Path
import re
import shutil
import statistics
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone


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


def parse_interface_ip_status(output: str) -> dict[str, bool] | None:
    """Report whether an interface has usable IPv4/IPv6 or only link-local addresses."""
    try:
        interfaces = json.loads(output)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(interfaces, list):
        return None
    result = {"ipv4": False, "ipv6": False, "link_local": False}
    for interface in interfaces:
        if not isinstance(interface, dict):
            continue
        address_info = interface.get("addr_info", [])
        if not isinstance(address_info, list):
            continue
        for info in address_info:
            if not isinstance(info, dict):
                continue
            local = info.get("local")
            if not isinstance(local, str):
                continue
            try:
                address = ipaddress.ip_address(local)
            except ValueError:
                continue
            if address.is_loopback or address.is_unspecified or address.is_multicast:
                continue
            if address.is_link_local:
                result["link_local"] = True
            elif address.version == 4:
                result["ipv4"] = True
            else:
                result["ipv6"] = True
    return result


def read_interface_ip_status(interface: str, timeout: float = 2.0) -> dict[str, bool] | None:
    """Read only IP address-family presence from a local interface; return no address values."""
    if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,64}", interface):
        return None
    ip = shutil.which("ip")
    if not ip:
        return None
    result = _run_local([ip, "-j", "address", "show", "dev", interface], timeout)
    if result is None or result.returncode != 0:
        return None
    return parse_interface_ip_status(result.stdout)


def read_video_devices(sysfs_directory: str | Path = "/sys/class/video4linux") -> list[str]:
    """List locally exposed video4linux device names without opening device nodes."""
    directory = Path(sysfs_directory)
    devices = []
    try:
        entries = sorted(directory.iterdir(), key=lambda path: path.name)
    except OSError:
        return devices
    for entry in entries:
        if not re.fullmatch(r"video\d+", entry.name):
            continue
        try:
            raw_name = (entry / "name").read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        name = " ".join(
            "".join(character if character.isprintable() else " " for character in raw_name).split()
        )[:120]
        if name and name not in devices:
            devices.append(name)
    return devices


def read_display_connectors(drm_directory: str | Path = "/sys/class/drm") -> list[dict[str, str | None]]:
    """Read DRM connector state only; do not read monitor EDID or identifiers."""
    directory = Path(drm_directory)
    try:
        entries = sorted(directory.iterdir(), key=lambda path: path.name)
    except OSError:
        return []

    connectors = []
    for entry in entries:
        if not re.fullmatch(r"card\d+-[A-Za-z0-9_.-]{1,64}", entry.name) or not entry.is_dir():
            continue
        status = _read(entry / "status")
        if status not in {"connected", "disconnected", "unknown"}:
            continue
        enabled = _read(entry / "enabled")
        if enabled not in {"enabled", "disabled", "unknown"}:
            enabled = None
        connectors.append({"name": entry.name, "status": status, "enabled": enabled})
    return connectors


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


def read_rfkill_status(
    rfkill_path: str | Path = "/sys/class/rfkill",
) -> list[dict[str, str | bool]] | None:
    """Read allowlisted wireless radio block flags from local sysfs."""
    root = Path(rfkill_path)
    if not root.is_dir():
        return None
    radios = []
    try:
        entries = sorted(root.glob("rfkill*"), key=lambda path: path.name)
    except OSError:
        return None
    allowed_types = {"wlan", "bluetooth", "wwan", "gps", "nfc", "uwb", "wimax", "fm"}
    for entry in entries:
        if not re.fullmatch(r"rfkill\d+", entry.name):
            continue
        radio_type = _read(entry / "type")
        soft = _read(entry / "soft")
        hard = _read(entry / "hard")
        if radio_type not in allowed_types or soft not in {"0", "1"} or hard not in {"0", "1"}:
            continue
        radios.append({
            "type": radio_type,
            "soft_blocked": soft == "1",
            "hard_blocked": hard == "1",
        })
    return radios


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
    """Read adapter, service and controller state without scanning for devices."""
    if not any(Path(controller_path).glob("hci*")):
        return "no-controller"
    systemctl = shutil.which("systemctl")
    if systemctl:
        service = _run_local(
            [systemctl, "is-active", "bluetooth.service"], timeout,
            env={**os.environ, "LC_ALL": "C"},
        )
        if service and service.stdout.strip() in {"inactive", "failed"}:
            return f"service-{service.stdout.strip()}"
    bluetoothctl = shutil.which("bluetoothctl")
    if bluetoothctl is None:
        return "not-installed"
    result = _run_local([bluetoothctl, "show"], timeout)
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
    volume = float(match.group(1))
    percent = volume * 100
    if not math.isfinite(percent):
        return None
    muted = bool(re.search(r"\[MUTED\]", output, re.IGNORECASE))
    return round(percent), muted


def parse_wpctl_endpoint_name(output: str) -> str | None:
    """Read only the human-facing PipeWire endpoint description."""
    match = re.search(
        r'^\s*(?:\*\s*)?node\.description\s*=\s*"((?:\\.|[^"\\])*)"\s*$',
        output,
        re.MULTILINE,
    )
    if not match:
        return None
    value = re.sub(r"\\([\\\"])", r"\1", match.group(1))
    cleaned = " ".join(
        "".join(character if character.isprintable() else " " for character in value).split()
    )[:120]
    return cleaned or None


def parse_pactl_volume(output: str) -> int | None:
    """Parse the first channel percentage from `pactl get-*-volume`."""
    match = re.search(r"\b([0-9]{1,3})%", output)
    return int(match.group(1)) if match else None


def parse_pactl_mute(output: str) -> bool | None:
    match = re.search(r"\bMute:\s*(yes|no)\b", output, re.IGNORECASE)
    return match.group(1).casefold() == "yes" if match else None


def read_audio_status(timeout: float = 2.0) -> dict[str, tuple[int, bool] | None | str]:
    """Read default speaker and microphone names, volume and mute state."""
    wpctl = shutil.which("wpctl")
    pactl = shutil.which("pactl")
    result: dict[str, tuple[int, bool] | None | str] = {
        "output": None, "input": None,
        "output_name": None, "input_name": None, "error": None,
    }
    if wpctl:
        for key, endpoint in (("output", "@DEFAULT_AUDIO_SINK@"), ("input", "@DEFAULT_AUDIO_SOURCE@")):
            response = _run_local([wpctl, "get-volume", endpoint], timeout)
            if response and response.returncode == 0:
                result[key] = parse_wpctl_volume(response.stdout)
                details = _run_local([wpctl, "inspect", endpoint], timeout)
                if details and details.returncode == 0:
                    result[f"{key}_name"] = parse_wpctl_endpoint_name(details.stdout)
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


def parse_printer_status(output: str) -> list[tuple[str, str]]:
    """Keep only local CUPS queue names and a small set of state labels."""
    printers = []
    for line in output.splitlines():
        match = re.match(
            r"^printer\s+(.+?)\s+(?:is\s+)?(idle|printing|disabled|busy|processing|stopped)\b",
            line.strip(),
            re.IGNORECASE,
        )
        if not match:
            continue
        name = " ".join(
            "".join(character if character.isprintable() else " " for character in match.group(1)).split()
        )[:100]
        if name:
            printers.append((name, match.group(2).casefold()))
    return printers


def parse_printer_job_counts(output: str, printer_names: list[str]) -> dict[str, int]:
    """Count unfinished jobs per known queue without retaining user or job names."""
    counts = {name: 0 for name in printer_names}
    for line in output.splitlines():
        fields = line.split(None, 1)
        if not fields:
            continue
        job_id = fields[0]
        for name in sorted(counts, key=len, reverse=True):
            suffix = job_id[len(name) + 1:] if job_id.startswith(f"{name}-") else ""
            if suffix.isdecimal():
                counts[name] += 1
                break
    return counts


def read_backup_tool_status() -> dict[str, str | bool]:
    """Check locally whether Ubuntu's Déjà Dup backup app is installed and launchable."""
    desktop = shutil.which("deja-dup")
    package = shutil.which("dpkg-query")
    installed = False
    if package:
        result = _run_local([package, "-W", "-f=${Status}", "deja-dup"], 2.0)
        installed = bool(
            result and result.returncode == 0
            and result.stdout.strip() == "install ok installed"
        )
    return {"installed": installed, "launcher": desktop or ""}


def read_printer_status(timeout: float = 3.0) -> tuple[list[tuple[str, str, int | None]], str | None]:
    """Read local CUPS queue state and unfinished job counts; never submit or cancel jobs."""
    lpstat = shutil.which("lpstat")
    if not lpstat:
        return [], "not-installed"
    env = os.environ.copy()
    env.update({"LANG": "C", "LC_ALL": "C"})
    env.pop("LANGUAGE", None)
    try:
        result = subprocess.run(
            [lpstat, "-h", "localhost", "-p"],
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
    printers = parse_printer_status(result.stdout)
    if not printers:
        return [], "no-printers"

    jobs = _run_local(
        [lpstat, "-h", "localhost", "-W", "not-completed", "-o"], timeout, env,
    )
    counts = (
        parse_printer_job_counts(jobs.stdout, [name for name, _state in printers])
        if jobs and jobs.returncode == 0 else None
    )
    return [
        (name, state, counts.get(name) if counts is not None else None)
        for name, state in printers
    ], None


ACCESSIBILITY_SETTINGS = {
    ("org.gnome.desktop.a11y.applications", "screen-reader-enabled"): ("screen_reader", "boolean"),
    ("org.gnome.desktop.a11y.applications", "screen-magnifier-enabled"): ("screen_magnifier", "boolean"),
    ("org.gnome.desktop.a11y.applications", "screen-keyboard-enabled"): ("screen_keyboard", "boolean"),
    ("org.gnome.desktop.a11y.interface", "high-contrast"): ("high_contrast", "boolean"),
    ("org.gnome.desktop.a11y.keyboard", "stickykeys-enable"): ("sticky_keys", "boolean"),
    ("org.gnome.desktop.a11y.keyboard", "slowkeys-enable"): ("slow_keys", "boolean"),
    ("org.gnome.desktop.a11y.keyboard", "bouncekeys-enable"): ("bounce_keys", "boolean"),
    ("org.gnome.desktop.a11y.keyboard", "mousekeys-enable"): ("mouse_keys", "boolean"),
    ("org.gnome.desktop.interface", "text-scaling-factor"): ("text_scale", "float"),
    ("org.gnome.desktop.interface", "cursor-size"): ("cursor_size", "integer"),
    ("org.gnome.desktop.wm.preferences", "visual-bell"): ("visual_bell", "boolean"),
}


def parse_accessibility_settings(outputs: dict[str, str]) -> dict[str, bool | float | int | None]:
    """Parse only the allowlisted, read-only GNOME accessibility preferences."""
    settings: dict[str, bool | float | int | None] = {
        value[0]: None for value in ACCESSIBILITY_SETTINGS.values()
    }
    for schema_output in outputs.values():
        for line in schema_output.splitlines():
            fields = line.split(None, 2)
            if len(fields) != 3:
                continue
            schema, key, raw_value = fields
            spec = ACCESSIBILITY_SETTINGS.get((schema, key))
            if not spec:
                continue
            name, kind = spec
            value = raw_value.strip()
            if kind == "boolean" and value in {"true", "false"}:
                settings[name] = value == "true"
            elif kind == "integer":
                try:
                    parsed = int(value)
                except ValueError:
                    continue
                if 1 <= parsed <= 256:
                    settings[name] = parsed
            elif kind == "float":
                try:
                    parsed = float(value)
                except ValueError:
                    continue
                if math.isfinite(parsed) and 0 < parsed <= 10:
                    settings[name] = parsed
    return settings


def read_accessibility_settings(timeout: float = 1.0) -> tuple[dict[str, bool | float | int | None], str | None]:
    """Read selected GNOME accessibility settings without changing them."""
    empty = parse_accessibility_settings({})
    gsettings = shutil.which("gsettings")
    if not gsettings:
        return empty, "not-installed"
    env = os.environ.copy()
    env.update({"LANG": "C", "LC_ALL": "C"})
    env.pop("LANGUAGE", None)
    outputs = {}
    for schema, key in ACCESSIBILITY_SETTINGS:
        try:
            result = subprocess.run(
                [gsettings, "get", schema, key],
                capture_output=True,
                check=False,
                text=True,
                timeout=timeout,
                env=env,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        if result.returncode == 0:
            outputs[schema] = outputs.get(schema, "") + f"{schema} {key} {result.stdout.strip()}\n"
    settings = parse_accessibility_settings(outputs)
    return settings, None if any(value is not None for value in settings.values()) else "unavailable"


def parse_time_status(output: str) -> dict[str, str | bool | None]:
    """Parse only timezone and automatic clock synchronization properties."""
    status: dict[str, str | bool | None] = {
        "timezone": None, "can_ntp": None, "ntp": None, "synchronized": None,
    }
    properties = {
        "Timezone": "timezone",
        "CanNTP": "can_ntp",
        "NTP": "ntp",
        "NTPSynchronized": "synchronized",
    }
    for line in output.splitlines():
        key, separator, raw_value = line.partition("=")
        if not separator or key not in properties:
            continue
        value = raw_value.strip()
        if key == "Timezone":
            if re.fullmatch(r"[A-Za-z0-9_+./-]{1,128}", value):
                status[properties[key]] = value
        elif value in {"yes", "no"}:
            status[properties[key]] = value == "yes"
    return status


def read_time_status(timeout: float = 3.0) -> tuple[dict[str, str | bool | None], str | None]:
    """Read local timezone and clock-sync state without triggering synchronization."""
    empty = parse_time_status("")
    timedatectl = shutil.which("timedatectl")
    if not timedatectl:
        return empty, "not-installed"
    env = os.environ.copy()
    env.update({"LANG": "C", "LC_ALL": "C"})
    env.pop("LANGUAGE", None)
    try:
        result = subprocess.run(
            [timedatectl, "show", "--property=Timezone", "--property=CanNTP", "--property=NTP", "--property=NTPSynchronized"],
            capture_output=True,
            check=False,
            text=True,
            timeout=timeout,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return empty, "timeout"
    except OSError:
        return empty, "unavailable"
    if result.returncode != 0:
        return empty, "unavailable"
    status = parse_time_status(result.stdout)
    return status, None if any(value is not None for value in status.values()) else "unavailable"


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


def _clean_display_label(value: str, limit: int = 120) -> str:
    """Collapse untrusted local labels and remove control characters."""
    return " ".join(
        "".join(character if character.isprintable() else " " for character in value).split()
    )[:limit]


def read_memory_status(meminfo_path: str | Path = "/proc/meminfo") -> dict[str, int] | None:
    """Read total and available RAM plus swap use from local Linux procfs."""
    meminfo = _read(Path(meminfo_path))
    if not meminfo:
        return None
    values: dict[str, int] = {}
    for line in meminfo.splitlines():
        key, separator, value = line.partition(":")
        if not separator:
            continue
        parts = value.split()
        if key in {"MemTotal", "MemAvailable", "SwapTotal", "SwapFree"} and parts and parts[0].isdigit():
            values[key] = int(parts[0]) * 1024
    total = values.get("MemTotal", 0)
    available = values.get("MemAvailable", -1)
    swap_total = values.get("SwapTotal", 0)
    swap_free = values.get("SwapFree", 0)
    if total <= 0 or not 0 <= available <= total or not 0 <= swap_free <= swap_total:
        return None
    return {
        "total": total,
        "available": available,
        "used": total - available,
        "swap_total": swap_total,
        "swap_used": swap_total - swap_free,
    }


def parse_pressure_status(output: str) -> dict[str, float] | None:
    """Read PSI avg10 stall percentages for `some` and `full` categories."""
    if not isinstance(output, str):
        return None
    result: dict[str, float] = {}
    for line in output.splitlines():
        fields = line.split()
        if not fields or fields[0] not in {"some", "full"}:
            continue
        avg10 = next((field.partition("=")[2] for field in fields[1:] if field.startswith("avg10=")), None)
        if avg10 is None:
            continue
        try:
            percentage = float(avg10)
        except ValueError:
            continue
        if math.isfinite(percentage) and 0 <= percentage <= 100:
            result[fields[0]] = percentage
    return result or None


def pressure_threshold_exceeded(
    pressure: dict[str, dict[str, float]] | None,
    resource: str,
    metric: str,
    threshold: float,
) -> bool | None:
    """Compare an available pressure reading with a threshold; keep missing data unknown."""
    value = pressure.get(resource, {}).get(metric) if pressure else None
    if not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    return value >= threshold


def read_resource_pressure(pressure_path: str | Path = "/proc/pressure") -> dict[str, dict[str, float]] | None:
    """Read local Linux pressure-stall averages without recording process details."""
    root = Path(pressure_path)
    result = {}
    for resource in ("cpu", "memory", "io"):
        output = _read(root / resource)
        parsed = parse_pressure_status(output) if output else None
        if parsed:
            result[resource] = parsed
    return result or None


def parse_failed_services(output: str) -> list[tuple[str, str]]:
    """Parse only failed systemd service unit names and descriptions."""
    services = []
    for line in output.splitlines():
        fields = line.split(None, 4)
        if len(fields) < 4 or not re.fullmatch(r"(?:[A-Za-z0-9_.@:-]|\\x[0-9A-Fa-f]{2}){1,200}\.service", fields[0]):
            continue
        if fields[2] != "failed" or fields[3] != "failed":
            continue
        description = ""
        if len(fields) == 5:
            description = " ".join(
                "".join(character if character.isprintable() else " " for character in fields[4]).split()
            )[:160]
        services.append((fields[0], description))
    return services


def read_failed_services(timeout: float = 3.0) -> tuple[list[tuple[str, str]], str | None]:
    """Read failed service units from the local system manager; make no changes."""
    systemctl = shutil.which("systemctl")
    if not systemctl:
        return [], "not-installed"
    result = _run_local(
        [systemctl, "--failed", "--type=service", "--no-legend", "--plain", "--no-pager"],
        timeout,
        env={**os.environ, "LC_ALL": "C"},
    )
    if result is None:
        return [], "timeout"
    if result.returncode != 0:
        return [], "unavailable"
    return parse_failed_services(result.stdout), None


def read_boot_timing(timeout: float = 3.0) -> tuple[str | None, str | None]:
    """Read systemd's local boot timing summary without changing system state."""
    systemd_analyze = shutil.which("systemd-analyze")
    if not systemd_analyze:
        return None, "not-installed"
    result = _run_local(
        [systemd_analyze, "time"],
        timeout,
        env={**os.environ, "LANG": "C", "LC_ALL": "C"},
    )
    if result is None or result.returncode != 0:
        return None, "unavailable"
    lines = []
    for line in result.stdout.splitlines()[:2]:
        cleaned = " ".join(
            "".join(character if character.isprintable() else " " for character in line).split()
        )
        if cleaned:
            lines.append(cleaned[:240])
    if not lines:
        return None, "unavailable"
    return "\n".join(lines), None


def read_boot_critical_chain(timeout: float = 5.0) -> tuple[str | None, str | None]:
    """Read systemd's dependency chain to graphical.target without changing state."""
    systemd_analyze = shutil.which("systemd-analyze")
    if not systemd_analyze:
        return None, "not-installed"
    result = _run_local(
        [systemd_analyze, "critical-chain", "graphical.target"],
        timeout,
        env={**os.environ, "LANG": "C", "LC_ALL": "C"},
    )
    if result is None or result.returncode != 0:
        return None, "unavailable"
    lines = []
    for line in result.stdout.splitlines()[:32]:
        cleaned = "".join(
            character if character.isprintable() else " " for character in line
        ).rstrip()
        if cleaned:
            lines.append(cleaned[:200])
    if not lines:
        return None, "unavailable"
    return "\n".join(lines), None


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
                    vendor_name = _clean_display_label(vendor.group(2))
                    continue
                if vendor_name:
                    break
                continue
            if vendor_name and line.startswith("\t") and not line.startswith("\t\t"):
                device = re.match(r"^\t([0-9A-Fa-f]{4})\s{2,}(.+?)\s*$", line)
                if device and device.group(1).upper() == wanted_device:
                    device_name = _clean_display_label(device.group(2))
                    return _clean_display_label(f"{vendor_name} {device_name}")
        if vendor_name:
            return vendor_name
    return None


def read_pci_devices(
    devices_path: str | Path = "/sys/bus/pci/devices",
    pci_databases: tuple[str, ...] = (
        "/usr/share/misc/pci.ids", "/usr/share/hwdata/pci.ids", "/usr/share/pci.ids",
    ),
) -> list[dict[str, str | None]]:
    """Read PCI IDs and bound kernel drivers from sysfs without exposing device paths."""
    root = Path(devices_path)
    try:
        entries = sorted(root.iterdir(), key=lambda path: path.name)
    except OSError:
        return []

    devices = []
    for path in entries:
        vendor = _read(path / "vendor")
        device = _read(path / "device")
        class_code = _read(path / "class")
        if not vendor or not device or not class_code:
            continue
        if not re.fullmatch(r"0x[0-9a-fA-F]{4}", vendor) or not re.fullmatch(r"0x[0-9a-fA-F]{4}", device):
            continue
        try:
            # Class 06 contains host, ISA, PCI and bridge devices, which add little
            # value to an end-user troubleshooting list.
            if (int(class_code, 16) >> 16) & 0xFF == 0x06:
                continue
        except ValueError:
            continue
        try:
            driver = (path / "driver").resolve(strict=True).name
        except OSError:
            driver = None
        pci_id = f"{vendor[2:].lower()}:{device[2:].lower()}"
        name = lookup_pci_device_name(vendor, device, pci_databases)
        devices.append({
            "id": pci_id,
            "name": name,
            "driver": driver,
        })
    return devices


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


def lookup_usb_device_name(
    vendor_id: str,
    product_id: str,
    databases: tuple[str, ...] = (
        "/usr/share/hwdata/usb.ids", "/usr/share/misc/usb.ids", "/var/lib/usbutils/usb.ids",
    ),
) -> tuple[str | None, str | None] | None:
    """Match USB vendor and product IDs against an installed local usb.ids file."""
    if not re.fullmatch(r"[0-9a-fA-F]{4}", vendor_id) or not re.fullmatch(r"[0-9a-fA-F]{4}", product_id):
        return None
    wanted_vendor = vendor_id.upper()
    wanted_product = product_id.upper()
    for database in databases:
        try:
            lines = Path(database).read_text(encoding="ascii", errors="replace").splitlines()
        except OSError:
            continue
        vendor_name = None
        for line in lines:
            vendor_match = re.match(r"^([0-9A-Fa-f]{4})\s{2,}(.+?)\s*$", line)
            if vendor_match:
                if vendor_name:
                    break
                if vendor_match.group(1).upper() == wanted_vendor:
                    vendor_name = _clean_display_label(vendor_match.group(2))
                continue
            if vendor_name and line.startswith("\t") and not line.startswith("\t\t"):
                product_match = re.match(r"^\t([0-9A-Fa-f]{4})\s{2,}(.+?)\s*$", line)
                if product_match and product_match.group(1).upper() == wanted_product:
                    return vendor_name, _clean_display_label(product_match.group(2))
        if vendor_name:
            return vendor_name, None
    return None


def read_network_adapter_details(
    interface: str,
    sys_root: str | Path = "/sys",
    pci_databases: tuple[str, ...] = (
        "/usr/share/misc/pci.ids", "/usr/share/hwdata/pci.ids", "/usr/share/pci.ids",
    ),
    usb_databases: tuple[str, ...] = (
        "/usr/share/hwdata/usb.ids", "/usr/share/misc/usb.ids", "/var/lib/usbutils/usb.ids",
    ),
) -> dict[str, str | None] | None:
    """Read a network interface's local bus ID, cached device name and driver."""
    if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,64}", interface):
        return None
    root = Path(sys_root)
    try:
        device_path = (root / "class/net" / interface / "device").resolve(strict=True)
    except OSError:
        return None

    candidates = (device_path, *device_path.parents)
    driver = None
    for candidate in candidates:
        try:
            driver = (candidate / "driver").resolve(strict=True).name
        except OSError:
            continue
        if driver:
            break

    for candidate in candidates:
        vendor = _read(candidate / "vendor")
        product = _read(candidate / "device")
        if vendor and product and re.fullmatch(r"0x[0-9a-fA-F]{4}", vendor) and re.fullmatch(r"0x[0-9a-fA-F]{4}", product):
            return {
                "bus": "PCI",
                "id": f"{vendor[2:].lower()}:{product[2:].lower()}",
                "name": lookup_pci_device_name(vendor, product, pci_databases),
                "driver": driver,
            }

    for candidate in candidates:
        vendor = _read(candidate / "idVendor")
        product = _read(candidate / "idProduct")
        if vendor and product and re.fullmatch(r"[0-9a-fA-F]{4}", vendor) and re.fullmatch(r"[0-9a-fA-F]{4}", product):
            resolved_name = lookup_usb_device_name(vendor, product, usb_databases)
            name = " ".join(resolved_name) if resolved_name else None
            return {
                "bus": "USB",
                "id": f"{vendor.lower()}:{product.lower()}",
                "name": name,
                "driver": driver,
            }
    return {"bus": None, "id": None, "name": None, "driver": driver}


def read_usb_devices(
    devices_path: str | Path = "/sys/bus/usb/devices",
    usb_databases: tuple[str, ...] = (
        "/usr/share/hwdata/usb.ids", "/usr/share/misc/usb.ids", "/var/lib/usbutils/usb.ids",
    ),
) -> list[dict[str, str | list[str] | None]]:
    """Read connected USB descriptors and bound interface drivers, never serials."""
    devices_root = Path(devices_path)
    if not devices_root.is_dir():
        return []

    devices = []
    try:
        entries = sorted(devices_root.iterdir(), key=lambda path: path.name)
    except OSError:
        return []

    drivers_by_device: dict[str, set[str]] = {}
    for interface in entries:
        device_name, separator, _interface_id = interface.name.partition(":")
        if not separator:
            continue
        try:
            driver = (interface / "driver").resolve(strict=True).name
        except OSError:
            continue
        drivers_by_device.setdefault(device_name, set()).add(driver)

    for device_path in entries:
        if ":" in device_path.name:
            continue  # USB interface entries are not devices.
        vendor_id = _read(device_path / "idVendor")
        product_id = _read(device_path / "idProduct")
        if not vendor_id or not product_id:
            continue
        if not re.fullmatch(r"[0-9a-fA-F]{4}", vendor_id) or not re.fullmatch(r"[0-9a-fA-F]{4}", product_id):
            continue
        if vendor_id.casefold() == "1d6b" and _read(device_path / "bDeviceClass") == "09":
            continue  # The Linux host-controller root hub is not a peripheral.

        descriptors = []
        for field in ("manufacturer", "product"):
            value = _read(device_path / field)
            if value:
                cleaned = " ".join(
                    "".join(character if character.isprintable() else " " for character in value).split()
                )[:120]
                if cleaned and cleaned not in descriptors:
                    descriptors.append(cleaned)

        if len(descriptors) == 2 and descriptors[1].casefold().startswith(
            f"{descriptors[0].casefold()} "
        ):
            descriptors.pop(0)

        database_name = lookup_usb_device_name(vendor_id, product_id, usb_databases)
        database_vendor, database_product = database_name or (None, None)
        display_name = " ".join(descriptors) or None
        if database_vendor and display_name:
            sysfs_vendor = descriptors[0] if descriptors else ""
            vendor_matches = (
                database_vendor.casefold() in display_name.casefold()
                or bool(sysfs_vendor) and (
                    sysfs_vendor.casefold() in database_vendor.casefold()
                    or database_vendor.casefold() in sysfs_vendor.casefold()
                )
            )
            if not vendor_matches:
                display_name = f"{database_vendor} · {display_name}"
        elif database_vendor:
            display_name = " ".join(part for part in (database_vendor, database_product) if part)
        elif database_product:
            display_name = database_product

        devices.append({
            "id": f"{vendor_id.lower()}:{product_id.lower()}",
            "name": display_name,
            "drivers": sorted(drivers_by_device.get(device_path.name, set())),
        })
    return devices


def read_hardware_details(
    cpuinfo_path: str | Path = "/proc/cpuinfo",
    meminfo_path: str | Path = "/proc/meminfo",
    sys_root: str | Path = "/sys",
    pci_databases: tuple[str, ...] = (
        "/usr/share/misc/pci.ids", "/usr/share/hwdata/pci.ids", "/usr/share/pci.ids",
    ),
) -> dict[str, str | None | list[str] | list[dict[str, str | None]]]:
    """Read useful hardware facts while deliberately excluding serial numbers."""
    cpuinfo = _read(Path(cpuinfo_path)) or ""
    meminfo = _read(Path(meminfo_path)) or ""
    sys_root = Path(sys_root)
    product = _read(sys_root / "class/dmi/id/product_name")
    if product and product.casefold() in {"default string", "to be filled by o.e.m.", "not specified"}:
        product = None

    memory_kib = parse_memory_kib(meminfo)
    memory = f"{round(memory_kib / 1_048_576)} GiB" if memory_kib is not None else None
    try:
        operating_system = platform.freedesktop_os_release().get("PRETTY_NAME")
    except (AttributeError, OSError):
        operating_system = None
    return {
        "operating_system": operating_system,
        "kernel": platform.release(),
        "system_model": product,
        "processor": parse_cpu_model(cpuinfo),
        "memory": memory,
        "graphics": _graphics_adapters(sys_root / "class/drm", pci_databases),
        "pci_devices": read_pci_devices(sys_root / "bus/pci/devices", pci_databases),
        "usb_devices": read_usb_devices(sys_root / "bus/usb/devices"),
        "architecture": platform.machine(),
    }


def normalize_session_type(session_type: str | None) -> str | None:
    """Return a stable display-session label for the known XDG session types."""
    if not isinstance(session_type, str):
        return None
    return {
        "wayland": "Wayland",
        "x11": "X11",
        "tty": "TTY",
    }.get(session_type.strip().casefold())


def read_remote_session(timeout: float = 1.5) -> bool | None:
    """Report whether the current user's active graphical session is remote.

    Only logind's local Remote flag is returned. Host names, addresses and
    session identifiers are never included in the result.
    """
    loginctl = shutil.which("loginctl")
    if not loginctl:
        return None

    env = os.environ.copy()
    env.update({"LANG": "C", "LC_ALL": "C"})
    env.pop("LANGUAGE", None)
    session_id = os.environ.get("XDG_SESSION_ID", "").strip()
    if not re.fullmatch(r"[0-9]+", session_id):
        user_session = _run_local(
            [loginctl, "show-user", str(os.getuid()), "--property=Display", "--value"],
            timeout,
            env=env,
        )
        if not user_session or user_session.returncode != 0:
            return None
        session_id = user_session.stdout.strip()
        if not re.fullmatch(r"[0-9]+", session_id):
            return None

    result = _run_local(
        [loginctl, "show-session", session_id, "--property=Remote", "--value"],
        timeout,
        env=env,
    )
    if not result or result.returncode != 0:
        return None
    return {"yes": True, "true": True, "no": False, "false": False}.get(
        result.stdout.strip().casefold()
    )


def normalize_desktop_name(current_desktop: str | None, session_desktop: str | None) -> str | None:
    """Return the reported desktop names without guessing when XDG values are absent."""
    for value in (current_desktop, session_desktop):
        if not isinstance(value, str) or not value.strip():
            continue
        names = [name.strip() for name in value.replace(":", ",").split(",") if name.strip()]
        if names:
            return ", ".join(names)
    return None


def read_storage_status(path: str | Path = "/") -> dict[str, int | bool | None]:
    """Return local filesystem capacity and whether it is mounted read-only."""
    usage = shutil.disk_usage(path)
    try:
        read_only = bool(os.statvfs(path).f_flag & os.ST_RDONLY)
    except OSError:
        read_only = None
    return {"total": usage.total, "used": usage.used, "free": usage.free, "read_only": read_only}


def read_storage_locations(
    root_path: str | Path = "/", home_path: str | Path | None = None,
) -> dict[str, dict[str, int | bool | None]]:
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
    """Read charge, optional cycle count and capacity estimate without device identifiers."""
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
            try:
                cycle_count = int(_read(battery / "cycle_count") or "")
            except ValueError:
                cycle_count = -1
            if cycle_count >= 0:
                details["cycle_count"] = cycle_count
            try:
                state_of_health = int(_read(battery / "state_of_health") or "")
            except ValueError:
                state_of_health = -1
            if 0 <= state_of_health <= 100:
                details["state_of_health_percent"] = state_of_health
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


def battery_is_discharging(batteries: list[dict[str, str | int]]) -> bool:
    """Whether any detected battery reports that it is discharging."""
    return any(str(item.get("status", "")).casefold() == "discharging" for item in batteries)


def battery_power_status_unknown(batteries: list[dict[str, str | int]]) -> bool:
    """Whether batteries exist but none reports a recognized external-power state."""
    known = {"charging", "full", "not charging", "discharging"}
    return bool(batteries) and not any(
        str(item.get("status", "")).casefold() in known for item in batteries
    )


def sensor_near_critical_limit(
    sensors: list[dict[str, str | float]], margin_c: float = 10.0,
) -> bool:
    """Check whether the hottest sensor is close to its device-reported critical limit."""
    if not sensors:
        return False
    hottest = max(sensors, key=lambda item: item["temperature_c"])
    critical = hottest.get("critical_c")
    return isinstance(critical, (int, float)) and hottest["temperature_c"] >= critical - margin_c


def read_temperature_sensors(
    hwmon_path: str | Path = "/sys/class/hwmon",
    thermal_path: str | Path = "/sys/class/thermal",
) -> list[dict[str, str | float]]:
    """Read available local temperature sensors without probing or changing hardware."""
    sensors = []
    hwmon_root = Path(hwmon_path)
    try:
        hwmon_devices = sorted(hwmon_root.glob("hwmon*"))
    except OSError:
        hwmon_devices = []

    for device in hwmon_devices:
        chip = _read(device / "name") or ""
        try:
            inputs = sorted(device.glob("temp*_input"))
        except OSError:
            inputs = []
        for input_path in inputs:
            raw = _read(input_path)
            try:
                millidegrees = int(raw or "")
            except ValueError:
                continue
            if not -40_000 <= millidegrees <= 200_000:
                continue
            stem = input_path.name.removesuffix("_input")
            label = _read(device / f"{stem}_label")
            name_parts = [part for part in (chip, label) if part]
            name = " · ".join(name_parts) or stem
            sensor: dict[str, str | float] = {
                "name": " ".join("".join(c if c.isprintable() else " " for c in name).split())[:100],
                "temperature_c": round(millidegrees / 1000, 1),
            }
            critical = _read(device / f"{stem}_crit")
            try:
                critical_millidegrees = int(critical or "")
            except ValueError:
                critical_millidegrees = 0
            if -40_000 <= critical_millidegrees <= 200_000 and critical_millidegrees > 0:
                sensor["critical_c"] = round(critical_millidegrees / 1000, 1)
            sensors.append(sensor)

    if sensors:
        return sensors

    thermal_root = Path(thermal_path)
    try:
        zones = sorted(thermal_root.glob("thermal_zone*"))
    except OSError:
        zones = []
    for zone in zones:
        raw = _read(zone / "temp")
        try:
            millidegrees = int(raw or "")
        except ValueError:
            continue
        if not -40_000 <= millidegrees <= 200_000:
            continue
        name = _read(zone / "type") or zone.name
        sensors.append({
            "name": " ".join("".join(c if c.isprintable() else " " for c in name).split())[:100],
            "temperature_c": round(millidegrees / 1000, 1),
        })
    return sensors


def read_power_profile(timeout: float = 2.0) -> str:
    """Read the active power profile when power-profiles-daemon is available."""
    powerprofilesctl = shutil.which("powerprofilesctl")
    if not powerprofilesctl:
        return "unavailable"
    result = _run_local([powerprofilesctl, "get"], timeout)
    if result is None:
        return "unavailable"
    if result.returncode != 0:
        return "unavailable"
    profile = result.stdout.strip().casefold()
    return profile if profile in {"power-saver", "balanced", "performance"} else "unavailable"


def _run_cpu_benchmark_sample(duration_seconds: float) -> tuple[int, float]:
    deadline = time.perf_counter() + duration_seconds
    value = 1
    iterations = 0
    started = time.perf_counter()
    while time.perf_counter() < deadline:
        value = (value * 1664525 + 1013904223) & 0xFFFFFFFF
        iterations += 1
    elapsed = time.perf_counter() - started
    return iterations, elapsed


def run_cpu_benchmark(duration_seconds: float = 1.0) -> dict[str, float | int]:
    """Warm up, then use the median of three short integer-workload samples."""
    duration_seconds = max(0.1, min(float(duration_seconds), 5.0))
    _warmup_iterations, warmup_elapsed = _run_cpu_benchmark_sample(
        min(0.2, duration_seconds),
    )
    sample_rates = []
    iterations = 0
    measured_elapsed = 0.0
    for _ in range(3):
        sample_iterations, sample_elapsed = _run_cpu_benchmark_sample(duration_seconds)
        iterations += sample_iterations
        measured_elapsed += sample_elapsed
        if sample_elapsed > 0:
            sample_rates.append(sample_iterations / sample_elapsed)
    return {
        "iterations": iterations,
        "duration_seconds": round(warmup_elapsed + measured_elapsed, 3),
        "iterations_per_second": round(statistics.median(sample_rates)) if sample_rates else 0,
        "samples": len(sample_rates),
    }


def benchmark_score_change_percent(current: float, previous: float) -> float | None:
    """Return a relative score change, or None when no valid baseline exists."""
    if not math.isfinite(current) or not math.isfinite(previous) or previous <= 0:
        return None
    return round((current - previous) / previous * 100, 1)


_BENCHMARK_METHODS = {
    "cpu": "python-integer-loop-v2-median3",
    "graphics": "glmark2-score-v1",
}


def get_application_version(project_file: str | Path | None = None) -> str:
    """Return the installed version, or read it from the source checkout."""
    if project_file is None:
        project_file = Path(__file__).resolve().parent.parent / "pyproject.toml"
        if not Path(project_file).is_file():
            try:
                return metadata.version("ubuntu-start")
            except metadata.PackageNotFoundError:
                dpkg_query = shutil.which("dpkg-query")
                if not dpkg_query:
                    return "unknown"
                result = _run_local(
                    [dpkg_query, "-W", "-f=${Version}", "ubuntu-start"], timeout=2.0,
                )
                if result and result.returncode == 0:
                    package_version = result.stdout.strip()
                    if re.fullmatch(r"[0-9][A-Za-z0-9.+:~-]*", package_version):
                        return package_version
                return "unknown"
    try:
        contents = Path(project_file).read_text(encoding="utf-8")
    except OSError:
        return "unknown"
    match = re.search(r'(?m)^version\s*=\s*"([^"\n]+)"\s*$', contents)
    return match.group(1) if match else "unknown"


def _benchmark_state_path(path: str | Path | None = None) -> Path:
    if path is not None:
        return Path(path)
    state_home = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
    if not state_home.is_absolute():
        state_home = Path.home() / ".local/state"
    return state_home / "ubuntu-start" / "benchmarks.json"


def load_benchmark_baselines(
    path: str | Path | None = None,
    session_type: str | None = None,
    app_version: str | None = None,
) -> dict[str, dict[str, float | str]]:
    """Load compatible benchmark baselines from the user's private state directory."""
    try:
        with _benchmark_state_path(path).open(encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError, TypeError):
        return {}
    if not isinstance(payload, dict) or payload.get("schema_version") != 2:
        return {}
    entries = payload.get("baselines")
    if not isinstance(entries, dict):
        return {}
    current_session = (session_type or os.environ.get("XDG_SESSION_TYPE", "unknown")).casefold()
    current_version = app_version or get_application_version()

    baselines: dict[str, dict[str, float | str]] = {}
    for kind, method in _BENCHMARK_METHODS.items():
        entry = entries.get(kind)
        if not isinstance(entry, dict) or entry.get("method") != method:
            continue
        recorded_version = entry.get("app_version")
        if not isinstance(recorded_version, str) or (
            current_version != "*" and recorded_version != current_version
        ):
            continue
        score = entry.get("score")
        if isinstance(score, bool) or not isinstance(score, (int, float)):
            continue
        if not math.isfinite(score) or score <= 0:
            continue
        recorded_session = entry.get("session_type")
        if kind == "graphics" and (
            not isinstance(recorded_session, str)
            or current_session != "*" and recorded_session.casefold() != current_session
        ):
            continue
        baseline: dict[str, float | str] = {
            "score": float(score),
            "method": method,
            "app_version": recorded_version,
        }
        recorded_at = entry.get("recorded_at")
        if isinstance(recorded_at, str):
            baseline["recorded_at"] = recorded_at
        if kind == "graphics":
            baseline["session_type"] = recorded_session.casefold()
        duration = entry.get("duration_seconds")
        if (
            kind == "cpu"
            and isinstance(duration, (int, float))
            and not isinstance(duration, bool)
            and math.isfinite(duration)
            and duration > 0
        ):
            baseline["duration_seconds"] = float(duration)
        baselines[kind] = baseline
    return baselines


def save_benchmark_baseline(
    kind: str,
    score: float,
    duration_seconds: float | None = None,
    path: str | Path | None = None,
    recorded_at: str | None = None,
    session_type: str | None = None,
    app_version: str | None = None,
) -> bool:
    """Atomically save one score locally, with a restrictive file mode."""
    method = _BENCHMARK_METHODS.get(kind)
    if method is None or isinstance(score, bool) or not isinstance(score, (int, float)):
        return False
    if not math.isfinite(score) or score <= 0:
        return False

    baseline: dict[str, float | str] = {
        "score": float(score),
        "method": method,
        "app_version": app_version or get_application_version(),
        "recorded_at": recorded_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    if kind == "graphics":
        baseline["session_type"] = (
            session_type or os.environ.get("XDG_SESSION_TYPE", "unknown")
        ).casefold()
    if duration_seconds is not None:
        if (
            isinstance(duration_seconds, bool)
            or not isinstance(duration_seconds, (int, float))
            or not math.isfinite(duration_seconds)
            or duration_seconds <= 0
        ):
            return False
        baseline["duration_seconds"] = float(duration_seconds)

    destination = _benchmark_state_path(path)
    baselines = load_benchmark_baselines(
        destination,
        session_type="*",
        app_version=str(baseline["app_version"]),
    )
    baselines[kind] = baseline
    temporary_path = None
    descriptor = None
    try:
        destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        descriptor, temporary_path = tempfile.mkstemp(prefix="benchmarks-", dir=destination.parent)
        os.fchmod(descriptor, 0o600)
        handle = os.fdopen(descriptor, "w", encoding="utf-8")
        descriptor = None
        with handle:
            json.dump({"schema_version": 2, "baselines": baselines}, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, destination)
        temporary_path = None
        return True
    except OSError:
        return False
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass
        if temporary_path:
            try:
                os.unlink(temporary_path)
            except OSError:
                pass


def clear_benchmark_baselines(path: str | Path | None = None) -> bool:
    """Remove the user's locally saved CPU and graphics benchmark scores."""
    try:
        _benchmark_state_path(path).unlink()
    except FileNotFoundError:
        return True
    except OSError:
        return False
    return True


def find_benchmark_tool(name: str) -> str | None:
    """Return only known benchmark launchers, when installed."""
    allowed = {"glmark2-wayland", "glmark2", "gnome-disks"}
    if name not in allowed:
        return None
    return shutil.which(name)


def find_graphics_benchmark_tool(session_type: str | None = None) -> str | None:
    """Prefer the glmark2 launcher matching the current display session."""
    session_type = (session_type or os.environ.get("XDG_SESSION_TYPE", "")).casefold()
    candidates = (
        ("glmark2-wayland", "glmark2")
        if session_type == "wayland"
        else ("glmark2", "glmark2-wayland")
    )
    for candidate in candidates:
        executable = find_benchmark_tool(candidate)
        if executable:
            return executable
    return None


def parse_glmark2_score(output: str) -> int | None:
    """Extract glmark2's final aggregate score from its output."""
    if not isinstance(output, str):
        return None
    match = re.search(r"^\s*glmark2 Score:\s*(\d+)\s*$", output, re.IGNORECASE | re.MULTILINE)
    return int(match.group(1)) if match else None


def parse_secure_boot_status(output: str) -> str | None:
    """Parse the small set of Secure Boot states reported by mokutil."""
    if not isinstance(output, str):
        return None
    for line in output.splitlines():
        normalized = " ".join(line.casefold().split())
        if normalized == "secureboot enabled":
            return "enabled"
        if normalized == "secureboot disabled":
            return "disabled"
        if normalized == "platform is in setup mode":
            return "setup-mode"
        if normalized == "efi variables are not supported on this system":
            return "unsupported"
    return None


def read_secure_boot_status(timeout: float = 3.0) -> tuple[str | None, str | None]:
    """Read Secure Boot state with mokutil; never change firmware settings."""
    mokutil = shutil.which("mokutil")
    if not mokutil:
        return None, "not-installed"
    result = _run_local([mokutil, "--sb-state"], timeout, env={**os.environ, "LC_ALL": "C"})
    if result is None:
        return None, "timeout-or-unavailable"
    state = parse_secure_boot_status(f"{result.stdout}\n{result.stderr}")
    if state:
        return state, None
    return None, "unavailable"


def parse_apt_upgrade_simulation(output: str) -> tuple[int, int] | None:
    """Return upgradeable and held-back package counts from `apt-get -s upgrade`."""
    if not isinstance(output, str) or not output.strip():
        return None
    upgrade_count = sum(1 for line in output.splitlines() if line.startswith("Inst "))
    summary = re.search(r"\b(\d+) not upgraded\.", output)
    if not summary:
        return None
    return upgrade_count, int(summary.group(1))


def read_apt_update_status(
    timeout: float = 15.0,
    update_stamp: str | Path = "/var/lib/apt/periodic/update-success-stamp",
) -> tuple[dict[str, int | None] | None, str | None]:
    """Simulate an APT upgrade against cached indexes; never refresh or install packages."""
    apt_get = shutil.which("apt-get")
    if not apt_get:
        return None, "not-installed"
    result = _run_local([apt_get, "-s", "upgrade"], timeout, env={**os.environ, "LC_ALL": "C"})
    if result is None:
        return None, "timeout"
    if result.returncode != 0:
        return None, "unavailable"
    counts = parse_apt_upgrade_simulation(result.stdout)
    if counts is None:
        return None, "unavailable"
    try:
        last_updated = Path(update_stamp).stat().st_mtime_ns // 1_000_000_000
    except OSError:
        last_updated = None
    return {"upgradeable": counts[0], "held_back": counts[1], "last_updated": last_updated}, None


def read_reboot_required(path: str | Path = "/run/reboot-required") -> bool | None:
    """Read Ubuntu's local reboot-required marker without changing system state."""
    try:
        Path(path).stat()
    except FileNotFoundError:
        return False
    except OSError:
        return None
    return True


def parse_dpkg_audit(output: str) -> list[str] | None:
    """Extract package names reported by dpkg --audit; None means unknown output."""
    if not isinstance(output, str):
        return None
    if not output.strip():
        return []
    packages = set()
    for line in output.splitlines():
        match = re.match(
            r"^\s+([a-z0-9][a-z0-9+.-]*(?::[a-z0-9][a-z0-9-]*)?)(?:\s|$)",
            line,
        )
        if match:
            packages.add(match.group(1))
    return sorted(packages) if packages else None


def read_package_health(timeout: float = 8.0) -> tuple[list[str] | None, str | None]:
    """Run the local, read-only dpkg audit without changing packages or contacting a network."""
    dpkg = shutil.which("dpkg")
    if not dpkg:
        return None, "not-installed"
    result = _run_local([dpkg, "--audit"], timeout, env={**os.environ, "LC_ALL": "C"})
    if result is None:
        return None, "timeout-or-unavailable"
    if result.returncode != 0:
        return None, "unavailable"
    packages = parse_dpkg_audit(result.stdout)
    if packages is None:
        return None, "unavailable"
    return packages, None


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
    route_attributes = {
        "via", "dev", "proto", "metric", "scope", "table", "src", "onlink",
        "nexthop", "weight", "encap", "mtu", "advmss", "pref",
    }
    for line in output.splitlines():
        fields = line.split()
        if len(fields) >= 5 and fields[0] == "default" and "via" in fields and "dev" in fields:
            try:
                gateway = str(ipaddress.ip_address(fields[fields.index("via") + 1]))
                interface = fields[fields.index("dev") + 1]
            except (ValueError, IndexError):
                continue
            if (
                interface not in route_attributes
                and interface
                and interface.replace("_", "").replace("-", "").replace(".", "").isalnum()
            ):
                return gateway, interface
    return None


def _normalize_unicast_mac(value: str | None) -> str | None:
    """Return a canonical unicast MAC address, or None for invalid addresses."""
    if not isinstance(value, str):
        return None
    mac = value.upper().replace("-", ":")
    parts = mac.split(":")
    if len(parts) != 6 or not all(
        len(part) == 2 and all(char in "0123456789ABCDEF" for char in part)
        for part in parts
    ):
        return None
    octets = [int(part, 16) for part in parts]
    if octets[0] & 1 or not any(octets):
        return None
    return ":".join(parts)


def parse_neighbor_mac(output: str) -> str | None:
    """Return a valid unicast MAC address from `ip neigh` output."""
    fields = output.split()
    if "lladdr" not in fields:
        return None
    try:
        return _normalize_unicast_mac(fields[fields.index("lladdr") + 1])
    except IndexError:
        return None


def lookup_oui_vendor(mac: str | None, databases: tuple[str, ...] = (
    "/usr/share/ieee-data/oui.txt", "/usr/share/hwdata/oui.txt", "/usr/share/misc/oui.txt",
)) -> str | None:
    """Match a MAC prefix against an installed IEEE OUI database; never use a web lookup."""
    normalized = _normalize_unicast_mac(mac)
    if not normalized:
        return None
    # Locally administered addresses do not identify a manufacturer OUI.
    if int(normalized[:2], 16) & 2:
        return None
    prefix = normalized.upper().replace(":", "-")[:8]
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


def _run_local(
    command: list[str], timeout: float = 3.0, env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(command, capture_output=True, text=True, check=False, timeout=timeout, env=env)
    except (OSError, subprocess.TimeoutExpired):
        return None


def run_network_diagnostics(timeout: float = 3.0) -> dict[str, str | float | None]:
    """Measure configured DNS and gateway latency; call only after user starts the check."""
    result: dict[str, str | float | None] = {
        "dns_latency_ms": None, "dns_test_duration_ms": None, "dns_error": None,
        "gateway": None, "gateway_interface": None,
        "gateway_latency_ms": None, "gateway_test_duration_ms": None,
        "gateway_error": None,
        "gateway_mac": None, "gateway_vendor": None,
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
        ping_command = shutil.which("ping")
        if not ping_command:
            result["gateway_error"] = "ping-not-installed"
        else:
            start = time.monotonic()
            ping = _run_local([ping_command, family, "-I", interface, "-n", "-c", "1", "-W", str(max(1, int(timeout))), gateway], timeout + 1)
            if ping is None:
                result["gateway_error"] = "timeout"
                result["gateway_test_duration_ms"] = round((time.monotonic() - start) * 1000, 1)
            elif ping.returncode == 0:
                timing = re.search(r"time[=<]([0-9.]+)\s*ms", ping.stdout)
                result["gateway_latency_ms"] = float(timing.group(1)) if timing else round((time.monotonic() - start) * 1000, 1)
            else:
                result["gateway_error"] = "no-response"
                result["gateway_test_duration_ms"] = round((time.monotonic() - start) * 1000, 1)
        neighbor = _run_local(["ip", family, "neigh", "show", "to", gateway, "dev", interface], timeout)
        mac = parse_neighbor_mac(neighbor.stdout) if neighbor and neighbor.returncode == 0 else None
        result["gateway_mac"] = mac
        result["gateway_vendor"] = lookup_oui_vendor(mac)
    else:
        result["gateway_error"] = "no-default-route"

    start = time.monotonic()
    getent_command = shutil.which("getent")
    if not getent_command:
        result["dns_error"] = "getent-not-installed"
        return result
    dns = _run_local([getent_command, "ahosts", "ubuntu.com"], timeout)
    dns_elapsed_ms = round((time.monotonic() - start) * 1000, 1)
    result["dns_test_duration_ms"] = dns_elapsed_ms
    if dns and dns.returncode == 0 and dns.stdout.strip():
        result["dns_latency_ms"] = dns_elapsed_ms
    elif dns is None:
        result["dns_error"] = "timeout"
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
            # A missed ping may mean ICMP is filtered, not that the gateway is down.
            "gateway_reachable": True if diagnostics.get("gateway_latency_ms") is not None else None,
        }
    return json.dumps(report, ensure_ascii=False, indent=2) + "\n"


def is_valid_support_report(report_text: str) -> bool:
    """Accept only editable JSON documents that retain the support-report schema."""
    try:
        report = json.loads(report_text)
    except (TypeError, json.JSONDecodeError):
        return False
    return (
        isinstance(report, dict)
        and type(report.get("report_version")) is int
        and report.get("report_version") == 1
        and isinstance(report.get("system"), dict)
    )
