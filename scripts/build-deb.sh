#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
output_dir=${1:-"$root/build/packages"}
version=$(sed -n "s/^project([^,]*, version: '\([^']*\)'.*/\1/p" "$root/meson.build" | head -n 1)
if [ -z "$version" ]; then
    printf 'Could not read the project version from meson.build.\n' >&2
    exit 1
fi

temporary=$(mktemp -d "${TMPDIR:-/tmp}/ubuntu-start-deb.XXXXXX")
trap 'rm -rf "$temporary"' EXIT HUP INT TERM
build_dir="$temporary/build"
package_root="$temporary/package"

meson setup "$build_dir" "$root" --prefix=/usr
meson compile -C "$build_dir"
DESTDIR="$package_root" meson install -C "$build_dir"
sh "$root/scripts/check-staged-install.sh" "$package_root"
if ! command -v desktop-file-validate >/dev/null 2>&1; then
    printf 'desktop-file-validate is required; install desktop-file-utils.\n' >&2
    exit 1
fi
desktop-file-validate "$package_root/usr/share/applications/se.danielnylander.UbuntuStart.desktop"

install -d "$package_root/DEBIAN" "$package_root/usr/share/doc/ubuntu-start"
sed "s/@VERSION@/${version}-1/" "$root/packaging/deb/control.in" \
    > "$package_root/DEBIAN/control"
install -m 0644 "$root/LICENSE" "$package_root/usr/share/doc/ubuntu-start/copyright"
install -m 0644 "$root/README.md" "$package_root/usr/share/doc/ubuntu-start/README.md"

mkdir -p "$output_dir"
package_file="$output_dir/ubuntu-start_${version}-1_all.deb"
dpkg-deb --root-owner-group --build "$package_root" "$package_file"
printf 'Built %s\n' "$package_file"
