#!/usr/bin/env python3
"""Ubuntu Start: a localized first-run and device troubleshooting guide."""
import gettext
import locale
import os
import platform
import shutil
import sys
import threading
import time
import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk
from system_diagnostics import battery_is_discharging, battery_power_status_unknown, benchmark_score_change_percent, build_support_report, check_internet_connection, clear_benchmark_baselines, find_benchmark_tool, find_graphics_benchmark_tool, get_application_version, is_valid_support_report, load_benchmark_baselines, normalize_desktop_name, normalize_session_type, parse_glmark2_score, pressure_threshold_exceeded, read_accessibility_settings, read_apt_update_status, read_automatic_upgrade_status, read_audio_status, read_backup_tool_status, read_battery_status, read_bluetooth_status, read_boot_critical_chain, read_boot_timing, read_display_connectors, read_failed_services, read_firewall_status, read_hardware_details, read_interface_ip_status, read_memory_status, read_network_adapter_details, read_network_devices, read_package_health, read_pci_devices, read_power_profile, read_printer_status, read_remote_session, read_reboot_required, read_resource_pressure, read_rfkill_status, read_root_encryption_status, read_secure_boot_status, read_storage_locations, read_temperature_sensors, read_time_status, read_usb_devices, read_video_devices, read_wifi_link_status, run_cpu_benchmark, run_network_diagnostics, save_benchmark_baseline, sensor_near_critical_limit
from guide_search import find_guide_matches
from first_run_state import TASK_IDS as FIRST_RUN_TASK_IDS, load_completed_tasks, save_completed_tasks

APP_ID = "se.danielnylander.UbuntuStart"
DOMAIN = "ubuntu-start"
_prefix_locale_dir = os.path.join(os.path.dirname(sys.executable), "..", "share", "locale")
LOCALEDIR = os.environ.get(
    "UBUNTU_START_LOCALEDIR",
    _prefix_locale_dir if os.path.isdir(_prefix_locale_dir) else "/usr/share/locale",
)
locale.setlocale(locale.LC_ALL, "")
gettext.bindtextdomain(DOMAIN, LOCALEDIR)
gettext.textdomain(DOMAIN)
_ = gettext.gettext

FIRST_RUN_TASKS = [
    (
        "language-keyboard", _("Language and keyboard"),
        _("Choose your display language, region and keyboard layout."),
        ("settings", "keyboard"),
    ),
    (
        "network", _("Internet connection"),
        _("Connect to Wi-Fi or a wired network."), ("settings", "wifi"),
    ),
    (
        "updates", _("Updates"),
        _("Check for system updates and restart if Ubuntu asks you to."),
        ("app", "update-manager"),
    ),
    (
        "backups", _("Set up backups"),
        _("Choose a separate backup location and make sure you can restore a file."),
        ("guide", "Set up backups"),
    ),
    (
        "security", _("Improve everyday security"),
        _("Review updates, account protection, app permissions and safe browsing."),
        ("guide", "Improve everyday security"),
    ),
    (
        "sound-display", _("Sound and display"),
        _("Choose speakers, microphone and monitor settings."), ("settings", "sound"),
    ),
    (
        "privacy", _("Privacy and screen lock"),
        _("Review app permissions and automatic screen locking."),
        ("settings", "privacy"),
    ),
    (
        "accessibility", _("Accessibility"),
        _("Adjust text size, magnification, screen reader and keyboard access."),
        ("settings", "universal-access"),
    ),
]

GUIDES = [
    (_("Sound and microphones"), "sound", [
        (_("Choose the right devices"), _("Open Sound Settings and select the speakers or headphones you want to use.")),
        (_("Check the volume"), _("Make sure output volume is up and the device is not muted. Try another app or audio file.")),
        (_("Check the microphone"), _("Speak and watch the input level in Sound Settings. Check the app’s microphone permission if only one app is affected.")),
    ]),
    (_("Battery and charging"), "power", [
        (_("Check the power adapter"), _("Connect the adapter securely at both ends and try a working outlet. Stop using a cable or adapter that is damaged or unusually hot.")),
        (_("Check the charging status"), _("Review the charge level and charging state on the Network and hardware page. If it is not charging, check the power connection and Power Settings.")),
        (_("Check for a charging limit"), _("Some computers intentionally pause charging below 100% to reduce battery wear. If Network and hardware reports a charge limit, check your computer manufacturer's instructions or power settings. Ubuntu Start only reads this value and does not change it.")),
        (_("Check for battery wear"), _("Use capacity estimates, reported battery health and cycle count as context, not as a universal replacement threshold. If capacity is much lower than design, consult the laptop manufacturer’s battery service information.")),
    ]),
    (_("Bluetooth"), "bluetooth", [
        (_("Check power and charge"), _("Make sure Bluetooth is enabled and the device has enough charge.")),
        (_("Turn on pairing mode"), _("Keep the device nearby and follow its instructions for pairing mode.")),
        (_("Try pairing again"), _("If an old pairing is listed, remove it in Settings, then pair the device again.")),
    ]),
    (_("Fingerprint reader"), "system", [
        (_("Keep your account password available"), _("Fingerprint sign-in is an alternative to your account password, not a replacement. Keep password sign-in available in case the reader does not work or Ubuntu asks for your password.")),
        (_("Open fingerprint settings"), _("Open Settings, choose System, then Users. Look for Fingerprint Login and select Disabled to add a fingerprint. Unlock the panel if you are setting up another user.")),
        (_("Enroll a finger"), _("Choose a finger and follow the on-screen prompts. Lift and reposition your finger each time the reader asks. A clean, dry finger can make enrollment easier.")),
        (_("Test fingerprint sign-in"), _("Save your work before signing out. At the sign-in screen, select your account and try the enrolled finger. If it is not accepted, choose password sign-in.")),
        (_("If fingerprint settings are missing"), _("Fingerprint readers need hardware and software supported by Ubuntu. Check the device model or hardware ID in Network and hardware and use Ubuntu or manufacturer support information. Do not paste unreviewed PAM commands or install drivers from untrusted websites.")),
    ]),
    (_("Printers"), "printers", [
        (_("Check the printer"), _("Make sure it is powered on and has paper, ink or toner, and no paper jam.")),
        (_("Check the connection"), _("For a network printer, confirm it is on the same network as this computer. For USB, reconnect the cable.")),
        (_("Add the printer"), _("Open Printer Settings, add the printer and send a test page.")),
        (_("Check for a model-specific driver"), _("If printing still fails, consult Ubuntu’s documentation or the printer manufacturer before installing extra software.")),
    ]),
    (_("Displays and graphics"), "display", [
        (_("Check power and cables"), _("Make sure the display is on, the cable is connected and the correct input is selected.")),
        (_("Compare supported resolutions"), _("On the Network and hardware page, review the resolutions Linux reports for connected displays. This list does not identify the currently selected resolution or refresh rate. Open Display Settings to compare the available options.")),
        (_("Open Display Settings"), _("Check whether Ubuntu detects the display. Try a supported resolution and refresh rate.")),
        (_("Review graphics drivers"), _("If graphics are unstable or a feature is missing, review the drivers offered by Ubuntu before changing anything.")),
    ]),
    (_("External display or projector"), "display", [
        (_("Check the display input"), _("Turn the display on and select the input that matches its cable, such as HDMI or DisplayPort.")),
        (_("Reconnect the cable"), _("Disconnect and reconnect both ends. If you use a dock or adapter, test a direct connection when possible.")),
        (_("Review display arrangement"), _("Open Display Settings, select Detect Displays if available, and check the arrangement, resolution and refresh rate.")),
        (_("Test one display at a time"), _("Disconnect other external screens temporarily. If the display still is not detected, try another cable or port.")),
    ]),
    (_("Keyboards"), "keyboard", [
        (_("Check the connection"), _("For a wired keyboard, reconnect the cable. For a wireless keyboard, check its charge or batteries, power switch and USB receiver.")),
        (_("Check the keyboard layout"), _("Open Keyboard Settings and select the layout you intend to use. Test the keys in another app to see whether the problem is app-specific.")),
        (_("Try another port or keyboard"), _("For a USB keyboard, try another port. If available, connect another keyboard to help identify whether the problem is with the keyboard or computer.")),
    ]),
    (_("Touchpads"), "mouse", [
        (_("Make sure the touchpad is enabled"), _("Open Mouse and Touchpad Settings and check that the touchpad is switched on. Some laptops also have a keyboard shortcut that turns it off.")),
        (_("Check the surface and pointer speed"), _("Keep the touchpad clean and dry. Adjust pointer speed in Settings, then test basic movement before trying gestures.")),
        (_("Compare with an external mouse"), _("If a mouse works but the touchpad does not, check for Ubuntu updates and consult the laptop support information before changing drivers.")),
    ]),
    (_("Wi-Fi"), "wifi", [
        (_("Check Wi-Fi and airplane mode"), _("Turn airplane mode off and make sure Wi-Fi is enabled in Quick Settings.")),
        (_("Check for a wireless radio block"), _("Refresh Wireless radio status on the Network and hardware page. A software block may come from airplane mode. A hard block is reported by hardware or firmware and cannot be cleared by an app; check the computer manual before changing settings.")),
        (_("Check the network"), _("See whether another device can connect. If none can, restart the router and check its internet connection.")),
        (_("Reconnect to the network"), _("Forget the network in Wi-Fi Settings, then connect again and carefully enter the password.")),
        (_("If only this computer has trouble"), _("Install available Ubuntu updates. Check the computer or Wi-Fi adapter support information before installing a driver.")),
    ]),
    (_("Camera"), "privacy", [
        (_("Check the camera"), _("Open its privacy shutter or switch, reconnect it if external and make sure its indicator light turns on.")),
        (_("Check app permissions"), _("Review camera access in Privacy Settings. A managed work or school computer may restrict access.")),
        (_("Close other camera apps"), _("Quit video calls and other apps that may already be using the camera, then try again.")),
    ]),
    (_("USB devices"), "hardware", [
        (_("Check the USB connection"), _("Make sure the device is powered on. Reconnect it directly to the computer if possible, without a hub.")),
        (_("Refresh the USB device list"), _("Open Network and hardware and refresh Connected USB devices. If the device appears, note its hardware ID and driver.")),
        (_("Use unknown USB storage carefully"), _("Do not connect a USB drive you found or received unexpectedly. If you must inspect an untrusted drive, avoid opening files or shortcuts and ask a trusted technician to check it in an isolated environment. Ubuntu Start does not scan USB storage for malware.")),
        (_("Try another port or cable"), _("Use another port or cable. Check whether another device works in the same port.")),
        (_("Use hardware details when asking for help"), _("The hardware ID and driver can help support identify the device. Do not share a serial number.")),
    ]),
    (_("PCI device is missing or not working"), "hardware", [
        (_("Refresh the PCI device list"), _("Open Network and hardware and refresh PCI devices. The list shows hardware IDs and any kernel driver currently attached.")),
        (_("Check the driver status"), _("A device with no attached driver may need a driver, but this status alone does not prove a fault. Check Ubuntu’s Additional Drivers tool and the device manufacturer’s Ubuntu support information.")),
        (_("Keep the hardware ID for support"), _("Share the PCI hardware ID and driver name when asking for help. Do not install drivers from an untrusted source.")),
    ]),
    (_("Check whether a storage drive is healthy"), "disks", [
        (_("Back up important files first"), _("If you hear unusual noises from the disk, see read errors or suspect that the drive is failing, back up important files to another drive or a trusted backup service before testing. Avoid benchmarks for now.")),
        (_("Open Disks and select the drive"), _("Open Disks from the Activities overview and select the physical drive by its model and capacity. Check carefully that you selected the drive you intend to inspect.")),
        (_("Review SMART health information"), _("Open the drive menu and choose SMART Data and Self-Tests. Read the overall assessment and attributes. This option may be unavailable for some drives, USB adapters or virtual machines.")),
        (_("Run a short self-test if available"), _("Only start a short self-test after important files are backed up. Wait for it to finish. A passed test cannot guarantee that a drive is fault-free.")),
        (_("Act on warnings"), _("If the assessment or test reports a problem, avoid repeated tests and writes, back up any remaining important files and contact the manufacturer or support. Missing SMART data does not prove that a drive is healthy or failing.")),
    ]),
    (_("Wired network"), "network", [
        (_("Check the Ethernet cable"), _("Connect the cable firmly to the computer and to a router, switch or wall socket. Look for a link light near the port.")),
        (_("Wait for a connection"), _("Ubuntu normally configures a wired connection automatically. Give it a few seconds and check the network menu.")),
        (_("Check Network Settings"), _("Open Network Settings and confirm that the wired connection is enabled.")),
        (_("Try another port or cable"), _("If there is still no link, try a different cable or router port. Ask your network administrator before entering manual IP settings.")),
    ]),
    (_("Computer feels slow"), "hardware", [
        (_("Check memory while it feels slow"), _("Open Network and hardware and refresh Memory use. Compare available RAM and swap while the slowdown is happening.")),
        (_("Check CPU, memory and storage pressure"), _("Refresh System resource pressure during the slowdown. A higher percentage means tasks spent more time waiting on that resource; the reading is system-wide and does not identify a process.")),
        (_("Close applications you recognize"), _("Save your work, then close applications and browser tabs you are not using. Avoid stopping unfamiliar system processes.")),
        (_("Check free storage"), _("Review the system filesystem in Network and hardware. If it is almost full, follow the safe disk cleanup guide.")),
        (_("Review Ubuntu updates"), _("Check cached update status, then open Software Updater to refresh package information and review any changes.")),
    ]),
    (_("A system service is marked failed"), "hardware", [
        (_("Check whether a feature is affected"), _("A failed service does not always mean something is broken. First check whether a device or feature related to the service is actually not working.")),
        (_("Read the service name and description"), _("Refresh System service status in systemd and compare the name with the feature that has a problem. The list does not show why the service failed.")),
        (_("Inspect one service in Terminal"), _("Open Terminal and run systemctl status SERVICE.service, replacing SERVICE.service with the exact unit name shown. Read the Active and Description lines first. This command only displays current status; it does not change the service.")),
        (_("Read recent service messages"), _("If you need more detail, run journalctl -u SERVICE.service -b --no-pager -n 40 with the same unit name. This displays up to 40 recent messages from this boot. Review the output before sharing it because logs can contain private details.")),
        (_("Ask for help with useful details"), _("Share the exact service unit name, what feature is affected, and the relevant error lines after removing usernames, device names and other private details. Never post a full log without reviewing it.")),
        (_("Get help before changing services"), _("Check Ubuntu documentation or ask your system administrator before stopping, restarting or disabling a service. Some failures are temporary or expected.")),
    ]),
    (_("Computer gets hot or the fan is loud"), "hardware", [
        (_("Keep vents clear"), _("Place the computer on a firm surface and keep air vents clear of fabric, dust and other obstructions.")),
        (_("Check available temperature sensors"), _("Open Network and hardware and refresh Temperature sensor status. Some computers, docks and virtual machines do not expose temperature sensors to Linux.")),
        (_("Compare readings with device guidance"), _("Sensor labels and normal temperatures vary by model. Check the computer manufacturer’s guidance instead of relying on a universal temperature limit.")),
        (_("Stop if the computer becomes unusually hot"), _("Save your work and shut down if the computer becomes unusually hot, smells burnt or behaves unpredictably. Contact the manufacturer or support service.")),
    ]),
    (_("Improve benchmark results"), "performance", [
        (_("Prepare a fair comparison"), _("Connect the computer to power, save your work, close demanding apps you recognize, and wait for updates, backups and file copies to finish. Repeat each test under similar conditions.")),
        (_("Use an available performance power profile"), _("If Ubuntu offers the Performance profile, choose it in Settings > Power while connected to AC. It can increase fan noise, heat and power use. Switch back to Balanced or Power Saver when finished.")),
        (_("Keep the computer cool"), _("Place the computer on a firm, flat surface and keep its air vents clear. Let it cool before repeating a test. Stop if it becomes unusually hot or smells burnt.")),
        (_("Keep graphics test conditions the same"), _("Use the same display, resolution and desktop session for each run. In Software and Updates > Additional Drivers, use only a driver Ubuntu recommends for this computer; avoid drivers from unfamiliar websites.")),
        (_("Start with a read-only disk test"), _("Use the read-only benchmark in GNOME Disks first, and wait for file copies or updates to finish. A write benchmark changes data on the selected drive; run it only when you have a current backup.")),
        (_("Understand what each score measures"), _("The CPU score measures Ubuntu Start's own workload, not overall computer speed. Graphics scores depend on the driver, display and desktop session; disk results depend on the selected drive and current activity. Compare the same computer and settings. Do not overclock or disable security features to chase a higher score.")),
    ]),
]

