#!/usr/bin/env python3
"""Build a Malta BIOS image around the extracted M30 exception vector.

QEMU's Malta MIPS-LE path byte-swaps each 32-bit word in a supplied BIOS
image before creating the read-only reset-address mirror. This builder emits
the inverse word order so guest-visible instructions and data stay little
endian after QEMU's swap.
"""

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path


BIOS_SIZE = 4 * 1024 * 1024
SWAP_SIZE = 0x3E0000
VECTOR_BIOS_OFFSET = 0x8180
VECTOR_DRIVER_OFFSET = 0x380
TABLE_SLOT_9_OFFSET = 0x1A9C8
TABLE_HANDLER = 0xBFC06F18
EXPECTED_KERNEL_SHA256 = "58f9d0c62bdbdab7cfeee1c5e65bbe8b88ee962f8eecd3dd0515d1a1056d8bd6"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("kernel_driver", type=Path)
    parser.add_argument("harness", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    output_path = args.output.resolve()
    input_paths = {args.kernel_driver.resolve(), args.harness.resolve()}
    aliases_input = output_path in input_paths
    if output_path.exists():
        aliases_input |= any(
            source.exists() and os.path.samefile(output_path, source)
            for source in (args.kernel_driver, args.harness)
        )
    if aliases_input:
        raise SystemExit("output path must not overwrite kernel.drv or harness")

    kernel = args.kernel_driver.read_bytes()
    digest = hashlib.sha256(kernel).hexdigest()
    if digest != EXPECTED_KERNEL_SHA256:
        raise SystemExit(f"kernel.drv SHA-256 mismatch: {digest}")
    if len(kernel) < VECTOR_DRIVER_OFFSET + 0x80:
        raise SystemExit("kernel.drv is truncated before exception vector")

    image = bytearray(b"\xff" * BIOS_SIZE)
    harness = args.harness.read_bytes()
    if not harness or len(harness) > VECTOR_BIOS_OFFSET:
        raise SystemExit("harness must fit before the injected exception vector")
    image[: len(harness)] = harness
    image[VECTOR_BIOS_OFFSET : VECTOR_BIOS_OFFSET + 0x80] = kernel[
        VECTOR_DRIVER_OFFSET : VECTOR_DRIVER_OFFSET + 0x80
    ]
    image[TABLE_SLOT_9_OFFSET : TABLE_SLOT_9_OFFSET + 4] = TABLE_HANDLER.to_bytes(
        4, "little"
    )

    # Malta's little-endian loader swaps complete words up to 0x3e0000.
    for offset in range(0, SWAP_SIZE, 4):
        image[offset : offset + 4] = image[offset : offset + 4][::-1]
    output_path.write_bytes(image)
    print(
        "MALTA BIOS IMAGE PASS "
        f"size=0x{len(image):x} vector=0xbfc08180 "
        f"table-slot9=0xbfc06f18 kernel-sha256={digest}"
    )


if __name__ == "__main__":
    main()
