#!/usr/bin/env python3
"""Render a Ghidra-guided approximation of the M30 now-playing screen.

This is deliberately a host emulator, not a claim that qemu-system-mipsel can
boot the M30.  It consumes the real RU3 ``music.sty`` resource and validates
the real ``music.ap`` bank/call-site used by the shared marquee renderer.  The
small framebuffer renderer is useful for regression tests while the remaining
ATJ2127 UI dispatcher and LCD hardware are being modelled.
"""

from __future__ import annotations

import argparse
import json
import struct
from dataclasses import dataclass, field
from pathlib import Path


WIDTH, HEIGHT = 320, 240
SCROLL_VADDR = 0x40D55078
SCROLL_STYLE = 0x2005
MAIN_PAINT_STYLE = 0x2005
SECONDARY_STYLE = 0x2004
RU3_MAGIC = b"RU3\x19"

# Ghidra names these as _UNK_40d551xx because they are literal-pool function
# pointers.  These are the exact addresses read from the real AP bank.
DISPATCH_POINTERS = {
    0x40D5516C: "ui_dispatch",
    0x40D55170: "ui_read_status",
    0x40D55174: "ui_status_state",
    0x40D55178: "ui_set_backlight",
    0x40D5517C: "ui_restore_context",
    0x40D55180: "timer_ms",
    0x40D55198: "scroll_state",
    0x40D551B0: "scroll_state_byte",
    0x40D54F10: "key_read_begin",
    0x40D54F14: "key_read_event",
    0x40D54F18: "key_event_decode",
    0x40D54F1C: "key_event_fallback",
    0x40D54F20: "scroll_event_local",
    0x40D54F24: "key_poll",
    0x40D54F28: "key_event_callback",
}


def rgb565(value: int) -> tuple[int, int, int]:
    return (
        ((value >> 11) & 0x1F) * 255 // 31,
        ((value >> 5) & 0x3F) * 255 // 63,
        (value & 0x1F) * 255 // 31,
    )


def _u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


@dataclass(frozen=True)
class TextBox:
    style_id: int
    x: int
    y: int
    width: int
    height: int
    back_x: int
    back_y: int
    back_id: int
    text_color: int
    attrib: int


@dataclass(frozen=True)
class PicBox:
    style_id: int
    x: int
    y: int
    attrib: int
    frames: tuple[int, ...]


@dataclass(frozen=True)
class MusicStyle:
    path: Path
    textboxes: tuple[TextBox, ...]
    picboxes: tuple[PicBox, ...]

    @classmethod
    def load(cls, path: Path) -> "MusicStyle":
        data = path.read_bytes()
        if data[:4] != RU3_MAGIC:
            raise ValueError(f"not an RU3 resource: {path}")
        style_addr = _u32(data, 8)
        style_begin = _u32(data, style_addr + 8)
        pic_addr, pic_count = _u32(data, style_begin + 8), _u32(data, style_begin + 12)
        text_addr, text_count = _u32(data, style_begin + 16), _u32(data, style_begin + 20)
        pics: list[PicBox] = []
        for i in range(pic_count):
            v = struct.unpack_from("<16H", data, pic_addr + i * 32)
            pics.append(PicBox(v[0], v[1], v[2], v[3], tuple(v[4:])))
        texts: list[TextBox] = []
        for i in range(text_count):
            v = struct.unpack_from("<10H", data, text_addr + i * 20)
            texts.append(TextBox(*v))
        return cls(path, tuple(texts), tuple(pics))

    def textboxes_by_geometry(self) -> tuple[TextBox, ...]:
        return tuple(sorted(self.textboxes, key=lambda item: (item.y, item.x)))

    def color(self, box: TextBox) -> tuple[int, int, int]:
        return rgb565(box.text_color)


@dataclass(frozen=True)
class Bank:
    file_offset: int
    virtual_address: int
    size: int


