#!/usr/bin/env python3
"""Reproduce the controlled directory-slot experiment.

The M30 uses four literal 50-byte values for the eight-entry directory list.
The surrounding data page is 0x200 bytes immediately before the 0x40cd4e00
overlay bank, but the caller passes path_info at 0x40cd4d90.  A 64-byte slot
experiment therefore overlaps that structure even though it fits the page.
This patch remains opt-in and requires an explicit acknowledgement.

The default experiment remains the historical 52-byte change.  The more
useful candidate is ``--slot-bytes 64``: it changes both the slot stride and
the length passed to the directory-name reader, allowing roughly 30 UTF-16
characters instead of the current ~23-24.
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path


BANK_ADDR = 0x48754400
BANK_SIZE = 0x800
SLOT_INSN_OFFSETS = (0x186, 0x1C6, 0x2EA, 0x3A8)
OLD_INSN = 0x6A32  # MIPS16: li v0, 50
INSN_BASE = 0x6A00  # MIPS16: li v0, immediate
LIST_BUFFER_ADDR = 0x40CD4C00
PATH_INFO_ADDR = 0x40CD4D90
LIST_SLOT_COUNT = 8


def patch_ap(src: Path, dst: Path, slot_bytes: int, allow_path_info_overlap: bool = False) -> None:
    if slot_bytes < 2 or slot_bytes > 0x7F or slot_bytes % 2:
        raise SystemExit("slot-bytes must be an even MIPS16 immediate in 2..127")
    if slot_bytes * 8 > 0x200:
        raise SystemExit("slot-bytes would exceed the inferred 0x200-byte list page")
    list_end = LIST_BUFFER_ADDR + slot_bytes * LIST_SLOT_COUNT
    if list_end > PATH_INFO_ADDR and not allow_path_info_overlap:
        raise SystemExit(
            f"slot-bytes={slot_bytes} would overwrite path_info at 0x{PATH_INFO_ADDR:08x}; "
            "use --allow-path-info-overlap only to generate a deliberately unsafe analysis copy"
        )

    data = bytearray(src.read_bytes())
    bank_offsets = []
    for entry in range(0x100, 0x1000, 12):
        file_off, address, size = struct.unpack_from("<III", data, entry)
        if address == BANK_ADDR and size == BANK_SIZE:
            bank_offsets.append(file_off)
    if len(bank_offsets) != 1:
        raise SystemExit(f"{src}: expected one browser-list bank, found {bank_offsets!r}")

    bank_off = bank_offsets[0]
    for offset in SLOT_INSN_OFFSETS:
        actual = struct.unpack_from("<H", data, bank_off + offset)[0]
        if actual != OLD_INSN:
            raise SystemExit(
                f"{src}: unexpected instruction at bank+0x{offset:x}: "
                f"0x{actual:04x}, expected 0x{OLD_INSN:04x}"
            )
    for offset in SLOT_INSN_OFFSETS:
        struct.pack_into("<H", data, bank_off + offset, INSN_BASE | slot_bytes)

    dst.write_bytes(data)
    print(f"{src.name}: four 50-byte slot values changed to {slot_bytes} at bank 0x{BANK_ADDR:08x}")


if __name__ == "__main__":
    args = sys.argv[1:]
    allow_path_info_overlap = "--allow-path-info-overlap" in args
    args = [arg for arg in args if arg != "--allow-path-info-overlap"]
    if len(args) not in (3, 5) or args[0] != "--acknowledge-unsafe":
        raise SystemExit(
            "unsafe slot-size experiment disabled; use only for controlled "
            "tests: patch_ui_name_capacity.py --acknowledge-unsafe "
            "[--slot-bytes 64] INPUT.ap OUTPUT.ap [--allow-path-info-overlap]"
        )
    if len(args) == 3:
        slot_bytes, src_arg, dst_arg = 52, args[1], args[2]
    else:
        if args[1] != "--slot-bytes":
            raise SystemExit("expected --slot-bytes N")
        slot_bytes, src_arg, dst_arg = int(args[2], 0), args[3], args[4]
    patch_ap(Path(src_arg), Path(dst_arg), slot_bytes, allow_path_info_overlap)
