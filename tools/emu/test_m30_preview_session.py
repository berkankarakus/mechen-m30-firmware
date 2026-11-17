import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).parents[2]
SIM = ROOT / "tools/sim"
if str(SIM) not in sys.path:
    sys.path.insert(0, str(SIM))

from m30_preview_session import M30PreviewSession
from usound_callback import Break0ExceptionContext, UsoundCallbackBoundary
from usb_audio_stream import UsbAudioStream


AP = ROOT / "build/qemu-minimal-safe/work/verify/fw/music.ap"
STY = ROOT / "build/qemu-minimal-safe/work/verify/fw/music.sty"


@unittest.skipUnless(AP.exists() and STY.exists(), "extracted firmware resources are not present")
class M30PreviewSessionTests(unittest.TestCase):
    def make_session(self) -> M30PreviewSession:
        return M30PreviewSession.create(
            AP,
            STY,
            callback=UsoundCallbackBoundary(),
            audio=UsbAudioStream(),
            title="LONG TITLE",
            artist="ARTIST",
            album="ALBUM",
            filename="FILE",
            scroll_offset=7,
        )

    def test_one_session_records_lcd_audio_and_callback_boundaries(self) -> None:
        session = self.make_session()
        exception = Break0ExceptionContext(
            exception_code=9,
            epc=0x8005_26AB,
            bad_vaddr=0,
            status=2,
        )
        session.observe_callback(
            0x10,
            (1, 2, 3, 0x1_0000_0004),
            exception=exception,
        )
        self.assertEqual(session.submit_audio_packet(bytes(range(200))), 50)

        trace = session.trace()
        self.assertEqual(trace["lcd"]["pixels"], 320 * 240)
        self.assertEqual(trace["lcd"]["remaining_pixels"], 0)
        self.assertEqual(trace["audio"]["queued_bytes"], 200)
        self.assertEqual(trace["callback"]["calls"][0]["selector"], "0x00000010")
        self.assertEqual(
            trace["callback"]["calls"][0]["args"],
            ["0x00000001", "0x00000002", "0x00000003", "0x00000004"],
        )
        self.assertEqual(
            trace["callback"]["calls"][0]["exception"],
            {
                "code": "0x00000009",
                "epc": "0x800526ab",
                "bad_vaddr": "0x00000000",
                "status": "0x00000002",
                "provenance": "caller-provided",
            },
        )
        self.assertEqual(
            [call["identifier"] for call in trace["state_dispatch"]["transport"]],
            [0x1002, 0x1004, 0x1003],
        )

    def test_trace_is_json_safe_and_identifies_hybrid_boundary(self) -> None:
        session = self.make_session()
        session.observe_callback(0x10, (0, 0, 0, 0))

        trace = session.trace()
        self.assertEqual(trace["provenance"]["kind"], "hybrid-host-session")
        self.assertIn("fixed-ROM service not executed", trace["provenance"]["callback"])
        self.assertNotIn("exception", trace["callback"]["calls"][0])

    def test_trace_includes_extracted_handoff_for_caller_supplied_ra(self) -> None:
        session = self.make_session()
        session.observe_callback(
            0x10,
            (0, 0, 0, 0),
            exception=Break0ExceptionContext(9, 0x1234, 0, 0, ra=0x5678),
        )

        exception = session.trace()["callback"]["calls"][0]["exception"]

        self.assertEqual(
            exception["ker_xsys_entry_candidate"],
            {
                "handler_target": "0xbfc06d6c",
                "stores": [
                    {"address": "0x00013dd8", "value": "0x00001234"},
                    {"address": "0x00013ddc", "value": "0x00005678"},
                ],
                "provenance": (
                    "derived from ker_xsys.bin; register values caller-provided; "
                    "vector path unverified"
                ),
            },
        )

    def test_observe_callback_keeps_two_argument_injection_compatible(self) -> None:
        class LegacyCallbackBoundary:
            def __init__(self) -> None:
                self.calls = []

            def trap(self, selector: int, args: tuple[int, int, int, int]):
                call = SimpleNamespace(selector=selector, args=args)
                self.calls.append(call)

                return call

        session = self.make_session()
        session.callback = LegacyCallbackBoundary()
        call = session.observe_callback(0x10, (1, 2, 3, 4))

        self.assertEqual(call.selector, 0x10)
        self.assertEqual(call.args, (1, 2, 3, 4))
        self.assertNotIn("exception", session.trace()["callback"]["calls"][0])


if __name__ == "__main__":
    unittest.main()
