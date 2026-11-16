import unittest

from usound_format import expand_three_to_four
from usound_software_ring import (
    DIRECT_READY_THRESHOLD,
    EXPANDED_READY_THRESHOLD,
    RING_CAPACITY,
    SoftwareRing,
)


class UsoundSoftwareRingTests(unittest.TestCase):
    def test_direct_write_advances_and_stores_bytes(self) -> None:
        ring = SoftwareRing()

        self.assertFalse(ring.produce(b"abc", expanded=False))
        self.assertEqual(ring.data[:3], b"abc")
        self.assertEqual(ring.write_offset, 3)
        self.assertEqual(ring.available, 3)

    def test_direct_write_wraps(self) -> None:
        ring = SoftwareRing(write_offset=RING_CAPACITY - 2)

        ring.produce(b"abcd", expanded=False)
        self.assertEqual(ring.data[-2:], b"ab")
        self.assertEqual(ring.data[:2], b"cd")
        self.assertEqual(ring.write_offset, 2)

    def test_expanded_write_uses_three_to_four_layout(self) -> None:
        ring = SoftwareRing()

        ring.produce(bytes((1, 2, 3)), expanded=True)
        self.assertEqual(ring.data[:4], expand_three_to_four(bytes((1, 2, 3))))
        self.assertEqual(ring.available, 4)

    def test_ready_edge_uses_format_specific_threshold(self) -> None:
        direct = SoftwareRing()
        self.assertFalse(direct.produce(bytes(DIRECT_READY_THRESHOLD - 1), expanded=False))
        self.assertTrue(direct.produce(b"x", expanded=False))

        expanded = SoftwareRing()
        source = bytes(EXPANDED_READY_THRESHOLD // 4 * 3)
        self.assertTrue(expanded.produce(source, expanded=True))
        self.assertEqual(expanded.available, EXPANDED_READY_THRESHOLD)

    def test_overrun_sets_available_to_wrapped_write_offset(self) -> None:
        ring = SoftwareRing(write_offset=RING_CAPACITY - 4, available=RING_CAPACITY - 4)

        ring.produce(b"abcdefgh", expanded=False)
        self.assertEqual(ring.write_offset, 4)
        self.assertEqual(ring.available, 4)


if __name__ == "__main__":
    unittest.main()
