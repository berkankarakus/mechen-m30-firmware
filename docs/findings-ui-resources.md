# M30 UI resource boundary

This note records the safe, byte-level structure of the browser/main-menu
resource trees and selected RU3 style members. It does not claim that a node
ID or RU3 group index has a user-facing meaning unless that meaning is already
proven elsewhere.

## Reproducible check

```sh
PYTHONPATH=tools/emu python3 tools/emu/ui_resource_probe.py \
  --analysis-root analysis
python3 -m unittest tools/emu/test_ui_resource_probe.py
```

The two MCG members and four selected STY members are byte-identical in all
six local firmware extractions. Therefore the community firmware did not
change these menu/resource boundaries.

## MCG trees

`browser.mcg` is 0xa00 bytes and contains 17 contiguous node records. The
node IDs, in index order, are:

```text
0, 14, 5, 19, 1, 6, 15, 16, 20, 2, 8, 17, 18, 21, 3, 10, 11
```

`mainmenu.mcg` is 0x200 bytes and contains 3 top-level nodes with IDs
`0, 1, 2`. Both files carry the `ACTMCGGM01` marker and an `[INFO] filesum`
matching the parsed node count.

This gives the emulator a deterministic menu-tree input and prevents a UI
patch from silently changing node count/order. It does not identify the
localized names, because those are resource strings in the corresponding STY
members.

## RU3 style members

All four selected STY files start with `RU3 0x19`. The header points to a
style table; the probe follows that pointer, validates each non-empty group
address against the member size, and stops at the first `(0, 0)` group. The
observed non-empty group counts are:

| Member | Size | Non-empty groups | Style table address / start |
|---|---:|---:|---:|
| `browser.sty` | `0x7800` | 1 | `0x7600 / 0x7610` |
| `config.sty` | `0x72800` | 2 | `0x72600 / 0x72610` |
| `udisk.sty` | `0x2f600` | 3 | `0x2f400 / 0x2f410` |
| `upgrade.sty` | `0x6200` | 3 | `0x6000 / 0x6010` |

The group addresses/counts are structural facts only. Item sizes and semantic
IDs must be supplied by the matching application/resource headers before any
resource-only patch is considered.

## Consequence for the emulator

The safe next emulator step is to load the real MCG node list and RU3 group
metadata as immutable fixtures, then connect already-proven application IDs
to those records. Adding a new menu node or changing a style group is not yet
safe: it would require proving the corresponding AP lookup and preserving the
fixed member size/checksum contract.
