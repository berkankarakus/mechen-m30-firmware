"""Fail-closed model of the recovered usound MIPS16 callback envelope."""

from __future__ import annotations

from dataclasses import dataclass, field


CALLBACK_SELECTOR = 0x10
ADJACENT_SELECTOR = 0x0F
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
    """Arguments captured at the exception boundary, not a service result."""

    selector: int
    args: tuple[int, int, int, int]
    exception: Break0ExceptionContext | None = None


@dataclass
class UsoundCallbackBoundary:
    """Record known callback traps without executing the missing kernel ABI."""

    calls: list[Break0Call] = field(default_factory=list)

    def trap(
        self,
        selector: int,
        args: tuple[int, int, int, int],
        *,
        exception: Break0ExceptionContext | None = None,
    ) -> Break0Call:
        if len(args) != 4:
            raise ValueError("usound callback envelope requires four arguments")

        normalized = tuple(value & 0xFFFFFFFF for value in args)
        call = Break0Call(
            selector=selector & 0xFFFFFFFF,
            args=normalized,
            exception=exception,
        )
        self.calls.append(call)

        return call

    @property
    def known_callback_count(self) -> int:
        return sum(call.selector == CALLBACK_SELECTOR for call in self.calls)

    def service_effect(self, call: Break0Call) -> None:
        """Reject service execution until the fixed-ROM dispatcher is known."""

        if call.selector not in (CALLBACK_SELECTOR, ADJACENT_SELECTOR):
            raise ValueError(f"unknown usound selector: 0x{call.selector:x}")
        raise NotImplementedError("fixed-ROM callback service is unresolved")
