import unittest

from usb_ring import RING_CAPACITY, RingConsumer


class UsbRingTests(unittest.TestCase):
    def test_linear_read_advances_and_depletes(self) -> None:
        chunks = []
        ring = RingConsumer(available=128, read_offset=32)

        self.assertEqual(ring.consume(40, lambda offset, size: chunks.append((offset, size))), 40)
        self.assertEqual(chunks, [(32, 40)])
        self.assertEqual(ring.available, 88)
        self.assertEqual(ring.read_offset, 72)

    def test_wrapped_read_splits_at_ring_end(self) -> None:
        chunks = []
        ring = RingConsumer(available=64, read_offset=RING_CAPACITY - 16)

        self.assertEqual(ring.consume(40, lambda offset, size: chunks.append((offset, size))), 40)
        self.assertEqual(chunks, [(RING_CAPACITY - 16, 16), (0, 24)])
        self.assertEqual(ring.read_offset, 24)

    def test_insufficient_data_does_not_advance(self) -> None:
        chunks = []
        ring = RingConsumer(available=8, read_offset=4)

        self.assertEqual(ring.consume(9, lambda offset, size: chunks.append((offset, size))), 0)
        self.assertEqual(chunks, [])
        self.assertEqual(ring.available, 8)
        self.assertEqual(ring.read_offset, 4)
        self.assertEqual(ring.short_read_count, 1)

    def test_short_read_counter_resets_at_observed_threshold(self) -> None:
        ring = RingConsumer(available=0)

        for _ in range(99):
            self.assertEqual(ring.consume(1, lambda *_: None), 0)
        self.assertEqual(ring.short_read_count, 99)
        self.assertEqual(ring.consume(1, lambda *_: None), 0)
        self.assertEqual(ring.short_read_count, 0)
        self.assertEqual(ring.reset_signal, 0)

    def test_zero_length_read_is_a_noop(self) -> None:
        chunks = []
        ring = RingConsumer(available=20, read_offset=9)

        self.assertEqual(ring.consume(0, lambda offset, size: chunks.append((offset, size))), 0)
        self.assertEqual(chunks, [])
        self.assertEqual(ring.available, 20)
        self.assertEqual(ring.read_offset, 9)


if __name__ == "__main__":
    unittest.main()
