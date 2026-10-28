# Ubuntu Start

An Ubuntu Desktop guide for first-run setup and device troubleshooting.

![Ubuntu Start app icon](data/se.nylander.UbuntuStart.png)

![Ubuntu Start welcome screen in English](screenshots/welcome-en.png)

[Swedish welcome screen](screenshots/welcome-sv.png) · [More screenshots](screenshots/)

![Search results for printer troubleshooting](screenshots/search-en.png)

![Step-by-step Wi-Fi system guide](screenshots/system-guides-en.png)

![Accessibility instructions for larger text](screenshots/accessibility-en.png)

![Read-only network and hardware overview](screenshots/network-hardware-en.png)

[More screenshots: network diagnostics (EN)](screenshots/network-diagnostics-en.png) · [audio status (EN)](screenshots/audio-status-en.png) · [Terminal guide (EN)](screenshots/terminal-guide-en.png) · [WiFi Analyzer recommendation (EN)](screenshots/wifi-analyzer-en.png) · [help page (EN)](screenshots/help-en.png) · [hardware summary (EN)](screenshots/help-hardware-en.png)

[Swedish system guides](screenshots/system-guides-sv.png) · [network and hardware overview](screenshots/network-hardware-sv.png) · [network diagnostics](screenshots/network-diagnostics-sv.png) · [audio status](screenshots/audio-status-sv.png) · [Terminal guide](screenshots/terminal-guide-sv.png) · [WiFi Analyzer recommendation](screenshots/wifi-analyzer-sv.png) · [help page](screenshots/help-sv.png) · [hardware summary](screenshots/help-hardware-sv.png) · [accessibility settings](screenshots/accessibility-panel-en.png)


Ubuntu Start combines a first-run guide with practical device troubleshooting for Ubuntu Desktop. It is a GTK 4/libadwaita application intended for Ubuntu GNOME.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for contributor guidance and the maintainer pull request review process.

## Current scope

