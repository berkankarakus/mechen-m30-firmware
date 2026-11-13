#!/usr/bin/env python3
"""Match the four now-playing transport icons to the custom red artwork."""
from __future__ import annotations
import struct
import sys
from pathlib import Path

TABLE_OFFSET = 0x400
ICONS = ((7, 0xEB78, 0xC80, 40, 40), (8, 0xF7F8, 0xC80, 40, 40),
         (29, 0x167E0, 0xC80, 40, 40), (30, 0x17460, 0xC80, 40, 40))


def recolor(pixel: int) -> int:
    """Map the grayscale artwork onto the default artwork's main red."""
    bg = (24, 24, 24)  # RGB565 0x18c3, the stock icon background
    target = (230, 42, 50)  # RGB565 main red used by the custom default artwork
    r = ((pixel >> 11) & 31) * 255 // 31
    g = ((pixel >> 5) & 63) * 255 // 63
    b = (pixel & 31) * 255 // 31
    lum = (299 * r + 587 * g + 114 * b) // 1000
    if lum <= bg[0]:
        return pixel
    alpha = min(1.0, (lum - bg[0]) / (238 - bg[0]))
    rr = round(bg[0] + alpha * (target[0] - bg[0]))
    gg = round(bg[1] + alpha * (target[1] - bg[1]))
    bb = round(bg[2] + alpha * (target[2] - bg[2]))
    return ((rr * 31 // 255) << 11) | ((gg * 63 // 255) << 5) | (bb * 31 // 255)


def patch(src: Path, dst: Path) -> None:
    original = src.read_bytes()
    data = bytearray(original)
    changed = 0
    for index, expected_off, expected_size, width, height in ICONS:
        off, size, fmt, _ = struct.unpack_from('<IIII', original, TABLE_OFFSET + index * 16)
        if (off, size, fmt >> 16) != (expected_off, expected_size, width):
            raise SystemExit(f'unexpected control icon {index}: {(off, size, fmt >> 16)!r}')
        for pos in range(off, off + size, 2):
            old = struct.unpack_from('<H', original, pos)[0]
            new = recolor(old)
            if new != old:
                struct.pack_into('<H', data, pos, new)
                changed += 1
    if len(data) != len(original):
        raise AssertionError('music.sty size changed')
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(data)
    print(f'recolored transport icons 7, 8, 29, 30; {changed} pixels changed; size unchanged')


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit('usage: patch_music_controls.py INPUT_MUSIC.STY OUTPUT_MUSIC.STY')
    patch(Path(sys.argv[1]), Path(sys.argv[2]))
