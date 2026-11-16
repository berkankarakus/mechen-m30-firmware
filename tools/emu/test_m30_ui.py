import tempfile
import unittest
from pathlib import Path

from m30_ui import (
    MAIN_PAINT_STYLE,
    FirmwareTrace,
    MusicStyle,
    NowPlaying,
    marquee_positions,
    rgb565,
    text_pixel_width,
)
from music_bitmap import load_music_bitmap


ROOT = Path(__file__).parents[2]
AP = ROOT / "build/qemu-minimal-safe/work/verify/fw/music.ap"
STY = ROOT / "build/qemu-minimal-safe/work/verify/fw/music.sty"


@unittest.skipUnless(AP.exists() and STY.exists(), "extracted firmware resources are not present")
class M30UiTests(unittest.TestCase):
    def test_real_bank_contains_audited_scroll_call(self):
        trace = FirmwareTrace.load(AP)
        self.assertEqual(trace.instruction, bytes.fromhex("04 f0 05 6a"))
        self.assertTrue(trace.scroll_bank.virtual_address <= 0x40D55078 < trace.scroll_bank.virtual_address + trace.scroll_bank.size)
        self.assertEqual(trace.dispatch_targets["ui_dispatch"], 0xBFC16405)
        self.assertEqual(trace.dispatch_targets["timer_ms"], 0xBFC16BB1)
        self.assertEqual(trace.dispatch_targets["key_read_begin"], 0xBFC16AE9)
        self.assertEqual(trace.dispatch_targets["scroll_event_local"], 0x40D54DF8)

    def test_real_style_contains_panel_geometry(self):
        style = MusicStyle.load(STY)
        panel = [box for box in style.textboxes if box.width == 129 and box.height == 20]
        self.assertEqual([(box.x, box.y) for box in panel], [(190, 40), (190, 75), (190, 111), (190, 147)])
        self.assertEqual(style.color(panel[0]), (255, 255, 255))

    def test_trace_keeps_shared_scroll_style_distinct(self):
        ui = NowPlaying(MusicStyle.load(STY), FirmwareTrace.load(AP))
        calls = ui.dispatch_trace()
        self.assertEqual(calls[0]["style_id"], f"0x{MAIN_PAINT_STYLE:04x}")
        self.assertEqual(calls[1]["style_id"], "0x2005")

    def test_observed_dispatch_trace_has_real_call_order(self):
        ui = NowPlaying(MusicStyle.load(STY), FirmwareTrace.load(AP), title="LONG TITLE")
        calls = ui.observed_dispatch_trace()
        self.assertEqual(len(calls), 9)
        self.assertEqual([call["op"] for call in calls], [0x14, 0x12, 0x14, 0x12, 0x02, 0x02, 0x03, 0x06, 0x03])
        self.assertEqual(calls[4]["payload"], "control_0x1012")
        self.assertEqual(calls[7]["role"], "draw_dynamic_text")

    def test_render_is_320x240_ppm(self):
        ui = NowPlaying(MusicStyle.load(STY), FirmwareTrace.load(AP), title="LONG TITLE")
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "frame.ppm"
            ui.render().ppm(out)
            self.assertEqual(out.read_bytes()[:15], b"P6\n320 240\n255\n")
            self.assertEqual(len(out.read_bytes()), 15 + 320 * 240 * 3)

    def test_render_uses_the_real_album_art_bitmap(self):
        style = MusicStyle.load(STY)
        bitmap = load_music_bitmap(STY, 0)
        frame = NowPlaying(style, FirmwareTrace.load(AP)).render()
        expected = frame.pixels[(28 * 320) * 3 : (28 * 320) * 3 + 3]

        self.assertEqual(bitmap.pixels[0], 0x8430)
        self.assertEqual(expected, bytes(rgb565(bitmap.pixels[0])))

    def test_marquee_uses_pixel_positions_and_gap(self):
        self.assertEqual(text_pixel_width("AB", 1), 12)
        self.assertEqual(marquee_positions("AB", 99, 40), (0,))
        positions = marquee_positions("ABCDEFGHIJK", 10, 30)
        self.assertEqual(positions[0], -10)
        self.assertGreaterEqual(len(positions), 1)

    def test_marquee_does_not_leak_into_field_label(self):
        ui = NowPlaying(
            MusicStyle.load(STY),
            FirmwareTrace.load(AP),
            title="A VERY LONG TITLE THAT MUST WRAP",
            scroll_offset=17,
        )
        frame = ui.render()
        # The first metadata label begins at x=190.  The value viewport starts
        # 42 pixels later; pixels before it must remain the label/background.
        label_pixel = frame.pixels[(40 * 320 + 190) * 3 : (40 * 320 + 190) * 3 + 3]
        self.assertEqual(label_pixel, bytes((255, 24, 32)))


if __name__ == "__main__":
    unittest.main()
