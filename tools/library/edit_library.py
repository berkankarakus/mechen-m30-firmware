#!/usr/bin/env python3
"""Safely edit MUSIC.LIB metadata and rebuild its derived indexes.

The editor never changes the input file.  It copies only the requested text
fields, preserves the location/link tail byte-for-byte, and delegates index
construction to the checked-in host model.  Output below /Volumes is refused
so a mounted card cannot be overwritten accidentally.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
import struct
import tempfile

SIM_ROOT = Path(__file__).resolve().parents[1] / "sim"
if str(SIM_ROOT) not in sys.path:
    sys.path.insert(0, str(SIM_ROOT))

import libmodel
from library_file import (
    interpret_library_section_index,
    parse_library_layout,
    read_library_section_index,
)
from sd_block_device import SdCardBlockDevice


RECORD_START = 0x200
RECORD_SIZE = 0x100
TEXT_FIELDS = {
    "title": (0x00, 0x40),
    "artist": (0x40, 0x18),
    "album": (0x58, 0x30),
    "genre": (0x88, 0x18),
}
SECTION_HEADER_OFFSETS = (0x10, 0x2C, 0x48, 0x64)
SECTOR_SIZE = 512


def _encode_text(value: str, width: int, original: bytes) -> bytes:
    """Encode a field while preserving the original ASCII/UTF-16 style."""
    if "\0" in value:
        raise ValueError("metadata values cannot contain NUL characters")
    if original[:2] == b"\xff\xfe" or any(ord(character) > 0xFF for character in value):
        try:
            encoded = b"\xff\xfe" + value.encode("utf-16-le")
        except UnicodeEncodeError as error:
            raise ValueError("value contains an invalid Unicode character") from error
        if len(encoded) > width:
            raise ValueError(f"metadata value does not fit in {width} bytes")
        return encoded.ljust(width, b"\0")

    try:
        encoded = value.encode("latin-1") + b"\0"
    except UnicodeEncodeError as error:
        raise ValueError("value cannot be represented in this field") from error
    if len(encoded) > width:
        raise ValueError(f"metadata value does not fit in {width} bytes")
    return encoded.ljust(width, b"\0")


def parse_edit(spec: str) -> tuple[int, str, str]:
    """Parse ``RECORD.FIELD=VALUE`` from the command line."""
    try:
        target, value = spec.split("=", 1)
        index_text, field = target.split(".", 1)
        record_index = int(index_text, 10)
    except (ValueError, AttributeError) as error:
        raise ValueError("edit must be RECORD.FIELD=VALUE") from error

    if field not in TEXT_FIELDS:
        raise ValueError(f"unsupported field: {field}")
    if record_index < 0:
        raise ValueError("record index must be non-negative")
    return record_index, field, value


def apply_edits(data: bytes, edits: list[tuple[int, str, str]]) -> bytes:
    """Return an edited image while preserving every non-text record byte."""
    if len(data) < RECORD_START:
        raise ValueError("MUSIC.LIB image is shorter than its header")

    record_count = int.from_bytes(data[8:10], "little")
    required = RECORD_START + record_count * RECORD_SIZE
    if len(data) < required:
        raise ValueError("MUSIC.LIB image is shorter than its record area")

    edited = bytearray(data)
    for record_index, field, value in edits:
        if record_index >= record_count:
            raise IndexError(f"record index {record_index} is outside the library")
        offset, width = TEXT_FIELDS[field]
        record_start = RECORD_START + record_index * RECORD_SIZE
        original = bytes(edited[record_start + offset : record_start + offset + width])
        encoded = _encode_text(value, width, original)
        edited[record_start + offset : record_start + offset + width] = encoded
    return bytes(edited)


def read_existing_tie_orders(data: bytes) -> tuple[tuple[int, ...], ...] | None:
    """Read existing section ranks for stable equal-key rebuilding.

    A freshly generated synthetic fixture has no section tables, so the editor
    falls back to the host model's normal stable ordering in that case.
    """
    if len(data) < RECORD_START:
        return None
    record_count = int.from_bytes(data[8:10], "little")
    orders: list[tuple[int, ...]] = []
    for header_offset in SECTION_HEADER_OFFSETS:
        order_sector = struct.unpack_from("<H", data, header_offset + 14 + 3 * 2)[0]
        start = order_sector * SECTOR_SIZE
        end = start + record_count * 2
        if order_sector == 0 or end > len(data):
            return None
        order = struct.unpack_from(f"<{record_count}H", data, start)
        if sorted(order) != list(range(record_count)):
            return None
        ranks = [0] * record_count
        for position, record_index in enumerate(order):
            ranks[record_index] = position
        orders.append(tuple(ranks))
    return tuple(orders)


def validate_library_image(data: bytes) -> None:
    """Validate all recovered section tables and node links."""
    if len(data) % SECTOR_SIZE:
        raise ValueError("MUSIC.LIB image size must be sector-aligned")
    layout = parse_library_layout(data)
    device = SdCardBlockDevice(len(data) // SECTOR_SIZE)
    device.storage[:] = data
    for section in layout.sections:
        index = read_library_section_index(device, 0, section.name)
        interpret_library_section_index(index, layout.record_count)


def _refuse_volume_output(output: Path) -> None:
    resolved = output.expanduser().resolve()
    if resolved.parts and resolved.parts[0] == "/" and len(resolved.parts) > 1 and resolved.parts[1] == "Volumes":
        raise ValueError("refusing to write a MUSIC.LIB directly under /Volumes")


def edit_library(input_path: Path, output_path: Path, edits: list[tuple[int, str, str]]) -> None:
    """Edit a copy and rebuild its derived section tables."""
    input_path = input_path.expanduser().resolve()
    output_path = output_path.expanduser().resolve()
    _refuse_volume_output(output_path)
    if input_path == output_path:
        raise ValueError("input and output must be different files")

    original = input_path.read_bytes()
    edited = apply_edits(original, edits)
    if edited == original:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(original)
        return
    tie_orders = read_existing_tie_orders(edited)
    with tempfile.TemporaryDirectory(prefix="m30-library-edit-") as temp_dir:
        modified_path = Path(temp_dir) / "modified.lib"
        rebuilt_path = Path(temp_dir) / "rebuilt.lib"
        modified_path.write_bytes(edited)
        libmodel.main(str(modified_path), str(rebuilt_path), tie_orders=tie_orders)
        rebuilt = rebuilt_path.read_bytes()
        validate_library_image(rebuilt)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(rebuilt)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--set",
        dest="edits",
        action="append",
        required=True,
        metavar="RECORD.FIELD=VALUE",
    )
    args = parser.parse_args(argv)

    try:
        edits = [parse_edit(spec) for spec in args.edits]
        edit_library(args.input, args.output, edits)
    except (IndexError, OSError, ValueError) as error:
        raise SystemExit(f"edit_library: {error}") from error
    print(f"wrote rebuilt MUSIC.LIB: {args.output}")


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    main()
