"""Safe fallback record contract from the M30 library scan."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LibraryFallbackRecord:
    """Metadata emitted when a tag reader is unavailable or rejects a file."""

    title: str
    artist: str = "No Artist"
    album: str = "No Album"
    genre: str = "No Genre"
    tag_ok: bool = False

    @classmethod
    def from_short_name(cls, short_name: str) -> "LibraryFallbackRecord":
        if not short_name:
            raise ValueError("fallback record requires a non-empty short name")

        return cls(title=short_name)
