"""Byte-level codec for the recovered 256-byte MUSIC.LIB record."""

from __future__ import annotations

from dataclasses import dataclass
import struct


RECORD_SIZE = 0x100


def _text(data: bytes) -> str:
    if data[:2] == b"\xff\xfe":
        return data[2:].decode("utf-16-le", "replace").split("\0", 1)[0]

    return data.split(b"\0", 1)[0].decode("latin-1")


@dataclass(frozen=True)
class LibraryRecord:
    title: str
    artist: str
    album: str
    genre: str
    track_text: str
    tag_ok: bool
    extension: str
    always_one: int
    location_primary: bytes
    track_number: int
    location_secondary: bytes
    previous_index: int
    next_index: int


def decode_record(data: bytes) -> LibraryRecord:
    """Decode one record without assigning semantics to opaque location bytes."""
    if len(data) != RECORD_SIZE:
        raise ValueError("MUSIC.LIB records must be exactly 256 bytes")

    return LibraryRecord(
        title=_text(data[0x00:0x40]),
        artist=_text(data[0x40:0x58]),
        album=_text(data[0x58:0x88]),
        genre=_text(data[0x88:0xA0]),
        track_text=data[0xA0:0xA3].split(b"\0", 1)[0].decode("ascii"),
        tag_ok=data[0xA3] != 0,
        extension=data[0xA4:0xA8].split(b"\0", 1)[0].decode("latin-1"),
        always_one=data[0xA8],
        location_primary=data[0xA9:0xF2],
        track_number=struct.unpack_from("<H", data, 0xF2)[0],
        location_secondary=data[0xF4:0xFC],
        previous_index=struct.unpack_from("<H", data, 0xFC)[0],
        next_index=struct.unpack_from("<H", data, 0xFE)[0],
    )
