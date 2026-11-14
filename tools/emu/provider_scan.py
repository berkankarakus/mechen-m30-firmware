#!/usr/bin/env python3
"""Scan extracted driver files for observed far-pointer literals.

This is a byte-presence tool, not a code-classification tool.  Finding a
pointer in a file does not prove that the file provides the target; absence
from all extracted drivers is useful negative evidence for the dispatcher/ROM
boundary investigation.
"""

from __future__ import annotations

import argparse
import json
import struct
from dataclasses import asdict, dataclass
from pathlib import Path


OBSERVED_POINTERS = {
    0x164C9001: "A19 + 0x001",
    0x164C90ED: "A19 + 0x0ed",
    0x26089471: "B02 + 0x471",
    0x260894E9: "B02 + 0x4e9",
    0x26409401: "B16 + 0x401",
}


@dataclass(frozen=True)
class Occurrence:
    path: str
    offset: int


def scan_file(path: Path, pointers: tuple[int, ...] = tuple(OBSERVED_POINTERS)) -> dict[int, tuple[Occurrence, ...]]:
    data = path.read_bytes()
    result: dict[int, tuple[Occurrence, ...]] = {}
    for pointer in pointers:
        needle = struct.pack("<I", pointer)
        hits: list[Occurrence] = []
        start = 0
        while True:
            offset = data.find(needle, start)
            if offset < 0:
                break
            hits.append(Occurrence(str(path), offset))
            start = offset + 1
        if hits:
            result[pointer] = tuple(hits)
    return result


def scan_driver_directory(root: Path) -> dict[int, tuple[Occurrence, ...]]:
    merged: dict[int, list[Occurrence]] = {}
    for path in sorted(root.glob("*.drv")):
        for pointer, occurrences in scan_file(path).items():
            merged.setdefault(pointer, []).extend(occurrences)
    return {pointer: tuple(items) for pointer, items in merged.items()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, help="directory containing extracted .drv files")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()
    result = scan_driver_directory(args.root)
    if args.as_json:
        payload = {
            f"0x{pointer:08x}": {
                "label": OBSERVED_POINTERS[pointer],
                "occurrences": [asdict(item) for item in occurrences],
            }
            for pointer, occurrences in result.items()
        }
        print(json.dumps(payload, indent=2))
        return 0
    for pointer, label in OBSERVED_POINTERS.items():
        occurrences = result.get(pointer, ())
        print(f"0x{pointer:08x} {label}: {len(occurrences)} occurrence(s)")
        for item in occurrences:
            print(f"  {item.path}:0x{item.offset:x}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
