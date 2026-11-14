import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from prepare_qemu_banks import prepare


ROOT = Path(__file__).parents[2]
AP = ROOT / "build/qemu-minimal-safe/work/verify/fw/music.ap"


@unittest.skipUnless(AP.exists(), "extracted music.ap is not present")
class QemuBankPreparationTests(unittest.TestCase):
    def test_preserves_real_bank_addresses_and_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            manifest = prepare(AP, out)
            self.assertEqual(manifest["source_sha256"], hashlib.sha256(AP.read_bytes()).hexdigest())
            self.assertEqual(manifest["bank_count"], 87)
            self.assertEqual(manifest["audited_scroll_call"]["bank"], 0x40D54C00)
            info = json.loads((out / "manifest.json").read_text())
            self.assertEqual(info, manifest)
            bank = next(item for item in manifest["banks"] if item["virtual_address"] == 0x40D54C00)
            payload = Path(bank["payload"])
            self.assertEqual(payload.read_bytes()[0x27878 - bank["file_offset"]:][:4], bytes.fromhex("04 f0 05 6a"))

    def test_generated_assembly_has_one_section_per_bank(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            manifest = prepare(AP, out)
            assembly = (out / "banks.s").read_text()
            linker = (out / "banks.ld").read_text()
            for bank in manifest["banks"]:
                section = f".bank_{bank['virtual_address']:08x}"
                self.assertEqual(assembly.count(section), 1)
                self.assertEqual(linker.count(section), 2)


if __name__ == "__main__":
    unittest.main()
