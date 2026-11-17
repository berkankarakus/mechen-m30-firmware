#!/usr/bin/env python3
"""Compare the recovered tie-refinement candidate with device index tables.

This is an order-only experiment. It never writes MUSIC.LIB or changes the
default emulator sorter. The refinement shape follows the recovered
FUN_40114d54 path: equal runs are re-read in bounded key slices and sorted
again until no run remains or the field is exhausted.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import struct
import sys
from typing import Sequence


TOOLS_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_ROOT / "sim"))

from library_index_sort import (
    INDEX_TEXT_CONVERSION_STALE_TAIL,
    SECTION_SPECS,
    refine_sort_record_indices,
)


SECTOR_SIZE = 512
HEADER_SIZE = 0x200
RECORD_SIZE = 0x100
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


def compare_library(
    data: bytes,
    expected_sha256: str | None = None,
    conversion_mode: str = INDEX_TEXT_CONVERSION_STALE_TAIL,
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
        candidate_order = refine_sort_record_indices(
            records,
            section_name,
            previous_rank=previous_rank,
            conversion_mode=conversion_mode,
        )
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
        "conversion_mode": conversion_mode,
        "sections": sections,
    }


def main(
    path: Path,
    expected_sha256: str | None,
    conversion_mode: str,
) -> None:
    summary = compare_library(
        path.read_bytes(),
        expected_sha256,
        conversion_mode,
    )
    print(
        "MUSIC.LIB TIE REFINEMENT PROBE PASS "
        f"bytes={summary['bytes']} records={summary['record_count']} "
        f"sha256={summary['sha256']} conversion={summary['conversion_mode']}"
    )

    for section_name, section in summary["sections"].items():
        print(
            f"section={section_name} "
            f"matching={section['matching_entries']}/{section['record_count']} "
            f"first_mismatch={section['first_mismatch']}"
        )


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3, 4):
        raise SystemExit(
            "usage: library_tie_refinement_probe.py MUSIC.LIB "
            "[EXPECTED_SHA256| -] [stale-tail|stop-zero]"
        )

    expected_sha256 = None
    if len(sys.argv) == 3 and sys.argv[2] != "-":
        expected_sha256 = sys.argv[2]

    conversion_mode = INDEX_TEXT_CONVERSION_STALE_TAIL
    if len(sys.argv) == 4:
        conversion_mode = sys.argv[3]

    main(Path(sys.argv[1]), expected_sha256, conversion_mode)
