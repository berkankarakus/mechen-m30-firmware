import unittest
from pathlib import Path

from ru3_preview import render_style


ROOT = Path(__file__).parents[2]
FW = Path("/private/tmp/m30-card-inspect.sNixua/fw")
UPGRADE = FW / "upgrade.sty"
MUSIC = FW / "music.sty"


@unittest.skipUnless(UPGRADE.exists() and MUSIC.exists(), "card-extracted RU3 fixtures are not present")
class Ru3PreviewTests(unittest.TestCase):
    def test_upgrade_style_renders_real_bitmap_records(self) -> None:
        preview = render_style(UPGRADE, text_values={0: "CONFIRM", 1: "UPGRADE"})
        self.assertEqual((preview.framebuffer.width, preview.framebuffer.height), (320, 240))
        self.assertGreater(len(preview.trace["picboxes"]), 0)
        self.assertEqual(len(preview.trace["textboxes"]), 2)

    def test_music_style_uses_real_artwork_resource(self) -> None:
        preview = render_style(MUSIC)
        self.assertEqual(preview.trace["picboxes"][2]["resource"], 0)
        self.assertEqual(preview.trace["picboxes"][2]["width"], 150)
        self.assertEqual(preview.trace["picboxes"][2]["height"], 150)


if __name__ == "__main__":
    unittest.main()
