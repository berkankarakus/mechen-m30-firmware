#!/usr/bin/env python3
"""Validate and summarize an ATJ2127 0x9fc00000 Boot ROM dump."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


ROM_SIZE = 0x40000
HANDLERS = {
    0x5F90: "exception dispatch alternate target (candidate)",
    0x6D6C: "EPC exception handler target (candidate)",
}


def hexdump(data: bytes, start: int, radius: int = 16) -> str:
    lo = max(0, start - radius)
    hi = min(len(data), start + radius)
    return " ".join(f"{b:02x}" for b in data[lo:hi])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("dump", type=Path)
    args = parser.parse_args()
    data = args.dump.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    print(f"file:   {args.dump}")
    print(f"size:   0x{len(data):x} ({len(data)} bytes)")
    print(f"sha256: {digest}")
    if len(data) != ROM_SIZE:
        print(f"ERROR: expected exactly 0x{ROM_SIZE:x} bytes")
        return 1

    print("candidate ROM offsets (bfc0xxxx uncached alias -> 9fc0xxxx):")
    for offset, label in HANDLERS.items():
        print(f"  0x{offset:04x}: {label}")
        print(f"    {hexdump(data, offset)}")

    guard = bytes.fromhex("ff ff 03 00")
    matches = [i for i in range(len(data) - len(guard) + 1) if data[i : i + len(guard)] == guard]
    print(f"0x0003ffff little-endian matches: {len(matches)}")
    if matches:
        print("  " + ", ".join(f"0x{x:x}" for x in matches[:32]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
