import tempfile
import unittest
from pathlib import Path

from folder_ui import (
    DIRECTORY_TEXT_WIDTH,
    SELECTION_BACKGROUND,
    FolderList,
    FolderRow,
    draw_directory_text,
    directory_marquee_positions,
)
from m30_ui import Framebuffer


class FolderUiTests(unittest.TestCase):
    def test_slot_truncation_happens_before_scroll(self):
        row = FolderRow("ABCDEFGHIJKLMNOPQRSTUVWXYZ-long")
        self.assertTrue(row.truncated)
        self.assertEqual(len(row.slot_text), 23)
        self.assertNotIn("long", row.slot_text)

    def test_short_name_stays_stationary(self):
        self.assertEqual(directory_marquee_positions("Music", 73), (0,))

    def test_long_name_uses_pixel_offsets_and_gap(self):
        positions = directory_marquee_positions("A" * 40, 1)
        self.assertEqual(positions[0], -1)
        self.assertGreaterEqual(len(positions), 1)
        self.assertLessEqual(max(positions), DIRECTORY_TEXT_WIDTH)

    def test_render_trace_records_selected_redraw_contract(self):
        view = FolderList(
            (
                FolderRow("Music"),
                FolderRow("A very long folder name that is truncated"),
            ),
            selected_index=1,
            scroll_offset_px=7,
        )
        frame, trace = view.render()
        self.assertEqual((frame.width, frame.height), (320, 240))
        self.assertFalse(trace[0]["selected"])
        self.assertTrue(trace[1]["selected"])
        self.assertTrue(trace[1]["truncated"])
        self.assertEqual(trace[1]["background"], "selection-red")
        self.assertEqual(trace[1]["restore_mode"], "solid-selection-red")
        self.assertEqual(trace[1]["offset_px"], 7)

    def test_render_is_a_ppm(self):
        view = FolderList((FolderRow("Music"),))
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "folder.ppm"
            view.render()[0].ppm(out)
            self.assertEqual(out.read_bytes()[:15], b"P6\n320 240\n255\n")
            self.assertEqual(len(out.read_bytes()), 15 + 320 * 240 * 3)

    def test_marquee_cannot_paint_outside_text_viewport(self):
        frame = Framebuffer()
        frame.fill(SELECTION_BACKGROUND)
        draw_directory_text(
            frame,
            "A" * 48,
            35,
            20,
            DIRECTORY_TEXT_WIDTH,
            (235, 235, 235),
            offset_px=17,
        )
        expected = bytes(SELECTION_BACKGROUND)
        for x in (30, 34, 240, 319):
            for y in range(20, 36):
                start = (y * frame.width + x) * 3
                self.assertEqual(frame.pixels[start:start + 3], expected)


if __name__ == "__main__":
    unittest.main()
