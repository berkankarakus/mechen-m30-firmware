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


class CardChangePolicy(str, Enum):
    """Policy for the observed powered card removal-and-reinsertion case."""

    MANUAL_UPDATE_REQUIRED = "manual-update-required"
    AUTOMATIC_REBUILD = "automatic-rebuild"


@dataclass
class IndexStatus:
    """State model for manual updates and one observed powered reinsertion."""

    state: IndexState = IndexState.UP_TO_DATE
    progress: int = 100
    files_seen: int = 0
    files_total: int = 0
    message: str = "Index up to date"
    card_change_policy: CardChangePolicy = CardChangePolicy.MANUAL_UPDATE_REQUIRED

    def powered_card_reinserted(self, files_total: int | None = None) -> None:
        """Apply the policy after a powered card removal-and-reinsertion.

        The event is based on one reported device observation. Its detection
        and dispatch path, removal-only behavior, and other card-change cases
        are not modeled.
        """

        if self.card_change_policy is CardChangePolicy.AUTOMATIC_REBUILD:
            if files_total is None:
                raise ValueError("automatic card reinsertion requires files_total")

            self.begin(files_total)
            self.message = "Updating playlist after powered card reinsertion"
            return

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


MAX_VOLUME_LEVEL = 100
DEFAULT_VOLUME_LIMIT = MAX_VOLUME_LEVEL


class SleepTimerPersistence(str, Enum):
    ONE_SHOT = "one-shot"
    PERSISTENT = "persistent"


@dataclass
class SleepTimerState:
    """Track the selected sleep-timer value across a modeled reboot.

    The public change note establishes persistence, but not the timer unit,
    selectable values, or countdown implementation. The value is therefore
    intentionally opaque and this state does not model elapsed time.
    """

    selected_value: int | None = None
    persistence: SleepTimerPersistence = SleepTimerPersistence.PERSISTENT

    def select(self, value: int | None) -> None:
        self.selected_value = value

    def reboot(self) -> None:
        """Apply the observed setting lifetime without advancing a timer."""
        if self.persistence is SleepTimerPersistence.ONE_SHOT:
            self.selected_value = None


@dataclass
class VolumeLimitState:
    """Model the documented UI-level volume cap without claiming DAC scaling."""

    limit: int = DEFAULT_VOLUME_LIMIT

    def __post_init__(self) -> None:
        self._validate_level(self.limit)

    def set_limit(self, limit: int) -> None:
        """Set the inclusive maximum volume level exposed by the UI."""
        self._validate_level(limit)
        self.limit = limit

    def clamp(self, requested_level: int) -> int:
        """Return a requested level constrained by the configured cap."""
        self._validate_level(requested_level)

        return min(requested_level, self.limit)

    @staticmethod
    def _validate_level(level: int) -> None:
        if not 0 <= level <= MAX_VOLUME_LEVEL:
            raise ValueError("volume level must be between 0 and 100")


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


# Evidence-backed firmware contract, recovered from the M30 `music.ap` and
# `mengine.ap` selector/coefficient paths.  Keep this separate from the
# five-band UI catalogue above: the latter is a proposed host-side design,
# while this table describes what the shipped binary actually consumes.
FIRMWARE_EQ_BAND_HZ: tuple[int, ...] = (80, 200, 480, 980, 4000, 8000, 16000)
FIRMWARE_EQ_Q_VALUES: tuple[int, ...] = (10, 6, 4, 6, 10, 5, 8)
FIRMWARE_EQ_GAIN_SCALE = 10
FIRMWARE_EQ_MESSAGE_ID = 0x303
FIRMWARE_EQ_SELECTOR_OFFSET = 0x41
FIRMWARE_EQ_STRUCTURE_SIZE = 0xF0
FIRMWARE_EQ_STRUCTURE_BAND_OFFSET = 0x10
FIRMWARE_EQ_BAND_STRIDE = 8
FIRMWARE_EQ_BUILTIN_BAND_COUNT = 7
FIRMWARE_EQ_CLEAR_TAIL_START = 0x48
FIRMWARE_EQ_CLEAR_TAIL_END = 0x90
# The invalid-magic path clears the 0x38-byte persistent block before filling
# its known fields. Its seven Custom bytes therefore start at zero. The
# separate setting.ap row is raw resource data; no path from it to this block
# has been verified.
FIRMWARE_EQ_ZEROED_BLOCK_CUSTOM: tuple[int, ...] = (0, 0, 0, 0, 0, 0, 0)
FIRMWARE_EQ_SETTING_CUSTOM_ROW: tuple[int, ...] = (-9, 0, 0, 0, 0, 0, 6)


