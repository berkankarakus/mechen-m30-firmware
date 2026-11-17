# Device SD library evidence

This note records the three files supplied from an M30 SD card. The binary
files remain outside Git under the persistent evidence root; this repository
stores only provenance, hashes, and read-only interpretation results.

## Captured files

| File | Bytes | SHA-256 | Safe interpretation |
|---|---:|---|---|
| `MUSIC.LIB` | 2,625,536 | `e386db27a9f47641e8755e5a58a903e6e66f83afe2be84c97d5d7e59de0f3c88` | A 4,000-record, 512-byte-sector library image |
| `M3U.LIB` | 1,550,848 | `ad4deb5b599eb97309e49a1d907cab445e3785d04f0ee103e6126f8ab0703a01` | `M3U` header, zero entry count, stale MP3 data after header |
| `ALBUM.PIC` | 128,000 | `65bad6f0a143f3990f1d0e958699513159dc3b06f7bcec0452ee318217c8e671` | `ALBUM` container, 250 sectors, observed 150x150 RGB565-sized payload and zero padding |

The source files were copied to the persistent evidence root before the SD
card was ejected. A future session can reproduce the checks with:

```sh
shasum -a 256 \
  <persistent-evidence-root>/device-sd/ALBUM.PIC \
  <persistent-evidence-root>/device-sd/M3U.LIB \
  <persistent-evidence-root>/device-sd/MUSIC.LIB
```

## Mounted-volume revalidation

On 2026-11-16 the same three files were read directly from the mounted
`/Volumes/MECHEN M30` volume, without writing to the card. Their sizes and
SHA-256 values matched the captured evidence exactly. The read-only probes
also reproduced the library geometry, the refined order comparison, and the
`ALBUM.PIC` container boundary. This confirms that the attached volume is the
same evidence set, not a new or partially rebuilt library.

The M3U header probe additionally observed `u16@0x08 = 0`,
`u16@0x0a = 1`, `ALLFILE` at `0x10`, and `55 aa` at `0x1fe..0x1ff`.
The data after the header is stale MP3 content, not an example of playlist
records.

```text
MUSIC.LIB: 2625536 bytes, e386db27a9f47641e8755e5a58a903e6e66f83afe2be84c97d5d7e59de0f3c88
M3U.LIB:   1550848 bytes, ad4deb5b599eb97309e49a1d907cab445e3785d04f0ee103e6126f8ab0703a01
ALBUM.PIC: 128000 bytes,   65bad6f0a143f3990f1d0e958699513159dc3b06f7bcec0452ee318217c8e671
```

The bounded M3U check is reproducible with:

```sh
PYTHONPATH=tools/emu \
  python3 tools/emu/m3u_library_evidence_probe.py \
  <persistent-evidence-root>/device-sd/M3U.LIB \
  ad4deb5b599eb97309e49a1d907cab445e3785d04f0ee103e6126f8ab0703a01
```

### Read-only mounted-volume metadata

On the same read-only inspection, the mounted volume reported these
filesystem metadata values. The inode values belong to this mount and are
useful for detecting a replacement or re-enumeration during a session; they
are not treated as M30 record identifiers. The content hash remains the
authoritative identity used by the probes.

| File | Inode | Mode | Bytes | Blocks | Modification time |
|---|---:|---|---:|---:|---|
| `MUSIC.LIB` | `1768` | `-rwx------` | `2,625,536` | `5,376` | `2014-12-31 23:00:02` |
| `M3U.LIB` | `11,140` | `-rwx------` | `1,550,848` | `3,072` | `2014-12-31 23:10:48` |
| `ALBUM.PIC` | `11,124` | `-rwx------` | `128,000` | `256` | `2014-12-31 23:11:06` |

## MUSIC.LIB geometry and indexes

`tools/emu/musiclib_evidence_probe.py` reads the image through
`SdCardBlockDevice`, checks the supplied SHA-256, parses the `0x200` header,
and validates every non-empty section index through
`interpret_library_section_index()`.

Observed output:

