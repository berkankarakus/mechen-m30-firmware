import tempfile
import unittest
from pathlib import Path

from folder_ui import (
    DIRECTORY_TEXT_WIDTH,
    SELECTION_BACKGROUND,
    VISIBLE_DIRECTORY_ROWS,
    FolderList,
    FolderRow,
    draw_directory_text,
    directory_marquee_positions,
)
from m30_ui import Framebuffer
from scroll_accel import NEXT, PREVIOUS


class FolderUiTests(unittest.TestCase):
    def test_slot_truncation_happens_before_scroll(self):
        row = FolderRow("ABCDEFGHIJKLMNOPQRSTUVWXYZ-long")
        self.assertTrue(row.truncated)
        self.assertEqual(len(row.slot_text), 23)
        self.assertNotIn("long", row.slot_text)

    def test_trace_distinguishes_slot_clipping_from_renderer_clipping(self):
        view = FolderList(
            (FolderRow("Music"), FolderRow("A very long folder name that should scroll smoothly")),
            selected_index=1,
            scroll_offset_px=32,
        )
        _, trace = view.render()
        clipping = trace[1]["clipping"]
        self.assertEqual(clipping["clip_stage"], "filesystem-slot")
        self.assertTrue(clipping["source_clipped"])
        self.assertFalse(clipping["renderer_clipped"])
        self.assertFalse(clipping["scroll_eligible"])
        self.assertGreater(clipping["source_text_width_px"], clipping["slot_text_width_px"])
        self.assertLess(clipping["slot_text_width_px"], clipping["viewport_width_px"])

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
        self.assertEqual(trace[1]["restore_mode"], "sdimage-tail")
        self.assertEqual(trace[1]["offset_px"], 7)

    def test_short_selected_name_keeps_solid_selection_restore(self):
        view = FolderList((FolderRow("Music"),), selected_index=0)
        _, trace = view.render()
        self.assertEqual(trace[0]["restore_mode"], "solid-selection-red")

    def test_selection_scrolls_the_viewport_for_long_folder_lists(self):
        rows = tuple(FolderRow(f"Folder {index}") for index in range(12))
        view = FolderList(rows, selected_index=11)
        _, trace = view.render()
        self.assertEqual(VISIBLE_DIRECTORY_ROWS, 7)
        self.assertEqual(view.first_visible_index, 5)
        self.assertEqual(trace[0]["index"], 5)
        self.assertEqual(trace[-1]["index"], 11)
        self.assertTrue(trace[-1]["selected"])
        self.assertEqual(
            view.navigation_snapshot(),
            {"total": 12, "start": 6, "end": 12, "active": 12, "visible_rows": 7},
        )

    def test_selection_movement_wraps_at_list_edges(self):
        view = FolderList(tuple(FolderRow(str(index)) for index in range(10)))
        self.assertEqual(view.move_selection(-1), 9)
        self.assertEqual(view.move_selection(1), 0)
        self.assertEqual(view.first_visible_index, 0)

    def test_single_step_wrap_matches_real_folder_handler(self):
        view = FolderList(tuple(FolderRow(str(index)) for index in range(7)), selected_index=6)
        result = view.move_event(NEXT, 0)
        self.assertEqual(
            (result["selected_index"], result["consumed_steps"], result["wrapped"]),
            (0, 1, True),
        )
        result = view.move_event(PREVIOUS, 1)
        self.assertEqual(
            (result["selected_index"], result["consumed_steps"], result["wrapped"]),
            (6, 1, True),
        )

    def test_accelerated_events_move_and_scroll_the_folder_view(self):
        view = FolderList(tuple(FolderRow(str(index)) for index in range(100)))
        for now in range(0, 1600, 100):
            view.accelerator.steps_for(NEXT, now)
        result = view.move_event(NEXT, 1600)
        self.assertEqual(result["requested_steps"], 20)
        self.assertEqual(result["consumed_steps"], 20)
        self.assertEqual(result["selected_index"], 20)
        self.assertEqual(result["first_visible_index"], 14)
        self.assertTrue(result["page_reload"])
        self.assertEqual((result["mode"], result["update"]), (4, 2))

    def test_accelerated_folder_events_reset_on_direction_change_and_wrap(self):
        view = FolderList(tuple(FolderRow(str(index)) for index in range(4)), selected_index=3)
        result = view.move_event(NEXT, 0)
        self.assertEqual((result["selected_index"], result["consumed_steps"]), (0, 1))
        result = view.move_event(PREVIOUS, 1)
        self.assertEqual((result["requested_steps"], result["selected_index"]), (1, 3))
        result = view.move_event(PREVIOUS, 701)
        self.assertEqual((result["requested_steps"], result["selected_index"]), (1, 2))

    def test_marquee_offset_uses_the_64_millisecond_refresh_tick(self):
        view = FolderList((FolderRow("A long folder name"),), scroll_offset_px=3)
        self.assertEqual(view.marquee_offset_at(0), 3)
        self.assertEqual(view.marquee_offset_at(63), 3)
        self.assertEqual(view.marquee_offset_at(64), 4)
        self.assertEqual(view.marquee_offset_at(240, start_ms=80), 5)
        self.assertEqual(view.scroll_offset_px, 3)

    def test_render_at_does_not_mutate_the_model_offset(self):
        view = FolderList(
            (FolderRow("A long folder name that is truncated"),),
            scroll_offset_px=2,
        )
        _, trace = view.render_at(160)
        self.assertEqual(trace[0]["offset_px"], 4)
        self.assertEqual(view.scroll_offset_px, 2)

    def test_marquee_time_must_be_monotonic_and_non_negative(self):
        view = FolderList((FolderRow("Music"),))
        with self.assertRaises(ValueError):
            view.marquee_offset_at(-1)
        with self.assertRaises(ValueError):
            view.marquee_offset_at(10, start_ms=11)

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
