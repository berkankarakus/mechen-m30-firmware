#!/usr/bin/env python3
"""Extract an AP resident trap stub by its load address, checking segment metadata."""
from __future__ import annotations

import argparse
import struct
from pathlib import Path


def u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("setting_ap", type=Path)
    parser.add_argument("--address", type=lambda value: int(value, 0), default=0xBFC16584)
    parser.add_argument("--length", type=lambda value: int(value, 0), default=4)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    image = args.setting_ap.read_bytes()
    segments = []
    for offset in range(0x100, 0x1000, 12):
        file_offset, load_address, size = struct.unpack_from("<III", image, offset)
        if file_offset and load_address and size and file_offset + size <= len(image):
            segments.append((file_offset, load_address, size, f"bank@{offset:#x}"))
    for header in (0x08, 0x14):
        file_offset, size, load_address = struct.unpack_from("<III", image, header)
        if file_offset and size and load_address and file_offset + size <= len(image):
            segments.append((file_offset, load_address, size, f"resident@{header:#x}"))

    matches = [segment for segment in segments
               if segment[1] <= args.address
               and args.address + args.length <= segment[1] + segment[2]]
    if len(matches) != 1:
        raise SystemExit(f"expected one containing segment, got {len(matches)}")
    file_offset, load_address, size, name = matches[0]
    image_offset = file_offset + args.address - load_address
    stub = image[image_offset:image_offset + args.length]
    if args.address == 0xBFC16584 and args.length == 4 and stub != bytes.fromhex("0f 6b 05 e8"):
        raise SystemExit(f"unexpected trap bytes at {image_offset:#x}: {stub.hex(' ')}")
    if args.output:
        args.output.write_bytes(stub)
    print(f"AP_STUB_PASS segment={name} load={load_address:#x} file={image_offset:#x} "
          f"address={args.address:#x} bytes={stub.hex(' ')}")


if __name__ == "__main__":
    main()
