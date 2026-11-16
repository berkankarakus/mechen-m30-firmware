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

## Reader-side consumer evidence

Ghidra 12.2 was also run against the extracted 2025-06-26 `music.ap` with
`tools/ghidra/run_library_record_consumer_probe.sh`. The relevant consumers
show the following behavior:

- `FUN_712d27f4` walks active records (`record + 0xa8 == 1`) and compares an
  incoming eight-byte file key with `record + 0xf4..0xfb`; a match returns the
  library record index.
- `FUN_71092500` performs the same lookup while loading the current record,
  then copies `+0xf4..0xfb`, `+0xa9..0xf1`, and `+0xa4..0xa7` into its output
  structure.
- `FUN_712d2a9c`, `FUN_71352810`, `FUN_713528ec`, `FUN_717d282c`, and the
  playback-side helper at `FUN_7181291c` use the same eight-byte locator
  boundary; they do not expose a byte order or filesystem structure for the
  primary blob.

An exhaustive 2025-06-26 `music.ap` decompile also found no direct
`record + 0xfc` or `record + 0xfe` access in these record consumers. This is
useful negative evidence, not proof that an indirect ROM helper never reads
the fields. The preserved decompile hash is
`bf393413491046318d5a985445dcf5eb8a3aeaccb952816143ffcc65d25f9af0`.
The eight-byte secondary locator can now be modeled as a file-identity key at
the boundary, while `+0xa9..+0xf1` and `+0xfc..+0xff` remain lossless opaque
fields until an actual M30 card image and its directory contents are paired.

The repository's `tools/library/mklib.py` fixture writes
`previous_index=i-1` and `next_index=i+1` while constructing synthetic records.
That makes the linked-record hypothesis useful for test data and explains why
the host codec exposes these two words, but it is local fixture convention,
not independent firmware evidence. In particular, the fixture's terminal
`next_index` behavior must not be promoted to a device sentinel rule.

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
