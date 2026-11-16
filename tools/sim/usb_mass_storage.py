"""Evidence-backed USB mass-storage block-request boundary.

The extracted ``uhost.drv`` contains the ``USBC`` marker, READ(10) and
WRITE(10) opcodes, a block address, and transfer lengths expressed in
512-byte units.  It does not provide enough evidence for complete CBW/CSW
serialization or controller behavior, so this model stops at the request
fields that are visible in the decompilation.
"""

from __future__ import annotations

from dataclasses import dataclass

from sd_block_device import SdCardBlockDevice

CBW_SIGNATURE = b"USBC"
READ10_OPCODE = 0x28
WRITE10_OPCODE = 0x2A
READ_DIRECTION = 0x80
BLOCK_SIZE = 512
CONTROL_OPERATION = 0x1F
OBSERVED_STATUS_CODES = frozenset(range(0x80, 0x89))


@dataclass(frozen=True)
class UsbMassStorageTransportEvent:
    """One raw controller event observed around the block transport."""

    operation: int
    status: int

    def __post_init__(self) -> None:
        if self.operation != CONTROL_OPERATION:
            raise ValueError("operation is not the observed USB control operation")

        if not 0 <= self.status <= 0xFF:
            raise ValueError("status must fit one byte")

        if self.status not in OBSERVED_STATUS_CODES:
            raise ValueError("status is outside the observed USB status range")


@dataclass(frozen=True)
class UsbMassStorageBlockRequest:
    """One observed SCSI block request without transport framing."""

    opcode: int
    block_address: int
    block_count: int
    direction: int | None = None

    def __post_init__(self) -> None:
        if self.opcode not in (READ10_OPCODE, WRITE10_OPCODE):
            raise ValueError("opcode must be READ(10) or WRITE(10)")

        if self.block_address < 0:
            raise ValueError("block_address must be non-negative")

        if self.block_count < 0:
            raise ValueError("block_count must be non-negative")

        if self.direction is not None and not 0 <= self.direction <= 0xFF:
            raise ValueError("direction must fit one byte")

        if self.opcode == READ10_OPCODE and self.direction != READ_DIRECTION:
            raise ValueError("READ(10) requires the observed 0x80 direction")

        if self.opcode == WRITE10_OPCODE and self.direction is not None:
            raise ValueError("WRITE(10) direction remains unresolved")

    @classmethod
    def read10(cls, block_address: int, block_count: int) -> "UsbMassStorageBlockRequest":
        """Build the observed READ(10) request boundary."""
        return cls(
            opcode=READ10_OPCODE,
            block_address=block_address,
            block_count=block_count,
            direction=READ_DIRECTION,
        )

    @classmethod
    def write10(cls, block_address: int, block_count: int) -> "UsbMassStorageBlockRequest":
        """Build a WRITE(10) request without guessing its direction byte."""
        return cls(
            opcode=WRITE10_OPCODE,
            block_address=block_address,
            block_count=block_count,
        )

    @property
    def transfer_bytes(self) -> int:
        """Return the observed block-count-to-byte-count conversion."""
        return self.block_count * BLOCK_SIZE

    def read_from(self, device: SdCardBlockDevice) -> bytes:
        """Read the requested sectors without adding USB transport framing."""
        if self.opcode != READ10_OPCODE:
            raise ValueError("read_from requires a READ(10) request")

        return b"".join(
            device.read_sector(self.block_address + offset)
            for offset in range(self.block_count)
        )

    def write_to(self, device: SdCardBlockDevice, payload: bytes) -> None:
        """Write the requested sectors without assigning a WRITE direction byte."""
        if self.opcode != WRITE10_OPCODE:
            raise ValueError("write_to requires a WRITE(10) request")

        if len(payload) != self.transfer_bytes:
            raise ValueError(
                f"WRITE(10) payload must be exactly {self.transfer_bytes} bytes"
            )

        for offset in range(self.block_count):
            start = offset * BLOCK_SIZE
            device.write_sector(
                self.block_address + offset,
                payload[start : start + BLOCK_SIZE],
            )
