#!/usr/bin/env python3
"""Repair the upgrade prompt while preserving its UTF-16 resource boundary."""
from __future__ import annotations
import sys
from pathlib import Path

OLD = "Select to upgrade with[%s]".encode("utf-16le") + b"\0\0\0\0"
# Keep the original fixed-width resource slot and both UTF-16 terminators.
# The previous longer wording consumed one terminator and broke formatting.
NEW = "Confirm upgrade file: [%s]".encode("utf-16le") + b"\0\0\0\0"
EXPECTED_COPIES = 4


def patch(src: Path, dst: Path) -> None:
    data = src.read_bytes()
    count = data.count(OLD)
    if count != EXPECTED_COPIES:
        raise SystemExit(f"expected {EXPECTED_COPIES} padded English strings, found {count}")
    changed = data.replace(OLD, NEW)
    if len(changed) != len(data) or changed.count(NEW) != EXPECTED_COPIES:
        raise SystemExit("replacement changed resource size or copy count")
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(changed)
    print(f"rewrote {count} UTF-16LE prompt variants; resource size and separators unchanged")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: patch_upgrade_prompt.py INPUT.sty OUTPUT.sty")
    patch(Path(sys.argv[1]), Path(sys.argv[2]))