```text
MUSIC.LIB EVIDENCE PASS bytes=2625536 records=4000 record_area_sectors=2000 sha256=e386db27a9f47641e8755e5a58a903e6e66f83afe2be84c97d5d7e59de0f3c88
location_key_samples=({'index': 0, 'cluster_no': 1265055, 'dir_entry': 0}, {'index': 1, 'cluster_no': 1265055, 'dir_entry': 128}, {'index': 3999, 'cluster_no': 481882, 'dir_entry': 2112})
location_lookup_samples=({'index': 0, 'found_index': 0}, {'index': 1, 'found_index': 1}, {'index': 3999, 'found_index': 3999})
section=ALBUM node_counts=(549, 0, 0) spans=549 records_per_level=(4000, 0, 0)
section=ARTIST node_counts=(363, 707, 0) spans=1070 records_per_level=(4000, 4000, 0)
section=GENRE node_counts=(30, 439, 709) spans=1178 records_per_level=(4000, 4000, 4000)
```

This is the first M30-created multi-group image in the corpus. It confirms
that the host decoder's node layout, sector references, order/inverse tables,
deepest node-index table, and node-run coverage are useful on a real device
image rather than only on the 251-record public sample.

The device header reports the following non-empty section references:

| Section | Node sectors | Order / inverse / node-index sectors |
|---|---|---|
| `ALBUM` | level 0: `2033` | `2051`, `2067`, `2083` |
| `ARTIST` | level 0: `2099`; level 1: `2111` | `2134`, `2150`, `2166` |
| `GENRE` | level 0: `2182`; level 1: `2183`; level 2: `2197` | `2220`, `2236`, `2252` |

`ALLSONG` has no node levels in this image and retains the observed table
references at sectors `2001` and `2017`.

## Model comparison boundary

The existing reference model reproduces the 4,000-record geometry and all
section sector locations. Comparing its generated indexes with the device
image shows mostly identical order entries, but not byte-identical results:

- `ALLSONG`: 3,801/4,000 order entries match;
- `ALBUM`: the device has 549 groups versus the model's 548;
- `ARTIST`: the device has 363/707 groups versus 362/706;
- `GENRE`: the device has 30/439/709 groups versus 30/438/708.

The first mismatches are generally equal visible text keys or adjacent
duplicate metadata groups. This proves the model's current sort is a useful
candidate, not the device's exact tie-break policy. The emulator therefore
keeps candidate sorting separate from the read-only byte decoder and does not
rewrite the device indexes from this comparison alone.

### Observed previous-rank replay

The candidate comparator was replayed with the device image's actual preceding
section rank supplied to each later pass. This avoids attributing a later-pass
difference to an earlier-pass tie order. The read-only result was:

| Section | Candidate entries matching device order | First mismatch |
|---|---:|---:|
| `ALLSONG` | 3,801 / 4,000 | 14 |
| `ALBUM` | 3,981 / 4,000 | 859 |
| `ARTIST` | 3,944 / 4,000 | 83 |
| `GENRE` | 4,000 / 4,000 | none |

The reproducible probe is:

```sh
PYTHONPATH=tools/sim:tools/emu \
  python3 tools/emu/library_order_probe.py \
  <persistent-evidence-root>/device-sd/MUSIC.LIB \
  e386db27a9f47641e8755e5a58a903e6e66f83afe2be84c97d5d7e59de0f3c88
```

This is strong evidence that the preceding-section rank is the correct
secondary key for the later passes, especially because the complete `GENRE`
order matches. The remaining `ALBUM`/`ARTIST` differences are concentrated in
UTF-16/ASCII representation boundaries and unresolved text-converter/tie
refinement behavior. A byte-origin classification of the mismatching order
positions found 199 UTF-16↔UTF-16 differences in `ALLSONG`, 19
UTF-16↔UTF-16 differences in `ALBUM`, and 56 `ARTIST` differences split into
26 UTF-16↔UTF-16, 15 ASCII→UTF-16, and 15 UTF-16→ASCII positions. The probe is
diagnostic only; it does not make the candidate sorter a firmware writer and
does not rewrite a device index.

## Location-key corroboration

