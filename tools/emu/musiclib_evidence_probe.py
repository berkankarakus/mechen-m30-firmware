#!/usr/bin/env python3
"""Verify an external MUSIC.LIB sample through the host SD/index model."""

from __future__ import annotations

import hashlib
from pathlib import Path
import sys

from library_file import (
    SECTOR_SIZE,
    interpret_library_section_index,
    read_library_layout,
    read_library_section_index,
)
from sd_block_device import SdCardBlockDevice


EXPECTED_PUBLIC_SAMPLE_SHA256 = (
    "cc3f476c8edb50ea8493b726d46ac82b139a6e87a86cc04c2cdbc30fd3fb8afe"
)
INDEXED_SECTIONS = ("ALBUM", "ARTIST", "GENRE")


def inspect_music_library(
    data: bytes,
    expected_sha256: str | None = EXPECTED_PUBLIC_SAMPLE_SHA256,
) -> dict[str, object]:
    """Validate a byte image and return its bounded index summary."""
    if len(data) % SECTOR_SIZE:
        raise ValueError("MUSIC.LIB image must contain complete 512-byte sectors")

    sha256 = hashlib.sha256(data).hexdigest()
    if expected_sha256 is not None and sha256 != expected_sha256:
        raise ValueError(
            f"MUSIC.LIB SHA-256 {sha256} does not match {expected_sha256}"
        )

    card = SdCardBlockDevice(sector_count=len(data) // SECTOR_SIZE)
    for sector in range(card.sector_count):
        start = sector * SECTOR_SIZE
        card.write_sector(sector, data[start : start + SECTOR_SIZE])

    layout = read_library_layout(card, 0)
    section_summaries: dict[str, object] = {}
    for section_name in INDEXED_SECTIONS:
        section_index = read_library_section_index(card, 0, section_name)
        spans = interpret_library_section_index(
            section_index,
            layout.record_count,
        )
        section_summaries[section_name] = {
            "node_counts": layout.section(section_name).node_counts,
            "span_count": len(spans),
            "record_count_per_level": tuple(
                sum(len(span.record_indices) for span in spans if span.level == level)
                for level in range(3)
            ),
        }

    return {
        "bytes": len(data),
        "sha256": sha256,
        "record_count": layout.record_count,
        "record_area_sectors": layout.record_area_sectors,
        "sections": section_summaries,
    }


def main(path: Path) -> None:
    summary = inspect_music_library(path.read_bytes())
    print(
        "MUSIC.LIB EVIDENCE PASS "
        f"bytes={summary['bytes']} "
        f"records={summary['record_count']} "
        f"record_area_sectors={summary['record_area_sectors']} "
        f"sha256={summary['sha256']}"
    )
    for name, section in summary["sections"].items():
        print(
            f"section={name} "
            f"node_counts={section['node_counts']} "
            f"spans={section['span_count']} "
            f"records_per_level={section['record_count_per_level']}"
        )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: musiclib_evidence_probe.py MUSIC.LIB")

    main(Path(sys.argv[1]))
