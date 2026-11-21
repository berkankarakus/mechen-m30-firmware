#!/usr/bin/env python3
"""Check the Ghidra-decompiled bit-banged DAC-bus protocol shape.

This validates the recovered driver code shape, not electrical behavior or a
specific codec register map. Input is the temporary output from DumpC.java.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path


FUNCTION_RE = re.compile(
    r"^// ===== (FUN_[0-9a-fA-F]+) @ [^\n]+\n(.*?)(?=^// ===== |\Z)",
    re.MULTILINE | re.DOTALL,
)


def functions_from(path: Path) -> dict[str, str]:
    return dict(FUNCTION_RE.findall(path.read_text(encoding="utf-8")))


def _ordered_calls(body: str, expected: tuple[str, ...], label: str) -> None:
    calls = [call.split("(", 1)[0].strip() for call in
             re.findall(r"\bFUN_[0-9a-fA-F]+\s*\(", body)]
    if calls:
        calls = calls[1:]  # The first occurrence is the function definition.
    if not _contains_ordered(calls, expected):
        raise ValueError(f"{label}: expected ordered calls {expected}, saw {calls}")


def _contains_ordered(actual: list[str], expected: tuple[str, ...]) -> bool:
    cursor = 0
    for item in actual:
        if cursor < len(expected) and item == expected[cursor]:
            cursor += 1
    return cursor == len(expected)


def verify(path: Path) -> None:
    functions = functions_from(path)
    required = (
        "FUN_bfc18fe0",
        "FUN_bfc19028",
        "FUN_bfc191d4",
        "FUN_bfc192e0",
        "FUN_bfc19330",
        "FUN_bfc19114",
    )
    missing = [name for name in required if name not in functions]
    if missing:
        raise ValueError("missing Ghidra function bodies: " + ", ".join(missing))

    _ordered_calls(functions["FUN_bfc18fe0"], (
        "FUN_bfc18db8", "FUN_bfc18e10", "FUN_bfc18de4", "FUN_bfc18e3c",
    ), "start condition")
    _ordered_calls(functions["FUN_bfc19028"], (
        "FUN_bfc18de4", "FUN_bfc18e10", "FUN_bfc18db8",
    ), "stop condition")

    transmit = functions["FUN_bfc191d4"]
    if not re.search(
        r"for\s*\(bStack_10\s*=\s*0;\s*bStack_10\s*<\s*8;.*?"
        r"\(uint\)param_1\s*<<\s*\(bStack_10\s*&\s*0x1f\)\s*&\s*0x80",
        transmit,
        re.DOTALL,
    ):
        raise ValueError("transmit: expected eight bit-7-to-bit-0 tests")
    _ordered_calls(transmit, ("FUN_bfc18e10", "FUN_bfc18e3c"), "transmit clock")

    ack = functions["FUN_bfc19330"]
    if not re.search(r"return\s+cVar1\s*==\s*'\\0'\s*;", ack):
        raise ValueError("ACK sampler must report success for a low sampled bit")
    _ordered_calls(ack, ("FUN_bfc18e10", "FUN_bfc18fa0", "FUN_bfc18e3c"), "ACK clock/sample")

    ack_nack = functions["FUN_bfc192e0"]
    low = ack_nack.find("FUN_bfc18de4(")
    high = ack_nack.find("FUN_bfc18db8(")
    if low < 0 or high < 0 or low > high:
        raise ValueError("read ACK/NACK: expected low for ACK and high for NACK")
    _ordered_calls(ack_nack, ("FUN_bfc18e10", "FUN_bfc18e3c"), "read ACK/NACK clock")

    receive = functions["FUN_bfc19114"]
    if "FUN_bfc192e0(uStack_f" not in receive:
        raise ValueError("receive: expected per-byte ACK/NACK helper")
    if "if (cStackX_8 == '\\x01')" not in receive:
        raise ValueError("receive: expected final-byte NACK selection")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("decomp", type=Path)
    args = parser.parse_args()
    verify(args.decomp)
    print("DAC PROTOCOL SHAPE PASS two-wire-start-stop msb-first ack-low final-nack")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
