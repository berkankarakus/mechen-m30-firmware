import unittest

from mmm_bp_model import REFILL_BLOCK_BYTES, fade_mode_name, plan_ring_read


class MmmBpBufferTests(unittest.TestCase):
    def test_refill_contract_is_512_bytes(self):
        self.assertEqual(REFILL_BLOCK_BYTES, 0x200)

    def test_ring_read_without_wrap(self):
        plan = plan_ring_read(read_offset=4, capacity=32, available=20, requested=12)
        self.assertEqual((plan.first_offset, plan.first_length), (4, 12))
        self.assertEqual((plan.second_offset, plan.second_length), (None, 0))

    def test_ring_read_splits_at_end(self):
        plan = plan_ring_read(read_offset=28, capacity=32, available=8, requested=8)
        self.assertEqual((plan.first_offset, plan.first_length), (28, 4))
        self.assertEqual((plan.second_offset, plan.second_length), (0, 4))

    def test_reader_rejects_short_buffer(self):
        with self.assertRaises(ValueError):
            plan_ring_read(read_offset=0, capacity=32, available=3, requested=4)

    def test_fade_mode_names_are_conservative(self):
        self.assertEqual(fade_mode_name(2), "slow")
        self.assertEqual(fade_mode_name(3), "fast")
        self.assertEqual(fade_mode_name(1), "inactive")


if __name__ == "__main__":
    unittest.main()
