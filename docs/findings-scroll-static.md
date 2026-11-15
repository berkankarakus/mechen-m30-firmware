# Folder-name marquee: static binary findings

This is an offline analysis of `drv_ui.drv` from stock V1.101.10 and
community V1.292.00. The files are byte-identical (SHA-256
`011f4e6a50738026ac641370f493c5df2e59adc435871d8a213e717604d2576a`). It is
not a device or real-LCD test.

The same SHA-256 and the same 24-entry bank layout were also observed in the
archived `v1.101.11`, `v1.101.12`, `v5`, and `first-pass-verify` images. That
means a UI-only fix targeting this driver would not distinguish those
firmware generations; the behavior difference seen on-device must come from
the caller/resource path or from another image component.

## What is confirmed

### Name preparation: `FUN_30009070`

- The text pointer is read from the list descriptor.
- The routine scans at most `0x66` bytes (102 bytes) for a terminator.
- On a terminator it writes two spaces and a second terminator before the
  marquee wraps.
- This scan happens after the browser has populated its fixed 50-byte slot.
  Therefore a name lost during list-item copying cannot be recovered by the
  marquee routine.

The relevant instructions are at flat addresses `0x300090e0`–`0x3000914e`:
the `sltiu ... 102` bound, the terminator test, and the three writes that add
the two-space gap.

The maintained flat-map decompile confirms the preparation details from the
real `drv_ui.drv`: in UTF-16 mode the routine walks at most `0x66` bytes in
two-byte units, appends two spaces and a UTF-16 terminator, then skips a
leading `FF FE` marker before handing the buffer to the scroll state. Non-
UTF-16 input is routed through a separate resource/string helper instead of
being widened here.

### Marquee state update: `FUN_30009674`

- The routine receives a scroll descriptor and reads the current text/layout
  state through indirect helper pointers.
- It updates 16-bit layout/state fields in its stack descriptor, including the
  fields later used as the current horizontal position and remaining width.
- The update path uses measured geometry and does not advance by complete
  characters. The existing simulator's old character-step model was therefore
  misleading; it has now been supplemented with a pixel-offset model.
- Several draw/measure/clear operations are indirect calls. The function does
  not contain an obvious full-viewport fill inline, so the red rectangle is
  most likely in one of those helpers or in the selected-item background path.

The new Ghidra flat-map decompile adds three useful constraints:

- the initial resident system-operation call receives `(buffer, 0, 0x7c, 1)`;
  this is an operation envelope, not by itself proof of a solid-color LCD
  fill;
- the `0x7c` value is also stored in the temporary region descriptor passed to
  the two later text/background helpers, so it is the bounded region width
  used by the marquee path rather than a palette value;
- the routine consumes two 8-byte string records per pass (`param_3` selects
  the first record and the next record is selected from the state byte),
  measures each record, and then draws it through separate indirect helpers;
- when measured width is smaller than the available width, the code adjusts
  the x origin by the remaining width before drawing. This is the concrete
  source-level reason a stale right-edge rectangle can remain if the helper's
  background restore is incomplete.

The public reference implementation now gives a concrete comparison for that
indirect path: its `clear_remain_pixel_sdimage()` restores the remaining
rectangle from the saved selected-row bitmap before issuing LCD DMA. This is
stronger than the earlier generic “clear helper” hypothesis, but the M30
function-pointer table still has to be matched to that API before patching.

The helper addresses are runtime-initialized resident pointers, not file
literals, so their exact LCD/resource semantics are still unresolved. The
resident helper at `0xbfc09e34` is now also decompiled: it conditionally
forwards a three-argument call to the raw target stored at `0xbfc09e70`
(`0x164490a1`, candidate A17 + `0xa1`) only for the relevant display-mode
range and state. A17 is absent from the extracted M30 driver, so this target
must remain an unresolved external/provider entry; the forwarder is not the
clear implementation. The host test now explicitly records that absence. The
B3 runtime probe now also binds the literal envelope: the initial system
operation is the resident wrapper `0xbfc09c01`, the three-argument background
operation goes through the conditional resident forwarder `0xbfc09e35`, and
the text-side SD-image renderer is the B16-qualified pointer `0x26409401`.
These are exact pointer values, not yet names for the underlying LCD/resource
operation. The resident probe asserts the forwarder shape. The flat loader used for this result is
`tools/ghidra/FlatLoad.java`; the complete temporary decompile was generated
from the stock/community-identical `analysis/community/fw/drv_ui.drv`
without modifying it.