SYSTEM_GUIDES = [
    (_("Connect to Wi-Fi"), ("settings", "wifi"), _("Open Wi-Fi Settings"), [
        (_("Open Quick Settings"), _("Select the system menu at the top-right of the screen, then open the Wi-Fi section.")),
        (_("Choose a network"), _("Select the network name you recognize. Ask its owner if you are not sure which network to use.")),
        (_("Enter the password"), _("Type the network password when Ubuntu asks, then select Connect. Never share the password in a support request.")),
        (_("Check the connection"), _("Wait for the Wi-Fi icon to settle. If it disconnects, move closer to the router and check the password.")),
    ]),
    (_("Connect to a VPN"), ("settings", "network"), _("Open Network Settings"), [
        (_("Get the connection details"), _("Ask your VPN provider or work or school administrator for the connection type and setup details. Never share passwords, private keys or VPN configuration files in a support request.")),
        (_("Add the VPN in Network Settings"), _("Open Network Settings and look for the VPN section. Choose + if it is available. If your connection type is not listed, ask the provider or administrator which trusted Ubuntu component is required.")),
        (_("Connect and check the status"), _("Select the saved VPN from the system menu and choose Connect. If it fails, check your internet connection, device clock and setup details. A VPN does not make all online activity anonymous.")),
    ]),
    (_("Connect with an Ethernet cable"), ("settings", "network"), _("Open Network Settings"), [
        (_("Connect the cable"), _("Plug one end into the computer and the other into a router, switch or active wall socket.")),
        (_("Wait for Ubuntu"), _("A wired connection is usually configured automatically. The network menu shows when it is ready.")),
        (_("Check the connection"), _("Open Network Settings and make sure the Wired switch is on. If there is no link light, try another port or cable.")),
    ]),
    (_("Understand connection test results"), ("overview", "network-diagnostics"), _("Open network diagnostics"), [
        (_("Read the DNS time"), _("The DNS time measures one lookup for ubuntu.com using your configured resolver. It does not measure the speed of every website or your full internet connection. Compare repeated results on the same network; there is no single pass value for every connection.")),
        (_("Read the gateway response"), _("The gateway time measures one ping between this computer and the local router. A Wi-Fi signal, router load and local network conditions can affect it. Some gateways ignore ping, so no reply alone does not prove that the network is down.")),
        (_("Compare the two checks"), _("If the gateway responds but DNS fails, review DNS settings and check for a network sign-in page. If gateway replies are slow on Wi-Fi, move closer to the access point and compare again. These checks suggest where to look; they do not diagnose the cause.")),
        (_("Understand the manufacturer match"), _("The gateway manufacturer is matched locally from its MAC address. The database may be missing or outdated, and a randomized or reassigned address may not identify the router maker.")),
    ]),
    (_("Understand system startup time"), ("overview", "startup-time"), _("Open startup time check"), [
        (_("Read the reported boot timing"), _("Open Network and hardware and select Check startup time. The check reads the timing summary reported by systemd and makes no system changes.")),
        (_("Understand the timing parts"), _("The summary can include firmware, boot loader, kernel and userspace time. Firmware and boot loader values appear only when the system reports them.")),
        (_("Inspect the dependency chain"), _("Select Inspect graphical startup chain to read the systemd path to graphical.target. The @ value shows when a unit became active; the + value shows how long it took to start.")),
        (_("Review service names before sharing"), _("The chain shows one dependency path, not every service or proof of a fault. Service names can reveal installed software, so review the output before sharing it.")),
        (_("Know what the timing leaves out"), _("Systemd's boot timing does not measure every app that starts after you sign in. If the desktop becomes slow only after login, the reported boot time may not explain it.")),
        (_("Avoid changing services based on one reading"), _("Boot time varies with updates and background work. Do not disable or mask system services based on one timing result; ask for help before changing them.")),
    ]),
    (_("Check date and time"), ("settings", ("system", "datetime")), _("Open Date & Time Settings"), [
        (_("Check the time zone"), _("Make sure the selected time zone matches your location. A wrong time zone changes the displayed local time.")),
        (_("Review automatic time"), _("If automatic date and time is available, turn it on so Ubuntu can keep the system clock synchronized.")),
        (_("Check the network connection"), _("If the clock is not synchronized, check the internet connection and review Date and Time Settings again.")),
        (_("Ask before changing a managed computer"), _("Work or school computers may control time settings centrally. Ask the administrator if the options are locked.")),
    ]),
    (_("Add a printer"), ("settings", "printers"), _("Open Printer Settings"), [
        (_("Connect the printer"), _("Turn it on and connect it to the same network as your computer, or connect it with USB.")),
        (_("Add the printer"), _("Open Printers in Settings, select Add Printer and choose the printer Ubuntu finds.")),
        (_("Print a test page"), _("Follow the prompts, then print a test page. Install a model-specific driver only when Ubuntu or the manufacturer recommends it.")),
    ]),
    (_("Check printer queue"), ("overview", "printer"), _("Open printer status"), [
        (_("Refresh the local queue status"), _("Open Network and hardware and select Refresh printer status to read queues from the local CUPS service.")),
        (_("Check a disabled queue"), _("If a queue is disabled or stopped, check the printer for paper, power or connection problems, then review its message in Printer Settings.")),
        (_("Send a test page when ready"), _("Once the printer and queue are ready, send a test page from Printer Settings.")),
    ]),
    (_("Pair a Bluetooth device"), ("settings", "bluetooth"), _("Open Bluetooth Settings"), [
        (_("Prepare the device"), _("Charge the device, keep it nearby and follow its instructions to enable pairing mode.")),
        (_("Enable Bluetooth"), _("Open Bluetooth Settings and make sure Bluetooth is switched on. Managed computers may restrict this setting.")),
        (_("Check the Bluetooth service"), _("Open Network and hardware and refresh Bluetooth status. If the service is not running or has failed, refresh System service status and ask for help before changing service settings.")),
        (_("Select and pair the device"), _("Choose the device from the list and confirm the pairing code on both devices if prompted.")),
        (_("Reconnect if pairing fails"), _("Remove an old pairing, restart Bluetooth on the device and computer, then try again.")),
    ]),
    (_("Fix Bluetooth audio"), ("settings", "sound"), _("Open Sound Settings"), [
        (_("Check that the headset is connected"), _("Charge the headset, enable Bluetooth and connect it in Bluetooth Settings. If it is not paired yet, use the Bluetooth pairing guide first.")),
        (_("Select the headset as the output"), _("Open Sound Settings and select the headset under Output. Check that the volume is up and the device is not muted.")),
        (_("Choose the right microphone for calls"), _("For calls, check which microphone the app uses. Some headsets switch to a call profile while their microphone is active, which can change playback quality. Available profiles vary by headset.")),
        (_("Test audio in another app"), _("Play a familiar sound in another app. If it works there, check the original app’s volume and audio-device settings.")),
        (_("Pair again only if needed"), _("If the headset still has no sound, remove its old pairing in Bluetooth Settings, put it back in pairing mode and connect it again. Do not install drivers from an unfamiliar website.")),
    ]),
    (_("Fix an external display"), ("settings", "display"), _("Open Display Settings"), [
        (_("Select the right input"), _("Turn on the display and select the input that matches its cable.")),
        (_("Check cable and adapter"), _("Reconnect both ends. If you use a dock or adapter, test a direct connection when possible.")),
        (_("Review display settings"), _("Check that Ubuntu detects the display, then choose a supported resolution and refresh rate.")),
        (_("Isolate the problem"), _("Disconnect other displays and try another cable or port to identify the cause.")),
    ]),
    (_("Make text easier to read"), ("settings", "universal-access"), _("Open Accessibility Settings"), [
        (_("Open Accessibility settings"), _("In Settings, choose Accessibility and open the Seeing section.")),
        (_("Turn on Large Text"), _("Switch on Large Text. You can also try the accessibility menu in the top bar for a quick toggle.")),
        (_("Adjust other display options"), _("Try High Contrast or a different cursor size if those make the screen easier for you to use.")),
    ]),
    (_("Set up automatic screen locking"), ("settings", "privacy"), _("Open Settings"), [
        (_("Open Privacy settings"), _("Open Settings and look for Privacy & Security or Privacy. Panel names can vary between Ubuntu releases.")),
        (_("Turn on automatic screen locking"), _("Find Screen Lock and enable automatic screen locking. On managed computers, your organization may control this setting.")),
        (_("Choose a practical lock delay"), _("Choose how long the computer can be idle before locking. A shorter delay protects an unattended session sooner, while a longer delay can be more convenient.")),
        (_("Test the lock and sign-in"), _("Press Super+L to lock the screen, then unlock it using your usual sign-in method. Keep your account password available in case another sign-in method is unavailable.")),
        (_("Know what screen locking protects"), _("Locking protects an open session when you step away; it does not sign you out, and it does not encrypt files on the disk. Keep backups, and use disk encryption when you need protection for files on a powered-off or lost computer.")),
    ]),
    (_("Improve everyday security"), ("settings", "privacy"), _("Open Privacy & Security Settings"), [
        (_("Install Ubuntu security updates"), _("Open Software Updater regularly, review the proposed changes and install updates from Ubuntu. Check Software & Updates for automatic security update settings; available options and names can vary by release.")),
        (_("Check the automatic security update setup"), _("On Network and hardware, choose Check automatic update setup to read APT's setting, the unattended-upgrades package and the daily systemd timer. If one is disabled or missing, review Software & Updates or ask your administrator. This check cannot confirm a successful recent run or which repositories are included.")),
        (_("Check whether updates are waiting"), _("On Network and hardware, run the cached package update check. If packages are ready to upgrade, open Software Updater to refresh the lists, review the proposed changes and install trusted Ubuntu updates. The check does not refresh lists or install packages.")),
        (_("Choose software carefully"), _("Prefer Ubuntu App Center or official Ubuntu repositories. Check the publisher and requested permissions before installing an app. Avoid installers and drivers from websites you do not trust.")),
        (_("Protect your account"), _("Use a long, unique password for your computer and a password manager for accounts. Turn on multi-factor authentication for online accounts when available. For important accounts, prefer phishing-resistant sign-in such as passkeys or security keys when supported. Never share passwords or sign-in codes.")),
        (_("Use a standard account for everyday work"), _("Use a standard, non-administrator account for everyday tasks when your computer setup allows it. Approve administrator prompts only when you started the action and understand what it will change. Do not enter your password into an unexpected prompt.")),
        (_("Check sign-in requests before approving"), _("Before entering a password or approving a passkey prompt, check that you opened the expected website or app and that the request matches the action you started. Cancel unexpected prompts and open the service from a bookmark or its known address.")),
        (_("Prepare account recovery"), _("For online accounts, keep recovery details up to date and store any multi-factor backup codes somewhere private and secure. Use the service’s official recovery process; never share recovery codes with someone who contacts you.")),
        (_("Lock the screen when you step away"), _("Press Super+L to lock your session and set a practical automatic lock delay in Settings. Screen locking protects an open session, but it does not encrypt files on a powered-off or lost computer.")),
        (_("Review privacy and sharing settings"), _("Open Privacy & Security in Settings and review app permissions, location access, remote desktop and file sharing. Turn off access you do not use. Panel names vary between Ubuntu releases; ask your administrator before changing a managed computer.")),
        (_("Back up important files"), _("Keep a current backup on a separate drive or trusted backup service, and check that you can restore a file. Disconnect a backup drive when it is not in use, so mistakes or malware cannot immediately affect it. Disk encryption can protect files on a powered-off or lost computer; plan it before installation, and do not try to enable it on an existing system without a verified backup and trusted instructions.")),
        (_("Understand the firewall before changing it"), _("Ubuntu Desktop does not always include a firewall management tool, and UFW may not be installed or enabled. This app checks UFW only; it cannot tell whether another firewall is active. Do not install or enable a firewall blindly: rules can affect remote desktop, SSH, file sharing or printers. Read Ubuntu’s firewall guide or ask your administrator before changing network access.")),
        (_("Treat links and terminal commands with care"), _("Check unexpected messages and download links through a separate trusted route. Do not run commands or installers you do not understand, especially commands that ask for sudo or change security settings.")),
        (_("Spot suspicious messages and sign-in pages"), _("Be cautious of unexpected urgency, payment requests, attachments and links asking you to sign in. Open the service using a bookmark or by typing its known address yourself. Check the address carefully, and never ignore a browser certificate warning to continue.")),
        (_("Use public Wi-Fi carefully"), _("Confirm the network name and sign-in steps with the venue; look-alike hotspots can be misleading. For sensitive tasks, prefer your own mobile hotspot or a VPN from your organization or a provider you trust. A VPN does not make a fake hotspot or sign-in page trustworthy. In Settings, review Sharing and turn off remote desktop or file sharing you do not need.")),
        (_("Check Secure Boot status"), _("Secure Boot can help prevent untrusted boot software from loading. Check its status in the Security section of Network and hardware. If it is off, consult your computer manufacturer or administrator before changing firmware settings; some drivers or managed setups may need extra steps.")),
        (_("If your computer is lost or stolen"), _("From another trusted device, use the official account recovery and device-management services available to you. Change passwords for important accounts, revoke sessions and report a work or school device to its administrator. Disk encryption can help protect data on a powered-off device, but screen locking alone does not encrypt its storage.")),
        (_("If you suspect an account was compromised"), _("From a trusted device, change the affected account password, sign out other sessions and review recovery details and recent sign-ins. Contact your organization's administrator for a work account. If you suspect the Ubuntu computer itself is compromised, disconnect it from networks and seek trusted technical help before entering more passwords.")),
        (_("If you suspect malware or ransomware"), _("Stop using the affected computer for online accounts and disconnect it from Wi-Fi or wired networks if you can do so safely. Do not delete files, run cleanup tools, pay a ransom or connect backup drives. Use a separate trusted device to contact your organization's administrator or a reputable support professional. Restore files only from a known-good backup after the computer has been checked.")),
    ]),
    (_("Magnify part of the screen"), ("settings", "universal-access"), _("Open Accessibility Settings"), [
        (_("Open the Zoom section"), _("In Settings, choose Accessibility, then open Zoom.")),
        (_("Turn on Desktop Zoom"), _("Switch on Desktop Zoom and move the pointer to the screen edge to explore the magnified area.")),
        (_("Tune the magnifier"), _("Adjust magnification and pointer tracking until the view feels comfortable. Turn Zoom off in the same section.")),
    ]),
    (_("Use the screen reader"), ("settings", "universal-access"), _("Open Accessibility Settings"), [
        (_("Open the Seeing section"), _("In Settings, choose Accessibility and look for Screen Reader.")),
        (_("Turn on the screen reader"), _("Enable Orca and follow its welcome prompts. Connect a refreshable Braille display first if you use one.")),
        (_("Learn the keyboard shortcuts"), _("Use Orca’s help and keyboard shortcuts to navigate and adjust speech preferences.")),
    ]),
    (_("Use the on-screen keyboard"), ("settings", "universal-access"), _("Open Accessibility Settings"), [
        (_("Open the Typing section"), _("In Settings, choose Accessibility and open Typing.")),
        (_("Turn on Screen Keyboard"), _("Enable Screen Keyboard to enter text by selecting keys on the screen.")),
        (_("Try it and turn it off when finished"), _("Select a text field to try the keyboard. Return to the same setting to turn it off.")),
    ]),
    (_("Make keyboard input easier"), ("settings", "universal-access"), _("Open Accessibility Settings"), [
        (_("Open the Typing section"), _("In Settings, choose Accessibility and open Typing or Typing Assist.")),
        (_("Try a typing assistance option"), _("Sticky Keys lets you press shortcut keys one at a time. Slow Keys can ignore brief presses, and Bounce Keys can ignore rapid repeated presses.")),
        (_("Adjust one option at a time"), _("Try one option, then type in a text field. Turn it off in the same section if it does not help.")),
    ]),
    (_("Use visual alerts for sound"), ("settings", "universal-access"), _("Open Accessibility Settings"), [
        (_("Open the Hearing section"), _("In Settings, choose Accessibility and open Hearing.")),
        (_("Turn on Visual Alerts"), _("Enable Visual Alerts so the screen flashes when a sound alert occurs.")),
        (_("Choose and test a flash style"), _("Select the whole screen or focused window if those choices are available. Try a sound alert to check that the flash is noticeable.")),
        (_("Turn off alerts if they distract you"), _("Return to the same section to change the flash style or turn Visual Alerts off.")),
    ]),
    (_("Free up disk space safely"), ("overview", "storage"), _("Open storage overview"), [
        (_("Check which filesystem is low"), _("Open Network and hardware and review the available space for the system and home filesystems.")),
        (_("Check available file entries"), _("If you cannot save files even though storage space remains, check the available file entries in Network and hardware. Some filesystems limit file entries, often called inodes, separately from bytes. Ask for help before removing files from system folders.")),
        (_("Review large personal files"), _("In Files, check Downloads, Videos and other folders you recognize. Sort by size when that option is available.")),
        (_("Remove only files you recognize"), _("Move important files to a separate drive or trusted backup before deleting them. Empty the Trash only after checking its contents.")),
        (_("Leave system files alone"), _("Do not delete files from system folders or paste cleanup commands that use sudo. Ask for help if you are unsure what a file does.")),
        (_("Check storage again"), _("Return to the storage overview after cleaning up. If you need space for Ubuntu updates, run Software Updater again when enough space is available.")),
    ]),
    (_("Set up backups"), ("external", "https://help.ubuntu.com/stable/ubuntu-help/backup-why.html.en"), _("Open Ubuntu backup help"), [
        # Keep the guide concise so the action remains visible in the default window.

        (_("Choose what you cannot replace"), _("Focus on personal files that would be difficult to recreate. Use the Backups app if it is available, or copy files you recognize with Files.")),
        (_("Store the backup separately"), _("Choose a separate external drive or trusted online service with enough free space. If you encrypt it, keep the recovery password safe so you can restore your files.")),
        (_("Verify and repeat"), _("Check that the first backup finishes and restore or open a non-critical file. Repeat backups regularly, especially after important changes.")),
    ]),
    (_("Restore files from a backup"), ("app", "deja-dup"), _("Open Backups"), [
        (_("Connect the backup location"), _("Connect the separate drive or make the trusted network location used for your backup available. Do not format or initialize a drive just because Ubuntu asks about it.")),
        (_("Open Backups and choose Restore"), _("Open the Backups app and choose Restore. Select the backup location if asked. If the backup is encrypted, enter its password only in the trusted Backups app; never share it in a support request.")),
        (_("Choose a backup date and files"), _("Select a date from before the files were lost or changed, then choose the files or folders you need. If you are unsure, restore a single non-critical file first.")),
        (_("Restore to a separate folder first"), _("When the app offers a destination, choose a new or temporary folder so restored files do not overwrite current files. Compare the restored copy before moving anything into its original location.")),
        (_("Check the restored files"), _("Open a few restored files and confirm that they contain what you need. Keep the backup until you have checked the restored data and made a fresh backup.")),
    ]),
    (_("Install Ubuntu updates"), ("app", "update-manager"), _("Open Software Updater"), [
        (_("Check for incomplete package installations"), _("On the Network and hardware page, run the package health check to review the local dpkg audit. It lists entries but does not repair them. Review any proposed changes in Software Updater, or ask your administrator. Do not remove packages based only on this report.")),
        (_("Open Software Updater"), _("Ubuntu checks for updates when Software Updater opens. Select Check if it does not start checking.")),
        (_("Review available updates"), _("Read the update summary. Save your work before installing system updates.")),
        (_("Install and restart if asked"), _("Save your work first. Select Install Now and enter your password if prompted. Restart from Ubuntu’s system menu when an update asks you to; this app never restarts the computer.")),
    ]),
    (_("Recover from an interrupted package update"), ("terminal", ""), _("Open Terminal"), [
        (_("Make sure no package operation is running"), _("Check that Software Updater or App Center is not currently installing or updating packages. Save your work and wait for any active operation to finish. Do not remove package-manager lock files.")),
        (_("Finish package configuration"), _("Open Terminal and run sudo dpkg --configure -a to finish configuring packages that were already unpacked. Enter your password only if you expected the sudo prompt. Wait for the prompt to return and read any errors.")),
        (_("Repair broken dependencies"), _("If dpkg finishes without errors but APT still reports broken dependencies, run sudo apt --fix-broken install without -y. Review which packages APT proposes to install, upgrade or remove. Confirm only a plan you understand; type n and press Enter to cancel if anything looks unexpected. Ask your administrator if this is a managed computer.")),
        (_("Check the result"), _("Open Software Updater again or rerun Ubuntu Start’s package health check. If the error remains, note its exact text and ask for help. Do not delete lock files or remove packages named only in an error.")),
    ]),
    (_("Plan an Ubuntu version upgrade"), ("external", "https://ubuntu.com/desktop/docs/en/latest/how-to/upgrade-ubuntu-desktop/"), _("Open Ubuntu’s upgrade guide"), [
        (_("Find your current Ubuntu version"), _("Open Settings and choose System, then About. On older Ubuntu releases, version details may be under Details. You can also see the version in Ubuntu Start’s system details.")),
        (_("Check the support period"), _("LTS releases receive five years of standard security maintenance. Interim releases are supported for nine months. Ubuntu Pro can extend security coverage for eligible LTS systems. Check the official release lifecycle for your version.")),
        (_("Prepare before upgrading"), _("Back up important files, connect a laptop to power and make sure several gigabytes of disk space are available. Install current updates and restart if Ubuntu asks.")),
        (_("Follow Ubuntu’s supported upgrade path"), _("Open Software Updater and follow its release upgrade prompt. Read the release notes and review each prompt. Ubuntu supports upgrades between consecutive LTS releases or consecutive interim releases; an older system may need more than one upgrade.")),
        (_("If no upgrade is offered"), _("An upgrade may not be offered immediately. LTS upgrades can wait for the first point release, and interim upgrades may appear several days after release. Check the official guide or ask your administrator on a managed computer. Do not force a development release.")),
    ]),
    (_("Install a desktop application"), ("app-center", ""), _("Open Ubuntu App Center"), [
        (_("Search for the app name"), _("Enter the app’s exact name in the App Center search box. Check that the result is the app you intended.")),
        (_("Review the publisher and source"), _("Check who publishes the app, where it comes from and which permissions it requests. Follow your organization’s software policy on managed computers.")),
        (_("Install when you are ready"), _("Select Install only after reviewing the details. Ubuntu may ask you to confirm with your password.")),
        (_("Keep apps up to date"), _("Use the App Center’s Updates section to review available app updates. Save your work before updating.")),
    ]),
    (_("Use the Terminal"), ("terminal", ""), _("Open Terminal"), [
        (_("What the prompt means"), _("The prompt is the text before the cursor. It shows that the terminal is ready for a command. Type after it; do not type the prompt itself.")),
        (_("Run a command"), _("Type a command and press Enter to run it. For example, pwd shows the current folder and ls lists its files. These commands only show information.")),
        (_("Read the result"), _("Commands may print information or an error message. Read the last lines first. If a command finishes without an error, it may return to the prompt without printing anything.")),
        (_("Copy and paste safely"), _("Copy text with Ctrl+Shift+C and paste with Ctrl+Shift+V. Before pasting a command, read all of it: some terminals can run multiple pasted lines, and commands may change or delete files.")),
        (_("Move between folders"), _("Use cd Documents to enter a folder and cd .. to go up one level. Use pwd to check where you are.")),
        (_("Use Tab and command history"), _("Press Tab to complete a file or folder name when it is unique. Press the Up Arrow to find a command you used earlier; check it before pressing Enter.")),
        (_("Search command history"), _("Press Ctrl+R and type part of an earlier command to search shell history. Press Ctrl+R again to cycle through older matches. Press Esc to put the selected command back at the prompt and review it; press Enter only if you intend to run it. Do not put passwords or access tokens directly in commands, because shell history may save them.")),
        (_("Clear the terminal view"), _("Press Ctrl+L to clear the text currently shown in the terminal. This does not delete files or command history.")),
        (_("Type paths with spaces"), _("Put quotation marks around a folder or file name that contains spaces, for example: cd \"My Documents\". You can also type the first letters and press Tab to complete the name.")),
        (_("Ask a command for help"), _("Try a command followed by --help, such as ls --help. For more detail, use man followed by the command name; press q to leave the manual.")),
        (_("Understand sudo"), _("sudo runs a command with administrator privileges. Use it only when you understand and trust the command. Your password is not shown while you type it.")),
        (_("Enter a password at a prompt"), _("When sudo or another trusted tool asks for your password, typing may show no letters or dots. Type it only if you expected the prompt and trust the command, then press Enter. Press Ctrl+C if the prompt is unexpected; never share your password.")),
        (_("Wait for a command to finish"), _("While a command is working, the prompt may not appear. Wait for it to return before typing another command. Some commands take time. Ctrl+C asks a command to stop but cannot undo changes already made; do not close the terminal during system updates or file operations.")),
        (_("Stop a running command"), _("Ctrl+C asks the current command to stop. It does not undo changes the command has already made.")),
        (_("Keep commands from trusted sources"), _("Do not paste commands you do not understand, especially commands using sudo, rm, disk tools or scripts downloaded from the internet.")),
    ]),
]

