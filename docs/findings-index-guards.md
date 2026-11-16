# Automatic-index guard: stock versus community

This is an offline Ghidra comparison of stock V1.101.10 and community
V1.292.00. It does not prove behavior on every M30 unit, but it resolves what
the two one-byte community changes do in the surrounding control flow.

## Reproduction

```sh
bash tools/ghidra/run_index_guard_probe.sh \
  analysis/stock/fw analysis/community/fw
```

The probe decompiles the same entry locations from both AP sets and checks the
raw bytes at the patch offsets.

## What the comparison shows

### `config.ap + 0x1e0d`

The stock entry contains an `in_v0 == 0` conditional around the normal
configuration/update preparation path. The community byte change (`0x22 ->
0x10`) removes that conditional in the decompiler output; the no-automatic-
update path is no longer guarded by the incoming status value.

### `udisk.ap + 0x1909`

The stock USB/storage entry contains an `in_v0 != 0` block that marks the
update state dirty and sets the corresponding flag. The community byte change
removes that block from the decompiled control flow.

These two findings explain why the community firmware is reasonably described
as containing an automatic-index bypass while preserving the manual Settings
-> Update Playlist path. They do not prove that unrelated startup code can
never initiate a rebuild, nor do they replace a cold-boot and powered-card
physical test.

### Dated official-corpus control check

The same raw offsets were checked in the nine newly extracted official
corpora. Every dated official file retained `0x22` at both `config.ap+0x1e0d`
and `udisk.ap+0x1909`; the community baseline alone has `0x10` at both
locations. This supports the hypothesis that the two-byte guard change is a
community-specific modification rather than a general property of the M30
firmware line. It still does not identify the separate powered-card event
path observed on the device.

## Interpretation of the recent device test

An older stock-based index experiment was not V1.292.00. Therefore its
indexing after card insertion cannot falsify the community guard. The correct
physical comparison is the untouched community image:

`<local-workspace>/mechen-m30-community-firmware/releases/v1.292.00/MECHEN_M30.HEX`

with the stock image retained offline for rollback.

## Physical result on this M30

User-reported test on 2026-11-15: the untouched community V1.292.00 image was
flashed successfully, and removing/reinserting the card while the device was
running started indexing again.

This is now a device observation, not a static inference. It shows that the
two community guard sites do not cover this powered card-insertion trigger on
the tested unit, or that a separate card-event path starts the builder. It
does not invalidate the decompiled meaning of the two guard sites; it narrows
the remaining work to the card-event/startup call chain.

The host model keeps these outcomes separate: the static guard contract uses
`CardChangePolicy.MANUAL_UPDATE_REQUIRED`, while the tested powered-card
observation is represented explicitly by
`CardChangePolicy.AUTOMATIC_REBUILD`. The latter requires a file count and
enters the normal bounded update state; it does not claim that every card or
startup trigger behaves this way.
