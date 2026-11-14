#!/usr/bin/env python3
"""Host-side model of the two resident driver-loader variants.

This turns the Ghidra-derived loader contracts into deterministic events. It
models copying and residency bookkeeping only; no raw MIPS payload is called.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from yqhx import YqhxImage, slot_layout


@dataclass(frozen=True)
class LoaderSpec:
    name: str
    header_read: int
    slot_stride: int
    uses_entry_callback: bool


LOADER_A408 = LoaderSpec("bfc0a408", 0x4C, 0, True)
LOADER_A578 = LoaderSpec("bfc0a578", 0x44, 12, False)


@dataclass(frozen=True)
class DriverLoadEvent:
    loader: str
    mode: int
    slot_offset: int
    header_read: int
    already_installed: bool
    plan: tuple[tuple[str, int, int], ...]
    entry: int
    entry_context: bytes | None


class ResidentDriverLoader:
    """Track the resident slots exposed by one decompiled loader."""

    def __init__(self, spec: LoaderSpec):
        self.spec = spec
        self._installed: set[int] = set()
        self.events: list[DriverLoadEvent] = []

    @classmethod
    def a408(cls) -> "ResidentDriverLoader":
        return cls(LOADER_A408)

    @classmethod
    def a578(cls) -> "ResidentDriverLoader":
        return cls(LOADER_A578)

    def slot_offset(self, mode: int) -> int:
        if self.spec is LOADER_A408:
            return (mode & 0xFF) * slot_layout(mode)[1]
        return (mode & 0xFF) * self.spec.slot_stride

    def load(self, path: Path, mode: int) -> DriverLoadEvent:
        image = YqhxImage.load(path)
        offset = self.slot_offset(mode)
        already_installed = offset in self._installed
        if not already_installed:
            self._installed.add(offset)
        event = DriverLoadEvent(
            loader=self.spec.name,
            mode=mode & 0xFF,
            slot_offset=offset,
            header_read=self.spec.header_read,
            already_installed=already_installed,
            plan=image.load_plan(),
            entry=image.entry,
            entry_context=image.entry_context if self.spec.uses_entry_callback else None,
        )
        self.events.append(event)
        return event