The public US212A application-design manual documents the file record's
filesystem key as two little-endian 32-bit values: `cluster_no` followed by
`dir_entry`. That matches the firmware consumer's eight-byte compare/copy
boundary at `+0xf4..+0xfb`. The host codec now exposes these values as
`LibraryRecord.cluster_no` and `LibraryRecord.dir_entry` while retaining the
original eight bytes losslessly. The primary `+0xa9..+0xf1` directory-layer
blob remains opaque.

On the supplied image, adjacent records demonstrate plausible directory
addressing: records 0 and 1 share `cluster_no=0x00134d9f` and use directory
entries `0` and `0x80`; the probe now records these samples automatically.
This is corroboration of the field mapping, not a complete filesystem
reconstruction.

## M3U and album-picture boundary

`M3U.LIB` begins with `M3U` and contains the ASCII marker `ALLFILE` at
`0x10`; the observed `u16` fields at `0x08` and `0x0a` are 0 and 1. The
signature at `0x1fe..0x1ff` is `55 aa`. A direct frame-chain scan of the
device image found 1,484 consecutive MPEG-1 Layer III frames from file offset
`0x2fd` through the end of the file. The frames are 320 kbps, 44.1 kHz, joint
stereo, without CRC. The last frame extends `0x221` bytes beyond EOF; the
first 253 bytes after the 512-byte header finish the preceding frame. This
image contains no example of an M30 playlist record.

The firmware evidence explains the stale tail. `playlist.ap` sets the M3U
file size to `0x17aa00`, creates that file, and writes its 512-byte header
before scanning for playlist files. The scan writes 0x100-byte records only
for found playlist files. With the observed zero count, it produces no
payload writes. The old MP3 bytes therefore remained in the allocated file
area. That the filesystem allocator leaves such clusters uncleared is a
logical inference, not directly proven allocator behavior.

The arithmetic `(0x17aa00 - 0x200) / 0x100 = 6,056` is not a playlist-record
count or a meaningful block count. The public comparison file at
`https://raw.githubusercontent.com/xleph/MP3.LIB/main/M3U.LIB` shares the
header family, but raw payload-block comparison does not identify M30 records.

