#!/usr/bin/env python3
"""Repair the upgrade prompt while preserving its UTF-16 resource boundary."""
from __future__ import annotations
import hashlib
import sys
from pathlib import Path

OLD = "Select to upgrade with[%s]".encode("utf-16le") + b"\0\0\0\0"
# Keep the original fixed-width resource slot and both UTF-16 terminators.
# The previous longer wording consumed one terminator and broke formatting.
NEW = "Confirm upgrade file: [%s]".encode("utf-16le") + b"\0\0\0\0"
EXPECTED_COPIES = 4
EXPECTED_SOURCE_SHA256 = frozenset(
    {
        "2abac067f05e1e2d86de72a1410c0d10e49029c103a4f9649c4888f47081907b",
        "ef1e9750d2a143c6c01ca3b07a5cb58ae72a95e19d024526fa4c07e2d3245a0c",
    }
)


def patch(src: Path, dst: Path, validate_source: bool = True) -> None:
    data = src.read_bytes()

    if validate_source:
        source_sha256 = hashlib.sha256(data).hexdigest()
        if source_sha256 not in EXPECTED_SOURCE_SHA256:
            raise SystemExit(
                "unexpected setting resource payload: "
                f"sha256={source_sha256}"
            )

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
