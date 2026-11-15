"""Evidence-backed, deliberately narrow USB Audio host-side contract.

This is not a firmware or USB-controller emulator. It records only values
found in ``usound.drv`` and validates packet framing without inventing the
unresolved PCM ring/driver ABI.
"""

from __future__ import annotations

from dataclasses import dataclass


OBSERVED_CONTROL_REQUESTS = frozenset((0x21, 0x22))


@dataclass(frozen=True)
class UsbAudioContract:
    usb_bcd: int = 0x0100
    vendor_id: int = 0x10D6
    product_id: int = 0xDD00
    channels: int = 2
    sample_width_bits: int = 16
    sample_rate_hz: int = 48_000
    iso_out_endpoint: int = 0x01
    packet_bytes: int = 200
    hid_in_endpoint: int = 0x82

    @property
    def frame_bytes(self) -> int:
        return self.channels * (self.sample_width_bits // 8)

    @property
    def frames_per_packet(self) -> int:
        if self.packet_bytes % self.frame_bytes:
            raise ValueError("descriptor packet is not frame-aligned")
        return self.packet_bytes // self.frame_bytes

    def accepts_sample_rate(self, rate_hz: int) -> bool:
        """The descriptor advertises one discrete rate, not a range."""

        return rate_hz == self.sample_rate_hz

    def validate_packet(self, payload: bytes) -> int:
        """Return frame count for one exact-size isochronous OUT packet."""

        if len(payload) != self.packet_bytes:
            raise ValueError(
                f"expected {self.packet_bytes} bytes, received {len(payload)}"
            )
        return len(payload) // self.frame_bytes

    @staticmethod
    def control_request_is_observed(request: int) -> bool:
        """Report only request codes observed in the decompiled driver."""

        return request in OBSERVED_CONTROL_REQUESTS
