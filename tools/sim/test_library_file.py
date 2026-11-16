import struct
import unittest

from sd_block_device import SdCardBlockDevice
from library_file import (
    HEADER_SIZE,
    RECORD_SIZE,
    SECTOR_SIZE,
    parse_library_layout,
    read_library_image,
    read_library_layout,
)


def make_library(record_count: int = 3) -> bytearray:
    record_sectors = (record_count * RECORD_SIZE + SECTOR_SIZE - 1) // SECTOR_SIZE
    data = bytearray((1 + record_sectors) * SECTOR_SIZE)
    struct.pack_into("<H", data, 0x08, record_count)

    for name, offset in (("ALLSONG", 0x10), ("ALBUM", 0x2C), ("ARTIST", 0x48), ("GENRE", 0x64)):
        data[offset : offset + len(name)] = name.encode("ascii")

    struct.pack_into("<3H", data, 0x10 + 8, 1, 0, 0)
    struct.pack_into("<7H", data, 0x10 + 14, 3, 0, 0, 4, 5, 0, 0)
    return data


class MusicLibraryLayoutTests(unittest.TestCase):
    def test_reads_library_image_from_caller_supplied_sd_sector(self):
        image = make_library()
        card = SdCardBlockDevice(sector_count=5)
        for offset in range(len(image) // SECTOR_SIZE):
            start = offset * SECTOR_SIZE
            card.write_sector(1 + offset, image[start : start + SECTOR_SIZE])

        self.assertEqual(read_library_image(card, 1), bytes(image))
        self.assertEqual(read_library_layout(card, 1).record_count, 3)

    def test_sd_bounds_reject_an_incomplete_record_area(self):
        image = make_library()
        card = SdCardBlockDevice(sector_count=2)
        card.write_sector(1, image[:SECTOR_SIZE])

        with self.assertRaises(IndexError):
            read_library_layout(card, 1)

    def test_parses_record_area_and_section_directory(self):
        layout = parse_library_layout(bytes(make_library()))

        self.assertEqual(layout.record_count, 3)
        self.assertEqual(layout.record_area_sectors, 2)
        self.assertEqual(layout.record_area_end_sector, 3)
        self.assertEqual(layout.section("ALLSONG").node_counts, (1, 0, 0))
        self.assertEqual(layout.section("ALLSONG").sector_references, (3, 0, 0, 4, 5, 0, 0))
        self.assertEqual(layout.section("GENRE").node_counts, (0, 0, 0))

    def test_zero_records_still_has_a_valid_header(self):
        layout = parse_library_layout(bytes(make_library(0)))

        self.assertEqual(layout.record_area_sectors, 0)
        self.assertEqual(layout.record_area_end_sector, 1)

    def test_truncated_record_area_is_rejected(self):
        data = make_library(3)[:HEADER_SIZE]

        with self.assertRaises(ValueError):
            parse_library_layout(bytes(data))

    def test_unknown_section_name_is_rejected(self):
        data = make_library()
        data[0x2C : 0x2C + 5] = b"OTHER"

        with self.assertRaises(ValueError):
            parse_library_layout(bytes(data))


if __name__ == "__main__":
    unittest.main()
