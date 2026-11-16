# MUSIC.LIB node format evidence

This note records the byte-level evidence behind the host decoder for the
16-byte section nodes. It does not claim that the public comparison file is an
M30 dump.

## Evidence

The repository's reference builder emits every node with:

```text
struct.pack("<BBHHHHHHH", node_type, depth, child_count, song_count,
            first_record_index, first_child_index, parent_index,
            previous_index, next_index)
```

That gives this fixed layout:

| Offset | Width | Host field |
|---:|---:|---|
| `0x00` | `u8` | `node_type` |
| `0x01` | `u8` | `depth` |
| `0x02` | `u16` | `child_count` |
| `0x04` | `u16` | `song_count` |
| `0x06` | `u16` | `first_record_index` |
| `0x08` | `u16` | `first_child_index` |
| `0x0a` | `u16` | `parent_index` |
| `0x0c` | `u16` | `previous_index` |
| `0x0e` | `u16` | `next_index` |

An independent public comparison repository contains a raw `MUSIC.LIB` file
and describes its `.LIB` files as coming directly from an MP3 player. Its
header reports 251 records. The section directory references the same
ordering used by the local builder: `ALLSONG` order/inverse tables, then
`ALBUM`, `ARTIST`, and `GENRE` node/table groups. The first observed nodes
also decode cleanly with the layout above: `node_type=1`, the expected depth,
`song_count=251`, `first_record_index=23`, and `0xffff` link sentinels where
the group has no corresponding link.

The comparison is not a byte-identical reproduction of the local builder.
Running `libmodel.py` and `libdiff.py` against the public file keeps the
record count and section locations compatible, but reports different sort and
group results: the public `ARTIST` directory has counts `(1, 1, 0)` while the
local model derives `(2, 2, 0)`, and the public `GENRE` directory has
`(1, 1, 1)` while the model derives `(1, 2, 2)`. This is evidence that the
wire layout is shared while grouping/tie-breaking behavior may vary by
firmware or by the source library's contents.

The local builder and `libdiff.py` also establish the three per-record table
roles after the node slots: reference `3` is the section's sorted record
order, reference `4` is its inverse rank, and reference `5` is the per-song
node/group index when that section has levels. `tools/sim/library_file.py`
exposes these as `LibrarySectionTables` without validating or rewriting the
values. The public comparison's grouping divergence is why the host model
does not turn these tables into a user-facing sort policy.

## New Ghidra confirmation

Ghidra 12.2 was run against the extracted 2025-06-26 `playlist.ap` with:

```sh
bash tools/ghidra/run_library_index_probe.sh \
  /path/to/2025-06-26/fw/playlist.ap \
  /private/tmp/m30-ghidra-library-index-current
```

The probe decompiles the four index passes, the node writer, the shared sort
dispatcher, and the text-key converter. The node writer confirms that the
first record is read from the sorted order array, each node consumes one
positive run length, child counts are accumulated from a child run stream,
and parent indices advance from a parent run stream. It writes the previous
and next links from the node counter and terminates the final next link with
`0xffff`. The main entry calls the passes in `ALLSONG`, `ALBUM`, `ARTIST`,
`GENRE` order. The converter distinguishes UTF-16LE BOM, UTF-8 BOM, and
plain-byte paths, with the BOM paths reading twice the requested field width
before conversion.

The preserved decompile output `index.c` has SHA-256
`b4d24e168ca61c697c489404ad35d92644d6a0e0effb5b03b010e76dc356fcbc`.
The same hash was obtained for all twelve dated `playlist.ap` members in the
corpus (2022-08-05 through 2025-06-26). The decompile outputs are intentionally
kept outside the repository because they are derived from vendor firmware; the
probe is the canonical regeneration path. This twelve-release match makes
the index/node/key-converter contract a cross-version finding, but it does not
resolve the opaque location bytes or prove that the public sample's grouping
is M30-specific.

