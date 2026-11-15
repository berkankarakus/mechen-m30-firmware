"""Non-executing model of the recovered ``mmm_bp.al`` buffer boundary.

This models only observable control contracts from the decompilation.  It is
not an audio renderer and deliberately does not invent sample attenuation
coefficients.
"""

from __future__ import annotations

from dataclasses import dataclass


REFILL_BLOCK_BYTES = 0x200
FADE_MODES = {2: "slow", 3: "fast"}


@dataclass(frozen=True)
class RingReadPlan:
    """A bounded, possibly wrapped read from the decoder ring."""

    requested: int
    first_offset: int
    first_length: int
    second_offset: int | None
    second_length: int


def plan_ring_read(
    read_offset: int,
    capacity: int,
    available: int,
    requested: int,
) -> RingReadPlan:
    """Return the two-copy plan used by the ring reader.

    The recovered reader accepts a request only when it is no larger than the
    available count, then splits it at the physical ring end.  It does not
    read or mutate a buffer here.
    """
    if capacity <= 0:
        raise ValueError("ring capacity must be positive")
    if not 0 <= read_offset < capacity:
        raise ValueError("read offset must be inside the ring")
    if not 0 <= available <= capacity:
        raise ValueError("available count must fit the ring")
    if not 0 <= requested <= available:
        raise ValueError("requested bytes exceed the available count")
    first_length = min(requested, capacity - read_offset)
    second_length = requested - first_length
    return RingReadPlan(
        requested=requested,
        first_offset=read_offset,
        first_length=first_length,
        second_offset=0 if second_length else None,
        second_length=second_length,
    )


def fade_mode_name(mode: int) -> str:
    """Return the recovered diagnostic/state name for a fade mode."""
    return FADE_MODES.get(mode, "inactive")
