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
import tempfile

import libmodel


RECORD_START = 0x200
RECORD_SIZE = 0x100
TEXT_FIELDS = {
    "title": (0x00, 0x40),
    "artist": (0x40, 0x18),
    "album": (0x58, 0x30),
    "genre": (0x88, 0x18),
}


def _encode_text(value: str, width: int, original: bytes) -> bytes:
    """Encode a field while preserving the original ASCII/UTF-16 style."""
    if original[:2] == b"\xff\xfe" or any(ord(character) > 0xFF for character in value):
        encoded = b"\xff\xfe" + value.encode("utf-16-le")
        return encoded[: width - 2].ljust(width, b"\0")

    try:
        encoded = value.encode("latin-1")
    except UnicodeEncodeError as error:
        raise ValueError("value cannot be represented in this field") from error
    return encoded[: width - 1].ljust(width, b"\0")


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

    edited = apply_edits(input_path.read_bytes(), edits)
    with tempfile.TemporaryDirectory(prefix="m30-library-edit-") as temp_dir:
        modified_path = Path(temp_dir) / "modified.lib"
        rebuilt_path = Path(temp_dir) / "rebuilt.lib"
        modified_path.write_bytes(edited)
        libmodel.main(str(modified_path), str(rebuilt_path))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(rebuilt_path.read_bytes())


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
