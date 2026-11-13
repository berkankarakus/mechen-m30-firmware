"""Host-side behavior model for the MECHEN M30 feature work.

This is deliberately not a firmware emulator. It gives the filename-order,
EQ-menu and manual-index policies a deterministic contract before they are
translated into MIPS16e patches.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
import unicodedata
from typing import Iterable, Sequence


_CHUNK_RE = re.compile(r"(\d+)")


def _basename_without_extension(name: str) -> str:
    """Return the display/order name while preserving dot-files."""
    leaf = name.replace("\\", "/").rsplit("/", 1)[-1]
    if leaf.startswith(".") and leaf.count(".") == 1:
        return leaf
    stem, dot, _extension = leaf.rpartition(".")
    return stem if dot and stem else leaf


def _text_key(value: str) -> str:
    # Casefold is more appropriate than lower() for a host-side model. The
    # eventual device mapping must be checked against its Latin-1 converter.
    return unicodedata.normalize("NFKC", value).casefold()


def natural_sort_key(name: str) -> tuple:
    """Build a deterministic case-insensitive natural filename key.

    Numeric runs compare numerically, so ``Track 2`` sorts before ``Track 10``.
    The final original-name fallback keeps equal display stems deterministic.
    """
    stem = _text_key(_basename_without_extension(name))
    chunks = []
    for chunk in _CHUNK_RE.split(stem):
        if not chunk:
            continue
        if chunk.isdigit():
            chunks.append((0, int(chunk), len(chunk)))
        else:
            chunks.append((1, chunk))
    return (tuple(chunks), _text_key(name), name)


def sort_filenames(names: Iterable[str]) -> list[str]:
    """Return filenames in the proposed M30 browser order."""
    return sorted(names, key=natural_sort_key)


class IndexState(str, Enum):
    UP_TO_DATE = "up-to-date"
    DIRTY = "manual-update-needed"
    UPDATING = "updating"
    FAILED = "update-failed"


@dataclass
class IndexStatus:
    """State machine for the no-automatic-index policy."""

    state: IndexState = IndexState.UP_TO_DATE
    progress: int = 100
    files_seen: int = 0
    files_total: int = 0
    message: str = "Index up to date"

    def card_changed(self) -> None:
        self.state = IndexState.DIRTY
        self.progress = 0
        self.message = "Manual Update Playlist required"

    def begin(self, files_total: int) -> None:
        if files_total < 0:
            raise ValueError("files_total must be non-negative")
        self.state = IndexState.UPDATING
        self.progress = 0
        self.files_seen = 0
        self.files_total = files_total
        self.message = "Updating playlist"

    def advance(self, files: int = 1) -> None:
        if self.state != IndexState.UPDATING:
            raise RuntimeError("index is not updating")
        if files < 0 or self.files_seen + files > self.files_total:
            raise ValueError("progress exceeds the requested file count")
        self.files_seen += files
        self.progress = 100 if not self.files_total else round(self.files_seen * 100 / self.files_total)

    def complete(self) -> None:
        if self.state != IndexState.UPDATING or self.files_seen != self.files_total:
            raise RuntimeError("index cannot complete before all files are processed")
        self.state = IndexState.UP_TO_DATE
        self.progress = 100
        self.message = "Index up to date"

    def fail(self, message: str = "Update failed; try again") -> None:
        self.state = IndexState.FAILED
        self.message = message


@dataclass(frozen=True)
class EqPreset:
    name: str
    bands_db: tuple[int, ...]
    description: str


# Five-band curves are a UI/DSP contract for now, not firmware coefficients.
# The firmware's physical coefficient count must be recovered before applying
# these values to the player.
EQ_PRESETS: tuple[EqPreset, ...] = (
    EqPreset("Flat", (0, 0, 0, 0, 0), "Neutral"),
    EqPreset("Classical", (0, 0, -1, 2, 3), "Open highs, restrained mids"),
    EqPreset("Jazz", (0, 0, 1, 2, 1), "Warm and articulate"),
    EqPreset("Rock", (3, 2, -1, 2, 3), "Punchy low end and presence"),
    EqPreset("Pop", (-1, 2, 3, 1, -1), "Forward vocal range"),
    EqPreset("Dance", (4, 3, 0, 2, 3), "Low-end drive"),
    EqPreset("Electronic", (3, 2, -1, 1, 4), "Sub and high detail"),
    EqPreset("Hip-Hop", (4, 3, -1, 1, 2), "Bass emphasis"),
    EqPreset("Funk", (3, 1, 0, 2, 2), "Groove and snap"),
    EqPreset("Vocal", (-2, 0, 3, 2, -1), "Speech and vocal clarity"),
    EqPreset("Acoustic", (1, 1, 1, 2, 2), "Natural brightness"),
    EqPreset("Bass Boost", (5, 3, 0, -1, -1), "Low-end emphasis"),
    EqPreset("Treble Boost", (-1, -1, 0, 3, 5), "High-frequency emphasis"),
    EqPreset("Custom", (0, 0, 0, 0, 0), "User-defined curve"),
    EqPreset("Off", (0, 0, 0, 0, 0), "DSP bypass request"),
)


def eq_names() -> tuple[str, ...]:
    return tuple(p.name for p in EQ_PRESETS)


def find_eq(name: str) -> EqPreset:
    for preset in EQ_PRESETS:
        if preset.name.casefold() == name.casefold():
            return preset
    raise KeyError(name)


@dataclass
class ArtworkSession:
    """Non-blocking playback/artwork contract for the latency experiment."""

    audio_started: bool = False
    artwork_state: str = "none"
    chunks_decoded: int = 0
    events: list[str] | None = None

    def __post_init__(self) -> None:
        if self.events is None:
            self.events = []

    def start_track(self, has_artwork: bool) -> None:
        self.audio_started = True
        self.events.append("audio-start")
        if has_artwork:
            self.artwork_state = "pending"
            self.events.append("artwork-placeholder")
        else:
            self.artwork_state = "none"

    def decode_chunk(self) -> None:
        if not self.audio_started:
            raise RuntimeError("artwork cannot decode before audio starts")
        if self.artwork_state != "pending":
            raise RuntimeError("no artwork is pending")
        self.chunks_decoded += 1
        self.events.append("artwork-yield")

    def finish_artwork(self) -> None:
        if self.artwork_state != "pending":
            raise RuntimeError("no artwork is pending")
        self.artwork_state = "ready"
        self.events.append("artwork-ready")

