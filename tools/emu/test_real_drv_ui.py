import unittest
from pathlib import Path

from bank_runtime import LazyBankRuntime
from driver_banks import DriverBankImage


REPO = Path(__file__).resolve().parents[2]
DRIVER = REPO / "analysis" / "community" / "fw" / "drv_ui.drv"


@unittest.skipUnless(DRIVER.is_file(), "archived community drv_ui.drv is unavailable")
class RealDriverUiTests(unittest.TestCase):
    def test_real_b2_candidate_preserves_aligned_entry(self) -> None:
        image = DriverBankImage.load(DRIVER)
        candidate = image.resolve_far_candidate(0x26089471)
        self.assertIsNotNone(candidate)
        assert candidate is not None
        self.assertEqual((candidate.group, candidate.index), ("B", 2))
        self.assertTrue(candidate.bank_present)
        self.assertEqual(candidate.payload_offset, 0x471)
        self.assertEqual(candidate.entry_offset, 0x470)
        self.assertEqual(candidate.file_offset, 0x8AF1)
        self.assertEqual(candidate.entry_file_offset, 0x8AF0)

    def test_real_missing_providers_are_not_created(self) -> None:
        image = DriverBankImage.load(DRIVER)
        for pointer, bank in ((0x164C9001, ("A", 19)), (0x26409401, ("B", 16))):
            candidate = image.resolve_far_candidate(pointer)
            self.assertIsNotNone(candidate)
            assert candidate is not None
            self.assertEqual((candidate.group, candidate.index), bank)
            self.assertFalse(candidate.bank_present)
            self.assertIsNone(candidate.file_offset)

    def test_real_runtime_exposes_safe_policies(self) -> None:
        runtime = LazyBankRuntime.from_path(
            DRIVER,
            validated_entries={("B", 2, 0x470)},
        )
        valid = runtime.dispatch(0x26089471)
        invalid = runtime.dispatch(0x260894E9)
        missing = runtime.dispatch(0x26409401)
        self.assertEqual(valid.dispatch_policy, "lazy-load-then-call")
        self.assertEqual(invalid.dispatch_policy, "never-direct-call")
        self.assertEqual(missing.dispatch_policy, "lazy-only")
        self.assertEqual(len(runtime.loads), 1)


if __name__ == "__main__":
    unittest.main()
