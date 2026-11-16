#!/usr/bin/env python3
"""Replace the stock missing-cover glyph with a static M30 red waveform."""
from __future__ import annotations
import hashlib
import struct
import sys
from pathlib import Path

TABLE_OFFSET = 0x400
RESOURCE = 0
EXPECTED = (0x840, 45000, 150)
EXPECTED_RESOURCE_OFFSETS = (0x840, 0x850)
EXPECTED_RESOURCE_SHA256 = (
    "8213347c2ed4c8170062c5781397ca354278c7ded6377320dee1b35294c12ef4"
)
WIDTH = HEIGHT = 150


def rgb565(r: int, g: int, b: int) -> int:
    return ((r * 31 // 255) << 11) | ((g * 63 // 255) << 5) | (b * 31 // 255)


def render() -> tuple[bytes, bytes]:
    rgb = bytearray()
    raw = bytearray()
    cx = cy = 74.5
    for y in range(HEIGHT):
        for x in range(WIDTH):
            d = ((x-cx)**2 + (y-cy)**2) ** 0.5
            shade = max(0, 12 - int(d / 22))
            color = (18 + shade, 19 + shade, 22 + shade)
            if 52 <= d <= 54:
                color = (120, 21, 29)
            elif d < 52:
                color = (25 + shade, 20 + shade // 2, 23 + shade // 2)
            for bx, h in zip((47, 59, 71, 83, 95, 107), (12, 22, 34, 44, 29, 17)):
                if bx <= x < bx + 6 and 75 - h // 2 <= y < 75 + h // 2:
                    color = (230, 42, 50) if bx != 71 and bx != 83 else (255, 74, 77)
                    break
            if 43 <= x < 108 and y in (73, 74, 76, 77):
                if not (58 <= x < 63 or 70 <= x < 77 or 82 <= x < 89 or 101 <= x < 106):
                    color = (160, 29, 37)
            pixel = rgb565(*color)
            raw.extend(struct.pack('<H', pixel))
            rgb.extend(color)
    return bytes(raw), b'P6\n150 150\n255\n' + rgb


def patch(
    src: Path,
    dst: Path,
    preview: Path,
    validate_source: bool = True,
) -> None:
    original = src.read_bytes()
    off, size, fmt, _ = struct.unpack_from('<IIII', original, TABLE_OFFSET + RESOURCE * 16)
    width = fmt >> 16
    if (
        size != EXPECTED[1]
        or width != EXPECTED[2]
        or off not in EXPECTED_RESOURCE_OFFSETS
    ):
        raise SystemExit(f'unexpected missing-cover resource: {(off, size, width)!r}')

    if validate_source:
        resource_sha256 = hashlib.sha256(original[off:off + size]).hexdigest()
        if resource_sha256 != EXPECTED_RESOURCE_SHA256:
            raise SystemExit(
                "unexpected missing-cover resource payload: "
                f"sha256={resource_sha256}"
            )

    pixels, ppm = render()
    if len(pixels) != size:
        raise AssertionError('rendered bitmap size mismatch')
    data = bytearray(original)
    data[off:off + size] = pixels
    dst.parent.mkdir(parents=True, exist_ok=True)
    preview.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(data)
    preview.write_bytes(ppm)
    if len(data) != len(original):
        raise AssertionError('resource size changed')
    changed = sum(a != b for a, b in zip(original, data))
    print(f'music.sty missing-cover bitmap replaced: {WIDTH}x{HEIGHT}, {changed} changed bytes')
    print(f'wrote {dst} and preview {preview}')


if __name__ == '__main__':
    if len(sys.argv) != 4:
        raise SystemExit('usage: patch_default_art.py INPUT_MUSIC.STY OUTPUT_MUSIC.STY PREVIEW.PPM')
    patch(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
