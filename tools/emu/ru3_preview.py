#!/usr/bin/env python3
"""Render static RU3 screen resources into a deterministic host preview.

This renderer covers the resource/geometry layer shared by M30 screens. It
draws direct RGB565 PicBox resources at their real coordinates and uses
resource-backed TextBox geometry for supplied placeholder or test strings.
It does not claim to execute an application's menu state machine, AP bank,
font rasterizer, or input handling.
"""

from __future__ import annotations

import argparse
import json
import struct
from dataclasses import dataclass
from pathlib import Path

from m30_font import M30Font
from m30_ui import Framebuffer, draw_text, rgb565
from music_bitmap import MusicBitmap, load_music_bitmap


WIDTH, HEIGHT = 320, 240
RU3_MAGIC = b"RU3\x19"


@dataclass(frozen=True)
class Ru3Preview:
    style_path: Path
    textboxes: tuple[object, ...]
    picboxes: tuple[object, ...]
    framebuffer: Framebuffer
    trace: dict[str, object]


def _resource_index(value: int) -> int | None:
    """Normalize an RU3 resource reference, including common.sty 0x8000 IDs."""
    if value == 0xFFFF:
        return None
    return value & 0x7FFF if value & 0x8000 else value


def _load_style(path: Path):
    data = path.read_bytes()
    if data[:4] != RU3_MAGIC:
        raise ValueError(f"not an RU3 resource file: {path}")
    style_addr = struct.unpack_from("<I", data, 8)[0]
    style_begin = struct.unpack_from("<I", data, style_addr + 8)[0]
    pic_addr, pic_count = struct.unpack_from("<II", data, style_begin + 8)
    text_addr, text_count = struct.unpack_from("<II", data, style_begin + 16)

    from m30_ui import PicBox, TextBox

    pics = []
    for index in range(pic_count):
        values = struct.unpack_from("<16H", data, pic_addr + index * 32)
        pics.append(PicBox(values[0], values[1], values[2], values[3], tuple(values[4:])))
    texts = []
    for index in range(text_count):
        values = struct.unpack_from("<10H", data, text_addr + index * 20)
        texts.append(TextBox(*values))
    return tuple(pics), tuple(texts)


def _draw_bitmap(frame: Framebuffer, bitmap: MusicBitmap, x: int, y: int) -> None:
    for row in range(bitmap.height):
        for column in range(bitmap.width):
            frame.pixel(x + column, y + row, rgb565(bitmap.pixels[row * bitmap.width + column]))


def render_style(
    path: Path,
    *,
    text_values: dict[int, str] | None = None,
    font: M30Font | None = None,
) -> Ru3Preview:
    picboxes, textboxes = _load_style(path)
    frame = Framebuffer()
    # Same background word used by the audited M30 clear-background path.
    frame.fill(rgb565(0x18C3))
    text_values = text_values or {}
    rendered_pics: list[dict[str, object]] = []
    skipped_pics: list[dict[str, object]] = []

    for index, picbox in enumerate(picboxes):
        resource_index = next(
            (_resource_index(value) for value in picbox.frames if _resource_index(value) is not None),
            None,
        )
        if resource_index is None:
            skipped_pics.append({"picbox": index, "reason": "no-frame"})
            continue
        try:
            bitmap = load_music_bitmap(path, resource_index)
        except ValueError as exc:
            skipped_pics.append({"picbox": index, "resource": resource_index, "reason": str(exc)})
            continue
        _draw_bitmap(frame, bitmap, picbox.x, picbox.y)
        rendered_pics.append(
            {
                "picbox": index,
                "resource": resource_index,
                "x": picbox.x,
                "y": picbox.y,
                "width": bitmap.width,
                "height": bitmap.height,
            }
        )

    rendered_texts: list[dict[str, object]] = []
    for index, textbox in enumerate(textboxes):
        value = text_values.get(index, f"TEXT {index}")
        color = rgb565(textbox.text_color)
        if font:
            font.draw_text(
                frame,
                value,
                textbox.x,
                textbox.y + 2,
                color,
                clip=(textbox.x, textbox.y, textbox.width, textbox.height),
                pixel_scale=2,
            )
        else:
            draw_text(
                frame,
                value,
                textbox.x,
                textbox.y,
                color,
                scale=1,
                clip=(textbox.x, textbox.y, textbox.width, textbox.height),
            )
        rendered_texts.append(
            {
                "textbox": index,
                "x": textbox.x,
                "y": textbox.y,
                "width": textbox.width,
                "height": textbox.height,
                "text": value,
                "rgb565": f"0x{textbox.text_color:04x}",
            }
        )

    trace = {
        "kind": "static-ru3-preview",
        "style": str(path),
        "provenance": "real RU3 PicBox/TextBox records; optional shipped font and host app state",
        "picboxes": rendered_pics,
        "skipped_picboxes": skipped_pics,
        "textboxes": rendered_texts,
        "framebuffer": [WIDTH, HEIGHT],
    }
    return Ru3Preview(path, textboxes, picboxes, frame, trace)


def _parse_text_values(values: list[str]) -> dict[int, str]:
    result: dict[int, str] = {}
    for value in values:
        try:
            index, text = value.split("=", 1)
            result[int(index, 0)] = text
        except ValueError as exc:
            raise ValueError(f"text must use INDEX=VALUE: {value!r}") from exc
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--style", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--trace", type=Path, required=True)
    parser.add_argument("--text", action="append", default=[], metavar="INDEX=VALUE")
    parser.add_argument("--font", type=Path, help="M30 new_m.fnt; defaults to the style directory")
    args = parser.parse_args()
    font_path = args.font or args.style.with_name("new_m.fnt")
    font = M30Font.load(font_path) if font_path.exists() else None
    preview = render_style(args.style, text_values=_parse_text_values(args.text), font=font)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    preview.framebuffer.ppm(args.out)
    args.trace.parent.mkdir(parents=True, exist_ok=True)
    args.trace.write_text(json.dumps(preview.trace, indent=2) + "\n")
    print(
        f"RU3 PREVIEW PASS style={args.style.name} "
        f"picboxes={len(preview.trace['picboxes'])} "
        f"textboxes={len(preview.trace['textboxes'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
