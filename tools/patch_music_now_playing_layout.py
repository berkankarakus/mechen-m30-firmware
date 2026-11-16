#!/usr/bin/env python3
"""Build the superseded global-style now-playing layout experiment.

The M30 music.ap refresh path uses style 0x2005 for a dynamic metadata/file
draw.  This patch clones the already-present first right-panel textbox style
onto that record, preserving the resource size and all other controls.

Important: 0x2005 is also used by another music.ap UI path.  The isolated
call-site patch in patch_music_now_playing_call.py is preferred for firmware
testing because it leaves the shared 0x2005 style unchanged.
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path


TEXTBOX_GROUP_INDEX = 2
TEXTBOX_SIZE = 20
TARGET_INDEX = 5  # style 0x2005
SOURCE_INDEX = 1   # existing right-panel style 0x2001
EXPECTED_TARGET = (78, 149, 3, 90, 20, 115, 0, 6, 65535, 7)


def patch(src: Path, dst: Path) -> None:
    original = src.read_bytes()
    if original[:4] != b"RU3\x19":
        raise SystemExit(f"not an RU3 resource file: {src}")

    style_addr = struct.unpack_from("<I", original, 8)[0]
    style_begin = struct.unpack_from("<I", original, style_addr + 8)[0]
    group_addr, group_count = struct.unpack_from(
        "<2I", original, style_begin + TEXTBOX_GROUP_INDEX * 8
    )
    if group_count < TARGET_INDEX + 1 or group_count <= SOURCE_INDEX:
        raise SystemExit(f"unexpected textbox count: {group_count}")

    target_off = group_addr + TARGET_INDEX * TEXTBOX_SIZE
    source_off = group_addr + SOURCE_INDEX * TEXTBOX_SIZE
    target = struct.unpack_from("<10H", original, target_off)
    source = struct.unpack_from("<10H", original, source_off)
    if target != EXPECTED_TARGET:
        raise SystemExit(f"unexpected 0x2005 textbox: {target!r}")

    data = bytearray(original)
    struct.pack_into("<10H", data, target_off, *source)
    if len(data) != len(original):
        raise AssertionError("resource size changed")

    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(data)
    changed = sum(a != b for a, b in zip(original, data))
    print(f"cloned textbox 0x2001 -> 0x2005: {changed} bytes changed")
    print(f"target offset: 0x{target_off:x}; wrote {dst}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: patch_music_now_playing_layout.py INPUT.STY OUTPUT.STY")
    patch(Path(sys.argv[1]), Path(sys.argv[2]))
