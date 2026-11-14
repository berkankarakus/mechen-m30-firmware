import struct
import tempfile
import unittest
from pathlib import Path

from provider_scan import scan_driver_directory, scan_file


class ProviderScanTests(unittest.TestCase):
    def test_scan_file_reports_all_little_endian_occurrences(self) -> None:
        pointer = 0x26089471
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "drv_ui.drv"
            path.write_bytes(b"x" + struct.pack("<I", pointer) + b"y" + struct.pack("<I", pointer))
            result = scan_file(path, (pointer,))
        self.assertEqual([item.offset for item in result[pointer]], [1, 6])

    def test_directory_scan_merges_driver_files(self) -> None:
        first = 0x164C9001
        second = 0x26409401
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.drv").write_bytes(struct.pack("<I", first))
            (root / "b.drv").write_bytes(struct.pack("<I", second))
            (root / "ignored.bin").write_bytes(struct.pack("<I", first))
            result = scan_driver_directory(root)
        self.assertEqual(len(result[first]), 1)
        self.assertEqual(len(result[second]), 1)
        self.assertEqual(result[first][0].path, str(root / "a.drv"))


if __name__ == "__main__":
    unittest.main()
