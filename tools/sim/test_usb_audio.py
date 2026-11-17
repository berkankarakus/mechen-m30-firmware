import unittest

from usb_audio import UsbAudioContract, patch_usound_descriptors


def make_device_descriptor() -> bytes:
    descriptor = bytearray(18)
    descriptor[0:2] = bytes((18, 1))
    descriptor[8:12] = bytes((0xD6, 0x10, 0x00, 0xDD))
    return bytes(descriptor)


def make_configuration_descriptor() -> bytes:
    descriptor = bytearray(0x8A)
    descriptor[0:2] = bytes((9, 2))
    descriptor[0x36] = 1
    descriptor[0x58:0x5A] = bytes((2, 16))
    descriptor[0x5B:0x5E] = bytes((0x80, 0xBB, 0x00))
    descriptor[0x65:0x67] = bytes((0xC8, 0x00))
    return bytes(descriptor)


def make_config_items() -> dict[int, bytes]:
    return {
        0x107: b"0x10D6\0",
        0x108: b"0xdd01\0",
        0x10C: b"M30\0",
        0x10F: b"USB AUDIO\0",
        0x114: bytes((3, 0, 0, 0)),
        0x115: bytes((0,)),
    }


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

    def test_descriptor_patch_matches_configured_vid_pid_and_strings(self) -> None:
        result = patch_usound_descriptors(
            make_device_descriptor(),
            make_configuration_descriptor(),
            make_config_items(),
        )

        self.assertEqual(result.device_descriptor[8:12], bytes((0xD6, 0x10, 0x01, 0xDD)))
        self.assertEqual(result.string_descriptor(1), bytes.fromhex("08 03 4d 00 33 00 30 00"))
        self.assertEqual(
            result.string_descriptor(2),
            bytes.fromhex("14 03 55 00 53 00 42 00 20 00 41 00 55 00 44 00 49 00 4f 00"),
        )
        self.assertEqual(result.sample_rate_hz, 48_000)
        self.assertEqual(result.configuration_descriptor[0x36], 3)
        self.assertEqual(result.configuration_descriptor[0x58:0x5A], bytes((2, 16)))
        self.assertEqual(result.configuration_descriptor[0x5B:0x5E], bytes((0x80, 0xBB, 0)))
        self.assertEqual(result.configuration_descriptor[0x65:0x67], bytes((0xC8, 0)))

    def test_descriptor_patch_selects_24_bit_96_khz_format(self) -> None:
        config_items = make_config_items()
        config_items[0x115] = bytes((1,))

        result = patch_usound_descriptors(
            make_device_descriptor(),
            make_configuration_descriptor(),
            config_items,
        )

        self.assertEqual(result.sample_rate_hz, 96_000)
        self.assertEqual(result.configuration_descriptor[0x58:0x5A], bytes((3, 24)))
        self.assertEqual(result.configuration_descriptor[0x5B:0x5E], bytes((0, 0x77, 1)))
        self.assertEqual(result.configuration_descriptor[0x65:0x67], bytes((0x20, 3)))

    def test_descriptor_patch_preserves_defaults_when_vid_pid_are_empty(self) -> None:
        config_items = make_config_items()
        config_items[0x107] = b"0x\0"
        config_items[0x108] = b"0x\0"

        result = patch_usound_descriptors(
            make_device_descriptor(),
            make_configuration_descriptor(),
            config_items,
        )

        self.assertEqual(result.device_descriptor[8:12], bytes((0xD6, 0x10, 0x00, 0xDD)))

    def test_descriptor_patch_applies_interface_flag_bit_one(self) -> None:
        config_items = make_config_items()
        config_items[0x114] = bytes((0, 0, 0, 0))

        result = patch_usound_descriptors(
            make_device_descriptor(),
            make_configuration_descriptor(),
            config_items,
        )

        self.assertEqual(result.configuration_descriptor[0x36], 1)

    def test_empty_string_value_produces_empty_usb_string_descriptor(self) -> None:
        config_items = make_config_items()
        config_items[0x10C] = b"\0"

        result = patch_usound_descriptors(
            make_device_descriptor(),
            make_configuration_descriptor(),
            config_items,
        )

        self.assertEqual(result.string_descriptor(1), bytes((2, 3)))

    def test_malformed_vid_pid_value_is_rejected(self) -> None:
        config_items = make_config_items()
        config_items[0x107] = b"0x1GZZ\0"

        with self.assertRaises(ValueError):
            patch_usound_descriptors(
                make_device_descriptor(),
                make_configuration_descriptor(),
                config_items,
            )


if __name__ == "__main__":
    unittest.main()
