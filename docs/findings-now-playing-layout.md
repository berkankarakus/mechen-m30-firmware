# Now-playing layout findings

The HTML prototype is now constrained by the resource layout instead of by a
generic 320x240 mockup.  The device's display is 320x240, and the current
music resource contains a 160-pixel boundary for the right-side information
area.  The metadata textbox width is approximately 129 pixels.

## Source-level path

The public US212A source maps the now-playing flow as follows:

1. `music_scene_playing()` obtains the album-art region from `ALBUM_ART_REGION`.
2. `play_scene_paint()` refreshes the artwork, track number, progress, EQ,
   shuffle, playback status, and ID3 information independently.
3. `play_scroll_init()` starts the title/artist/album state machine.
4. `play_scroll_deal()` passes `g_scroll_content[3]` to
   `ui_scroll_string_ext()`.
5. `ui_scroll_string_ext()` uses `ID3_SCROLL_TEXTBOX` and
   `ID3_MUSIC_PICBOX`; the horizontal pass is followed by a vertical pass and
   an idle delay.

The three content buffers are populated in this order:

```text
g_scroll_content[0] = title
g_scroll_content[1] = artist
g_scroll_content[2] = album
```

The firmware does not have a fourth dynamic metadata buffer in this path, so
`FILE` in the HTML is currently a design-only field.  Adding a live filename
line would require an application change, not just a bitmap resource edit.

## Resource controls

The read-only `tools/inspect_music_sty.py` parser reports the fixed control
groups and their offsets.  For the extracted community-compatible resource,
the relevant textbox records are 20 bytes each and are kept in-place so a
resource-only patch cannot resize the member.

Before changing a textbox record, the runtime use of that style ID must be
confirmed.  `ID3_SCROLL_TEXTBOX` is directly referenced by the scroll code;
the other textbox IDs are also used for album-art regions, lyrics, and browser
filename display.  They must not be repurposed globally.

The resource also contains the controls that the first host mockup had
previously drawn by hand.  The extracted `music.sty` records are:

```text
timebox[0]     x=70,  y=202, w=64, h=12
timebox[1]     right viewport embedded at x=235, y=202, w=64, h=12
progressbar[0] origin x=70, y=220
```

Resources `18..27` are the ten direct 8x12 digit glyphs, resource `5` is the
colon, and resource `36` is the slash.  Resource `17` is a 231x6 neutral
progress strip; resources `31` and `32` are one-pixel fill columns.  These
facts let the host preview reproduce the counter/progress geometry and native
small glyphs without inventing a font or placing the controls from the HTML
prototype.  The values and optional PicBox frame choices still come from an
explicit host state until the AP playback state machine is connected.

Bitmap inspection also assigns the four transport frames without changing the
resource member: PicBox 4 frames 0..3 are play, pause, next, and previous;
PicBox 1 frames 0..1 are shuffle-off and shuffle-on. The preview defaults to
the pause frame because its default state represents a currently playing
track. The five PicBox 0 top-row frames remain intentionally unresolved.

The same inspection separates the embedded EQ indicator from the playback
progress bar: PicBox 3 frame 0 is the blank 124x24 bitmap and frame 1 is the
visible `EQ:` bitmap at its recorded position. The bottom progress bar is a
different `progressbar[0]` record and is rendered from resources 17, 31, and
32. PicBoxes 5..8 are fixed metadata glyphs (album, artist, title, and track),
so the host trace reports those roles instead of calling them unresolved.

The extracted `new_m.fnt` is also an Actions sparse-index font: 1024 ten-byte
presence entries begin at `0x10`, glyph records begin at `0x2810`, and this
M30 member uses 61-byte records with a final advance-width byte.  ASCII glyph
lookup is now implemented read-only in `tools/emu/m30_font.py`; the preview
renders the metadata at the native bitmap scale so the recovered glyph shapes
fit the 129-pixel TextBox viewports.  Each fixed 16-pixel row is clipped to
the glyph's trailer advance before drawing; using the full row made narrow
glyphs (notably `I`) overlap their neighbours.  This is a host-rendering
correction only: `new_m.fnt` is not changed and no flash patch is proposed.
The raw ASCII and lowercase records are not a consistent display raster
(punctuation such as `.` can also place ink outside its advance), so the host
preview now uses a complete, deterministic 5x7-to-2x metadata rasterizer for
printable ASCII.  The raw reader remains available for provenance.

