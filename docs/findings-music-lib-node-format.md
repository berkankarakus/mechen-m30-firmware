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

Source: [xleph/MP3.LIB](https://github.com/xleph/MP3.LIB), especially its
[README](https://github.com/xleph/MP3.LIB/blob/main/README.md) and public
[MUSIC.LIB member](https://github.com/xleph/MP3.LIB/blob/main/MUSIC.LIB).

The comparison binary was used only as a temporary local hex reference. It is
not stored in this repository.

## Emulator boundary

`tools/sim/library_file.py` keeps `read_library_section_nodes()` as a raw
16-byte reader and adds `decode_library_section_node()` for the field layout.
This preserves unknown bytes and lets callers opt into the recovered fields.

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

## Next evidence target

Compare an M30-created `MUSIC.LIB` byte image against the existing raw reader
and this decoder. The highest-value checks are the section reference order,
node link sentinels, and whether `first_record_index` points into the same
record index space. Until then, new behavior should remain behind the decoder
boundary rather than being presented as M30-specific behavior.
