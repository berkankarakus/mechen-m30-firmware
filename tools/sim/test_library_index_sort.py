import struct
import unittest

from library_index_sort import sort_record_indices


def make_record(
    *,
    title: bytes = b"",
    album: bytes = b"",
    artist: bytes = b"",
    genre: bytes = b"",
    track: int = 0,
) -> bytes:
    record = bytearray(0x100)
    record[0x00 : 0x00 + len(title)] = title
    record[0x40 : 0x40 + len(artist)] = artist
    record[0x58 : 0x58 + len(album)] = album
    record[0x88 : 0x88 + len(genre)] = genre
    struct.pack_into("<b", record, 0xF2, track)
    return bytes(record)


class LibraryIndexSortTests(unittest.TestCase):
    def test_all_song_sort_is_ascii_case_insensitive_and_stable(self):
        records = (
            make_record(title=b"beta\0"),
            make_record(title=b"ALPHA\0"),
            make_record(title=b"alpha\0"),
        )

        self.assertEqual(sort_record_indices(records, "ALLSONG"), (1, 2, 0))

    def test_album_sort_uses_signed_track_byte_before_previous_rank(self):
        records = (
            make_record(album=b"Album\0", track=0),
            make_record(album=b"album\0", track=-1),
            make_record(album=b"Other\0", track=0),
        )

        self.assertEqual(
            sort_record_indices(records, "ALBUM", previous_rank=(2, 1, 0)),
            (1, 0, 2),
        )

    def test_non_first_section_requires_previous_rank(self):
        records = (make_record(artist=b"Artist\0"),)

        with self.assertRaises(ValueError):
            sort_record_indices(records, "ARTIST")

    def test_rejects_non_record_sized_input(self):
        with self.assertRaises(ValueError):
            sort_record_indices((bytes(0xFF),), "ALLSONG")


if __name__ == "__main__":
    unittest.main()
