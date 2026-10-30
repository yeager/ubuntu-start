#!/usr/bin/env python3
"""Ensure a version tag matches Ubuntu Start project metadata."""

from __future__ import annotations

import os
import re
import sys
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def expected_versions(root: Path = ROOT) -> tuple[str, str, str]:
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    project_version = project["project"]["version"]
    meson_text = (root / "meson.build").read_text(encoding="utf-8")
    meson_match = re.search(r"project\('ubuntu-start', version: '([^']+)'", meson_text)
    if not meson_match:
        raise ValueError("Could not read Ubuntu Start version from meson.build")
    appstream = ET.parse(root / "data/se.danielnylander.UbuntuStart.metainfo.xml")
    release = appstream.getroot().find("releases/release")
    if release is None or not release.get("version"):
        raise ValueError("Could not read latest AppStream release version")
    return project_version, meson_match.group(1), release.get("version", "")


def validate_tag(tag: str, root: Path = ROOT) -> tuple[bool, str]:
    if not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", tag):
        return False, f"Release tag must use vMAJOR.MINOR.PATCH format; got {tag!r}"
    expected = expected_versions(root)
    tag_version = tag[1:]
    if len(set(expected)) != 1:
        return False, "Project version metadata disagrees: " + ", ".join(expected)
    if tag_version != expected[0]:
        return False, f"Tag version {tag_version} does not match project version {expected[0]}"
    return True, f"Release tag {tag} matches pyproject.toml, meson.build, and AppStream metadata"


def main() -> int:
    tag = os.environ.get("RELEASE_TAG", "")
    valid, message = validate_tag(tag)
    print(message)
    return 0 if valid else 1


if __name__ == "__main__":
    sys.exit(main())
