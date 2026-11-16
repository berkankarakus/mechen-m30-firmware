#!/usr/bin/env python3
"""Compose the first offline M30 patch set.

This intentionally works on already-unpacked AP files.  It combines:

* the existing v5 build's AP files;
* the two hardware-accepted automatic-library bypass bytes found in the
  community V1.206+ payload; and
* the V1.101.11 music.ap delta, which includes the accepted end-of-track
  ASRC-drain fix.

No firmware image is flashed by this script.  The caller repacks the output
with tools/repack_fw.py after the byte guards pass.

usage: patch_first_pass.py STOCK_FW V5_FW DRAIN_FW OUT_FW
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path


FILES = (
    "browser.ap",
    "config.ap",
    "mainmenu.ap",
    "mengine.ap",
    "music.ap",
    "playlist.ap",
    "setting.ap",
    "udisk.ap",
)

# These are the two one-byte changes in the hardware-accepted community
# payload that suppress automatic file-list generation while retaining the
# manual Settings -> Update Playlist path.
AUTO_INDEX_GUARDS = {
    # cmp -l reports one-based positions: 7694 -> zero-based 0x1e0d and
    # 6410 -> zero-based 0x1909.
    "config.ap": (0x1E0D, 0x22, 0x10),
    "udisk.ap": (0x1909, 0x22, 0x10),
}


def changed_ranges(a: bytes, b: bytes) -> list[tuple[int, int]]:
    positions = [i for i, (x, y) in enumerate(zip(a, b)) if x != y]
    if not positions:
        return []
    out: list[tuple[int, int]] = []
    start = end = positions[0]
    for pos in positions[1:]:
        if pos == end + 1:
            end = pos
        else:
            out.append((start, end))
            start = end = pos
    out.append((start, end))
    return out


def main(stock_root: str, v5_root: str, drain_root: str, out_root: str) -> None:
    stock = Path(stock_root)
    v5 = Path(v5_root)
    drain = Path(drain_root)
    out = Path(out_root)
    out.mkdir(parents=True, exist_ok=True)

    for name in FILES:
        stock_bytes = (stock / name).read_bytes()
        # A minimal V5 build only emits modules it changed.  For untouched
        # modules (currently config.ap and udisk.ap), start from stock and
        # then apply the automatic-index guards below.
        v5_path = v5 / name
        result = bytearray(v5_path.read_bytes() if v5_path.exists() else stock_bytes)
        drain_bytes = (drain / name).read_bytes()
        if len(stock_bytes) != len(result) or len(stock_bytes) != len(drain_bytes):
            raise SystemExit(f"{name}: module size differs")

        # Only import community bytes where the v5 patch did not already
        # touch the stock module.  This makes accidental patch collisions
        # fail loudly instead of silently choosing one implementation.
        v5_ranges = changed_ranges(stock_bytes, result)
        for lo, hi in changed_ranges(stock_bytes, drain_bytes):
            if any(lo <= v5_hi and hi >= v5_lo for v5_lo, v5_hi in v5_ranges):
                raise SystemExit(f"{name}: community playback delta overlaps v5 at 0x{lo:x}-0x{hi:x}")
            result[lo : hi + 1] = drain_bytes[lo : hi + 1]

        if name in AUTO_INDEX_GUARDS:
            off, old, new = AUTO_INDEX_GUARDS[name]
            if stock_bytes[off] != old or result[off] != old:
                raise SystemExit(f"{name}: automatic-index guard byte is not the expected stock value")
            result[off] = new

        (out / name).write_bytes(result)

    print("first-pass AP composition succeeded")
    print("  automatic file-list regeneration: disabled")
    print("  end-of-track community playback delta: imported")
    print(f"  output: {out}")


if __name__ == "__main__":
    if len(sys.argv) != 5:
        raise SystemExit(__doc__)
    main(*sys.argv[1:])