class UbuntuStart(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.connect("activate", self.on_activate)

    def on_activate(self, app):
        windows = app.get_windows()
        if windows:
            windows[0].present()
            return
        win = Adw.ApplicationWindow(application=app, title=_("Ubuntu Start"), default_width=900, default_height=620)
        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        about_button = Gtk.Button(label=_("About"))
        about_button.connect("clicked", lambda *_: self.show_about())
        header.pack_end(about_button)
        toolbar.add_top_bar(header)
        split = Adw.NavigationSplitView()
        sidebar = Adw.NavigationPage(title=_("Guide"))
        content = Adw.NavigationPage(title=_("Ubuntu Start"))
        stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        self.main_stack = stack
        nav = Gtk.StackSidebar(stack=stack)
        nav.set_margin_top(12)
        nav.set_margin_bottom(12)
        nav.set_margin_start(8)
        nav.set_margin_end(8)
        nav.set_hexpand(True)
        nav.set_vexpand(True)
        stack.set_vexpand(True)
        stack.set_hexpand(True)
        stack.set_margin_top(24)
        stack.set_margin_bottom(24)
        stack.set_margin_start(28)
        stack.set_margin_end(28)
        sidebar_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        sidebar_box.set_size_request(230, -1)
        sidebar_box.append(nav)
        sidebar.set_child(sidebar_box)
        content.set_child(stack)
        split.set_sidebar(sidebar)
        split.set_content(content)
        toolbar.set_content(split)
        win.set_content(toolbar)

        first_page_name = _("Welcome")
        first_page = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
        first_page.set_child(self.make_welcome())
        stack.add_titled(first_page, first_page_name, first_page_name)
        stack.set_visible_child_name(first_page_name)
        key_controller = Gtk.EventControllerKey()
        key_controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        key_controller.connect("key-pressed", self.on_key_pressed)
        win.add_controller(key_controller)
        win.present()

        remaining_pages = [
            (_("Get started"), self.make_get_started),
            (_("Tips and tricks"), self.make_tips_page),
            (_("Fix a device"), self.make_device_page),
            (_("System guides"), self.make_system_guides),
            (_("Network and hardware"), self.make_network_hardware),
            (_("Drivers"), self.make_drivers),
            (_("Help and support"), self.make_help),
        ]
        GLib.idle_add(self.add_next_page, stack, remaining_pages)

    def add_next_page(self, stack, remaining_pages):
        """Populate one guide page per idle callback after the window is shown."""
        if not remaining_pages:
            return GLib.SOURCE_REMOVE
        name, builder = remaining_pages.pop(0)
        scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
        scroller.set_child(builder())
        stack.add_titled(scroller, name, name)
        if name == _("Fix a device") and getattr(self, "_pending_device_search_focus", False):
            stack.set_visible_child_name(name)
            self.device_search.grab_focus()
            self._pending_device_search_focus = False
        return GLib.SOURCE_CONTINUE if remaining_pages else GLib.SOURCE_REMOVE

    def on_key_pressed(self, _controller, keyval, _keycode, state):
        if keyval == Gdk.KEY_f and state & Gdk.ModifierType.CONTROL_MASK:
            if hasattr(self, "device_search"):
                self.main_stack.set_visible_child_name(_("Fix a device"))
                self.device_search.grab_focus()
            else:
                self._pending_device_search_focus = True
            return True
        return False

    def page(self, title, subtitle=None, include_rows=True):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        heading = Gtk.Label(label=title, xalign=0, wrap=True, css_classes=["title-1"])
        box.append(heading)
        if subtitle:
            box.append(Gtk.Label(label=subtitle, xalign=0, wrap=True, css_classes=["body"]))
        rows = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE, css_classes=["boxed-list"])
        if include_rows:
            box.append(rows)
        return box, rows

    def row(self, parent, title, subtitle, action_label=None, callback=None):
        row = Adw.ActionRow(
            title=GLib.markup_escape_text(str(title)),
            subtitle=GLib.markup_escape_text(str(subtitle)),
        )
        if action_label and callback:
            button = Gtk.Button(label=action_label, valign=Gtk.Align.CENTER)
            button.connect("clicked", lambda *_: callback())
            row.add_suffix(button)
        if isinstance(parent, Adw.PreferencesGroup):
            parent.add(row)
        else:
            parent.append(row)

    def make_welcome(self):
        box, rows = self.page(_("A calmer start with Ubuntu"), _("Set up the essentials, then find clear steps when a device does not work."))
        self.row(rows, _("Your computer, at a glance"), _("Use Settings to check your Ubuntu version, storage and connected devices."), _("Open Settings"), lambda: self.open_app("gnome-control-center"))
        self.row(rows, _("Take it one step at a time"), _("You can come back to any guide whenever you need it."))
        return box

    def make_get_started(self):
        box, _rows = self.page(
            _("Get started"),
            _("Work through these steps at your own pace. Your checklist is saved privately on this computer."),
            include_rows=False,
        )
        tasks = FIRST_RUN_TASKS
        self.first_run_completed = load_completed_tasks() & FIRST_RUN_TASK_IDS
        self.first_run_tasks = tasks
        self.first_run_checks = {}
        self.first_run_progress = Gtk.Label(xalign=0, wrap=True)
        self.first_run_save_status = Gtk.Label(xalign=0, wrap=True)
        checklist_rows = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE, css_classes=["boxed-list"])
        box.append(self.first_run_progress)
        box.append(checklist_rows)
        for task_id, title, subtitle, target in tasks:
            row = Gtk.ListBoxRow()
            task_content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            task_description = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            check = Gtk.CheckButton(
                label=title, active=task_id in self.first_run_completed,
                valign=Gtk.Align.CENTER, hexpand=True,
            )
            check.update_property(
                [Gtk.AccessibleProperty.LABEL, Gtk.AccessibleProperty.DESCRIPTION],
                [title, subtitle],
            )
            handler_id = check.connect("toggled", self.on_first_run_task_toggled, task_id)
            self.first_run_checks[task_id] = (check, handler_id)
            subtitle_label = Gtk.Label(
                label=subtitle, xalign=0, wrap=True, css_classes=["dim-label"],
            )
            task_description.append(check)
            task_description.append(subtitle_label)
            task_description.set_hexpand(True)
            task_content.append(task_description)
            button_label = (
                _("Open Software Updater")
                if target == ("app", "update-manager") else _("Open Settings")
            )
            if target[0] == "guide":
                button_label = (
                    _("Open the backup setup guide")
                    if target[1] == "Set up backups"
                    else _("Open the everyday security guide")
                )
            button = Gtk.Button(label=button_label, valign=Gtk.Align.CENTER)
            button.connect("clicked", lambda *_args, selected=target: self.open_target(selected))
            task_content.append(button)
            task_content.set_margin_start(12)
            task_content.set_margin_end(12)
            task_content.set_margin_top(8)
            task_content.set_margin_bottom(8)
            row.set_child(task_content)
            checklist_rows.append(row)
        self.update_first_run_progress()
        box.append(self.first_run_save_status)
        reset_checklist = Gtk.Button(label=_("Reset checklist"), halign=Gtk.Align.START)
        reset_checklist.connect("clicked", self.reset_first_run_checklist)
        box.append(reset_checklist)
        accessibility_box, _accessibility_rows = self.page(
            _("Accessibility status"),
            _("Read selected GNOME accessibility settings. Ubuntu Start does not change them."),
            include_rows=False,
        )
        self.accessibility_box = accessibility_box
        accessibility_status = Gtk.Label(label="", xalign=0, wrap=True)
        accessibility_rows = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE, css_classes=["boxed-list"])
        accessibility_settings = Gtk.Button(label=_("Open Accessibility Settings"), halign=Gtk.Align.START)
        accessibility_settings.connect(
            "clicked", lambda *_: self.open_target(("settings", "universal-access")),
        )
        accessibility_refresh = Gtk.Button(label=_("Refresh accessibility status"), halign=Gtk.Align.START)
        accessibility_refresh.connect(
            "clicked",
            lambda *_: self.refresh_accessibility_status(
                accessibility_refresh, accessibility_status, accessibility_rows, announce=True,
            ),
        )
        accessibility_box.append(accessibility_settings)
        accessibility_box.append(accessibility_refresh)
        accessibility_box.append(accessibility_status)
        accessibility_box.append(accessibility_rows)
        box.append(accessibility_box)
        self.refresh_accessibility_status(accessibility_refresh, accessibility_status, accessibility_rows)
        time_box, _time_rows = self.page(
            _("Date and time status"),
            _("Read the local time zone, whether automatic time synchronization is supported and enabled, and whether the clock is synchronized. The app suggests what to check but does not change settings or start synchronization."),
            include_rows=False,
        )
        time_status = Gtk.Label(label="", xalign=0, wrap=True)
        time_rows = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE, css_classes=["boxed-list"])
        time_refresh = Gtk.Button(label=_("Refresh date and time status"), halign=Gtk.Align.START)
        time_guide_button = Gtk.Button(label=_("Open date and time guide"), halign=Gtk.Align.START)
        time_refresh.connect(
            "clicked",
            lambda *_: self.refresh_time_status(time_refresh, time_status, time_rows, announce=True),
        )
        time_guide_button.connect("clicked", lambda *_: self.open_time_guide())
        time_box.append(time_refresh)
        time_box.append(time_guide_button)
        time_box.append(time_status)
        time_box.append(time_rows)
        box.append(time_box)
        self.refresh_time_status(time_refresh, time_status, time_rows)
        return box

    def update_first_run_progress(self, announce=False):
        completed = len(self.first_run_completed)
        total = len(self.first_run_tasks)
        message = _("Setup progress: {completed} of {total} steps complete.").format(
            completed=completed, total=total,
        )
        self.first_run_progress.set_text(message)
        if announce:
            self.announce_to_screen_reader(self.first_run_progress, message)

    def on_first_run_task_toggled(self, check, task_id):
        if check.get_active():
            self.first_run_completed.add(task_id)
        else:
            self.first_run_completed.discard(task_id)
        if save_completed_tasks(self.first_run_completed):
            self.first_run_save_status.set_text(_("Progress saved on this computer."))
        else:
            self.first_run_save_status.set_text(
                _("Progress could not be saved. It will remain until you close the app."),
            )
        self.update_first_run_progress(announce=True)

    def reset_first_run_checklist(self, _button=None):
        if not save_completed_tasks(set()):
            self.first_run_save_status.set_text(
                _("Progress could not be saved. It will remain until you close the app."),
            )
            return
        self.first_run_completed.clear()
        for check, handler_id in self.first_run_checks.values():
            check.handler_block(handler_id)
            check.set_active(False)
            check.handler_unblock(handler_id)
        self.first_run_save_status.set_text(_("Checklist reset. Progress is saved on this computer."))
        self.update_first_run_progress(announce=True)

    def open_target(self, target):
        kind, value = target
        if kind == "settings":
            arguments = value if isinstance(value, (tuple, list)) else (value,)
            self.open_app("gnome-control-center", *arguments)
        elif kind == "terminal":
            self.open_terminal()
        elif kind == "app-center":
            self.confirm_app_center()
        elif kind == "guide":
            self.open_system_guide(value)
        elif kind == "external":
            self.confirm_external_link(
                value,
                _("Open Ubuntu help?"),
                _("This opens Ubuntu Desktop documentation in your browser. The website will receive a normal web request and can see your IP address."),
            )
        elif kind == "overview" and value == "storage":
            self.main_stack.set_visible_child_name(_("Network and hardware"))
            GLib.timeout_add(50, self.scroll_to_storage_overview)
        elif kind == "overview" and value == "printer":
            self.main_stack.set_visible_child_name(_("Network and hardware"))
            GLib.timeout_add(50, self.scroll_to_printer_status)
        elif kind == "overview" and value == "network-diagnostics":
            self.main_stack.set_visible_child_name(_("Network and hardware"))
            GLib.timeout_add(50, self.scroll_to_network_diagnostics)
        elif kind == "overview" and value == "startup-time":
            self.main_stack.set_visible_child_name(_("Network and hardware"))
            GLib.timeout_add(50, self.scroll_to_startup_time)
        else:
            self.open_app(value)

    def scroll_to_storage_overview(self):
        scroller = self.main_stack.get_visible_child()
        if scroller and self.storage_box.get_mapped():
            found, bounds = self.storage_box.compute_bounds(scroller.get_child())
            if found:
                adjustment = scroller.get_vadjustment()
                adjustment.set_value(bounds.get_y())
        return GLib.SOURCE_REMOVE

    def scroll_to_printer_status(self):
        scroller = self.main_stack.get_visible_child()
        if scroller and self.printer_box.get_mapped():
            found, bounds = self.printer_box.compute_bounds(scroller.get_child())
            if found:
                adjustment = scroller.get_vadjustment()
                adjustment.set_value(bounds.get_y())
        return GLib.SOURCE_REMOVE

    def scroll_to_network_diagnostics(self):
        scroller = self.main_stack.get_visible_child()
        if scroller and self.network_diagnostics_box.get_mapped():
            found, bounds = self.network_diagnostics_box.compute_bounds(scroller.get_child())
            if found:
                scroller.get_vadjustment().set_value(bounds.get_y())
        return GLib.SOURCE_REMOVE

    def scroll_to_startup_time(self):
        scroller = self.main_stack.get_visible_child()
        if scroller and self.startup_time_box.get_mapped():
            found, bounds = self.startup_time_box.compute_bounds(scroller.get_child())
            if found:
                adjustment = scroller.get_vadjustment()
                adjustment.set_value(bounds.get_y())
        return GLib.SOURCE_REMOVE

    def confirm_app_center(self):
        dialog = Adw.AlertDialog(
            heading=_("Open Ubuntu App Center?"),
            body=_("The App Center may contact your configured software sources to show apps and updates. Ubuntu Start will not install anything. You can review app details and choose whether to install in the App Center."),
        )
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("open", _("Open App Center"))
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")

        def on_response(_dialog, response):
            if response != "open":
                return
            for executable in ("snap-store", "ubuntu-app-center", "gnome-software"):
                if shutil.which(executable):
                    self.open_app(executable)
                    return
            self.show_error(_("No supported software center was found."))

        dialog.connect("response", on_response)
        dialog.present(self.get_active_window())

    def open_terminal(self):
        for executable in ("ptyxis", "kgx", "gnome-terminal", "x-terminal-emulator"):
            if shutil.which(executable):
                self.open_app(executable)
                return
        self.show_error(_("No supported terminal application was found."))

    def make_device_page(self):
        box, _rows = self.page(
            _("Fix a device"),
            _("Choose a device or search all guides for a symptom. These checks do not install software or change system files."),
            include_rows=False,
        )
        search = Gtk.SearchEntry(placeholder_text=_("Search all guides and steps"))
        search.set_tooltip_text(_("Press Ctrl+F to search guides and troubleshooting steps."))
        self.device_search = search
        search_label = Gtk.Label(label=_("Search all guides and steps"), xalign=0)
        search_label.set_mnemonic_widget(search)
        box.append(search_label)
        box.append(search)
        browse = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        chooser = Gtk.DropDown.new_from_strings([title for title, _panel, _steps in GUIDES])
        self.device_chooser = chooser
        chooser_label = Gtk.Label(label=_("Choose a device"), xalign=0)
        chooser_label.set_mnemonic_widget(chooser)
        browse.append(chooser_label)
        browse.append(chooser)
        steps_stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        for index, (_title, _panel, steps) in enumerate(GUIDES):
            group = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            group.append(Gtk.Label(label=_("Suggested checks"), xalign=0, css_classes=["title-3"]))
            rows = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE, css_classes=["boxed-list"])
            for step_title, description in steps:
                rows.append(Adw.ActionRow(title=step_title, subtitle=description))
            if _panel == "wifi":
                analyzer = Adw.ActionRow(
                    title=_("WiFi Analyzer"),
                    subtitle=_("See nearby Wi-Fi signal levels and channel use to investigate weak signal or crowded channels."),
                )
                analyzer_button = Gtk.Button(label=_("View on GitHub"), valign=Gtk.Align.CENTER)
                analyzer_button.connect("clicked", lambda *_: self.confirm_external_link(
                    "https://github.com/yeager/wifi-analyzer",
                    _("Open WiFi Analyzer on GitHub?"),
                    _("This opens the project page in your browser. GitHub will receive a normal web request and can see your IP address."),
                ))
                analyzer.add_suffix(analyzer_button)
                rows.append(analyzer)
            group.append(rows)
            steps_stack.add_named(group, f"guide-{index}")
        browse.append(steps_stack)
        box.append(browse)

        results = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        result_rows = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE, css_classes=["boxed-list"])
        results.append(result_rows)
        no_results = Gtk.Label(label=_("No matching steps. Try another word."), xalign=0, wrap=True)
        results.append(no_results)
        results.set_visible(False)
        box.append(results)

        search_entries = []
        for guide_index, (guide_title, _panel, steps) in enumerate(GUIDES):
            search_entries.extend(
                ("device", guide_index, guide_title, step_title, description)
                for step_title, description in steps
            )
        for guide_index, (guide_title, _target, _action, steps) in enumerate(SYSTEM_GUIDES):
            search_title = (
                _("Security and privacy guide")
                if guide_title == _("Improve everyday security") else guide_title
            )
            search_entries.extend(
                ("system", guide_index, search_title, step_title, description)
                for step_title, description in steps
            )

        open_button = Gtk.Button(label=_("Open related Settings"), halign=Gtk.Align.START)
        browse.append(open_button)

        def update_guide(*_args):
            selected = chooser.get_selected()
            if selected < len(GUIDES):
                steps_stack.set_visible_child_name(f"guide-{selected}")
                target = GUIDES[selected][1]
                if target == "hardware":
                    label = _("Open hardware overview")
                elif target == "disks":
                    label = _("Open Disks")
                elif target == "system":
                    label = _("Open System Settings")
                else:
                    label = _("Open related Settings")
                open_button.set_label(label)

        def update_search(*_args):
            query = search.get_text().strip().casefold()
            browse.set_visible(not query)
            results.set_visible(bool(query))
            while (child := result_rows.get_first_child()) is not None:
                result_rows.remove(child)
            if not query:
                return
            matches = find_guide_matches(query, search_entries)
            for kind, guide_index, guide_title, step_title, description in matches:
                row = Adw.ActionRow(title=f"{guide_title}: {step_title}", subtitle=description)
                button = Gtk.Button(label=_("Show this guide"), valign=Gtk.Align.CENTER)
                button.connect(
                    "clicked",
                    lambda *_args, k=kind, i=guide_index: self.open_search_result(search, k, i),
                )
                row.add_suffix(button)
                result_rows.append(row)
            no_results.set_visible(not matches)

        chooser.connect("notify::selected", update_guide)
        search.connect("changed", update_search)
        update_guide()
        open_button.connect(
            "clicked",
            lambda *_: self.open_device_target(GUIDES[chooser.get_selected()][1]),
        )
        return box

    def open_device_target(self, target):
        if target == "hardware":
            self.main_stack.set_visible_child_name(_("Network and hardware"))
        elif target == "disks":
            self.open_app("gnome-disks")
        else:
            self.open_app("gnome-control-center", target)

    def make_system_guides(self):
        box, _rows = self.page(
            _("System guides"),
            _("Follow clear steps for common Ubuntu tasks. Open the related system tool when you are ready to make a change."),
            include_rows=False,
        )
        chooser = Gtk.DropDown.new_from_strings([title for title, _target, _action, _steps in SYSTEM_GUIDES])
        self.system_guide_chooser = chooser
        guide_label = Gtk.Label(label=_("Choose a system guide"), xalign=0)
        guide_label.set_mnemonic_widget(chooser)
        box.append(guide_label)
        box.append(chooser)
        guide_stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        for index, (title, target, action, steps) in enumerate(SYSTEM_GUIDES):
            guide_box, rows = self.page(title)
            for step_title, description in steps:
                self.row(rows, step_title, description)
            open_button = Gtk.Button(label=action, halign=Gtk.Align.START)
            open_button.connect("clicked", lambda *_args, t=target: self.open_target(t))
            guide_box.append(open_button)
            if title == _("Improve everyday security"):
                privacy_button = Gtk.Button(
                    label=_("Review privacy and sharing settings"),
                    halign=Gtk.Align.START,
                )
                privacy_button.connect(
                    "clicked", lambda *_: self.open_target(("settings", "privacy")),
                )
                guide_box.append(privacy_button)
                updates_button = Gtk.Button(
                    label=_("Check automatic update setup"), halign=Gtk.Align.START,
                )
                updates_button.connect("clicked", lambda *_: self.open_automatic_updates_status())
                guide_box.append(updates_button)
                firewall_button = Gtk.Button(
                    label=_("Check firewall status"), halign=Gtk.Align.START,
                )
                firewall_button.connect("clicked", lambda *_: self.open_firewall_status())
                guide_box.append(firewall_button)
                encryption_button = Gtk.Button(
                    label=_("Check root filesystem encryption"), halign=Gtk.Align.START,
                )
                encryption_button.connect(
                    "clicked", lambda *_: self.open_root_encryption_status(),
                )
                guide_box.append(encryption_button)
                secure_boot_button = Gtk.Button(
                    label=_("Check Secure Boot status"), halign=Gtk.Align.START,
                )
                secure_boot_button.connect(
                    "clicked", lambda *_: self.open_secure_boot_status(),
                )
                guide_box.append(secure_boot_button)
                security_help_button = Gtk.Button(
                    label=_("Open security documentation"),
                    halign=Gtk.Align.START,
                )
                security_help_button.connect(
                    "clicked", lambda *_args: self.open_security_documentation(),
                )
                guide_box.append(security_help_button)
            guide_stack.add_named(guide_box, f"system-guide-{index}")
        box.append(guide_stack)

        def select_guide(*_args):
            selected = chooser.get_selected()
            if selected < len(SYSTEM_GUIDES):
                guide_stack.set_visible_child_name(f"system-guide-{selected}")

        chooser.connect("notify::selected", select_guide)
        select_guide()
        return box

    def open_search_result(self, search, kind, guide_index):
        if kind == "device":
            self.main_stack.set_visible_child_name(_("Fix a device"))
            self.device_chooser.set_selected(guide_index)
        else:
            self.main_stack.set_visible_child_name(_("System guides"))
            self.system_guide_chooser.set_selected(guide_index)
        search.set_text("")

    def make_network_hardware(self):
        box, _rows = self.page(
            _("Network and hardware"),
            _("Most information comes from this computer. Network and internet checks ask before contacting the configured DNS resolver or an internet site."),
            include_rows=False,
        )

        network_box, _unused = self.page(
            _("Network status"),
            _("NetworkManager device states help show whether Ubuntu sees a wired or wireless adapter. The app also reads the local adapter name, hardware ID and kernel driver when exposed. If the optional iw tool is installed, signal strength and link rates are read from the active Wi-Fi link; the network name is not collected and nearby networks are not scanned. Signal values closer to 0 dBm are usually stronger. Link rates are not internet speed tests."),
            include_rows=False,
        )
        network_status = Gtk.Label(label=_("Network status has not been refreshed yet."), xalign=0, wrap=True)
        network_rows = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE, css_classes=["boxed-list"])
        refresh_button = Gtk.Button(label=_("Refresh network status"), halign=Gtk.Align.START)
        refresh_button.connect("clicked", lambda *_: self.refresh_network_status(network_status, network_rows, announce=True))
        network_box.append(refresh_button)
        network_box.append(network_status)
        network_box.append(network_rows)
        box.append(network_box)
        self.refresh_network_status(network_status, network_rows)

        firewall_box, _firewall_rows = self.page(
            _("Firewall status"),
            _("Read the overall local UFW status only. This check does not show firewall rules, contact the network or change settings."),
            include_rows=False,
        )
        self.firewall_status_row = Adw.ActionRow(
            title=_("UFW firewall"), subtitle=_("Not checked yet."),
        )
        firewall_box.append(self.firewall_status_row)
        self.firewall_refresh_button = Gtk.Button(
            label=_("Check firewall status"), halign=Gtk.Align.START,
        )
        self.firewall_refresh_button.connect(
            "clicked",
            lambda *_: self.refresh_firewall_status(
                self.firewall_refresh_button, self.firewall_status_row, announce=True,
            ),
        )
        firewall_box.append(self.firewall_refresh_button)
        firewall_box.append(Gtk.Label(
            label=_("An inactive firewall is not automatically a problem. Before changing firewall settings, check whether you use remote desktop, SSH, file sharing, printers or a managed network."),
            xalign=0, wrap=True, css_classes=["body"],
        ))
        box.append(firewall_box)
        self.refresh_firewall_status(self.firewall_refresh_button, self.firewall_status_row)

        wifi_check_box, _wifi_check_rows = self.page(
            _("Wi-Fi quick check"),
            _("Combine local connection, radio-block and IP-address status to suggest a next step. This check does not contact the internet or scan nearby networks."),
            include_rows=False,
        )
        wifi_check_status = Gtk.Label(label=_("Wi-Fi check has not been run yet."), xalign=0, wrap=True)
        wifi_check_button = Gtk.Button(label=_("Check Wi-Fi connection"), halign=Gtk.Align.START)
        wifi_check_button.connect(
            "clicked",
            lambda *_: self.refresh_wifi_quick_check(wifi_check_button, wifi_check_status, announce=True),
        )
        wifi_settings_button = Gtk.Button(label=_("Open Wi-Fi Settings"), halign=Gtk.Align.START)
        wifi_settings_button.connect("clicked", lambda *_: self.open_wifi_settings())
        wifi_guide_button = Gtk.Button(label=_("Open Wi-Fi troubleshooting guide"), halign=Gtk.Align.START)
        wifi_guide_button.connect("clicked", lambda *_: self.open_wifi_guide())
        wifi_check_box.append(wifi_check_button)
        wifi_check_box.append(wifi_settings_button)
        wifi_check_box.append(wifi_guide_button)
        wifi_check_box.append(wifi_check_status)
        box.append(wifi_check_box)

        radio_box, _radio_unused = self.page(
            _("Wireless radio status"),
            _("Read local Linux radio block flags for Wi-Fi, Bluetooth and other wireless devices. This does not enable or disable radios."),
            include_rows=False,
        )
        radio_status = Gtk.Label(label=_("Radio status has not been refreshed yet."), xalign=0, wrap=True)
        radio_rows = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE, css_classes=["boxed-list"])
        radio_refresh = Gtk.Button(label=_("Refresh radio status"), halign=Gtk.Align.START)
        radio_refresh.connect(
            "clicked",
            lambda *_: self.refresh_rfkill_status(
                radio_refresh, radio_status, radio_rows, announce=True,
            ),
        )
        radio_guide_button = Gtk.Button(
            label=_("Open Wi-Fi troubleshooting guide"), halign=Gtk.Align.START,
        )
        radio_guide_button.connect("clicked", lambda *_: self.open_wifi_guide())
        radio_box.append(radio_refresh)
        radio_box.append(radio_guide_button)
        radio_box.append(radio_status)
        radio_box.append(radio_rows)
        box.append(radio_box)
        self.refresh_rfkill_status(radio_refresh, radio_status, radio_rows)

        security_box, _security_rows = self.page(
            _("Storage encryption status"),
            _("Read the block-device paths used by the root filesystem. This check does not inspect every file or other mounted disk, and it does not change storage settings."),
            include_rows=False,
        )
        self.root_encryption_row = Adw.ActionRow(
            title=_("Root filesystem encryption"), subtitle=_("Not checked yet."),
        )
        security_box.append(self.root_encryption_row)
        self.root_encryption_refresh_button = Gtk.Button(
            label=_("Check root filesystem encryption"), halign=Gtk.Align.START,
        )
        self.root_encryption_refresh_button.connect(
            "clicked",
            lambda *_: self.refresh_root_encryption_status(
                self.root_encryption_refresh_button, self.root_encryption_row, announce=True,
            ),
        )
        security_box.append(self.root_encryption_refresh_button)
        security_box.append(Gtk.Label(
            label=_("This read-only check uses lsblk when available. It cannot confirm that all personal files or other disks are encrypted."),
            xalign=0, wrap=True, css_classes=["body"],
        ))
        box.append(security_box)
        self.refresh_root_encryption_status(
            self.root_encryption_refresh_button, self.root_encryption_row,
        )

        bluetooth_box, bluetooth_rows = self.page(
            _("Bluetooth status"),
            _("Read the local controller power state only. Ubuntu Start does not scan for nearby devices."),
        )
        bluetooth_status = Adw.ActionRow(title=_("Bluetooth controller"), subtitle=_("Checking status…"))
        bluetooth_rows.append(bluetooth_status)
        bluetooth_refresh = Gtk.Button(label=_("Refresh Bluetooth status"), halign=Gtk.Align.START)
        bluetooth_refresh.connect("clicked", lambda *_: self.refresh_bluetooth_status(bluetooth_status, announce=True))
        bluetooth_guide_button = Gtk.Button(label=_("Open Bluetooth pairing guide"), halign=Gtk.Align.START)
        bluetooth_guide_button.connect("clicked", lambda *_: self.open_bluetooth_guide())
        bluetooth_box.append(bluetooth_refresh)
        bluetooth_box.append(bluetooth_guide_button)
        box.append(bluetooth_box)
        self.refresh_bluetooth_status(bluetooth_status)

        audio_box, audio_rows = self.page(
            _("Audio status"),
            _("Read the default speaker and microphone names, volume and mute state when available. This check does not play sound or change settings."),
        )
        output_status = Adw.ActionRow(title=_("Speaker output"), subtitle=_("Checking status…"))
        input_status = Adw.ActionRow(title=_("Microphone input"), subtitle=_("Checking status…"))
        audio_rows.append(output_status)
        audio_rows.append(input_status)
        audio_refresh = Gtk.Button(label=_("Refresh audio status"), halign=Gtk.Align.START)
        audio_refresh.connect("clicked", lambda *_: self.refresh_audio_status(output_status, input_status, announce=True))
        audio_settings_button = Gtk.Button(label=_("Open Sound Settings"), halign=Gtk.Align.START)
        audio_settings_button.connect("clicked", lambda *_: self.open_sound_settings())
        audio_guide_button = Gtk.Button(
            label=_("Open sound and microphone guide"), halign=Gtk.Align.START,
        )
        audio_guide_button.connect("clicked", lambda *_: self.open_sound_guide())
        bluetooth_audio_guide_button = Gtk.Button(
            label=_("Open Bluetooth audio guide"), halign=Gtk.Align.START,
        )
        bluetooth_audio_guide_button.connect("clicked", lambda *_: self.open_bluetooth_audio_guide())
        audio_box.append(audio_refresh)
        audio_box.append(audio_settings_button)
        audio_box.append(audio_guide_button)
        audio_box.append(bluetooth_audio_guide_button)
        box.append(audio_box)
        self.refresh_audio_status(output_status, input_status)

        printer_box, _printer_rows = self.page(
            _("Printer queue status"),
            _("Read printer queues from the local printing service. This does not send a print job or contact a printer directly."),
            include_rows=False,
        )
        self.printer_box = printer_box
        printer_status = Gtk.Label(label="", xalign=0, wrap=True)
        printer_rows = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE, css_classes=["boxed-list"])
        printer_refresh = Gtk.Button(label=_("Refresh printer status"), halign=Gtk.Align.START)
        printer_refresh.connect(
            "clicked",
            lambda *_: self.refresh_printer_status(
                printer_refresh, printer_status, printer_rows, announce=True,
            ),
        )
        self.add_printer_controls(printer_box, printer_refresh, printer_status)

        printer_box.append(printer_rows)
        box.append(printer_box)
        self.refresh_printer_status(printer_refresh, printer_status, printer_rows)

        diagnostic_box, _diagnostic_rows = self.page(
            _("Connection quality"),
            _("The test looks up ubuntu.com using your configured DNS, pings your local gateway once, and reads its MAC address from the local neighbor table. DNS queries may be visible to your configured DNS provider; no diagnostic report is uploaded."),
            include_rows=False,
        )
        self.network_diagnostics_box = diagnostic_box
        diagnostic_status = Gtk.Label(label="", xalign=0, wrap=True)
        self.last_network_diagnostics = None
        diagnostic_button = Gtk.Button(label=_("Test DNS and gateway"), halign=Gtk.Align.START)
        diagnostic_button.connect("clicked", lambda *_: self.confirm_network_diagnostics(diagnostic_button, diagnostic_status))
        diagnostic_box.append(diagnostic_button)
        diagnostic_box.append(diagnostic_status)
        network_settings_button = Gtk.Button(
            label=_("Open Network Settings"), halign=Gtk.Align.START,
        )
        network_settings_button.connect(
            "clicked", lambda *_: self.open_target(("settings", "network")),
        )
        diagnostic_box.append(network_settings_button)
        box.append(diagnostic_box)

        internet_box, _internet_rows = self.page(
            _("Internet connection test"),
            _("This optional test sends a small HTTPS request to ubuntu.com. It shares your IP address with that site, as any web request does; no diagnostic details are sent."),
            include_rows=False,
        )
        internet_status = Gtk.Label(label="", xalign=0, wrap=True)
        internet_button = Gtk.Button(label=_("Test internet connection"), halign=Gtk.Align.START)
        internet_button.connect("clicked", lambda *_: self.confirm_internet_test(internet_button, internet_status))
        internet_box.append(internet_button)
        internet_box.append(internet_status)
        box.append(internet_box)

        updates_box, _updates_rows = self.page(
            _("Ubuntu update status"),
            _("Simulate an upgrade using local APT package lists only and read Ubuntu’s local restart-required marker. This check does not contact a network, refresh package lists, install packages or make system changes."),
            include_rows=False,
        )
        updates_status = Gtk.Label(label="", xalign=0, wrap=True)
        updates_rows = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE, css_classes=["boxed-list"])
        updates_refresh = Gtk.Button(label=_("Check cached update status"), halign=Gtk.Align.START)
        updates_refresh.connect(
            "clicked",
            lambda *_: self.refresh_apt_update_status(
                updates_refresh, updates_status, updates_rows, announce=True,
            ),
        )
        updates_open = Gtk.Button(label=_("Open Software Updater"), halign=Gtk.Align.START)
        updates_open.connect("clicked", lambda *_: self.open_app("update-manager"))
        updates_box.append(updates_refresh)
        updates_box.append(updates_open)
        updates_box.append(updates_status)
        updates_box.append(updates_rows)
        box.append(updates_box)
        self.refresh_apt_update_status(updates_refresh, updates_status, updates_rows)

        automatic_updates_box, _automatic_updates_rows = self.page(
            _("Automatic security updates"),
            _("Read the merged APT setting, the unattended-upgrades package and its daily systemd timer. This local check does not contact a network or change settings, and it cannot confirm that an update ran successfully or which repositories are allowed."),
            include_rows=False,
        )
        automatic_updates_status = Gtk.Label(label=_("Automatic update setup has not been checked yet."), xalign=0, wrap=True)
        automatic_updates_rows = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE, css_classes=["boxed-list"])
        automatic_updates_refresh = Gtk.Button(label=_("Check automatic update setup"), halign=Gtk.Align.START)
        automatic_updates_refresh.connect(
            "clicked",
            lambda *_: self.refresh_automatic_update_status(
                automatic_updates_refresh, automatic_updates_status, automatic_updates_rows,
                announce=True,
            ),
        )
        automatic_updates_open_settings = Gtk.Button(
            label=_("Open Software & Updates"), halign=Gtk.Align.START,
        )
        automatic_updates_open_settings.connect(
            "clicked", lambda *_: self.open_app("software-properties-gtk"),
        )
        automatic_updates_box.append(automatic_updates_refresh)
        automatic_updates_box.append(automatic_updates_open_settings)
        automatic_updates_box.append(automatic_updates_status)
        automatic_updates_box.append(automatic_updates_rows)
        box.append(automatic_updates_box)
        self.automatic_updates_status = automatic_updates_status
        self.automatic_updates_rows = automatic_updates_rows
        self.automatic_updates_refresh = automatic_updates_refresh

        package_box, _package_rows = self.page(
            _("Package installation health"),
            _("Check the local dpkg database for interrupted or incomplete package installations. This read-only check does not use the network or change system files. If entries appear, review them in Software Updater or ask your administrator before running repair commands."),
            include_rows=False,
        )
        package_status = Gtk.Label(label=_("Package health has not been checked yet."), xalign=0, wrap=True)
        package_rows = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE, css_classes=["boxed-list"])
        package_refresh = Gtk.Button(label=_("Check package health"), halign=Gtk.Align.START)
        package_refresh.connect(
            "clicked",
            lambda *_: self.refresh_package_health(
                package_refresh, package_status, package_rows, announce=True,
            ),
        )
        package_open = Gtk.Button(label=_("Open Software Updater"), halign=Gtk.Align.START)
        package_open.connect("clicked", lambda *_: self.open_app("update-manager"))
        package_box.append(package_refresh)
        package_box.append(package_open)
        package_box.append(package_status)
        package_box.append(package_rows)
        box.append(package_box)

        storage_locations = read_storage_locations()
        storage_box, storage_rows = self.page(
            _("Storage"),
            _("Local filesystem capacity and, when Linux reports it, available file entries. A filesystem can run out of file entries even while byte space remains. A separate home filesystem is shown when your personal files use a different mounted volume."),
        )
        self.storage_box = storage_box
        self.storage_rows = storage_rows
        self.add_storage_status_rows(storage_rows, storage_locations)
        box.append(storage_box)

        backup_box, _backup_rows = self.page(
            _("Backup app availability"),
            _("Check locally whether Ubuntu’s Déjà Dup Backups app is installed. This does not inspect your files, backup destinations or backup history."),
            include_rows=False,
        )
        backup_status = Gtk.Label(label="", xalign=0, wrap=True)
        backup_refresh = Gtk.Button(label=_("Check backup app"), halign=Gtk.Align.START)
        backup_refresh.connect(
            "clicked",
            lambda *_: self.refresh_backup_tool_status(backup_status, backup_open, announce=True),
        )
        backup_open = Gtk.Button(label=_("Open Backups"), halign=Gtk.Align.START)
        backup_open.connect("clicked", lambda *_: self.open_app("deja-dup"))
        backup_open.set_sensitive(False)
        backup_app_center = Gtk.Button(label=_("Open Ubuntu App Center"), halign=Gtk.Align.START)
        backup_app_center.connect("clicked", lambda *_: self.confirm_app_center())
        backup_box.append(backup_refresh)
        backup_box.append(backup_open)
        backup_box.append(backup_app_center)
        backup_box.append(backup_status)
        box.append(backup_box)
        self.refresh_backup_tool_status(backup_status, backup_open)

        battery_box, _battery_rows = self.page(
            _("Battery"),
            _("Charge level, charging state, reported battery health, cycle count, any charge limit exposed by the battery, and the active power profile are read from local system information when available. An estimated capacity compared with the original design is shown only if the battery exposes both values. Battery health algorithms vary by manufacturer, so reported values are not directly comparable. These readings are informational, not universal service thresholds. Ubuntu Start does not change charge limits or power settings."),
            include_rows=False,
        )
        battery_refresh = Gtk.Button(label=_("Refresh battery status"), halign=Gtk.Align.START)
        battery_status_label = Gtk.Label(label="", xalign=0, wrap=True)
        battery_rows = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE, css_classes=["boxed-list"])
        battery_refresh.connect(
            "clicked",
            lambda *_: self.refresh_battery_status(
                battery_refresh, battery_status_label, battery_rows, announce=True,
            ),
        )
        battery_guide_button = Gtk.Button(
            label=_("Open battery and charging guide"), halign=Gtk.Align.START,
        )
        battery_guide_button.connect("clicked", lambda *_: self.open_battery_guide())
        battery_box.append(battery_refresh)
        battery_box.append(battery_guide_button)
        battery_box.append(battery_status_label)
        battery_box.append(battery_rows)
        self.refresh_battery_status(battery_refresh, battery_status_label, battery_rows)
        box.append(battery_box)

        video_box, _video_rows = self.page(
            _("Video device status"),
            _("Read names of video devices reported by Linux. Ubuntu Start does not open a camera or test video or audio."),
            include_rows=False,
        )
        video_status = Gtk.Label(label="", xalign=0, wrap=True)
        video_rows = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE, css_classes=["boxed-list"])
        video_refresh = Gtk.Button(label=_("Refresh video device status"), halign=Gtk.Align.START)
        video_refresh.connect(
            "clicked",
            lambda *_: self.refresh_video_status(video_refresh, video_status, video_rows, announce=True),
        )
        video_guide_button = Gtk.Button(label=_("Open camera guide"), halign=Gtk.Align.START)
        video_guide_button.connect("clicked", lambda *_: self.open_camera_guide())
        video_box.append(video_refresh)
        video_box.append(video_guide_button)
        video_box.append(video_status)
        video_box.append(video_rows)
        box.append(video_box)
        self.refresh_video_status(video_refresh, video_status, video_rows)

        hardware_box, hardware_rows = self.page(
            _("Hardware overview"),
            _("This summary reads local system files. Serial numbers are never collected."),
        )
        hardware = read_hardware_details()
        values = [
            (_("Operating system"), hardware["operating_system"]),
            (_("Kernel"), hardware["kernel"]),
            (_("System model"), hardware["system_model"]),
            (_("Processor"), hardware["processor"]),
            (_("Memory"), hardware["memory"]),
            (_("Graphics adapters"), "; ".join(hardware["graphics"]) if hardware["graphics"] else None),
            (_("Architecture"), hardware["architecture"]),
        ]
        for label, value in values:
            self.row(hardware_rows, label, value or _("Not available"))
        box.append(hardware_box)

        pci_box, _pci_rows = self.page(
            _("PCI devices"),
            _("This read-only list shows PCI hardware IDs and attached kernel drivers. Device names are matched against an installed local PCI database when available. Bridge devices are omitted; a missing driver is not by itself proof of a problem."),
            include_rows=False,
        )
        pci_status = Gtk.Label(label="", xalign=0, wrap=True)
        pci_rows = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE, css_classes=["boxed-list"])
        pci_refresh = Gtk.Button(label=_("Refresh PCI device list"), halign=Gtk.Align.START)
        pci_refresh.connect(
            "clicked",
            lambda *_: self.refresh_pci_status(pci_refresh, pci_status, pci_rows, announce=True),
        )
        pci_box.append(pci_refresh)
        pci_box.append(pci_status)
        pci_box.append(pci_rows)
        box.append(pci_box)
        self.refresh_pci_status(pci_refresh, pci_status, pci_rows)

        memory_box, _memory_rows = self.page(
            _("Memory use"),
            _("Read available RAM and swap from Linux. Compare the values while the computer feels slow. If little memory is available, save your work and close applications you recognize and are not using."),
            include_rows=False,
        )
        memory_status = Gtk.Label(label="", xalign=0, wrap=True)
        memory_rows = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE, css_classes=["boxed-list"])
        memory_refresh = Gtk.Button(label=_("Refresh memory status"), halign=Gtk.Align.START)
        memory_refresh.connect(
            "clicked",
            lambda *_: self.refresh_memory_status(memory_refresh, memory_status, memory_rows, announce=True),
        )
        memory_box.append(memory_refresh)
        memory_box.append(memory_status)
        memory_box.append(memory_rows)
        box.append(memory_box)
        self.refresh_memory_status(memory_refresh, memory_status, memory_rows)

        benchmark_box, _benchmark_rows = self.page(
            _("Performance benchmark"),
            _("Run a single-threaded integer workload on one CPU thread and open Ubuntu tools for graphics and disk measurements. Results are not uploaded. The CPU score measures this app's workload only; compare it on the same computer with the same app version. Readiness checks are short-term indicators, not a diagnosis; unavailable readings are shown as unavailable."),
            include_rows=False,
        )
        benchmark_status = Gtk.Label(label=_("Before testing: connect power, save work, close heavy apps and let the computer cool. Benchmarks can make the computer warm and use battery power."), xalign=0, wrap=True)
        saved_benchmarks = load_benchmark_baselines()
        saved_cpu = saved_benchmarks.get("cpu", {})
        saved_graphics = saved_benchmarks.get("graphics", {})
        previous_cpu_score = {"value": saved_cpu.get("score")}
        previous_graphics_score = {"value": saved_graphics.get("score")}
        saved_results = []
        if previous_cpu_score["value"] and saved_cpu.get("duration_seconds"):
            saved_results.append(_("Single-thread CPU baseline: {score} iterations/second (median of three samples; {duration} seconds total). Run again after a change to compare.").format(
                score=round(previous_cpu_score["value"]),
                duration=saved_cpu["duration_seconds"],
            ))
        if previous_graphics_score["value"]:
            saved_results.append(_("Graphics baseline: {score}. Run again later to compare with the same settings.").format(
                score=round(previous_graphics_score["value"]),
            ))
        benchmark_results = Gtk.Label(
            label="\n".join(saved_results) if saved_results else _("No benchmark has run yet."),
            xalign=0,
            wrap=True,
        )
        clear_benchmark_button = Gtk.Button(
            label=_("Clear saved benchmark results"), halign=Gtk.Align.START,
        )
        precheck = Gtk.Button(label=_("Check benchmark readiness"), halign=Gtk.Align.START)
        cpu_button = Gtk.Button(label=_("Run CPU benchmark"), halign=Gtk.Align.START)
        graphics_button = Gtk.Button(label=_("Run graphics benchmark"), halign=Gtk.Align.START)
        cancel_graphics_button = Gtk.Button(label=_("Cancel graphics benchmark"), halign=Gtk.Align.START)
        cancel_graphics_button.set_sensitive(False)
        graphics_run = {"process": None, "cancelled": False}
        disk_button = Gtk.Button(label=_("Open disk read benchmark"), halign=Gtk.Align.START)
        disk_help_button = Gtk.Button(label=_("Open GNOME disk benchmark guide"), halign=Gtk.Align.START)
        disk_write_button = Gtk.Button(label=_("Open optional disk write benchmark…"), halign=Gtk.Align.START)

        def readiness(*_args):
            precheck.set_sensitive(False)
            message = _("Checking benchmark readiness…")
            benchmark_status.set_text(message)
            self.announce_to_screen_reader(benchmark_status, message)

            def read_status():
                profile = read_power_profile()
                pressure = read_resource_pressure()
                battery = read_battery_status()
                sensors = read_temperature_sensors()
                GLib.idle_add(show_readiness, profile, pressure, battery, sensors)

            threading.Thread(target=read_status, daemon=True).start()

        def show_readiness(profile, pressure, battery, sensors):
            precheck.set_sensitive(True)
            notes = []
            notes.append(_("Power profile: {profile}").format(profile=profile if profile != "unavailable" else _("not available")))
            if battery_is_discharging(battery):
                notes.append(_("The battery is discharging; connect AC power for a more comparable run."))
            elif battery_power_status_unknown(battery):
                notes.append(_("Battery power status is unknown; connect AC power for a more comparable run."))
            cpu_busy = pressure_threshold_exceeded(pressure, "cpu", "some", 20)
            if cpu_busy is True:
                notes.append(_("CPU pressure is elevated right now; close busy apps and check again."))
            elif cpu_busy is False:
                notes.append(_("No high CPU pressure was detected in the recent sample."))
            else:
                notes.append(_("CPU pressure data is not available; readiness could not be checked."))
            memory_full = pressure_threshold_exceeded(pressure, "memory", "full", 1)
            memory_some = pressure_threshold_exceeded(pressure, "memory", "some", 20)
            if memory_full is True or memory_some is True:
                notes.append(_("Memory pressure is elevated; save work and close apps you recognize before benchmarking."))
            elif memory_full is False and memory_some is False:
                notes.append(_("No high memory pressure was detected in the recent sample."))
            else:
                notes.append(_("Memory pressure data is not available; readiness could not be checked."))
            io_busy = pressure_threshold_exceeded(pressure, "io", "some", 10)
            if io_busy is True:
                notes.append(_("Storage I/O is busy; wait for file copies or updates to finish before measuring the disk."))
            elif io_busy is False:
                notes.append(_("No high storage I/O pressure was detected in the recent sample."))
            else:
                notes.append(_("Storage I/O pressure data is not available; readiness could not be checked."))
            if profile == "power-saver":
                notes.append(_("Power Saver can reduce performance. On AC power, review Power Settings and use Performance only if it is offered."))
            if sensors:
                hottest_sensor = max(sensors, key=lambda item: item["temperature_c"])
                hottest = hottest_sensor["temperature_c"]
                notes.append(_("Hottest exposed sensor: {temperature} °C; sensor meaning varies by device.").format(temperature=hottest))
                if sensor_near_critical_limit(sensors):
                    notes.append(_("At least one sensor is within 10 °C of its reported critical limit. Let the computer cool before benchmarking; each limit is specific to its sensor."))
            else:
                notes.append(_("Temperature sensors are not available."))
            message = "\n".join(notes)
            benchmark_status.set_text(message)
            self.announce_to_screen_reader(benchmark_status, message)
            return GLib.SOURCE_REMOVE

        def confirmed_cpu():
            dialog = Adw.AlertDialog(heading=_("Run the CPU benchmark?"), body=_("After a short warm-up, this runs three one-second, single-threaded CPU measurements and uses their median. It can increase heat and battery use. Save work first; the result is a relative app-specific score, not a whole-system rating."))
            dialog.add_response("cancel", _("Cancel"))
            dialog.add_response("run", _("Run benchmark"))
            dialog.set_default_response("run")
            dialog.set_response_appearance("run", Adw.ResponseAppearance.SUGGESTED)
            dialog.connect("response", lambda _dialog, response: start_cpu() if response == "run" else None)
            dialog.present(self.get_active_window())

        def start_cpu():
            cpu_button.set_sensitive(False)
            graphics_button.set_sensitive(False)
            clear_benchmark_button.set_sensitive(False)
            message = _("Warming up and measuring CPU…")
            benchmark_results.set_text(message)
            self.announce_to_screen_reader(benchmark_results, message)
            def work():
                result = run_cpu_benchmark()
                GLib.idle_add(show_cpu, result)
            threading.Thread(target=work, daemon=True).start()

        def show_cpu(result):
            cpu_button.set_sensitive(True)
            graphics_button.set_sensitive(True)
            score = result["iterations_per_second"]
            previous = previous_cpu_score["value"]
            change = benchmark_score_change_percent(score, previous) if previous else None
            if change is not None:
                message = _("Single-thread CPU: {score} iterations/second; {change} % since the previous run (median of three samples). Keep power and temperature conditions similar when comparing.").format(score=score, change=f"{change:+.1f}")
                message = add_benchmark_comparison_note(message)
            else:
                message = _("Single-thread CPU baseline: {score} iterations/second (median of three samples over {duration} seconds). Run again after a change to compare.").format(score=score, duration=result["duration_seconds"])
            previous_cpu_score["value"] = score
            saved = save_benchmark_baseline(
                "cpu", score, result["duration_seconds"],
            )
            clear_benchmark_button.set_sensitive(True)
            if not saved:
                message += "\n" + _("This score could not be saved locally for future comparisons.")
            benchmark_results.set_text(message)
            self.announce_to_screen_reader(benchmark_results, message)

        def launch_graphics(*_args):
            executable = find_graphics_benchmark_tool()
            if not executable:
                message = _("Graphics benchmark unavailable. Install the Ubuntu package glmark2 from your configured software sources or ask your administrator. Ubuntu Start will not install it.")
                benchmark_results.set_text(message)
                self.announce_to_screen_reader(benchmark_results, message)
                return
            dialog = Adw.AlertDialog(heading=_("Run the graphics benchmark?"), body=_("This opens glmark2 and renders a graphics workload. It can make the computer warm and use battery power. The result depends on the graphics driver, display and desktop session."))
            dialog.add_response("cancel", _("Cancel"))
            dialog.add_response("run", _("Run benchmark"))
            dialog.set_default_response("run")
            dialog.connect("response", lambda _dialog, response: run_graphics(executable) if response == "run" else None)
            dialog.present(self.get_active_window())

        def run_graphics(executable):
            graphics_button.set_sensitive(False)
            cpu_button.set_sensitive(False)
            clear_benchmark_button.set_sensitive(False)
            graphics_run["cancelled"] = False
            message = _("Running graphics benchmark…")
            benchmark_results.set_text(message)
            self.announce_to_screen_reader(benchmark_results, message)
            try:
                process = Gio.Subprocess.new(
                    [executable],
                    Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_MERGE,
                )
                graphics_run["process"] = process
                cancel_graphics_button.set_sensitive(True)
                process.communicate_utf8_async(None, None, graphics_finished, None)
            except GLib.Error:
                graphics_button.set_sensitive(True)
                cpu_button.set_sensitive(True)
                clear_benchmark_button.set_sensitive(True)
                message = _("Could not start the graphics benchmark.")
                benchmark_results.set_text(message)
                self.announce_to_screen_reader(benchmark_results, message)

        def cancel_graphics(*_args):
            process = graphics_run["process"]
            if process is None:
                return
            graphics_run["cancelled"] = True
            cancel_graphics_button.set_sensitive(False)
            message = _("Stopping graphics benchmark…")
            benchmark_results.set_text(message)
            self.announce_to_screen_reader(benchmark_results, message)
            process.force_exit()

        def graphics_finished(process, async_result, _user_data):
            graphics_button.set_sensitive(True)
            cpu_button.set_sensitive(True)
            cancel_graphics_button.set_sensitive(False)
            graphics_run["process"] = None
            clear_benchmark_button.set_sensitive(True)
            try:
                completed, output, _stderr = process.communicate_utf8_finish(async_result)
            except GLib.Error:
                completed, output = False, ""
            if graphics_run["cancelled"]:
                message = _("Graphics benchmark was cancelled.")
                graphics_run["cancelled"] = False
            elif not completed or not process.get_successful():
                message = _("Graphics benchmark did not complete successfully.")
            else:
                score = parse_glmark2_score(output or "")
                if score is None:
                    message = _("Could not read the glmark2 score from its output.")
                else:
                    previous = previous_graphics_score["value"]
                    change = benchmark_score_change_percent(score, previous) if previous else None
                    if change is None:
                        message = _("Graphics baseline: {score}. Run again later to compare with the same settings.").format(score=score)
                    else:
                        message = _("Graphics score: {score}; {change} % since the previous run. Keep the display, driver and session the same when comparing.").format(score=score, change=f"{change:+.1f}")
                        message = add_benchmark_comparison_note(message)
                    previous_graphics_score["value"] = score
                    if not save_benchmark_baseline("graphics", score):
                        message += "\n" + _("This score could not be saved locally for future comparisons.")
            benchmark_results.set_text(message)
            self.announce_to_screen_reader(benchmark_results, message)

        def confirm_clear_benchmarks(*_args):
            dialog = Adw.AlertDialog(
                heading=_("Clear saved benchmark results?"),
                body=_("This removes the CPU and graphics scores saved on this computer. It does not affect system settings or installed applications."),
            )
            dialog.add_response("cancel", _("Cancel"))
            dialog.add_response("clear", _("Clear saved results"))
            dialog.set_default_response("cancel")
            dialog.connect("response", clear_benchmarks)
            dialog.present(self.get_active_window())

        def clear_benchmarks(_dialog, response):
            if response != "clear":
                return
            if not clear_benchmark_baselines():
                message = _("Could not clear saved benchmark results.")
            else:
                previous_cpu_score["value"] = None
                previous_graphics_score["value"] = None
                message = _("Saved benchmark results cleared.")
            benchmark_results.set_text(message)
            self.announce_to_screen_reader(benchmark_results, message)

        def launch_disk(*_args):
            executable = find_benchmark_tool("gnome-disks")
            if not executable:
                message = _("GNOME Disks is not installed. The Ubuntu package is gnome-disk-utility; install it from your configured software sources or ask your administrator. Ubuntu Start will not install it.")
                benchmark_results.set_text(message)
                self.announce_to_screen_reader(benchmark_results, message)
                return
            self.open_app(executable)
            message = _("In Disks, select a drive, open its menu and choose Benchmark… Use the read-only benchmark first. It may take several minutes.")
            benchmark_results.set_text(message)
            self.announce_to_screen_reader(benchmark_results, message)

        def launch_write(*_args):
            executable = find_benchmark_tool("gnome-disks")
            if not executable:
                message = _("GNOME Disks is not installed. The Ubuntu package is gnome-disk-utility; install it from your configured software sources or ask your administrator. Ubuntu Start will not install it.")
                benchmark_results.set_text(message)
                self.announce_to_screen_reader(benchmark_results, message)
                return
            dialog = Adw.AlertDialog(heading=_("Open the optional disk write benchmark?"), body=_("A write benchmark writes data to the selected drive and may require administrator approval. Use it only if you understand the risk and have a current backup. The app does not run or authorize the write test."))
            dialog.add_response("cancel", _("Cancel"))
            dialog.add_response("open", _("Open Disks"))
            dialog.set_default_response("cancel")
            dialog.connect("response", lambda _dialog, response: self.open_app(executable) if response == "open" else None)
            dialog.present(self.get_active_window())

        precheck.connect("clicked", readiness)
        cpu_button.connect("clicked", lambda *_: confirmed_cpu())
        graphics_button.connect("clicked", launch_graphics)
        cancel_graphics_button.connect("clicked", cancel_graphics)
        disk_button.connect("clicked", launch_disk)
        disk_help_button.connect("clicked", lambda *_: self.confirm_external_link(
            "https://help.gnome.org/gnome-help/disk-benchmark.html",
            _("Open GNOME disk benchmark guide?"),
            _("This opens GNOME's online guide to disk tests and results in your browser. The website receives a normal web request and can see your IP address."),
        ))
        disk_write_button.connect("clicked", launch_write)
        clear_benchmark_button.connect("clicked", confirm_clear_benchmarks)
        for widget in (precheck, cpu_button, graphics_button, cancel_graphics_button, disk_button, disk_help_button, disk_write_button, clear_benchmark_button, benchmark_status, benchmark_results):
            benchmark_box.append(widget)
        box.append(benchmark_box)

        pressure_box, _pressure_rows = self.page(
            _("System resource pressure"),
            _("Linux reports how often at least one task was waiting for CPU time, memory or storage I/O during the last 10 seconds. Memory and storage may also report periods when all non-idle tasks were stalled at once. These system-wide readings do not identify a process or prove the cause of a slowdown."),
            include_rows=False,
        )
        pressure_status = Gtk.Label(label="", xalign=0, wrap=True)
        pressure_rows = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE, css_classes=["boxed-list"])
        pressure_refresh = Gtk.Button(label=_("Refresh system pressure"), halign=Gtk.Align.START)
        pressure_refresh.connect(
            "clicked",
            lambda *_: self.refresh_resource_pressure(
                pressure_refresh, pressure_status, pressure_rows, announce=True,
            ),
        )
        pressure_box.append(pressure_refresh)
        pressure_box.append(pressure_status)
        pressure_box.append(pressure_rows)
        box.append(pressure_box)
        self.refresh_resource_pressure(pressure_refresh, pressure_status, pressure_rows)

        services_box, _service_rows = self.page(
            _("System service status"),
            _("Lists service units systemd currently marks as failed. A failure can be temporary or expected and does not prove that a feature is broken. The list does not include logs or explain the cause; do not change services based on this status alone."),
            include_rows=False,
        )
        services_status = Gtk.Label(label="", xalign=0, wrap=True)
        service_rows = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE, css_classes=["boxed-list"])
        services_refresh = Gtk.Button(label=_("Refresh system service status"), halign=Gtk.Align.START)
        services_refresh.connect(
            "clicked",
            lambda *_: self.refresh_failed_services(
                services_refresh, services_status, service_rows, announce=True,
            ),
        )
        services_box.append(services_refresh)
        services_box.append(services_status)
        services_box.append(service_rows)
        box.append(services_box)
        self.refresh_failed_services(services_refresh, services_status, service_rows)

        startup_box, _startup_rows = self.page(
            _("System startup time"),
            _("Read systemd's local boot-time summary. The optional dependency-chain view lists local service names, which can reveal installed software; review it before sharing."),
            include_rows=False,
        )
        self.startup_time_box = startup_box
        startup_status = Gtk.Label(label=_("Startup time has not been checked yet."), xalign=0, wrap=True)
        startup_rows = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE, css_classes=["boxed-list"])
        startup_chain = Gtk.Label(label="", xalign=0, wrap=True, selectable=True, css_classes=["monospace"])
        startup_chain.set_visible(False)
        startup_refresh = Gtk.Button(label=_("Check startup time"), halign=Gtk.Align.START)
        startup_refresh.connect(
            "clicked",
            lambda *_: self.refresh_startup_timing(
                startup_refresh, startup_status, startup_rows, announce=True,
            ),
        )
        startup_guide = Gtk.Button(label=_("Open startup time guide"), halign=Gtk.Align.START)
        startup_guide.connect("clicked", lambda *_: self.open_startup_time_guide())
        startup_chain_button = Gtk.Button(
            label=_("Inspect graphical startup chain"), halign=Gtk.Align.START,
        )
        startup_chain_button.connect(
            "clicked",
            lambda *_: self.refresh_startup_chain(
                startup_chain_button, startup_status, startup_chain, announce=True,
            ),
        )
        startup_box.append(startup_refresh)
        startup_box.append(startup_guide)
        startup_box.append(startup_chain_button)
        startup_box.append(startup_status)
        startup_box.append(startup_rows)
        startup_box.append(startup_chain)
        box.append(startup_box)

        temperature_box, _temperature_rows = self.page(
            _("Temperature sensor status"),
            _("Read temperature values that Linux already exposes. Sensor coverage and normal temperatures vary by model. This check does not stress-test hardware or change fan or power settings."),
            include_rows=False,
        )
        temperature_status = Gtk.Label(label="", xalign=0, wrap=True)
        temperature_rows = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE, css_classes=["boxed-list"])
        temperature_refresh = Gtk.Button(label=_("Refresh temperature status"), halign=Gtk.Align.START)
        temperature_refresh.connect(
            "clicked",
            lambda *_: self.refresh_temperature_status(
                temperature_refresh, temperature_status, temperature_rows, announce=True,
            ),
        )
        temperature_box.append(temperature_refresh)
        temperature_box.append(temperature_status)
        temperature_box.append(temperature_rows)
        box.append(temperature_box)
        self.refresh_temperature_status(temperature_refresh, temperature_status, temperature_rows)

        usb_box, _usb_rows = self.page(
            _("Connected USB devices"),
            _("This local list reads USB device names and bound kernel drivers. It may match vendor and product names from an installed local USB ID database; hardware IDs remain visible for reference. Serial numbers are not read."),
            include_rows=False,
        )
        usb_status = Gtk.Label(label="", xalign=0, wrap=True)
        usb_rows = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE, css_classes=["boxed-list"])
        usb_refresh = Gtk.Button(label=_("Refresh USB device list"), halign=Gtk.Align.START)
        usb_refresh.connect(
            "clicked",
            lambda *_: self.refresh_usb_status(usb_refresh, usb_status, usb_rows, announce=True),
        )
        usb_box.append(usb_refresh)
        usb_box.append(usb_status)
        usb_box.append(usb_rows)
        self.refresh_usb_status(usb_refresh, usb_status, usb_rows)
        box.append(usb_box)
        return self.add_display_status(box)

    def add_storage_status_rows(self, storage_rows, storage_locations):
        for location, storage in storage_locations.items():
            title = _("System filesystem") if location == "system" else _("Home folder filesystem")
            storage_percent = round(storage["used"] / storage["total"] * 100) if storage["total"] else 0
            self.row(storage_rows, title, _("{free} free of {total} ({percent}% used)").format(
                free=GLib.format_size(storage["free"]), total=GLib.format_size(storage["total"]), percent=storage_percent,
            ))
            file_total = storage.get("file_entries_total")
            file_free = storage.get("file_entries_free")
            if isinstance(file_total, int) and isinstance(file_free, int) and file_total > 0:
                self.row(
                    storage_rows,
                    _("Available file entries"),
                    _("{free} of {total} available ({percent}% used)").format(
                        free=locale.format_string("%d", file_free, grouping=True),
                        total=locale.format_string("%d", file_total, grouping=True),
                        percent=round((file_total - file_free) / file_total * 100),
                    ),
                )
            if storage_percent >= 95:
                warning_title = _("System filesystem is almost full") if location == "system" else _("Home folder filesystem is almost full")
                self.row(storage_rows, warning_title, _("Remove files you no longer need or review large downloads. Ubuntu may need free space for updates. Avoid deleting system files."))
            if storage.get("read_only") is True:
                self.row(
                    storage_rows,
                    _("Filesystem is mounted read-only"),
                    _("Ubuntu cannot write to this filesystem right now. If this is unexpected, restart the computer. If it remains read-only, use Ubuntu recovery options or ask a trusted support person before attempting repairs."),
                )

    def refresh_usb_status(self, button, status_label, device_rows, announce=False):
        button.set_sensitive(False)
        status_label.set_text(_("Reading USB devices…"))

        def read_status():
            devices = read_usb_devices()
            GLib.idle_add(
                self.show_usb_status, button, status_label, device_rows, devices, announce,
            )

        threading.Thread(target=read_status, daemon=True).start()

    def refresh_pci_status(self, button, status_label, device_rows, announce=False):
        button.set_sensitive(False)
        status_label.set_text(_("Reading PCI devices…"))
        while (child := device_rows.get_first_child()) is not None:
            device_rows.remove(child)

        def read_status():
            devices = read_pci_devices()
            GLib.idle_add(
                self.show_pci_status, button, status_label, device_rows, devices, announce,
            )

        threading.Thread(target=read_status, daemon=True).start()

    def show_pci_status(self, button, status_label, device_rows, devices, announce=False):
        button.set_sensitive(True)
        while (child := device_rows.get_first_child()) is not None:
            device_rows.remove(child)
        if devices:
            for device in devices:
                name = device["name"] or _("PCI device")
                title = f"{name} [{device['id']}]"
                driver = device["driver"]
                subtitle = (
                    _("Kernel driver: {driver}").format(driver=driver)
                    if driver else _("No kernel driver is currently attached.")
                )
                self.row(device_rows, title, subtitle)
            message = (
                _("PCI device list updated: 1 device found.")
                if len(devices) == 1
                else _("PCI device list updated: {count} devices found.").format(count=len(devices))
            )
        else:
            message = _("No PCI devices found")
            self.row(device_rows, message, _("Linux did not expose any PCI devices to list."))
        status_label.set_text(message)
        if announce:
            self.announce_to_screen_reader(status_label, message)
        return GLib.SOURCE_REMOVE

    def refresh_video_status(self, button, status_label, device_rows, announce=False):
        button.set_sensitive(False)
        status_label.set_text(_("Reading video devices…"))
        while (child := device_rows.get_first_child()) is not None:
            device_rows.remove(child)

        def read_status():
            devices = read_video_devices()
            GLib.idle_add(self.show_video_status, button, status_label, device_rows, devices, announce)

        threading.Thread(target=read_status, daemon=True).start()

    def show_video_status(self, button, status_label, device_rows, devices, announce=False):
        button.set_sensitive(True)
        while (child := device_rows.get_first_child()) is not None:
            device_rows.remove(child)
        if devices:
            for device in devices:
                self.row(device_rows, device, _("Reported by Linux"))
            if len(devices) == 1:
                message = _("Video device status updated: 1 device found.")
            else:
                message = _("Video device status updated: {count} devices found.").format(count=len(devices))
        else:
            message = _("No video devices reported by Linux")
            self.row(
                device_rows,
                message,
                _("Connect a camera or check its privacy shutter, then refresh. This status does not test the camera."),
            )
        status_label.set_text(message)
        if announce:
            self.announce_to_screen_reader(status_label, message)
        return GLib.SOURCE_REMOVE

    def open_camera_guide(self):
        self.open_device_guide(_("Camera"))

    def open_device_guide(self, guide_title):
        guide_index = next(
            index for index, (title, _target, _steps) in enumerate(GUIDES)
            if title == guide_title
        )
        self.device_search.set_text("")
        self.device_chooser.set_selected(guide_index)
        self.main_stack.set_visible_child_name(_("Fix a device"))

    def open_wifi_guide(self):
        self.open_device_guide(_("Wi-Fi"))

    def open_sound_guide(self):
        self.open_device_guide(_("Sound and microphones"))

    def open_sound_settings(self):
        self.open_app("gnome-control-center", "sound")

    def open_time_guide(self):
        guide_index = next(
            index for index, (title, _target, _action, _steps) in enumerate(SYSTEM_GUIDES)
            if title == _("Check date and time")
        )
        self.system_guide_chooser.set_selected(guide_index)
        self.main_stack.set_visible_child_name(_("System guides"))

    def open_startup_time_guide(self):
        guide_index = next(
            index for index, (title, _target, _action, _steps) in enumerate(SYSTEM_GUIDES)
            if title == _("Understand system startup time")
        )
        self.system_guide_chooser.set_selected(guide_index)
        self.main_stack.set_visible_child_name(_("System guides"))

    def open_system_guide(self, guide_title):
        guide_index = next(
            (index for index, (title, _target, _action, _steps) in enumerate(SYSTEM_GUIDES)
             if title == _(guide_title)),
            None,
        )
        if guide_index is None:
            return
        self.system_guide_chooser.set_selected(guide_index)
        self.main_stack.set_visible_child_name(_("System guides"))

    def open_security_guide(self):
        UbuntuStart.open_system_guide(self, "Improve everyday security")

    def open_security_documentation(self):
        self.confirm_external_link(
            "https://ubuntu.com/security",
            _("Open Ubuntu security documentation?"),
            _("This opens Ubuntu’s official security website in your browser. The website receives a normal web request and can see your IP address."),
        )

    def show_usb_status(self, button, status_label, device_rows, devices, announce=False):
        button.set_sensitive(True)
        while (child := device_rows.get_first_child()) is not None:
            device_rows.remove(child)

        if not devices:
            message = _("No external USB devices detected")
            self.row(
                device_rows, message,
                _("Connect a USB device and refresh the list."),
            )
        else:
            summaries = []
            for device in devices:
                device_name = device["name"]
                title = (
                    f"{device_name} [{device['id']}]" if device_name
                    else _("USB device ({id})").format(id=device["id"])
                )
                drivers = device["drivers"]
                subtitle = (
                    _("Kernel driver: {drivers}").format(drivers=", ".join(drivers))
                    if drivers else _("No kernel driver is currently attached.")
                )
                self.row(device_rows, title, subtitle)
                summaries.append(title)
            message = _("USB device list updated: {devices}").format(devices="; ".join(summaries))

        status_label.set_text(message)
        if announce:
            self.announce_to_screen_reader(status_label, message)
        return GLib.SOURCE_REMOVE

    def confirm_internet_test(self, button, status_label):
        dialog = Adw.AlertDialog(
            heading=_("Allow an internet connection test?"),
            body=_("Ubuntu Start will send one small HTTPS request to ubuntu.com. The site can see your IP address. No system details, Wi-Fi name or passwords are sent."),
        )
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("test", _("Test connection"))
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")

        def on_response(_dialog, response):
            if response == "test":
                button.set_sensitive(False)
                status_label.set_text(_("Checking connection to ubuntu.com…"))

                def check():
                    started = time.monotonic()
                    result = check_internet_connection()
                    elapsed_ms = round((time.monotonic() - started) * 1000, 1)
                    GLib.idle_add(
                        self.show_internet_result, button, status_label, result, elapsed_ms,
                    )

                threading.Thread(target=check, daemon=True).start()

        dialog.connect("response", on_response)
        dialog.present(self.get_active_window())

    def confirm_network_diagnostics(self, button, status_label):
        dialog = Adw.AlertDialog(
            heading=_("Run DNS and gateway tests?"),
            body=_("This sends one DNS lookup for ubuntu.com to your configured resolver and one ping to your local gateway. The gateway MAC address is checked against a local vendor database. No information is sent to an external vendor lookup service."),
        )
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("run", _("Run tests"))
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")

        def on_response(_dialog, response):
            if response == "run":
                button.set_sensitive(False)
                status_label.set_text(_("Testing DNS and gateway…"))

                def check():
                    result = run_network_diagnostics()
                    GLib.idle_add(self.show_network_diagnostic_result, button, status_label, result)

                threading.Thread(target=check, daemon=True).start()

        dialog.connect("response", on_response)
        dialog.present(self.get_active_window())

    def show_network_diagnostic_result(self, button, status_label, result):
        button.set_sensitive(True)
        self.last_network_diagnostics = result
        lines = []
        if result.get("dns_latency_ms") is not None:
            lines.append(_("DNS lookup: {ms} ms").format(ms=format_milliseconds(result["dns_latency_ms"])))
        elif result.get("dns_test_duration_ms") is not None:
            dns_error = result.get("dns_error")
            elapsed = format_milliseconds(result["dns_test_duration_ms"])
            if dns_error == "timeout":
                lines.append(_("DNS lookup timed out after {ms} ms. Check the network connection or DNS server.").format(ms=elapsed))
            elif dns_error == "resolvectl-not-available":
                lines.append(_("systemd-resolved is not available, so a DNS query could not be made. Ask your administrator to check the system DNS service."))
            else:
                lines.append(_("DNS lookup failed after {ms} ms. Check DNS settings or the network connection.").format(ms=elapsed))
        else:
            if result.get("dns_error") == "resolvectl-not-available":
                lines.append(_("systemd-resolved is not available, so a DNS query could not be made. Ask your administrator to check the system DNS service."))
            else:
                lines.append(_("DNS lookup failed. Check DNS settings or the network connection."))
        gateway = result.get("gateway")
        if gateway:
            lines.append(_("Gateway: {address}").format(address=gateway))
            if result.get("gateway_latency_ms") is not None:
                latency = format_milliseconds(result["gateway_latency_ms"])
                if result.get("gateway_latency_is_upper_bound"):
                    lines.append(_("Gateway response: less than {ms} ms").format(ms=latency))
                else:
                    lines.append(_("Gateway response: {ms} ms").format(ms=latency))
                duration = result.get("gateway_test_duration_ms")
                if duration is not None:
                    lines.append(_("Ping test completed in {ms} ms").format(ms=format_milliseconds(duration)))
            elif result.get("gateway_error") == "ping-not-installed":
                lines.append(_("The ping tool is not installed. Check that the iputils-ping package is installed or ask your administrator."))
            elif result.get("gateway_error") == "timeout":
                elapsed = result.get("gateway_test_duration_ms")
                if elapsed is not None:
                    lines.append(_("The gateway ping timed out after {ms} ms. Some routers block ping requests.").format(ms=format_milliseconds(elapsed)))
                else:
                    lines.append(_("The gateway ping timed out. Some routers block ping requests."))
            else:
                elapsed = result.get("gateway_test_duration_ms")
                if elapsed is not None:
                    lines.append(_("The gateway did not answer the ping after {ms} ms. Some routers block ping requests.").format(ms=format_milliseconds(elapsed)))
                else:
                    lines.append(_("Gateway did not answer the ping. Some routers block ping requests."))
            mac = result.get("gateway_mac")
            if mac:
                lines.append(_("Gateway MAC address: {mac}").format(mac=mac))
                vendor = result.get("gateway_vendor")
                lines.append(_("Manufacturer: {vendor}").format(vendor=vendor) if vendor else _("Manufacturer not found in the local vendor database."))
            else:
                lines.append(_("Gateway MAC address is not available in the local neighbor table."))
        else:
            if result.get("gateway_error") == "ip-not-installed":
                lines.append(_("The iproute2 package is not installed, so the default gateway could not be checked."))
                lines.append(_("Ask your administrator to install iproute2, then run the network test again."))
            else:
                lines.append(_("No default gateway was found."))
                lines.append(_("Next step: check Wi-Fi or wired connection in Settings. On a managed network, ask the administrator before changing route settings."))
        if result.get("dns_latency_ms") is None and result.get("dns_error") != "resolvectl-not-available":
            lines.append(_("Next step: check that the network is connected and review its DNS settings."))
        if (result.get("gateway") and result.get("gateway_latency_ms") is None
                and result.get("gateway_error") != "ping-not-installed"):
            lines.append(_("Next step: check the local connection. Some gateways block ping, so this alone does not prove that the network is down."))
        status_label.set_text("\n".join(lines))
        self.announce_to_screen_reader(status_label, "\n".join(lines))
        return GLib.SOURCE_REMOVE

    def confirm_external_link(self, uri, heading, body):
        dialog = Adw.AlertDialog(heading=heading, body=body)
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("open", _("Open link"))
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")
        dialog.connect("response", lambda _dialog, response: self.open_uri(uri) if response == "open" else None)
        dialog.present(self.get_active_window())

    def show_internet_result(self, button, status_label, result, elapsed_ms):
        button.set_sensitive(True)
        if result.startswith("reachable:"):
            message = _(
                "ubuntu.com responded in {ms} ms. Internet access is available."
            ).format(ms=format_milliseconds(elapsed_ms))
        else:
            message = _(
                "Could not reach ubuntu.com after {ms} ms. Check the router, "
                "network sign-in page, DNS settings or firewall."
            ).format(ms=format_milliseconds(elapsed_ms))
        status_label.set_text(message)
        self.announce_to_screen_reader(status_label, message)
        return GLib.SOURCE_REMOVE

    def refresh_network_status(self, status_label, device_rows, announce=False):
        status_label.set_text(_("Checking NetworkManager…"))
        while (child := device_rows.get_first_child()) is not None:
            device_rows.remove(child)

        def read_status():
            devices, error = read_network_devices()
            adapter_details = {
                name: details
                for name, _device_type, _state in devices
                if (details := read_network_adapter_details(name)) is not None
            }
            interface_ips = {
                name: details
                for name, _device_type, state in devices
                if state in {"connected", "unmanaged"}
                if (details := read_interface_ip_status(name)) is not None
            }
            wifi_details = {
                name: details
                for name, device_type, state in devices
                if device_type == "wifi" and state == "connected"
                if (details := read_wifi_link_status(name))
            }
            GLib.idle_add(
                self.show_network_status, status_label, device_rows, devices,
                error, announce, wifi_details, interface_ips, adapter_details,
            )

        threading.Thread(target=read_status, daemon=True).start()

    def refresh_wifi_quick_check(self, button, status_label, announce=False):
        button.set_sensitive(False)
        status_label.set_text(_("Checking Wi-Fi status…"))

        def read_status():
            devices, error = read_network_devices()
            radios = read_rfkill_status()
            connected = [
                name for name, device_type, state in devices
                if device_type == "wifi" and state == "connected"
            ]
            interface_ips = {
                name: details for name in connected
                if (details := read_interface_ip_status(name)) is not None
            }
            wifi_details = {
                name: details for name in connected
                if (details := read_wifi_link_status(name))
            }
            GLib.idle_add(
                self.show_wifi_quick_check, button, status_label, devices, error,
                radios, interface_ips, wifi_details, announce,
            )

        threading.Thread(target=read_status, daemon=True).start()

    def show_wifi_quick_check(
        self, button, status_label, devices, error, radios,
        interface_ips, wifi_details, announce=False,
    ):
        button.set_sensitive(True)
        if error:
            message = _("Could not read Wi-Fi connection status from NetworkManager. Refresh Network status and try again.")
        else:
            wifi_devices = [
                (name, state) for name, device_type, state in devices
                if device_type == "wifi"
            ]
            if not wifi_devices:
                message = _("NetworkManager reports no Wi-Fi device. If this computer has Wi-Fi, review the hardware and driver details.")
            else:
                name, state = wifi_devices[0]
                wlan = next((radio for radio in radios or () if radio["type"] == "wlan"), None)
                if wlan and wlan["soft_blocked"] and wlan["hard_blocked"]:
                    message = _("Wi-Fi is blocked in software and by hardware or firmware. Check airplane mode and the computer’s Wi-Fi switch or keyboard shortcut.")
                elif wlan and wlan["soft_blocked"]:
                    message = _("Wi-Fi is blocked in software. Check airplane mode or the Wi-Fi switch in Quick Settings.")
                elif wlan and wlan["hard_blocked"]:
                    message = _("Wi-Fi is blocked by hardware or firmware. Check the computer’s physical switch or keyboard shortcut and consult its manual.")
                elif state == "disconnected":
                    message = _("The Wi-Fi device is available but not connected. Open Wi-Fi Settings and choose a network you recognize.")
                elif state == "unavailable (firmware missing)":
                    message = _("NetworkManager reports that Wi-Fi firmware is missing. Review the hardware and driver details, then ask the computer manufacturer or administrator for help.")
                elif state == "unavailable":
                    message = _("The Wi-Fi device is unavailable. Check radio-block status and review the hardware and driver details.")
                elif state == "connecting":
                    message = _("Wi-Fi is connecting. Wait briefly, refresh the status, and check the Wi-Fi guide if it does not connect.")
                elif state != "connected":
                    message = _("Wi-Fi status is {state}. Refresh the status or open the Wi-Fi guide for next steps.").format(state=state)
                else:
                    addresses = (interface_ips or {}).get(name)
                    if addresses is None:
                        message = _("Wi-Fi is connected, but IP-address status is unavailable. Internet access has not been tested.")
                    elif addresses["ipv4"] or addresses["ipv6"]:
                        message = _("Wi-Fi is connected and has an IP address. This does not confirm internet access; run Test DNS and gateway if websites still fail.")
                    elif addresses["link_local"]:
                        message = _("Wi-Fi is connected but only a link-local address was found. Check router address assignment or a network sign-in page.")
                    else:
                        message = _("Wi-Fi is connected but no IP address was found. Check router address assignment or a network sign-in page.")
                    metrics = (wifi_details or {}).get(name, {})
                    if "signal_dbm" in metrics:
                        message += "\n" + _("Reported Wi-Fi signal: {signal} dBm. Values closer to 0 are generally stronger; compare from the same location.").format(signal=metrics["signal_dbm"])
                if radios is None:
                    message += "\n" + _("Radio-block status is unavailable, so the hardware or software block could not be checked.")
        status_label.set_text(message)
        if announce:
            self.announce_to_screen_reader(status_label, message)
        return GLib.SOURCE_REMOVE

    def open_wifi_settings(self):
        self.open_app("gnome-control-center", "wifi")

    def refresh_rfkill_status(self, button, status_label, radio_rows, announce=False):
        button.set_sensitive(False)
        status_label.set_text(_("Checking radio block status…"))
        while (child := radio_rows.get_first_child()) is not None:
            radio_rows.remove(child)

        def read_status():
            radios = read_rfkill_status()
            GLib.idle_add(
                self.show_rfkill_status, button, status_label, radio_rows, radios, announce,
            )

        threading.Thread(target=read_status, daemon=True).start()

    def refresh_firewall_status(self, button, status_row, announce=False):
        button.set_sensitive(False)
        status_row.set_subtitle(_("Checking firewall status…"))

        def read_status():
            state, error = read_firewall_status()
            GLib.idle_add(
                self.show_firewall_status, button, status_row, state, error, announce,
            )

        threading.Thread(target=read_status, daemon=True).start()

    def show_firewall_status(self, button, status_row, state, error, announce=False):
        button.set_sensitive(True)
        messages = {
            "active": _("UFW is active. This confirms only that UFW reports active; review its rules in Ubuntu settings or with an administrator."),
            "inactive": _("UFW is inactive. Do not enable it blindly, especially if you use remote access, file sharing or a managed network."),
        }
        errors = {
            "not-installed": _("UFW is not installed, so its firewall status cannot be checked."),
            "timeout-or-unavailable": _("The firewall status check could not finish. Try again later."),
            "unavailable": _("Could not read UFW status."),
        }
        message = messages.get(state, errors.get(error, errors["unavailable"]))
        status_row.set_subtitle(message)
        if announce:
            self.announce_to_screen_reader(status_row, _("Firewall status: {status}").format(status=message))
        return GLib.SOURCE_REMOVE

    def show_rfkill_status(self, button, status_label, radio_rows, radios, announce=False):
        button.set_sensitive(True)
        if radios is None:
            message = _("Radio block status is not available on this computer.")
        elif not radios:
            message = _("Linux did not expose any wireless radio block controls.")
        else:
            labels = {
                "wlan": _("Wi-Fi radio"),
                "bluetooth": _("Bluetooth radio"),
                "wwan": _("Mobile broadband radio"),
                "gps": _("GPS radio"),
                "nfc": _("NFC radio"),
                "uwb": _("UWB radio"),
                "wimax": _("WiMAX radio"),
                "fm": _("FM radio"),
            }
            blocked_states = {
                (False, False): _("Not blocked"),
                (True, False): _("Blocked in software"),
                (False, True): _("Blocked by hardware or firmware"),
                (True, True): _("Blocked in software and by hardware or firmware"),
            }
            summaries = []
            blocked = False
            for radio in radios:
                title = labels[radio["type"]]
                state = blocked_states[(radio["soft_blocked"], radio["hard_blocked"])]
                if radio["soft_blocked"] or radio["hard_blocked"]:
                    blocked = True
                    if radio["type"] == "wlan":
                        next_step = _("Check the physical Wi-Fi switch or keyboard shortcut; consult the computer manual if it remains blocked.")
                    elif radio["type"] == "bluetooth":
                        next_step = _("Check the physical Bluetooth switch or keyboard shortcut; consult the computer manual if it remains blocked.")
                    else:
                        next_step = _("Check the computer or device manual for its radio controls.")
                    state = f"{state} · {next_step}"
                self.row(radio_rows, title, state)
                summaries.append(f"{title}: {state}")
            if blocked:
                message = _("One or more wireless radios are blocked. Review the details below.")
            else:
                message = _("No reported wireless radios are blocked.")
        status_label.set_text(message)
        if announce:
            details = "; ".join(summaries) if radios else message
            self.announce_to_screen_reader(
                status_label,
                _("Wireless radio status updated: {details}").format(details=details),
            )
        return GLib.SOURCE_REMOVE

    def refresh_bluetooth_status(self, status_row, announce=False):
        status_row.set_subtitle(_("Checking status…"))

        def read_status():
            status = read_bluetooth_status()
            GLib.idle_add(self.show_bluetooth_status, status_row, status, announce)

        threading.Thread(target=read_status, daemon=True).start()

    def refresh_backup_tool_status(self, status_label, open_button=None, announce=False):
        status_label.set_text(_("Checking whether Backups is installed…"))
        if open_button is not None:
            open_button.set_sensitive(False)

        def read_status():
            status = read_backup_tool_status()
            GLib.idle_add(self.show_backup_tool_status, status_label, status, open_button, announce)

        threading.Thread(target=read_status, daemon=True).start()

    def show_backup_tool_status(self, status_label, status, open_button=None, announce=False):
        launchable = bool(status.get("installed") and status.get("launcher"))
        if open_button is not None:
            open_button.set_sensitive(launchable)
        if launchable:
            message = _("Déjà Dup Backups is installed. This does not confirm that backups are configured or recent.")
        elif status.get("installed"):
            message = _("Déjà Dup Backups is installed, but its launcher was not found. Open Ubuntu App Center or ask your administrator for help.")
        else:
            message = _("Déjà Dup Backups is not installed. You can look for Backups in Ubuntu App Center or use Files to copy important files to a separate drive.")
        status_label.set_text(message)
        if announce:
            self.announce_to_screen_reader(status_label, message)
        return GLib.SOURCE_REMOVE

    def show_bluetooth_status(self, status_row, status, announce=False):
        states = {
            "powered": _("On"),
            "off": _("Off"),
            "no-controller": _("No Bluetooth controller found"),
            "service-inactive": _("Bluetooth service is not running. Refresh System service status for details."),
            "service-failed": _("Bluetooth service has failed. Refresh System service status for details."),
            "unknown": _("Power state is unknown"),
            "not-installed": _("Bluetooth command-line tool is not installed"),
            "timeout-or-unavailable": _("Bluetooth controller did not respond in time"),
            "unavailable": _("Could not read Bluetooth controller status"),
        }
        message = states.get(status, states["unavailable"])
        status_row.set_subtitle(message)
        if announce:
            self.announce_to_screen_reader(status_row, f"{status_row.get_title()}: {message}")
        return GLib.SOURCE_REMOVE

    def open_bluetooth_guide(self):
        guide_index = next(
            index for index, (title, _target, _action, _steps) in enumerate(SYSTEM_GUIDES)
            if title == _("Pair a Bluetooth device")
        )
        self.system_guide_chooser.set_selected(guide_index)
        self.main_stack.set_visible_child_name(_("System guides"))

    def open_bluetooth_audio_guide(self):
        guide_index = next(
            index for index, (title, _target, _action, _steps) in enumerate(SYSTEM_GUIDES)
            if title == _("Fix Bluetooth audio")
        )
        self.system_guide_chooser.set_selected(guide_index)
        self.main_stack.set_visible_child_name(_("System guides"))

    def open_battery_guide(self):
        self.open_device_guide(_("Battery and charging"))

    def refresh_audio_status(self, output_row, input_row, announce=False):
        output_row.set_subtitle(_("Checking status…"))
        input_row.set_subtitle(_("Checking status…"))

        def read_status():
            status = read_audio_status()
            GLib.idle_add(self.show_audio_status, output_row, input_row, status, announce)

        threading.Thread(target=read_status, daemon=True).start()

    def refresh_printer_status(self, button, status_label, printer_rows, announce=False):
        button.set_sensitive(False)
        status_label.set_text(_("Checking printer queues…"))
        while (child := printer_rows.get_first_child()) is not None:
            printer_rows.remove(child)

        def read_status():
            printers, error = read_printer_status()
            GLib.idle_add(
                self.show_printer_status, button, status_label, printer_rows,
                printers, error, announce,
            )

        threading.Thread(target=read_status, daemon=True).start()

    def refresh_accessibility_status(self, button, status_label, setting_rows, announce=False):
        button.set_sensitive(False)
        status_label.set_text(_("Checking accessibility settings…"))
        while (child := setting_rows.get_first_child()) is not None:
            setting_rows.remove(child)

        def read_status():
            settings, error = read_accessibility_settings()
            GLib.idle_add(
                self.show_accessibility_status, button, status_label, setting_rows,
                settings, error, announce,
            )

        threading.Thread(target=read_status, daemon=True).start()

    def refresh_time_status(self, button, status_label, setting_rows, announce=False):
        button.set_sensitive(False)
        status_label.set_text(_("Checking date and time status…"))
        while (child := setting_rows.get_first_child()) is not None:
            setting_rows.remove(child)

        def read_status():
            status, error = read_time_status()
            GLib.idle_add(self.show_time_status, button, status_label, setting_rows, status, error, announce)

        threading.Thread(target=read_status, daemon=True).start()

    def show_time_status(self, button, status_label, setting_rows, status, error, announce=False):
        button.set_sensitive(True)
        timezone = status.get("timezone")
        self.row(setting_rows, _("Time zone"), timezone if isinstance(timezone, str) else _("Not available"))
        can_ntp = status.get("can_ntp")
        self.row(
            setting_rows,
            _("Automatic time synchronization available"),
            _("Available") if can_ntp is True
            else _("Unavailable") if can_ntp is False
            else _("Not available"),
        )
        ntp = status.get("ntp")
        self.row(
            setting_rows,
            _("Automatic time synchronization"),
            _("On") if ntp is True else _("Off") if ntp is False else _("Not available"),
        )
        synchronized = status.get("synchronized")
        sync_label = (
            _("Synchronized") if synchronized is True
            else _("Not synchronized") if synchronized is False
            else _("Not available")
        )
        self.row(setting_rows, _("Clock synchronization"), sync_label)
        guidance = None
        if can_ntp is False:
            guidance = _(
                "Automatic time synchronization is unavailable on this system. If this is a "
                "managed computer, ask your administrator how its clock is maintained."
            )
        elif ntp is False:
            guidance = _(
                "Automatic time synchronization is off. Open Date & Time Settings and turn on "
                "automatic date and time if the option is available."
            )
        elif ntp is True and synchronized is False:
            guidance = _(
                "Automatic time synchronization is on, but the clock is not synchronized. Check "
                "the network connection and Date & Time Settings."
            )
        if guidance:
            self.row(setting_rows, _("Next step"), guidance)
        errors = {
            "not-installed": _("The timedatectl tool is not installed."),
            "timeout": _("The system time service did not respond in time."),
            "unavailable": _("Could not read the local date and time status."),
        }
        message = errors.get(error, _("Local date and time status read. No settings were changed."))
        status_label.set_text(message)
        if announce:
            self.announce_to_screen_reader(status_label, message)
        return GLib.SOURCE_REMOVE

    def show_accessibility_status(self, button, status_label, setting_rows, settings, error, announce=False):
        button.set_sensitive(True)
        for key, title in (
            ("screen_reader", _("Screen reader")),
            ("screen_magnifier", _("Screen magnifier")),
            ("screen_keyboard", _("On-screen keyboard")),
            ("high_contrast", _("High contrast")),
            ("sticky_keys", _("Sticky Keys")),
            ("slow_keys", _("Slow Keys")),
            ("bounce_keys", _("Bounce Keys")), ("mouse_keys", _("Mouse Keys")),
            ("visual_bell", _("Visual sound alerts")),
        ):
            value = settings.get(key)
            state = _("On") if value is True else _("Off") if value is False else _("Not available")
            self.row(setting_rows, title, state)

        text_scale = settings.get("text_scale")
        scale_label = _("Not available")
        if isinstance(text_scale, (int, float)):
            scale_label = _("{percent}%").format(percent=round(text_scale * 100))
        self.row(setting_rows, _("Text size"), scale_label)

        cursor_size = settings.get("cursor_size")
        cursor_label = _("Not available")
        if isinstance(cursor_size, int):
            cursor_label = _("{pixels} pixels").format(pixels=cursor_size)
        self.row(setting_rows, _("Pointer size"), cursor_label)

        errors = {
            "not-installed": _("GNOME Settings tools are not installed."),
            "unavailable": _("Could not read GNOME accessibility settings."),
        }
        message = errors.get(error, _("GNOME accessibility settings read. No settings were changed."))
        status_label.set_text(message)
        if announce:
            self.announce_to_screen_reader(status_label, message)
        return GLib.SOURCE_REMOVE

    def show_printer_status(self, button, status_label, printer_rows, printers, error, announce=False):
        button.set_sensitive(True)
        labels = {
            "idle": _("Ready"),
            "printing": _("Printing"),
            "disabled": _("Disabled"),
            "busy": _("Busy"),
            "processing": _("Busy"),
            "stopped": _("Stopped"),
        }
        if printers:
            for name, state, pending_jobs in printers:
                self.row(printer_rows, name, self.printer_queue_status(state, pending_jobs, labels))
            message = _("Printer status updated: {count} printer queues found.").format(count=len(printers))
        else:
            messages = {
                "not-installed": _("CUPS printer tools are not installed."),
                "timeout": _("The local printing service did not respond in time."),
                "unavailable": _("Could not read printer queues from the local printing service."),
                "no-printers": _("No printer queues were found in the local printing service."),
            }
            message = messages.get(error, messages["unavailable"])
        status_label.set_text(message)
        if announce:
            self.announce_to_screen_reader(status_label, message)
        return GLib.SOURCE_REMOVE

    def refresh_battery_status(self, button, status_label, battery_rows, announce=False):
        button.set_sensitive(False)
        status_label.set_text(_("Checking battery status…"))

        def read_status():
            batteries = read_battery_status()
            power_profile = read_power_profile()
            GLib.idle_add(
                self.show_battery_status, button, status_label, battery_rows,
                batteries, announce, power_profile,
            )

        threading.Thread(target=read_status, daemon=True).start()

    def refresh_apt_update_status(self, button, status_label, update_rows, announce=False):
        button.set_sensitive(False)
        status_label.set_text(_("Checking cached package update status…"))

        def read_status():
            status, error, reboot_required = self.read_update_status()
            GLib.idle_add(
                self.show_apt_update_status, button, status_label, update_rows,
                status, error, reboot_required, announce,
            )

        threading.Thread(target=read_status, daemon=True).start()

    def open_automatic_updates_status(self):
        self.main_stack.set_visible_child_name(_("Network and hardware"))
        self.refresh_automatic_update_status(
            self.automatic_updates_refresh,
            self.automatic_updates_status,
            self.automatic_updates_rows,
            announce=True,
        )

    def open_firewall_status(self):
        self.main_stack.set_visible_child_name(_("Network and hardware"))
        self.refresh_firewall_status(
            self.firewall_refresh_button, self.firewall_status_row, announce=True,
        )

    def open_root_encryption_status(self):
        self.main_stack.set_visible_child_name(_("Network and hardware"))
        self.refresh_root_encryption_status(
            self.root_encryption_refresh_button, self.root_encryption_row, announce=True,
        )

    def open_secure_boot_status(self):
        self.main_stack.set_visible_child_name(_("Drivers"))
        self.refresh_secure_boot_status(
            self.secure_boot_refresh_button, self.secure_boot_status_row, announce=True,
        )

    def refresh_automatic_update_status(self, button, status_label, update_rows, announce=False):
        button.set_sensitive(False)
        status_label.set_text(_("Checking automatic update setup…"))

        def read_status():
            status, error = read_automatic_upgrade_status()
            GLib.idle_add(
                self.show_automatic_update_status, button, status_label, update_rows,
                status, error, announce,
            )

        threading.Thread(target=read_status, daemon=True).start()

    def refresh_package_health(self, button, status_label, package_rows, announce=False):
        button.set_sensitive(False)
        status_label.set_text(_("Checking package installation health…"))

        def read_status():
            packages, error = read_package_health()
            GLib.idle_add(
                self.show_package_health, button, status_label, package_rows,
                packages, error, announce,
            )

        threading.Thread(target=read_status, daemon=True).start()

    def show_package_health(self, button, status_label, package_rows, packages, error, announce=False):
        button.set_sensitive(True)
        while (child := package_rows.get_first_child()) is not None:
            package_rows.remove(child)

        error_messages = {
            "not-installed": _("dpkg is not available on this system."),
            "timeout-or-unavailable": _("The package check could not finish. Try again later."),
            "unavailable": _("Could not read the local package database."),
        }
        if error or packages is None:
            message = error_messages.get(error, error_messages["unavailable"])
        elif packages:
            for package in packages:
                self.row(
                    package_rows, package,
                    _("dpkg reports an incomplete or inconsistent installation."),
                )
            message = _("Package check found {count} package entries to review.").format(count=len(packages))
        else:
            message = _("dpkg reported no incomplete package installations.")

        status_label.set_text(message)
        if announce:
            self.announce_to_screen_reader(status_label, message)
        return GLib.SOURCE_REMOVE

    def refresh_memory_status(self, button, status_label, memory_rows, announce=False):
        button.set_sensitive(False)
        status_label.set_text(_("Checking memory status…"))

        def read_status():
            status = read_memory_status()
            GLib.idle_add(self.show_memory_status, button, status_label, memory_rows, status, announce)

        threading.Thread(target=read_status, daemon=True).start()

    def show_memory_status(self, button, status_label, memory_rows, status, announce=False):
        button.set_sensitive(True)
        while (child := memory_rows.get_first_child()) is not None:
            memory_rows.remove(child)

        if not status:
            message = _("Memory status is not available from this system.")
        else:
            used_percent = round(status["used"] / status["total"] * 100)
            self.row(memory_rows, _("Total RAM"), GLib.format_size(status["total"]))
            self.row(memory_rows, _("Available RAM"), GLib.format_size(status["available"]))
            self.row(
                memory_rows,
                _("Estimated RAM in use"),
                _("{size} ({percent}%)").format(
                    size=GLib.format_size(status["used"]), percent=used_percent,
                ),
            )
            if status["swap_total"]:
                swap_percent = round(status["swap_used"] / status["swap_total"] * 100)
                swap_text = _("{used} of {total} ({percent}%)").format(
                    used=GLib.format_size(status["swap_used"]),
                    total=GLib.format_size(status["swap_total"]),
                    percent=swap_percent,
                )
            else:
                swap_text = _("No swap space is configured")
            self.row(memory_rows, _("Swap in use"), swap_text)
            message = _("Memory status updated. Available RAM: {available}. Swap: {swap}.").format(
                available=GLib.format_size(status["available"]),
                swap=swap_text,
            )

        status_label.set_text(message)
        if announce:
            self.announce_to_screen_reader(status_label, message)
        return GLib.SOURCE_REMOVE

    def refresh_resource_pressure(self, button, status_label, pressure_rows, announce=False):
        button.set_sensitive(False)
        status_label.set_text(_("Checking system pressure…"))

        def read_status():
            status = read_resource_pressure()
            GLib.idle_add(
                self.show_resource_pressure,
                button, status_label, pressure_rows, status, announce,
            )

        threading.Thread(target=read_status, daemon=True).start()

    def show_resource_pressure(self, button, status_label, pressure_rows, status, announce=False):
        button.set_sensitive(True)
        while (child := pressure_rows.get_first_child()) is not None:
            pressure_rows.remove(child)

        resource_labels = {
            "cpu": _("Tasks waiting on CPU"),
            "memory": _("Tasks waiting on memory"),
            "io": _("Tasks waiting on storage I/O"),
        }
        if not status:
            message = _("System resource pressure is not available on this system.")
        else:
            details = []
            for resource, label in resource_labels.items():
                percentage = status.get(resource, {}).get("some")
                value = (
                    _("{percent:.1f}% in the last 10 seconds").format(percent=percentage)
                    if percentage is not None else _("Not available")
                )
                self.row(pressure_rows, label, value)
                details.append(f"{label}: {value}")
                full_percentage = status.get(resource, {}).get("full")
                if resource in {"memory", "io"} and full_percentage is not None:
                    full_label = (
                        _("All tasks waiting on memory")
                        if resource == "memory"
                        else _("All tasks waiting on storage I/O")
                    )
                    full_value = _("{percent:.1f}% in the last 10 seconds").format(
                        percent=full_percentage,
                    )
                    self.row(pressure_rows, full_label, full_value)
                    details.append(f"{full_label}: {full_value}")
            message = _("System pressure updated: {details}").format(details="; ".join(details))

        status_label.set_text(message)
        if announce:
            self.announce_to_screen_reader(status_label, message)
        return GLib.SOURCE_REMOVE

    def refresh_startup_timing(self, button, status_label, timing_rows, announce=False):
        button.set_sensitive(False)
        status_label.set_text(_("Checking system startup time…"))
        while (child := timing_rows.get_first_child()) is not None:
            timing_rows.remove(child)

        def read_status():
            timing, error = read_boot_timing()
            GLib.idle_add(
                self.show_startup_timing,
                button, status_label, timing_rows, timing, error, announce,
            )

        threading.Thread(target=read_status, daemon=True).start()

    def show_startup_timing(self, button, status_label, timing_rows, timing, error, announce=False):
        button.set_sensitive(True)
        while (child := timing_rows.get_first_child()) is not None:
            timing_rows.remove(child)
        error_messages = {
            "not-installed": _("systemd-analyze is not installed."),
            "unavailable": _("Could not read system startup time."),
        }
        if error:
            message = error_messages.get(error, error_messages["unavailable"])
        elif timing:
            self.row(timing_rows, _("Reported boot timing"), timing)
            message = _("Systemd reported the startup timing above. It does not include every app started after sign-in.")
        else:
            message = error_messages["unavailable"]
        status_label.set_text(message)
        if announce:
            self.announce_to_screen_reader(status_label, message)
        return GLib.SOURCE_REMOVE

    def refresh_startup_chain(self, button, status_label, chain_label, announce=False):
        button.set_sensitive(False)
        chain_label.set_visible(False)
        chain_label.set_text("")
        status_label.set_text(_("Inspecting the graphical startup chain…"))

        def read_chain():
            chain, error = read_boot_critical_chain()
            GLib.idle_add(
                self.show_startup_chain,
                button, status_label, chain_label, chain, error, announce,
            )

        threading.Thread(target=read_chain, daemon=True).start()

    def show_startup_chain(self, button, status_label, chain_label, chain, error, announce=False):
        button.set_sensitive(True)
        error_messages = {
            "not-installed": _("systemd-analyze is not installed."),
            "unavailable": _("Could not read the graphical startup chain."),
        }
        if error:
            message = error_messages.get(error, error_messages["unavailable"])
        elif chain:
            chain_label.set_text(chain)
            chain_label.set_visible(True)
            message = _("Systemd's critical chain to graphical.target is shown. It is one dependency path and does not prove a unit is faulty.")
        else:
            message = error_messages["unavailable"]
        status_label.set_text(message)
        if announce:
            self.announce_to_screen_reader(status_label, message)
        return GLib.SOURCE_REMOVE

    def refresh_failed_services(self, button, status_label, service_rows, announce=False):
        button.set_sensitive(False)
        status_label.set_text(_("Checking system service status…"))

        def read_status():
            services, error = read_failed_services()
            GLib.idle_add(
                self.show_failed_services,
                button, status_label, service_rows, services, error, announce,
            )

        threading.Thread(target=read_status, daemon=True).start()

    def show_failed_services(self, button, status_label, service_rows, services, error, announce=False):
        button.set_sensitive(True)
        while (child := service_rows.get_first_child()) is not None:
            service_rows.remove(child)

        error_messages = {
            "not-installed": _("The system service manager is not available."),
            "timeout": _("The system service manager did not respond in time."),
            "unavailable": _("Could not read system service status."),
        }
        if error:
            message = error_messages.get(error, error_messages["unavailable"])
        elif services:
            for unit, description in services:
                self.row(service_rows, unit, description or _("No description available"))
            message = _("{count} service units are marked as failed.").format(count=len(services))
        else:
            message = _("No failed system services are reported.")

        status_label.set_text(message)
        if announce:
            self.announce_to_screen_reader(status_label, message)
        return GLib.SOURCE_REMOVE

    def refresh_temperature_status(self, button, status_label, temperature_rows, announce=False):
        button.set_sensitive(False)
        status_label.set_text(_("Checking temperature sensors…"))

        def read_status():
            sensors = read_temperature_sensors()
            GLib.idle_add(
                self.show_temperature_status,
                button, status_label, temperature_rows, sensors, announce,
            )

        threading.Thread(target=read_status, daemon=True).start()

    def show_temperature_status(self, button, status_label, temperature_rows, sensors, announce=False):
        button.set_sensitive(True)
        while (child := temperature_rows.get_first_child()) is not None:
            temperature_rows.remove(child)

        if sensors:
            for sensor in sensors:
                temperature = sensor["temperature_c"]
                value = _("{temperature:.1f} °C").format(temperature=temperature)
                if "critical_c" in sensor:
                    value = _("{temperature:.1f} °C · critical threshold {critical:.1f} °C").format(
                        temperature=temperature, critical=sensor["critical_c"],
                    )
                self.row(temperature_rows, sensor["name"], value)
            message = _("Temperature status updated: {count} sensors found.").format(count=len(sensors))
        else:
            message = _("No temperature sensors are exposed by Linux on this system.")

        status_label.set_text(message)
        if announce:
            self.announce_to_screen_reader(status_label, message)
        return GLib.SOURCE_REMOVE

    def show_apt_update_status(self, button, status_label, update_rows, status, error, reboot_required=None, announce=False):
        self.reset_update_status(
            button, update_rows, reboot_required
        )

        error_messages = {
            "not-installed": _("APT package tools are not available."),
            "timeout": _("The local package check took too long. Try again later."),
            "unavailable": _("Could not read update status from the local package lists."),
        }
        if error or not status:
            message = error_messages.get(error, error_messages["unavailable"])
        else:
            self.row(
                update_rows,
                _("Packages ready to upgrade"),
                str(status["upgradeable"]),
            )
            self.row(
                update_rows,
                _("Packages kept back"),
                str(status["held_back"]),
            )
            last_updated = status.get("last_updated")
            if last_updated is None:
                updated_text = _("Not available")
            else:
                updated_text = GLib.DateTime.new_from_unix_local(last_updated).format("%x %H:%M")
            self.row(update_rows, _("Package lists last updated"), updated_text)
            if status["upgradeable"]:
                message = _("{count} package updates appear in the cached lists. Open Software Updater to refresh the lists and review available updates. Nothing was installed.").format(count=status["upgradeable"])
            else:
                message = _("No package updates appear in the cached lists. The lists may be out of date; open Software Updater to check for current updates. Nothing was installed.")

        status_label.set_text(message)
        if announce:
            self.announce_to_screen_reader(status_label, message)
        return GLib.SOURCE_REMOVE

    def show_automatic_update_status(self, button, status_label, update_rows, status, error, announce=False):
        button.set_sensitive(True)
        while (child := update_rows.get_first_child()) is not None:
            update_rows.remove(child)

        if error or not status:
            errors = {
                "not-installed": _("APT configuration tools are not installed."),
                "unavailable": _("Could not read the local automatic update configuration."),
            }
            message = errors.get(error, errors["unavailable"])
        else:
            labels = {
                True: _("Enabled"),
                False: _("Disabled"),
                None: _("Not available"),
            }
            self.row(update_rows, _("APT automatic upgrade setting"), labels[status["configured"]])
            package_labels = {
                True: _("Installed"),
                False: _("Not installed"),
                None: _("Not available"),
            }
            self.row(update_rows, _("unattended-upgrades package"), package_labels[status["package_installed"]])
            self.row(update_rows, _("Daily upgrade timer"), labels[status["timer_enabled"]])
            last_trigger = status.get("last_trigger")
            if last_trigger is None:
                last_trigger_text = _("Not available")
            else:
                last_trigger_text = GLib.DateTime.new_from_unix_local(last_trigger).format("%x %H:%M")
            self.row(update_rows, _("Last scheduled timer trigger"), last_trigger_text)

            if status["configured"] is False:
                message = _("Automatic APT upgrades are disabled in the merged configuration. Review Software & Updates or ask your administrator.")
            elif status["configured"] is True and status["package_installed"] is False:
                message = _("APT is configured for automatic upgrades, but the unattended-upgrades package is not installed. Review Software & Updates or ask your administrator.")
            elif status["configured"] is True and status["timer_enabled"] is False:
                message = _("APT is configured for automatic upgrades, but the daily systemd timer is not enabled. Review Software & Updates or ask your administrator.")
            elif all(status[key] is True for key in ("configured", "package_installed", "timer_enabled")):
                message = _("APT automatic upgrades are configured and the daily timer is enabled. This does not confirm a successful recent run or which repositories are allowed.")
            else:
                message = _("Could not confirm the full automatic update setup. Review Software & Updates or ask your administrator.")

        status_label.set_text(message)
        if announce:
            self.announce_to_screen_reader(status_label, message)
        return GLib.SOURCE_REMOVE

    def show_battery_status(self, button, status_label, battery_rows, batteries, announce=False, power_profile="unavailable"):
        button.set_sensitive(True)
        while (child := battery_rows.get_first_child()) is not None:
            battery_rows.remove(child)

        battery_states = {
            "Charging": _("Charging"),
            "Discharging": _("Discharging"),
            "Full": _("Full"),
            "Not charging": _("Not charging"),
            "Unknown": _("Unknown"),
        }
        profiles = {
            "power-saver": _("Power saver"),
            "balanced": _("Balanced"),
            "performance": _("Performance"),
        }
        if power_profile in profiles:
            self.row(
                battery_rows,
                _("Active power profile"),
                profiles[power_profile],
            )
        else:
            self.row(
                battery_rows,
                _("Active power profile"),
                _("Power profile information is not available on this system."),
            )
        if batteries:
            summaries = []
            for index, battery in enumerate(batteries, start=1):
                title = _("Battery {number}").format(number=index)
                state = battery_states.get(battery["status"], battery_states["Unknown"])
                charge = _("Charge: {capacity}% · {status}").format(
                    capacity=battery["capacity"], status=state,
                )
                self.row(battery_rows, title, charge)
                summary_parts = [_("{capacity}% · {status}").format(
                    capacity=battery["capacity"], status=state,
                )]
                charge_end = battery.get("charge_end_threshold")
                if isinstance(charge_end, int):
                    charge_start = battery.get("charge_start_threshold")
                    if isinstance(charge_start, int):
                        charge_limit = _(
                            "Charging resumes below {start}% and stops at {end}%."
                        ).format(start=charge_start, end=charge_end)
                    else:
                        charge_limit = _("Charging stops at {end}%.").format(end=charge_end)
                    self.row(battery_rows, _("Charge limit"), charge_limit)
                    summary_parts.append(charge_limit)
                if "design_capacity_percent" in battery:
                    self.row(
                        battery_rows,
                        _("Estimated capacity vs. design"),
                        _("{percent}% of original design capacity").format(
                            percent=battery["design_capacity_percent"],
                        ),
                    )
                if "cycle_count" in battery:
                    self.row(
                        battery_rows,
                        _("Reported charge cycles"),
                        str(battery["cycle_count"]),
                    )
                    summary_parts.append(_("Charge cycles: {count}").format(
                        count=battery["cycle_count"],
                    ))
                if "state_of_health_percent" in battery:
                    self.row(
                        battery_rows,
                        _("Reported battery health"),
                        _("{percent}%").format(
                            percent=battery["state_of_health_percent"],
                        ),
                    )
                    summary_parts.append(_("Battery-reported health: {percent}%").format(
                        percent=battery["state_of_health_percent"],
                    ))
                summaries.append(" · ".join(summary_parts))
            message = _("Battery status updated: {details}").format(details="; ".join(summaries))
        else:
            message = _("No battery information found. This computer may not have a battery, or the system does not expose battery data.")
            self.row(battery_rows, _("No battery information"), message)

        status_label.set_text(message)
        if announce:
            self.announce_to_screen_reader(status_label, message)
        return GLib.SOURCE_REMOVE

    def show_audio_status(self, output_row, input_row, status, announce=False):
        error = status.get("error")
        if error == "not-installed":
            unavailable = _("PipeWire and PulseAudio tools are not installed")
        else:
            unavailable = _("No default audio device or volume status is available")
        announcements = []
        for row, key in ((output_row, "output"), (input_row, "input")):
            reading = status.get(key)
            if not isinstance(reading, tuple):
                message = (
                    f"{unavailable}. " + _("Open Sound Settings to choose a default device.")
                    if error else
                    _("No default device is available. Open Sound Settings to choose a default device.")
                )
                row.set_subtitle(message)
                announcements.append(f"{row.get_title()}: {message}")
                continue
            percent, muted = reading
            state = _("Muted") if muted else _("Not muted")
            name = status.get(f"{key}_name")
            volume_state = _("{percent}% · {state}").format(percent=percent, state=state)
            if muted:
                volume_state += " · " + _("Open Sound Settings to unmute this device.")
            elif percent == 0:
                volume_state += " · " + (
                    _("Raise the output volume in Sound Settings.")
                    if key == "output" else
                    _("Raise the input volume in Sound Settings.")
                )
            message = f"{name} · {volume_state}" if isinstance(name, str) and name else volume_state
            row.set_subtitle(message)
            announcements.append(f"{row.get_title()}: {message}")
        if announce:
            self.announce_to_screen_reader(output_row, " ".join(announcements))
        return GLib.SOURCE_REMOVE

    def show_network_status(
        self, status_label, device_rows, devices, error, announce=False,
        wifi_details=None, interface_ips=None, adapter_details=None,
    ):
        errors = {
            "not-installed": _("NetworkManager command-line tools are not installed."),
            "timeout": _("NetworkManager did not respond in time. Try refreshing again."),
            "unavailable": _("Could not read device status from NetworkManager."),
        }
        if error:
            message = errors.get(error, errors["unavailable"])
            status_label.set_text(message)
            if announce:
                self.announce_to_screen_reader(status_label, message)
            return GLib.SOURCE_REMOVE
        if not devices:
            message = _("NetworkManager reported no network devices.")
            status_label.set_text(message)
            if announce:
                self.announce_to_screen_reader(status_label, message)
            return GLib.SOURCE_REMOVE

        message = _("This is local device status; internet access has not been tested.")
        status_label.set_text(message)
        device_types = {
            "wifi": _("Wi-Fi"),
            "ethernet": _("Wired"),
            "wwan": _("Mobile broadband"),
            "bridge": _("Bridge"),
            "vpn": _("VPN"),
        }
        states = {
            "connected": _("Connected"),
            "disconnected": _("Disconnected"),
            "connecting": _("Connecting"),
            "unavailable": _("Unavailable"),
            "unmanaged": _("Not managed by NetworkManager"),
            "unavailable (firmware missing)": _("Unavailable (missing firmware)"),
        }
        device_announcements = []
        for name, device_type, state in devices:
            title = f"{device_types.get(device_type, device_type)} · {name}"
            subtitle = states.get(state, state)
            adapter = (adapter_details or {}).get(name, {})
            metrics = (wifi_details or {}).get(name, {})
            details = []
            if adapter.get("name"):
                details.append(adapter["name"])
            if adapter.get("bus") and adapter.get("id"):
                details.append(_("Hardware ID: {bus} {id}").format(
                    bus=adapter["bus"], id=adapter["id"],
                ))
            if adapter.get("driver"):
                details.append(_("Kernel driver: {driver}").format(driver=adapter["driver"]))
            if "signal_dbm" in metrics:
                details.append(_("Signal: {dbm} dBm").format(dbm=metrics["signal_dbm"]))
            if "rx_bitrate_mbps" in metrics:
                details.append(_("Receive rate: {rate} Mbit/s").format(rate=metrics["rx_bitrate_mbps"]))
            if "tx_bitrate_mbps" in metrics:
                details.append(_("Transmit rate: {rate} Mbit/s").format(rate=metrics["tx_bitrate_mbps"]))
            addresses = (interface_ips or {}).get(name)
            if addresses is not None:
                if addresses["ipv4"] and addresses["ipv6"]:
                    details.append(_("IPv4 and IPv6 addresses assigned"))
                elif addresses["ipv4"]:
                    details.append(_("IPv4 address assigned"))
                elif addresses["ipv6"]:
                    details.append(_("IPv6 address assigned"))
                elif addresses["link_local"]:
                    details.append(_("Only link-local addresses assigned"))
                else:
                    details.append(_("No IP address assigned"))
            if details:
                subtitle = f"{subtitle} · {' · '.join(details)}"
            self.row(device_rows, title, subtitle)
            device_announcements.append(f"{title}: {subtitle}")
        if announce:
            announcement = _("Network status updated: {details}").format(
                details="; ".join(device_announcements),
            )
            self.announce_to_screen_reader(status_label, announcement)
        return GLib.SOURCE_REMOVE

    def make_drivers(self):
        box, rows = self.page(_("Graphics drivers"), _("Ubuntu can offer compatible drivers for some graphics hardware. Review the available choices in Ubuntu’s Additional Drivers tool before installing anything."))
        self.row(rows, _("Review available drivers"), _("This opens Ubuntu’s driver tool. Read the recommendation and confirm any changes there."), _("Open Drivers"), lambda: self.open_app("software-properties-gtk", "--open-tab=4"))
        self.row(rows, _("Secure Boot"), _("Some drivers need a one-time confirmation during restart when Secure Boot is enabled. Follow Ubuntu’s on-screen instructions."))
        self.secure_boot_status_row = Adw.ActionRow(
            title=_("Secure Boot status"), subtitle=_("Not checked yet."),
        )
        rows.append(self.secure_boot_status_row)
        self.secure_boot_refresh_button = Gtk.Button(
            label=_("Check Secure Boot status"), halign=Gtk.Align.START,
        )
        self.secure_boot_refresh_button.connect(
            "clicked",
            lambda *_: self.refresh_secure_boot_status(
                self.secure_boot_refresh_button, self.secure_boot_status_row, announce=True,
            ),
        )
        box.append(self.secure_boot_refresh_button)
        box.append(Gtk.Label(
            label=_("This read-only check uses mokutil when available. It does not change firmware settings or enroll keys."),
            xalign=0, wrap=True, css_classes=["body"],
        ))
        self.refresh_secure_boot_status(
            self.secure_boot_refresh_button, self.secure_boot_status_row,
        )
        self.row(
            rows,
            _("If the graphics adapter has no name"),
            _("Adapter names come from a local PCI database. If only a PCI ID is shown, keep that ID and the driver name to identify the hardware. Choose drivers through Ubuntu’s Additional Drivers tool."),
            _("Open hardware overview"),
            lambda: self.main_stack.set_visible_child_name(_("Network and hardware")),
        )
        self.row(rows, _("Need more detail?"), _("Ubuntu’s driver guidance explains the supported installation route."), _("Open Ubuntu help"), lambda: self.open_uri("https://ubuntu.com/desktop/docs/en/latest/how-to/graphics/install-nvidia-drivers/"))
        return box

    def refresh_secure_boot_status(self, button, status_row, announce=False):
        button.set_sensitive(False)
        status_row.set_subtitle(_("Checking Secure Boot status…"))

        def read_status():
            state, error = read_secure_boot_status()
            GLib.idle_add(
                self.show_secure_boot_status, button, status_row, state, error, announce,
            )

        threading.Thread(target=read_status, daemon=True).start()

    def show_secure_boot_status(self, button, status_row, state, error, announce=False):
        button.set_sensitive(True)
        messages = {
            "enabled": _("Enabled. Some third-party drivers may require a one-time key confirmation during restart."),
            "disabled": _("Disabled. Review Ubuntu’s driver recommendation before installing a driver."),
            "setup-mode": _("The computer is in firmware Setup Mode. Check the manufacturer’s instructions before changing firmware settings."),
            "unsupported": _("Secure Boot status is not available in this boot mode."),
        }
        errors = {
            "not-installed": _("mokutil is not installed, so Secure Boot status cannot be read."),
            "timeout-or-unavailable": _("The Secure Boot status check could not finish. Try again later."),
            "unavailable": _("Could not read Secure Boot status from firmware."),
        }
        message = messages.get(state, errors.get(error, errors["unavailable"]))
        status_row.set_subtitle(message)
        if announce:
            self.announce_to_screen_reader(status_row, _("Secure Boot status: {status}").format(status=message))
        return GLib.SOURCE_REMOVE

    def refresh_root_encryption_status(self, button, status_row, announce=False):
        button.set_sensitive(False)
        status_row.set_subtitle(_("Checking root filesystem encryption…"))

        def read_status():
            state, error = read_root_encryption_status()
            GLib.idle_add(
                self.show_root_encryption_status, button, status_row, state, error, announce,
            )

        threading.Thread(target=read_status, daemon=True).start()

    def show_root_encryption_status(self, button, status_row, state, error, announce=False):
        button.set_sensitive(True)
        messages = {
            "encrypted": _("An encryption layer was detected on every reported path to the root filesystem. This does not verify other disks or every personal file."),
            "partial": _("Encryption was detected on some, but not all, reported paths to the root filesystem. Review the storage layout."),
            "unencrypted": _("No encryption layer was detected on the reported paths to the root filesystem. This check may not detect every encryption method."),
        }
        errors = {
            "not-installed": _("lsblk is not installed, so root filesystem encryption cannot be checked."),
            "timeout-or-unavailable": _("The storage layout could not be read. Try again later."),
            "unavailable": _("The storage layout did not provide enough information to check root filesystem encryption."),
        }
        message = messages.get(state, errors.get(error, errors["unavailable"]))
        status_row.set_subtitle(message)
        if announce:
            self.announce_to_screen_reader(
                status_row, _("Root filesystem encryption status: {status}").format(status=message),
            )
        return GLib.SOURCE_REMOVE

    def system_details(self):
        try:
            os_info = platform.freedesktop_os_release()
            os_name = os_info.get("PRETTY_NAME", _("Unknown Ubuntu version"))
        except (AttributeError, OSError):
            os_name = _("Unknown Ubuntu version")
        desktop = normalize_desktop_name(
            os.environ.get("XDG_CURRENT_DESKTOP"),
            os.environ.get("XDG_SESSION_DESKTOP"),
        ) or _("Not available")
        session_type_label = normalize_session_type(os.environ.get("XDG_SESSION_TYPE")) or _("Not available")
        hardware = read_hardware_details()
        graphics = "; ".join(hardware["graphics"]) if hardware["graphics"] else _("Not available")
        storage_locations = read_storage_locations()
        details = [
            (_("Ubuntu Start version"), get_application_version()),
            (_("Ubuntu version"), os_name),
            (_("Desktop"), desktop),
            (_("Session type"), session_type_label),
            (_("Desktop connection"), desktop_connection_label(read_remote_session())),
            (_("Kernel"), platform.release()),
            (_("System model"), hardware["system_model"] or _("Not available")),
            (_("Processor"), hardware["processor"] or _("Not available")),
            (_("Memory"), hardware["memory"] or _("Not available")),
            (_("Graphics adapters"), graphics),
            (_("Architecture"), platform.machine()),
        ]
        usb_devices = hardware.get("usb_devices", [])
        if usb_devices:
            usb_summaries = []
            for device in usb_devices:
                name = device["name"] or _("Unknown USB device")
                drivers = ", ".join(device["drivers"]) or _("no driver attached")
                usb_summaries.append(
                    _("{name} [{id}] (driver: {drivers})").format(
                        name=name, id=device["id"], drivers=drivers,
                    )
                )
            details.append((_("Connected USB devices"), "; ".join(usb_summaries)))
        pci_devices = hardware.get("pci_devices", [])
        if pci_devices:
            pci_summaries = []
            for device in pci_devices:
                name = device["name"] or _("PCI device")
                driver = device["driver"] or _("No kernel driver is currently attached.")
                pci_summaries.append(f"{name} [{device['id']}] ({driver})")
            details.append((_("PCI devices"), "; ".join(pci_summaries)))
        for location, storage in storage_locations.items():
            label = _("System filesystem") if location == "system" else _("Home folder filesystem")
            percent = round(storage["used"] / storage["total"] * 100) if storage["total"] else 0
            value = _("{free} free of {total} ({percent}% used)").format(
                free=GLib.format_size(storage["free"]),
                total=GLib.format_size(storage["total"]),
                percent=percent,
            )
            details.append((label, value))
            file_total = storage.get("file_entries_total")
            file_free = storage.get("file_entries_free")
            if isinstance(file_total, int) and isinstance(file_free, int) and file_total > 0:
                details.append((
                    f"{label}: {_('Available file entries')}",
                    _("{free} of {total} available ({percent}% used)").format(
                        free=locale.format_string("%d", file_free, grouping=True),
                        total=locale.format_string("%d", file_total, grouping=True),
                        percent=round((file_total - file_free) / file_total * 100),
                    ),
                ))
        return details

    def make_help(self):
        box, rows = self.page(
            _("Help and support"),
            _("Find trusted instructions and prepare useful details when you ask others for help."),
        )
        self.row(rows, _("Ubuntu Desktop guide"), _("Official help for settings, accessibility, networks and common tasks."), _("Open guide"), lambda: self.open_uri("https://help.ubuntu.com/stable/ubuntu-help/"))
        self.row(rows, _("Security and privacy guide"), _("Practical steps for updates, trusted apps, account protection, backups and network access."), _("Read security guide"), lambda: self.open_security_guide())
        self.row(rows, _("Ubuntu security documentation"), _("Official guidance on security updates, firewalls and Ubuntu security features."), _("Open security documentation"), lambda: self.open_security_documentation())
        self.row(rows, _("Ubuntu automatic security updates"), _("How Ubuntu installs security updates automatically and how to review the settings."), _("Read update guidance"), lambda: self.confirm_external_link(
            "https://documentation.ubuntu.com/security/security-updates/",
            _("Open Ubuntu update guidance?"),
            _("This opens Ubuntu’s official security update documentation in your browser. The website receives a normal web request and can see your IP address."),
        ))
        self.row(rows, _("Ubuntu guide to staying safe online"), _("Learn about safer web browsing, suspicious messages and network access."), _("Read online safety guide"), lambda: self.confirm_external_link(
            "https://help.ubuntu.com/stable/ubuntu-help/net-security.html.en",
            _("Open Ubuntu online safety guidance?"),
            _("This opens Ubuntu’s official desktop help in your browser. The website receives a normal web request and can see your IP address."),
        ))
        self.row(rows, _("Ubuntu firewall help"), _("Understand when firewall rules may be needed and how they affect network services."), _("Read firewall guide"), lambda: self.confirm_external_link(
            "https://help.ubuntu.com/stable/ubuntu-help/net-firewall-on-off.html.en",
            _("Open Ubuntu firewall guidance?"),
            _("This opens Ubuntu’s official desktop help in your browser. The website receives a normal web request and can see your IP address."),
        ))
        self.row(rows, _("Ubuntu release lifecycle"), _("Check standard support periods for LTS and interim releases."), _("View support periods"), lambda: self.confirm_external_link(
            "https://ubuntu.com/about/release-cycle",
            _("Open Ubuntu release information?"),
            _("This opens Ubuntu’s official release lifecycle page in your browser. The website receives a normal web request and can see your IP address."),
        ))
        self.row(rows, _("Ask Ubuntu"), _("Search community answers or ask a focused question about Ubuntu."), _("Open Ask Ubuntu"), lambda: self.open_uri("https://askubuntu.com/"))
        self.row(rows, _("Ubuntu community forum"), _("Get help from Ubuntu users and community members."), _("Open forum"), lambda: self.open_uri("https://discourse.ubuntu.com/c/support-and-help/306"))

        details_box, details_rows = self.page(
            _("System details"),
            _("These read-only details help explain a problem. They omit your username, computer name, serial numbers, network addresses, Wi-Fi names and installed applications."),
        )
        for label, value in self.system_details():
            self.row(details_rows, label, value)
        copy_status = Gtk.Label(label="", xalign=0, wrap=True)
        copy_button = Gtk.Button(label=_("Copy system details"), halign=Gtk.Align.START)
        copy_button.connect("clicked", lambda *_: self.review_system_details(copy_status))
        details_box.append(copy_button)
        details_box.append(copy_status)
        export_status = Gtk.Label(label="", xalign=0, wrap=True)
        export_button = Gtk.Button(label=_("Review and save support report"), halign=Gtk.Align.START)
        export_button.connect("clicked", lambda *_: self.review_support_report(export_status))
        details_box.append(export_button)
        details_box.append(export_status)
        box.append(details_box)

        tips_box, tips_rows = self.page(_("When asking for help"))
        self.row(tips_rows, _("Describe what happened"), _("Include your Ubuntu version, the device model, the exact error and what you already tried. Remove passwords and other personal details."))
        box.append(tips_box)
        return box

    def make_tips_page(self):
        box, rows = self.page(
            _("Tips and tricks"),
            _("These are Ubuntu’s default shortcuts. Open Keyboard Settings to review or change them; key labels can vary by device."),
        )
        tips = [
            (_("Find apps and settings"), _("Press the Super key and start typing the name of an app or setting.")),
            (_("Switch between apps"), _("Press Alt+Tab to move between open apps.")),
            (_("Arrange windows side by side"), _("Press Super+Left or Super+Right to place the current window on one side of the screen.")),
            (_("Open Quick Settings"), _("Select the system menu at the top-right to reach Wi-Fi, Bluetooth, sound, brightness and power controls.")),
            (_("Take a screenshot"), _("On Ubuntu GNOME, press Print to open the screenshot controls and choose a screen, window or area.")),
            (_("Show hidden files"), _("In Files, press Ctrl+H to show or hide hidden files. Be careful when changing hidden configuration files.")),
            (_("Create a folder in Files"), _("Press Ctrl+Shift+N to create a folder in the current location.")),
            (_("Open a location in Files"), _("Press Ctrl+L in Files to type a folder path or enter a network address. Press Enter to open it.")),
            (_("Rename a file"), _("Select a file in Files and press F2 to rename it. Check the new name before pressing Enter.")),
            (_("Undo a file action"), _("Press Ctrl+Z in Files to undo a recent file operation when available. Check the result before continuing.")),
            (_("Keep a backup copy"), _("Copy important documents and photos to a separate drive or trusted backup service. Check occasionally that you can open a backed-up file.")),
            (_("Choose trusted app sources"), _("Prefer Ubuntu App Center or the software source recommended by your organization. Check the publisher before installing an app.")),
            (_("Switch keyboard layouts"), _("If you have added more than one layout, press Super+Space to switch between them.")),
            (_("Lock the screen"), _("Press Super+L before leaving your computer to lock the screen.")),
            (_("Open Terminal"), _("Ctrl+Alt+T opens Terminal on Ubuntu by default. You can change this shortcut in Keyboard Settings.")),
        ]
        for title, description in tips:
            self.row(rows, title, description)
        self.row(
            rows,
            _("Keyboard shortcuts"),
            _("Review or change the shortcuts used by your desktop."),
            _("Open Keyboard Settings"),
            lambda: self.open_app("gnome-control-center", "keyboard"),
        )
        return box

    def review_system_details(self, status_label):
        report = "\n".join(f"{label}: {value}" for label, value in self.system_details())
        dialog = Adw.AlertDialog(
            heading=_("Review system details before copying"),
            body=_("Review this information before copying it. It may reveal details about your computer. Share it only with a support person you trust.\n\n{details}").format(details=report),
        )
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("copy", _("Copy"))
        dialog.set_default_response("cancel")
        dialog.connect(
            "response",
            lambda _dialog, response: self.copy_system_details(status_label, report)
            if response == "copy" else None,
        )
        dialog.present(self.get_active_window())

    def copy_system_details(self, status_label, report=None):
        display = Gdk.Display.get_default()
        if display is None:
            status_label.set_text(_("Clipboard is unavailable."))
            return
        if report is None:
            report = "\n".join(f"{label}: {value}" for label, value in self.system_details())
        display.get_clipboard().set(report)
        status_label.set_text(_("System details copied."))
        self.announce_to_screen_reader(status_label, status_label.get_text())

    def announce_to_screen_reader(self, widget, message):
        if hasattr(Gtk.Accessible, "announce"):
            Gtk.Accessible.announce(
                widget, message, Gtk.AccessibleAnnouncementPriority.MEDIUM,
            )

    def show_about(self):
        about = Adw.AboutDialog(
            application_name=_("Ubuntu Start"),
            application_icon=APP_ID,
            version=get_application_version(),
            developer_name="Daniel Nylander",
            developers=["Daniel Nylander"],
            issue_url="https://github.com/yeager/ubuntu-start/issues",
            license_type=Gtk.License.GPL_3_0_ONLY,
            comments=_("An Ubuntu Desktop guide for first-run setup and device troubleshooting."),
        )
        about.add_link(_("Daniel Nylander's website"), "https://www.danielnylander.se")
        about.add_link(_("GitHub repository"), "https://github.com/yeager/ubuntu-start")
        about.present(self.get_active_window())

    def review_support_report(self, status_label):
        report = build_support_report(self.system_details(), getattr(self, "last_network_diagnostics", None))
        window = Adw.Window(
            transient_for=self.get_active_window(), modal=True,
            title=_("Review support report"), default_width=680, default_height=560,
        )
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content.set_margin_top(18)
        content.set_margin_bottom(18)
        content.set_margin_start(18)
        content.set_margin_end(18)
        content.append(Gtk.Label(
            label=_("Review or edit this report before saving. It stays on this computer unless you choose to share it. Network addresses, MAC addresses, host names and serial numbers are omitted."),
            xalign=0, wrap=True,
        ))
        editor = Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD_CHAR, monospace=True, vexpand=True)
        editor.get_buffer().set_text(report)
        scroller = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
        scroller.set_child(editor)
        content.append(scroller)
        report_status = Gtk.Label(label="", xalign=0, wrap=True)
        content.append(report_status)
        buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8, halign=Gtk.Align.END)
        close_button = Gtk.Button(label=_("Close"))
        save_button = Gtk.Button(label=_("Save report"), css_classes=["suggested-action"])
        close_button.connect("clicked", lambda *_: window.close())
        save_button.connect(
            "clicked",
            lambda *_: self.choose_report_destination(window, editor, status_label, report_status),
        )
        buttons.append(close_button)
        buttons.append(save_button)
        content.append(buttons)
        window.set_content(content)
        window.present()

    def choose_report_destination(self, parent, editor, status_label, editor_status_label=None):
        chooser = Gtk.FileChooserNative.new(
            _("Save support report"), parent, Gtk.FileChooserAction.SAVE,
            _("Save"), _("Cancel"),
        )
        chooser.set_current_name("ubuntu-start-support-report.json")

        def on_response(dialog, response):
            if response == Gtk.ResponseType.ACCEPT:
                target = dialog.get_file()
                text = editor.get_buffer().get_text(
                    editor.get_buffer().get_start_iter(), editor.get_buffer().get_end_iter(), True,
                )
                if not is_valid_support_report(text):
                    error_label = editor_status_label or status_label
                    error_label.set_text(_("The report must be valid JSON and keep its report version and system details. Restore those fields, then save again."))
                    self.announce_to_screen_reader(error_label, error_label.get_text())
                    dialog.destroy()
                    return
                try:
                    target.replace_contents(
                        text.encode("utf-8"), None, False,
                        Gio.FileCreateFlags.REPLACE_DESTINATION, None,
                    )
                    status_label.set_text(_("Support report saved locally."))
                    self.announce_to_screen_reader(status_label, status_label.get_text())
                    parent.close()
                except GLib.Error as error:
                    self.show_error(str(error))
            dialog.destroy()

        chooser.connect("response", on_response)
        chooser.show()

    def open_app(self, executable, *args):
        try:
            Gio.Subprocess.new([executable, *args], Gio.SubprocessFlags.NONE)
        except GLib.Error as error:
            self.show_error(str(error))

    def open_uri(self, uri):
        try:
            Gio.AppInfo.launch_default_for_uri(uri, None)
        except GLib.Error as error:
            self.show_error(str(error))

    def show_error(self, detail):
        dialog = Adw.AlertDialog(heading=_("Could not open the requested tool"), body=detail)
        dialog.add_response("close", _("Close"))
        dialog.present(self.get_active_window())

    def add_display_status(self, parent):
        display_box, _display_rows = self.page(
            _("Display connection status"),
            _("Read connection state and resolutions reported by Linux for display connectors. Resolution lists do not show the currently selected resolution or refresh rate. The check does not read monitor identifiers or change display settings. Some graphics drivers and virtual machines expose limited connector data."),
            include_rows=False,
        )
        display_status = Gtk.Label(label="", xalign=0, wrap=True)
        display_rows = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE, css_classes=["boxed-list"])
        display_refresh = Gtk.Button(label=_("Refresh display status"), halign=Gtk.Align.START)
        display_refresh.connect(
            "clicked",
            lambda *_: self.refresh_display_status(display_refresh, display_status, display_rows, announce=True),
        )
        display_guide_button = Gtk.Button(label=_("Open external display guide"), halign=Gtk.Align.START)
        display_guide_button.connect("clicked", lambda *_: self.open_display_guide())
        display_box.append(display_refresh)
        display_box.append(display_guide_button)
        display_box.append(display_status)
        display_box.append(display_rows)
        parent.append(display_box)
        self.refresh_display_status(display_refresh, display_status, display_rows)
        return parent

    def refresh_display_status(self, button, status_label, display_rows, announce=False):
        button.set_sensitive(False)
        status_label.set_text(_("Reading display connector status…"))
        while (child := display_rows.get_first_child()) is not None:
            display_rows.remove(child)

        def read_status():
            connectors = read_display_connectors()
            GLib.idle_add(
                self.show_display_status, button, status_label, display_rows, connectors, announce,
            )

        threading.Thread(target=read_status, daemon=True).start()

    def show_display_status(self, button, status_label, display_rows, connectors, announce=False):
        button.set_sensitive(True)
        while (child := display_rows.get_first_child()) is not None:
            display_rows.remove(child)
        connection_states = {
            "connected": _("Connected"),
            "disconnected": _("Disconnected"),
            "unknown": _("Unknown"),
        }
        enabled_states = {
            "enabled": _("Active"),
            "disabled": _("Inactive"),
            "unknown": _("Unknown"),
        }
        if connectors:
            details = []
            for connector in connectors:
                connection = connection_states[connector["status"]]
                enabled = enabled_states.get(connector["enabled"])
                subtitle = f"{connection} · {enabled}" if enabled else connection
                title = _("Display connector {name}").format(name=connector["name"])
                self.row(display_rows, title, subtitle)
                details.append(f"{title}: {subtitle}")
                resolutions = connector.get("resolutions")
                resolution_count = connector.get("resolution_count")
                if resolutions:
                    resolution_text = ", ".join(resolutions)
                    if isinstance(resolution_count, int) and resolution_count > len(resolutions):
                        resolution_text = _("{resolutions}, and {count} more").format(
                            resolutions=resolution_text,
                            count=resolution_count - len(resolutions),
                        )
                    resolution_title = _("Resolutions reported by Linux")
                    self.row(display_rows, resolution_title, resolution_text)
                    details.append(f"{resolution_title}: {resolution_text}")
            if len(connectors) == 1:
                message = _("Display status updated: 1 connector found.")
            else:
                message = _("Display status updated: {count} connectors found.").format(
                    count=len(connectors),
                )
        else:
            message = _("No display connector status reported by Linux.")
            self.row(
                display_rows,
                message,
                _("A graphics driver or virtual machine may not expose connector data. Open Display Settings to check whether a monitor is detected."),
            )
            details = [message]
        status_label.set_text(message)
        if announce:
            self.announce_to_screen_reader(status_label, f"{message} {'; '.join(details)}")
        return GLib.SOURCE_REMOVE

    def open_display_guide(self):
        display_index = next(
            index for index, (title, _target, _steps) in enumerate(GUIDES)
            if title == _("External display or projector")
        )
        self.device_search.set_text("")
        self.device_chooser.set_selected(display_index)
        self.main_stack.set_visible_child_name(_("Fix a device"))

    def add_printer_controls(self, parent, refresh_button, status_label):
        parent.append(refresh_button)
        guide_button = Gtk.Button(label=_("Open print queue guide"), halign=Gtk.Align.START)
        guide_button.connect("clicked", lambda *_: self.open_printer_guide())
        parent.append(guide_button)
        parent.append(status_label)

    def read_update_status(self):
        status, error = read_apt_update_status()
        return status, error, read_reboot_required()

    def reset_update_status(self, button, update_rows, reboot_required):
        button.set_sensitive(True)
        while (child := update_rows.get_first_child()) is not None:
            update_rows.remove(child)
        reboot_state = (
            _("Required") if reboot_required is True
            else _("Not required") if reboot_required is False
            else _("Not available")
        )
        self.row(update_rows, _("Restart required"), reboot_state)

    def printer_queue_status(self, state, pending_jobs, labels):
        status = labels.get(state, _("Status unknown"))
        if pending_jobs is None:
            unavailable = _("Unfinished job count unavailable")
            return f"{status} · {unavailable}"
        job_count = _n(
            "{count} unfinished print job",
            "{count} unfinished print jobs",
            pending_jobs,
        ).format(count=pending_jobs)
        return f"{status} · {job_count}"

    def open_printer_guide(self):
        printer_index = next(
            index for index, (title, _target, _steps) in enumerate(GUIDES)
            if title == _("Print job is stuck or the queue is paused")
        )
        self.device_search.set_text("")
        self.device_chooser.set_selected(printer_index)
        self.main_stack.set_visible_child_name(_("Fix a device"))


