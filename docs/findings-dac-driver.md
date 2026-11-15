# M30 DAC driver: static boundary

`drv_dac.drv` is the low-level codec/DAC bus helper. It is not the audio
decoder and it does not contain the user-visible fade curve. The result below
comes from Ghidra 12.2 and raw `yqhx` bytes; no hardware bus trace was taken.

## Reproducible checks

```sh
PYTHONPATH=tools/emu python3 tools/emu/dac_binary_probe.py \
  analysis/community/fw/drv_dac.drv
bash tools/ghidra/run_dac_probe.sh analysis/community/fw/drv_dac.drv
```

The driver SHA-256 is identical in the local community, stock, first-pass,
V1.101.11, V1.101.12, and V5 extractions:

```text
a3d21100a8fd324a77c08aaecf444ddc4f66ace56bd9dfbdc228e508ef956a33
```

## Container and functions

The image has one resident payload:

| Field | Value |
|---|---:|
| file offset | `0x200` |
| length | `0x800` |
| destination | `0xbfc18d00` |
| BSS | `0x9fc16090`, `0x16c` bytes |
| entry field | `0xbfc18d08` |
| static functions | 27 |

The decompiled functions expose a small GPIO/serial-bus abstraction. A device
context passed to the helpers contains register pointers and masks at offsets
`+0x04`, `+0x08`, `+0x0c`, `+0x10`, `+0x14`, `+0x18`, and `+0x1c`.

Observed operations:

- `FUN_bfc18db8` / `FUN_bfc18de4`: set/clear the masked output at context
  `+0x18`.
- `FUN_bfc18e10` / `FUN_bfc18e3c`: set/clear the masked output at `+0x08`.
- `FUN_bfc18e68` / `FUN_bfc18e88`: set/clear the masked output at `+0x14`.
- `FUN_bfc18ee8` / `FUN_bfc18f08`: set/clear the masked output at `+0x04`.
- `FUN_bfc18f68` and `FUN_bfc18fa0`: find the first set bit and read one
  masked bus bit.
- `FUN_bfc191d4`: shifts one byte out, eight bits, using the set/clear and
  delay helpers.
- `FUN_bfc19240`: samples eight bus bits into one byte.
- `FUN_bfc19060`: sends a byte sequence while polling the bus-ready helper.
- `FUN_bfc19114`: receives a byte sequence.

The entry-adjacent functions `FUN_bfc18d08` and `FUN_bfc18d1c` return zero;
`FUN_bfc18d30` and `FUN_bfc18d70` perform line setup/teardown around the
context. The `drv_dac` name is therefore consistent with a codec control bus,
not with PCM decoding.

## Consequence for the requested playback work

This driver can explain how a higher layer writes codec registers, but it does
not tell us which register controls volume, mute, ramping, or fade-out. Those
meanings require tracing callers and the codec register tables. The DSP files
(`ad*.dsp`) remain separate and unexamined; they should not be treated as
solved by this driver analysis.

No firmware patch is proposed. The safe next step is to locate callers of the
DAC context/API in the resident audio path and correlate their arguments with
the existing fade/volume state machine. Without that caller trace, changing
these bit operations would risk silencing the device or leaving the codec
bus in an invalid state.
