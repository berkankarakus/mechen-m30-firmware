import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]
SIM = ROOT / "tools/sim"
if str(SIM) not in sys.path:
    sys.path.insert(0, str(SIM))

from m30_preview_session import M30PreviewSession
from usound_callback import UsoundCallbackBoundary
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
        session.observe_callback(0x10, (1, 2, 3, 0x1_0000_0004))
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

    def test_trace_is_json_safe_and_identifies_hybrid_boundary(self) -> None:
        session = self.make_session()
        trace = session.trace()
        self.assertEqual(trace["provenance"]["kind"], "hybrid-host-session")
        self.assertIn("fixed-ROM service not executed", trace["provenance"]["callback"])


if __name__ == "__main__":
    unittest.main()
