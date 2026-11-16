#!/usr/bin/env python3
"""Compare the recovered tie-refinement candidate with device index tables.

This is an order-only experiment. It never writes MUSIC.LIB or changes the
default emulator sorter. The refinement shape follows the recovered
FUN_40114d54 path: equal runs are re-read in bounded key slices and sorted
again until no run remains or the field is exhausted.
"""

from __future__ import annotations

from functools import cmp_to_key
import hashlib
from pathlib import Path
import struct
import sys
from typing import Sequence


TOOLS_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_ROOT / "sim"))

from library_index_sort import (
    SECTION_SPECS,
    _convert_index_text,
    _signed_track_byte,
)


SECTOR_SIZE = 512
HEADER_SIZE = 0x200
RECORD_SIZE = 0x100
INITIAL_KEY_LENGTH = 16
MAX_REFINEMENT_SLICE = 100
REFINEMENT_BUDGET = 0x10000


def _compare_probe_text(left: bytes, right: bytes) -> int:
    for left_byte, right_byte in zip(left, right):
        if 0x61 <= left_byte <= 0x7A:
            left_byte -= 32

        if 0x61 <= right_byte <= 0x7A:
            right_byte -= 32

        if left_byte != right_byte:
            return -1 if left_byte < right_byte else 1

        if left_byte == 0 and right_byte == 0:
            return 0

    return 0


def _read_order(data: bytes, record_count: int, section_number: int) -> tuple[int, ...]:
    section_offset = 0x10 + section_number * 0x1C
    table_sector = struct.unpack_from("<H", data, section_offset + 20)[0]
    table_offset = table_sector * SECTOR_SIZE

    return struct.unpack_from(f"<{record_count}H", data, table_offset)


def _inverse_rank(order: Sequence[int], record_count: int) -> tuple[int, ...]:
    rank = [0] * record_count

    for position, record_index in enumerate(order):
        rank[record_index] = position

    return tuple(rank)


def _equal_runs(
    order: Sequence[int],
    keys: Sequence[bytes],
    compared_length: int,
) -> tuple[tuple[int, int], ...]:
    runs: list[tuple[int, int]] = []
    start = 0

    while start < len(order):
        end = start + 1

        while end < len(order):
            left = keys[order[end - 1]][:compared_length]
            right = keys[order[end]][:compared_length]

            if _compare_probe_text(left, right) != 0:
                break

            end += 1

        if end - start > 1:
            runs.append((start, end))

        start = end

    return tuple(runs)


def _refine_order(
    records: Sequence[bytes],
    section_name: str,
    previous_rank: Sequence[int] | None,
) -> tuple[int, ...]:
    section_number, field_offset, field_width = SECTION_SPECS[section_name]
    keys = tuple(
        _convert_index_text(record, field_offset, field_width)
        for record in records
    )

    def compare_initial(left_index: int, right_index: int) -> int:
        result = _compare_probe_text(
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

        if section_number and previous_rank is not None:
            left_rank = previous_rank[left_index]
            right_rank = previous_rank[right_index]

            if left_rank != right_rank:
                return -1 if left_rank < right_rank else 1

        return 0

    order = list(sorted(range(len(records)), key=cmp_to_key(compare_initial)))
    compared_length = min(INITIAL_KEY_LENGTH, field_width)

    while compared_length < field_width:
        runs = _equal_runs(order, keys, compared_length)

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

        next_length = compared_length + refinement_length

        for (start, end), run_length in zip(runs, refinement_lengths):
            run_end = compared_length + run_length
            order[start:end] = sorted(
                order[start:end],
                key=cmp_to_key(
                    lambda left, right: _compare_probe_text(
                        keys[left][compared_length:run_end],
                        keys[right][compared_length:run_end],
                    )
                ),
            )

        compared_length = next_length

    return tuple(order)


def compare_library(
    data: bytes,
    expected_sha256: str | None = None,
) -> dict[str, object]:
    actual_sha256 = hashlib.sha256(data).hexdigest()

    if expected_sha256 is not None and actual_sha256 != expected_sha256:
        raise ValueError(
            f"MUSIC.LIB SHA-256 {actual_sha256} does not match {expected_sha256}"
        )

    record_count = struct.unpack_from("<H", data, 8)[0]
    records = tuple(
        data[offset : offset + RECORD_SIZE]
        for offset in range(HEADER_SIZE, HEADER_SIZE + record_count * RECORD_SIZE, RECORD_SIZE)
    )
    previous_rank: tuple[int, ...] | None = None
    sections: dict[str, dict[str, int | None]] = {}

    for section_name, (section_number, _, _) in SECTION_SPECS.items():
        actual_order = _read_order(data, record_count, section_number)
        candidate_order = _refine_order(records, section_name, previous_rank)
        matching_entries = sum(
            actual_index == candidate_index
            for actual_index, candidate_index in zip(actual_order, candidate_order)
        )
        first_mismatch = next(
            (
                position
                for position, (actual_index, candidate_index) in enumerate(
                    zip(actual_order, candidate_order)
                )
                if actual_index != candidate_index
            ),
            None,
        )
        sections[section_name] = {
            "matching_entries": matching_entries,
            "record_count": record_count,
            "first_mismatch": first_mismatch,
        }
        previous_rank = _inverse_rank(actual_order, record_count)

    return {
        "bytes": len(data),
        "sha256": actual_sha256,
        "record_count": record_count,
        "sections": sections,
    }


def main(path: Path, expected_sha256: str | None) -> None:
    summary = compare_library(path.read_bytes(), expected_sha256)
    print(
        "MUSIC.LIB TIE REFINEMENT PROBE PASS "
        f"bytes={summary['bytes']} records={summary['record_count']} "
        f"sha256={summary['sha256']}"
    )

    for section_name, section in summary["sections"].items():
        print(
            f"section={section_name} "
            f"matching={section['matching_entries']}/{section['record_count']} "
            f"first_mismatch={section['first_mismatch']}"
        )


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        raise SystemExit(
            "usage: library_tie_refinement_probe.py MUSIC.LIB [EXPECTED_SHA256| -]"
        )

    expected_sha256 = None
    if len(sys.argv) == 3 and sys.argv[2] != "-":
        expected_sha256 = sys.argv[2]

    main(Path(sys.argv[1]), expected_sha256)
