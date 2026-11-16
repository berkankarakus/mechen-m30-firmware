"""Byte-layout model for the recovered ``MUSIC.LIB`` file header."""

from __future__ import annotations

from dataclasses import dataclass
import struct


SECTOR_SIZE = 512
HEADER_SIZE = 0x200
RECORD_SIZE = 0x100
RECORD_START_SECTOR = 1
SECTION_HEADERS = (
    ("ALLSONG", 0x10),
    ("ALBUM", 0x2C),
    ("ARTIST", 0x48),
    ("GENRE", 0x64),
)


@dataclass(frozen=True)
class LibrarySection:
    """One section's counts and opaque sector references."""

    name: str
    node_counts: tuple[int, int, int]
    sector_references: tuple[int, ...]


@dataclass(frozen=True)
class MusicLibraryLayout:
    """Verified file geometry without interpreting index node contents."""

    record_count: int
    record_area_sectors: int
    sections: tuple[LibrarySection, ...]

    @property
    def record_area_end_sector(self) -> int:
        """Return the first sector after the padded record area."""
        return RECORD_START_SECTOR + self.record_area_sectors

    def section(self, name: str) -> LibrarySection:
        for section in self.sections:
            if section.name == name:
                return section

        raise KeyError(name)


def parse_library_layout(data: bytes) -> MusicLibraryLayout:
    """Parse the documented header and section directory from one library."""
    if len(data) < HEADER_SIZE:
        raise ValueError("MUSIC.LIB data is shorter than its header")

    record_count = struct.unpack_from("<H", data, 0x08)[0]
    record_bytes = record_count * RECORD_SIZE
    record_area_sectors = (record_bytes + SECTOR_SIZE - 1) // SECTOR_SIZE
    required_bytes = (RECORD_START_SECTOR + record_area_sectors) * SECTOR_SIZE
    if len(data) < required_bytes:
        raise ValueError("MUSIC.LIB data is shorter than its record area")

    sections: list[LibrarySection] = []
    for name, offset in SECTION_HEADERS:
        raw_name = data[offset : offset + 8].split(b"\0", 1)[0]
        if raw_name.decode("ascii") != name:
            raise ValueError(f"unexpected MUSIC.LIB section name at 0x{offset:x}")

        node_counts = struct.unpack_from("<3H", data, offset + 8)
        sector_references = struct.unpack_from("<7H", data, offset + 14)
        sections.append(
            LibrarySection(
                name=name,
                node_counts=node_counts,
                sector_references=sector_references,
            )
        )

    return MusicLibraryLayout(
        record_count=record_count,
        record_area_sectors=record_area_sectors,
        sections=tuple(sections),
    )