@dataclass(frozen=True)
class FirmwareTrace:
    ap_path: Path
    banks: tuple[Bank, ...]
    scroll_bank: Bank
    scroll_file_offset: int
    instruction: bytes
    scroll_style_id: int
    dispatch_targets: dict[str, int]
    source: str = "FUN_40d54f2c / shared scroll renderer"

    @classmethod
    def load(cls, path: Path) -> "FirmwareTrace":
        data = path.read_bytes()
        if data[4:8] != b"yqhx":
            raise ValueError(f"not an Actions .ap file: {path}")
        header_words = struct.unpack_from("<12I", data, 0x2C)
        banks: list[Bank] = []
        for offset in range(0x100, 0x100 + header_words[0] - 11, 12):
            file_offset, address, size = struct.unpack_from("<III", data, offset)
            if file_offset and address and size and file_offset + size <= len(data):
                banks.append(Bank(file_offset, address, size))
        bank = next((b for b in banks if b.virtual_address <= SCROLL_VADDR < b.virtual_address + b.size), None)
        if bank is None:
            raise ValueError(f"music.ap has no bank containing 0x{SCROLL_VADDR:08x}")
        file_offset = bank.file_offset + SCROLL_VADDR - bank.virtual_address
        instruction = data[file_offset:file_offset + 4]
        # MIPS16e: the audited call-site is ``li v0, 0x2005``.
        style_by_instruction = {
            bytes.fromhex("04 f0 05 6a"): 0x2005,
            bytes.fromhex("04 f0 01 6a"): 0x2001,
        }
        if instruction not in style_by_instruction:
            raise ValueError(
                f"unexpected scroll call-site at 0x{SCROLL_VADDR:08x}: "
                f"{instruction.hex(' ')}"
            )
        dispatch_targets: dict[str, int] = {}
        for address, name in DISPATCH_POINTERS.items():
            pointer_bytes = cls._read_virtual(data, banks, address, 4)
            dispatch_targets[name] = struct.unpack_from("<I", pointer_bytes)[0]
        return cls(path, tuple(banks), bank, file_offset, instruction, style_by_instruction[instruction], dispatch_targets)

    @staticmethod
    def _read_virtual(data: bytes, banks: list[Bank], address: int, size: int) -> bytes:
        for bank in banks:
            if bank.virtual_address <= address and address + size <= bank.virtual_address + bank.size:
                offset = bank.file_offset + address - bank.virtual_address
                return data[offset:offset + size]
        raise ValueError(f"no AP bank contains virtual range 0x{address:08x}+{size}")

    def json(self) -> dict[str, object]:
        return {
            "ap": str(self.ap_path),
            "source": self.source,
            "scroll_call": {
                "virtual_address": f"0x{SCROLL_VADDR:08x}",
                "file_offset": f"0x{self.scroll_file_offset:x}",
                "instruction": self.instruction.hex(" "),
                "style_id": f"0x{self.scroll_style_id:04x}",
            },
            "dispatch_targets": {
                name: f"0x{address:08x}" for name, address in self.dispatch_targets.items()
            },
            "banks": [
                {"file_offset": f"0x{b.file_offset:x}", "virtual_address": f"0x{b.virtual_address:x}", "size": b.size}
                for b in self.banks
            ],
        }


@dataclass
class Framebuffer:
    width: int = WIDTH
    height: int = HEIGHT
    pixels: bytearray = field(default_factory=lambda: bytearray(WIDTH * HEIGHT * 3))

    def fill(self, color: tuple[int, int, int]) -> None:
        r, g, b = color
        self.pixels[:] = bytes((r, g, b)) * (self.width * self.height)

    def rect(self, x: int, y: int, width: int, height: int, color: tuple[int, int, int]) -> None:
        r, g, b = color
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(self.width, x + width), min(self.height, y + height)
        for yy in range(y0, y1):
            start = (yy * self.width + x0) * 3
            self.pixels[start:(yy * self.width + x1) * 3] = bytes((r, g, b)) * (x1 - x0)

    def pixel(self, x: int, y: int, color: tuple[int, int, int]) -> None:
        if 0 <= x < self.width and 0 <= y < self.height:
            start = (y * self.width + x) * 3
            self.pixels[start:start + 3] = bytes(color)

    def ppm(self, path: Path) -> None:
        path.write_bytes(f"P6\n{self.width} {self.height}\n255\n".encode() + self.pixels)


