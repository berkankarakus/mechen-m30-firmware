import struct
import tempfile
import unittest
from pathlib import Path

from bank_runtime import LazyBankRuntime


def synthetic_driver() -> bytes:
    data = bytearray(0x1400)
    data[4:8] = b"yqhx"
    struct.pack_into("<I", data, 0x48, 0x600)
    struct.pack_into("<I", data, 0x4C, 0x800)
    struct.pack_into("<I", data, 0x50, 0x1000)
    struct.pack_into(">HH", data, 0x100, 0x100, 0x200)
    struct.pack_into(">HH", data, 0x104, 0x200, 0x300)
    struct.pack_into(">HH", data, 0x108, 0x300, 0xB00)
    data[0xB00:0x1300] = bytes(range(256)) * 8
    return bytes(data)


class LazyBankRuntimeTests(unittest.TestCase):
    def runtime(self, entries=()):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "drv_ui.drv"
        path.write_bytes(synthetic_driver())
        return LazyBankRuntime.from_path(path, validated_entries=set(entries))

    def test_validated_entry_loads_once(self):
        runtime = self.runtime({("B", 2, 0x470)})
        first = runtime.dispatch(0x26089471)
        second = runtime.dispatch(0x26089471)
        self.assertEqual(first.status, "validated-entry")
        self.assertEqual(first.dispatch_policy, "lazy-load-then-call")
        self.assertTrue(first.loaded)
        self.assertFalse(second.loaded)
        self.assertEqual(len(runtime.loads), 1)
        self.assertEqual(runtime.loads[0].payload_offset, 0x471)
        self.assertEqual(runtime.loads[0].entry_offset, 0x470)
        self.assertEqual(runtime.loads[0].file_offset, 0xF71)
        self.assertEqual(runtime.loads[0].entry_file_offset, 0xF70)

    def test_unvalidated_entry_is_never_executed(self):
        runtime = self.runtime()
        result = runtime.dispatch(0x260894E9)
        self.assertEqual(result.status, "bank-loaded-entry-unresolved")
        self.assertEqual(result.dispatch_policy, "never-direct-call")
        self.assertTrue(result.loaded)
        self.assertEqual(len(runtime.loads), 1)

    def test_resident_pointer_does_not_create_bank_load(self):
        runtime = self.runtime()
        result = runtime.dispatch(0xBFC09C01)
        self.assertEqual(result.status, "resident-or-unresolved")
        self.assertEqual(result.dispatch_policy, "resident-or-unresolved")
        self.assertFalse(runtime.loads)

    def test_missing_bank_is_recorded_without_loading(self):
        runtime = self.runtime()
        result = runtime.dispatch(0x26409401)
        self.assertEqual(result.status, "bank-missing-or-external")
        self.assertEqual(result.dispatch_policy, "lazy-only")
        self.assertIsNotNone(result.candidate)
        assert result.candidate is not None
        self.assertFalse(result.candidate.bank_present)
        self.assertFalse(result.loaded)
        self.assertEqual(runtime.loads, [])


if __name__ == "__main__":
    unittest.main()
