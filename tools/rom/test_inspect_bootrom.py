import unittest

from inspect_bootrom import HANDLERS, ROM_SIZE, guard_matches, hexdump, validate_dump


class BootRomInspectorTests(unittest.TestCase):
    def test_accepts_exactly_one_rom_window(self):
        validate_dump(bytes(ROM_SIZE))

    def test_rejects_partial_and_oversized_reads(self):
        with self.assertRaisesRegex(ValueError, "expected exactly"):
            validate_dump(bytes(ROM_SIZE - 1))
        with self.assertRaisesRegex(ValueError, "expected exactly"):
            validate_dump(bytes(ROM_SIZE + 1))

    def test_finds_guard_without_confusing_candidate_offsets(self):
        data = bytearray(ROM_SIZE)
        data[0x1234:0x1238] = bytes.fromhex("ff ff 03 00")
        self.assertEqual(guard_matches(data), [0x1234])
        self.assertEqual(sorted(HANDLERS), [0x5F90, 0x6D6C])

    def test_hexdump_clamps_at_rom_edges(self):
        data = bytes(range(32))
        self.assertEqual(hexdump(data, 0, radius=4), "00 01 02 03")
        self.assertEqual(hexdump(data, 31, radius=4), "1b 1c 1d 1e 1f")


if __name__ == "__main__":
    unittest.main()
