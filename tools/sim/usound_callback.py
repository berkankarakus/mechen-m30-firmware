"""Fail-closed model of observed MIPS16 break-0 module-call envelopes."""

from __future__ import annotations

from dataclasses import dataclass, field


LIBC_MODULE_ID = 0x10
KERNEL_MODULE_ID = 0x0F
UDISK_MODULE_ID = 0x01
OBSERVED_MODULE_IDS = frozenset({UDISK_MODULE_ID, KERNEL_MODULE_ID, LIBC_MODULE_ID})
EXCEPTION_EPC_SAVE_ADDRESS = 0x00013DD8
EXCEPTION_RA_SAVE_ADDRESS = 0x00013DDC
EXCEPTION_HANDLER_TARGET = 0xBFC06D6C


@dataclass(frozen=True)
class Break0ExceptionContext:
    """Optional register values supplied for an observed MIPS break exception."""

    exception_code: int
    epc: int
    bad_vaddr: int
    status: int
    ra: int | None = None

    def __post_init__(self) -> None:
        if self.exception_code != 9:
            raise ValueError("MIPS break 0 must report exception code 9")

        object.__setattr__(self, "exception_code", self.exception_code & 0xFFFFFFFF)
        object.__setattr__(self, "epc", self.epc & 0xFFFFFFFF)
        object.__setattr__(self, "bad_vaddr", self.bad_vaddr & 0xFFFFFFFF)
        object.__setattr__(self, "status", self.status & 0xFFFFFFFF)

        if self.ra is not None:
            object.__setattr__(self, "ra", self.ra & 0xFFFFFFFF)

    def handoff_trace(self) -> dict[str, object] | None:
        """Describe only the proven pre-handler stores when RA was supplied."""

        if self.ra is None:
            return None

        return {
            "handler_target": EXCEPTION_HANDLER_TARGET,
            "stores": [
                {"address": EXCEPTION_EPC_SAVE_ADDRESS, "value": self.epc},
                {"address": EXCEPTION_RA_SAVE_ADDRESS, "value": self.ra},
            ],
            "provenance": (
                "derived from ker_xsys.bin; register values caller-provided; "
                "vector path unverified"
            ),
        }


@dataclass(frozen=True)
class Break0Call:
    """Module ID and arguments captured at break 0, not a service result."""

    module_id: int
    args: tuple[int, int, int, int]
    exception: Break0ExceptionContext | None = None


@dataclass
class FirmwareBreak0Boundary:
    """Record break-0 module calls without executing the missing ROM ABI."""

    calls: list[Break0Call] = field(default_factory=list)

    def trap(
        self,
        module_id: int,
        args: tuple[int, int, int, int],
        *,
        exception: Break0ExceptionContext | None = None,
    ) -> Break0Call:
        if len(args) != 4:
            raise ValueError("firmware module-call envelope requires four arguments")

        normalized = tuple(value & 0xFFFFFFFF for value in args)
        call = Break0Call(
            module_id=module_id & 0xFFFFFFFF,
            args=normalized,
            exception=exception,
        )
        self.calls.append(call)

        return call

    @property
    def libc_module_call_count(self) -> int:
        return sum(call.module_id == LIBC_MODULE_ID for call in self.calls)

    def service_effect(self, call: Break0Call) -> None:
        """Reject service execution until the fixed-ROM dispatcher is known."""

        if call.module_id not in OBSERVED_MODULE_IDS:
            raise ValueError(f"unknown firmware module: 0x{call.module_id:x}")

        raise NotImplementedError(
            f"fixed-ROM service effect for module 0x{call.module_id:x} is unresolved"
        )


UsoundCallbackBoundary = FirmwareBreak0Boundary
