#!/usr/bin/env python3
"""Set the Custom EQ gains sent by the music app without editing settings.

The Custom producer in music.ap copies seven bytes from its source pointer
before sending the EQ message. This patch redirects that pointer to a
seven-byte curve in zero-filled space within the same loaded bank. Values are
firmware-relative steps; the firmware's DSP gain units are not calibrated.
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path


BANK_VA = 0x403D4C00
BANK_FILE_OFFSET = 0x8400
BANK_SIZE = 0x800
SOURCE_POINTER_FILE_OFFSET = 0x86F8
EXPECTED_SOURCE_POINTER = 0x9FC15720
CURVE_VA = 0x403D4F00
CURVE_FILE_OFFSET = CURVE_VA - BANK_VA + BANK_FILE_OFFSET
# Bass-forward curve within the corpus's observed -4..+6 preset envelope.
CUSTOM_GAINS = (6, 5, 0, -2, 0, 4, 3)


def _segment_offsets(data: bytes) -> list[int]:
    """Return file offsets for the exact AP segment-table mapping."""
    matches = []
    for table_entry in range(0x100, min(0x1000, len(data)), 12):
        file_offset, address, size = struct.unpack_from("<III", data, table_entry)
        if address == BANK_VA and size == BANK_SIZE:
            matches.append(file_offset)
    return matches


def patch(src: Path, dst: Path) -> None:
    data = bytearray(src.read_bytes())
    if _segment_offsets(data) != [BANK_FILE_OFFSET]:
        raise SystemExit(
            f"{src}: expected one music bank at file 0x{BANK_FILE_OFFSET:x}, "
            f"VA 0x{BANK_VA:08x}, size 0x{BANK_SIZE:x}"
        )

    old_pointer = struct.unpack_from("<I", data, SOURCE_POINTER_FILE_OFFSET)[0]
    if old_pointer != EXPECTED_SOURCE_POINTER:
        raise SystemExit(
            f"{src}: unexpected Custom EQ source pointer "
            f"0x{old_pointer:08x} at 0x{SOURCE_POINTER_FILE_OFFSET:x}"
        )
    if data[CURVE_FILE_OFFSET : CURVE_FILE_OFFSET + len(CUSTOM_GAINS)] != bytes(len(CUSTOM_GAINS)):
        raise SystemExit(f"{src}: proposed in-bank curve storage is not all zero")
    if CURVE_FILE_OFFSET + len(CUSTOM_GAINS) > BANK_FILE_OFFSET + BANK_SIZE:
        raise SystemExit(f"{src}: proposed curve lies outside the loaded music bank")

    for offset, value in enumerate(CUSTOM_GAINS):
        data[CURVE_FILE_OFFSET + offset] = value & 0xFF
    struct.pack_into("<I", data, SOURCE_POINTER_FILE_OFFSET, CURVE_VA)
    dst.write_bytes(data)
    print(
        f"{src.name}: Custom EQ gains {CUSTOM_GAINS!r} at file 0x{CURVE_FILE_OFFSET:x}; "
        f"copy source 0x{EXPECTED_SOURCE_POINTER:08x} -> 0x{CURVE_VA:08x}"
    )


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: patch_eq_custom.py INPUT.music.ap OUTPUT.music.ap")
    patch(Path(sys.argv[1]), Path(sys.argv[2]))
