# M30 `aud_dev.drv`: banked audio-device service

`aud_dev.drv` contains a small resident stub, a loaded far-pointer table, and
banked MIPS16 code. Its ROM dispatch boundary and hardware-facing effects are
still only partly understood.

## Reproducible checks

```sh
PYTHONPATH=tools/emu python3 tools/emu/auddev_binary_probe.py \
  analysis/community/fw/aud_dev.drv
```

`tools/ghidra/run_auddev_bank_probe.sh` is retained as an exploratory
disassembly, not as a validated bank-loader probe. Its assumed A/B table
layout is not established for `aud_dev.drv`; likewise,
`tools/inspect_drv.py` expects a different compact start/end table. Do not use
either tool's generic bank-table interpretation as proof of an aud_dev file
mapping.

The member is byte-identical in the local community, stock, first-pass,
V1.101.11, V1.101.12, and V5 extractions. SHA-256:

```text
3349287198faaa90a503353673674d5628e85711db9ee16217db5a803484f09c
```

## YQHX segments and the far-pointer table

The header has four segment descriptors. The fourth descriptor at header
offset `0x2c` loads the 21-word table from file `0x200`, length `0x54`, to
`0x9fc09f00`. The resident stub is file `0x300`, length 8, at `0xbfc09f58`.
The other two descriptors are empty; BSS size is zero and the entry field is
`0x1c009000`. `tools/emu/yqhx.py` currently parses all four descriptors and
includes this table in its load plan; `test_yqhx.py` covers the fourth entry.

The resident bytes `10 6b 05 e8 0f 6b 05 e8` are MIPS16 `break 0` stubs for
modules `0x10` and `0x0f`. They are not the COP2-looking words at file `0x200`.
The loaded table begins `25 9b 08 2c 91 9b 08 2c`; entry 18 at file `0x248`
is `0x2c149401`.

The reported nonzero payload starts are
`0x500, 0x800, 0xe00, 0x1600, 0x1700, 0x1f00, 0x2500, 0x2900`. The proposed
far-pointer encoding is `0x2c000000 | (bank << 18) | window_offset`; entry 18
`0x2c149401` therefore identifies slot `0x0c`, bank 5, and MIPS16 window
offset `0x9401` (aligned address `0x9400`). The file mapping of bank 5 to
`0x1f00` is supported by the independent reference `0x2c149958` at file
`0x240c`, which resolves to the `spk_comp.dat` name at file `0x2458` under that
mapping. File `0x2500` is the next bank (bank 6), not bank 5. These are static
address correlations; the generic `inspect_drv.py` and the current
`run_auddev_bank_probe.sh` table assumptions do not validate the aud_dev bank
loader or its runtime mapping. The existing `driver_banks.py` parser is
specific to the `drv_ui.drv` layout and does not parse this member's table.

## Operation dispatch and EQ shared memory

`mmm_pp.al` calls module `0x0c`, op `0x12` with argument 0 equal to `1` and
argument 1 pointing to `dae_cfg` shared memory. Other calls use argument 0
values `0`, `2`, and `3`. The proposed table-index-equals-op mapping is a
strong inference: the 13 observed operation calls align with their table
entries, while shifts of one entry do not. The fixed-ROM dispatcher is absent,
so the mapping is not proven.

Under that candidate mapping, entry 18 points to the MIPS16 bytes at `0x9400`.
The reported static Ghidra analysis of that file range says the `id=1` path checks
`SHM+7`, reads flags and values around `SHM+3..+0xd`, consumes sixteen
8-byte bands from `SHM+0x10..+0x8f`, and reads gain adjustments from
`SHM+0xc0..+0xcb` into a structure at `cfg+0x94`. This is the first evidence
that the EQ shared-memory band area reaches an audio-device routine. Because
the ROM dispatch mapping is not proven, treat the association between op
`0x12` and this entry as an inference.

The same routine is reported to handle `id=0` with a rate structure
`{2, rate*1000, 0x80}`, including a 44000-to-44100 adjustment; entry 19 is
reported as a getter. The producer's EQ builder writes seven bands and clears
bands 7–15, while the consumer reads sixteen. That shape is consistent with
the observed `0xf0`-byte shared-memory structure; it does not show how the
values become audible DSP coefficients.

