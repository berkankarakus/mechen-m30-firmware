"""Evidence-backed FAT32/exFAT extension-table boundary.

The resident FAT32 and exFAT drivers share a fixed 31-slot table.  The
caller-side mask numbering is unresolved, so this model accepts explicit slot
numbers and never invents a mask or directory-walker policy.
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass


FIRMWARE_EXTENSION_SLOTS: tuple[str, ...] = (
    "MP3",
    "WMA",
    "WAV",
    "AAC",
    "FLAC",
    "APE",
    "AVI",
    "TXT",
    "JPG",
    "JPEG",
    "DSF",
    "DFF",
    "LRC",
    "ASF",
    "OGG",
    "TTA",
    "ISO",
    "AAX",
    "AA",
    "MP1",
    "MP2",
    "M4A",
    "POS",
    "ACT",
    "BMK",
    "AIF",
    "APK",
    "PCM",
    "**",
    "*f",
    "   ",
)


@dataclass(frozen=True)
class FilesystemExtensionTable:
    """Resolve the proven slot vocabulary without assigning mask semantics."""

    slots: tuple[str, ...] = FIRMWARE_EXTENSION_SLOTS

    def __post_init__(self) -> None:
        if len(self.slots) != 31:
            raise ValueError("firmware extension table must contain 31 slots")

        if any(len(slot.encode("ascii")) > 4 for slot in self.slots):
            raise ValueError("firmware extension slots must fit four bytes")

    def slot_for_extension(self, extension: str) -> int | None:
        """Return the exact firmware slot for an ASCII extension, if present."""
        candidate = extension.upper()

        try:
            normalized_slots = tuple(slot.upper() for slot in self.slots)
            return normalized_slots.index(candidate)

        except ValueError:
            return None

    def accepts_slot(self, extension: str, accepted_slots: Collection[int]) -> bool:
        """Apply an explicit caller decision without modeling its bitmask."""
        slot = self.slot_for_extension(extension)

        if slot is None:
            return False

        return slot in accepted_slots
