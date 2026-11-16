"""Fail-closed model of the recovered usound MIPS16 callback envelope."""

from __future__ import annotations

from dataclasses import dataclass, field


CALLBACK_SELECTOR = 0x10
ADJACENT_SELECTOR = 0x0F


@dataclass(frozen=True)
class Break0Call:
    """Arguments captured at the exception boundary, not a service result."""

    selector: int
    args: tuple[int, int, int, int]


@dataclass
class UsoundCallbackBoundary:
    """Record known callback traps without executing the missing kernel ABI."""

    calls: list[Break0Call] = field(default_factory=list)

    def trap(self, selector: int, args: tuple[int, int, int, int]) -> Break0Call:
        if len(args) != 4:
            raise ValueError("usound callback envelope requires four arguments")
        normalized = tuple(value & 0xFFFFFFFF for value in args)
        call = Break0Call(selector & 0xFFFFFFFF, normalized)
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