@dataclass(frozen=True)
class FirmwareEqPreset:
    """One selector entry in the recovered M30 EQ message contract."""

    name: str
    eq_type: int
    selector: int
    gain_int8: tuple[int, ...] | None


@dataclass(frozen=True)
class FirmwareEqProfile:
    """One verified firmware revision's seven-band EQ contract."""

    name: str
    band_hz: tuple[int, ...]
    q_values: tuple[int, ...]
    presets: tuple[FirmwareEqPreset, ...]
    setting_custom_row: tuple[int, ...] | None


@dataclass(frozen=True)
class FirmwareEqBuildResult:
    """Observed output of the M30's gated seven-band structure builder."""

    selector_copy: int
    structure: bytes
    built: bool


@dataclass(frozen=True)
class FirmwareEqCommand:
    """The proven EQ command envelope sent to the engine."""

    message_id: int
    eq_type: int
    selector: int
    selector_source_offset: int


FIRMWARE_EQ_PRESETS: tuple[FirmwareEqPreset, ...] = (
    FirmwareEqPreset("Off", 0, 0, (0, 0, 0, 0, 0, 0, 0)),
    FirmwareEqPreset("Rock", 7, 1, (5, 3, 0, -1, 0, 4, 5)),
    FirmwareEqPreset("Funk", 7, 2, (3, 0, 0, 0, 0, -1, -2)),
    FirmwareEqPreset("Hip hop", 7, 3, (0, 0, 1, 2, 0, 1, 1)),
    FirmwareEqPreset("Jazz", 7, 4, (3, 0, 0, -1, 0, 2, 4)),
    FirmwareEqPreset("Classical", 7, 5, (0, 0, 0, -1, -1, -2, -4)),
    FirmwareEqPreset("Techno", 7, 6, (5, 2, 0, 0, 0, 0, 6)),
    # Custom gains are copied from RAM by music.ap before this payload is sent.
    FirmwareEqPreset("Custom", 7, 7, None),
)


FIRMWARE_EQ_CURRENT_PROFILE = FirmwareEqProfile(
    name="current",
    band_hz=FIRMWARE_EQ_BAND_HZ,
    q_values=FIRMWARE_EQ_Q_VALUES,
    presets=FIRMWARE_EQ_PRESETS,
    setting_custom_row=FIRMWARE_EQ_SETTING_CUSTOM_ROW,
)
FIRMWARE_EQ_2024_04_PROFILE = FirmwareEqProfile(
    name="2024-04",
    band_hz=(50, 200, 480, 980, 4000, 8000, 16000),
    q_values=FIRMWARE_EQ_Q_VALUES,
    presets=FIRMWARE_EQ_PRESETS,
    setting_custom_row=None,
)
FIRMWARE_EQ_PROFILES: dict[str, FirmwareEqProfile] = {
    profile.name: profile
    for profile in (FIRMWARE_EQ_CURRENT_PROFILE, FIRMWARE_EQ_2024_04_PROFILE)
}


def find_firmware_eq_profile(name: str) -> FirmwareEqProfile:
    """Return a verified EQ profile by its case-insensitive name."""
    normalized_name = name.casefold()
    for profile in FIRMWARE_EQ_PROFILES.values():
        if profile.name.casefold() == normalized_name:
            return profile

    raise KeyError(name)


def firmware_eq_names() -> tuple[str, ...]:
    """Return the names in the recovered selector order."""
    return tuple(p.name for p in FIRMWARE_EQ_PRESETS)


def find_firmware_eq(name: str) -> FirmwareEqPreset:
    """Look up a recovered firmware selector by name."""
    for preset in FIRMWARE_EQ_PRESETS:
        if preset.name.casefold() == name.casefold():
            return preset
    raise KeyError(name)


def firmware_eq_payload(name: str) -> tuple[int, int]:
    """Return the `{eq_type, selector}` bytes sent in message ``0x303``."""
    command = firmware_eq_command(name)
    return command.eq_type, command.selector


def firmware_eq_command(name: str) -> FirmwareEqCommand:
    """Build the proven message envelope without inventing DSP payload fields."""
    preset = find_firmware_eq(name)
    return FirmwareEqCommand(
        FIRMWARE_EQ_MESSAGE_ID,
        preset.eq_type,
        preset.selector,
        FIRMWARE_EQ_SELECTOR_OFFSET,
    )


