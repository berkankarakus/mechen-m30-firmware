import unittest

from metadata_reader import (
    MetadataReadChunk,
    plan_metadata_operation,
    plan_metadata_read,
)


class MetadataReaderTests(unittest.TestCase):
    def test_read_is_split_at_each_internal_buffer_boundary(self):
        chunks = plan_metadata_read(0x1F0, 0x220)

        self.assertEqual(
            chunks,
            (
                MetadataReadChunk(0x1F0, 0x10, True),
                MetadataReadChunk(0x200, 0x200, True),
                MetadataReadChunk(0x400, 0x10, False),
            ),
        )

    def test_read_inside_one_buffer_does_not_flush_early(self):
        chunks = plan_metadata_read(0x24, 0x20)

        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].offset, 0x24)
        self.assertEqual(chunks[0].length, 0x20)
        self.assertFalse(chunks[0].flush_after)

    def test_empty_read_has_no_chunks(self):
        self.assertEqual(plan_metadata_read(0x200, 0), ())

    def test_operation_preserves_trailing_skip_arithmetic(self):
        plan = plan_metadata_operation(0x1F0, 0x220, 0x260)

        self.assertEqual(plan.chunks[0], MetadataReadChunk(0x1F0, 0x10, True))
        self.assertEqual(plan.trailing_skip, 0x40)

    def test_operation_rejects_total_shorter_than_copy(self):
        with self.assertRaises(ValueError):
            plan_metadata_operation(0, 0x21, 0x20)


if __name__ == "__main__":
    unittest.main()
