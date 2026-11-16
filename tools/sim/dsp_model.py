"""Safe host-side model of the recovered ``mmm_mp.al`` DSP selector.

The firmware lookup table is proven, but the DSP payload ABI is not.  This
module therefore resolves a format index to a filename and optionally checks
an extracted member's opaque descriptor; it never executes DSP bytes.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import struct


MMM_MP_DSP_NAMES: tuple[str, ...] = (
    "adMP3.dsp",
    "adWMA.dsp",
    "adWAVH.dsp",
    "adFLAC.dsp",
    "adAPE.dsp",
    "adSBC.dsp",
    "adAAC.dsp",
    "adDSD.dsp",
    "adAAX.dsp",
    "adOGG.dsp",
    "adALAC.dsp",
    "adWMAL.dsp",
    "adTTA.dsp",
    "audiopp.dsp",
    "adppext.dsp",
    "adppdrc.dsp",
)

DSP_HEADER_BYTES = 16 * 4


@dataclass(frozen=True)
class DspSelection:
    """One opaque lookup result; ``payload_executable`` is always false."""

    format_index: int
    firmware_name: str
    member_name: str
    path: Path | None
    size: int | None
    sha256: str | None
    header_words: tuple[int, ...] | None

    @property
    def available(self) -> bool:
        return self.path is not None

    @property
    def payload_executable(self) -> bool:
        return False


def firmware_dsp_name(format_index: int) -> str:
    """Return the exact mixed-case table entry used by ``mmm_mp.al``."""
    if not 0 <= format_index < len(MMM_MP_DSP_NAMES):
        raise ValueError("mmm_mp DSP format index must be in the range 0..15")
    return MMM_MP_DSP_NAMES[format_index]


def _inspect_member(path: Path) -> tuple[int, str, tuple[int, ...]]:
    data = path.read_bytes()
    if len(data) < DSP_HEADER_BYTES:
        raise ValueError(f"DSP member is shorter than its descriptor: {path}")
    if data[:4] != b"yqhx":
        raise ValueError(f"DSP member has no offset-zero yqhx marker: {path}")
    if data[4:8] == b"yqhx":
        raise ValueError(f"DSP member unexpectedly uses a resident header: {path}")
    return len(data), hashlib.sha256(data).hexdigest(), struct.unpack_from("<16I", data)


def select_dsp(format_index: int, directory: Path) -> DspSelection:
    """Resolve one selector entry without treating a missing member as safe.

    FAT member lookup is case-insensitive on the target, while the extracted
    corpus uses lower-case names.  The host model makes that normalization
    explicit and returns an unavailable selection when a table entry is not
    present in the local corpus (for example ``adSBC.dsp``).
    """
    firmware_name = firmware_dsp_name(format_index)
    member_name = firmware_name.casefold()
    path = directory / member_name
    if not path.is_file():
        return DspSelection(format_index, firmware_name, member_name, None, None, None, None)
    size, digest, words = _inspect_member(path)
    return DspSelection(format_index, firmware_name, member_name, path, size, digest, words)