def firmware_eq_gains(
    selector: int,
    custom: Sequence[int] | None = None,
    *,
    profile: FirmwareEqProfile = FIRMWARE_EQ_CURRENT_PROFILE,
) -> tuple[int, ...]:
    """Resolve the seven gain values used by the recovered engine path.

    Selector 7 is the RAM-backed Custom path.  It intentionally requires an
    explicit seven-value curve instead of silently inventing coefficients.
    """
    if not 0 <= selector < len(profile.presets):
        raise ValueError("firmware EQ selector must be in the range 0..7")
    preset = profile.presets[selector]
    if selector == 7:
        if custom is None or len(custom) != len(profile.band_hz):
            raise ValueError("Custom firmware EQ requires seven gain values")
        if any(not -128 <= value <= 127 for value in custom):
            raise ValueError("Custom firmware EQ gains must fit signed int8")
        return tuple(custom)
    assert preset.gain_int8 is not None
    return preset.gain_int8


def firmware_eq_gain_s16(
    selector: int,
    custom: Sequence[int] | None = None,
    *,
    profile: FirmwareEqProfile = FIRMWARE_EQ_CURRENT_PROFILE,
) -> tuple[int, ...]:
    """Return the builder's signed-16 gain words after its observed x10 step."""

    return tuple(
        gain * FIRMWARE_EQ_GAIN_SCALE
        for gain in firmware_eq_gains(selector, custom, profile=profile)
    )


def build_firmware_eq_structure(
    selector: int,
    active_flag: int,
    structure: bytes,
    custom: Sequence[int] | None = None,
    *,
    profile: FirmwareEqProfile = FIRMWARE_EQ_CURRENT_PROFILE,
) -> FirmwareEqBuildResult:
    """Apply the p-code-verified EQ builder writes to an existing RAM image.

    The selector mirror is written before the active/busy guards. On an
    inactive call or when structure byte +0x0c is exactly 1, the 0xf0-byte
    structure is unchanged. Unknown header and trailing bytes are preserved.
    """

    if len(structure) != FIRMWARE_EQ_STRUCTURE_SIZE:
        raise ValueError("EQ structure must be exactly 0xf0 bytes")

    if not 0 <= selector <= 0xFF:
        raise ValueError("EQ selector must fit one byte")

    if not 0 <= active_flag <= 0xFF:
        raise ValueError("EQ active flag must fit one byte")

    if active_flag == 0 or structure[0x0C] == 1:
        return FirmwareEqBuildResult(selector, structure, False)

    if selector >= len(profile.presets):
        raise ValueError("EQ builder model only supports observed selectors 0..7")

    gains = firmware_eq_gain_s16(selector, custom, profile=profile)
    updated = bytearray(structure)
    updated[0x07] = 1
    updated[0x0D] = int(selector != 0)

    for band_index in range(FIRMWARE_EQ_BUILTIN_BAND_COUNT):
        offset = FIRMWARE_EQ_STRUCTURE_BAND_OFFSET + band_index * FIRMWARE_EQ_BAND_STRIDE
        record = (
            profile.band_hz[band_index].to_bytes(2, "little")
            + profile.q_values[band_index].to_bytes(2, "little")
            + gains[band_index].to_bytes(2, "little", signed=True)
            + bytes((1, 0))
        )
        updated[offset : offset + FIRMWARE_EQ_BAND_STRIDE] = record

    updated[FIRMWARE_EQ_CLEAR_TAIL_START : FIRMWARE_EQ_CLEAR_TAIL_END] = bytes(
        FIRMWARE_EQ_CLEAR_TAIL_END - FIRMWARE_EQ_CLEAR_TAIL_START
    )

    return FirmwareEqBuildResult(selector, bytes(updated), True)


def eq_names() -> tuple[str, ...]:
    return tuple(p.name for p in EQ_PRESETS)


def find_eq(name: str) -> EqPreset:
    for preset in EQ_PRESETS:
        if preset.name.casefold() == name.casefold():
            return preset
    raise KeyError(name)


@dataclass
class ArtworkSession:
    """Playback-start and UI-thread artwork contract.

    The engine starts audio before the UI requests artwork, but the recovered
    artwork decode itself is synchronous on the UI thread. Keep those facts
    separate so a host trace does not accidentally present the decode as an
    asynchronous implementation.
    """

    audio_started: bool = False
    artwork_state: str = "none"
    ui_blocked: bool = False
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
        self.ui_blocked = True
        self.chunks_decoded += 1
        self.events.append("artwork-decode-block")

    def finish_artwork(self) -> None:
        if self.artwork_state != "pending":
            raise RuntimeError("no artwork is pending")
        self.artwork_state = "ready"
        self.ui_blocked = False
        self.events.append("artwork-ready")