The same public repository provides [`literalLocations`](https://github.com/xleph/MP3.LIB/blob/main/literalLocations), a packed list of 302 8-byte disk-location signatures, and [`readbloc.c`](https://github.com/xleph/MP3.LIB/blob/main/readbloc.c), which searches for them in library files. Interpreting each 8-byte value as little-endian, none of its 296 unique signatures occurs in the public M3U.LIB sample, the supplied M30 M3U.LIB or MUSIC.LIB, or the independent MUSIC.LIB sample. This negative cross-device comparison identifies no M30 payload fields and supplies no M30 decoding rule.

### M3U writer ABI cross-check

The Ghidra probe `tools/ghidra/run_m3u_writer_probe.sh` checks the
firmware-side writer independently of the stale payload. It confirms that
the M3U scan performs a counting pass and a writing pass, builds the file
location fields at `+0xa9` and `+0xf4`, writes predecessor/successor fields at
`+0xfc` and `+0xfe`, and emits 0x100-byte records. Before the record write, the
shared text path handles UTF-16LE and UTF-8 BOM cases. The indirect slots
resolve statically to module 6's text-conversion dispatcher and module 0x10's
copy/fill dispatcher; they are not evidence of an unknown encryption callback.

The probe passed for every available dated `playlist.ap` corpus member from
2022-09-14 through 2025-06-26. This makes the writer boundary a stable
cross-version finding. The firmware-derived record ABI is separate from the
stale payload in the supplied M3U.LIB; several field meanings remain
interpretation-level.

### M3U header counters and index writes

The header `u16` at `+0x0a` is the first record sector, not a mode. In
`FUN_4019502c`, it is copied from RAM address `0x9fc15442` (literal at VA
`0x40195214`). `FUN_40055108` copies the sector counter from `0x9fc1540a` to
that header value. Resident `FUN_bfc16410` adds `ceil(length / 512)` after
each sector write; `FUN_40194c78` resets the counter, then appends the 512-byte
header through the resident write entry. The header itself therefore advances
the counter to 1, matching `u16@0x0a = 1` and record sector 1.

The header `u16` at `+0x08` is the number of playlist entries. The startup
path in `FUN_40055108` clears its RAM word at `0x9fc15440`. `FUN_40154ecc`
increments it as the first scan pass finds entries, resets it through
`FUN_40154e74` before the write pass, and increments it after each record is
written. A scan that finds no `.m3u` file leaves the count at zero, matching
the captured M3U.LIB header. The scan limit is associated with a table value
of 50, but the runtime phase byte controlling that limit has not been
observed; that part remains a hypothesis.

After record creation, the code path `FUN_40154fe4` → `FUN_40155038` calls
the sorter at `0x71812875`, then invokes tie refinement at `FUN_40114d54`.
It writes two `u16` tables of `count * 2` bytes after the records. The
captured M3U.LIB has zero entries and stale MP3 data in its unwritten area, so
it cannot verify these records or either table. The exact field semantics and
the sorter’s relation to the MUSIC.LIB index builder remain separate open
questions.

The stock and community `playlist.ap` files have SHA-256
`7b1971f1496318a9682b0abc7681c058ded702aa533c97a32e428f5088b77b64` and
`184f2c201537e6657024a2a5a054d12fe4a7f134e06205f0786a8d71d2a29403`.
Their M3U-relevant banks are byte-identical:

| Bank | File offset | Bytes | SHA-256 prefix |
|---|---:|---:|---|
| `0x40054c00` | `0x2400` | `0x800` | `5063c698200fd2ab` |
| `0x40154c00` | `0x4400` | `0x800` | `62ec16f38205b18e` |
| `0x40194c00` | `0x4c00` | `0x800` | `125f7dd31ea8a5a6` |
| `0xbfc16400` | `0x1400` | `0x7bc` | `a52313d2f619670b` |
| `0x48014400` | `0x7400` | `0x800` | `f98ca14b65a67112` |

The full images are 133,632 bytes and have identical 70-entry bank tables.
Differences occur in seven ranges across three other banks, including the
sorting bank at `0x71812500`, file offsets `0xa5ed..0xa5ef`. The supplied
comparison indicates the M3U path calls comparator mode 2 and that the
changed sort bytes are in another branch; the mode-to-branch mapping was
inherited from an earlier analysis and should be rechecked before relying on
it. A separate store to `0x9fc15440` exists in bank `0x48114400` at VA
`0x481146f8`; its role is unresolved.

The shortest useful device test is to create two or three known `.m3u` files,
including ASCII and non-ASCII names, run “Update Playlist”, and capture the
new M3U.LIB. That would provide real records and both index tables to compare
with the recovered writer and sorting path.

The captured 4,000-record M30 `MUSIC.LIB` provides a separate value-level
check of those two tail words: every `previous_index` equals `record_index - 1`
except record zero, which contains `0xffff`; every `next_index` equals
`record_index + 1` through record 3998. Record 3999 stores `next_index=4000`,
which is outside the zero-based record range. This is consistent with the
writer linking records in scan order and preserving a one-past-end terminal
value, but one image does not establish how any reader interprets that value.
The public 251-record comparison file is excluded from this check because its
record-tail layout is not M30-compatible. The host codec therefore continues
to preserve these words without validating them as links.

Reproduce the static check with:

```sh
bash tools/ghidra/run_m3u_writer_probe.sh \
  /path/to/analysis/community/fw/playlist.ap
```

`ALBUM.PIC` begins with `ALBUM`, has `NOA` at `0x10`, and is exactly 250
sectors. The first payload begins at `0x200`; the next 45,000 bytes are the
size of a 150x150 two-byte-per-pixel image, and all remaining 82,488 bytes are
zero padding. The decompiled cache writer independently uses a six-byte
`OK`/`NO` record followed by `w*h*2` bytes, so the device file is not treated
as an `OK` record at offset zero. The host boundary decoder in
`tools/sim/artwork_cache.py` validates this container without assigning
meaning to the `ALBUM`/`NOA` header fields or to RGB565 byte order.

The read-only check is reproducible with:

```sh
PYTHONPATH=tools/sim:tools/emu \
  python3 tools/emu/album_pic_evidence_probe.py \
  <persistent-evidence-root>/device-sd/ALBUM.PIC
```

