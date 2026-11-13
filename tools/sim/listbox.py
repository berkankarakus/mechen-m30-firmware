"""M30 directory-list rendering contract.

The Actions US212A SDK source in the public ATJ2127 reference project shows
that directory and menu views share the listbox driver.  The M30 common.sty
directory item has a 205-pixel text region beginning at x=35, a 30-pixel row
height, and an 80 ms active-scroll refresh interval.  This model keeps those
values explicit so UI regressions can be tested without claiming to render
the LCD or reproduce the vendor font rasterizer.
"""

from __future__ import annotations

from dataclasses import dataclass


DIRECTORY_TEXT_X = 35
DIRECTORY_TEXT_WIDTH = 205
DIRECTORY_TEXT_HEIGHT = 16
DIRECTORY_ROW_HEIGHT = 30
DIRECTORY_HEAD_X = 5
DIRECTORY_SCROLL_PERIOD_MS = 80
NAME_BUFFER_BYTES = 52
SCROLL_GAP_CHARS = 2


@dataclass(frozen=True)
class DirectoryItemStyle:
    text_x: int = DIRECTORY_TEXT_X
    text_width: int = DIRECTORY_TEXT_WIDTH
    text_height: int = DIRECTORY_TEXT_HEIGHT
    row_height: int = DIRECTORY_ROW_HEIGHT
    head_x: int = DIRECTORY_HEAD_X
    scroll_period_ms: int = DIRECTORY_SCROLL_PERIOD_MS


M30_DIRECTORY_STYLE = DirectoryItemStyle()


def firmware_name_capacity_bytes() -> int:
    """Return the fixed per-entry name buffer from the Actions UI contract."""
    return NAME_BUFFER_BYTES


def needs_active_scroll(text_width: int, style: DirectoryItemStyle = M30_DIRECTORY_STYLE) -> bool:
    """Match the SDK's long-string decision for the active list item."""
    return text_width > style.text_width


def scroll_window(
    text: str,
    frame: int,
    viewport_chars: int,
    gap_chars: int = SCROLL_GAP_CHARS,
) -> str:
    """Return a deterministic character approximation of the SDK marquee.

    The real driver uses measured glyph widths and appends two spaces before
    wrapping.  The emulator contract uses character cells so the state and
    redraw behavior can be tested independently of the proprietary font.
    """
    if viewport_chars <= 0:
        raise ValueError("viewport_chars must be positive")
    if gap_chars < 0:
        raise ValueError("gap_chars must be non-negative")
    if len(text) <= viewport_chars:
        return text
    stream = text + (" " * gap_chars)
    start = frame % len(stream)
    doubled = stream + stream
    return doubled[start : start + viewport_chars]


def active_redraw_period_ms(style: DirectoryItemStyle = M30_DIRECTORY_STYLE) -> int:
    return style.scroll_period_ms

