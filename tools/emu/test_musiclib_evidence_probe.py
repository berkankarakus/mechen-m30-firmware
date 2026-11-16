import unittest

from musiclib_evidence_probe import inspect_music_library


def make_empty_library() -> bytes:
    data = bytearray(512)
    for name, offset in (
        ("ALLSONG", 0x10),
        ("ALBUM", 0x2C),
        ("ARTIST", 0x48),
        ("GENRE", 0x64),
    ):
        data[offset : offset + len(name)] = name.encode("ascii")

    return bytes(data)


class MusicLibraryEvidenceProbeTests(unittest.TestCase):
    def test_accepts_a_sector_aligned_empty_library_with_any_hash(self):
        summary = inspect_music_library(
            make_empty_library(),
            expected_sha256=None,
        )

        self.assertEqual(summary["bytes"], 512)
        self.assertEqual(summary["record_count"], 0)
        self.assertEqual(summary["record_area_sectors"], 0)
        self.assertEqual(summary["sections"]["ALBUM"]["span_count"], 0)

    def test_rejects_a_non_sector_aligned_image(self):
        with self.assertRaises(ValueError):
            inspect_music_library(bytes(511), expected_sha256=None)

    def test_rejects_a_hash_mismatch_before_interpreting_the_image(self):
        with self.assertRaises(ValueError):
            inspect_music_library(make_empty_library(), expected_sha256="0" * 64)


if __name__ == "__main__":
    unittest.main()
