"""Host model of the recovered 0x6e40-byte usound software-ring writer."""

from __future__ import annotations

from dataclasses import dataclass, field

from usound_format import expand_three_to_four


RING_CAPACITY = 0x6E40
EXPANDED_READY_THRESHOLD = 0x1B90
DIRECT_READY_THRESHOLD = 0x3720


@dataclass
class SoftwareRing:
    """Model ``FUN_bfc30dc4``'s byte producer, without hardware I/O."""

    data: bytearray = field(default_factory=lambda: bytearray(RING_CAPACITY))
    write_offset: int = 0
    available: int = 0
    ready_signal: int = 0

    def __post_init__(self) -> None:
        if len(self.data) != RING_CAPACITY:
            raise ValueError("software ring must be exactly 0x6e40 bytes")
        if not 0 <= self.write_offset < RING_CAPACITY:
            raise ValueError("write_offset must be a ring offset")
        if not 0 <= self.available <= RING_CAPACITY:
            raise ValueError("available must fit inside the software ring")

    def produce(self, source: bytes, *, expanded: bool) -> bool:
        """Write one hardware block and return whether the ready edge fired."""

        output = expand_three_to_four(source) if expanded else source
        output_size = len(output)
        if output_size > RING_CAPACITY:
            raise ValueError("one produced block cannot exceed the ring")

        first = min(output_size, RING_CAPACITY - self.write_offset)
        self.data[self.write_offset : self.write_offset + first] = output[:first]
        second = output_size - first
        if second:
            self.data[:second] = output[first:]

        self.write_offset = (self.write_offset + output_size) % RING_CAPACITY
        self.available += output_size
        if self.available > RING_CAPACITY:
            # This is the observed overrun policy, not a generic clamp.
            self.available = self.write_offset

        threshold = EXPANDED_READY_THRESHOLD if expanded else DIRECT_READY_THRESHOLD
        if self.available >= threshold and self.ready_signal == 0:
            self.ready_signal = 1
            return True
        return False
