#!/usr/bin/env python3
"""Build a community V1.292 HEX with Custom EQ gains and 64 ms marquee."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import shutil
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(TOOLS / "emu"))

from patch_eq_custom import patch as patch_custom  # noqa: E402
from patch_ui_motion import patch_ap as patch_motion  # noqa: E402
from candidate_delta_probe import verify_exact_delta  # noqa: E402
from repack_fw import main as repack  # noqa: E402
from repacked_hex_probe import verify_repacked_hex  # noqa: E402


EXPECTED_HEX_SHA256 = "5e17d883f697a67d4face6f624ddc30952c5542c918b219be974bf380383ed2c"
EXPECTED_AFI_SHA256 = "66e46b5e16d133091a0cf8102ea2a07383d77a8aa33e0393c3b27129ce0e79de"
CHANGED_MEMBERS = ("browser.ap", "music.ap")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(source_hex: Path, source_afi: Path, source_fw: Path, output_hex: Path) -> None:
    for path in (source_hex, source_afi):
        if not path.is_file():
            raise ValueError(f"missing input: {path}")
    if not source_fw.is_dir():
        raise ValueError(f"missing extracted firmware directory: {source_fw}")
    if sha256(source_hex) != EXPECTED_HEX_SHA256:
        raise ValueError("input HEX is not the pinned community V1.292.00 baseline")
    if sha256(source_afi) != EXPECTED_AFI_SHA256:
        raise ValueError("decrypted AFI does not match the pinned community baseline")
    if output_hex.exists():
        raise ValueError(f"refusing to overwrite existing output: {output_hex}")

    output_hex.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="m30-custom-eq-64ms-") as temporary:
        work = Path(temporary)
        candidate_fw = work / "fw"
        shutil.copytree(source_fw, candidate_fw)

        for name in CHANGED_MEMBERS:
            if not (candidate_fw / name).is_file():
                raise ValueError(f"source member missing: {name}")
        patch_motion(candidate_fw / "browser.ap", candidate_fw / "browser.ap")
        patch_motion(candidate_fw / "music.ap", candidate_fw / "music.ap")
        patch_custom(candidate_fw / "music.ap", candidate_fw / "music.ap")
        verify_exact_delta(source_fw, candidate_fw, CHANGED_MEMBERS)

        # Establish that the pinned HEX and decrypted AFI are an exact pair.
        roundtrip = work / "community-noop.HEX"
        repack(str(source_hex), str(source_afi), str(roundtrip), {})
        if sha256(roundtrip) != EXPECTED_HEX_SHA256:
            raise ValueError("community no-op repack did not reproduce source HEX")

        replacements = {name: str(candidate_fw / name) for name in CHANGED_MEMBERS}
        repack(str(source_hex), str(source_afi), str(output_hex), replacements)
        verified = verify_repacked_hex(
            source_hex,
            source_afi,
            output_hex,
            source_fw,
            candidate_fw,
            CHANGED_MEMBERS,
        )
        print(f"decrypted round-trip verified members={','.join(verified)}")

    if output_hex.stat().st_size != source_hex.stat().st_size:
        raise ValueError("candidate HEX size differs from community baseline")
    print(f"candidate sha256={sha256(output_hex)}")
    print(f"changed members={','.join(CHANGED_MEMBERS)}")
    print("config.ap, config.bin and saved-settings bytes unchanged; device behavior not tested")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_hex", type=Path)
    parser.add_argument("source_afi", type=Path)
    parser.add_argument("source_fw", type=Path)
    parser.add_argument("output_hex", type=Path)
    args = parser.parse_args()
    build(args.source_hex, args.source_afi, args.source_fw, args.output_hex)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
