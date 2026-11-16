import unittest

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


if __name__ == "__main__":
    unittest.main()
