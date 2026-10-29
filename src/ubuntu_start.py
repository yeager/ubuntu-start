#!/usr/bin/env python3
"""Ubuntu Start: a localized first-run and device troubleshooting guide."""
import gettext
import locale
import os
import platform
import shutil
import sys
import threading
import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk
from system_diagnostics import build_support_report, check_internet_connection, read_accessibility_settings, read_audio_status, read_battery_status, read_bluetooth_status, read_hardware_details, read_interface_ip_status, read_network_devices, read_printer_status, read_storage_locations, read_time_status, read_usb_devices, read_video_devices, read_wifi_link_status, run_network_diagnostics
from guide_search import find_guide_matches

APP_ID = "se.nylander.UbuntuStart"
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

GUIDES = [
    (_("Sound and microphones"), "sound", [
        (_("Choose the right devices"), _("Open Sound Settings and select the speakers or headphones you want to use.")),
        (_("Check the volume"), _("Make sure output volume is up and the device is not muted. Try another app or audio file.")),
        (_("Check the microphone"), _("Speak and watch the input level in Sound Settings. Check the app’s microphone permission if only one app is affected.")),
    ]),
    (_("Battery and charging"), "power", [
        (_("Check the power adapter"), _("Connect the adapter securely at both ends and try a working outlet. Stop using a cable or adapter that is damaged or unusually hot.")),
        (_("Check the charging status"), _("Review the charge level and charging state on the Network and hardware page. If it is not charging, check the power connection and Power Settings.")),
        (_("Check for battery wear"), _("If the estimated capacity is much lower than the design capacity, consult the laptop manufacturer’s support information about battery service.")),
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
        (_("Try another port or cable"), _("Use another port or cable. Check whether another device works in the same port.")),
        (_("Use hardware details when asking for help"), _("The hardware ID and driver can help support identify the device. Do not share a serial number.")),
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
    (_("Check date and time"), ("settings", "datetime"), _("Open Date & Time Settings"), [
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
        (_("Select and pair the device"), _("Choose the device from the list and confirm the pairing code on both devices if prompted.")),
        (_("Reconnect if pairing fails"), _("Remove an old pairing, restart Bluetooth on the device and computer, then try again.")),
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
        (_("Review large personal files"), _("In Files, check Downloads, Videos and other folders you recognize. Sort by size when that option is available.")),
        (_("Remove only files you recognize"), _("Move important files to a separate drive or trusted backup before deleting them. Empty the Trash only after checking its contents.")),
        (_("Leave system files alone"), _("Do not delete files from system folders or paste cleanup commands that use sudo. Ask for help if you are unsure what a file does.")),
        (_("Check storage again"), _("Return to the storage overview after cleaning up. If you need space for Ubuntu updates, run Software Updater again when enough space is available.")),
    ]),
    (_("Install Ubuntu updates"), ("app", "update-manager"), _("Open Software Updater"), [
        (_("Open Software Updater"), _("Ubuntu checks for updates when Software Updater opens. Select Check if it does not start checking.")),
        (_("Review available updates"), _("Read the update summary. Save your work before installing system updates.")),
        (_("Install and restart if asked"), _("Select Install Now and enter your password if prompted. Restart only when Ubuntu asks you to.")),
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

        pages = [
            (_("Welcome"), self.make_welcome()),
            (_("Get started"), self.make_get_started()),
            (_("Tips and tricks"), self.make_tips_page()),
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
        key_controller = Gtk.EventControllerKey()
        key_controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        key_controller.connect("key-pressed", self.on_key_pressed)
        win.add_controller(key_controller)
        win.present()

    def on_key_pressed(self, _controller, keyval, _keycode, state):
        if keyval == Gdk.KEY_f and state & Gdk.ModifierType.CONTROL_MASK:
            self.main_stack.set_visible_child_name(_("Fix a device"))
            self.device_search.grab_focus()
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
        accessibility_box, _accessibility_rows = self.page(
            _("Accessibility status"),
            _("Read selected GNOME accessibility settings. Ubuntu Start does not change them."),
            include_rows=False,
        )
        self.accessibility_box = accessibility_box
        accessibility_status = Gtk.Label(label="", xalign=0, wrap=True)
        accessibility_rows = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE, css_classes=["boxed-list"])
        accessibility_refresh = Gtk.Button(label=_("Refresh accessibility status"), halign=Gtk.Align.START)
        accessibility_refresh.connect(
            "clicked",
            lambda *_: self.refresh_accessibility_status(
                accessibility_refresh, accessibility_status, accessibility_rows, announce=True,
            ),
        )
        accessibility_box.append(accessibility_refresh)
        accessibility_box.append(accessibility_status)
        accessibility_box.append(accessibility_rows)
        box.append(accessibility_box)
        self.refresh_accessibility_status(accessibility_refresh, accessibility_status, accessibility_rows)
        time_box, _time_rows = self.page(
            _("Date and time status"),
            _("Read the local time zone and clock synchronization state. This does not change settings or start synchronization."),
            include_rows=False,
        )
        time_status = Gtk.Label(label="", xalign=0, wrap=True)
        time_rows = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE, css_classes=["boxed-list"])
        time_refresh = Gtk.Button(label=_("Refresh date and time status"), halign=Gtk.Align.START)
        time_refresh.connect(
            "clicked",
            lambda *_: self.refresh_time_status(time_refresh, time_status, time_rows, announce=True),
        )
        time_box.append(time_refresh)
        time_box.append(time_status)
        time_box.append(time_rows)
        box.append(time_box)
        self.refresh_time_status(time_refresh, time_status, time_rows)
        return box

    def open_target(self, target):
        kind, value = target
        if kind == "settings":
            self.open_app("gnome-control-center", value)
        elif kind == "terminal":
            self.open_terminal()
        elif kind == "app-center":
            self.confirm_app_center()
        elif kind == "overview" and value == "storage":
            self.main_stack.set_visible_child_name(_("Network and hardware"))
            GLib.timeout_add(50, self.scroll_to_storage_overview)
        elif kind == "overview" and value == "printer":
            self.main_stack.set_visible_child_name(_("Network and hardware"))
            GLib.timeout_add(50, self.scroll_to_printer_status)
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
            search_entries.extend(
                ("system", guide_index, guide_title, step_title, description)
                for step_title, description in steps
            )

        open_button = Gtk.Button(label=_("Open related Settings"), halign=Gtk.Align.START)
        browse.append(open_button)

        def update_guide(*_args):
            selected = chooser.get_selected()
            if selected < len(GUIDES):
                steps_stack.set_visible_child_name(f"guide-{selected}")
                open_button.set_label(
                    _("Open hardware overview")
                    if GUIDES[selected][1] == "hardware"
                    else _("Open related Settings")
                )

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
            _("NetworkManager device states help show whether Ubuntu sees a wired or wireless adapter. If the optional iw tool is installed, signal strength and link rates are read from the active Wi-Fi link; the network name is not collected and nearby networks are not scanned. Signal values closer to 0 dBm are usually stronger. Link rates are not internet speed tests."),
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

        bluetooth_box, bluetooth_rows = self.page(
            _("Bluetooth status"),
            _("Read the local controller power state only. Ubuntu Start does not scan for nearby devices."),
        )
        bluetooth_status = Adw.ActionRow(title=_("Bluetooth controller"), subtitle=_("Checking status…"))
        bluetooth_rows.append(bluetooth_status)
        bluetooth_refresh = Gtk.Button(label=_("Refresh Bluetooth status"), halign=Gtk.Align.START)
        bluetooth_refresh.connect("clicked", lambda *_: self.refresh_bluetooth_status(bluetooth_status, announce=True))
        bluetooth_box.append(bluetooth_refresh)
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
        audio_box.append(audio_refresh)
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
        printer_box.append(printer_refresh)
        printer_box.append(printer_status)
        printer_box.append(printer_rows)
        box.append(printer_box)
        self.refresh_printer_status(printer_refresh, printer_status, printer_rows)

        diagnostic_box, _diagnostic_rows = self.page(
            _("Connection quality"),
            _("The test looks up ubuntu.com using your configured DNS, pings your local gateway once, and reads its MAC address from the local neighbor table. DNS queries may be visible to your configured DNS provider; no diagnostic report is uploaded."),
            include_rows=False,
        )
        diagnostic_status = Gtk.Label(label="", xalign=0, wrap=True)
        self.last_network_diagnostics = None
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

        storage_locations = read_storage_locations()
        storage_box, storage_rows = self.page(
            _("Storage"),
            _("Local filesystem capacity. A separate home filesystem is shown when your personal files use a different mounted volume."),
        )
        self.storage_box = storage_box
        self.storage_rows = storage_rows
        for location, storage in storage_locations.items():
            title = _("System filesystem") if location == "system" else _("Home folder filesystem")
            storage_percent = round(storage["used"] / storage["total"] * 100) if storage["total"] else 0
            self.row(storage_rows, title, _("{free} free of {total} ({percent}% used)").format(
                free=GLib.format_size(storage["free"]), total=GLib.format_size(storage["total"]), percent=storage_percent,
            ))
            if storage_percent >= 95:
                warning_title = _("System filesystem is almost full") if location == "system" else _("Home folder filesystem is almost full")
                self.row(storage_rows, warning_title, _("Remove files you no longer need or review large downloads. Ubuntu may need free space for updates. Avoid deleting system files."))
        box.append(storage_box)

        battery_box, _battery_rows = self.page(
            _("Battery"),
            _("Charge level and charging state come from local system information. An estimated capacity compared with the original design is shown only if the battery exposes both values."),
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
        battery_box.append(battery_refresh)
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
            (_("System model"), hardware["system_model"]),
            (_("Processor"), hardware["processor"]),
            (_("Memory"), hardware["memory"]),
            (_("Graphics adapters"), "; ".join(hardware["graphics"]) if hardware["graphics"] else None),
            (_("Architecture"), hardware["architecture"]),
        ]
        for label, value in values:
            self.row(hardware_rows, label, value or _("Not available"))
        box.append(hardware_box)

        usb_box, _usb_rows = self.page(
            _("Connected USB devices"),
            _("This local list reads USB device names and bound kernel drivers. Serial numbers are not read."),
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
        return box

    def refresh_usb_status(self, button, status_label, device_rows, announce=False):
        button.set_sensitive(False)
        status_label.set_text(_("Reading USB devices…"))

        def read_status():
            devices = read_usb_devices()
            GLib.idle_add(
                self.show_usb_status, button, status_label, device_rows, devices, announce,
            )

        threading.Thread(target=read_status, daemon=True).start()

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
        camera_index = next(
            index for index, (title, _target, _steps) in enumerate(GUIDES)
            if title == _("Camera")
        )
        self.device_search.set_text("")
        self.device_chooser.set_selected(camera_index)
        self.main_stack.set_visible_child_name(_("Fix a device"))

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
        self.last_network_diagnostics = result
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
            lines.append(_("Next step: check Wi-Fi or wired connection in Settings. On a managed network, ask the administrator before changing route settings."))
        if result.get("dns_latency_ms") is None:
            lines.append(_("Next step: check that the network is connected and review its DNS settings."))
        if result.get("gateway") and result.get("gateway_latency_ms") is None:
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

    def show_internet_result(self, button, status_label, result):
        button.set_sensitive(True)
        if result.startswith("reachable:"):
            message = _("ubuntu.com responded. Internet access is available.")
        else:
            message = _("Could not reach ubuntu.com. Check the router, network sign-in page, DNS settings or firewall.")
        status_label.set_text(message)
        self.announce_to_screen_reader(status_label, message)
        return GLib.SOURCE_REMOVE

    def refresh_network_status(self, status_label, device_rows, announce=False):
        status_label.set_text(_("Checking NetworkManager…"))
        while (child := device_rows.get_first_child()) is not None:
            device_rows.remove(child)

        def read_status():
            devices, error = read_network_devices()
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
                error, announce, wifi_details, interface_ips,
            )

        threading.Thread(target=read_status, daemon=True).start()

    def refresh_bluetooth_status(self, status_row, announce=False):
        status_row.set_subtitle(_("Checking status…"))

        def read_status():
            status = read_bluetooth_status()
            GLib.idle_add(self.show_bluetooth_status, status_row, status, announce)

        threading.Thread(target=read_status, daemon=True).start()

    def show_bluetooth_status(self, status_row, status, announce=False):
        states = {
            "powered": _("On"),
            "off": _("Off"),
            "no-controller": _("No Bluetooth controller found"),
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
        ntp = status.get("ntp")
        self.row(
            setting_rows,
            _("Automatic time synchronization"),
            _("On") if ntp is True else _("Off") if ntp is False else _("Not available"),
        )
        synchronized = status.get("synchronized")
        sync_label = _("Synchronized") if synchronized is True else _("Not synchronized") if synchronized is False else _("Not available")
        self.row(setting_rows, _("Clock synchronization"), sync_label)
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
            for name, state in printers:
                self.row(printer_rows, name, labels.get(state, _("Status unknown")))
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
            GLib.idle_add(
                self.show_battery_status, button, status_label, battery_rows,
                batteries, announce,
            )

        threading.Thread(target=read_status, daemon=True).start()

    def show_battery_status(self, button, status_label, battery_rows, batteries, announce=False):
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
        if batteries:
            summaries = []
            for index, battery in enumerate(batteries, start=1):
                title = _("Battery {number}").format(number=index)
                state = battery_states.get(battery["status"], battery_states["Unknown"])
                charge = _("Charge: {capacity}% · {status}").format(
                    capacity=battery["capacity"], status=state,
                )
                self.row(battery_rows, title, charge)
                summaries.append(_("{capacity}% · {status}").format(
                    capacity=battery["capacity"], status=state,
                ))
                if "design_capacity_percent" in battery:
                    self.row(
                        battery_rows,
                        _("Estimated capacity vs. design"),
                        _("{percent}% of original design capacity").format(
                            percent=battery["design_capacity_percent"],
                        ),
                    )
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
                message = unavailable if error else _("No default device is available")
                row.set_subtitle(message)
                announcements.append(f"{row.get_title()}: {message}")
                continue
            percent, muted = reading
            state = _("Muted") if muted else _("Not muted")
            name = status.get(f"{key}_name")
            volume_state = _("{percent}% · {state}").format(percent=percent, state=state)
            message = f"{name} · {volume_state}" if isinstance(name, str) and name else volume_state
            row.set_subtitle(message)
            announcements.append(f"{row.get_title()}: {message}")
        if announce:
            self.announce_to_screen_reader(output_row, " ".join(announcements))
        return GLib.SOURCE_REMOVE

    def show_network_status(
        self, status_label, device_rows, devices, error, announce=False,
        wifi_details=None, interface_ips=None,
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
            metrics = (wifi_details or {}).get(name, {})
            details = []
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
        self.row(
            rows,
            _("If the graphics adapter has no name"),
            _("Adapter names come from a local PCI database. If only a PCI ID is shown, keep that ID and the driver name to identify the hardware. Choose drivers through Ubuntu’s Additional Drivers tool."),
            _("Open hardware overview"),
            lambda: self.main_stack.set_visible_child_name(_("Network and hardware")),
        )
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
        storage_locations = read_storage_locations()
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
        for location, storage in storage_locations.items():
            label = _("System filesystem") if location == "system" else _("Home folder filesystem")
            percent = round(storage["used"] / storage["total"] * 100) if storage["total"] else 0
            value = _("{free} free of {total} ({percent}% used)").format(
                free=GLib.format_size(storage["free"]),
                total=GLib.format_size(storage["total"]),
                percent=percent,
            )
            details.append((label, value))
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

    def copy_system_details(self, status_label):
        display = Gdk.Display.get_default()
        if display is None:
            status_label.set_text(_("Clipboard is unavailable."))
            return
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
            developer_name="Daniel Nylander",
            developers=["Daniel Nylander"],
            website="https://www.danielnylander.se",
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
        buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8, halign=Gtk.Align.END)
        close_button = Gtk.Button(label=_("Close"))
        save_button = Gtk.Button(label=_("Save report"), css_classes=["suggested-action"])
        close_button.connect("clicked", lambda *_: window.close())
        save_button.connect("clicked", lambda *_: self.choose_report_destination(window, editor, status_label))
        buttons.append(close_button)
        buttons.append(save_button)
        content.append(buttons)
        window.set_content(content)
        window.present()

    def choose_report_destination(self, parent, editor, status_label):
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


def main():
    app = UbuntuStart()
    return app.run(None)

if __name__ == "__main__":
    raise SystemExit(main())
