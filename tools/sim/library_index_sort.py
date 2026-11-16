"""Candidate sort-order model of the recovered MUSIC.LIB index passes."""

from __future__ import annotations

from functools import cmp_to_key
import struct
from typing import Sequence


RECORD_SIZE = 0x100
SECTION_SPECS = {
    "ALLSONG": (0, 0x00, 0x40),
    "ALBUM": (1, 0x58, 0x30),
    "ARTIST": (2, 0x40, 0x18),
    "GENRE": (3, 0x88, 0x18),
}


def _convert_index_text(record: bytes, offset: int, width: int) -> bytes:
    field = record[offset : offset + width]
    if field[:2] != b"\xff\xfe":
        return bytes(field)

    buffer = bytearray(
        record[offset + 2 : offset + 2 + 2 * width].ljust(2 * width, b"\0")
    )
    for index in range(width):
        character = buffer[2 * index] | (buffer[2 * index + 1] << 8)
        if character >= 256:
            break

        buffer[index] = character
        if character == 0:
            break

    return bytes(buffer[:width])


def _compare_text(left: bytes, right: bytes) -> int:
    for left_byte, right_byte in zip(left, right):
        if 0x61 <= left_byte <= 0x7A:
            left_byte -= 32

        if 0x61 <= right_byte <= 0x7A:
            right_byte -= 32

        if left_byte != right_byte:
            return -1 if left_byte < right_byte else 1

        if left_byte == 0:
            return 0

    return 0


def _signed_track_byte(record: bytes) -> int:
    return struct.unpack_from("<b", record, 0xF2)[0]


def sort_record_indices(
    records: Sequence[bytes],
    section_name: str,
    previous_rank: Sequence[int] | None = None,
) -> tuple[int, ...]:
    """Return the recovered stable sort order without writing an index file."""
    if section_name not in SECTION_SPECS:
        raise ValueError(f"unsupported MUSIC.LIB section: {section_name}")

    section_number, field_offset, field_width = SECTION_SPECS[section_name]
    for record in records:
        if len(record) != RECORD_SIZE:
            raise ValueError("MUSIC.LIB sort records must be exactly 256 bytes")

    if section_number and (previous_rank is None or len(previous_rank) != len(records)):
        raise ValueError("non-first section sorting requires one previous rank per record")

    keys = tuple(
        _convert_index_text(record, field_offset, field_width)
        for record in records
    )

    def compare(left_index: int, right_index: int) -> int:
        result = _compare_text(keys[left_index], keys[right_index])
        if result:
            return result

        if section_name == "ALBUM":
            left_track = _signed_track_byte(records[left_index])
            right_track = _signed_track_byte(records[right_index])
            if left_track != right_track:
                return -1 if left_track < right_track else 1

        if section_number:
            left_rank = previous_rank[left_index]
            right_rank = previous_rank[right_index]
            if left_rank != right_rank:
                return -1 if left_rank < right_rank else 1

        return 0

    return tuple(sorted(range(len(records)), key=cmp_to_key(compare)))
