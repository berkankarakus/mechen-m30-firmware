#!/usr/bin/env python3
"""Redirect the verified M30 marquee renderer to the right-panel textbox.

Ghidra identifies FUN_40d54f2c as the shared scroll renderer.  Its draw call
at virtual address 0x40d55078 loads style 0x2005.  The M30 resource already
contains 0x2001 as the first right-panel textbox, so this isolated experiment
changes only that renderer call and leaves the unrelated 0x40154ddc call
unchanged.
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path


TARGET_VADDR = 0x40D55078
EXPECTED = bytes.fromhex("04 f0 05 6a")
REPLACEMENT = bytes.fromhex("04 f0 01 6a")


def file_offset_for_vaddr(data: bytes, vaddr: int) -> int:
    for table_off in range(0x100, 0x1000, 12):
        file_off, load_addr, size = struct.unpack_from("<III", data, table_off)
        if file_off and load_addr and size and file_off + size <= len(data):
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
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(data)
    print(
        f"scroll renderer 0x2005 -> 0x2001: "
        f"1 byte changed; virtual 0x{TARGET_VADDR:08x}, file 0x{offset:x}; "
        f"wrote {dst}"
    )


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: patch_music_scroll_call.py INPUT.AP OUTPUT.AP")
    patch(Path(sys.argv[1]), Path(sys.argv[2]))
