#!/usr/bin/env python3
"""Patch only the directory-list marquee timer in M30 application overlays.

The stock common UI schedules the active-name marquee every 80 ms.  The
MIPS16 literal is present in the shared directory-loop bank of both browser.ap
and music.ap.  Moving it to 64 ms increases the redraw cadence without
changing the text renderer, list contents, playback, indexing, or input code.
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path


BANK_ADDR = 0x40CD4E00
BANK_SIZE = 0x600
TIMER_OFFSET = 0x19E  # virtual 0x40CD4F9E: li a1, 80
STOCK_INSN = 0x6D50    # MIPS16: li a1, 0x50 (80 ms)
PATCHED_INSN = 0x6D40  # MIPS16: li a1, 0x40 (64 ms)


def patch_ap(src: Path, dst: Path) -> None:
    data = bytearray(src.read_bytes())
    entries = []
    for off in range(0x100, 0x1000, 12):
        file_off, address, size = struct.unpack_from("<III", data, off)
        if address == BANK_ADDR and size == BANK_SIZE:
            entries.append(file_off)
    if len(entries) != 1:
        raise SystemExit(f"{src}: expected one 0x{BANK_ADDR:08x} bank, found {entries!r}")

    file_off = entries[0] + TIMER_OFFSET
    old = struct.unpack_from("<H", data, file_off)[0]
    if old != STOCK_INSN:
        raise SystemExit(
            f"{src}: unexpected marquee timer instruction at 0x{file_off:x}: "
            f"0x{old:04x}, expected 0x{STOCK_INSN:04x}"
        )
    struct.pack_into("<H", data, file_off, PATCHED_INSN)
    dst.write_bytes(data)
    print(f"{src.name}: marquee timer 80 ms -> 64 ms at file 0x{file_off:x}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: patch_ui_motion.py INPUT.ap OUTPUT.ap")
    patch_ap(Path(sys.argv[1]), Path(sys.argv[2]))
