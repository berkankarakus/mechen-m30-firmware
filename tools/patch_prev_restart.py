#!/usr/bin/env python3
"""Make the music previous key restart the current track from the beginning."""

from pathlib import Path
import sys


SITE = 0x3A64
OLD = bytes.fromhex("82f3 086a 4bea")  # li v0,5000; neg v0
NEW = bytes.fromhex("006a 0065 4bea")  # li v0,0; nop; neg v0


def patch(src: Path, dst: Path) -> None:
    data = bytearray(src.read_bytes())
    if data[SITE:SITE + len(OLD)] != OLD:
        got = data[SITE:SITE + len(OLD)].hex(" ")
        raise SystemExit(f"unexpected previous-key threshold at 0x{SITE:x}: {got}")
    data[SITE:SITE + len(OLD)] = NEW
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(data)
    print(f"previous-key threshold 5000 ms -> 0 ms at file offset 0x{SITE:x}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: patch_prev_restart.py INPUT_MENGINE.AP OUTPUT_MENGINE.AP")
    patch(Path(sys.argv[1]), Path(sys.argv[2]))
