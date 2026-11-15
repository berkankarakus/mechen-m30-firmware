# `mmm_bp.al` fade/buffer boundary

This is a static finding. It is relevant to the user's observation that some
tracks lose their final fade-out, but it is not yet a claim that the firmware
fade algorithm has been reconstructed.

## Reproducible checks

```sh
PYTHONPATH=tools/emu python3 tools/emu/mmm_bp_binary_probe.py \
  --analysis-root analysis
bash tools/ghidra/run_mmm_bp_fade_probe.sh analysis/community/fw/mmm_bp.al
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

This proves a firmware fade state machine and its buffer-facing boundary, but
not yet whether a particular Audacity-rendered tail is lost before this state
machine, during buffer exhaustion, or in the downstream DSP. The next trace is
the external callback behind the step calls and the caller that supplies
`param + 0x81`/`+0xba`; then compare a short-tail file against the
`available-count` and `0x200`-byte refill conditions.

Because all six corpora agree byte-for-byte at these locations, the community
firmware did not change this module. The next step is to trace callers and
the external callbacks that consume the state; only then can we distinguish a
real end-of-stream fade from a diagnostic message or a short-buffer underrun.
