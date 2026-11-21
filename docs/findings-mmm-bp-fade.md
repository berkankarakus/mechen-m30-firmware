# `mmm_bp.al` fade/buffer boundary

This is a static finding. It is relevant to the user's observation that some
tracks lose their final fade-out, but it is not yet a claim that the firmware
fade algorithm has been reconstructed.

## Reproducible checks

```sh
PYTHONPATH=tools/emu python3 tools/emu/mmm_bp_binary_probe.py \
  --analysis-root analysis
bash tools/ghidra/run_mmm_bp_fade_probe.sh analysis/community/fw/mmm_bp.al
bash tools/ghidra/run_mmm_bp_fade_probe.sh analysis/stock/fw/mmm_bp.al
```

The binary probe finds the same markers at the same offsets in all six local
corpora (`stock`, `community`, `first-pass-verify`, `v1.101.11`, `v1.101.12`,
and `v5`):

| File offset | Marker | Mapped address |
| ---: | --- | ---: |
| `0x500` | `dsp dec error:` | `0xbfc21500` |
| `0x510` | `dsp dec slow!!` | `0xbfc21510` |
| `0x674` | `set_fast step:` | `0xbfc21674` |
| `0x684` | `set_slow step:` | `0xbfc21684` |
| `0x864` | `not enough data fade out!` | `0xbfc21864` |
| `0x880` | `buffer remain:` | `0xbfc21880` |
| `0xb70` | `fade out:` | `0xbfc27470` |
| `0xb7c` | `fade in:` | `0xbfc2747c` |
| `0xd8c` | `frame space:` | `0xbfc2768c` |

The YQHX image has two loaded segments relevant here: file `0x400..0xaf0`
maps to `0xbfc21400`, and file `0xb00..0x1700` maps to `0xbfc27400`.

## Ghidra boundary

`FUN_bfc27400` and adjacent small routines pass the `fade out:`/`fade in:`
strings to an external logging/diagnostic call with mode `0x41`, while updating
state pointers around `param + 0xbc`, `+0xc0`, `+0xc4`, `+0xc8`, and `+0xcc`.
`FUN_68021c8c` initializes decoder state and selects DSP-related strings;
`FUN_680a1ed4` handles buffer/control state, including `0x80` and `0x400`
buffer-size cases.

The actual fade-step path is stronger than the string evidence alone:

- `FUN_bfc21590` branches on state byte `param + 0xba`: state `2` emits the
  `set_slow step:` diagnostic, while state `3` emits `set_fast step:`. Both
  paths advance the step counter at `param + 0x8a` and update a shared
  time/level value using a 100-step phase.
- `FUN_bfc216a8` is the surrounding decoder/buffer state machine. It calls
  `FUN_bfc21530` when the end-state transition is reached, emits
  `not enough data fade out!` and `buffer remain:` at its failure/progress
  branches, and then feeds the buffer loop through `FUN_bfc276ac`.
- `FUN_bfc27400` records the explicit fade-in/fade-out control event and
  updates the shared state pointers used by the step path.
- `FUN_bfc276ac` requests a `0x200`-byte decoder block and advances a ring of
  `0x20`-byte slots while decrementing the available-count state.
  `FUN_bfc274c8` is the corresponding wrap-around reader: it refuses a read
  larger than the available count and splits a read at the ring end.
- `FUN_bfc27520` consumes the ring state and calls the shared callback with
  fade/control modes when the frame/buffer boundary changes. Its final output
  scaling uses the current sample/level fields, so this is the first concrete
  bridge between the fade state machine and the buffered output path.

The callback boundary is now anchored to the literal pool rather than only to
Ghidra's `_UNK_` names: `0xbfc21698`, `0xbfc27488`, `0xbfc274c4`, and
`0xbfc276a0` contain the odd MIPS16 value `0xbfc21a3d`; the buffer state at
`0xbfc2769c` contains `0x9fc21b00`; and the ring helpers use the odd entries
`0xbfc274c9` and `0xbfc2748d` from `0xbfc2772c` and `0xbfc27730`. The latter
two normalize to the already recovered even-entry routines `FUN_bfc274c8` and
`FUN_bfc2748c`. The `0xbfc21a3d` target itself does not decompile as a valid
function in this module: the aligned instruction probe sees `li` followed by
`break 0` and zero padding at `0xbfc21a3c`. Therefore the static value is not
treated as a callback body. It is consistent with a runtime-relocated/filled
slot, but that part is an inference; the slot remains unsupported and is not a
safe patch site.

