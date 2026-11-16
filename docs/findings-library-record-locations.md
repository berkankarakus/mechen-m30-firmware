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

The record scan's location write is now traced one step further. In
`FUN_40094f2c`, the firmware calls the filesystem module entry
`0xbfc1640d` (module `0x11`) with operation `3`, passing the primary buffer
at `record + 0xa9` and the secondary buffer at `record + 0xf4` together.
The pointer is resolved from the literal pool, not inferred from the record
bytes. This establishes that both slices are produced by one filesystem
location ABI call; it still does not establish the internal layout of the
73-byte primary result. The repeatable check is
`tools/ghidra/run_library_record_probe.sh`.

The host codec preserves the unresolved regions and decodes the supported
secondary file key:

| Range | Host field | Status |
|---|---|---|
| `0xa9..0xf1` | `location_primary` | opaque bytes |
| `0xf2..0xf3` | `track_number` | little-endian numeric field; low byte participates in index sort |
| `0xf4..0xfb` | `location_secondary` | little-endian `cluster_no` + `dir_entry` file key; preserved as raw bytes too |
| `0xfc..0xff` | `previous_index`, `next_index` | decoded record-link candidates; M30 consumer semantics still need tracing |

The host `find_library_record_index()` helper now reproduces the reader-side
lookup boundary: it compares the eight-byte key only on active records
(`+0xa8 == 1`) and stops after the first 4,000 records. The real device image
round-trips samples at indices `0`, `1`, and `3999` through this lookup.

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

The same consumer probe passed against every available dated `music.ap`
member from 2022-09-14 through 2025-06-26. The eight-byte locator boundary and
the negative result for direct `+0xfc`/`+0xfe` reads therefore survive the
available version changes. This is stronger evidence for keeping the record
links lossless-but-opaque in the host emulator; it is not proof that an
indirect ROM helper never reads them.

## US212A SDK correspondence

A publicly mirrored US212A application-design manual documents the same
`plist_f_info_t` family used by the Actions playlist layer. Its 256-byte file
record describes a `cluster_no` followed by a `dir_entry`, both as 32-bit
filesystem location fields; its LIB section header also documents `file_index`,
`sort_index`, and `index_parent` as sector-based tables. The manual is
preserved outside Git at the persistent evidence root with SHA-256
`c6795e5aaef95af5b9bd16d469086e4f69603db87409791f039315705d7d0b05`:

<https://tchumim.com/assets/uploads/files/1622479367338-%D7%9E%D7%93%D7%A8%D7%99%D7%9A-%D7%9C%D7%AA%D7%9B%D7%95%D7%A0%D7%9F-%D7%90%D7%A4%D7%9C%D7%99%D7%A7%D7%A6%D7%99%D7%95%D7%AA-us212a.pdf>

Combined with the Ghidra consumer's eight-byte compare/copy boundary and the
real card's values, this is sufficient to expose the two little-endian words
as `cluster_no` and `dir_entry` in the host codec. The primary
`0xa9..0xf1` directory-layer blob and the `0xfc..0xff` links stay lossless
and unresolved.

An exhaustive 2025-06-26 `music.ap` decompile also found no direct
`record + 0xfc` or `record + 0xfe` access in these record consumers. This is
useful negative evidence, not proof that an indirect ROM helper never reads
the fields. The preserved decompile hash is
`bf393413491046318d5a985445dcf5eb8a3aeaccb952816143ffcc65d25f9af0`.
The eight-byte secondary locator is now modeled as a little-endian
`cluster_no`/`dir_entry` file-identity key at the boundary, while
`+0xa9..+0xf1` and `+0xfc..+0xff` remain lossless opaque fields until an
actual M30 card image and its directory contents are paired.

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

This is why no primary-location decoder or record rewriter has been added to
the host emulator. The current `decode_record()` contract is deliberately
loss-aware: it returns the decoded secondary key and the unresolved slices so
callers can preserve them without inventing semantics.

## Next evidence target

Use an actual M30-created `MUSIC.LIB` together with the corresponding MP3
directory tree. Compare `cluster_no`/`dir_entry` and the opaque primary slice
against file names, sizes, cluster boundaries, and the record links before
assigning further location meaning.
