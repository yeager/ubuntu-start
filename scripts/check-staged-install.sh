#!/bin/sh
set -eu

stage_dir=${1:?Usage: check-staged-install.sh STAGE_DIR}
app_id=se.danielnylander.UbuntuStart
desktop_file="$stage_dir/usr/share/applications/$app_id.desktop"
metainfo_file="$stage_dir/usr/share/metainfo/$app_id.metainfo.xml"

required_files="
usr/libexec/ubuntu-start/ubuntu_start.py
usr/libexec/ubuntu-start/system_diagnostics.py
usr/libexec/ubuntu-start/guide_search.py
usr/libexec/ubuntu-start/first_run_state.py
usr/share/applications/$app_id.desktop
usr/share/metainfo/$app_id.metainfo.xml
usr/share/icons/hicolor/512x512/apps/$app_id.png
usr/share/locale/sv/LC_MESSAGES/ubuntu-start.mo
"

for relative_path in $required_files; do
    if [ ! -f "$stage_dir/$relative_path" ]; then
        printf 'Missing staged install file: %s\n' "$relative_path" >&2
        exit 1
    fi
done

if ! grep -Fqx 'Exec=python3 /usr/libexec/ubuntu-start/ubuntu_start.py' \
    "$desktop_file"; then
    printf 'Desktop launcher does not point to the installed application.\n' >&2
    exit 1
fi

launcher_path=/usr/libexec/ubuntu-start/ubuntu_start.py
if [ ! -f "$stage_dir$launcher_path" ]; then
    printf 'Desktop launcher target is not installed: %s\n' "$launcher_path" >&2
    exit 1
fi

if ! grep -Fqx "APP_ID = \"$app_id\"" \
    "$stage_dir/usr/libexec/ubuntu-start/ubuntu_start.py"; then
    printf 'Installed application ID does not match the desktop identifier.\n' >&2
    exit 1
fi

if ! grep -Fqx "Icon=$app_id" "$desktop_file"; then
    printf 'Desktop launcher does not name the installed application icon.\n' >&2
    exit 1
fi

if ! grep -Fqx 'Comment[sv]=Kom igång med Ubuntu och felsök anslutna enheter' \
    "$desktop_file"; then
    printf 'Desktop launcher is missing its Swedish description.\n' >&2
    exit 1
fi

if ! grep -Fqx "  <id>$app_id</id>" "$metainfo_file"; then
    printf 'AppStream component ID does not match the application ID.\n' >&2
    exit 1
fi

if ! grep -Fqx "  <icon type=\"stock\">$app_id</icon>" "$metainfo_file"; then
    printf 'AppStream icon ID does not match the application ID.\n' >&2
    exit 1
fi

if ! grep -Fqx "  <launchable type=\"desktop-id\">$app_id.desktop</launchable>" "$metainfo_file"; then
    printf 'AppStream launcher ID does not match the desktop file.\n' >&2
    exit 1
fi