GUIDES.extend([
    (_("Print job is stuck or the queue is paused"), "printers", [
        (_("Check the printer itself"), _("Check its display or status lights, power, paper, open covers, and ink or toner before sending the job again.")),
        (_("Refresh the local queue"), _("Open Network and hardware and refresh Printer queue status. The queue state and unfinished-job count can show whether work is waiting or the queue is paused.")),
        (_("Review the queue in Printer Settings"), _("Open Printer Settings and inspect the queue. Cancel only a job you own and are ready to discard. On a shared printer, ask its owner or administrator before changing other jobs.")),
        (_("Send one test page"), _("After fixing the cause, send one test page. Avoid resending the same document repeatedly if it does not print.")),
    ]),
    (_("Wi-Fi is slow or keeps disconnecting"), "wifi", [
        (_("Compare the connection near the router"), _("Move closer to the router and try the same task again. If it works better nearby, distance or obstacles may be weakening the signal.")),
        (_("Check the active Wi-Fi link"), _("Refresh Network status on the Network and hardware page. When available, signal values closer to 0 dBm are stronger. Receive and transmit rates describe the Wi-Fi link, not your measured internet speed.")),
        (_("Compare the Wi-Fi link with internet reachability"), _("On Network and hardware, run Test DNS and gateway, then Test internet connection. These checks ask first and show elapsed times. DNS and gateway results help compare the configured resolver with the local router; the HTTPS check confirms whether ubuntu.com responds. None measures download speed or proves the cause of a slowdown.")),
        (_("Compare another device or service"), _("Try another device on the same Wi-Fi and another app or website. If several devices have trouble, check the router or ask your internet provider. If only this computer is affected, check its adapter and Ubuntu updates.")),
        (_("Look for nearby channel overlap"), _("The Wi-Fi guide links to WiFi Analyzer, a separate project for comparing nearby signal levels and channel use. Select View on GitHub to read about it; this opens an external project page after confirmation. Ask the network owner before changing router settings.")),
        (_("Keep private details out of support requests"), _("Share the adapter model, hardware ID and driver if you need help. Do not share the Wi-Fi password or private network details.")),
    ]),
    (_("Wi-Fi is connected but the internet does not work"), "network", [
        (_("Check whether the problem affects other devices"), _("Try another device on the same network and try a different website or app. If several devices are affected, check the router or contact the internet provider.")),
        (_("Look for a network sign-in page"), _("Public Wi-Fi in places such as hotels, libraries and airports may require a sign-in page, sometimes called a captive portal. Open a browser and follow the network's instructions only if you expected this page. Do not ignore certificate warnings or enter sensitive account details on an unfamiliar page.")),
        (_("Check the VPN if you use one"), _("A VPN or managed work or school policy can affect internet access. Check its status and ask your administrator for help; do not bypass your organization's VPN or security policy.")),
        (_("Run the optional connection checks"), _("On the Network and hardware page, you can choose Test DNS and gateway or Test internet connection. Each test asks first and shows its duration. DNS uses your configured resolver, gateway ping stays on the local network, and the internet test contacts ubuntu.com.")),
        (_("Review network settings"), _("Open Network Settings and check that the expected Wi-Fi or wired connection is active. Avoid changing proxy, DNS or manual IP settings unless your network administrator or provider gives you the correct values.")),
    ]),
])

