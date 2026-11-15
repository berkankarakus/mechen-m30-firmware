# Folder marquee: reference-source match and 64-byte experiment

This note combines the public US212A/ATJ2127 UI-driver source with the M30
V1.101.10 / community V1.292.00 static binaries. It is not a device or full
ATJ2127-QEMU result.

The public reference snapshot used for comparison is
[Suber/PD196_ATJ2127](https://github.com/Suber/PD196_ATJ2127), commit
`b964feb76a7890a0ee32db188689da3254b724f9`. It is used only as a source/API
reference; its generated resources and coordinates are not copied into M30.

The accompanying public US212A design manual also separates the relevant UI
operations: string scrolling, string measurement, line splitting, picture
display, and reading a picture region back into a buffer are distinct driver
interfaces. Its graphics section likewise distinguishes solid-color fills from
image-backed fills. This supports the existing interpretation of the M30 B3
indirect calls: a `put_string_line_sdimage`-shaped call can be the text draw
side of the restore path, but it is not by itself proof that the background
provider is a solid fill. The manual is a generic API reference, not a M30
binary mapping: [US212A UI-driver design manual](https://tchumim.com/assets/uploads/files/1622479367338-%D7%9E%D7%93%D7%A8%D7%99%D7%9A-%D7%9C%D7%AA%D7%9B%D7%A0%D7%95%D7%9F-%D7%90%D7%A4%D7%9C%D7%99%D7%A7%D7%A6%D7%99%D7%95%D7%AA-us212a.pdf).

## What the reference source explains

The active directory item in the M30 `common.sty` listbox is not a plain
colour fill:

- `data_x=35`, `data_width=205`, `data_height=16`, row height `30`;
- active background mode is `SPIC` (`item.attrib` bits 10-11 = `1`);
- active long-string mode is `SCROLL` (`str_attrib` bits 4-5 = `1`);
- active background resource is the 310x29 selection bitmap (resource 80 in
  the extracted `common.sty`), currently red in the safe UI candidate.

The reference `show_list_item()` first draws that selected bitmap. When the
name needs scrolling, it calls `load_bgpic_sd()` and changes the text path to
`CHAR_FILL_SDIMAGE`. The marquee then restores the background from the image
while drawing characters. The source's `clear_remain_pixel_sdimage()` clears
only the remaining edge region requested by the marquee. This makes the red
rectangle a normal selected-row background, not evidence that the palette is
wrong; the missing-text symptom is a separate buffer/rendering problem.

The source implementation makes the restore boundary more precise:

- `show_list_item()` calls `u_show_pic()` for the active-row bitmap;
- when the text needs scrolling, it calls `load_bgpic_sd()` with the same
  resource ID and switches to `CHAR_FILL_SDIMAGE`;
- `hori_scroll()` calls `clear_remain_pixel_sdimage()` for the one-pixel or
  remaining tail region;
- `clear_remain_pixel_sdimage()` reads the corresponding rectangle from the
  saved background image and sends only that rectangle through the LCD DMA
  path.

Therefore a red strip appearing behind a moving folder name is exactly the
kind of symptom produced when the selected-row background was drawn but the
image-backed tail restore is skipped, clipped, or given the wrong x/y origin.
The M30 binary still needs a direct pointer/API match before this becomes a
flashable fix.

The host contract in `tools/sim/listbox.py` now models this distinction: the
initial empty row may clear the full viewport, while an active marquee frame
records a one-pixel `sdimage-tail` restore. This is a rendering model update,
not a firmware patch.

## M30-specific truncation point

`browser.ap` function `FUN_48754574` contains four `li v0, 50` literals. They
define both the directory slot stride and the length passed onward to the
name-reading path. The browser and music applications each contain the same
`0x48754400` bank.

The caller supplies `0x40cd4c00` as the list buffer and `0x40cd4d90` as the
`path_info` argument. The code bank begins at `0x40cd4e00` and is only
`0x600` bytes, leaving a preceding `0x200`-byte page for this mixed data.
The important boundary is therefore not just the page end: eight 50-byte
slots end exactly at `0x40cd4d90` (`8 * 50 = 0x190`).

An initial 50 -> 64 experiment was generated for static inspection, but it
would overwrite `path_info` because `8 * 64 = 0x200`. It is unsafe and must
not be flashed. The same overlap means that a simple 50 -> 52 change is not
safe either; a real patch must relocate `path_info` (and prove every user of
that structure) or render the original name without this shared slot.

## Safety status

The experiment is deliberately kept opt-in in
`tools/patch_ui_name_capacity.py`. It is not included in the current safe HEX
and must not be flashed until the following checks pass:

1. repack/decrypt round trip and member-size/checksum verification;
2. path-info overlap check for title + seven rows;
3. a real-bank harness or QEMU memory test that writes adjacent slots and
   confirms listbox state is unchanged;
4. a physical test with short names, long ASCII names, UTF-16 names, folder
   entry/exit, and rapid selection movement.

The expected improvement of a future safe solution is specifically the
missing tail of long folder names. It does not change the red selection
bitmap or the underlying pixel-marquee routine, so any remaining red/black
residue after the name must be investigated separately in the `SDIMAGE`
redraw path.
