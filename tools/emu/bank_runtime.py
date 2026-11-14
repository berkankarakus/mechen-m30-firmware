#!/usr/bin/env python3
"""Conservative lazy-bank runtime for the host-side M30 emulator."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from driver_banks import DriverBankImage, FarEntryCandidate


@dataclass(frozen=True)
class BankLoad:
    pointer: int
    group: str
    index: int
    payload_offset: int
    file_offset: int


@dataclass(frozen=True)
class DispatchResult:
    pointer: int
    status: str
    candidate: FarEntryCandidate | None
    loaded: bool


class LazyBankRuntime:
    """Model the observable part of a far call without executing raw bytes."""

    def __init__(
        self,
        driver: DriverBankImage,
        *,
        validated_entries: set[tuple[str, int, int]] | None = None,
    ) -> None:
        self.driver = driver
        self.validated_entries = validated_entries or set()
        self.active: tuple[str, int] | None = None
        self.loads: list[BankLoad] = []

    @classmethod
    def from_path(
        cls,
        path: Path,
        *,
        validated_entries: set[tuple[str, int, int]] | None = None,
    ) -> "LazyBankRuntime":
        return cls(DriverBankImage.load(path), validated_entries=validated_entries)

    def dispatch(self, pointer: int) -> DispatchResult:
        candidate = self.driver.resolve_far_candidate(pointer)
        if candidate is None:
            return DispatchResult(pointer & 0xFFFFFFFF, "resident-or-unresolved", None, False)
        if not candidate.bank_present:
            return DispatchResult(candidate.pointer, "bank-missing-or-external", candidate, False)

        # Validation is keyed by the actual aligned MIPS16 entry, while the
        # candidate keeps the raw odd pointer offset for provenance.
        key = (candidate.group, candidate.index, candidate.entry_offset)
        loaded = self.active != (candidate.group, candidate.index)
        if loaded:
            self.active = (candidate.group, candidate.index)
            self.loads.append(
                BankLoad(
                    candidate.pointer,
                    candidate.group,
                    candidate.index,
                    candidate.payload_offset,
                    candidate.file_offset,
                )
            )

        if key not in self.validated_entries:
            return DispatchResult(candidate.pointer, "bank-loaded-entry-unresolved", candidate, loaded)
        return DispatchResult(candidate.pointer, "validated-entry", candidate, loaded)
