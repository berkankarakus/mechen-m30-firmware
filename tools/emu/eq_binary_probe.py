#!/usr/bin/env python3
"""Cross-check the host EQ contract against extracted firmware bytes."""

from __future__ import annotations

import argparse
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "sim"))

from m30_model import (  # noqa: E402
    FIRMWARE_EQ_BAND_HZ,
    FIRMWARE_EQ_CUSTOM_DEFAULT,
    FIRMWARE_EQ_PRESETS,
    FIRMWARE_EQ_Q_X10,
)


ENGINE_GAIN_TABLE = 0x440C
ENGINE_FREQUENCY_TABLE = 0x43EC
ENGINE_Q_TABLE = 0x43FC
SETTING_EQ_TABLE = 0x5A94
ENGINE_ROW_STRIDE = 7
SETTING_ROW_STRIDE = 16


def signed_bytes(data: bytes) -> tuple[int, ...]:
    return tuple(value - 256 if value >= 128 else value for value in data)


def u16_rows(data: bytes, offset: int, count: int) -> tuple[int, ...]:
    return struct.unpack_from("<" + "H" * count, data, offset)


def verify(mengine_path: Path, setting_path: Path) -> None:
    mengine = mengine_path.read_bytes()
    setting = setting_path.read_bytes()

    frequencies = u16_rows(mengine, ENGINE_FREQUENCY_TABLE, len(FIRMWARE_EQ_BAND_HZ))
    if frequencies != FIRMWARE_EQ_BAND_HZ:
        raise AssertionError(f"frequency table {frequencies!r} != model {FIRMWARE_EQ_BAND_HZ!r}")

    q_values = u16_rows(mengine, ENGINE_Q_TABLE, len(FIRMWARE_EQ_Q_X10))
    if q_values != FIRMWARE_EQ_Q_X10:
        raise AssertionError(f"Q table {q_values!r} != model {FIRMWARE_EQ_Q_X10!r}")

    for selector in range(7):
        offset = ENGINE_GAIN_TABLE + selector * ENGINE_ROW_STRIDE
        actual = signed_bytes(mengine[offset : offset + ENGINE_ROW_STRIDE])
        expected = FIRMWARE_EQ_PRESETS[selector].gains_db
        if actual != expected:
            raise AssertionError(
                f"mengine selector {selector} {actual!r} != model {expected!r}"
            )

    custom_offset = SETTING_EQ_TABLE + 7 * SETTING_ROW_STRIDE
    custom = signed_bytes(setting[custom_offset : custom_offset + len(FIRMWARE_EQ_CUSTOM_DEFAULT)])
    if custom != FIRMWARE_EQ_CUSTOM_DEFAULT:
        raise AssertionError(
            f"setting Custom default {custom!r} != model {FIRMWARE_EQ_CUSTOM_DEFAULT!r}"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mengine_ap", type=Path)
    parser.add_argument("setting_ap", type=Path)
    args = parser.parse_args()
    verify(args.mengine_ap, args.setting_ap)
    print("EQ BINARY PROBE PASS bands=7 gain_rows=7 custom=setting.ap:0x5b04")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
