import unittest

from library_record import LibraryFallbackRecord


class LibraryFallbackRecordTests(unittest.TestCase):
    def test_fallback_uses_short_name_and_fixed_metadata(self):
        record = LibraryFallbackRecord.from_short_name("TRACK~1.MP3")
        self.assertEqual(record.title, "TRACK~1.MP3")
        self.assertEqual(record.artist, "No Artist")
        self.assertEqual(record.album, "No Album")
        self.assertEqual(record.genre, "No Genre")
        self.assertFalse(record.tag_ok)

    def test_fallback_rejects_an_empty_name(self):
        with self.assertRaises(ValueError):
            LibraryFallbackRecord.from_short_name("")


if __name__ == "__main__":
    unittest.main()
