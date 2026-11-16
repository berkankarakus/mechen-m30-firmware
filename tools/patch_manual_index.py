#!/usr/bin/env python3
"""Disable automatic playlist regeneration while retaining manual Update Playlist."""
from __future__ import annotations
import shutil
import sys
from pathlib import Path

# Verified against the stock 2025-06-26 M30 payload and the established
# manual-index policy delta: config.ap +0x1e0d and udisk.ap +0x1909.
PATCHES = {"config.ap": (0x1E0D, 0x22, 0x10), "udisk.ap": (0x1909, 0x22, 0x10)}


def main(stock_root: str, output_root: str) -> None:
    src, dst = Path(stock_root), Path(output_root)
    dst.mkdir(parents=True, exist_ok=True)
    for name, (offset, expected, replacement) in PATCHES.items():
        data = bytearray((src / name).read_bytes())
        if data[offset] != expected:
            raise SystemExit(f"{name}+0x{offset:x}: expected 0x{expected:02x}, found 0x{data[offset]:02x}")
        data[offset] = replacement
        (dst / name).write_bytes(data)
        print(f"{name}+0x{offset:x}: 0x{expected:02x} -> 0x{replacement:02x}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: patch_manual_index.py STOCK_FW_DIR OUTPUT_DIR")
    main(*sys.argv[1:])
