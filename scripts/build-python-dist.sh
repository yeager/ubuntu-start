#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
build_dir=${1:-"$root/build/python-dist"}
mkdir -p "$build_dir/python-dist"

while IFS= read -r language || [ -n "$language" ]; do
    case "$language" in
        ''|'#'*) continue ;;
    esac
    catalog="$root/po/$language.po"
    output_dir="$build_dir/locale/$language/LC_MESSAGES"
    package_dir="$root/packaging/pypi/locale/$language/LC_MESSAGES"
    mkdir -p "$output_dir" "$package_dir"
    msgfmt --check --check-format "$catalog" -o "$output_dir/ubuntu-start.mo"
    install -m 0644 "$output_dir/ubuntu-start.mo" "$package_dir/ubuntu-start.mo"
done < "$root/po/LINGUAS"

printf 'Prepared Python distribution assets in %s\n' "$build_dir"
