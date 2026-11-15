#!/usr/bin/env python3
"""Check the tiny extracted ``aud_dev.drv`` member without executing it."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "emu"))

from yqhx import YqhxImage  # noqa: E402


AUDDEV_SEGMENT = (0x300, 0x8, 0xBFC09F58)
AUDDEV_BSS = (0x9FC34160, 0)
AUDDEV_ENTRY = 0x1C009000
AUDDEV_BYTES = bytes.fromhex("106b05e80f6b05e8")


def verify(path: Path) -> None:
    image = YqhxImage.load(path)
    segment = image.segments[0]
    actual_segment = (segment.file_offset, segment.length, segment.destination)
    if actual_segment != AUDDEV_SEGMENT:
        raise AssertionError(f"audio-device segment {actual_segment!r} != {AUDDEV_SEGMENT!r}")
    if (image.bss_address, image.bss_size) != AUDDEV_BSS:
        raise AssertionError(
            f"audio-device BSS {(image.bss_address, image.bss_size)!r} != {AUDDEV_BSS!r}"
        )
    if image.entry != AUDDEV_ENTRY:
        raise AssertionError(
            f"audio-device entry 0x{image.entry:08x} != 0x{AUDDEV_ENTRY:08x}"
        )
    body = path.read_bytes()[AUDDEV_SEGMENT[0] : AUDDEV_SEGMENT[0] + len(AUDDEV_BYTES)]
    if body != AUDDEV_BYTES:
        raise AssertionError(f"audio-device body {body.hex()} != {AUDDEV_BYTES.hex()}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("audio_device_driver", type=Path)
    args = parser.parse_args()
    verify(args.audio_device_driver)
    print("AUDIO DEVICE BINARY PROBE PASS segment=0xbfc09f58+0x8 body=2x-cop2-write")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
