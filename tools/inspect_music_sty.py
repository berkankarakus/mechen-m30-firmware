#!/usr/bin/env python3
"""Inspect the fixed control groups used by the M30 music.sty resource.

The public US212A UI headers define the binary layouts for picbox, textbox,
numbox, timebox, and progressbar controls.  This reader is intentionally
read-only and validates the resource file before emitting JSON, so it can be
used as a preflight step before any resource-only patch.
"""

from __future__ import annotations

import json
import struct
import sys
from pathlib import Path


HEADER = 0x400
GROUPS = (
    ("generic", 0, 0),
    ("picbox", 32, 9),
    ("textbox", 20, 10),
    ("numbox", 28, 14),
    ("timebox", 24, 12),
    ("progressbar", 24, 12),
)


def u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def u16s(data: bytes, offset: int, size: int) -> list[int]:
    return list(struct.unpack_from(f"<{size // 2}H", data, offset))


def parse(path: Path) -> dict[str, object]:
    data = path.read_bytes()
    if data[:4] != b"RU3\x19":
        raise ValueError(f"not an RU3 resource file: {path}")

    style_addr = u32(data, 8)
    style_begin = u32(data, style_addr + 8)
    if style_begin + len(GROUPS) * 8 > len(data):
        raise ValueError("style group table is outside the resource")

    groups: dict[str, object] = {}
    for group_index, (name, item_size, _expected_fields) in enumerate(GROUPS):
        address = u32(data, style_begin + group_index * 8)
        count = u32(data, style_begin + group_index * 8 + 4)
        if name == "generic":
            groups[name] = {"address": address, "count": count}
            continue
        if item_size * count > len(data) - address:
            raise ValueError(f"{name} group exceeds resource bounds")

        items = []
        for index in range(count):
            values = u16s(data, address + index * item_size, item_size)
            item: dict[str, object] = {"index": index, "offset": address + index * item_size}
            if name == "picbox":
                item.update({
                    "id": values[0], "x": values[1], "y": values[2],
                    "attrib": values[3], "frames": values[4:],
                })
            elif name == "textbox":
                item.update({
                    "id": values[0], "x": values[1], "y": values[2],
                    "width": values[3], "height": values[4],
                    "back_x": values[5], "back_y": values[6],
                    "back_id": values[7], "text_color": values[8],
                    "attrib": values[9],
                })
            else:
                item["words"] = values
            items.append(item)
        groups[name] = {"address": address, "count": count, "items": items}

    return {
        "file": str(path),
        "size": len(data),
        "style_addr": style_addr,
        "style_begin": style_begin,
        "groups": groups,
    }


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: inspect_music_sty.py MUSIC.STY")
    print(json.dumps(parse(Path(sys.argv[1])), indent=2))