The ownership boundary is also clearer now: `FUN_bfc21530` consumes the
control flag at `param + 0x81`, clears it, and initializes fade mode `2` plus
the step counter at `+0x8a`; `FUN_bfc21590` later changes mode `2` to `3` when
the recovered phase condition is reached. The mapped control routine
`FUN_680a1ed4` explicitly clears `+0x81` during its reset path. The first
external writer that sets `+0x81` is still unresolved, so this is not yet a
safe patch site. A full `LoadAP` + `DumpC` pass over all 30 recovered
functions finds exactly four `+0x81` references: one reset-path clear in
`FUN_680a1ed4`, and the read plus two clears in `FUN_bfc21530`. There is no
mapped assignment that arms the byte, which narrows the missing writer to an
external/indirect boundary rather than another hidden `mmm_bp` function.

This proves a firmware fade state machine and its buffer-facing boundary, but
not yet whether a particular Audacity-rendered tail is lost before this state
machine, during buffer exhaustion, or in the downstream DSP. The remaining
static trace target is the external callback behind the step calls and the
caller that supplies `param + 0x81`/`+0xba`; then compare a short-tail file
against the `available-count` and `0x200`-byte refill conditions.

## Emulator boundary

`tools/sim/mmm_bp_model.py` now exposes the safe part of this contract:
`plan_ring_read()` rejects reads larger than the available count and returns
the same two-segment wrap plan as the recovered reader; `REFILL_BLOCK_BYTES`
records the observed `0x200` decoder refill; `read_ring_bytes()` applies that
plan to a concrete ring byte source without interpreting samples; and
`advance_fade_step()` models
the proven mode selection, 60-step phase, and ±1000 level arithmetic while
keeping the caller-provided base level opaque. No DSP bytes, callback body, or
guessed attenuation coefficients are executed.

Because all six corpora agree byte-for-byte at these locations, the community
firmware did not change this module. The next step is to trace callers and
the external callbacks that consume the state; only then can we distinguish a
real end-of-stream fade from a diagnostic message or a short-buffer underrun.

## End-state ordering relative to the refill loop

A targeted instruction dump of `FUN_bfc216a8` narrows the end-state sequence.
In its active state-1 path, it calls `FUN_bfc27520` at `0xbfc21794` before
reading the status word through the pointer at context `+0xd0`. The next
instructions compare that status with `3` (`0xbfc217a2`) and branch to
`0xbfc217b4` (`0xbfc217a4`) when equal. That branch writes state `2` at
`0xbfc217ba` and returns at `0xbfc217c8`. The `0x200`-byte refill helper
`FUN_bfc276ac` is called at `0xbfc21712` from the loop reached only when the
status is not `3` and the elapsed-time guard has not fired. Thus status `3`
allows a preceding `FUN_bfc27520` pass, but exits before another refill-loop
iteration; the recovered code does not show a loop that waits for a downstream
queue to become empty before returning.

This is a concrete ordering fact, **not** proof that `FUN_bfc27520` drains the
ASRC/DAC queue: its indirect callback implementation remains unresolved, and
no device queue level or audible tail was measured. Nor does this function
call the separate `music.ap` track-index advance callback. The relation between
this decoder-side terminal state and the `music.ap` mode-4 advance path is
still unproven. `mmm_bp.al` SHA-256 is identical in stock V1.101.10 and
community V1.292.00 (`ab5d98b578406c4e04fb7b546317fbec0d36ce4a7c139ef0922b06bb4b753c5b`),
so this ordering is not a community-only change.

The Ghidra runner now pins the instruction addresses above in addition to the
decompilation checks. Reproduce against either extracted member with the two
commands above. The code was statically disassembled/decompiled; this new
ordering check does not execute the decoder callbacks.