- First steps for language, networking, updates, sound, display and privacy.
- Everyday tips for search, window management and Files, plus guidance on backups and choosing trusted app sources.
- Search device checks and step-by-step system guides together, then open a matching guide directly. Topics include sound, Bluetooth, batteries, printers, displays/graphics, keyboards, touchpads, Wi-Fi, Ethernet, cameras, accessibility and Terminal basics.
- Step-by-step guides for installing apps, updates, Wi-Fi, Ethernet, printers, batteries, keyboards, touchpads, larger text, screen magnification and the Orca screen reader.
- Accessibility guides explain larger text, zoom, screen reading, the on-screen keyboard, typing assistance and visual sound alerts, with plain-language steps before each change.
- A beginner-friendly Terminal guide explains the prompt, command output and errors, `pwd`, `ls`, `cd`, paths with spaces, Tab completion, command history, `--help`, `man`, `sudo` and safe ways to stop a command.
- Optional connection diagnostics report DNS lookup and gateway ping latency in milliseconds, plus the gateway MAC address and a local OUI vendor match. The test asks before running; it sends one DNS lookup to the configured resolver and one ping to the local gateway.
- Read-only Bluetooth status reports whether a controller is present and powered on without scanning for nearby devices.
- Read-only audio status checks the default speaker and microphone volume and mute state through PipeWire or PulseAudio without playing sounds or changing settings.
- Wi-Fi troubleshooting recommends [WiFi Analyzer](https://github.com/yeager/wifi-analyzer) for nearby signal levels and channel use. Opening GitHub requires confirmation.
- Built-in links to official Ubuntu documentation, Ask Ubuntu and the Ubuntu support forum.
- Read-only NetworkManager, Bluetooth, hardware and storage summaries, battery charge and estimated capacity versus original design when exposed, plus a copyable support report that omits usernames, host names, serial numbers, network addresses, Wi-Fi names and installed applications.
- Links into GNOME Control Center and Ubuntu's Additional Drivers tool. System changes remain in Ubuntu's own tools and require the user's confirmation.
- gettext-based localization with English source strings and a complete Swedish (`sv`) catalog.

## Build and run on Ubuntu

Install the platform dependencies, then build with Meson:

```sh
sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 gettext meson ninja-build
meson setup build --prefix=/usr
meson compile -C build
sudo meson install -C build
```

For a source checkout, run `python3 src/ubuntu_start.py` to use the English source strings. To try the Swedish catalog from the checkout:

```sh
mkdir -p build/locale/sv/LC_MESSAGES
msgfmt po/sv.po -o build/locale/sv/LC_MESSAGES/ubuntu-start.mo
LANGUAGE=sv UBUNTU_START_LOCALEDIR="$PWD/build/locale" python3 src/ubuntu_start.py
```

Run the unit tests with `PYTHONPATH=src python3 -m unittest discover -s tests -v`. The CI workflow runs these tests and builds the app for pull requests.

NetworkManager, Bluetooth, audio, storage, battery and hardware summaries use local system information. DNS/gateway tests and the WiFi Analyzer GitHub link ask for confirmation before contacting an external service; DNS uses the configured resolver, ping targets the local gateway, and vendor matching uses a local OUI file when available. The separate internet test sends one HTTPS HEAD request to `ubuntu.com` after confirmation. Opening the Ubuntu App Center asks first because it may contact configured software sources; Ubuntu Start does not install apps. Other help pages open only when selected. No diagnostic report is uploaded, and serial numbers are not read. The app expects GTK 4, libadwaita and PyGObject.

## Validation

Release `v0.3.0` passed GitHub CI and the release workflow. All 41 unit tests pass; source-string coverage, template sync, translation checks and AppStream validation pass, with 394 Swedish messages translated. On Ubuntu 26.10 machine `trv2`, Meson 1.10.1 built the release, the staged-install checker passed and the AppStream metadata validated. This verifies the build and package layout, not behavior with physical devices or a live user session. Network diagnostics were not run against the real network. Some screenshots predate the v0.3.0 guide-search, app-installation, accessibility and tips updates.

An earlier revision was also launched under Xvfb in English and Swedish. At that point PipeWire reported an unmuted default speaker at 100% and no default microphone. The GNOME Control Center panel list confirmed the Bluetooth, Wi-Fi, printer, display, privacy, sound and keyboard panel identifiers. The two Ubuntu driver/update utilities were installed with `dpkg -i`; Additional Drivers and Update Manager opened in Swedish, and `dpkg --audit` and `apt-get check` reported no package errors. These observations apply to that earlier revision. Xvfb does not verify physical-device behavior or hardware acceleration.

## Localization

English is the source and default language. The app uses the desktop locale to select translations; Swedish strings live in `po/sv.po`. Add more languages through gettext catalogs and list their language codes in `po/LINGUAS`. Regenerate the template with `xgettext` and validate catalogs with `msgfmt --check`.

See [po/README.md](po/README.md) for instructions on updating Swedish translations and contributing another language.

## Current limitations

Device troubleshooting guides are instructional. Optional network diagnostics run only after confirmation, use DNS for `ubuntu.com` and ping the local gateway, and do not upload a report. The app does not install packages or run privileged operations; system changes remain in Ubuntu's own tools. Settings panel names and the Additional Drivers launcher can differ across Ubuntu releases, so validate integrations on each supported release.


## Releases

Tagged versions (`v*`) are built and published by GitHub Actions. Each release includes a source archive and SHA-256 checksum.

## Screenshots

The screenshots show the welcome page, searchable troubleshooting, system how-to guides, accessibility settings, local network and hardware information, the support summary and Ubuntu Software & Updates. The driver-tool capture was taken while Ubuntu was still scanning for available drivers.


## License

Ubuntu Start is licensed under the GNU General Public License version 3. See [LICENSE](LICENSE).
