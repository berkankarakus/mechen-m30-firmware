#!/usr/bin/env python3
"""Inspect the M30 common.sty directory-list layout.

The structure sizes and field order come from the public Actions US212A UI
driver source.  This tool intentionally only reads a .sty file; it does not
rewrite resources or firmware.
"""

from __future__ import annotations

import json
import struct
import sys
from pathlib import Path


RESOURCE_TABLE = 0x400
LISTBOX_CTRL = 6
LISTBOX_SIZE = 28
LISTBOX_ITEM_SIZE = 44


def u16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def inspect(path: Path) -> dict[str, object]:
    data = path.read_bytes()
    if data[:4] != b"RU3\x19":
        raise ValueError(f"not an RU3 resource file: {path}")

    style_addr = u32(data, 8)
    style_begin = u32(data, style_addr + 8)
    listbox_addr = u32(data, style_begin + LISTBOX_CTRL * 8)
    fields = struct.unpack_from("<4I3H2B2H", data, listbox_addr)
    title_addr, slider_addr, item_addr, ratio_addr = fields[:4]
    back_id, back_x, back_y, inc_y, num_one_page, attrib, reserve = fields[4:]

    item = struct.unpack_from("<22H", data, item_addr)
    (
        list_back_id, head_id, head_act_id, head_x, head_y, back_id_item,
        back_act_id, back_x_item, back_y_item, tail_id, tail_act_id, tail_x,
        tail_y, data_x, data_y, data_width, data_height, data_color,
        data_act_color, item_attrib, str_attrib, item_reserve,
    ) = item

    return {
        "file": str(path),
        "style_addr": style_addr,
        "style_begin": style_begin,
        "listbox_addr": listbox_addr,
        "listbox": {
            "title_addr": title_addr,
            "slider_addr": slider_addr,
            "item_addr": item_addr,
            "ratio_addr": ratio_addr,
            "back_id": back_id,
            "back_x": back_x,
            "back_y": back_y,
            "row_height": inc_y,
            "items_per_page": num_one_page,
            "attrib": attrib,
            "reserve": reserve,
        },
        "item": {
            "head_id": head_id,
            "head_act_id": head_act_id,
            "head_x": head_x,
            "head_y": head_y,
            "back_id": back_id_item,
            "back_act_id": back_act_id,
            "data_x": data_x,
            "data_y": data_y,
            "data_width": data_width,
            "data_height": data_height,
            "data_color": data_color,
            "data_act_color": data_act_color,
            "attrib": item_attrib,
            "str_attrib": str_attrib,
            "active_display_mode": (str_attrib >> 4) & 0x3,
            "inactive_display_mode": (str_attrib >> 10) & 0x3,
        },
    }


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: inspect_sty_layout.py COMMON.STY")
    print(json.dumps(inspect(Path(sys.argv[1])), indent=2))

