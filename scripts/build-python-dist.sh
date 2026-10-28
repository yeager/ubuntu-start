#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
build_dir=${1:-"$root/build/python-dist"}
mkdir -p "$build_dir/locale/sv/LC_MESSAGES" "$build_dir/python-dist"
mkdir -p "$root/packaging/pypi/locale/sv/LC_MESSAGES"

msgfmt --check --check-format "$root/po/sv.po" -o "$build_dir/locale/sv/LC_MESSAGES/ubuntu-start.mo"
install -m 0644 "$build_dir/locale/sv/LC_MESSAGES/ubuntu-start.mo" "$root/packaging/pypi/locale/sv/LC_MESSAGES/ubuntu-start.mo"

printf 'Prepared Python distribution assets in %s\n' "$build_dir"
