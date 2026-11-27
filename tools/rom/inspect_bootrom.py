#!/usr/bin/env python3
"""Validate and summarize an ATJ2127 0x9fc00000 Boot ROM dump."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


ROM_SIZE = 0x40000
GUARD_BYTES = bytes.fromhex("ff ff 03 00")
HANDLERS = {
    0x5F90: "exception dispatch alternate target (candidate)",
    0x6D6C: "EPC exception handler target (candidate)",
    0x6F18: "ExcCode 9 vector target from ker_init slot 9 (candidate)",
}
KERNEL_INIT_SOURCES = {
    0x12000: (0x14, "callback structure source candidate; runtime mapping unverified"),
    0x12014: (0x20, "second structure source candidate; runtime mapping unverified"),
    0x12200: (4, "word source candidate; runtime mapping unverified"),
    0x12204: (4, "adjacent word read by kernel init; runtime mapping unverified"),
}


def hexdump(data: bytes, start: int, radius: int = 16) -> str:
    lo = max(0, start - radius)
    hi = min(len(data), start + radius)
    return " ".join(f"{b:02x}" for b in data[lo:hi])


def guard_matches(data: bytes) -> list[int]:
    """Return offsets containing the observed little-endian 0x0003ffff guard."""
    return [
        offset
        for offset in range(len(data) - len(GUARD_BYTES) + 1)
        if data[offset : offset + len(GUARD_BYTES)] == GUARD_BYTES
    ]


def kernel_init_source_slices(data: bytes) -> dict[int, bytes]:
    """Extract the documented candidate source ranges from a full ADFU dump."""
    validate_dump(data)
    return {
        offset: data[offset : offset + size]
        for offset, (size, _) in KERNEL_INIT_SOURCES.items()
    }


def validate_dump(data: bytes) -> None:
    """Reject a partial or oversized read before interpreting ROM offsets."""
    if len(data) != ROM_SIZE:
        raise ValueError(f"expected exactly 0x{ROM_SIZE:x} bytes, got 0x{len(data):x}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("dump", type=Path)
    args = parser.parse_args()
    data = args.dump.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    print(f"file:   {args.dump}")
    print(f"size:   0x{len(data):x} ({len(data)} bytes)")
    print(f"sha256: {digest}")
    try:
        validate_dump(data)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 1

    print("candidate ROM offsets (bfc0xxxx uncached alias -> 9fc0xxxx):")
    for offset, label in HANDLERS.items():
        print(f"  0x{offset:04x}: {label}")
        print(f"    {hexdump(data, offset)}")

    print("kernel-init source candidates (ADFU-window offsets; runtime mapping unverified):")
    source_slices = kernel_init_source_slices(data)
    for offset, (size, label) in KERNEL_INIT_SOURCES.items():
        chunk = source_slices[offset]
        print(f"  0x{offset:05x} length=0x{size:x}: {label}")
        print(f"    {chunk.hex(' ')}")
        if offset == 0x12000 and len(chunk) >= 4:
            candidate = int.from_bytes(chunk[:4], "little")
            mode = "odd/MIPS16 candidate" if candidate & 1 else "mode unresolved"
            print(f"    first-word-callback-candidate=0x{candidate:08x} ({mode})")

    matches = guard_matches(data)
    print(f"0x0003ffff little-endian matches: {len(matches)}")
    if matches:
        print("  " + ", ".join(f"0x{x:x}" for x in matches[:32]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
