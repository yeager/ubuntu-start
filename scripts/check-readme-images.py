#!/usr/bin/env python3
"""Check the README image count and local image links."""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys


IMAGE_RE = re.compile(r"!\[[^\]]*\]\(([^)\s]+)(?:\s+[^)]*)?\)")


def check_readme(readme: Path, maximum: int) -> list[str]:
    text = readme.read_text(encoding="utf-8")
    images = IMAGE_RE.findall(text)
    errors = []
    if len(images) > maximum:
        errors.append(f"README contains {len(images)} embedded images; maximum is {maximum}.")
    for image in images:
        if image.startswith(("https://", "http://", "data:")):
            continue
        target = (readme.parent / image.split("#", 1)[0]).resolve()
        if not target.is_file():
            errors.append(f"README image target does not exist: {image}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("readme", nargs="?", type=Path, default=Path(__file__).resolve().parents[1] / "README.md")
    parser.add_argument("--maximum", type=int, default=6)
    args = parser.parse_args()
    errors = check_readme(args.readme, args.maximum)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"README image check passed ({len(IMAGE_RE.findall(args.readme.read_text(encoding='utf-8')))} embedded images; maximum {args.maximum}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
