#!/usr/bin/env python3
"""Inspect the compact bank table in an Actions ``.drv`` image.

The driver builder keeps the resident images at the front of the file and
stores the UI overlay banks in three groups.  Each bank-table entry contains
two byte-order 16-bit offsets: the first is the start of the bank payload and
the second is its end.  The offsets are relative to the group file offset in
the driver header.

This is intentionally a structural reader.  It does not claim that every
firmware uses the public SDK's runtime addresses; pass ``--runtime-base``
when that mapping has been established for a particular image.
"""

from __future__ import annotations

import argparse
import json
import struct
from dataclasses import asdict, dataclass
from pathlib import Path


GROUPS = (
    ("A", 0x48, 0x80),
    ("B", 0x4C, 0x100),
    ("C", 0x50, 0x180),
)

# These are the addresses from the public ATJ2127 UI linker script.  They are
# useful for comparison, but are not silently applied to an M30 image.
PUBLIC_RUNTIME_BASES = {"A": 0x16024C00, "B": 0x26025000, "C": 0x36021A00}
PUBLIC_BANK_SPACING = 0x40000


@dataclass(frozen=True)
class Bank:
    group: str
    index: int
    table_offset: int
    file_start: int
    file_end: int
    size: int
    runtime_start: int | None = None


def read_banks(path: Path, runtime_bases: dict[str, int] | None = None) -> tuple[Bank, ...]:
    data = path.read_bytes()
    if data[4:8] != b"yqhx":
        raise ValueError(f"not an Actions driver: {path}")
    banks: list[Bank] = []
    for group, group_offset_field, table_offset in GROUPS:
        group_file_offset = struct.unpack_from("<I", data, group_offset_field)[0]
        for index in range(64):
            entry_offset = table_offset + index * 4
            if entry_offset + 4 > len(data):
                break
            # The container header is little-endian, but the two 16-bit bank
            # offsets in these tables are stored in byte order.  Keeping this
            # explicit avoids silently turning (00 40, 04 40) into one bogus
            # little-endian 32-bit value.
            start, end = struct.unpack_from(">HH", data, entry_offset)
            if start == 0 and end == 0:
                break
            if end <= start:
                raise ValueError(
                    f"{path}: invalid {group}{index} range at 0x{entry_offset:x}: "
                    f"0x{start:x}..0x{end:x}"
                )
            file_start = group_file_offset + start
            file_end = group_file_offset + end
            runtime_start = None
            if runtime_bases is not None and group in runtime_bases:
                runtime_start = runtime_bases[group] + index * PUBLIC_BANK_SPACING
            banks.append(
                Bank(group, index, entry_offset, file_start, file_end, end - start, runtime_start)
            )
    return tuple(banks)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("driver", type=Path)
    parser.add_argument("--runtime-base", action="store_true", help="also show public SDK comparison addresses")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()
    runtime = PUBLIC_RUNTIME_BASES if args.runtime_base else None
    banks = read_banks(args.driver, runtime)
    if args.as_json:
        print(json.dumps([asdict(bank) for bank in banks], indent=2))
        return 0
    for bank in banks:
        line = (
            f"{bank.group}{bank.index:02d} table=0x{bank.table_offset:03x} "
            f"file=0x{bank.file_start:05x}..0x{bank.file_end:05x} size=0x{bank.size:x}"
        )
        if bank.runtime_start is not None:
            line += f" public_runtime=0x{bank.runtime_start:08x}"
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
