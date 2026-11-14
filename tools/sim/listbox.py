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
DIRECTORY_GLYPH_WIDTH_PX = 8
# The SDK declares 52 bytes, but the M30 browser binary initializes each
# directory-list slot with 0x32 (50) bytes.  This is the limit that matters
# before the marquee renderer gets a chance to scroll the name.
NAME_BUFFER_BYTES = 50
LIST_SLOT_COUNT = 8  # title slot + seven visible directory rows
INFERRED_LIST_BUFFER_BYTES = 0x200
EXPERIMENTAL_NAME_BUFFER_BYTES = 64
LIST_BUFFER_ADDR = 0x40CD4C00
PATH_INFO_ADDR = 0x40CD4D90
MAX_NON_OVERLAPPING_NAME_BYTES = (PATH_INFO_ADDR - LIST_BUFFER_ADDR) // LIST_SLOT_COUNT
SCROLL_GAP_CHARS = 2


@dataclass(frozen=True)
class DirectoryItemStyle:
    text_x: int = DIRECTORY_TEXT_X
    text_width: int = DIRECTORY_TEXT_WIDTH
    text_height: int = DIRECTORY_TEXT_HEIGHT
    row_height: int = DIRECTORY_ROW_HEIGHT
    head_x: int = DIRECTORY_HEAD_X
    scroll_period_ms: int = DIRECTORY_SCROLL_PERIOD_MS
    glyph_width_px: int = DIRECTORY_GLYPH_WIDTH_PX


M30_DIRECTORY_STYLE = DirectoryItemStyle()


@dataclass(frozen=True)
class MarqueeFrame:
    """Deterministic state for one list-row marquee redraw.

    The vendor font is unavailable, so this model does not rasterize glyphs.
    It does preserve the important renderer contract: one-pixel offsets and
    image-backed restoration of the remaining edge region.
    """

    offset_px: int
    viewport_width_px: int
    clear_width_px: int
    background: str
    visible_text: str
    restore_mode: str = "sdimage-tail"


def marquee_frame(
    text: str,
    offset_px: int,
    viewport_width_px: int = DIRECTORY_TEXT_WIDTH,
    *,
    gap_chars: int = SCROLL_GAP_CHARS,
    style: DirectoryItemStyle = M30_DIRECTORY_STYLE,
    background: str = "selection-red",
) -> MarqueeFrame:
    """Model one pixel-positioned marquee frame and redraw region."""
    if viewport_width_px <= 0:
        raise ValueError("viewport_width_px must be positive")
    if style.glyph_width_px <= 0:
        raise ValueError("glyph_width_px must be positive")
    if gap_chars < 0:
        raise ValueError("gap_chars must be non-negative")
    if not text:
        return MarqueeFrame(0, viewport_width_px, viewport_width_px, background, "", "solid")

    stream = text + (" " * gap_chars)
    stream_width = len(stream) * style.glyph_width_px
    normalized = offset_px % stream_width
    first_cell = normalized // style.glyph_width_px
    cells = (stream + stream)[first_cell : first_cell + (viewport_width_px // style.glyph_width_px) + 2]
    return MarqueeFrame(
        offset_px=normalized,
        viewport_width_px=viewport_width_px,
        # The reference driver's clear_remain_pixel_sdimage() restores the
        # remaining edge, normally one pixel, from the selected-row bitmap.
        clear_width_px=1,
        background=background,
        visible_text=cells,
        restore_mode="sdimage-tail",
    )


def firmware_name_capacity_bytes() -> int:
    """Return the fixed per-entry name buffer used by the M30 binary."""
    return NAME_BUFFER_BYTES


def experimental_name_layout() -> tuple[int, int]:
    """Return the opt-in slot size and total page use for the 64-byte test.

    The browser bank reserves the 0x200-byte page immediately before its
    0x40cd4e00 code bank for the directory list.  The caller also passes
    path_info at 0x40cd4d90, so 64 bytes * 8 overlaps that structure.  This
    function describes the deliberately unsafe analysis layout; it is not a
    production candidate.
    """
    used = LIST_SLOT_COUNT * EXPERIMENTAL_NAME_BUFFER_BYTES
    return EXPERIMENTAL_NAME_BUFFER_BYTES, used


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

