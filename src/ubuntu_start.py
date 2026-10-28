#!/usr/bin/env python3
"""Ubuntu Start: a localized first-run and device troubleshooting guide."""
import gettext
import locale
import os
import platform
import shutil
import threading
import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk
from system_diagnostics import check_internet_connection, read_audio_status, read_battery_status, read_bluetooth_status, read_hardware_details, read_network_devices, read_storage_status, run_network_diagnostics

APP_ID = "se.nylander.UbuntuStart"
DOMAIN = "ubuntu-start"
LOCALEDIR = os.environ.get("UBUNTU_START_LOCALEDIR", "/usr/share/locale")
locale.setlocale(locale.LC_ALL, "")
gettext.bindtextdomain(DOMAIN, LOCALEDIR)
gettext.textdomain(DOMAIN)
_ = gettext.gettext

GUIDES = [
    (_("Sound and microphones"), "sound", [
        (_("Choose the right devices"), _("Open Sound Settings and select the speakers or headphones you want to use.")),
        (_("Check the volume"), _("Make sure output volume is up and the device is not muted. Try another app or audio file.")),
        (_("Check the microphone"), _("Speak and watch the input level in Sound Settings. Check the app’s microphone permission if only one app is affected.")),
    ]),
    (_("Bluetooth"), "bluetooth", [
        (_("Check power and charge"), _("Make sure Bluetooth is enabled and the device has enough charge.")),
        (_("Turn on pairing mode"), _("Keep the device nearby and follow its instructions for pairing mode.")),
        (_("Try pairing again"), _("If an old pairing is listed, remove it in Settings, then pair the device again.")),
    ]),
    (_("Printers"), "printers", [
        (_("Check the printer"), _("Make sure it is powered on and has paper, ink or toner, and no paper jam.")),
        (_("Check the connection"), _("For a network printer, confirm it is on the same network as this computer. For USB, reconnect the cable.")),
        (_("Add the printer"), _("Open Printer Settings, add the printer and send a test page.")),
        (_("Check for a model-specific driver"), _("If printing still fails, consult Ubuntu’s documentation or the printer manufacturer before installing extra software.")),
    ]),
    (_("Displays and graphics"), "display", [
        (_("Check power and cables"), _("Make sure the display is on, the cable is connected and the correct input is selected.")),
        (_("Open Display Settings"), _("Check whether Ubuntu detects the display. Try a supported resolution and refresh rate.")),
        (_("Review graphics drivers"), _("If graphics are unstable or a feature is missing, review the drivers offered by Ubuntu before changing anything.")),
    ]),
    (_("Keyboards"), "keyboard", [
        (_("Check the connection"), _("For a wired keyboard, reconnect the cable. For a wireless keyboard, check its charge or batteries, power switch and USB receiver.")),
        (_("Check the keyboard layout"), _("Open Keyboard Settings and select the layout you intend to use. Test the keys in another app to see whether the problem is app-specific.")),
        (_("Try another port or keyboard"), _("For a USB keyboard, try another port. If available, connect another keyboard to help identify whether the problem is with the keyboard or computer.")),
    ]),
    (_("Touchpads"), "mouse", [
        (_("Make sure the touchpad is enabled"), _("Open Mouse & Touchpad Settings and check that the touchpad is switched on. Some laptops also have a keyboard shortcut that turns it off.")),
        (_("Check the surface and pointer speed"), _("Keep the touchpad clean and dry. Adjust pointer speed in Settings, then test basic movement before trying gestures.")),
        (_("Compare with an external mouse"), _("If a mouse works but the touchpad does not, check for Ubuntu updates and consult the laptop support information before changing drivers.")),
    ]),
    (_("Wi-Fi"), "wifi", [
        (_("Check Wi-Fi and airplane mode"), _("Turn airplane mode off and make sure Wi-Fi is enabled in Quick Settings.")),
        (_("Check the network"), _("See whether another device can connect. If none can, restart the router and check its internet connection.")),
        (_("Reconnect to the network"), _("Forget the network in Wi-Fi Settings, then connect again and carefully enter the password.")),
        (_("If only this computer has trouble"), _("Install available Ubuntu updates. Check the computer or Wi-Fi adapter support information before installing a driver.")),
    ]),
    (_("Camera"), "privacy", [
        (_("Check the camera"), _("Open its privacy shutter or switch, reconnect it if external and make sure its indicator light turns on.")),
        (_("Check app permissions"), _("Review camera access in Privacy Settings. A managed work or school computer may restrict access.")),
        (_("Close other camera apps"), _("Quit video calls and other apps that may already be using the camera, then try again.")),
    ]),
    (_("Wired network"), "network", [
        (_("Check the Ethernet cable"), _("Connect the cable firmly to the computer and to a router, switch or wall socket. Look for a link light near the port.")),
        (_("Wait for a connection"), _("Ubuntu normally configures a wired connection automatically. Give it a few seconds and check the network menu.")),
        (_("Check Network Settings"), _("Open Network Settings and confirm that the wired connection is enabled.")),
        (_("Try another port or cable"), _("If there is still no link, try a different cable or router port. Ask your network administrator before entering manual IP settings.")),
    ]),
]