## SDK-versus-M30 warning

The public SDK also contains `case/resource/music/music.ui`, which is useful
for understanding the editor's scene model.  Its generated `music.sty` is not
byte-compatible with the extracted M30 resource: the SDK has a different
number of picbox/textbox records and different control coordinates.  The SDK
source therefore explains the control structures and call flow, but its raw
coordinates must not be copied into an M30 HEX.

The M30 resource is the source of truth for a patch.  A candidate must preserve
its existing control-group counts and member size, and every changed style
record must be tied to a runtime style ID used by the M30 `music.ap`.

## M30 binary cross-check

The community-compatible M30 `music.ap` was loaded into Ghidra using the
ATJ2127 bank table and decompiled into 819 functions.  The main refresh path
is `FUN_40154ddc` at virtual address `0x40154ddc`.  It confirms three fixed
screen bands before redrawing the controls:

```text
header:     x=0, y=0x00, w=0x140, h=0x1c
content:    x=0, y=0x1c, w=0x140, h=0x97
footer:     x=0, y=0xb3, w=0x140, h=0x3d
```

The same path uses `0x1004` for the album-art picture box and `0x2005` for a
dynamic text draw.  `FUN_40114f20` clears a 150x150 content area at
`(0, 0x1c)` before handing the artwork/data to the UI dispatcher.

The paint branch's control sequence is also useful for the host preview:
`0x1002` (artwork), `0x1003` (EQ), `0x1004` (transport), and `0x1005` through
`0x1008` (the four metadata glyphs) are emitted by `FUN_40154ddc`.  The
resource still contains PicBoxes 0 and 1, but this refresh function does not
select their controls; the now-playing preview therefore leaves that header
band empty, matching the supplied device screenshot instead of drawing the
icons merely because their bitmaps exist in `music.sty`.

The metadata glyphs are part of the stable row layout in the host model and
replace the literal label text at a common x alignment; the value viewports
remain the real `x=190` TextBoxes. The transport control is transient in the
host model: the firmware emits it from the `param_1 & 0x8` / `param_1 & 0x20`
refresh branches, so the stable playback preview keeps it hidden by default
and exposes it through `--show-controls`.

The first call-site candidate changed the `0x2005` literal in this paint path,
but the device-visible marquee is emitted by the shared scroll renderer, not
by that call alone.  Ghidra identifies the actual draw path as:

```text
FUN_40d54f2c
  0x40d55078: li v0, 0x2005
```

This is the call that consumes the active title/artist/album scroll item.  The
new candidate changes this renderer call to `0x2001`, while leaving the
unrelated `FUN_40154ddc` literal unchanged.

The call-site audit found an important boundary: `0x2005` is also referenced by
`FUN_40d54f2c`, the shared scroll renderer.  Therefore changing the shared
`0x2005` textbox record is not screen-local.  The current isolated candidate
leaves that record unchanged and patches the immediate in `FUN_40d54f2c`:

```text
virtual: 0x40d55078
file:    music.ap 0x27878
before:  04 f0 05 6a   (li v0, 0x2005)
after:   04 f0 01 6a   (li v0, 0x2001)
```

`0x2001` is already the existing right-panel textbox geometry.  This keeps the
other `0x2005` caller on its original style while redirecting the now-playing
draw to the verified right-panel record.

This explains why the public SDK coordinates cannot be copied directly and
why the first firmware UI patch must target the M30-specific style record
`0x2005`, while leaving the scroll, artwork decode, and playback code intact.

## Prototype status

[`now-playing-ui.html`](now-playing-ui.html) uses the 160-pixel panel boundary,
129-pixel text width, red accent, and compact spacing.  It intentionally keeps
the `FILE` line as a visual placeholder until the application path is mapped.

The current firmware step is therefore the isolated scroll-renderer candidate.
It changes one byte in `music.ap` and carries the already-tested now-playing
`music.sty` artwork/icon resources; it does not modify `mengine.ap`, browser,
indexer, or settings code.  The earlier paint-path-only candidate did not
affect the visible marquee and is retained as an offline comparison only.