`tools/ghidra/run_auddev_eq_copy_probe.sh` executes the candidate bank-5 entry
at `0x9400` with either a synthetic payload or an optional `0xf0`-byte EQ
structure. It pins the driver SHA-256 and the Ghidra script checks that the
mapped code bytes match file offset `0x1f00` before execution. Real MIPS16 instructions make 16
calls through the slot at `0x98fc`, whose image value is `0xbfc09f59`, the odd
pointer to the resident module-`0x10` `break 0` stub. The captured call shape is
`a0=0x9fc34094+8*i`, `a1=source+0x10+8*i`, `a2=8`, `a3=0` for `i=0..15`;
the run took 907 p-code steps. The probe now services each call with an
explicit candidate `memcpy(a0,a1,a2)` shim and verifies all 16 destination
bands byte-for-byte against their source. The MIPS16 caller and its addresses
are real; the copy operation is a hypothesis from the shared call shape, not
the unavailable fixed-ROM implementation. This closes the caller's local
data-layout check under that shim, but does not prove ROM dispatch, DSP
coefficient use, or audible output.

`tools/ghidra/run_eq_auddev_chain_probe.sh` runs the real `mengine.ap` builder
for Off, Hip-hop, and default Custom, then feeds the resulting `0xf0`-byte
buffers to the candidate `aud_dev` consumer. The harness initializes the
builder buffer with `0xaa`, so the seven active band records and zeroed
inactive band region are produced by the builder, while trailing adjustment
bytes are deliberately preserved sentinels, not firmware defaults. For each
preset, the chain passes three tail cases: preserved sentinels, a synthetic
zeroed adjustment area, and synthetic low/high threshold-and-gain settings.
The candidate MIPS16 code's observed gain adjustments match those settings
band by band, and all 16 destination records are checked under the same
synthetic module-`0x10` memcpy shim. This verifies the candidate consumer's
record layout and adjustment arithmetic for these inputs; it does not prove
ROM dispatch, the actual service implementation, runtime tail values, DSP
consumption, or audible difference.

The banked code also references `spk_comp.dat`, a speaker-compensation filter
asset. Its relation to EQ gain processing and the downstream coefficient or
DSP path remains unknown. `drv_dac.drv` register writes and the fixed-ROM
operation dispatcher are the next static targets.

## Emulator boundary

The host YQHX parser now records four segment descriptors, including this
table segment. The aud_dev binary probe checks both nonempty segments and the
far-table word. This models the file's declared load layout; it does not
execute the banked code, emulate the ROM dispatcher, or model audio hardware.

`tools/sim/auddev_driver.py` also models the observed MMIO read/modify/write
effects for candidate operations 4, 6, and 8. The formulas come from the
banked MIPS16 routines and their literal pools; the model requires callers to
provide each input register word and returns the observed zero result. It
does not claim that the missing ROM dispatcher selects these routines with
`table[op]`.

Operation 6 writes the low nibble of `0xc0000110` to 6, or to 2 for codes
`0x0b`, `0x16`, and `0x2c`. It selects the low three bits of
`0xc000100c` from the observed input-code table. When bit 0 of `0xc0052000`
is set, the selector is adjusted by the modeled branches; interpreting the
input as a sample-rate code is an inference. The firmware stores the
`0xc000100c` selector only when its computed value differs from the current
value; the host model preserves that conditional store.

Operation 4 updates `0xc0000000`, `0xc0050000`, `0xc005001c`, and
`0xc0050004`. Operation 8 updates either `0xc0051010` or, for argument 0
equal to 4, `0xc0090060` and `0xc0051000`. The model keeps these operations
numbered because their higher-level meanings have not been established.
Seventeen host tests cover the formulas, branch cases, conditional stores,
input validation, and
no-partial-write behavior; they validate the model implementation, not the
firmware-to-ROM dispatch boundary or physical register effects.

Remaining unknowns include whether the ROM dispatcher indexes the table
directly by op, the exact behavior of non-EQ operations, `spk_comp.dat`
consumption, and the coefficient/DSP output path. No firmware patch or device
write has been made.
