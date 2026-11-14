"""Semantic labels for the indirect UI calls observed in the M30 B3 bank.

The values in this table are far pointers, not direct host addresses.  The
bank-qualified part is decoded with :mod:`bankmap`; the semantic label comes
from the call arity in ``FUN_260e4ff4`` and the matching public ATJ2127 UI
function signatures.  A label is useful to the host model, but it must not be
used as proof that the corresponding M30 payload bank is present in
``drv_ui.drv``.
"""

from __future__ import annotations

from dataclasses import dataclass

from bankmap import BankAddress, decode


@dataclass(frozen=True)
class UiCall:
    pointer: int
    bank: BankAddress
    candidates: tuple[str, ...]
    confidence: str
    note: str


# These are the exact values loaded from the B3 literal pool at file offset
# 0x9924.  A19 contains more than one function, hence the two separate
# pointers in that bank.
OBSERVED_CALLS: dict[int, tuple[tuple[str, ...], str, str]] = {
    0x164C90ED: (
        ("fix_switch_fontlib",),
        "high",
        "one display-mode argument in the B3 call site",
    ),
    0x164C9001: (
        ("fixf_get_string_length",),
        "high",
        "(string descriptor, max width, result) call shape",
    ),
    0x26089471: (
        ("arabic_uni_join",),
        "medium",
        "first one-argument Arabic/Hebrew preprocessing call",
    ),
    0x260894E9: (
        ("arabic_ascii_turn",),
        "medium",
        "second one-argument Arabic/Hebrew preprocessing call",
    ),
    0x26409401: (
        ("put_string_line_sdimage",),
        "high",
        "(string descriptor, region, mode) call shape",
    ),
}


def classify(pointer: int) -> UiCall | None:
    """Return a cautious semantic label for an observed B3 indirect call."""

    pointer &= 0xFFFFFFFF
    entry = OBSERVED_CALLS.get(pointer)
    if entry is None:
        return None
    candidates, confidence, note = entry
    return UiCall(pointer, decode(pointer), candidates, confidence, note)
