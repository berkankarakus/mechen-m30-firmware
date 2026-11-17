import struct
import tempfile
import unittest
from pathlib import Path

from eq_binary_probe import verify
from m30_model import FIRMWARE_EQ_2024_04_PROFILE, FIRMWARE_EQ_CURRENT_PROFILE


def make_eq_members(profile):
    mengine = bytearray(0x5000)
    setting = bytearray(0x5B0B)
    struct.pack_into("<7H", mengine, 0x43EC, *profile.band_hz)
    struct.pack_into("<7H", mengine, 0x43FC, *profile.q_values)

    for selector in range(7):
        gains = profile.presets[selector].gain_int8
        assert gains is not None
        offset = 0x440C + selector * 7
        mengine[offset : offset + 7] = bytes(value & 0xFF for value in gains)

    custom_offset = 0x5A94 + 7 * 16
    setting[custom_offset : custom_offset + len(profile.custom_default)] = bytes(
        value & 0xFF for value in profile.custom_default
    )
    return bytes(mengine), bytes(setting)


class EqBinaryProbeTests(unittest.TestCase):
    def test_current_profile_accepts_current_contract(self):
        mengine, setting = make_eq_members(FIRMWARE_EQ_CURRENT_PROFILE)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mengine_path = root / "mengine.ap"
            setting_path = root / "setting.ap"
            mengine_path.write_bytes(mengine)
            setting_path.write_bytes(setting)

            verify(mengine_path, setting_path)

    def test_2024_profile_accepts_the_verified_50_hz_exception(self):
        mengine, setting = make_eq_members(FIRMWARE_EQ_2024_04_PROFILE)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mengine_path = root / "mengine.ap"
            setting_path = root / "setting.ap"
            mengine_path.write_bytes(mengine)
            setting_path.write_bytes(setting)

            with self.assertRaises(AssertionError):
                verify(mengine_path, setting_path)

            verify(
                mengine_path,
                setting_path,
                FIRMWARE_EQ_2024_04_PROFILE,
            )


if __name__ == "__main__":
    unittest.main()
