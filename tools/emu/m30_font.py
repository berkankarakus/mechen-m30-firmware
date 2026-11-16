"""Read the sparse bitmap font shipped as ``new_m.fnt``.

The M30 font uses the Actions sparse-index layout: 1024 ten-byte entries at
0x10, followed by fixed-size glyph records at 0x2810.  This reader is
read-only and intentionally supports the ASCII subset needed by the screen
preview; it does not patch or rewrite the firmware font.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


MAGIC = b"FNT\x05"
INDEX_OFFSET = 0x10
INDEX_COUNT = 1024
INDEX_ENTRY_BYTES = 10
DATA_OFFSET = 0x2810
RECORD_BYTES = 61
ROW_BYTES = 2
ROWS_PER_RECORD = (RECORD_BYTES - 1) // ROW_BYTES
GLYPH_BITS = ROW_BYTES * 8
TRAILER_BYTES = 17


@dataclass(frozen=True)
class FontGlyph:
    codepoint: int
    advance: int
    rows: tuple[int, ...]


class M30Font:
    def __init__(self, path: Path, data: bytes):
        self.path = path
        self.data = data

    @classmethod
    def load(cls, path: Path) -> "M30Font":
        data = path.read_bytes()
        if data[:4] != MAGIC:
            raise ValueError(f"not an M30 Actions font: {path}")
        if (
            len(data) < DATA_OFFSET + TRAILER_BYTES
            or (len(data) - DATA_OFFSET - TRAILER_BYTES) % RECORD_BYTES
        ):
            raise ValueError(f"unexpected new_m.fnt record layout: {path}")
        return cls(path, data)

    def _record_index(self, codepoint: int) -> int | None:
        if not 0 <= codepoint < INDEX_COUNT * 64:
            return None
        block, bit = divmod(codepoint, 64)
        offset = INDEX_OFFSET + block * INDEX_ENTRY_BYTES
        base = int.from_bytes(self.data[offset:offset + 2], "little")
        presence = int.from_bytes(self.data[offset + 2:offset + 10], "little")
        mask = 1 << bit
        if not presence & mask:
            return None
        return base + (presence & (mask - 1)).bit_count()

    def glyph(self, char: str) -> FontGlyph:
        if len(char) != 1:
            raise ValueError("glyph() accepts one character")
        codepoint = ord(char)
        index = self._record_index(codepoint)
        if index is None:
            if char != "?":
                return self.glyph("?")
            return FontGlyph(ord("?"), 8, (0,) * ROWS_PER_RECORD)
        offset = DATA_OFFSET + index * RECORD_BYTES
        record = self.data[offset:offset + RECORD_BYTES]
        rows = tuple(
            int.from_bytes(record[row * ROW_BYTES:(row + 1) * ROW_BYTES], "big")
            for row in range(ROWS_PER_RECORD)
        )
        return FontGlyph(codepoint, record[-1], rows)

    @staticmethod
    def _scaled_advance(advance: int, pixel_scale: int) -> int:
        return (advance + pixel_scale - 1) // pixel_scale

    def text_width(self, text: str, *, pixel_scale: int = 1) -> int:
        if pixel_scale not in (1, 2):
            raise ValueError("pixel_scale must be 1 or 2")
        return sum(self._scaled_advance(self.glyph(char).advance, pixel_scale) for char in text)

    def draw_text(
        self,
        framebuffer,
        text: str,
        x: int,
        y: int,
        color: tuple[int, int, int],
        clip: tuple[int, int, int, int] | None = None,
        pixel_scale: int = 1,
    ) -> None:
        if pixel_scale not in (1, 2):
            raise ValueError("pixel_scale must be 1 or 2")
        cursor = x
        for char in text:
            glyph = self.glyph(char)
            output_rows = range(0, len(glyph.rows), pixel_scale)
            output_columns = range(0, GLYPH_BITS, pixel_scale)
            for row in output_rows:
                for column in output_columns:
                    ink = any(
                        glyph.rows[source_row] & (1 << (GLYPH_BITS - 1 - source_column))
                        for source_row in range(row, min(row + pixel_scale, len(glyph.rows)))
                        for source_column in range(column, min(column + pixel_scale, GLYPH_BITS))
                    )
                    if not ink:
                        continue
                    px, py = cursor + column // pixel_scale, y + row // pixel_scale
                    if clip and not (clip[0] <= px < clip[0] + clip[2] and clip[1] <= py < clip[1] + clip[3]):
                        continue
                    framebuffer.pixel(px, py, color)
            cursor += self._scaled_advance(glyph.advance, pixel_scale)

    def draw_marquee(
        self,
        framebuffer,
        text: str,
        x: int,
        y: int,
        width: int,
        height: int,
        color: tuple[int, int, int],
        offset: int = 0,
        gap_px: int = 12,
        pixel_scale: int = 1,
    ) -> None:
        text_width = self.text_width(text, pixel_scale=pixel_scale)
        clip = (x, y, width, height)
        if not text or text_width <= width:
            positions = (0,) if text else ()
        else:
            cycle = text_width + gap_px
            normalized = offset % cycle
            positions = []
            position = -normalized
            while position < width:
                if position + text_width > 0:
                    positions.append(position)
                position += cycle
        for relative_x in positions:
            self.draw_text(framebuffer, text, x + relative_x, y, color, clip, pixel_scale=pixel_scale)
