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
    FIRMWARE_EQ_CURRENT_PROFILE,
    FIRMWARE_EQ_PROFILES,
    FirmwareEqProfile,
    find_firmware_eq_profile,
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


def verify(
    mengine_path: Path,
    setting_path: Path,
    profile: FirmwareEqProfile = FIRMWARE_EQ_CURRENT_PROFILE,
) -> None:
    mengine = mengine_path.read_bytes()
    setting = setting_path.read_bytes()

    frequencies = u16_rows(mengine, ENGINE_FREQUENCY_TABLE, len(profile.band_hz))
    if frequencies != profile.band_hz:
        raise AssertionError(f"frequency table {frequencies!r} != model {profile.band_hz!r}")

    q_values = u16_rows(mengine, ENGINE_Q_TABLE, len(profile.q_x10))
    if q_values != profile.q_x10:
        raise AssertionError(f"Q table {q_values!r} != model {profile.q_x10!r}")

    for selector in range(7):
        offset = ENGINE_GAIN_TABLE + selector * ENGINE_ROW_STRIDE
        actual = signed_bytes(mengine[offset : offset + ENGINE_ROW_STRIDE])
        expected = profile.presets[selector].gains_db
        if actual != expected:
            raise AssertionError(
                f"mengine selector {selector} {actual!r} != model {expected!r}"
            )

    custom_offset = SETTING_EQ_TABLE + 7 * SETTING_ROW_STRIDE
    custom = signed_bytes(setting[custom_offset : custom_offset + len(profile.custom_default)])
    if custom != profile.custom_default:
        raise AssertionError(
            f"setting Custom default {custom!r} != model {profile.custom_default!r}"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mengine_ap", type=Path)
    parser.add_argument("setting_ap", type=Path)
    parser.add_argument(
        "--profile",
        choices=tuple(FIRMWARE_EQ_PROFILES),
        default=FIRMWARE_EQ_CURRENT_PROFILE.name,
    )
    args = parser.parse_args()
    profile = find_firmware_eq_profile(args.profile)
    verify(args.mengine_ap, args.setting_ap, profile)
    print(
        "EQ BINARY PROBE PASS "
        f"profile={profile.name} bands=7 gain_rows=7 custom=setting.ap:0x5b04"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
