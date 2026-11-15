#!/usr/bin/env python3
"""Render the evidence-based M30 folder/list view on the host.

This is a deterministic visualizer, not an ATJ2127 boot. Its inputs are the
observed M30 list geometry and the browser's fixed 0x32-byte UTF-16 name slot.
It exposes the slot text and redraw decisions in JSON so a future QEMU host
shim can be compared against the same contract.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path

from m30_ui import Framebuffer, draw_text
from scroll_accel import NEXT, PREVIOUS, ScrollAccelerator
from tools.sim.listbox import (
    DIRECTORY_ROW_HEIGHT,
    DIRECTORY_SCROLL_PERIOD_MS,
    DIRECTORY_TEXT_HEIGHT,
    DIRECTORY_TEXT_WIDTH,
    DIRECTORY_TEXT_X,
    LIST_SLOT_COUNT,
    M30_DIRECTORY_STYLE,
    directory_slot_text,
    firmware_name_payload_bytes,
)


WIDTH, HEIGHT = 320, 240
LIST_TOP_Y = 12
FOLDER_ICON_X = 5
FOLDER_ICON_SIZE = 22
FOLDER_GLYPH_WIDTH_PX = M30_DIRECTORY_STYLE.glyph_width_px
SCROLL_GAP_CHARS = 2

BACKGROUND = (18, 19, 22)
HEADER_BACKGROUND = (12, 13, 15)
SELECTION_BACKGROUND = (76, 16, 21)
RED = (255, 24, 32)
WHITE = (235, 235, 235)
DIM = (102, 106, 110)


@dataclass(frozen=True)
class FolderRow:
    name: str
    selected: bool = False

    @property
    def slot_text(self) -> str:
        return directory_slot_text(self.name)

    @property
    def truncated(self) -> bool:
        return self.slot_text != self.name


def directory_text_width(text: str) -> int:
    return len(text) * FOLDER_GLYPH_WIDTH_PX


def directory_marquee_positions(
    text: str,
    offset_px: int,
    viewport_width: int = DIRECTORY_TEXT_WIDTH,
    *,
    gap_chars: int = SCROLL_GAP_CHARS,
) -> tuple[int, ...]:
    """Return relative pixel positions for the repeated directory name."""
    if viewport_width <= 0:
        raise ValueError("viewport_width must be positive")
    if gap_chars < 0:
        raise ValueError("gap_chars must be non-negative")
    width = directory_text_width(text)
    if not text or width <= viewport_width:
        return (0,) if text else ()
    cycle = width + gap_chars * FOLDER_GLYPH_WIDTH_PX
    normalized = offset_px % cycle
    positions: list[int] = []
    position = -normalized
    while position < viewport_width:
        if position + width > 0:
            positions.append(position)
        position += cycle
    return tuple(positions)


def draw_folder_icon(fb: Framebuffer, x: int, y: int, color: tuple[int, int, int]) -> None:
    """Draw a small deterministic folder placeholder for layout testing."""
    fb.rect(x + 1, y + 5, FOLDER_ICON_SIZE - 2, FOLDER_ICON_SIZE - 6, color)
    fb.rect(x + 4, y + 2, 9, 4, color)
    fb.rect(x, y + 7, FOLDER_ICON_SIZE, 2, color)


def draw_directory_text(
    fb: Framebuffer,
    text: str,
    x: int,
    y: int,
    viewport_width: int,
    color: tuple[int, int, int],
    *,
    offset_px: int,
) -> tuple[int, ...]:
    positions = directory_marquee_positions(text, offset_px, viewport_width)
    clip = (x, y, viewport_width, DIRECTORY_TEXT_HEIGHT)
    for relative_x in positions:
        draw_text(
            fb,
            text,
            x + relative_x,
            y,
            color,
            scale=1,
            clip=clip,
            cell_width=FOLDER_GLYPH_WIDTH_PX,
        )
    return positions


@dataclass
class FolderList:
    rows: tuple[FolderRow, ...]
    selected_index: int = 0
    scroll_offset_px: int = 0
    top_y: int = LIST_TOP_Y
    accelerator: ScrollAccelerator = field(default_factory=ScrollAccelerator, repr=False)

    def __post_init__(self) -> None:
        if not self.rows:
            raise ValueError("folder list must contain at least one row")
        if not 0 <= self.selected_index < len(self.rows):
            raise ValueError("selected_index is outside the folder list")
        if not 0 <= self.top_y < HEIGHT:
            raise ValueError("top_y must be inside the framebuffer")

    @property
    def first_visible_index(self) -> int:
        """Return the first row in the viewport while keeping selection visible."""
        max_start = max(0, len(self.rows) - LIST_SLOT_COUNT)
        selected_start = max(0, self.selected_index - (LIST_SLOT_COUNT - 1))
        return min(selected_start, max_start)

    def move_selection(self, delta: int) -> int:
        """Move the folder selection with the stock list-edge wrap behavior."""
        if not isinstance(delta, int):
            raise TypeError("selection delta must be an integer")
        self.selected_index = (self.selected_index + delta) % len(self.rows)
        return self.selected_index

    def move_event(self, direction: int, now_ms: int) -> dict[str, int | bool | None]:
        """Apply one accelerated folder-navigation event to the host model.

        The folder browser wraps at the list edges, matching the real
        browser/music handler executed by the p-code boundary matrix. Reuse
        the accelerator's one-step loop so a multi-step burst stops at the
        first wrap just as the recovered callback does.
        """
        if direction not in (NEXT, PREVIOUS):
            raise ValueError("direction must be NEXT or PREVIOUS")
        requested = self.accelerator.steps_for(direction, now_ms)
        before = self.selected_index
        after_one_based, consumed = ScrollAccelerator.move_selection(
            before + 1,
            len(self.rows),
            direction,
            requested,
        )
        after = after_one_based - 1
        self.selected_index = after
        wrapped = (direction == NEXT and after < before) or (
            direction == PREVIOUS and after > before
        )
        page_reload = consumed > 1
        return {
            "direction": direction,
            "now_ms": now_ms,
            "requested_steps": requested,
            "consumed_steps": consumed,
            "selected_index": after,
            "first_visible_index": self.first_visible_index,
            "wrapped": wrapped,
            "page_reload": page_reload,
            "mode": 4 if page_reload else None,
            "update": 2 if page_reload else None,
        }

    def marquee_offset_at(self, now_ms: int, *, start_ms: int = 0) -> int:
        """Return the pixel offset at a measured directory refresh tick.

        The reference listbox advances an active marquee once per
        ``DIRECTORY_SCROLL_PERIOD_MS``. Keep the host model deterministic by
        using integer ticks; ``scroll_offset_px`` is the offset at
        ``start_ms``.
        """
        if now_ms < 0 or start_ms < 0:
            raise ValueError("marquee times must be non-negative")
        if now_ms < start_ms:
            raise ValueError("now_ms must not precede start_ms")
        ticks = (now_ms - start_ms) // DIRECTORY_SCROLL_PERIOD_MS
        return self.scroll_offset_px + ticks

    def render_at(
        self,
        now_ms: int,
        *,
        start_ms: int = 0,
    ) -> tuple[Framebuffer, list[dict[str, object]]]:
        """Render a deterministic frame at a directory marquee timestamp."""
        offset_px = self.marquee_offset_at(now_ms, start_ms=start_ms)
        original_offset = self.scroll_offset_px
        self.scroll_offset_px = offset_px
        try:
            return self.render()
        finally:
            self.scroll_offset_px = original_offset

    def render(self) -> tuple[Framebuffer, list[dict[str, object]]]:
        fb = Framebuffer()
        fb.fill(BACKGROUND)
        fb.rect(0, 0, WIDTH, self.top_y, HEADER_BACKGROUND)
        draw_text(fb, "BROWSE", DIRECTORY_TEXT_X, 2, DIM, scale=1, cell_width=8)

        trace: list[dict[str, object]] = []
        first_visible = self.first_visible_index
        visible_rows = self.rows[first_visible:first_visible + LIST_SLOT_COUNT]
        for slot, row in enumerate(visible_rows):
            row_y = self.top_y + slot * DIRECTORY_ROW_HEIGHT
            if row_y >= HEIGHT:
                break
            row_index = first_visible + slot
            selected = row_index == self.selected_index
            if selected:
                fb.rect(0, row_y, WIDTH, DIRECTORY_ROW_HEIGHT, SELECTION_BACKGROUND)
            draw_folder_icon(fb, FOLDER_ICON_X, row_y + 4, RED if selected else DIM)
            slot_text = row.slot_text
            positions = draw_directory_text(
                fb,
                slot_text,
                DIRECTORY_TEXT_X,
                row_y + 6,
                DIRECTORY_TEXT_WIDTH,
                WHITE if selected else DIM,
                offset_px=self.scroll_offset_px if selected else 0,
            )
            marquee_active = selected and (
                self.scroll_offset_px > 0
                or directory_text_width(slot_text) > DIRECTORY_TEXT_WIDTH
            )
            trace.append({
                "slot": slot,
                "index": row_index,
                "name": row.name,
                "slot_text": slot_text,
                "truncated": row.truncated,
                "selected": selected,
                "x": DIRECTORY_TEXT_X,
                "y": row_y + 6,
                "width": DIRECTORY_TEXT_WIDTH,
                "height": DIRECTORY_TEXT_HEIGHT,
                "offset_px": self.scroll_offset_px if selected else 0,
                "positions": list(positions),
                "refresh_period_ms": DIRECTORY_SCROLL_PERIOD_MS,
                "background": "selection-red" if selected else "list-background",
                "restore_mode": (
                    "sdimage-tail"
                    if marquee_active
                    else "solid-selection-red" if selected else "solid-list-background"
                ),
            })
        return fb, trace

    def json(self) -> dict[str, object]:
        _, rows = self.render()
        return {
            "geometry": {
                "framebuffer": [WIDTH, HEIGHT],
                "top_y": self.top_y,
                "text_x": DIRECTORY_TEXT_X,
                "text_width": DIRECTORY_TEXT_WIDTH,
                "text_height": DIRECTORY_TEXT_HEIGHT,
                "row_height": DIRECTORY_ROW_HEIGHT,
                "slot_count": LIST_SLOT_COUNT,
                "name_slot_bytes": 50,
                "name_payload_bytes": firmware_name_payload_bytes(),
            },
            "selected_index": self.selected_index,
            "first_visible_index": self.first_visible_index,
            "scroll_offset_px": self.scroll_offset_px,
            "rows": rows,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True, help="PPM framebuffer output")
    parser.add_argument("--trace", type=Path, help="write folder layout trace as JSON")
    parser.add_argument("--selected", type=int, default=0)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("names", nargs="*", default=["Music", "Podcasts", "Long folder name"])
    args = parser.parse_args()
    view = FolderList(tuple(FolderRow(name) for name in args.names), args.selected, args.offset)
    frame, _ = view.render()
    frame.ppm(args.out)
    if args.trace:
        args.trace.write_text(json.dumps(view.json(), indent=2) + "\n")
    print(f"rendered {args.out}; {len(view.rows[:LIST_SLOT_COUNT])} rows; name payload {firmware_name_payload_bytes()} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
