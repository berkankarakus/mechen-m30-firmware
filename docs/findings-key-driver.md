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

The host emulator also exposes the proven ADC classifier in
`tools/sim/key_driver.py`: it masks samples to seven bits, applies the seven
resident thresholds, returns `0xff` when no threshold matches, and keeps the
RAM-supplied normalized values explicit. The override path likewise requires
its external table value. `KeyDriverRepeatState` now carries the proven event
boundary into the application model: a new normalized value emits `0x2000`,
the fifth identical sample emits `0x1000`, and subsequent identical samples
emit `0x800`. The explicit `0x30` release, `0x32` to normalized key `0x0c`,
and `0x34` to normalized key `0x0d` paths are represented as well. The
external callback side effect, physical button names, and MMIO register
meanings remain unmodeled.

`tools/ghidra/run_key_classifier_matrix.sh` executes the real MIPS16
`FUN_bfc10178` against all 256 input bytes with the override MMIO bit both
clear and set. The code and threshold table remain from the extracted
`key.drv`; synthetic MMIO is mapped at the literal addresses `0xc0020028` and
`0xc0020054`, and the driver's BSS is mapped at its real address
`0x9fc14328`. Seven distinct caller-supplied values occupy B+9 through B+15,
and the override value occupies B+8. All 512 results match
`classify_adc_sample()`, including high-bit aliases, threshold boundaries, and
the override branch. This verifies the classifier routine and table indexing;
it does not populate the unknown runtime normalization table or model
electrical ADC sampling.

The normalized-value table initializer remains unresolved. Scanning 1,311
files across `analysis/{community,first-pass-verify,local-evidence,stock,
v1.101.11,v1.101.12,v5}` and the 12 dated extracted corpora, including
`afi/FWIMAGE.FW`, `dec.bin`, and `fw/*`, found pointer words into the key BSS
only in `key.drv` and exact embedded copies of that driver in the containers.
The corpus reduced to 251 unique files by SHA-256. The scan checked
halfword-aligned words in the `0x9fc14300..0x9fc143ff`,
`0xbfc14300..0xbfc143ff`, and `0x1fc14300..0x1fc143ff` windows. All 14
`key.drv` copies share SHA-256
`858d56ff19106fccb75e35552c9cecca99dce0579c7daac5dce376d742f67ba1`.

This is negative evidence against a direct literal-pointer initializer in
those files, not proof that no computed or indirect initializer exists. An
earlier attribution to a “module 5, selector 0x18” call from
`FUN_bfc10008` was incorrect. In the key driver's syscall envelope, module
`0x0f` is selected by the immediate `li v1, 0x0f` before `break 0`; values
such as `5` and `6` are arguments. `FUN_bfc10084` sends its stack-backed
`0xf0`/`0xf1` event word with arguments `(5, buffer, 0, 0x18)`, while
`FUN_bfc10008` contains `(6, 0, 0, 0x1a)` and `(6, buffer, 0, 0x18)` calls.
The SDK maps module `0x0f` operations `0x18`, `0x19`, and `0x1a` to
`MQ_SEND`, `MQ_RECEIVE`, and `MQ_FLUSH`; the M30 call shapes structurally
match that mapping. These queue calls do not identify the key normalization
table initializer.

The SDK's key path provides a separate lead: `key_rcode_scan.c` indexes
`key_map[i + 1]` for ADC ranges and `key_map[0]` for override, matching the
M30 driver's B+9+i and B+8 reads. SDK configuration code obtains the table
address from the installed key driver and copies 16 bytes from `keyID` into
it. This is verified SDK behavior; identifying the corresponding M30
configuration path is still a hypothesis. `manager.ap` contains the
`key.drv` name, but the config record layout has not been recovered. No
writer to B+8..B+15 has been found in `key.drv`; runtime values remain
unobserved.

## Kernel exception-vector table (separate from the key table)

The kernel exception table is now statically traced, and must not be confused
with the key driver's BSS normalization table. `ker_init.bin` has SHA-256
`f4c62848fb06ccbe6fba4323c4e29e46791c1abb25af648f0518eb0747492ec8` and
maps at `0xbfc32000`. Its entry flow calls the table constructor at
`0xbfc32bc8`; the constructor calls the MIPS16 setter at `0xbfc330a0`, which
stores `table[a0] = a1` at table base `0x9fc1a9a4`. The base pointer is the
literal at file offset `0x10dc` / VA `0xbfc330dc`. The setter accepts indices
0 through 13 and rejects a zero handler.

The constructor writes index 9 as `0xbfc06f18` (setter call at file offset
`0xc54` / VA `0xbfc32c54`). `kernel.drv` has SHA-256
`58f9d0c62bdbdab7cfeee1c5e65bbe8b88ee962f8eecd3dd0515d1a1056d8bd6`; its
MIPS32 exception vector at file offset `0x380` / VA `0xbfc08180` loads the
handler from `0x9fc1a9a4 + (Cause & 0x7c)`. ExcCode 9 therefore reads entry
`0x9fc1a9c8`, whose statically installed value is `0xbfc06f18`. The earlier
expected value `0xbfc34075` is disproved by this init-time write.

This establishes the extracted kernel's static table setup and vector lookup,
not runtime immutability or the handler's behavior. The target `0xbfc06f18`
is in the unavailable fixed ROM. No static link has been established from
that ROM handler to `ker_xsys.bin` entry `0xbfc34074`; that possible handoff
remains a hypothesis. The M30 key normalization table at B+8..B+15 is a
different table and remains unresolved.

The extracted `ker_init.bin` constructor at `0xbfc32bc8` has now been
executed in Ghidra p-code with its real MIPS16 setter at `0xbfc330a0` and a
sentinel-backed synthetic RAM table. `tools/ghidra/run_kernel_exception_table_init_probe.sh`
stops at `0xbfc32c5c`, immediately after the setter calls and before later
global initialization or fixed-ROM calls. The run verified all 14 accepted
slots: indices 0, 9, and 10 contain their constructor overrides, while the
other 11 contain `0xbfc19a75`; all 18 out-of-range slots 14..31 retain their
sentinels. This executes the extracted constructor logic, not the device boot
sequence; it does not establish that a particular device actually invoked
this constructor or reveal fixed-ROM behavior.

The public firmware changelog supplies a second, application-level distinction:
2022-08-16 says that the scroll wheel and all buttons are disabled while
locked, while 2022-08-05 and 2024-02-28 explicitly retain play/pause,
previous/next, and volume controls. `tools/sim/key_filter.py` now represents
these two observed policies as `WAKE_ONLY` and `MEDIA_KEYS_PASS`. The existing
`patched=True` argument remains a compatibility alias for the latter; this
does not assign physical names to normalized key values or claim a debounce
timing.

`tools/sim/key_input.py` composes these proven boundaries into one sample
session: caller-supplied ADC normalization values and override value pass
through classification, repeat-state event generation, and the selected
application key-filter policy. Each sample trace retains the classification,
optional driver event, and optional filter decision. Repeat counts remain
sample counts; the model assigns no physical key labels or real-time cadence.

It does **not** yet prove:

- which physical button corresponds to each normalized value;
- the meaning of the hardware registers or the callback at the header entry
  field `0x290094c4`;
- whether any key event forces the LCD/backlight on;
- application-specific consumers beyond the shared key filter;
- timing values in real milliseconds.

No flashable patch is proposed from this analysis. Further progress on this
path needs evidence for the RAM normalization table, physical ADC mapping, or
real sampling cadence; these are left as caller-provided or unresolved.
