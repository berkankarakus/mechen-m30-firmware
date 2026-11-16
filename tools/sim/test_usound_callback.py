import unittest

from usound_callback import CALLBACK_SELECTOR, UsoundCallbackBoundary


class UsoundCallbackBoundaryTests(unittest.TestCase):
    def test_records_selector_and_four_arguments(self) -> None:
        boundary = UsoundCallbackBoundary()
        call = boundary.trap(CALLBACK_SELECTOR, (1, 2, 3, 0x1_0000_0004))
        self.assertEqual(call.selector, CALLBACK_SELECTOR)
        self.assertEqual(call.args, (1, 2, 3, 4))
        self.assertEqual(boundary.known_callback_count, 1)

    def test_does_not_invent_kernel_service_effect(self) -> None:
        boundary = UsoundCallbackBoundary()
        call = boundary.trap(CALLBACK_SELECTOR, (0, 0, 0, 0))
        with self.assertRaises(NotImplementedError):
            boundary.service_effect(call)

    def test_rejects_unknown_selector(self) -> None:
        boundary = UsoundCallbackBoundary()
        call = boundary.trap(0x99, (0, 0, 0, 0))
        with self.assertRaises(ValueError):
            boundary.service_effect(call)


if __name__ == "__main__":
    unittest.main()