SYSTEM_GUIDES = [
    (_("Connect to Wi-Fi"), ("settings", "wifi"), _("Open Wi-Fi Settings"), [
        (_("Open Quick Settings"), _("Select the system menu at the top-right of the screen, then open the Wi-Fi section.")),
        (_("Choose a network"), _("Select the network name you recognize. Ask its owner if you are not sure which network to use.")),
        (_("Enter the password"), _("Type the network password when Ubuntu asks, then select Connect. Never share the password in a support request.")),
        (_("Check the connection"), _("Wait for the Wi-Fi icon to settle. If it disconnects, move closer to the router and check the password.")),
    ]),
    (_("Connect with an Ethernet cable"), ("settings", "network"), _("Open Network Settings"), [
        (_("Connect the cable"), _("Plug one end into the computer and the other into a router, switch or active wall socket.")),
        (_("Wait for Ubuntu"), _("A wired connection is usually configured automatically. The network menu shows when it is ready.")),
        (_("Check the connection"), _("Open Network Settings and make sure the Wired switch is on. If there is no link light, try another port or cable.")),
    ]),
    (_("Add a printer"), ("settings", "printers"), _("Open Printer Settings"), [
        (_("Connect the printer"), _("Turn it on and connect it to the same network as your computer, or connect it with USB.")),
        (_("Add the printer"), _("Open Printers in Settings, select Add Printer and choose the printer Ubuntu finds.")),
        (_("Print a test page"), _("Follow the prompts, then print a test page. Install a model-specific driver only when Ubuntu or the manufacturer recommends it.")),
    ]),
    (_("Make text easier to read"), ("settings", "universal-access"), _("Open Accessibility Settings"), [
        (_("Open Accessibility settings"), _("In Settings, choose Accessibility and open the Seeing section.")),
        (_("Turn on Large Text"), _("Switch on Large Text. You can also try the accessibility menu in the top bar for a quick toggle.")),
        (_("Adjust other display options"), _("Try High Contrast or a different cursor size if those make the screen easier for you to use.")),
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
    (_("Install Ubuntu updates"), ("app", "update-manager"), _("Open Software Updater"), [
        (_("Open Software Updater"), _("Ubuntu checks for updates when Software Updater opens. Select Check if it does not start checking.")),
        (_("Review available updates"), _("Read the update summary. Save your work before installing system updates.")),
        (_("Install and restart if asked"), _("Select Install Now and enter your password if prompted. Restart only when Ubuntu asks you to.")),
    ]),
    (_("Use the Terminal"), ("terminal", ""), _("Open Terminal"), [
        (_("What the prompt means"), _("The prompt is the text before the cursor. It shows that the terminal is ready for a command. Type after it; do not type the prompt itself.")),
        (_("Run a command"), _("Type a command and press Enter to run it. For example, pwd shows the current folder and ls lists its files. These commands only show information.")),
        (_("Read the result"), _("Commands may print information or an error message. Read the last lines first. If a command finishes without an error, it may return to the prompt without printing anything.")),
        (_("Move between folders"), _("Use cd Documents to enter a folder and cd .. to go up one level. Use pwd to check where you are.")),
        (_("Use Tab and command history"), _("Press Tab to complete a file or folder name when it is unique. Press the Up Arrow to find a command you used earlier; check it before pressing Enter.")),
        (_("Type paths with spaces"), _("Put quotation marks around a folder or file name that contains spaces, for example: cd \"My Documents\". You can also type the first letters and press Tab to complete the name.")),
        (_("Ask a command for help"), _("Try a command followed by --help, such as ls --help. For more detail, use man followed by the command name; press q to leave the manual.")),
        (_("Understand sudo"), _("sudo runs a command with administrator privileges. Use it only when you understand and trust the command. Your password is not shown while you type it.")),
        (_("Stop a running command"), _("Ctrl+C asks the current command to stop. It does not undo changes the command has already made.")),
        (_("Keep commands from trusted sources"), _("Do not paste commands you do not understand, especially commands using sudo, rm, disk tools or scripts downloaded from the internet.")),
    ]),
]

class UbuntuStart(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.connect("activate", self.on_activate)

    def on_activate(self, app):
        win = Adw.ApplicationWindow(application=app, title=_("Ubuntu Start"), default_width=900, default_height=620)
        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        toolbar.add_top_bar(header)
        split = Adw.NavigationSplitView()
        sidebar = Adw.NavigationPage(title=_("Guide"))
        content = Adw.NavigationPage(title=_("Ubuntu Start"))
        stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
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

        pages = [
            (_("Welcome"), self.make_welcome()),
            (_("Get started"), self.make_get_started()),
            (_("Fix a device"), self.make_device_page()),
            (_("System guides"), self.make_system_guides()),
            (_("Network and hardware"), self.make_network_hardware()),
            (_("Drivers"), self.make_drivers()),
            (_("Help and support"), self.make_help()),
        ]
        for name, page in pages:
            scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
            scroller.set_child(page)
            stack.add_titled(scroller, name, name)
        stack.set_visible_child_name(pages[0][0])
        win.present()

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
        row = Adw.ActionRow(title=title, subtitle=subtitle)
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
        box, rows = self.page(_("Get started"), _("A few useful places to begin. Ubuntu may ask for your password when you change system settings."))
        for title, subtitle, target in [
            (_("Language and keyboard"), _("Choose your display language, region and keyboard layout."), ("settings", "keyboard")),
            (_("Internet connection"), _("Connect to Wi-Fi or a wired network."), ("settings", "wifi")),
            (_("Updates"), _("Check for system updates and restart if Ubuntu asks you to."), ("app", "update-manager")),
            (_("Sound and display"), _("Choose speakers, microphone and monitor settings."), ("settings", "sound")),
            (_("Privacy and screen lock"), _("Review app permissions and automatic screen locking."), ("settings", "privacy")),
            (_("Accessibility"), _("Adjust text size, magnification, screen reader and keyboard access."), ("settings", "universal-access")),
        ]:
            self.row(rows, title, subtitle, _("Open Settings"), lambda t=target: self.open_target(t))
        return box

    def open_target(self, target):
        kind, value = target
        if kind == "settings":
            self.open_app("gnome-control-center", value)
        elif kind == "terminal":
            self.open_terminal()
        else:
            self.open_app(value)

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
        search = Gtk.SearchEntry(placeholder_text=_("Search all troubleshooting steps"))
        box.append(search)
        browse = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        chooser = Gtk.DropDown.new_from_strings([title for title, _panel, _steps in GUIDES])
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

        open_button = Gtk.Button(label=_("Open related Settings"), halign=Gtk.Align.START)
        browse.append(open_button)

        def update_guide(*_):
            selected = chooser.get_selected()
            if selected < len(GUIDES):
                steps_stack.set_visible_child_name(f"guide-{selected}")

        def update_search(*_):
            query = search.get_text().strip().casefold()
            browse.set_visible(not query)
            results.set_visible(bool(query))
            while (child := result_rows.get_first_child()) is not None:
                result_rows.remove(child)
            if not query:
                return
            terms = query.split()
            count = 0
            for guide_title, _panel, steps in GUIDES:
                for step_title, description in steps:
                    searchable = f"{guide_title} {step_title} {description}".casefold()
                    if all(term in searchable for term in terms):
                        result_rows.append(Adw.ActionRow(title=f"{guide_title}: {step_title}", subtitle=description))
                        count += 1
            no_results.set_visible(count == 0)

        chooser.connect("notify::selected", update_guide)
        search.connect("search-changed", update_search)
        update_guide()
        open_button.connect("clicked", lambda *_: self.open_app("gnome-control-center", GUIDES[chooser.get_selected()][1]))
        return box

    def make_system_guides(self):
        box, _rows = self.page(
            _("System guides"),
            _("Follow clear steps for common Ubuntu tasks. Open the related system tool when you are ready to make a change."),
            include_rows=False,
        )
        chooser = Gtk.DropDown.new_from_strings([title for title, _target, _action, _steps in SYSTEM_GUIDES])
        box.append(chooser)
        guide_stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        for index, (title, target, action, steps) in enumerate(SYSTEM_GUIDES):
            guide_box, rows = self.page(title)
            for step_title, description in steps:
                self.row(rows, step_title, description)
            open_button = Gtk.Button(label=action, halign=Gtk.Align.START)
            open_button.connect("clicked", lambda *_args, t=target: self.open_target(t))
            guide_box.append(open_button)
            guide_stack.add_named(guide_box, f"system-guide-{index}")
        box.append(guide_stack)

        def select_guide(*_args):
            selected = chooser.get_selected()
            if selected < len(SYSTEM_GUIDES):
                guide_stack.set_visible_child_name(f"system-guide-{selected}")

        chooser.connect("notify::selected", select_guide)
        select_guide()
        return box

    def make_network_hardware(self):
        box, _rows = self.page(
            _("Network and hardware"),
            _("Most information comes from this computer. Network and internet checks ask before contacting the configured DNS resolver or an internet site."),
            include_rows=False,
        )

        network_box, _unused = self.page(
            _("Network status"),
            _("NetworkManager device states help show whether Ubuntu sees a wired or wireless adapter."),
            include_rows=False,
        )
        network_status = Gtk.Label(label=_("Network status has not been refreshed yet."), xalign=0, wrap=True)
        network_rows = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE, css_classes=["boxed-list"])
        refresh_button = Gtk.Button(label=_("Refresh network status"), halign=Gtk.Align.START)
        refresh_button.connect("clicked", lambda *_: self.refresh_network_status(network_status, network_rows))
        network_box.append(refresh_button)
        network_box.append(network_status)
        network_box.append(network_rows)
        box.append(network_box)
        self.refresh_network_status(network_status, network_rows)

        bluetooth_box, bluetooth_rows = self.page(
            _("Bluetooth status"),
            _("Read the local controller power state only. Ubuntu Start does not scan for nearby devices."),
        )
        bluetooth_status = Adw.ActionRow(title=_("Bluetooth controller"), subtitle=_("Checking status…"))
        bluetooth_rows.append(bluetooth_status)
        bluetooth_refresh = Gtk.Button(label=_("Refresh Bluetooth status"), halign=Gtk.Align.START)
        bluetooth_refresh.connect("clicked", lambda *_: self.refresh_bluetooth_status(bluetooth_status))
        bluetooth_box.append(bluetooth_refresh)
        box.append(bluetooth_box)
        self.refresh_bluetooth_status(bluetooth_status)

        audio_box, audio_rows = self.page(
            _("Audio status"),
            _("Read the default speaker and microphone volume and mute state. This check does not play sound or change settings."),
        )
        output_status = Adw.ActionRow(title=_("Speaker output"), subtitle=_("Checking status…"))
        input_status = Adw.ActionRow(title=_("Microphone input"), subtitle=_("Checking status…"))
        audio_rows.append(output_status)
        audio_rows.append(input_status)
        audio_refresh = Gtk.Button(label=_("Refresh audio status"), halign=Gtk.Align.START)
        audio_refresh.connect("clicked", lambda *_: self.refresh_audio_status(output_status, input_status))
        audio_box.append(audio_refresh)
        box.append(audio_box)
        self.refresh_audio_status(output_status, input_status)

        diagnostic_box, _diagnostic_rows = self.page(
            _("Connection quality"),
            _("The test looks up ubuntu.com using your configured DNS, pings your local gateway once, and reads its MAC address from the local neighbor table. DNS queries may be visible to your configured DNS provider; no diagnostic report is uploaded."),
            include_rows=False,
        )
        diagnostic_status = Gtk.Label(label="", xalign=0, wrap=True)
        diagnostic_button = Gtk.Button(label=_("Test DNS and gateway"), halign=Gtk.Align.START)
        diagnostic_button.connect("clicked", lambda *_: self.confirm_network_diagnostics(diagnostic_button, diagnostic_status))
        diagnostic_box.append(diagnostic_button)
        diagnostic_box.append(diagnostic_status)
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

        storage = read_storage_status()
        storage_percent = round(storage["used"] / storage["total"] * 100) if storage["total"] else 0
        storage_box, storage_rows = self.page(
            _("Storage"),
            _("Local filesystem capacity. Ubuntu may need free space to install updates and save files."),
        )
        self.row(storage_rows, _("Available space"), _("{free} free of {total} ({percent}% used)").format(
            free=GLib.format_size(storage["free"]), total=GLib.format_size(storage["total"]), percent=storage_percent,
        ))
        if storage_percent >= 95:
            self.row(storage_rows, _("Storage is almost full"), _("Remove files you no longer need or review large downloads. Avoid deleting system files."))
        box.append(storage_box)

        batteries = read_battery_status()
        battery_box, battery_rows = self.page(
            _("Battery"),
            _("Charge level and charging state come from local system information. An estimated capacity compared with the original design is shown only if the battery exposes both values."),
        )
        battery_states = {
            "Charging": _("Charging"),
            "Discharging": _("Discharging"),
            "Full": _("Full"),
            "Not charging": _("Not charging"),
            "Unknown": _("Unknown"),
        }
        if batteries:
            for index, battery in enumerate(batteries, start=1):
                title = _("Battery {number}").format(number=index)
                self.row(battery_rows, title, _("Charge: {capacity}% · {status}").format(
                    capacity=battery["capacity"], status=battery_states.get(battery["status"], battery_states["Unknown"]),
                ))
                if "design_capacity_percent" in battery:
                    self.row(battery_rows, _("Estimated capacity vs. design"), _("{percent}% of original design capacity").format(
                        percent=battery["design_capacity_percent"],
                    ))
        else:
            self.row(battery_rows, _("No battery information"), _("This computer may not have a battery, or the system does not expose battery data."))
        box.append(battery_box)

        hardware_box, hardware_rows = self.page(
            _("Hardware overview"),
            _("This summary reads local system files. Serial numbers are never collected."),
        )
        hardware = read_hardware_details()
        values = [
            (_("System model"), hardware["system_model"]),
            (_("Processor"), hardware["processor"]),
            (_("Memory"), hardware["memory"]),
            (_("Graphics adapters"), "; ".join(hardware["graphics"]) if hardware["graphics"] else None),
            (_("Architecture"), hardware["architecture"]),
        ]
        for label, value in values:
            self.row(hardware_rows, label, value or _("Not available"))
        box.append(hardware_box)
        return box

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
                    result = check_internet_connection()
                    GLib.idle_add(self.show_internet_result, button, status_label, result)

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
        lines = []
        if result.get("dns_latency_ms") is not None:
            lines.append(_("DNS lookup: {ms} ms").format(ms=result["dns_latency_ms"]))
        else:
            lines.append(_("DNS lookup failed. Check DNS settings or the network connection."))
        gateway = result.get("gateway")
        if gateway:
            lines.append(_("Gateway: {address}").format(address=gateway))
            if result.get("gateway_latency_ms") is not None:
                lines.append(_("Gateway response: {ms} ms").format(ms=result["gateway_latency_ms"]))
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
            lines.append(_("No default gateway was found."))
        status_label.set_text("\n".join(lines))
        return GLib.SOURCE_REMOVE

    def confirm_external_link(self, uri, heading, body):
        dialog = Adw.AlertDialog(heading=heading, body=body)
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("open", _("Open link"))
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")
        dialog.connect("response", lambda _dialog, response: self.open_uri(uri) if response == "open" else None)
        dialog.present(self.get_active_window())

    def show_internet_result(self, button, status_label, result):
        button.set_sensitive(True)
        if result.startswith("reachable:"):
            status_label.set_text(_("ubuntu.com responded. Internet access is available."))
        else:
            status_label.set_text(_("Could not reach ubuntu.com. Check the router, network sign-in page, DNS settings or firewall."))
        return GLib.SOURCE_REMOVE

    def refresh_network_status(self, status_label, device_rows):
        status_label.set_text(_("Checking NetworkManager…"))
        while (child := device_rows.get_first_child()) is not None:
            device_rows.remove(child)

        def read_status():
            devices, error = read_network_devices()
            GLib.idle_add(self.show_network_status, status_label, device_rows, devices, error)

        threading.Thread(target=read_status, daemon=True).start()

    def refresh_bluetooth_status(self, status_row):
        status_row.set_subtitle(_("Checking status…"))

        def read_status():
            status = read_bluetooth_status()
            GLib.idle_add(self.show_bluetooth_status, status_row, status)

        threading.Thread(target=read_status, daemon=True).start()

    def show_bluetooth_status(self, status_row, status):
        states = {
            "powered": _("On"),
            "off": _("Off"),
            "no-controller": _("No Bluetooth controller found"),
            "unknown": _("Power state is unknown"),
            "not-installed": _("Bluetooth command-line tool is not installed"),
            "timeout-or-unavailable": _("Bluetooth controller did not respond in time"),
            "unavailable": _("Could not read Bluetooth controller status"),
        }
        status_row.set_subtitle(states.get(status, states["unavailable"]))
        return GLib.SOURCE_REMOVE

    def refresh_audio_status(self, output_row, input_row):
        output_row.set_subtitle(_("Checking status…"))
        input_row.set_subtitle(_("Checking status…"))

        def read_status():
            status = read_audio_status()
            GLib.idle_add(self.show_audio_status, output_row, input_row, status)

        threading.Thread(target=read_status, daemon=True).start()

    def show_audio_status(self, output_row, input_row, status):
        error = status.get("error")
        if error == "not-installed":
            unavailable = _("PipeWire and PulseAudio tools are not installed")
        else:
            unavailable = _("No default audio device or volume status is available")
        for row, key in ((output_row, "output"), (input_row, "input")):
            reading = status.get(key)
            if not isinstance(reading, tuple):
                row.set_subtitle(unavailable if error else _("No default device is available"))
                continue
            percent, muted = reading
            state = _("Muted") if muted else _("Not muted")
            row.set_subtitle(_("{percent}% · {state}").format(percent=percent, state=state))
        return GLib.SOURCE_REMOVE

    def show_network_status(self, status_label, device_rows, devices, error):
        errors = {
            "not-installed": _("NetworkManager command-line tools are not installed."),
            "timeout": _("NetworkManager did not respond in time. Try refreshing again."),
            "unavailable": _("Could not read device status from NetworkManager."),
        }
        if error:
            status_label.set_text(errors.get(error, errors["unavailable"]))
            return GLib.SOURCE_REMOVE
        if not devices:
            status_label.set_text(_("NetworkManager reported no network devices."))
            return GLib.SOURCE_REMOVE

        status_label.set_text(_("This is local device status; internet access has not been tested."))
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
        for name, device_type, state in devices:
            title = f"{device_types.get(device_type, device_type)} · {name}"
            self.row(device_rows, title, states.get(state, state))
        return GLib.SOURCE_REMOVE

    def make_drivers(self):
        box, rows = self.page(_("Graphics drivers"), _("Ubuntu can offer compatible drivers for some graphics hardware. Review the available choices in Ubuntu’s Additional Drivers tool before installing anything."))
        self.row(rows, _("Review available drivers"), _("This opens Ubuntu’s driver tool. Read the recommendation and confirm any changes there."), _("Open Drivers"), lambda: self.open_app("software-properties-gtk", "--open-tab=4"))
        self.row(rows, _("Secure Boot"), _("Some drivers need a one-time confirmation during restart when Secure Boot is enabled. Follow Ubuntu’s on-screen instructions."))
        self.row(rows, _("Need more detail?"), _("Ubuntu’s driver guidance explains the supported installation route."), _("Open Ubuntu help"), lambda: self.open_uri("https://ubuntu.com/desktop/docs/en/latest/how-to/graphics/install-nvidia-drivers/"))
        return box

    def system_details(self):
        try:
            os_info = platform.freedesktop_os_release()
            os_name = os_info.get("PRETTY_NAME", _("Unknown Ubuntu version"))
        except (AttributeError, OSError):
            os_name = _("Unknown Ubuntu version")
        desktop = os.environ.get("XDG_CURRENT_DESKTOP", "GNOME").replace(":", ", ")
        hardware = read_hardware_details()
        graphics = "; ".join(hardware["graphics"]) if hardware["graphics"] else _("Not available")
        details = [
            (_("Ubuntu version"), os_name),
            (_("Desktop"), desktop),
            (_("Kernel"), platform.release()),
            (_("System model"), hardware["system_model"] or _("Not available")),
            (_("Processor"), hardware["processor"] or _("Not available")),
            (_("Memory"), hardware["memory"] or _("Not available")),
            (_("Graphics adapters"), graphics),
            (_("Architecture"), platform.machine()),
        ]
        return details

    def make_help(self):
        box, rows = self.page(
            _("Help and support"),
            _("Find trusted instructions and prepare useful details when you ask others for help."),
        )
        self.row(rows, _("Ubuntu Desktop guide"), _("Official help for settings, accessibility, networks and common tasks."), _("Open guide"), lambda: self.open_uri("https://help.ubuntu.com/stable/ubuntu-help/"))
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
        copy_button.connect("clicked", lambda *_: self.copy_system_details(copy_status))
        details_box.append(copy_button)
        details_box.append(copy_status)
        box.append(details_box)

        tips_box, tips_rows = self.page(_("When asking for help"))
        self.row(tips_rows, _("Describe what happened"), _("Include your Ubuntu version, the device model, the exact error and what you already tried. Remove passwords and other personal details."))
        box.append(tips_box)
        return box

    def copy_system_details(self, status_label):
        display = Gdk.Display.get_default()
        if display is None:
            status_label.set_text(_("Clipboard is unavailable."))
            return
        report = "\n".join(f"{label}: {value}" for label, value in self.system_details())
        display.get_clipboard().set(report)
        status_label.set_text(_("System details copied."))

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


def main():
    app = UbuntuStart()
    return app.run(None)

if __name__ == "__main__":
    raise SystemExit(main())
