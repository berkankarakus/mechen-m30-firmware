#!/usr/bin/env python3
"""Build the M30 UI variant with a black active-row background.

This is intentionally a resource-only follow-up to patch_ui_theme.py.  The
active directory item uses resource 80 as its background; using black avoids
leaving a coloured rectangle behind the marquee while the text is redrawn.
The icon-background cleanup remains the same as the blue candidate.
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path


TABLE_OFFSET = 0x400
ENTRY_SIZE = 16
EXPECTED_SELECTION = (80, 0x47090, 0x463C)
STOCK_RED = 0xD000
LIST_BACKGROUND = 0x18C3
ACTIVE_BACKGROUND = 0x0000
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


def entries(data: bytes):
    for index in range((len(data) - TABLE_OFFSET) // ENTRY_SIZE):
        off, size, fmt, _ = struct.unpack_from("<IIII", data, TABLE_OFFSET + index * ENTRY_SIZE)
        width = fmt >> 16
        if off and size and off + size <= len(data):
            yield index, off, size, width


def patch(src: Path, dst: Path) -> None:
    original = src.read_bytes()
    data = bytearray(original)

    matches = []
    for index, off, size, width in entries(original):
        height = size // (width * 2) if width and size % (width * 2) == 0 else 0
        if width == 310 and height == 29:
            pixels = struct.unpack_from("<" + "H" * (size // 2), original, off)
            if pixels and all(pixel == STOCK_RED for pixel in pixels):
                matches.append((index, off, size))
    if matches != [EXPECTED_SELECTION]:
        raise SystemExit(f"unexpected selection resources: {matches!r}")

    _, selection_off, selection_size = matches[0]
    for pos in range(0, selection_size, 2):
        struct.pack_into("<H", data, selection_off + pos, ACTIVE_BACKGROUND)

    icon_changed = 0
    for index, expected_off, expected_size in ICON_RESOURCES:
        off, size, fmt, _ = struct.unpack_from("<IIII", original, TABLE_OFFSET + index * ENTRY_SIZE)
        if (off, size, fmt >> 16) != (expected_off, expected_size, 26):
            raise SystemExit(f"unexpected icon resource {index}: {(off, size, fmt >> 16)!r}")
        for pos in range(0, size, 2):
            pixel = struct.unpack_from("<H", original, off + pos)[0]
            if is_red_accent(pixel):
                struct.pack_into("<H", data, off + pos, LIST_BACKGROUND)
                icon_changed += 2

    allowed = set(range(selection_off, selection_off + selection_size))
    for _, icon_off, icon_size in ICON_RESOURCES:
        allowed.update(range(icon_off, icon_off + icon_size))
    unexpected = [i for i, (a, b) in enumerate(zip(original, data)) if a != b and i not in allowed]
    if unexpected:
        raise AssertionError(f"bytes changed outside declared UI resources: {unexpected[:8]!r}")

    dst.write_bytes(data)
    print(f"patched active selection resource 80: {selection_size} bytes -> black")
    print(f"removed red icon backgrounds: {icon_changed} bytes")
    print(f"wrote {dst} ({len(data)} bytes)")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: patch_ui_theme_black.py INPUT_COMMON.STY OUTPUT_COMMON.STY")
    patch(Path(sys.argv[1]), Path(sys.argv[2]))
