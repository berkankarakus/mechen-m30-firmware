import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools/rom/dump_bootrom.sh"


FAKE_ACTIONS_DUMP = """#!/bin/sh
set -eu
case " $* " in
  *' adfu_info '*)
    if [ "${FAKE_ADFU_IDENTITY:-ATJ2127}" = ATJ2127 ]; then
      echo 'guess: chip = ATJ2127' >&2
    else
      echo 'guess: chip = ATJ2157' >&2
    fi
    ;;
  *' read_mem2 '*)
    eval "out=\\${$#}"
    dd if=/dev/zero of="$out" bs=262144 count=1 2>/dev/null
    ;;
esac
"""


class DumpBootRomTests(unittest.TestCase):
    def make_fake_client(self, directory: Path) -> Path:
        client = directory / "actions_dump"
        client.write_text(FAKE_ACTIONS_DUMP)
        client.chmod(client.stat().st_mode | stat.S_IXUSR)
        return client

    def run_dump(self, directory: Path, identity: str) -> subprocess.CompletedProcess[str]:
        client = self.make_fake_client(directory)
        adfus = directory / "adfus.bin"
        adfus.write_bytes(b"payload")
        output = directory / "rom.bin"
        env = os.environ.copy()
        env["FAKE_ADFU_IDENTITY"] = identity
        return subprocess.run(
            [
                "bash",
                str(SCRIPT),
                "--actions-dump",
                str(client),
                "--adfus",
                str(adfus),
                "--out",
                str(output),
                "--execute",
                "--acknowledge-ram-only",
            ],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
        )

    def test_atj2127_identity_allows_read_only_dump(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            result = self.run_dump(directory, "ATJ2127")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("ADFU identity PASS: ATJ2127", result.stdout)
            self.assertEqual((directory / "rom.bin").stat().st_size, 0x40000)

    def test_other_identity_refuses_payload_upload(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            result = self.run_dump(directory, "ATJ2157")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("identity is not confirmed", result.stderr)
            self.assertFalse((directory / "rom.bin").exists())


if __name__ == "__main__":
    unittest.main()
