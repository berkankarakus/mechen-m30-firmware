import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "tools/ghidra/run_bootrom_probe.sh"


class BootRomProbeRunnerTests(unittest.TestCase):
    def setUp(self):
        fake_ghidra_source = """#!/usr/bin/env python3
import os
from pathlib import Path
import sys

args = sys.argv[1:]
mark_index = args.index("MarkFunction.java")
dump_index = args.index("DumpAt.java")
mark_targets = args[mark_index + 1]
dump_targets = args[dump_index + 1]
if mark_targets != dump_targets:
    raise SystemExit("MarkFunction and DumpAt target lists differ")
expected = "0x9fc05f90,0x9fc06d6c,0x9fc06f18"
if mark_targets != expected:
    raise SystemExit("unexpected candidate target list: " + mark_targets)
output = Path(args[dump_index + 2])
addresses = dump_targets.split(",")
functions = "\\n".join("FUN_" + address[2:] for address in addresses)
if os.environ.get("M30_FAKE_DECOMPILE_FAILURE") == "1":
    functions += "\\n// failed: synthetic decompiler error"
output.write_text(functions)
for address in addresses:
    print("DumpAt: " + address[2:] + " -> FUN_" + address[2:])
"""

        self.fake_ghidra_source = fake_ghidra_source

    def run_probe(self, decompile_failure=False):
        with tempfile.TemporaryDirectory(prefix="m30-rom-probe-test-") as temp:
            temp_path = Path(temp)
            fake_ghidra = temp_path / "analyzeHeadless"
            fake_ghidra.write_text(self.fake_ghidra_source)
            fake_ghidra.chmod(0o755)
            rom_dump = temp_path / "rom.bin"
            rom_dump.write_bytes(bytes(0x40000))

            env = os.environ.copy()
            env["GHIDRA"] = str(fake_ghidra)
            env["TMPDIR"] = temp
            if decompile_failure:
                env["M30_FAKE_DECOMPILE_FAILURE"] = "1"
            else:
                env.pop("M30_FAKE_DECOMPILE_FAILURE", None)
            return subprocess.run(
                ["bash", str(RUNNER), str(rom_dump)],
                capture_output=True,
                text=True,
                env=env,
                check=False,
            )

    def test_runner_passes_all_candidate_targets_to_ghidra(self):
        result = self.run_probe()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("BOOT ROM PROBE PASS", result.stdout)
        self.assertIn("exc9=0x9fc06f18", result.stdout)

    def test_runner_fails_when_decompiler_reports_error(self):
        result = self.run_probe(decompile_failure=True)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("BOOT ROM PROBE FAIL decompiler reported an error", result.stderr)


if __name__ == "__main__":
    unittest.main()
