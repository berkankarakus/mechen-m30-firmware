import unittest

from inspect_bootrom import (
    HANDLERS,
    KERNEL_INIT_SOURCES,
    ROM_SIZE,
    guard_matches,
    hexdump,
    kernel_init_source_slices,
    validate_dump,
)


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
        self.assertEqual(sorted(HANDLERS), [0x5F90, 0x6D6C, 0x6F18])
        self.assertIn("ExcCode 9", HANDLERS[0x6F18])

    def test_kernel_init_source_ranges_fit_the_dump(self):
        self.assertEqual(KERNEL_INIT_SOURCES[0x12000][0], 0x14)
        self.assertEqual(KERNEL_INIT_SOURCES[0x12014][0], 0x20)
        for offset, (size, _) in KERNEL_INIT_SOURCES.items():
            self.assertGreater(size, 0)
            self.assertLessEqual(offset + size, ROM_SIZE)

    def test_kernel_init_callback_word_is_little_endian_candidate(self):
        data = bytearray(ROM_SIZE)
        data[0x12000:0x12004] = bytes.fromhex("35 46 c0 bf")
        slices = kernel_init_source_slices(bytes(data))
        candidate = int.from_bytes(slices[0x12000][:4], "little")
        self.assertEqual(candidate, 0xbfc04635)
        self.assertEqual(candidate & 1, 1)

    def test_kernel_init_slices_use_window_offsets_and_exact_lengths(self):
        data = bytearray(ROM_SIZE)
        data[0x12000:0x12014] = bytes(range(0x14))
        data[0x12014:0x12034] = bytes(range(0x20))
        slices = kernel_init_source_slices(bytes(data))
        self.assertEqual(len(slices[0x12000]), 0x14)
        self.assertEqual(slices[0x12000], bytes(range(0x14)))
        self.assertEqual(slices[0x12014], bytes(range(0x20)))
        self.assertEqual(len(slices[0x12200]), 4)
        self.assertEqual(len(slices[0x12204]), 4)

    def test_hexdump_clamps_at_rom_edges(self):
        data = bytes(range(32))
        self.assertEqual(hexdump(data, 0, radius=4), "00 01 02 03")
        self.assertEqual(hexdump(data, 31, radius=4), "1b 1c 1d 1e 1f")


if __name__ == "__main__":
    unittest.main()