### Text alignment: `FUN_30008600`

The existing static finding remains: for multi-line centered text the routine
computes the x-coordinate from the pre-line-break `true_length`, then calls the
word/line splitter without recomputing x. This explains why a first line can
look left-aligned while a later line is centered. It is a separate issue from
the folder-name truncation.

## Current conclusion

The lowest-risk fix is not to change the four `50 -> 52` length immediates.
The browser's shared buffer is still only statically proven to be 50-byte
slots, and enlarging the lengths without moving the buffer can overwrite the
next item. The next binary investigation must resolve the indirect helpers
used by `FUN_30009674`, especially the clear/background operation, and then
find whether a larger name can be rendered directly from the filesystem
without using the truncated slot.

### New static lead: 64-byte slots

The bank map gives a stronger layout clue, and also rules out the first naive
expansion: the caller passes `0x40cd4c00` as the list buffer and
`0x40cd4d90` as `path_info`. Eight 50-byte slots end exactly at that second
address. Although eight 64-byte slots fit the surrounding `0x200` page, they
would overwrite `path_info`. The controlled experiment is documented in
[`findings-scroll-reference.md`](findings-scroll-reference.md); it remains
outside the safe candidate and is now explicitly marked unsafe.

## Next investigation

The former “map the indirect runtime pointers” step is now covered by the B3
candidate probes and the browser AP name probe. The exact browser callback
entry points and their copy limits are reproducible with:

```sh
bash tools/ghidra/run_browser_name_probe.sh analysis/community/fw/browser.ap
```

The remaining high-value work is:

1. Resolve the provider behind the conditional resident forwarder
   (`0x164490a1`) and the B2/B16 far-call candidates used by the descriptor
   envelope; only that mapping can distinguish a solid-color clear from an
   image-backed restore.
2. Trace the directory-mode callback separately from the library-mode callback
   at runtime, including the filesystem name format returned by kernel op 2.
3. Resolve ownership of the list buffer and adjacent `path_info`; only then
   consider a binary patch. Any candidate must show that adjacent list entries
   and listbox state remain intact.

## Driver bank layout recovered

The `yqhx` header is not just a signature.  For `drv_ui.drv`, header words at
`0x48`, `0x4c`, and `0x50` point to the file starts of the A/B/C overlay
groups: `0x1600`, `0x6600`, and `0x10600`.  The tables at `0x80`, `0x100`, and
`0x180` contain pairs of byte-order 16-bit `(start16, end16)` offsets
relative to those group starts.  The non-zero entries describe ten A banks of
`0x400` bytes, ten B banks of `0x800` bytes, and four C banks of `0x400`
bytes.

There is one useful boundary detail: `FUN_30009674` begins at file offset
`0x9674`, while the fourth B window starts at `0x9680`.  The 12-byte lead-in
is consistent with a bank entry/prologue kept immediately before the payload
window; it is why a simple “function offset must be inside the table range”
check would incorrectly discard the real marquee routine.  The public SDK bank
formula maps B3 to `0x260e5000`; remapping the B3 bytes at that address gives
the marquee entry at `0x260e4ff4`, which decompiles cleanly and retains the
`0x7c` clear call and the two-record text path. This is strong static
confirmation, not a physical-device trace. See
[`findings-kernel-loader.md`](findings-kernel-loader.md).

This explains why the earlier flat map was useful for decompilation but not a
runtime address map: the `0x30000000 + file_offset` names are analysis
coordinates.  The bank payloads are overlaid at their linker-selected
addresses after the driver loader has installed the resident image.  The
structure is now decoded by [`tools/inspect_drv.py`](../tools/inspect_drv.py),
which deliberately reports file ranges first and only prints the public SDK
runtime comparison addresses when `--runtime-base` is requested.

For the public ATJ2127 linker layout, the bases are A
`0x16024c00`, B `0x26025000`, and C `0x36021a00`, with `0x40000` spacing per
bank index. The M30 `kernel.drv` loader and the public linker description now
agree on the driver format and bank geometry, so these are high-confidence
M30 candidates. They are still not a direct hardware observation; the
indirect bank-window lookup must be resolved before using an exact callable
address in a patch.
