"""Host model of the observed ``ALBUM.PIC`` cache record boundary."""

from __future__ import annotations

from dataclasses import dataclass


ALBUM_PIC_HEADER_BYTES = 6
ALBUM_PIC_OK = "OK"
ALBUM_PIC_NONE = "NO"
RGB565_BYTES_PER_PIXEL = 2


@dataclass(frozen=True)
class AlbumPicRecord:
    """One cache record without interpreting the RGB565 byte order."""

    status: str
    x: int
    y: int
    width: int
    height: int
    pixels: bytes

    def __post_init__(self) -> None:
        if self.status not in (ALBUM_PIC_OK, ALBUM_PIC_NONE):
            raise ValueError("ALBUM.PIC status must be OK or NO")
        geometry = (self.x, self.y, self.width, self.height)

        if any(not 0 <= value <= 0xFF for value in geometry):
            raise ValueError("ALBUM.PIC geometry fields must fit one byte")

        if self.status == ALBUM_PIC_NONE:
            if (self.x, self.y, self.width, self.height) != (0, 0, 0, 0):
                raise ValueError("NO ALBUM.PIC records must have zero geometry")
            if self.pixels:
                raise ValueError("NO ALBUM.PIC records must not contain pixels")

        if self.status == ALBUM_PIC_OK:
            if self.width == 0 or self.height == 0:
                raise ValueError("OK ALBUM.PIC records must have non-zero dimensions")
            expected_size = self.width * self.height * RGB565_BYTES_PER_PIXEL
            if len(self.pixels) != expected_size:
                raise ValueError("OK ALBUM.PIC pixel payload has the wrong size")

    def encode(self) -> bytes:
        """Serialize the observed six-byte header and optional pixel payload."""
        header = self.status.encode("ascii") + bytes(
            (self.x, self.y, self.width, self.height)
        )

        return header + self.pixels


def decode_album_pic(data: bytes) -> AlbumPicRecord:
    """Decode one exact ``ALBUM.PIC`` record without rendering it."""
    if len(data) < ALBUM_PIC_HEADER_BYTES:
        raise ValueError("ALBUM.PIC record is shorter than its header")

    try:
        status = data[:2].decode("ascii")

    except UnicodeDecodeError as exception:
        raise ValueError("ALBUM.PIC status is not ASCII") from exception

    record = AlbumPicRecord(
        status=status,
        x=data[2],
        y=data[3],
        width=data[4],
        height=data[5],
        pixels=data[ALBUM_PIC_HEADER_BYTES:],
    )

    return record
