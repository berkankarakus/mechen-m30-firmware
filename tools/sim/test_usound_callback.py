import unittest

from usound_callback import (
    CALLBACK_SELECTOR,
    Break0ExceptionContext,
    UsoundCallbackBoundary,
)


class UsoundCallbackBoundaryTests(unittest.TestCase):
    def test_records_selector_and_four_arguments(self) -> None:
        boundary = UsoundCallbackBoundary()
        call = boundary.trap(CALLBACK_SELECTOR, (1, 2, 3, 0x1_0000_0004))
        self.assertEqual(call.selector, CALLBACK_SELECTOR)
        self.assertEqual(call.args, (1, 2, 3, 4))
        self.assertIsNone(call.exception)
        self.assertEqual(boundary.known_callback_count, 1)

    def test_records_optional_exception_context_as_captured(self) -> None:
        boundary = UsoundCallbackBoundary()
        exception = Break0ExceptionContext(
            exception_code=9,
            epc=0x1_8005_26AB,
            bad_vaddr=0,
            status=0x1_0000_0002,
        )

        call = boundary.trap(
            CALLBACK_SELECTOR,
            (1, 2, 3, 4),
            exception=exception,
        )

        self.assertEqual(call.exception.exception_code, 9)
        self.assertEqual(call.exception.epc, 0x8005_26AB)
        self.assertEqual(call.exception.bad_vaddr, 0)
        self.assertEqual(call.exception.status, 2)

    def test_derives_only_the_proven_handoff_when_ra_is_supplied(self) -> None:
        exception = Break0ExceptionContext(
            exception_code=9,
            epc=0x1_0000_0001,
            bad_vaddr=2,
            status=3,
            ra=0x1_0000_0004,
        )

        self.assertEqual(
            exception.handoff_trace(),
            {
                "handler_target": 0xBFC06D6C,
                "stores": [
                    {"address": 0x00013DD8, "value": 1},
                    {"address": 0x00013DDC, "value": 4},
                ],
                "provenance": (
                    "derived from ker_xsys.bin; register values caller-provided; "
                    "vector path unverified"
                ),
            },
        )

    def test_does_not_invent_handoff_without_caller_ra(self) -> None:
        exception = Break0ExceptionContext(9, 1, 2, 3)

        self.assertIsNone(exception.handoff_trace())

    def test_rejects_non_breakpoint_exception_code(self) -> None:
        with self.assertRaises(ValueError):
            Break0ExceptionContext(
                exception_code=8,
                epc=0,
                bad_vaddr=0,
                status=2,
            )

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
