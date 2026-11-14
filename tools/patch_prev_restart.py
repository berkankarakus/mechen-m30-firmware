#!/usr/bin/env python3
"""Reproduce an unsafe historical patch; this does not implement restart.

Static analysis showed that this site is the -5000 ms fast-backward
breakpoint, not a Previous-key time threshold.  Changing it can make a
previous-track transition start at the wrong position or chain-skip tracks.
The script remains only for forensic reproduction and refuses to patch unless
the caller explicitly acknowledges that risk.
"""

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
    if len(sys.argv) != 4 or sys.argv[1] != "--acknowledge-unsafe":
        raise SystemExit(
            "unsafe historical patch disabled; for forensic reproduction only: "
            "patch_prev_restart.py --acknowledge-unsafe INPUT_MENGINE.AP OUTPUT_MENGINE.AP"
        )
    patch(Path(sys.argv[2]), Path(sys.argv[3]))
