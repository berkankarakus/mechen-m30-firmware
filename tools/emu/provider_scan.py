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


def scan_driver_directory(
    root: Path, pointers: tuple[int, ...] = tuple(OBSERVED_POINTERS)
) -> dict[int, tuple[Occurrence, ...]]:
    merged: dict[int, list[Occurrence]] = {}
    for path in sorted(root.glob("*.drv")):
        for pointer, occurrences in scan_file(path, pointers).items():
            merged.setdefault(pointer, []).extend(occurrences)
    return {pointer: tuple(items) for pointer, items in merged.items()}


def scan_tree(
    root: Path, pointers: tuple[int, ...] = tuple(OBSERVED_POINTERS)
) -> dict[int, tuple[Occurrence, ...]]:
    """Scan every regular extracted firmware member below ``root``."""

    merged: dict[int, list[Occurrence]] = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        for pointer, occurrences in scan_file(path, pointers).items():
            merged.setdefault(pointer, []).extend(occurrences)
    return {pointer: tuple(items) for pointer, items in merged.items()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, help="directory containing extracted .drv files")
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument(
        "--all-files",
        action="store_true",
        help="scan every regular file below root instead of only top-level .drv files",
    )
    parser.add_argument(
        "--pointer",
        action="append",
        type=lambda value: int(value, 0),
        dest="pointers",
        help="additional custom 32-bit pointer to scan; repeat for multiple values",
    )
    args = parser.parse_args()
    pointers = tuple(args.pointers) if args.pointers else tuple(OBSERVED_POINTERS)
    result = (
        scan_tree(args.root, pointers)
        if args.all_files
        else scan_driver_directory(args.root, pointers)
    )
    if args.as_json:
        payload = {
            f"0x{pointer:08x}": {
                "label": OBSERVED_POINTERS.get(pointer, "custom pointer"),
                "occurrences": [asdict(item) for item in occurrences],
            }
            for pointer, occurrences in result.items()
        }
        print(json.dumps(payload, indent=2))
        return 0
    labels = {pointer: OBSERVED_POINTERS.get(pointer, "custom pointer") for pointer in pointers}
    for pointer, label in labels.items():
        occurrences = result.get(pointer, ())
        print(f"0x{pointer:08x} {label}: {len(occurrences)} occurrence(s)")
        for item in occurrences:
            print(f"  {item.path}:0x{item.offset:x}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
