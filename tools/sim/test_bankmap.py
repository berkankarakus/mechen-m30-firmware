import unittest

from bankmap import decode


class BankAddressTests(unittest.TestCase):
    def test_b3_marquee_lead_in(self):
        address = decode(0x260E4FF4)
        self.assertEqual(address.bank_type, "B")
        self.assertEqual(address.bank_index, 3)
        self.assertEqual(address.classification, "overlay-lead-in")
        self.assertEqual(address.window_start, 0x260E5000)

    def test_overlay_payload_is_distinct_from_lead_in(self):
        address = decode(0x260E5000)
        self.assertTrue(address.is_overlay_window)
        self.assertEqual(address.classification, "overlay")

    def test_low_offset_bank_entry_does_not_look_resident(self):
        address = decode(0x26089471)
        self.assertEqual(address.bank_type, "B")
        self.assertEqual(address.bank_index, 2)
        self.assertEqual(address.classification, "bank-stub-or-resident")
        self.assertFalse(address.is_overlay_window)
        self.assertEqual(address.payload_offset, 0x471)

    def test_far_entry_candidates_preserve_bank_window(self):
        address = decode(0x26409401)
        self.assertEqual(address.bank_index, 16)
        self.assertEqual(address.window_start, 0x26425000)
        self.assertEqual(address.payload_offset, 0x401)

    def test_non_overlay_pointer_is_external(self):
        address = decode(0xBFC09C01)
        self.assertEqual(address.classification, "resident-or-external")
        self.assertIsNone(address.bank_index)


if __name__ == "__main__":
    unittest.main()
