#!/usr/bin/env python3
"""Ensure every translatable source string exists in the Swedish catalog."""

from pathlib import Path
import re
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str]) -> None:
    subprocess.run(command, cwd=ROOT, check=True)


def normalized_template(path: Path) -> str:
    result = subprocess.run(
        ["msgcat", "--no-wrap", "--no-location", "--sort-output", str(path)],
        cwd=ROOT,
        capture_output=True,
        check=True,
        text=True,
    )
    return re.sub(
        r'(?m)^"POT-Creation-Date: .*\\n"$',
        r'"POT-Creation-Date: NORMALIZED\\n"',
        result.stdout,
    )


def main() -> None:
    run(["msgcmp", "po/sv.po", "po/ubuntu-start.pot"])
    with tempfile.TemporaryDirectory(prefix="ubuntu-start-l10n-") as temporary:
        template = Path(temporary) / "ubuntu-start.pot"
        run([
            "xgettext", "--from-code=UTF-8", "--language=Python", "--keyword=_",
            f"--output={template}", "src/ubuntu_start.py",
        ])
        run([
            "xgettext", "--from-code=UTF-8", "--language=Desktop", "--join-existing",
            f"--output={template}", "data/se.nylander.UbuntuStart.desktop",
        ])
        run(["msgcmp", "po/sv.po", str(template)])
        if normalized_template(ROOT / "po/ubuntu-start.pot") != normalized_template(template):
            raise SystemExit("po/ubuntu-start.pot is out of date; regenerate the gettext template")


if __name__ == "__main__":
    main()
