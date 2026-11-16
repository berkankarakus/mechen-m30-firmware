#!/usr/bin/env python3
"""Build the superseded paint-path-only now-playing experiment.

Ghidra identifies the call in FUN_40154ddc at virtual address 0x40154fde:
    li v0, 0x2005

The existing 0x2001 record is the right-panel textbox geometry.  Replacing
the immediate at this one call site avoids changing the globally shared
0x2005 style, which is also used by another music.ap UI path.

The visible marquee is actually emitted by FUN_40d54f2c at 0x40d55078;
patch_music_scroll_call.py is the preferred script and this file is retained
only to reproduce the earlier no-visible-change candidate.
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path


TARGET_VADDR = 0x40154FDE
EXPECTED = bytes.fromhex("04 f0 05 6a")
REPLACEMENT = bytes.fromhex("04 f0 01 6a")


def file_offset_for_vaddr(data: bytes, vaddr: int) -> int:
    for table_off in range(0x100, 0x1000, 12):
        file_off, load_addr, size = struct.unpack_from("<III", data, table_off)
        if not file_off or not load_addr or not size:
            continue
        if file_off + size > len(data):
            continue
        if load_addr <= vaddr < load_addr + size:
            return file_off + (vaddr - load_addr)
    raise SystemExit(f"no AP bank contains virtual address 0x{vaddr:08x}")


def patch(src: Path, dst: Path) -> None:
    original = src.read_bytes()
    offset = file_offset_for_vaddr(original, TARGET_VADDR)
    if original[offset : offset + len(EXPECTED)] != EXPECTED:
        actual = original[offset : offset + len(EXPECTED)].hex(" ")
        raise SystemExit(
            f"unexpected instruction at 0x{TARGET_VADDR:08x} "
            f"(file 0x{offset:x}): {actual}"
        )

    data = bytearray(original)
    data[offset : offset + len(EXPECTED)] = REPLACEMENT
    if len(data) != len(original):
        raise AssertionError("AP size changed")

    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(data)
    changed = sum(a != b for a, b in zip(original, data))
    print(
        f"now-playing call 0x2005 -> 0x2001: {changed} byte changed; "
        f"virtual 0x{TARGET_VADDR:08x}, file 0x{offset:x}; wrote {dst}"
    )


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: patch_music_now_playing_call.py INPUT.AP OUTPUT.AP")
    patch(Path(sys.argv[1]), Path(sys.argv[2]))
