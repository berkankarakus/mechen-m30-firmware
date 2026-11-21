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

### `config.ap + 0x1e0c..0x1e0d`

The community patch changes bytes `0d 22` to `0d 10`. The decompiler's
`in_v0 == 0` description is an artifact and should not be used as the semantic
condition. The automatic-index startup decision is a separate four-byte flash
word at `0x2f0000`: `config.ap` tests bit `0x10000` and, when set, starts
`playlist.ap` (application 10, parameter `0x4e`). The exact relation between
this flag and every card-event path remains unresolved.

### `udisk.ap + 0x1908..0x1909`

The community patch changes a conditional branch to an unconditional branch.
This removes that particular dirty-state path; it does not prevent another
component from setting or consuming the `0x2f0000` flag, or from starting the
playlist builder directly.

`playlist.ap` clears bit `0x10000` only after a successful update, so an
interrupted build can be retried on a later startup. These two community
changes affect only their specific guard paths. They do not establish a
general automatic-index bypass or identify the powered-card insertion path.

### Dated official-corpus control check

The two instruction bytes were checked in the nine newly extracted official
corpora. Every dated official file retained `0d 22` at `config.ap+0x1e0c` and
`08 22` at `udisk.ap+0x1908`; the community baseline has `0d 10` and `08 10`,
respectively. This supports the hypothesis that these byte changes are
community-specific rather than a general property of the M30 firmware line.
It still does not identify the separate powered-card event path observed on
the device.

## Interpretation of the recent device test

The reported powered-card test used a V1.292.00-based image with the two
community guard changes. Its exact device image hash was not recorded in the
evidence supplied here, so record the firmware version separately from a
byte-verified image identity.

## Physical result on this M30

User-reported test on 2026-11-15: with the two guard changes present in the
V1.292.00-based image, removing and reinserting the card while powered still
started indexing.

This is a device observation, not a static inference. It shows that those two
guard changes do not prevent indexing after powered card reinsertion on the
tested unit. The event may set the flash flag elsewhere or start the builder
directly. No card-event callback or flag setter has been identified, so the
call chain remains open.

The host model keeps these outcomes separate: the static guard contract uses
`CardChangePolicy.MANUAL_UPDATE_REQUIRED`, while the tested powered-card
removal-and-reinsertion observation is represented explicitly by
`CardChangePolicy.AUTOMATIC_REBUILD`. The latter requires a file count and
enters the normal bounded update state; it does not claim that every card or
startup trigger behaves this way.

## Next discriminating observation

If a read-only device flash read is available, compare the four-byte word at
`0x2f0000` before and after powered card reinsertion. A newly set `0x10000`
bit would direct the search toward its setter; an unchanged word would favor a
direct app launch or another trigger. Static candidates include the
`0x2f0000` reference in `kernel.drv` at file `0x33b8` and the
`0x9fc155d0` references in `mainmenu.ap`; `card.drv` and `cards.drv` contain
no known index call or flag literal. A main-menu event path involving message
`0xf2` carries the value `0x10000`, but no link from that event to card
detection, the flash-word setter, or playlist launch has been established.
Treat it only as a candidate. No setter or card-event callback has been
verified yet.

### Main-menu `0x9fc155d0` candidate check

A Ghidra load of `mainmenu.ap` found ten raw 32-bit occurrences of
`0x9fc155d0` and none of `0x9fc155d4`. Inspecting one occurrence in the
resident initialization path identified `FUN_40014d74`: it passes
`0x9fc155d0` to the persistence helper with ID `0x10000`, length `0x22`, and
read operation `0x12`; on a missing/invalid `0x55ab` record it initializes
and writes that record. Its caller is `FUN_40014efc`. This occurrence is
persistent-state initialization, not evidence that the address is the
powered-card event flag.

The currently decoded MIPS16 import calls in `mainmenu.ap` contain no
`a3` import selector `0x4e` (59 calls scanned). This does not test for an
application-launch argument `0x4e`; the import selector and app parameter
are different call fields. No conclusion about a main-menu app launch can
be drawn from this scan. The card-insertion-to-indexing path remains
unresolved. Several other raw pointer hits overlap decoded instruction
addresses, so the bytewise pointer scan is not a call-reference list; the
remaining hits need instruction-level classification.

The driver-side follow-up is bounded in
[`findings-card-reinsert-trigger.md`](findings-card-reinsert-trigger.md): the
exported `card.drv` vector contains block-I/O/control functions, while the
`cards.drv` probe helpers are only called from that driver's entry/setup
function. The outer event dispatcher and powered-reinsert route remain open.
