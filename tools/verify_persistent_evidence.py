#!/usr/bin/env python3
"""Verify the external evidence bundle required for M30 analysis."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import sys


CORPUS_HASHES = {
    "2022-08-05": "ee47440fdc5fbcb8bef85119d4ce39108ad92b961bb100cfa3c785bf858c14ac",
    "2022-08-16": "aa07468df20f8f0ca3116c1e0bb1305b1ab6eecbfdf32bb7ef70c7dcde0b2a6e",
    "2022-09-14": "6aa4e532307b5147d3da982439e0bfb82aca051853c3c911668fc651d909a640",
    "2022-11-17": "aa54f80afb13bb6d6c405854643a2d06f8ef768b5b958d3aac9f711a65224e72",
    "2022-12-16": "0e56c50e9720da7e95910582fbd1c293f77c1f1346c755a02ca2e08b5753184e",
    "2023-02-20": "ee164011fb1fe30f552348613f832c5cb0f2aee271834f891aad22be6674e6da",
    "2023-07-26": "07a8917d0d71c11894f9ecbb394b7013e04f2513d0ad5181ad9a3cb5e49c9bd5",
    "2024-02-28": "ac761a406b99366804c64df3d353fb73f11d91e4bea386202c22a4cd70d33739",
    "2024-03-19": "6103567b8ef71b635ad7ff1715070982e4135bb0fe1864d8e1d7b95aa5463752",
    "2024-04-24": "8355edd60c4b964ef85d5510ed634cc50591b35f6a8e95f95d4a40b09ef99289",
    "2025-02-17": "7ec4f3e1f528d7368a27a18db4fb51253823cf42a9e1760f4381b4233eb9974e",
    "2025-06-26": "6c7e27c8c90c4942664d66a0d6c9f9e48f8d3bc7d2d24223568255e233551258",
}

MODIFICATION_HASHES = {
    "2022-08-05": "e5f5390b00bdeadcde942991625b3fb493b8f5dc43a21d65803a45bac96050cf",
    "2022-08-16": "438fd4a47d145f6b63ab83f0404e0928eceda08ce48c3f33855197b19b615e3d",
    "2022-09-14": "131a8b4f6dd81af1430a7400818fe4c9a716e63871d5f38714ed644e04f8c4a3",
    "2022-11-17": "b5147752d3857c83ad5360ea23bfbb7c5807ccd8c17763ccda16a3f29b9a5e20",
    "2022-12-16": "785893d8729388572e49b6611c2c92808e40f03301dea1432f597d820ff82de2",
    "2023-02-20": "a321e028d17ac7afd973246b55f7fadeeadc426b811875bd18e875fea7fe6702",
    "2023-07-26": "34053cf1e26a48e38f397b80953513bb283a0598244033b5d1f719943e9fabf6",
    "2024-02-28": "3b7e0d0ac423c32acb07ffaf77e85e77d7d309367704d08b5713399da1fa0b2b",
    "2024-03-19": "ca78c82ffd626fc7c3a7f2b1a6b3aa11eb061d1eaf1fd09b0f279d565e91d4e1",
    "2024-04-24": "bcabe1323b2eb519065042c5bdf8a5aed9aa2711f29a220c0ee5d7f4da4ac626",
    "2025-06-26": "7932fbd0eb3a545930c4365c469e782a5b1bf254329951931b8cfb4b826f2430",
}

EXACT_FILES = {
    "device-sd/MUSIC.LIB": ("e386db27a9f47641e8755e5a58a903e6e66f83afe2be84c97d5d7e59de0f3c88", 2_625_536),
    "device-sd/M3U.LIB": ("ad4deb5b599eb97309e49a1d907cab445e3785d04f0ee103e6126f8ab0703a01", 1_550_848),
    "device-sd/ALBUM.PIC": ("65bad6f0a143f3990f1d0e958699513159dc3b06f7bcec0452ee318217c8e671", 128_000),
    "MUSIC.LIB": ("cc3f476c8edb50ea8493b726d46ac82b139a6e87a86cc04c2cdbc30fd3fb8afe", 1_536_000),
    "decompile/library-record-consumers-2025-06-26/consumers.c": ("16c1316bf4c0fa3deccf7378c735fc9c65933f7bc1fabcd5e8e8a9a245021268", None),
    "decompile/library-record-consumers-2025-06-26/album.c": ("e8cfb7d628e0b188e1a73a7617c2e7d6f52d9537dd36c6d98a1db5180dd6fe22", None),
    "decompile/library-record-consumers-2025-06-26/run.log": ("6e0226856e6c5976478def9f3c76cba4e1de83704c6d3dddd764378ca2564a47", None),
    "decompile/library-record-consumers-2025-06-26/album-run.log": ("d1f81e75f6adf462d037c018d468e12fd92b8c04190e2bbfe2424fa184f839c4", None),
    "decompile/library-index-2025-06-26/index.c": ("b4d24e168ca61c697c489404ad35d92644d6a0e0effb5b03b010e76dc356fcbc", None),
    "decompile/library-index-2025-06-26/run.log": ("ed7b274f79bc6a73896c592a9b65cad30813ff369629a115894430f85280bad8", None),
    "decompile/library-tie-2025-06-26/tie.c": ("80c8cd7af541f3327e459af47f487a0bebdd98334c1de1c503649acefb98b559", None),
    "decompile/library-tie-2025-06-26/run.log": ("32b960ef3325d8e8973b576e08d56c50751ecf9836d902ea0191ef8d59115ce5", None),
    "references/us212a-app-design-guide-v2.pdf": ("c6795e5aaef95af5b9bd16d469086e4f69603db87409791f039315705d7d0b05", None),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def verify_file(root: Path, relative_path: str, expected_hash: str, expected_size: int | None) -> bool:
    path = root / relative_path

    if not path.is_file():
        print(f"MISSING {relative_path}")

        return False

    actual_size = path.stat().st_size
    actual_hash = sha256(path)

    if expected_size is not None and actual_size != expected_size:
        print(f"SIZE   {relative_path}: expected {expected_size}, got {actual_size}")

        return False

    if actual_hash != expected_hash:
        print(f"HASH   {relative_path}: expected {expected_hash}, got {actual_hash}")

        return False

    print(f"OK     {relative_path}")

    return True


def verify_corpora(root: Path) -> bool:
    passed = True

    for date, expected_hash in CORPUS_HASHES.items():
        passed = verify_file(root, f"hex/{date}.HEX", expected_hash, None) and passed
        modification_hash = MODIFICATION_HASHES.get(date)

        if modification_hash is None:
            print(
                f"INFO   modifications/{date}.txt is not present; "
                "the dated corpus manifest is the only recorded note"
            )

        else:
            passed = verify_file(
                root,
                f"modifications/{date}.txt",
                modification_hash,
                None,
            ) and passed

        firmware_directory = root / "extracted" / date / "fw"

        if not firmware_directory.is_dir():
            print(f"MISSING extracted/{date}/fw")
            passed = False

            continue

        for member_name in ("music.ap", "music.sty", "setting.sty", "drv_ui.drv"):
            member_path = firmware_directory / member_name

            if not member_path.is_file():
                print(f"MISSING extracted/{date}/fw/{member_name}")
                passed = False

    return passed


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify the portable M30 evidence bundle outside the Git repository."
    )
    parser.add_argument(
        "root",
        type=Path,
        help="Persistent evidence root containing hex/, extracted/, device-sd/, and decompile/.",
    )
    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()
    root = arguments.root.expanduser().resolve()

    if not root.is_dir():
        print(f"evidence root does not exist: {root}", file=sys.stderr)

        return 2

    passed = True

    for relative_path, (expected_hash, expected_size) in EXACT_FILES.items():
        passed = verify_file(root, relative_path, expected_hash, expected_size) and passed

    passed = verify_corpora(root) and passed

    if not passed:
        print("PERSISTENT EVIDENCE FAIL")

        return 1

    print("PERSISTENT EVIDENCE PASS")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
