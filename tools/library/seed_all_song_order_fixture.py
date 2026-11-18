#!/usr/bin/env python3
"""Replace MUSIC.LIB titles with their captured ALLSONG rank for seeded tests.

usage: seed_all_song_order_fixture.py DEVICE_MUSIC.LIB OUT_MUSIC.LIB
All bytes except the 64-byte title field of each record are preserved.
"""

from pathlib import Path
import struct
import sys


HEADER_SIZE = 0x200
RECORD_SIZE = 0x100
TITLE_SIZE = 0x40
ALLSONG_ORDER_SECTOR_OFFSET = 0x24
SECTOR_SIZE = 512


def make_fixture(source_path: Path, output_path: Path) -> None:
    data = bytearray(source_path.read_bytes())
    if len(data) < HEADER_SIZE or data[:5] != b"MUSIC":
        raise ValueError("input is not a complete MUSIC.LIB image")

    song_count = struct.unpack_from("<H", data, 8)[0]
    if song_count == 0 or song_count > 9999:
        raise ValueError("song count must be between 1 and 9999")

    order_sector = struct.unpack_from(
        "<H",
        data,
        ALLSONG_ORDER_SECTOR_OFFSET,
    )[0]
    order_offset = order_sector * SECTOR_SIZE
    order_end = order_offset + song_count * 2
    if order_end > len(data):
        raise ValueError("ALLSONG order table extends beyond the input image")

    order = struct.unpack_from(f"<{song_count}H", data, order_offset)
    if sorted(order) != list(range(song_count)):
        raise ValueError("ALLSONG order table is not a permutation of song indices")

    record_area_end = HEADER_SIZE + song_count * RECORD_SIZE
    if record_area_end > len(data):
        raise ValueError("record area extends beyond the input image")

    for rank, song_index in enumerate(order):
        record_offset = HEADER_SIZE + song_index * RECORD_SIZE
        title = f"{rank:04d}".encode("ascii") + b"\0"
        data[record_offset:record_offset + TITLE_SIZE] = title.ljust(TITLE_SIZE, b"\0")

    output_path.write_bytes(data)
    print(f"wrote {output_path}: {song_count} songs, ALLSONG order sector {order_sector}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)

    make_fixture(Path(sys.argv[1]), Path(sys.argv[2]))