SYSTEM_GUIDES.append((_("Use Mouse Keys"), ("settings", "universal-access"), _("Open Accessibility Settings"), [
    (_("Open Pointing and Clicking"), _("In Accessibility Settings, open the Pointing and Clicking section.")),
    (_("Turn on Mouse Keys"), _("Mouse Keys lets you control the pointer with the numeric keypad. Turn Num Lock off to use the keypad for pointer movement.")),
    (_("Test it and turn it off if needed"), _("Try moving the pointer and clicking a simple target. Return to Pointing and Clicking to turn Mouse Keys off when you are finished.")),
]))


def add_benchmark_comparison_note(message: str) -> str:
    """Explain why one result should not be treated as a definitive change."""
    return message + "\n" + _(
        "Results can vary between runs. Compare several runs under similar conditions before drawing conclusions."
    )


def format_milliseconds(value: int | float) -> str:
    """Format a latency value with the active locale's decimal separator."""
    value = float(value)
    precision = 0 if value.is_integer() else 1
    formatted = f"{value:.{precision}f}"
    decimal_point = locale.localeconv().get("decimal_point") or "."
    return formatted.replace(".", decimal_point, 1)


_n = gettext.ngettext


def desktop_connection_label(remote_session: bool | None) -> str:
    """Describe local/remote access without displaying a remote host identity."""
    if remote_session is True:
        return _("Remote desktop")
    if remote_session is False:
        return _("Local desktop")
    return _("Not available")


def main():
    app = UbuntuStart()
    return app.run(None)

if __name__ == "__main__":
    raise SystemExit(main())
