# Contributing to Ubuntu Start

Thanks for helping improve Ubuntu Start. Contributions should make common Ubuntu Desktop tasks easier to understand, keep system changes in Ubuntu's own tools, and protect the user's privacy. The project is licensed under GNU GPL-3.0; see [LICENSE](LICENSE).

## Before opening a pull request

- For a larger feature or a change to how the app works, open an issue first so we can agree on the approach.
- Keep each pull request focused. Explain the problem, the change and how you checked it. Link the related issue when there is one.
- Include screenshots when a visible change is hard to understand from the description alone. Use real app screenshots and avoid personal or identifying information.
- Do not include passwords, access tokens, serial numbers, private network details or unrelated files.

## Working on the app

Ubuntu Start uses Python, GTK 4, libadwaita, Meson and gettext. Keep the English source strings in `src/ubuntu_start.py` and put user-facing text through gettext's `_()` function.

When you change user-facing strings:

1. Update `po/ubuntu-start.pot` and merge the new messages into `po/sv.po`.
2. Keep the Swedish catalog complete and natural. Translate explanations as well as labels and buttons.
3. Check the catalog with `msgfmt --check po/sv.po -o /tmp/ubuntu-start-sv.mo`.

Build the app and run its unit tests from the repository root:

```sh
meson setup build --prefix=/usr
meson compile -C build
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

For user-interface changes, launch the app on Ubuntu GNOME in English and Swedish. Check the relevant page, its navigation, keyboard use, screen-reader labels, links into GNOME Settings and any included screenshots. Pull request CI checks source-string coverage, Swedish translations, AppStream metadata, unit tests, the Meson build and a staged-install smoke check on Ubuntu 24.04 and 26.04. CI does not replace checking the changed interface.

## System and privacy changes

- Prefer read-only diagnostics and explain what information is collected.
- Do not send diagnostics or network probes outside the computer without clear user action and an explanation.
- Do not collect passwords, serial numbers, host names, IP addresses, Wi-Fi names or installed application lists for the support summary.
- Do not install packages, change system files or run commands as root. Open Ubuntu's own settings and tools when a system change is needed, and let Ubuntu ask the user to confirm it.
- Keep guidance specific and safe. Ask users to check with their administrator before entering manual network settings or changing managed devices.

## How maintainers handle incoming pull requests

1. Read the description and inspect the full diff. Confirm the change is focused, the screenshots match the code and any linked issue is addressed.
2. Check the GitHub Actions result. Review translation coverage, unit-test output and the Meson build. For UI changes, reproduce the affected flow on Ubuntu GNOME and check English and Swedish.
3. Review privacy and system behavior. Confirm diagnostics stay local, privileged actions are absent and settings changes remain under the user's control.
4. Leave specific review comments for changes needed. If the intent or behavior is unclear, ask in the pull request before approving. Recheck the updated diff after revisions.
5. Approve and merge using the merge method enabled in the repository when the change is ready. If declining a contribution, explain the reason and close the pull request respectfully.

Do not merge while required checks are failing or while a blocking review thread is unresolved. A passing build alone is not approval of the user experience or privacy behavior.

## Releases

Releases are created from version tags matching `v*`. Before tagging, update the version in `meson.build` and the matching release entry in `data/se.nylander.UbuntuStart.metainfo.xml`. Pushing the tag starts GitHub Actions, which checks source-string coverage and Swedish translations, validates AppStream metadata, runs the unit tests, builds and checks the staged installation, then publishes a source archive with a SHA-256 checksum. Check the workflow and release assets after it finishes.
