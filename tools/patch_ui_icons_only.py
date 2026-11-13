#!/usr/bin/env python3
"""Remove red fills from the directory file/folder icons, preserving selection red."""

from __future__ import annotations

import struct
import sys
from pathlib import Path


TABLE_OFFSET = 0x400
BACKGROUND = 0x18C3
ICON_RESOURCES = (
    (64, 0x41C10, 0x548),
    (75, 0x45628, 0x548),
    (76, 0x45B70, 0x548),
)


def is_red_accent(pixel: int) -> bool:
    red = ((pixel >> 11) & 31) * 255 // 31
    green = ((pixel >> 5) & 63) * 255 // 63
    blue = (pixel & 31) * 255 // 31
    return red >= 128 and red > green * 1.35 and red > blue * 1.35


def patch(src: Path, dst: Path) -> None:
    original = src.read_bytes()
    data = bytearray(original)
    for index, expected_off, expected_size in ICON_RESOURCES:
        off, size, fmt, _ = struct.unpack_from("<IIII", original, TABLE_OFFSET + index * 16)
        if (off, size, fmt >> 16) != (expected_off, expected_size, 26):
            raise SystemExit(f"unexpected icon resource {index}: {(off, size, fmt >> 16)!r}")
        for pos in range(0, size, 2):
            pixel = struct.unpack_from("<H", original, off + pos)[0]
            if is_red_accent(pixel):
                struct.pack_into("<H", data, off + pos, BACKGROUND)

    dst.write_bytes(data)
    print(f"patched icon resources only; selection resource 80 remains red; wrote {dst}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: patch_ui_icons_only.py INPUT_COMMON.STY OUTPUT_COMMON.STY")
    patch(Path(sys.argv[1]), Path(sys.argv[2]))
