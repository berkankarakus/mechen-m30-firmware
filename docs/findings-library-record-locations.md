# MUSIC.LIB record location bytes

This note separates the M30 record layout recovered from the firmware from
the structurally similar public comparison file.

## What the M30 index builder actually consumes

`tools/library/index.c` reads each 256-byte record during `extract()` and
uses these fields for index construction:

- title: `0x00..0x3f`
- album: `0x58..0x87`
- artist: `0x40..0x57`
- genre: `0x88..0x9f`
- numeric track byte: `0xf2` (the low byte is copied into the sort key)

The builder converts the four text fields into scratch keys, carries the
track byte through the sort key, and writes only derived scratch tables and
nodes to the index tail. It does not assign a filesystem or path meaning to
the record location slices. Reading a 256-byte window is not evidence that
every byte in that window is interpreted.

The decompiled `extract()` makes this boundary explicit. For section zero it
loads records in batches, calls `CONVERT()` only for the four text ranges, and
appends `rec[0xf2]` plus a zero pad to the later section keys. For later
sections it reads only those scratch keys, the previous-section rank, and the
group scratch tables. The temporary key layout is documented in the source as
`name[W] | track u8 | pad | rank u16 | group1 u16 | group2 u16 | song u16`;
none of the record-tail location bytes are copied into it. The `0xa8`
`always_one` byte is likewise not consumed by this pass.

The host codec therefore exposes, but does not decode, these regions:

| Range | Host field | Status |
|---|---|---|
| `0xa9..0xf1` | `location_primary` | opaque bytes |
| `0xf2..0xf3` | `track_number` | little-endian numeric field; low byte participates in index sort |
| `0xf4..0xfb` | `location_secondary` | opaque bytes |
| `0xfc..0xff` | `previous_index`, `next_index` | decoded record-link candidates; M30 consumer semantics still need tracing |

Changing an opaque location field while rebuilding the index is not currently
justified by the decompile. A future editor must preserve those bytes unless
a separate filesystem read/write trace proves their format.

This is stronger negative evidence than a missing symbol reference: the
indexer has a bounded record reader and an explicit scratch-key construction,
yet the location slices never enter either path. Any location interpretation
must therefore come from a different firmware consumer or from controlled
M30-generated card images, not from the index builder itself.

## Why the public comparison file is not enough

The public `MUSIC.LIB` comparison file matches the broad header, section, and
node geometry, but it is not a valid M30 record-tail fixture. In its first
record, the visible `MP3` marker occurs at a different record offset and the
bytes at the M30 codec's `0xf2` position are not an ASCII track field. It can
corroborate the shared index family, not the M30 record-location layout.

This is why no location decoder or record rewriter has been added to the host
emulator. The current `decode_record()` contract is deliberately loss-aware:
it returns the opaque slices so callers can preserve them without inventing
semantics.

## Next evidence target

Use an actual M30-created `MUSIC.LIB` together with the corresponding MP3
directory tree. Compare the opaque slices against file names, sizes, cluster
boundaries, and the record links before assigning any location meaning.
