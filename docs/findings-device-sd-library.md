# Device SD library evidence

This note records the three files supplied from an M30 SD card. The binary
files remain outside Git under the persistent evidence root; this repository
stores only provenance, hashes, and read-only interpretation results.

## Captured files

| File | Bytes | SHA-256 | Safe interpretation |
|---|---:|---|---|
| `MUSIC.LIB` | 2,625,536 | `e386db27a9f47641e8755e5a58a903e6e66f83afe2be84c97d5d7e59de0f3c88` | A 4,000-record, 512-byte-sector library image |
| `M3U.LIB` | 1,550,848 | `ad4deb5b599eb97309e49a1d907cab445e3785d04f0ee103e6126f8ab0703a01` | `M3U` header, `ALLFILE` marker, zero at the observed entry-count field `0x08` |
| `ALBUM.PIC` | 128,000 | `65bad6f0a143f3990f1d0e958699513159dc3b06f7bcec0452ee318217c8e671` | `ALBUM` header and 250 sectors; payload format is not assigned here |

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

## M3U and album-picture boundary

`M3U.LIB` begins with `M3U` and contains the ASCII marker `ALLFILE` at
`0x10`; the observed `u16` at `0x08` is zero. Its remaining bytes are not
treated as entries without a traced reader or a known entry count.

`ALBUM.PIC` begins with `ALBUM`, has `NOA` at `0x10`, and is exactly 250
sectors. Its first payload sector is non-zero binary data, but it does not
begin with the six-byte `OK`/`NO` record contract currently modeled for the
artwork cache. The file is therefore recorded as a separate opaque artifact;
the existing cache model is not applied at offset zero.

