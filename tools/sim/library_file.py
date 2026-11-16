"""Byte-layout model for the recovered ``MUSIC.LIB`` file header."""

from __future__ import annotations

from dataclasses import dataclass
import struct

from library_record_codec import LibraryRecord, decode_record
from sd_block_device import SdCardBlockDevice


SECTOR_SIZE = 512
HEADER_SIZE = 0x200
RECORD_SIZE = 0x100
SECTION_NODE_SIZE = 0x10
RECORD_START_SECTOR = 1
ORDER_TABLE_REFERENCE = 3
INVERSE_TABLE_REFERENCE = 4
NODE_INDEX_TABLE_REFERENCE = 5
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


@dataclass(frozen=True)
class LibrarySectionNode:
    """Decoded fields from one observed 16-byte index node."""

    node_type: int
    depth: int
    child_count: int
    song_count: int
    first_record_index: int
    first_child_index: int
    parent_index: int
    previous_index: int
    next_index: int


@dataclass(frozen=True)
class LibrarySectionTables:
    """Per-record tables emitted alongside one section's index nodes."""

    order: tuple[int, ...]
    inverse: tuple[int, ...]
    node_indices: tuple[int, ...]


@dataclass(frozen=True)
class LibrarySectionIndex:
    """Typed nodes and per-record tables for one section."""

    nodes_by_level: tuple[tuple[LibrarySectionNode, ...], ...]
    tables: LibrarySectionTables


def decode_library_section_node(data: bytes) -> LibrarySectionNode:
    """Decode one node using the recovered little-endian field layout."""
    if len(data) != SECTION_NODE_SIZE:
        raise ValueError("library section node must contain exactly 16 bytes")

    fields = struct.unpack("<BBHHHHHHH", data)

    return LibrarySectionNode(
        node_type=fields[0],
        depth=fields[1],
        child_count=fields[2],
        song_count=fields[3],
        first_record_index=fields[4],
        first_child_index=fields[5],
        parent_index=fields[6],
        previous_index=fields[7],
        next_index=fields[8],
    )


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


def read_library_image(
    device: SdCardBlockDevice,
    start_sector: int,
) -> bytes:
    """Read one ``MUSIC.LIB`` image from a caller-supplied start sector."""
    if start_sector < 0:
        raise ValueError("library start sector must be non-negative")

    header = device.read_sector(start_sector)
    record_count = struct.unpack_from("<H", header, 0x08)[0]
    record_bytes = record_count * RECORD_SIZE
    record_area_sectors = (record_bytes + SECTOR_SIZE - 1) // SECTOR_SIZE

    return header + b"".join(
        device.read_sector(start_sector + 1 + offset)
        for offset in range(record_area_sectors)
    )


def read_library_layout(
    device: SdCardBlockDevice,
    start_sector: int,
) -> MusicLibraryLayout:
    """Parse a library image read from the SD block boundary."""
    return parse_library_layout(read_library_image(device, start_sector))


def read_library_record(
    device: SdCardBlockDevice,
    start_sector: int,
    record_index: int,
) -> LibraryRecord:
    """Read and decode one bounded record from a caller-supplied SD image."""
    if start_sector < 0:
        raise ValueError("library start sector must be non-negative")

    if record_index < 0:
        raise ValueError("library record index must be non-negative")

    header = device.read_sector(start_sector)
    record_count = struct.unpack_from("<H", header, 0x08)[0]
    if record_index >= record_count:
        raise IndexError("library record index is outside the MUSIC.LIB record area")

    record_offset = HEADER_SIZE + record_index * RECORD_SIZE
    sector_offset, offset_in_sector = divmod(record_offset, SECTOR_SIZE)
    first_sector = device.read_sector(start_sector + sector_offset)
    record_end = offset_in_sector + RECORD_SIZE
    if record_end <= SECTOR_SIZE:
        record_bytes = first_sector[offset_in_sector:record_end]

    else:
        second_sector = device.read_sector(start_sector + sector_offset + 1)
        record_bytes = (
            first_sector[offset_in_sector:]
            + second_sector[: record_end - SECTOR_SIZE]
        )

    return decode_record(record_bytes)


def read_library_section_words(
    device: SdCardBlockDevice,
    start_sector: int,
    section_name: str,
    reference_index: int,
) -> tuple[int, ...]:
    """Read a referenced section table as raw little-endian 16-bit words."""
    if start_sector < 0:
        raise ValueError("library start sector must be non-negative")

    if not 0 <= reference_index < 7:
        raise ValueError("section reference index must fit the seven header entries")

    layout = parse_library_layout(read_library_image(device, start_sector))
    section = layout.section(section_name)
    sector = section.sector_references[reference_index]
    if sector == 0:
        return ()

    word_count = layout.record_count
    byte_count = word_count * 2
    sector_count = (byte_count + SECTOR_SIZE - 1) // SECTOR_SIZE
    data = b"".join(
        device.read_sector(start_sector + sector + offset)
        for offset in range(sector_count)
    )

    return struct.unpack_from(f"<{word_count}H", data, 0)


def read_library_section_tables(
    device: SdCardBlockDevice,
    start_sector: int,
    section_name: str,
) -> LibrarySectionTables:
    """Read the observed order, inverse, and node-index tables for a section."""
    return LibrarySectionTables(
        order=read_library_section_words(
            device,
            start_sector,
            section_name,
            ORDER_TABLE_REFERENCE,
        ),
        inverse=read_library_section_words(
            device,
            start_sector,
            section_name,
            INVERSE_TABLE_REFERENCE,
        ),
        node_indices=read_library_section_words(
            device,
            start_sector,
            section_name,
            NODE_INDEX_TABLE_REFERENCE,
        ),
    )


def read_library_section_index(
    device: SdCardBlockDevice,
    start_sector: int,
    section_name: str,
) -> LibrarySectionIndex:
    """Read one section without assigning user-facing sort or tree semantics."""
    nodes_by_level = tuple(
        tuple(
            decode_library_section_node(raw_node)
            for raw_node in read_library_section_nodes(
                device,
                start_sector,
                section_name,
                level,
            )
        )
        for level in range(3)
    )

    return LibrarySectionIndex(
        nodes_by_level=nodes_by_level,
        tables=read_library_section_tables(device, start_sector, section_name),
    )


def read_library_section_nodes(
    device: SdCardBlockDevice,
    start_sector: int,
    section_name: str,
    level: int,
) -> tuple[bytes, ...]:
    """Read referenced section nodes as bounded opaque 16-byte records."""
    if start_sector < 0:
        raise ValueError("library start sector must be non-negative")

    if not 0 <= level < 3:
        raise ValueError("section node level must be zero, one, or two")

    layout = parse_library_layout(read_library_image(device, start_sector))
    section = layout.section(section_name)
    node_count = section.node_counts[level]
    sector = section.sector_references[level]
    if node_count == 0 or sector == 0:
        return ()

    byte_count = node_count * SECTION_NODE_SIZE
    sector_count = (byte_count + SECTOR_SIZE - 1) // SECTOR_SIZE
    data = b"".join(
        device.read_sector(start_sector + sector + offset)
        for offset in range(sector_count)
    )

    return tuple(
        data[offset : offset + SECTION_NODE_SIZE]
        for offset in range(0, byte_count, SECTION_NODE_SIZE)
    )
