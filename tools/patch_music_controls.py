#!/usr/bin/env python3
"""Match the four now-playing transport icons to the custom red artwork."""
from __future__ import annotations
import hashlib
import struct
import sys
from pathlib import Path

TABLE_OFFSET = 0x400
ICONS = ((7, 0xEB78, 0xC80, 40, 40), (8, 0xF7F8, 0xC80, 40, 40),
         (29, 0x167E0, 0xC80, 40, 40), (30, 0x17460, 0xC80, 40, 40))
ICON_LAYOUTS = {
    "standard": ICONS,
    "2024-04-24": (
        (7, 0xEB88, 0xC80, 40, 40),
        (8, 0xF808, 0xC80, 40, 40),
        (30, 0x16AC0, 0xC80, 40, 40),
        (31, 0x17740, 0xC80, 40, 40),
    ),
}
ICON_PAYLOAD_SHA256 = {
    "standard": (
        "10dabd97b87228e4b382c0e0d24ce529c93b37007cb32536882a0b7f79ca835b",
        "f4a57f1862555eeb2ad96fb21bf8e19ca51a4ab7e4b968949e021792b375ff69",
        "fd3ff01b4f2996b76975cb3428fbafc9644b20373df070d13f4fa1f19a464986",
        "7a79f847dbb396f9a93b515ae4866711595b0b9a30d30ebdc6e61324735e5b6d",
    ),
    "2024-04-24": (
        "10dabd97b87228e4b382c0e0d24ce529c93b37007cb32536882a0b7f79ca835b",
        "f4a57f1862555eeb2ad96fb21bf8e19ca51a4ab7e4b968949e021792b375ff69",
        "fd3ff01b4f2996b76975cb3428fbafc9644b20373df070d13f4fa1f19a464986",
        "7a79f847dbb396f9a93b515ae4866711595b0b9a30d30ebdc6e61324735e5b6d",
    ),
}


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


def _metadata_matches(
    original: bytes,
    index: int,
    expected_off: int,
    expected_size: int,
    expected_width: int,
    expected_height: int,
) -> bool:
    off, size, fmt, height = struct.unpack_from(
        '<IIII',
        original,
        TABLE_OFFSET + index * 16,
    )

    return (off, size, fmt >> 16, height) == (
        expected_off,
        expected_size,
        expected_width,
        expected_height,
    )


def _select_icon_layout(
    original: bytes,
    validate_source: bool,
) -> tuple[str, tuple[tuple[int, int, int, int, int], ...]]:
    matches = []
    for name, entries in ICON_LAYOUTS.items():
        metadata_matches = all(
            _metadata_matches(
                original,
                index,
                expected_off,
                expected_size,
                width,
                height,
            )
            for index, expected_off, expected_size, width, height in entries
        )
        if not metadata_matches:
            continue

        if validate_source:
            payload_hashes = tuple(
                hashlib.sha256(original[offset:offset + size]).hexdigest()
                for _, offset, size, _, _ in entries
            )
            if payload_hashes != ICON_PAYLOAD_SHA256[name]:
                continue

        matches.append((name, entries))

    if len(matches) != 1:
        raise SystemExit(
            "unsupported or ambiguous transport-icon layout; "
            f"matches={[name for name, _ in matches]!r}"
        )

    return matches[0]


def patch(src: Path, dst: Path, validate_source: bool = True) -> None:
    original = src.read_bytes()
    data = bytearray(original)
    changed = 0
    layout_name, icons = _select_icon_layout(original, validate_source)
    for index, expected_off, expected_size, width, height in icons:
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
    indices = ', '.join(str(index) for index, _, _, _, _ in icons)
    print(
        f'recolored transport icons {indices} using {layout_name} layout; '
        f'{changed} pixels changed; size unchanged'
    )


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit('usage: patch_music_controls.py INPUT_MUSIC.STY OUTPUT_MUSIC.STY')
    patch(Path(sys.argv[1]), Path(sys.argv[2]))
