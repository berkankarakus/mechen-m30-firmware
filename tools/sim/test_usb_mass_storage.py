import unittest

from sd_block_device import SdCardBlockDevice
from usb_mass_storage import (
    BLOCK_SIZE,
    READ10_OPCODE,
    READ_DIRECTION,
    WRITE10_OPCODE,
    UsbMassStorageBlockRequest,
)


class UsbMassStorageBlockRequestTests(unittest.TestCase):
    def test_read10_preserves_observed_fields_and_block_size(self):
        request = UsbMassStorageBlockRequest.read10(0x1234, 3)
        self.assertEqual(request.opcode, READ10_OPCODE)
        self.assertEqual(request.block_address, 0x1234)
        self.assertEqual(request.block_count, 3)
        self.assertEqual(request.direction, READ_DIRECTION)
        self.assertEqual(request.transfer_bytes, 3 * BLOCK_SIZE)

    def test_write10_keeps_direction_unresolved(self):
        request = UsbMassStorageBlockRequest.write10(7, 2)
        self.assertEqual(request.opcode, WRITE10_OPCODE)
        self.assertIsNone(request.direction)
        self.assertEqual(request.transfer_bytes, 1024)

    def test_unknown_opcode_is_rejected(self):
        with self.assertRaises(ValueError):
            UsbMassStorageBlockRequest(0x12, 0, 1)

    def test_negative_block_fields_are_rejected(self):
        with self.assertRaises(ValueError):
            UsbMassStorageBlockRequest.read10(-1, 1)
        with self.assertRaises(ValueError):
            UsbMassStorageBlockRequest.read10(0, -1)

    def test_write_direction_is_not_invented(self):
        with self.assertRaises(ValueError):
            UsbMassStorageBlockRequest(
                opcode=WRITE10_OPCODE,
                block_address=0,
                block_count=1,
                direction=0,
            )

    def test_read10_moves_sector_bytes_from_sd_device(self):
        card = SdCardBlockDevice(sector_count=3)
        first = bytes([0x11]) * BLOCK_SIZE
        second = bytes([0x22]) * BLOCK_SIZE
        card.write_sector(1, first)
        card.write_sector(2, second)

        payload = UsbMassStorageBlockRequest.read10(1, 2).read_from(card)

        self.assertEqual(payload, first + second)

    def test_write10_moves_exact_sector_payload_to_sd_device(self):
        card = SdCardBlockDevice(sector_count=2)
        payload = bytes([0x33]) * (2 * BLOCK_SIZE)
        request = UsbMassStorageBlockRequest.write10(0, 2)

        request.write_to(card, payload)

        self.assertEqual(card.read_sector(0), bytes([0x33]) * BLOCK_SIZE)
        self.assertEqual(card.read_sector(1), bytes([0x33]) * BLOCK_SIZE)

    def test_request_direction_and_payload_size_are_checked(self):
        card = SdCardBlockDevice(sector_count=1)
        read_request = UsbMassStorageBlockRequest.read10(0, 1)
        write_request = UsbMassStorageBlockRequest.write10(0, 1)

        with self.assertRaises(ValueError):
            read_request.write_to(card, bytes(BLOCK_SIZE))
        with self.assertRaises(ValueError):
            write_request.read_from(card)
        with self.assertRaises(ValueError):
            write_request.write_to(card, bytes(BLOCK_SIZE - 1))


if __name__ == "__main__":
    unittest.main()
