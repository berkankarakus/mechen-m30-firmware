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

INITIAL_KEY_LENGTH = 16
MAX_REFINEMENT_SLICE = 100
REFINEMENT_BUDGET = 0x10000


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


def refine_sort_record_indices(
    records: Sequence[bytes],
    section_name: str,
    previous_rank: Sequence[int] | None = None,
) -> tuple[int, ...]:
    """Apply the recovered short-key sort and bounded tie refinement.

    This is deliberately separate from ``sort_record_indices``. The latter
    remains the small candidate comparator used by the offline builder; this
    opt-in model mirrors the independently recovered ``FUN_40114d54`` path,
    which re-reads equal runs in bounded key slices.
    """
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

    def compare_initial(left_index: int, right_index: int) -> int:
        result = _compare_text(
            keys[left_index][:INITIAL_KEY_LENGTH],
            keys[right_index][:INITIAL_KEY_LENGTH],
        )
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

    order = list(sorted(range(len(records)), key=cmp_to_key(compare_initial)))
    compared_length = min(INITIAL_KEY_LENGTH, field_width)

    while compared_length < field_width:
        runs: list[tuple[int, int]] = []
        start = 0
        while start < len(order):
            end = start + 1
            while end < len(order):
                left = keys[order[end - 1]][:compared_length]
                right = keys[order[end]][:compared_length]
                if _compare_text(left, right) != 0:
                    break

                end += 1

            if end - start > 1:
                runs.append((start, end))

            start = end

        if not runs:
            break

        refinement_lengths = [
            min(
                MAX_REFINEMENT_SLICE,
                field_width - compared_length,
                REFINEMENT_BUDGET // (end - start),
            )
            for start, end in runs
        ]
        refinement_length = min(refinement_lengths)
        if refinement_length <= 0:
            break

        for (start, end), run_length in zip(runs, refinement_lengths):
            run_end = compared_length + run_length
            order[start:end] = sorted(
                order[start:end],
                key=cmp_to_key(
                    lambda left, right: _compare_text(
                        keys[left][compared_length:run_end],
                        keys[right][compared_length:run_end],
                    )
                ),
            )

        compared_length += refinement_length

    return tuple(order)


def group_indices_from_runs(
    order: Sequence[int],
    run_lengths: Sequence[int],
) -> tuple[int, ...]:
    """Map each record index to its zero-based group from sorted runs."""
    if sorted(order) != list(range(len(order))):
        raise ValueError("library sort order is not a record-index permutation")

    if sum(run_lengths) != len(order):
        raise ValueError("library run lengths do not cover the sort order")

    groups = [0] * len(order)
    position = 0
    for group, run_length in enumerate(run_lengths):
        if run_length <= 0:
            raise ValueError("library run lengths must be positive")

        for record_index in order[position : position + run_length]:
            if not 0 <= record_index < len(order):
                raise ValueError("library group contains an invalid record index")

            groups[record_index] = group

        position += run_length

    return tuple(groups)


def deepest_group_indices_from_runs(
    order: Sequence[int],
    run_lengths: Sequence[Sequence[int]],
) -> tuple[int, ...]:
    """Map each record to the deepest node group emitted for a section."""
    if not run_lengths:
        return ()

    return group_indices_from_runs(order, run_lengths[-1])


def derive_section_run_lengths(
    records: Sequence[bytes],
    section_name: str,
    order: Sequence[int],
    *,
    album_group_indices: Sequence[int] | None = None,
    artist_group_indices: Sequence[int] | None = None,
) -> tuple[tuple[int, ...], ...]:
    """Derive the recovered nested group runs without writing index bytes."""
    if section_name not in SECTION_SPECS:
        raise ValueError(f"unsupported MUSIC.LIB section: {section_name}")

    section_number, field_offset, field_width = SECTION_SPECS[section_name]
    if len(order) != len(records):
        raise ValueError("library sort order must contain every record")

    if sorted(order) != list(range(len(records))):
        raise ValueError("library sort order is not a record-index permutation")

    if section_number >= 2:
        if album_group_indices is None or len(album_group_indices) != len(records):
            raise ValueError("artist and genre grouping require album groups")

    if section_number == 3:
        if artist_group_indices is None or len(artist_group_indices) != len(records):
            raise ValueError("genre grouping requires artist groups")

    if section_number == 0:
        return ()

    keys = tuple(
        _convert_index_text(record, field_offset, field_width)
        for record in records
    )
    level_count = section_number
    run_lengths: list[list[int]] = [[] for _ in range(level_count)]
    current_lengths = [0] * level_count

    for position, record_index in enumerate(order):
        if position:
            previous_index = order[position - 1]
            break_level = level_count
            if _compare_text(keys[previous_index], keys[record_index]) != 0:
                break_level = 0
            elif level_count > 1:
                if section_name == "ARTIST":
                    if album_group_indices[previous_index] != album_group_indices[record_index]:
                        break_level = 1
                elif artist_group_indices[previous_index] != artist_group_indices[record_index]:
                    break_level = 1
                elif (
                    section_name == "GENRE"
                    and album_group_indices[previous_index] != album_group_indices[record_index]
                ):
                    break_level = 2

            for level in range(break_level, level_count):
                run_lengths[level].append(current_lengths[level])
                current_lengths[level] = 0

        for level in range(level_count):
            current_lengths[level] += 1

    for level in range(level_count):
        run_lengths[level].append(current_lengths[level])

    return tuple(tuple(lengths) for lengths in run_lengths)
