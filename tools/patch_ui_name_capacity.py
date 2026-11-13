#!/usr/bin/env python3
"""Use the complete 52-byte directory-name slots in M30 browser list data.

The shared UI directory implementation reserves LIST_ITEM_BUFFER_LEN * 8
bytes, with LIST_ITEM_BUFFER_LEN=52.  The M30 browser callbacks currently
use 50-byte lengths and strides, leaving two bytes unused in every slot.
This guarded patch changes the four MIPS16 ``li ..., 50`` immediates in the
two callbacks to 52.  It does not enlarge the fixed buffer.
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path


BANK_ADDR = 0x48754400
BANK_SIZE = 0x800
SLOT_INSN_OFFSETS = (0x186, 0x1C6, 0x2EA, 0x3A8)
OLD_INSN = 0x6A32  # MIPS16: li v0, 50
NEW_INSN = 0x6A34  # MIPS16: li v0, 52


def patch_ap(src: Path, dst: Path) -> None:
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
        struct.pack_into("<H", data, bank_off + offset, NEW_INSN)

    dst.write_bytes(data)
    print(f"{src.name}: four 50-byte slot values changed to 52 at bank 0x{BANK_ADDR:08x}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: patch_ui_name_capacity.py INPUT.ap OUTPUT.ap")
    patch_ap(Path(sys.argv[1]), Path(sys.argv[2]))
