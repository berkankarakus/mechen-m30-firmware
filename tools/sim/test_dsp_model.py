import struct
import tempfile
import unittest
from pathlib import Path

from dsp_model import (
    MMM_MP_DSP_NAMES,
    select_dsp,
    select_initial_mengine_dsp_from_config_item_96,
    select_mengine_dsp,
)


class DspSelectorTests(unittest.TestCase):
    def test_table_preserves_recovered_firmware_spelling(self):
        with tempfile.TemporaryDirectory() as tmp:
            selection = select_dsp(0, Path(tmp))
        self.assertEqual(selection.firmware_name, "adMP3.dsp")
        self.assertEqual(selection.member_name, "admp3.dsp")
        self.assertEqual(len(MMM_MP_DSP_NAMES), 16)

    def test_missing_member_is_not_executed_or_invented(self):
        with tempfile.TemporaryDirectory() as tmp:
            selection = select_dsp(5, Path(tmp))
        self.assertFalse(selection.available)
        self.assertFalse(selection.payload_executable)
        self.assertIsNone(selection.sha256)

    def test_existing_member_is_header_checked_and_fingerprinted(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "admp3.dsp"
            path.write_bytes(b"yqhx" + struct.pack("<15I", *range(15)))
            selection = select_dsp(0, Path(tmp))
        self.assertTrue(selection.available)
        self.assertEqual(selection.size, 64)
        self.assertEqual(selection.header_words[0], 0x78687179)
        self.assertEqual(len(selection.sha256), 64)

    def test_offset_four_resident_header_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "admp3.dsp"
            path.write_bytes(b"\0\0\0\0yqhx" + bytes(58))
            with self.assertRaises(ValueError):
                select_dsp(0, Path(tmp))

    def test_index_bounds_are_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                select_dsp(-1, Path(tmp))
            with self.assertRaises(ValueError):
                select_dsp(16, Path(tmp))

    def test_mengine_processing_flag_selects_the_recovered_dsp_members(self):
        with tempfile.TemporaryDirectory() as tmp:
            processing = select_mengine_dsp(True, Path(tmp))
            bypass = select_mengine_dsp(False, Path(tmp))

        self.assertEqual(processing.format_index, 13)
        self.assertEqual(processing.firmware_name, "audiopp.dsp")
        self.assertEqual(bypass.format_index, 14)
        self.assertEqual(bypass.firmware_name, "adppext.dsp")
        self.assertFalse(processing.payload_executable)
        self.assertFalse(bypass.payload_executable)

    def test_mengine_processing_flag_requires_boolean_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                select_mengine_dsp(1, Path(tmp))

    def test_initial_config_item_96_default_selects_processing_dsp(self):
        config_item = bytes.fromhex("01 00 02 00 00 00 01 00")

        with tempfile.TemporaryDirectory() as tmp:
            selection = select_initial_mengine_dsp_from_config_item_96(
                config_item,
                Path(tmp),
            )

        self.assertEqual(selection.format_index, 13)
        self.assertEqual(selection.firmware_name, "audiopp.dsp")

    def test_initial_config_item_96_selects_bypass_for_values_other_than_one(self):
        config_item = bytes.fromhex("02 00 02 00 00 00 01 00")

        with tempfile.TemporaryDirectory() as tmp:
            selection = select_initial_mengine_dsp_from_config_item_96(
                config_item,
                Path(tmp),
            )

        self.assertEqual(selection.format_index, 14)
        self.assertEqual(selection.firmware_name, "adppext.dsp")

    def test_initial_config_item_96_requires_eight_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                select_initial_mengine_dsp_from_config_item_96(
                    bytes(7),
                    Path(tmp),
                )


if __name__ == "__main__":
    unittest.main()