An additional read-only probe dumps the tie-refinement and compare callbacks
to `<persistent-evidence-root>/decompile/library-tie-2025-06-26/tie.c`:

```sh
bash tools/ghidra/run_library_tie_probe.sh \
  /path/to/2025-06-26/fw/playlist.ap \
  /path/to/m30-evidence/decompile/library-tie-2025-06-26
```

The preserved `tie.c` has SHA-256
`80c8cd7af541f3327e459af47f487a0bebdd98334c1de1c503649acefb98b559`.
`FUN_40114d54` tracks the compared-byte length for each sorted entry, finds
equal runs, reloads a bounded additional key slice of `0x10000 / run_length`
bytes (capped by the remaining field width and 100 bytes), re-sorts that run,
and repeats while a run can still be refined. `FUN_71812548` uppercases ASCII
bytes, compares up to the supplied length, and returns equality when both
current bytes are NUL. This explains why a visible text-key model can match
the high-level order while missing terminator-adjacent UTF-16/ASCII ties. The
host model keeps this refinement opt-in until the source-offset conversion path
is independently reproduced.

The reproducible cross-comparison tool is
`tools/emu/library_tie_refinement_probe.py`. It applies the recovered bounded
refinement shape to the device image and compares each candidate order with
the stored section table while feeding the device's preceding-section rank to
later passes. Against the captured M30 image it reports:

```text
ALLSONG 3803/4000 (first mismatch 14)
ALBUM 3981/4000 (first mismatch 859)
ARTIST 4000/4000
GENRE 4000/4000
```

Run it with:

```sh
PYTHONPATH=tools/sim:tools/emu \
  python3 tools/emu/library_tie_refinement_probe.py \
  <persistent-evidence-root>/device-sd/MUSIC.LIB \
  e386db27a9f47641e8755e5a58a903e6e66f83afe2be84c97d5d7e59de0f3c88
```

This is still a differential probe, not a firmware writer or a replacement
for QEMU execution. The existing QEMU MIPS probe scripts remain the next
machine-local validation step when QEMU user-mode is available.

