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
buffer-size cases. These are strong navigation anchors for the fade and
buffer path, but the log calls alone do not prove sample attenuation.

Because all six corpora agree byte-for-byte at these locations, the community
firmware did not change this module. The next step is to trace callers and
the external callbacks that consume the state; only then can we distinguish a
real end-of-stream fade from a diagnostic message or a short-buffer underrun.
