import unittest

from filesystem_extension import FIRMWARE_EXTENSION_SLOTS, FilesystemExtensionTable


class FilesystemExtensionTableTests(unittest.TestCase):
    def setUp(self) -> None:
        self.table = FilesystemExtensionTable()

    def test_table_matches_the_recovered_31_slot_vocabulary(self):
        self.assertEqual(len(FIRMWARE_EXTENSION_SLOTS), 31)
        self.assertEqual(self.table.slot_for_extension("MP3"), 0)
        self.assertEqual(self.table.slot_for_extension("JPEG"), 9)
        self.assertEqual(self.table.slot_for_extension("*f"), 29)

    def test_extension_lookup_is_case_insensitive(self):
        self.assertEqual(self.table.slot_for_extension("flac"), 4)
        self.assertIsNone(self.table.slot_for_extension("FLACX"))

    def test_acceptance_requires_explicit_slot_selection(self):
        self.assertTrue(self.table.accepts_slot("mp3", {0}))
        self.assertFalse(self.table.accepts_slot("mp3", set()))
        self.assertFalse(self.table.accepts_slot("bin", {0}))


if __name__ == "__main__":
    unittest.main()