Source: [xleph/MP3.LIB](https://github.com/xleph/MP3.LIB), especially its
[README](https://github.com/xleph/MP3.LIB/blob/main/README.md) and public
[MUSIC.LIB member](https://github.com/xleph/MP3.LIB/blob/main/MUSIC.LIB).

The raw member was downloaded from
<https://raw.githubusercontent.com/xleph/MP3.LIB/main/MUSIC.LIB> and is
kept outside the repository at
`<persistent-evidence-root>/MUSIC.LIB`. Its SHA-256 is
`cc3f476c8edb50ea8493b726d46ac82b139a6e87a86cc04c2cdbc30fd3fb8afe`.
Passing this image through `SdCardBlockDevice`, `read_library_layout()`, and
`interpret_library_section_index()` confirms the 251-record header/record
boundary and the section node spans without copying the binary into Git.
The reusable command-line check is
`tools/emu/musiclib_evidence_probe.py`; it verifies the hash before parsing
and prints the per-level record coverage for ALBUM, ARTIST, and GENRE.

The comparison binary was used only as a temporary local hex reference. It is
not stored in this repository.

## Emulator boundary

`tools/sim/library_file.py` keeps `read_library_section_nodes()` as a raw
16-byte reader and adds `decode_library_section_node()` for the field layout.
This preserves unknown bytes and lets callers opt into the recovered fields.
`interpret_library_section_index()` now maps each validated node's song span
back to the raw record indices in the section order table. It validates the
order, inverse, node-index, node-link, and coverage contracts first, then
returns a read-only view; it does not rewrite tables or assign user-facing
folder/album/artist semantics.

Confidence is high for the byte order, field widths, and offsets because the
local builder and the independent hex sample agree. Confidence is medium for
the product-specific meaning of each link and index, and low for assuming the
local sort/group implementation applies to every player, because the
comparison file is not proven to be from an M30 and its derived directory
counts differ from the local model.

The emulator therefore does not yet infer a user-facing tree, resolve node
indices to directories, or assume that `node_type=1` has a broader meaning
than the observed builder contract. It also does not reuse the public sample
to change sorting or grouping behavior.

## Open TODOs and educated guesses

These are investigation targets, not emulator contracts:

| Bytes or behavior | Educated guess | Confidence | What would confirm or reject it |
|---|---|---|---|
| `0xa9..0xf1` | A fixed-width primary file-location or storage-metadata blob. Its size and position between tag metadata and the track field make a path, cluster, or locator representation plausible, but no current consumer decodes it. | Low | An M30-created record paired with its source path and a second record whose path differs in only one component. |
| `0xf4..0xfb` | A little-endian `cluster_no` followed by a little-endian `dir_entry`, matching the US212A `plist_f_info_t` documentation and the firmware's eight-byte lookup key. | Medium–high | A paired M30 directory dump or relocation experiment that independently reproduces both words. |
| `0xfc..0xff` | Per-record predecessor/successor links for source or scan order, separate from section-node links. The placement at the record tail and 16-bit width support this, but no reader has been traced. | Low–medium | Records reordered on disk while preserving metadata, or a traced playback/browser consumer reading these fields. |
| Section table reference `5` | A per-record index into the deepest node level for the section. The recovered `tables()` comment and code use the final run level: album groups for `ALBUM`, the deepest album groups for `ARTIST`, and genre groups for `GENRE`. The level-zero artist group is separately carried through scratch state for the next pass. | High for the local writer | A multi-group M30 image where table values match the deepest node ranges; the UI-facing meaning may still differ. |
| Nested run model | ALBUM, then ARTIST, then GENRE nodes are hierarchical runs rather than independent flat groups. This follows the recovered builder and is the strongest current behavioral guess. | Medium–high | A real M30 image with duplicate artists/albums/genres and matching node counts, child counts, and table values. |

The next evidence pass should therefore pair the decoded
`cluster_no`/`dir_entry` values with an M30 directory dump. The primary
location blob and record links remain opaque, and the candidate run model
remains read-only.

The current host tests do exercise the complete synthetic SD path: a
sector-backed image is loaded through `SdCardBlockDevice`, a record is read
through `read_library_record()`, and the decoded secondary key plus opaque
primary/tail values are checked for lossless transport. This verifies the
emulator's byte path, not the real-world meaning of the unresolved values.

`tools/sim/library_index_sort.py` now exposes the decompiled comparison as a
candidate order-only model: ASCII-only upper-casing, signed album track-byte
tie-breaking, and previous-section rank tie-breaking. It operates on raw
256-byte records and never writes an index or claims that its order is the
M30 device's final UI policy. This separation is intentional because the
public comparison file produces different grouping counts from the local
model.

The same module now derives the candidate nested run lengths that feed the
three node levels in the local builder. `ALBUM` produces its album runs;
`ARTIST` uses those album group indices as its child grouping; and `GENRE`
uses artist groups as its first child level and album groups as its second.
`group_indices_from_runs()` converts each run list to a per-record group
index. The implementation validates permutation, coverage, and positive run
lengths, but it remains a host-side reconstruction helper: it does not write
node bytes, replace parsed tables, or assert that M30 creates the same groups.

`validate_library_section_nodes()` checks only the recovered wire contract:
non-zero node type/depth and song counts, record bounds, same-level
previous/next sentinels, parent/child reciprocity, contiguous child ranges,
depth relationships, and per-level song coverage. The public 251-record
sample passes this check for all four sections. A multi-group M30 image is
still required before these links are used as a user-facing hierarchy.

## Next evidence target

Compare an M30-created `MUSIC.LIB` byte image against the existing raw reader
and this decoder. The highest-value checks are the section reference order,
node link sentinels, and whether `first_record_index` points into the same
record index space. Until then, new behavior should remain behind the decoder
boundary rather than being presented as M30-specific behavior.