# Compact 5x7 glyphs.  The emulator is for layout/scroll behaviour; it does
# not pretend to reproduce the proprietary M30 font rasterizer.
_FONT = {
    " ": (0, 0, 0, 0, 0),
    **{str(i): tuple(int(row, 2) for row in rows) for i, rows in {
        "0": ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
        "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
        "2": ("01110", "10001", "00001", "00010", "00100", "01000", "11111"),
        "3": ("11110", "00001", "00001", "01110", "00001", "00001", "11110"),
        "4": ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
        "5": ("11111", "10000", "10000", "11110", "00001", "00001", "11110"),
        "6": ("00110", "01000", "10000", "11110", "10001", "10001", "01110"),
        "7": ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
        "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
        "9": ("01110", "10001", "10001", "01111", "00001", "00010", "11100"),
    }.items()},
}
for _char, _rows in {
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "C": ("01111", "10000", "10000", "10000", "10000", "10000", "01111"),
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "G": ("01111", "10000", "10000", "10111", "10001", "10001", "01111"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": ("11111", "00100", "00100", "00100", "00100", "00100", "11111"),
    "J": ("00111", "00010", "00010", "00010", "10010", "10010", "01100"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "Q": ("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    "V": ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    "W": ("10001", "10001", "10001", "10101", "10101", "11011", "10001"),
    "X": ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
    "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    "Z": ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
    ":": ("00000", "00100", "00100", "00000", "00100", "00100", "00000"),
    "-": ("00000", "00000", "00000", "11111", "00000", "00000", "00000"),
    "/": ("00001", "00010", "00100", "01000", "10000", "10000", "10000"),
}.items():
    _FONT[_char] = tuple(int(row, 2) for row in _rows)


def draw_text(fb: Framebuffer, text: str, x: int, y: int, color: tuple[int, int, int], scale: int = 2, clip: tuple[int, int, int, int] | None = None) -> None:
    for index, char in enumerate(text.upper()):
        glyph = _FONT.get(char, _FONT[" "])
        gx = x + index * 6 * scale
        for row, bits in enumerate(glyph):
            for col in range(5):
                if bits & (1 << (4 - col)):
                    for sy in range(scale):
                        for sx in range(scale):
                            px, py = gx + col * scale + sx, y + row * scale + sy
                            if clip and not (clip[0] <= px < clip[0] + clip[2] and clip[1] <= py < clip[1] + clip[3]):
                                continue
                            fb.pixel(px, py, color)


@dataclass
class NowPlaying:
    style: MusicStyle
    trace: FirmwareTrace
    title: str = "TITLE"
    artist: str = "ARTIST"
    album: str = "ALBUM"
    filename: str = "FILE"
    scroll_offset: int = 0

    def dispatch_trace(self) -> list[dict[str, object]]:
        # This is the exact Ghidra-audited boundary that a future QEMU host
        # shim will receive from the real MIPS16 bank.
        return [
            {"kind": "ui_dispatch", "style_id": f"0x{MAIN_PAINT_STYLE:04x}", "source": "FUN_40154ddc", "text": self.title},
            {"kind": "ui_dispatch", "style_id": f"0x{self.trace.scroll_style_id:04x}", "source": self.trace.source, "text": self.title, "scroll_offset": self.scroll_offset},
        ]

    def observed_dispatch_trace(self) -> list[dict[str, object]]:
        """Return the observed dispatcher envelope from the real-bank probe.

        Pointer payloads are represented by stable semantic labels here. Their
        stack addresses and unresolved internal fields deliberately stay out
        of the host contract until a second payload probe identifies them.
        """
        return [
            {"op": 0x14, "a0": 0x18C3, "a1": 0, "a2": 0, "role": "clear_background"},
            {"op": 0x12, "a0": 0, "a1": 0, "a2": 0, "role": "clear_content"},
            {"op": 0x14, "a0": 0x18C3, "a1": 0, "a2": 0, "role": "clear_background"},
            {"op": 0x12, "a0": 0, "a1": 0, "a2": 0, "role": "clear_content"},
            {"op": 0x02, "payload": "control_0x1012", "role": "draw_control"},
            {"op": 0x02, "payload": "control_0x1013", "role": "draw_control"},
            {"op": 0x03, "a2": 1, "style_id": f"0x{self.trace.scroll_style_id:04x}", "text": self.title, "role": "draw_active_text"},
            {"op": 0x06, "a2": 6, "text": self.title, "scroll_offset": self.scroll_offset, "role": "draw_dynamic_text"},
            {"op": 0x03, "a2": 1, "style_id": f"0x{SECONDARY_STYLE:04x}", "text": self.title, "role": "draw_cleanup_text"},
        ]

    def render(self) -> Framebuffer:
        fb = Framebuffer()
        fb.fill((18, 19, 22))
        red = (255, 24, 32)
        dim = (80, 20, 24)
        white = (235, 235, 235)
        # Actual M30 screen bands observed in FUN_40154ddc.
        fb.rect(0, 0, WIDTH, 28, (12, 13, 15))
        fb.rect(0, 179, WIDTH, 61, (12, 13, 15))
        # Album-art control comes from the first 150x150 textbox.
        art = next(box for box in self.style.textboxes if box.x == 0 and box.y == 28 and box.width == 150)
        art_color = self.style.color(art)
        fb.rect(art.x, art.y, art.width, art.height, (22, 23, 26))
        fb.rect(12, 40, 126, 126, art_color if art_color != (0, 0, 0) else red)
        # A simple note-like mark makes the empty-art state unmistakable.
        fb.rect(64, 70, 10, 58, (18, 19, 22))
        fb.rect(73, 70, 32, 10, (18, 19, 22))
        fb.rect(97, 70, 10, 46, (18, 19, 22))
        # Metadata geometries are taken directly from textboxes 1..4.
        boxes = [box for box in self.style.textboxes if box.width == 129 and box.height == 20]
        values = (self.title, self.artist, self.album, self.filename)
        labels = ("TITLE", "ARTIST", "ALBUM", "FILE")
        for box, label, value in zip(boxes, labels, values):
            color = self.style.color(box)
            draw_text(fb, label, box.x, box.y, red, 1, (box.x, box.y, box.width, box.height))
            # Keep the value inside the exact M30 clipping rectangle.  The
            # offset models the shared renderer's horizontal pass.
            draw_text(fb, value, box.x + 42 - self.scroll_offset, box.y + 9, color, 1, (box.x, box.y, box.width, box.height))
            fb.rect(box.x, box.y + box.height - 1, box.width, 1, dim)
        # Transport/progress area: geometry is from the actual resource, not
        # the HTML mockup.  It is intentionally schematic until picbox image
        # decoding is added to the QEMU host shim.
        draw_text(fb, "00:18", 70, 202, white, 2)
        fb.rect(70, 220, 180, 4, dim)
        fb.rect(70, 220, 72, 4, red)
        draw_text(fb, "03/18", 250, 202, white, 1)
        draw_text(fb, "<", 158, 188, red, 2)
        draw_text(fb, ">", 180, 188, red, 2)
        return fb


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--music-ap", type=Path, required=True)
    parser.add_argument("--music-sty", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True, help="PPM framebuffer output")
    parser.add_argument("--trace", type=Path, help="write Ghidra/QEMU boundary trace as JSON")
    parser.add_argument("--title", default="TITLE")
    parser.add_argument("--artist", default="ARTIST")
    parser.add_argument("--album", default="ALBUM")
    parser.add_argument("--file", dest="filename", default="FILE")
    parser.add_argument("--offset", type=int, default=0)
    args = parser.parse_args()
    trace = FirmwareTrace.load(args.music_ap)
    ui = NowPlaying(MusicStyle.load(args.music_sty), trace, args.title, args.artist, args.album, args.filename, args.offset)
    ui.render().ppm(args.out)
    if args.trace:
        args.trace.write_text(json.dumps({
            "firmware": trace.json(),
            "calls": ui.dispatch_trace(),
            "observed_dispatch": ui.observed_dispatch_trace(),
        }, indent=2) + "\n")
    print(f"rendered {args.out} using {len(trace.banks)} real AP banks; scroll call 0x{SCROLL_VADDR:08x} -> style 0x{SCROLL_STYLE:04x}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
