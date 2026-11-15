#!/usr/bin/env python3
"""Verify the usound AP bank and packaged driver/resource names."""

from __future__ import annotations

import argparse
from pathlib import Path
import struct


AP_ENTRY = 0x40014C31
DRIVER_BANK = (0xD00, 0x40094C00, 0x664)
PACKAGED_NAMES = {
    0x1114: b"usound.sty\0",
    0x1120: b"common.sty\0",
    0x112C: b"usound.drv\0",
    0x1138: b"install_err\0",
}


def _banks(data: bytes) -> tuple[tuple[int, int, int], ...]:
    values: list[tuple[int, int, int]] = []
    for offset in range(0x100, 0x1000, 12):
        file_offset, address, size = struct.unpack_from("<III", data, offset)
        if file_offset and address and size and size <= 0x10000:
            if file_offset + size <= len(data):
                values.append((file_offset, address, size))
    return tuple(values)


def verify(path: Path) -> None:
    data = path.read_bytes()
    if len(data) != 0x5800:
        raise AssertionError(f"usound.ap size 0x{len(data):x} != 0x5800")
    if struct.unpack_from("<I", data, 0x40)[0] != AP_ENTRY:
        raise AssertionError("unexpected usound.ap entry")
    if DRIVER_BANK not in _banks(data):
        raise AssertionError(f"driver/resource bank {DRIVER_BANK!r} not found")
    bank_file, bank_address, _ = DRIVER_BANK
    for file_offset, marker in PACKAGED_NAMES.items():
        if data[file_offset : file_offset + len(marker)] != marker:
            raise AssertionError(f"missing packaged marker at 0x{file_offset:x}: {marker!r}")
        runtime = bank_address + file_offset - bank_file
        expected = {
            0x1114: 0x40095014,
            0x1120: 0x40095020,
            0x112C: 0x4009502C,
            0x1138: 0x40095038,
        }[file_offset]
        if runtime != expected:
            raise AssertionError(f"runtime mapping 0x{runtime:x} != 0x{expected:x}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("usound_ap", type=Path)
    args = parser.parse_args()
    verify(args.usound_ap)
    print(
        "USOUND AP BINARY PROBE PASS "
        "entry=0x40014c31 bank=0x40094c00/0x664 "
        "driver=0x4009502c resources=usound.sty,common.sty"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
