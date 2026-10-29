#!/usr/bin/env python3
"""Ensure every configured translation catalog matches the source template."""

from pathlib import Path
import ast
import re
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str]) -> None:
    subprocess.run(command, cwd=ROOT, check=True)


def message_keys(path: Path) -> set[tuple[str, str, str]]:
    """Read gettext message identities without depending on xgettext formatting."""
    entries: list[dict[str, str]] = []
    entry: dict[str, str] = {}
    active_field: str | None = None

    def finish_entry() -> None:
        nonlocal entry, active_field
        if "msgid" in entry:
            entries.append(entry)
        entry = {}
        active_field = None

    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r'^(msgctxt|msgid_plural|msgid)\s+("(?:\\.|[^"\\])*")$', line)
        if match:
            field, value = match.groups()
            if field == "msgid" and "msgid" in entry:
                finish_entry()
            entry[field] = ast.literal_eval(value)
            active_field = field
        elif re.match(r"^msgstr(?:\[\d+\])?\s", line):
            active_field = None
        elif line.startswith('"') and active_field:
            entry[active_field] += ast.literal_eval(line)
        elif not line and entry:
            finish_entry()
    finish_entry()
    return {
        (entry.get("msgctxt", ""), entry["msgid"], entry.get("msgid_plural", ""))
        for entry in entries
        if entry["msgid"]
    }


def main() -> None:
    languages = [
        line.strip()
        for line in (ROOT / "po/LINGUAS").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if not languages:
        raise SystemExit("po/LINGUAS does not list any translation catalogs")
    catalogs = [ROOT / "po" / f"{language}.po" for language in languages]
    missing = [str(catalog.relative_to(ROOT)) for catalog in catalogs if not catalog.is_file()]
    if missing:
        raise SystemExit("Missing catalog(s) listed in po/LINGUAS: " + ", ".join(missing))

    for catalog in catalogs:
        run(["msgcmp", str(catalog), "po/ubuntu-start.pot"])
    with tempfile.TemporaryDirectory(prefix="ubuntu-start-l10n-") as temporary:
        template = Path(temporary) / "ubuntu-start.pot"
        run([
            "xgettext", "--from-code=UTF-8", "--language=Python", "--keyword=_", "--keyword=_n:1,2",
            f"--output={template}", "src/ubuntu_start.py",
        ])
        run([
            "xgettext", "--from-code=UTF-8", "--language=Desktop", "--join-existing",
            f"--output={template}", "data/se.danielnylander.UbuntuStart.desktop",
        ])
        for catalog in catalogs:
            run(["msgcmp", str(catalog), str(template)])
        if message_keys(ROOT / "po/ubuntu-start.pot") != message_keys(template):
            raise SystemExit("po/ubuntu-start.pot is out of date; regenerate the gettext template")


if __name__ == "__main__":
    main()
