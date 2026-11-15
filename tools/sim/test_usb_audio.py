import unittest

from usb_audio import UsbAudioContract


class UsbAudioContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = UsbAudioContract()

    def test_descriptor_values_are_evidence_backed(self) -> None:
        self.assertEqual((self.contract.vendor_id, self.contract.product_id), (0x10D6, 0xDD00))
        self.assertEqual((self.contract.channels, self.contract.sample_width_bits), (2, 16))
        self.assertEqual(self.contract.sample_rate_hz, 48_000)
        self.assertEqual((self.contract.iso_out_endpoint, self.contract.packet_bytes), (1, 200))
        self.assertEqual(self.contract.hid_in_endpoint, 0x82)

    def test_packet_is_fifty_stereo_frames(self) -> None:
        self.assertEqual(self.contract.frame_bytes, 4)
        self.assertEqual(self.contract.frames_per_packet, 50)
        self.assertEqual(self.contract.validate_packet(bytes(200)), 50)

    def test_packet_size_is_exact(self) -> None:
        with self.assertRaises(ValueError):
            self.contract.validate_packet(bytes(196))
        with self.assertRaises(ValueError):
            self.contract.validate_packet(bytes(204))

    def test_descriptor_advertises_one_sample_rate(self) -> None:
        self.assertTrue(self.contract.accepts_sample_rate(48_000))
        self.assertFalse(self.contract.accepts_sample_rate(44_100))
        self.assertFalse(self.contract.accepts_sample_rate(96_000))

    def test_only_observed_control_request_codes_are_marked(self) -> None:
        self.assertTrue(self.contract.control_request_is_observed(0x21))
        self.assertTrue(self.contract.control_request_is_observed(0x22))
        self.assertFalse(self.contract.control_request_is_observed(0x01))


if __name__ == "__main__":
    unittest.main()
