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
from m30_font import M30Font
from music_bitmap import load_music_bitmap


ROOT = Path(__file__).parents[2]
AP = ROOT / "build/qemu-minimal-safe/work/verify/fw/music.ap"
STY = ROOT / "build/qemu-minimal-safe/work/verify/fw/music.sty"
FONT = ROOT / "build/qemu-minimal-safe/work/verify/fw/new_m.fnt"


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
        self.assertEqual(style.timeboxes[0].words[:4], (70, 202, 64, 12))
        self.assertEqual(style.timeboxes[1].words[6:10], (235, 202, 64, 12))
        self.assertEqual(style.progressbars[0].words[1:3], (70, 220))

    def test_trace_keeps_shared_scroll_style_distinct(self):
        ui = NowPlaying(MusicStyle.load(STY), FirmwareTrace.load(AP))
        calls = ui.dispatch_trace()
        self.assertEqual(calls[0]["style_id"], f"0x{MAIN_PAINT_STYLE:04x}")
        self.assertEqual(calls[1]["style_id"], "0x2005")

    def test_transport_frame_semantics_are_explicit(self):
        ui = NowPlaying(MusicStyle.load(STY), FirmwareTrace.load(AP), show_header=False)
        selected = {item["picbox"]: item for item in ui.selected_picbox_trace()}
        self.assertEqual(selected[4]["frame"], 1)
        self.assertEqual(selected[4]["state_semantics"], "pause")
        self.assertEqual(selected[1]["state_semantics"], "shuffle-off")
        self.assertEqual(selected[0]["state_semantics"], "unresolved")

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

    def test_render_uses_real_status_transport_and_progress_bitmaps(self):
        style = MusicStyle.load(STY)
        ui = NowPlaying(
            style,
            FirmwareTrace.load(AP),
            transport_frame=1,
            eq_frame=1,
            status_frame=0,
            show_controls=True,
        )
        frame = ui.render()
        for picbox_index, frame_index in ((2, 0), (3, 1), (4, 1), (5, 0), (6, 0), (7, 0), (8, 0)):
            picbox = style.picboxes[picbox_index]
            resource = style.bitmap(picbox.frames[frame_index])
            offset = (picbox.y * frame.width + picbox.x) * 3
            self.assertEqual(frame.pixels[offset:offset + 3], bytes(rgb565(resource.pixels[0])))

        selected = ui.selected_picbox_trace()
        self.assertFalse(selected[0]["active_on_now_playing_paint"])
        self.assertFalse(selected[1]["active_on_now_playing_paint"])
        self.assertTrue(selected[2]["active_on_now_playing_paint"])
        self.assertFalse(NowPlaying(style, FirmwareTrace.load(AP)).selected_picbox_trace()[4]["painted_in_preview"])
        self.assertTrue(selected[4]["painted_in_preview"])
        self.assertTrue(NowPlaying(style, FirmwareTrace.load(AP)).selected_picbox_trace()[5]["painted_in_preview"])
        self.assertEqual(selected[3]["state_semantics"], "eq-visible")
        self.assertEqual(selected[7]["state_semantics"], "title-icon")

    def test_render_uses_real_numeric_glyph_and_progress_resources(self):
        style = MusicStyle.load(STY)
        frame = NowPlaying(style, FirmwareTrace.load(AP), progress_fraction=0.4).render()
        digit_zero = style.bitmap(18)
        digit_offset = (202 * frame.width + 70) * 3
        self.assertEqual(frame.pixels[digit_offset:digit_offset + 3], bytes(rgb565(digit_zero.pixels[0])))
        bar = style.bitmap(17)
        bar_offset = (220 * frame.width + 70) * 3
        self.assertEqual(frame.pixels[bar_offset:bar_offset + 3], bytes(rgb565(style.bitmap(31).pixels[0])))
        background_offset = (220 * frame.width + 70 + round(bar.width * 0.4)) * 3
        self.assertEqual(frame.pixels[background_offset:background_offset + 3], bytes(rgb565(bar.pixels[round(bar.width * 0.4)])))

    def test_footer_separates_track_number_from_duration(self):
        style = MusicStyle.load(STY)
        ui = NowPlaying(
            style,
            FirmwareTrace.load(AP),
            track_position="88/103",
            elapsed="0:00:00",
            duration="0:04:08",
            show_controls=True,
            transport_frame=0,
        )
        frame = ui.render()
        number = style.numboxes[0].words
        background = bytes(rgb565(0x18C3))
        self.assertTrue(any(
            frame.pixels[(yy * frame.width + xx) * 3 : (yy * frame.width + xx + 1) * 3] != background
            for yy in range(number[1], number[1] + number[3])
            for xx in range(number[0], number[0] + number[2])
        ))
        right = style.timeboxes[1].words[6:]
        self.assertTrue(any(
            frame.pixels[(yy * frame.width + xx) * 3 : (yy * frame.width + xx + 1) * 3] != background
            for yy in range(right[1], right[1] + right[3])
            for xx in range(right[0], right[0] + right[2])
        ))

    def test_header_trace_matches_observed_resource_frames(self):
        ui = NowPlaying(MusicStyle.load(STY), FirmwareTrace.load(AP))
        selected = {item["picbox"]: item for item in ui.selected_picbox_trace()}
        self.assertEqual(selected[0]["frame"], 2)
        self.assertEqual(selected[1]["frame"], 1)
        self.assertTrue(selected[0]["painted_in_preview"])

    @unittest.skipUnless(FONT.exists(), "extracted M30 font is not present")
    def test_real_font_sparse_index_resolves_ascii_glyphs(self):
        font = M30Font.load(FONT)
        self.assertEqual(font.glyph("0").advance, 11)
        self.assertEqual(font.glyph("A").advance, 13)
        self.assertEqual(font.glyph("M").advance, 18)
        self.assertEqual(font.display_glyph("I").advance, 8)
        self.assertEqual(font.display_glyph("M").advance, 12)
        self.assertEqual(font.display_glyph("-").advance, 8)
        self.assertEqual(font.display_glyph(".").advance, 6)
        self.assertEqual(font.display_glyph("m").advance, 12)
        self.assertEqual(font.display_glyph("i").advance, 7)
        self.assertEqual(font.display_glyph("@").advance, 12)
        self.assertEqual(font.vertical_ink_bounds("M", pixel_scale=1), (1, 14))
        self.assertGreater(sum(font.glyph("A").rows), 0)
        self.assertEqual(font.text_width("A0", pixel_scale=2), 12)

    def test_marquee_uses_pixel_positions_and_gap(self):
        self.assertEqual(text_pixel_width("AB", 1), 12)
        self.assertEqual(marquee_positions("AB", 99, 40), (0,))
        positions = marquee_positions("ABCDEFGHIJK", 10, 30)
        self.assertEqual(positions[0], -10)
        self.assertGreaterEqual(len(positions), 1)

    def test_marquee_stays_inside_real_textbox_viewport(self):
        ui = NowPlaying(
            MusicStyle.load(STY),
            FirmwareTrace.load(AP),
            title="A VERY LONG TITLE THAT MUST WRAP",
            scroll_offset=17,
        )
        frame = ui.render()
        # The real TextBox begins at x=190.  A long value may scroll inside
        # that viewport, but cannot paint into the neighbouring art/status
        # area or beyond the right edge.
        left = frame.pixels[(40 * 320 + 189) * 3 : (40 * 320 + 189) * 3 + 3]
        right = frame.pixels[(40 * 320 + 319) * 3 : (40 * 320 + 319) * 3 + 3]
        self.assertEqual(left, bytes(rgb565(0x18C3)))
        self.assertEqual(right, bytes(rgb565(0x18C3)))

    def test_metadata_textboxes_share_icon_row_geometry(self):
        style = MusicStyle.load(STY)
        boxes = [box for box in style.textboxes if box.width == 129 and box.height == 20]
        icon_indices = (7, 6, 5, 8)
        for box, icon_index in zip(boxes, icon_indices):
            picbox = style.picboxes[icon_index]
            self.assertEqual((box.x, box.y), (picbox.x + 30, picbox.y))


if __name__ == "__main__":
    unittest.main()
