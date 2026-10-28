#!/usr/bin/env python3
"""Ubuntu Start: a localized first-run and device troubleshooting guide."""
import gettext
import locale
import os
import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")
from gi.repository import Adw, Gio, GLib, Gtk

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
            (_("Drivers"), self.make_drivers()),
        ]
        for name, page in pages:
            scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
            scroller.set_child(page)
            stack.add_titled(scroller, name, name)
        stack.set_visible_child_name(pages[0][0])
        win.present()

    def page(self, title, subtitle=None):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        heading = Gtk.Label(label=title, xalign=0, wrap=True, css_classes=["title-1"])
        box.append(heading)
        if subtitle:
            box.append(Gtk.Label(label=subtitle, xalign=0, wrap=True, css_classes=["body"]))
        rows = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE, css_classes=["boxed-list"])
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
        ]:
            self.row(rows, title, subtitle, _("Open Settings"), lambda t=target: self.open_target(t))
        return box

    def open_target(self, target):
        kind, value = target
        if kind == "settings":
            self.open_app("gnome-control-center", value)
        else:
            self.open_app(value)

    def make_device_page(self):
        box, _rows = self.page(_("Fix a device"), _("Choose a device and try these checks in order. They do not install software or change system files."))
        chooser = Gtk.DropDown.new_from_strings([title for title, _panel, _steps in GUIDES])
        box.append(chooser)
        steps_stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        for index, (_title, _panel, steps) in enumerate(GUIDES):
            group = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            group.append(Gtk.Label(label=_("Suggested checks"), xalign=0, css_classes=["title-3"]))
            rows = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE, css_classes=["boxed-list"])
            for step_title, description in steps:
                rows.append(Adw.ActionRow(title=step_title, subtitle=description))
            group.append(rows)
            steps_stack.add_named(group, f"guide-{index}")
        box.append(steps_stack)
        open_button = Gtk.Button(label=_("Open related Settings"), halign=Gtk.Align.START)
        box.append(open_button)
        def update(*_):
            selected = chooser.get_selected()
            if selected < len(GUIDES):
                steps_stack.set_visible_child_name(f"guide-{selected}")
        chooser.connect("notify::selected", update)
        update()
        open_button.connect("clicked", lambda *_: self.open_app("gnome-control-center", GUIDES[chooser.get_selected()][1]))
        return box

    def make_drivers(self):
        box, rows = self.page(_("Graphics drivers"), _("Ubuntu can offer compatible drivers for some graphics hardware. Review the available choices in Ubuntu’s Additional Drivers tool before installing anything."))
        self.row(rows, _("Review available drivers"), _("This opens Ubuntu’s driver tool. Read the recommendation and confirm any changes there."), _("Open Drivers"), lambda: self.open_app("software-properties-gtk", "--open-tab=4"))
        self.row(rows, _("Secure Boot"), _("Some drivers need a one-time confirmation during restart when Secure Boot is enabled. Follow Ubuntu’s on-screen instructions."))
        self.row(rows, _("Need more detail?"), _("Ubuntu’s driver guidance explains the supported installation route."), _("Open Ubuntu help"), lambda: self.open_uri("https://ubuntu.com/desktop/docs/en/latest/how-to/graphics/install-nvidia-drivers/"))
        return box

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
