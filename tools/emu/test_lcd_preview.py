import tempfile
import unittest
from pathlib import Path

from lcd_preview import render_preview
from lcd_transfer import COLUMN_ADDRESS_SET, MEMORY_ACCESS_CONTROL, MEMORY_WRITE, ROW_ADDRESS_SET


ROOT = Path(__file__).parents[2]
AP = ROOT / "build/qemu-minimal-safe/work/verify/fw/music.ap"
STY = ROOT / "build/qemu-minimal-safe/work/verify/fw/music.sty"


@unittest.skipUnless(AP.exists() and STY.exists(), "extracted firmware resources are not present")
class LcdPreviewTests(unittest.TestCase):
    def test_real_ui_pixels_cross_recovered_lcd_boundary(self):
        sink, ui = render_preview(
            AP,
            STY,
            title="LONG TITLE",
            artist="ARTIST",
            album="ALBUM",
            filename="FILE",
            scroll_offset=7,
        )

        self.assertEqual(
            [command.opcode for command in sink.commands],
            [MEMORY_ACCESS_CONTROL, COLUMN_ADDRESS_SET, ROW_ADDRESS_SET, MEMORY_WRITE],
        )
        self.assertEqual(sink.commands[0].payload, (0x48,))
        self.assertEqual(sink.window.pixel_count, 320 * 240)
        self.assertEqual(sink.remaining_pixels, 0)
        self.assertEqual(len(ui.render().pixels), 320 * 240 * 3)

    def test_preview_writes_a_ppm(self):
        sink, _ = render_preview(
            AP,
            STY,
            title="TITLE",
            artist="ARTIST",
            album="ALBUM",
            filename="FILE",
            scroll_offset=0,
        )
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "lcd.ppm"
            sink.framebuffer.ppm(out)
            data = out.read_bytes()
            self.assertEqual(data[:15], b"P6\n320 240\n255\n")
            self.assertEqual(len(data), 15 + 320 * 240 * 3)


if __name__ == "__main__":
    unittest.main()
