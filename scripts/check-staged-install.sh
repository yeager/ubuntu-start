#!/bin/sh
set -eu

stage_dir=${1:?Usage: check-staged-install.sh STAGE_DIR}

required_files="
usr/libexec/ubuntu-start/ubuntu_start.py
usr/libexec/ubuntu-start/system_diagnostics.py
usr/libexec/ubuntu-start/guide_search.py
usr/share/applications/se.nylander.UbuntuStart.desktop
usr/share/metainfo/se.nylander.UbuntuStart.metainfo.xml
usr/share/icons/hicolor/512x512/apps/se.nylander.UbuntuStart.png
usr/share/locale/sv/LC_MESSAGES/ubuntu-start.mo
"

for relative_path in $required_files; do
    if [ ! -f "$stage_dir/$relative_path" ]; then
        printf 'Missing staged install file: %s\n' "$relative_path" >&2
        exit 1
    fi
done

if ! grep -Fqx 'Exec=python3 /usr/libexec/ubuntu-start/ubuntu_start.py' \
    "$stage_dir/usr/share/applications/se.nylander.UbuntuStart.desktop"; then
    printf 'Desktop launcher does not point to the installed application.\n' >&2
    exit 1
fi

if ! grep -Fqx 'Icon=se.nylander.UbuntuStart' \
    "$stage_dir/usr/share/applications/se.nylander.UbuntuStart.desktop"; then
    printf 'Desktop launcher does not name the installed application icon.\n' >&2
    exit 1
fi

if ! grep -Fqx 'Comment[sv]=Kom igång med Ubuntu och felsök anslutna enheter' \
    "$stage_dir/usr/share/applications/se.nylander.UbuntuStart.desktop"; then
    printf 'Desktop launcher is missing its Swedish description.\n' >&2
    exit 1
fi
