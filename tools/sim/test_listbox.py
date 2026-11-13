import unittest

from listbox import (
    DIRECTORY_HEAD_X,
    DIRECTORY_ROW_HEIGHT,
    DIRECTORY_SCROLL_PERIOD_MS,
    DIRECTORY_TEXT_WIDTH,
    M30_DIRECTORY_STYLE,
    active_redraw_period_ms,
    firmware_name_capacity_bytes,
    needs_active_scroll,
    scroll_window,
)


class DirectoryListboxTests(unittest.TestCase):
    def test_m30_geometry_keeps_icon_and_text_separate(self):
        self.assertEqual(M30_DIRECTORY_STYLE.head_x, DIRECTORY_HEAD_X)
        self.assertEqual(M30_DIRECTORY_STYLE.text_width, DIRECTORY_TEXT_WIDTH)
        self.assertEqual(M30_DIRECTORY_STYLE.row_height, DIRECTORY_ROW_HEIGHT)

    def test_long_folder_name_uses_active_scroll_contract(self):
        self.assertFalse(needs_active_scroll(len("short")))
        self.assertTrue(needs_active_scroll(DIRECTORY_TEXT_WIDTH + 1))
        self.assertEqual(active_redraw_period_ms(), DIRECTORY_SCROLL_PERIOD_MS)

    def test_firmware_name_buffer_is_smaller_than_the_scroll_region(self):
        self.assertEqual(firmware_name_capacity_bytes(), 52)
        # A name can be truncated before the renderer gets a chance to scroll.
        self.assertLess(firmware_name_capacity_bytes(), DIRECTORY_TEXT_WIDTH)

    def test_scroll_wraps_with_two_space_gap(self):
        self.assertEqual(scroll_window("abcdefghij", 0, 5), "abcde")
        self.assertEqual(scroll_window("abcdefghij", 8, 5), "ij  a")

    def test_short_names_are_not_modified(self):
        self.assertEqual(scroll_window("folder", 37, 20), "folder")


if __name__ == "__main__":
    unittest.main()
