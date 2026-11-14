import unittest

from m30_ui import MAIN_PAINT_STYLE, SECONDARY_STYLE
from ui_dispatcher import (
    OP_CLEAR_COLOR,
    OP_DRAW_TEXT,
    Rect,
    TextPayload,
    UiDispatcher,
    replay_now_playing_dispatcher,
)


class UiDispatcherTests(unittest.TestCase):
    def test_known_clear_and_text_calls_render(self):
        dispatcher = UiDispatcher()
        dispatcher.call(0x18C3, 0, 0, OP_CLEAR_COLOR)
        dispatcher.call({"style_id": MAIN_PAINT_STYLE}, TextPayload("TITLE", 190, 40, 129, 20), 1, OP_DRAW_TEXT)
        self.assertEqual(len(dispatcher.calls), 2)
        self.assertTrue(all(call.rendered for call in dispatcher.calls))
        self.assertEqual(dispatcher.calls[1].style_id, MAIN_PAINT_STYLE)

    def test_unknown_operation_is_trace_only(self):
        dispatcher = UiDispatcher()
        before = bytes(dispatcher.framebuffer.pixels)
        self.assertEqual(dispatcher.call(123, 456, 0, 0x7F), 1)
        self.assertEqual(bytes(dispatcher.framebuffer.pixels), before)
        self.assertFalse(dispatcher.calls[0].rendered)

    def test_clear_rect_is_bounded(self):
        dispatcher = UiDispatcher()
        dispatcher.call(Rect(-10, -10, 400, 300), 0, 0, 0x12)
        self.assertTrue(dispatcher.calls[0].rendered)

    def test_replay_contains_the_two_verified_text_styles(self):
        trace = replay_now_playing_dispatcher().trace()
        styles = [call["style_id"] for call in trace if call["style_id"] is not None]
        self.assertIn(MAIN_PAINT_STYLE, styles)
        self.assertIn(SECONDARY_STYLE, styles)

    def test_dynamic_text_uses_the_clipped_marquee_path(self):
        dispatcher = UiDispatcher()
        dispatcher.call(
            {"style_id": MAIN_PAINT_STYLE},
            TextPayload("A LONG TITLE THAT WRAPS", 190, 40, 87, 20, offset=17),
            6,
            0x06,
        )
        self.assertTrue(dispatcher.calls[0].rendered)
        # The dynamic viewport starts at x=190 and is clipped to 87 pixels;
        # drawing must not write into the neighboring column.
        for y in range(40, 60):
            self.assertEqual(bytes(dispatcher.framebuffer.pixels[(y * 320 + 277) * 3 : (y * 320 + 277) * 3 + 3]), bytes((18, 19, 22)))


if __name__ == "__main__":
    unittest.main()
