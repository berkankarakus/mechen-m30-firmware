# M30 key driver: static boundary

This note records the first analysis of `key.drv`. It is a Ghidra/static-byte
result, not a physical key trace and not a complete model of the ATJ2127 input
peripheral.

## Reproducible checks

The binary contract is checked by:

```sh
PYTHONPATH=tools/emu python3 tools/emu/key_binary_probe.py \
  analysis/community/fw/key.drv
```

The resident MIPS16 functions are mapped and decompiled by:

```sh
bash tools/ghidra/run_key_probe.sh analysis/community/fw/key.drv
```

The extracted `key.drv` SHA-256 is identical in the local community, stock,
first-pass, V1.101.11, V1.101.12, and V5 directories:

```text
858d56ff19106fccb75e35552c9cecca99dce0579c7daac5dce376d742f67ba1
```

Thus the key driver is not a community-only change in the available corpus.

## Container and mapping

`key.drv` is a compact `yqhx` image:

| Field | Value |
|---|---:|
| resident file offset | `0x200` |
| resident length | `0xa00` |
| resident destination | `0xbfc10000` |
| BSS | `0x9fc14328`, `0xd6` bytes |
| header entry field | `0x290094c4` |

For `FlatLoad.java`, file byte zero is therefore represented by virtual
address `0xbfc0fe00`; file `0x200` maps to `0xbfc10000`. The segment is
MIPS16 and the current static pass discovers nine SAVE-prologue functions.

## Functions and observed roles

| Function | Evidence-backed role |
|---|---|
| `FUN_bfc10008` | initial hardware/configuration writes and a control syscall |
| `FUN_bfc10084` | periodic state/control update; emits `0xf0` or `0xf1` through a driver callback |
| `FUN_bfc10178` | samples a 7-bit hardware value, classifies it against thresholds, and returns a normalized table value |
| `FUN_bfc101f4` | packages a key/event value and submits it through the driver callback |
| `FUN_bfc10220` | translates a normalized value into event messages and repeat events |
| `FUN_bfc102e4` | main scan/debounce state machine; calls the hardware update and classifier |
| `FUN_bfc103cc` | periodic sampling/state update; touches the input-control registers |
| `FUN_bfc10508` | thin wrapper around the indirect driver operation |
| `FUN_bfc10518` | applies two bounded configuration bytes, updates a control register, and resets state |

`FUN_bfc10178` reads the sampled value from a hardware-mapped location, masks
it with `0x7f`, and compares it against the resident threshold table at
`0xbfc103c0` (file offset `0x5c0`):

```text
03 18 2a 3a 4a 5f 6f 00
```

The final zero is the terminator. The function maps the selected range through
a RAM-resident table; that RAM table is initialized outside the `key.drv`
payload, so the physical key names cannot be recovered from this file alone.

`FUN_bfc10220` has three explicit special input values (`0x30`, `0x32`, and
`0x34`) and a repeat path. When a value remains unchanged, the state counter
reaches a first repeat event of `0x1000` and a subsequent event of `0x800`.
The exact system-message meaning is not assigned here because the consumer
and the hardware callback ABI are not yet proven.

## What this does and does not answer

This explains why the device can continue to react to keys while the display
is off: key sampling and event generation are in a resident driver path, not
in the now-playing UI overlay. It also gives us a safe boundary for a host
model of debounce/repeat behavior.

It does **not** yet prove:

- which physical button corresponds to each normalized value;
- the meaning of the hardware registers or the callback at the header entry
  field `0x290094c4`;
- whether any key event forces the LCD/backlight on;
- the complete event-consumer path in the applications;
- timing values in real milliseconds.

No flashable patch is proposed from this analysis. The next safe step is to
trace the consumer of the normalized events in `music.ap`, `browser.ap`, and
the resident kernel, then add only the proven event contract to the host
emulator.
