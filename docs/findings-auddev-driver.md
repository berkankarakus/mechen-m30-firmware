# M30 `aud_dev.drv`: tiny member boundary

`aud_dev.drv` is not a complete audio playback implementation in the
extracted firmware. It contains an eight-byte MIPS32 payload, so it must be
kept separate from the much larger codec bus driver (`drv_dac.drv`) and the
unexamined decoder DSP members.

## Reproducible checks

```sh
PYTHONPATH=tools/emu python3 tools/emu/auddev_binary_probe.py \
  analysis/community/fw/aud_dev.drv
bash tools/ghidra/run_auddev_probe.sh analysis/community/fw/aud_dev.drv
```

The member is byte-identical in the local community, stock, first-pass,
V1.101.11, V1.101.12, and V5 extractions. Its SHA-256 is:

```text
3349287198faaa90a503353673674d5628e85711db9ee16217db5a803484f09c
```

## Container and observed bytes

| Field | Value |
|---|---:|
| file offset | `0x300` |
| length | `0x8` |
| destination | `0xbfc09f58` |
| BSS | `0x9fc34160`, `0` bytes |
| entry field | `0x1c009000` |
| body | `25 9b 08 2c 91 9b 08 2c` |

Mapping the member as MIPS32 gives two COP2 register reads/writes in Ghidra's
decompiler. The generated output then reaches the end of the eight-byte
segment and warns about missing control-flow bytes. There is no complete
function body, codec register table, PCM path, volume path, or fade logic in
this member.

## Consequence

`aud_dev.drv` is now classified as a tiny hardware-facing stub/fragment, not
an unresolved full audio driver. It should not be patched or emulated as a
playback path. The useful remaining audio targets are `drv_dac.drv` callers and
the `ad*.dsp` decoder/processing members; those are separate questions and
remain unmodified.
