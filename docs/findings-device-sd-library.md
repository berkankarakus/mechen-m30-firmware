# Device SD library evidence

This note records the three files supplied from an M30 SD card. The binary
files remain outside Git under the persistent evidence root; this repository
stores only provenance, hashes, and read-only interpretation results.

## Captured files

| File | Bytes | SHA-256 | Safe interpretation |
|---|---:|---|---|
| `MUSIC.LIB` | 2,625,536 | `e386db27a9f47641e8755e5a58a903e6e66f83afe2be84c97d5d7e59de0f3c88` | A 4,000-record, 512-byte-sector library image |
| `M3U.LIB` | 1,550,848 | `ad4deb5b599eb97309e49a1d907cab445e3785d04f0ee103e6126f8ab0703a01` | `M3U` header, `ALLFILE` marker, zero at the observed entry-count field `0x08` |
| `ALBUM.PIC` | 128,000 | `65bad6f0a143f3990f1d0e958699513159dc3b06f7bcec0452ee318217c8e671` | `ALBUM` container, 250 sectors, observed 150x150 RGB565-sized payload and zero padding |

The source files were copied to the persistent evidence root before the SD
card was ejected. A future session can reproduce the checks with:

```sh
shasum -a 256 \
  <persistent-evidence-root>/device-sd/ALBUM.PIC \
  <persistent-evidence-root>/device-sd/M3U.LIB \
  <persistent-evidence-root>/device-sd/MUSIC.LIB
```

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
`0x10`; the observed `u16` at `0x08` is zero. Its remaining bytes are not
treated as entries without a traced reader or a known entry count. The public
comparison sample at
`https://raw.githubusercontent.com/xleph/MP3.LIB/main/M3U.LIB` is also
512-byte-header-compatible, but its 5,800 256-byte payload blocks share no
exact block with the device's 6,056 blocks. This supports keeping M3U payload
interpretation outside the current MUSIC.LIB emulator contract.

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

