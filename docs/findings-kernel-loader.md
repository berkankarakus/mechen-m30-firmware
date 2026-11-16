# Kernel driver loader and UI bank addresses

This note records the first resident/kernel-side evidence for the `yqhx`
driver format. It is based on the extracted community image and cross-checked
against the archived stock images. It does not claim a complete ATJ2127 boot
emulation.

## Stable image evidence

`kernel.drv` and `drv_ui.drv` are byte-identical in all six locally archived
images (`stock`, `v1.101.11`, `v1.101.12`, `v5`, `community`, and
`first-pass-verify`). Their hashes are:

```text
kernel.drv  58f9d0c62bdbdab7cfeee1c5e65bbe8b88ee962f8eecd3dd0515d1a1056d8bd6
drv_ui.drv  011f4e6a50738026ac641370f493c5df2e59adc435871d8a213e717604d2576a
```

This means the loader observations below apply to the firmware versions we
have been comparing, rather than to one community-only variant.

## Resident addresses

The firmware's `dec.bin` contains the fixed kernel-component address table.
Two mappings are independently supported by code references:

- `ker_init.bin` at `0xbfc32000`: its code forms pointers such as
  `0xbfc32fac`, which land on the local data/string area in that segment.
- `kernel.drv` at `0xbfc08000`: this is also the EBase value installed by the
  kernel init routine (`FUN_bfc32224`).

The headless Ghidra dumps used for these findings are generated outside the
repository under `/private/tmp/m30-kernel.c` and `/private/tmp/m30-kerinit.c`.
The raw input files in the repository remain unchanged.

## Resident driver-loader behavior

The two decompiled resident routines use the same three-segment `yqhx`
contract but have separate driver-state tables. The host-side parser and
load-plan model is now in `tools/emu/yqhx.py`; `ResidentMemory` in
`tools/emu/driver_loader.py` can apply the verified file copies and BSS zeroing
without pretending to execute an unverified bank.

### `FUN_bfc0a408`

`kernel.drv`, loaded at `0xbfc08000`, contains the routine
`FUN_bfc0a408` at `0xbfc0a408`. The decompilation shows this sequence:

1. Select a per-driver slot from the group/mode argument.
2. Open the requested file.
3. Read `0x4c` bytes from its beginning.
4. Require the four-byte magic at header offset `+0x04` to be `yqhx`.
5. Iterate three `(file_offset, length, destination)` triples beginning at
   header offset `+0x08`; zero-length entries are skipped.
6. Clear the BSS described by the header fields at `+0x38` and `+0x3c`.
7. Save the installed handle/state and invoke the driver entry callback using
   the header's trailing entry fields.

The routine is not itself the proof that every overlay bank is copied on every
call. It does, however, establish that the UI driver header is consumed by a
resident kernel loader and that the file is not simply executed at its flash
file offset.

The same decompilation contains a mode-dependent slot calculation: modes 6
and 7 use a four-byte slot stride, while other modes use a twelve-byte stride.
This is exposed as `slot_layout()` in `tools/emu/yqhx.py`; it is a structural
constraint for the emulator, not a claim that every mode has been identified.

### `FUN_bfc0a578`

The neighboring loader reads `0x44` bytes, uses a separate resident table,
parses the same three segment triples at `+0x08`, clears BSS using `+0x38` and
`+0x3c`, and stores the installed state plus a separate `+0x240` value. It
does not call the header's entry/context callback. The shorter read means its
surrounding ABI is not identical to `FUN_bfc0a408`, even though the copy/BSS
portion is compatible with the `yqhx` model. We therefore model the common
header and keep the two resident dispatch tables separate until their callers
are mapped. The executable host model is `tools/emu/driver_loader.py`.

Both function boundaries are reproducible with:

```sh
bash tools/ghidra/run_kernel_loader_probe.sh analysis/community/fw/kernel.drv
```

## `ker_xsys` exception-vector evidence

The extracted firmware's `fw.log` gives the fixed offsets and sizes of the
kernel support members: `kernel.drv` at `0x2000..0x6c00`, `ker_text.bin` at
`0x6c00..0x7800`, `ker_init.bin` at `0x7800..0x9000`, `ker_data.bin` at
`0x9000..0x9200`, and `ker_xsys.bin` at `0x9200..0x9a00` in `FWIMAGE.FW`.

Direct MIPS32 disassembly of `ker_xsys.bin` at its established runtime base
`0xbfc34000` shows that the exception entry at `0xbfc34074` reads COP0 EPC,
saves it at `0x13dd8`, saves the return address at `0x13ddc`, and jumps to
the fixed address `0xbfc06d6c`. The neighboring entry at `0xbfc340a4` reads a
byte at `0x9fc1a495`, indexes a four-byte table beginning at `0xbfc19974`,
and compares the result with `SP & 0x3ffff` before selecting an alternate
exception stack.

This is relevant to far calls because it proves that an exception/dispatch
path exists outside the extracted UI driver. It does **not** yet prove that
the `0x3ffff` comparison performs bank loading: the same code can be an
exception-stack guard, and the final `0xbfc06d6c` handler is in fixed ROM or
another component not present in the extracted `.drv` members. The current
emulator therefore keeps far entries lazy and unresolved. The multi-segment
Ghidra mapping used for this check is reproducible with
`tools/ghidra/MapSegments.java`.

A byte-signature sweep across the extracted `FWIMAGE.FW`, `kernel.drv`,
`NORHWSC.BIN`, `NORFWSC.BIN`, and all `ker_*.bin` members finds the exact
`0xbfc06d6c` sequence only in `ker_xsys.bin` as a jump target; no extracted
member contains the handler body. The reproducible probe is:

```sh
bash tools/ghidra/run_kernel_exception_probe.sh
```

For the present image, the safest interpretation is “firmware exception entry
into an unavailable fixed handler”, not “a complete bank loader recovered”.

## `drv_ui.drv` header and public bank formula

For the M30 `drv_ui.drv` header, the group-start fields are:

```text
header + 0x48 = 0x00001600   A group file start
header + 0x4c = 0x00006600   B group file start
header + 0x50 = 0x00010600   C group file start
```

The public ATJ2127 SDK's `link_base.xn` and `ui_driver.xn` define the
corresponding bank windows as:

```text
A bank 0: 0x16024c00, size 0x400
B bank 0: 0x26025000, size 0x800
C bank 0: 0x36021a00, size 0x400
next bank: +0x40000
```

The M30 bank table has the same three groups and the same bank sizes. This
makes the public formula a high-confidence runtime-address candidate for the
M30 image, and it is now exposed by `tools/inspect_drv.py --runtime-base`.
The final M30-specific proof still requires following the kernel's indirect
bank-window lookup or observing a resident pointer at runtime; the tool keeps
the label `public_runtime` to avoid silently presenting a candidate as a
hardware observation.

## Cross-version bank corpus check

The six locally archived `drv_ui.drv` files (`stock`, `v1.101.11`,
`v1.101.12`, `v5`, `community`, and `first-pass-verify`) are identical at
the byte level: each is 75,264 bytes and exposes exactly 24 banks:

```text
A00-A09  B00-B09  C00-C03
```

None of those six images contains A19 or B16. The A19/B16-qualified pointers
in the B3 literal pool are therefore not alternate copies hidden in another
locally archived M30 UI driver. They remain external-provider or
resident-dispatch candidates, which is why `LazyBankRuntime` records them but
does not execute them.

A second scan across every extracted `.drv` member in the community image found
the same negative result: the five exact little-endian pointer values
`0x164c9001`, `0x164c90ed`, `0x26089471`, `0x260894e9`, and `0x26409401` occur
within `drv_ui.drv` (including its B3 literal pool and related embedded
code/literal regions), but not as payload occurrences in the other driver
files (`kernel.drv`, `drv_lcd.drv`, `drv_dac.drv`, storage, USB, key, and audio
drivers). The copies in `dec.bin`/`FWIMAGE.FW` are container-level duplicates
of those firmware bytes. The scan is reproducible with:

```sh
PYTHONPATH=tools/emu python3 tools/emu/provider_scan.py analysis/community/fw
```

The same scan widened to every extracted firmware member (`--all-files`)
produces exactly the same 16 occurrences, all still in `drv_ui.drv`; no `.ap`,
`.sty`, `.bin`, DSP, or other extracted file provides a second copy of any
observed far pointer. This closes the remaining local-file provider search
without claiming anything about fixed ROM.

```sh
PYTHONPATH=tools/emu python3 tools/emu/provider_scan.py \
  --all-files analysis/community/fw
```

For the provider-only negative check, exclude the known consumer that owns the
literal pool:

```sh
PYTHONPATH=tools/emu python3 tools/emu/provider_scan.py \
  --all-files analysis/community/fw --exclude-name drv_ui.drv --require-zero
```

This currently finds zero copies of the A17/A19/B16 values in the other
extracted members. The unfiltered scan is still useful because it records the
consumer-side occurrences and their offsets.

The raw-byte scan was also rerun for the six resident loader/mask addresses
and the `0xbfc06d6c` exception target across every extracted member. All seven
values have zero little-endian occurrences in the local tree. This agrees
with the Ghidra reference result and further narrows the missing call path to
indirect runtime tables or fixed ROM rather than an overlooked extracted
literal.

The resident `kernel.drv` was also scanned at its established `0xbfc08000`
base for constants relevant to the proposed far-pointer translation. It
contains no literal `0x00009000` prefix and no literal `0x00025000` B-window
base. It does contain one `0x0003ffff` mask at `0xbfc0a9ac`, consumed as a
generic address mask by `FUN_bfc0a944`, plus unrelated `0x400` and `0x40000`
constants. This does not identify a bank-window translator; it is negative
evidence against placing the observed `0x9000` conversion directly in the
extracted resident image. The check is reproducible with:

```sh
bash tools/ghidra/run_kernel_bank_boundary_probe.sh \
  analysis/community/fw/kernel.drv
```

This rules out the simplest explanation that A19/B16 are provided by a second
extracted driver; the remaining search boundary is the resident dispatcher or
unavailable fixed ROM code.

### External ATJ2127 overlay cross-check

The public `actions_flash` reverse-engineering notes for a different ATJ2127
device/firmware describe a YQHX overlay window and tagged MIPS16 pointers of
the form `0x73...5a00...`. This is useful architecture evidence, but it is not
automatically an M30 ABI: the target notes identify an Actions US212D image at
V1.101.25, not the M30 image analyzed here. See the
[`actions_flash` RE notes](https://github.com/kilicdev/actions_flash/blob/main/RE_NOTES.md#12-binary-executable-format--overlay-system-yqhx).

As a local compatibility check, the M30 extracted `.ap`, `.drv`, and `.bin`
members were scanned for the exact masked signature
`(word & 0xff00ff00) == 0x73005a00`; the result was zero occurrences. The
observed M30 pointers (`0x164c...` and `0x2608...`) therefore must not be
rewritten using that external tag formula without a new M30-specific proof.
The scan is reproducible with:

```sh
PYTHONPATH=tools/emu python3 tools/emu/scan_pointer_signature.py \
  --require-zero analysis/community/fw
```

The Ghidra-side occurrence probe adds the next boundary check:

```sh
bash tools/ghidra/run_drvui_pointer_probe.sh analysis/community/fw/drv_ui.drv
```

It finds 16 little-endian occurrences across the five values, all inside the
flat `drv_ui.drv` corpus. In that mapping Ghidra assigns no occurrence to a
recognized function body, which is consistent with literal pools or embedded
data. Because the flat loader's function discovery is heuristic, this is
supporting evidence only; the runtime B3 remap remains the stronger function
boundary for the `0x9924` pool. The full-file probe reports these file offsets:

```text
0x164c9001: 0x891c, 0x9964, 0xceec, 0x112d8
0x164c90ed: 0x8308, 0x8914, 0x9038, 0x992c, 0xced4
0x26089471: 0x8b58, 0x995c, 0xcee8
0x260894e9: 0x8b5c, 0x9960
0x26409401: 0x8938, 0x996c
```

Grouping those hits with a `0x40`-byte gap threshold produces seven clusters.
The B3 literal pool is the five-hit cluster at `0x992c..0x996c`; the other
clusters are nearby code/data regions or isolated copies. This is reproduced
by:

```sh
bash tools/ghidra/run_drvui_pointer_cluster_probe.sh \
  analysis/community/fw/drv_ui.drv
```

The cluster report is provenance evidence, not a claim that every nearby word
is executable code. The runtime B3 remap and the separate B02 probe remain the
authority for code-entry classification.

## Consequence for the marquee investigation

The fourth B window begins at file offset `0x9680`; the static marquee routine
starts at `0x9674`, immediately before that payload boundary. With B3 mapped
at `0x260e5000`, the function begins at `0x260e4ff4` (the same 12-byte
lead-in relationship). A full Ghidra remap of the B3 bytes decompiles this
address cleanly and reproduces the expected behavior: it clears `0x7c`
pixels, reads the two text records, applies the active width/offset state, and
submits the resulting text rectangles.

This is a strong static/runtime-address confirmation of the public bank
formula and of the marquee candidate. It is still not a physical-device
trace, so it should be used for emulation and call-edge work before any patch
is built.

The remap is reproducible with:

```sh
bash tools/ghidra/run_drvui_runtime_probe.sh
```

## B3 literal-pool call classification

The runtime remap puts the B3 literal pool at `0x260e52a4`, corresponding to
`drv_ui.drv` file offset `0x9924`. The important values are:

| Pool address | Value | Current classification |
|---|---:|---|
| `0x260e52ac` | `0x164c90ed` | bank-qualified external UI entry; target bank bits identify A group 6, bank 19 |
| `0x260e52b0` | `0xbfc09ce1` | resident UI entry near `bfc09ce0` |
| `0x260e52bc` | `0xbfc09c01` | resident system-operation entry; the even-address disassembly is a trap/syscall stub, not the clear implementation itself |
| `0x260e52c0` | `0xbfc0a8bd` | resident UI state setter at `FUN_bfc0a8bc` |
| `0x260e52c4` | `0xbfc0a8c9` | resident UI state setter at `FUN_bfc0a8c8` |
| `0x260e52dc` | `0x26089471` | bank-qualified external UI entry; target bank bits identify B group 6, bank 2 |
| `0x260e52e0` | `0x260894e9` | second entry in the same B2-qualified region |
| `0x260e52ec` | `0x26409401` | bank-qualified external UI entry; target bank bits identify B group 6, bank 16 |
| `0x260e52f0` | `0x9fc0bf98` | resident RAM callback/state pointer |
| `0x260e52f4` | `0x9fc0bf84` | resident RAM callback/state pointer |

The resident targets were checked by remapping the `drv_ui` resident sections
at `0xbfc09c00` and `0xbfc0a800`. The bank-qualified values have the expected
Actions address encoding, but their low-offset entry/stub area is not the
`0x25000` overlay window itself. They should therefore be modeled as lazy bank
entries first; treating them as ordinary direct calls would skip the bank
manager behavior that QEMU still lacks.

The resident remap is reproducible with:

```sh
bash tools/ghidra/run_drvui_resident_probe.sh analysis/community/fw/drv_ui.drv
```

It confirms that `0xbfc09ce0` is a no-op return, `0xbfc09c00` is a trap/syscall
wrapper, and `0xbfc0a8bc`/`0xbfc0a8c8` write the two resident state slots used by
the B3 path. The instruction dump also shows a second trap entry at
`0xbfc09c04`; therefore the B3 odd pointer `0xbfc09c05` must be modeled as a
MIPS16 pointer to that second entry, not as a simple alias of `0xbfc09c00`.
These are extracted resident helpers, not the missing A19/B16 providers or proof
of the ROM bank translator.

The B3 call shapes narrow down the semantic roles without pretending that the
M30 bank table is complete:

| Pointer | B3 call shape | Strongest public-SDK match | Confidence |
|---|---|---|---|
| `0x164c90ed` | one display-mode argument | `fix_switch_fontlib` in A19 | high |
| `0x164c9001` | descriptor, max width, result | `fixf_get_string_length` in A19 | high |
| `0x26089471` | first one-argument Arabic/Hebrew transform | `arabic_uni_join` in B2 | medium |
| `0x260894e9` | second one-argument Arabic/Hebrew transform | `arabic_ascii_turn` in B2 | medium |
| `0x26409401` | descriptor, region, mode | `put_string_line_sdimage` in B16 | high |

This is now represented by the host-only classifier in
`tools/sim/ui_calls.py`. It deliberately returns no label for an unobserved
pointer. The distinction matters: the M30 `drv_ui.drv` table currently ends at
A09/B09/C03, so A19 and B16 are not proven to be payloads in this particular
driver file. The public headers establish the signatures and the B3 call sites
establish the argument shapes, but the resident/provider that services these
far pointers remains to be mapped.

### Public A17 source-role cross-check

The public ATJ2127 UI linker script assigns `BANK_A_17` to
`bank_a_ui_putstring_sub_2.o`, not to a generic LCD-fill module. The matching
source file contains `bankaf_put_string_line_arabic_hook()`, `char_out_rect()`,
and `load_bgpic_sd()`: it prepares text for Arabic/RTL rendering, chooses
left-to-right or right-to-left character output, and records the background
image used by the SD-image text path. The source and linker script are
available in the public [PD196_ATJ2127 UI driver](https://github.com/Suber/PD196_ATJ2127/tree/maint/case/drv/ui)
reference tree.

This is useful role evidence for the unresolved M30 resident target
`0x164490a1` (`A17 + 0x0a1`). M30's `0xbfc09e34` forwarder passes three
arguments to that target only for a restricted display-mode/state range, which
is compatible with a text/provider hook. It does **not** prove that the M30
target has the public source's exact offset or implementation, and it does not
identify the marquee's solid-color or background-restore helper. The public
source therefore narrows the next search to the text/provider dispatch
boundary while leaving the host emulator fail-closed.

There is one additional loader clue. All five observed far entries use the
same `0x9000` logical prefix in their low offset. Subtracting that prefix gives
the following candidate offset in the corresponding overlay window:

```text
0x164c9001 -> A19 + 0x001
0x164c90ed -> A19 + 0x0ed
0x26089471 -> B02 + 0x471
0x260894e9 -> B02 + 0x4e9
0x26409401 -> B16 + 0x401
```

The B02 `+0x471` candidate lands on valid MIPS16 code when the real B02
payload is mapped at `0x260a5000`; Ghidra identifies it as a thunk into the
bank body. The pointer's low MIPS16 bit means the decompiler entry is the
aligned address `0x260a5470` (file offset `0x8af0`), while the host candidate
retains payload offset `0x471` from the pointer value. This is stronger than a
numeric coincidence, but it does not yet prove how the hardware or resident
loader translates the `0x9000` prefix, so the host model exposes it as
`payload_offset` and never executes the far pointer directly. The reproducible
probe is:

```sh
bash tools/ghidra/run_drvui_b2_probe.sh analysis/community/fw/drv_ui.drv
```

The paired B02 `+0x4e9` candidate is a useful negative result. Under the same
candidate mapping it lands at `drv_ui.drv` file offset `0x8b69`, inside the
literal/data area following the nearby B02 code; Ghidra reports bad
instruction data there. Therefore the second B3 call must not be emulated by
blindly jumping to `B02 + 0x4e9`. It may use a different lazy-entry/stub
translation, or the literal value may be an address into a provider not
present in this M30 `drv_ui.drv`. The host model now preserves both the bank
and candidate payload offset, while leaving code-entry validation separate.

As a separate cross-check, Ghidra's reference manager finds zero direct code
or data references in `kernel.drv` to the six recovered loader/mask candidates
(`FUN_bfc0a408`, `FUN_bfc0a578`, `FUN_bfc0a6a0`, `FUN_bfc0a808`,
`FUN_bfc0a944`, and `FUN_bfc0ac98`). Their bodies are present, but calls are
therefore likely reached through resident function tables, indirect pointers,
or code outside this extracted image. The check is reproducible with:

```sh
bash tools/ghidra/run_kernel_loader_refs_probe.sh \
  analysis/community/fw/kernel.drv
```

## Next investigation

The remaining useful kernel-side target is the indirect bank-window lookup,
not the already-understood resident driver installation path. We should map
the low-offset stub area for the A19/B2/B16-qualified entries and connect each
stub to the corresponding `drv_ui` bank or shared UI module. Until then, the
host emulator and Ghidra p-code probes remain the safe test surface.

The host-side `LazyBankRuntime.boundary_trace()` now records the conservative
sequence supported by the available evidence: an unloaded overlay produces an
exception boundary, the resident loader copies the selected bank, and a
validated entry is retried. Missing providers and unvalidated entry offsets
stop in the trace; no raw far pointer is executed. This is an emulator
contract, not a claim that the unavailable fixed exception handler has been
recovered.

## Additional public sources checked

The following sources were checked after the initial `actions_flash` review.
They are useful as compatibility and recovery references, but none is treated
as proof of an M30-specific address or ABI.

### Public ATJ2127 SDK: update flow and filename handling

The public `Suber/PD196_ATJ2127` SDK contains source for its automatic-upgrade
menu. It defines the firmware filename as `UPGRADE.HEX`, also accepts the
display spelling `UPGRADE HEX`, opens the file from the root of the selected
storage volume, and asks for confirmation only after the file is found. The
same source formats the confirmation label from the filename rather than
requiring a runtime `%s` placeholder in the visible string.

This is useful for explaining the M30 upgrade-screen wording and for testing
the earlier spacing change, but the repository targets a different product
build. It must not be used as a drop-in source replacement for M30 UI code:

<https://github.com/Suber/PD196_ATJ2127/blob/maint/case/ap/ap_tools/menu_callback_autoupgrade_tools.c>

### Independent package parsers

Two independent tools provide cross-checks for the offline firmware boundary:

* Rockbox's `atjboottool` contains a maintained C implementation for unpacking
  Actions firmware containers. It is a good second parser for checking the
  outer update package before any modification is attempted:
  <https://github.com/Rockbox/rockbox/tree/master/utils/atj2137/atjboottool>
* `nfd/atj2127decrypt` provides an independent ATJ2127 `UPGRADE.HEX`
  decryptor/unpacker and documents a MIPS/QEMU debugging path for its own
  implementation. Its README explicitly notes that the generated decompiled
  code is ugly and that MBREC decoding is incomplete, so it is a validation
  oracle rather than a source of trusted boot code:
  <https://github.com/nfd/atj2127decrypt>

Neither parser should be allowed to rewrite the archived M30 tree silently.
The safe integration point is a compare-only check: package file names,
lengths, hashes, and YQHX metadata must agree before we use a result in the
emulator.

### Public ATJ2127 overlay ABI cross-check

The public `kilicdev/actions_flash` investigation log independently describes
the same broad execution model: YQHX overlay banks are copied into a fixed
execution window on demand, and MIPS16 system calls use a `break 0` path with
selector values in a register. Its example is an ATJ2127 reference/Bluetooth
build, not the M30 image, and its tagged-pointer constants do not match the
M30 A/B/C values. It is therefore useful as ABI corroboration only; it does
not identify the missing M30 `0xbfc06d6c` handler or authorize direct calls.

<https://github.com/kilicdev/actions_flash/blob/main/RE_NOTES.md>

### Recovery and read-only extraction boundary

The SanDisk Clip Sport recovery notes are for another ATJ2127 product, but
they provide a useful independent description of the boot chain: Boot ROM,
MBREC, BREC, then the firmware image, with ADFU recovery exposed as
`10d6:10d6`. They also describe raw-NAND readback as a separate operation
from flashing. This supports keeping our recovery model and our firmware
modification model separate:

<https://gist.github.com/roman-yepishev/737dfda3a0a853fe730286d3ce49fccd>

The same notes include a destructive hardware workaround for a failed device;
that procedure is explicitly out of scope here.

### USB/ADFU caution from a separate investigation

The recent Crystal701 investigation records that an ADFU identification
response can recover after a full power cycle, while a successful USB
identification does not guarantee that arbitrary memory reads are accepted.
This matches our practical rule: a future USB experiment must begin with a
read-only probe, record VID/PID and the exact response, and stop before any
`write_mem`, `write_flash`, or payload execution. It is a field report rather
than an M30 or ATJ2127 specification:

<https://gist.github.com/GOROman/934e9c522632b303065777bb154a4ef6>

### Sources deliberately not reused

The newer `sonigeez/actions-adfu` tool is documented for ATS30xx firmware and
its tested chip is ATS3085S4. Its dry-run and read-only ideas are useful, but
its loader and flash protocol are not evidence for this ATJ2127 M30 and are
not imported into the project:

<https://github.com/sonigeez/actions-adfu>

The practical outcome is a stronger offline/recovery boundary, not a claim
that we are ready to flash a custom image. We still need an M30-specific
provider/bank-window proof before modifying executable UI code with confidence.

## MIPS16 import-selector evidence

The B3 bank has a repeatable indirect-call pattern in which a `jalr` is
immediately followed by a MIPS16 delay-slot instruction `li a3,<selector>`.
The mapped B3 disassembly contains one selector-15 call at `0x260e5794`
immediately paired with one selector-17 call at `0x260e579e` in a second UI
function. Other indirect calls in the
same bank use different selectors, so this is evidence for a reusable import
ABI rather than proof that selectors 15/17 are the marquee operation. It is
stronger than a byte-pattern match because the values are attached to decoded
call sites, but it still does not establish the selector semantics or the
resident dispatch table that receives them.

The read-only cross-check is reproducible with:

```sh
bash tools/ghidra/run_drvui_import_probe.sh analysis/community/fw/drv_ui.drv
```

### Dated-corpus binutils cross-check

The same MIPS16 binutils scan was run against the nine hash-verified dated
HEX extractions currently available outside Git (2022-09-14 through
2025-06-26, excluding the three older `ACTS-FWT001` files that the current
unpacker cannot open). Every `drv_ui.drv` produced the same decoded import
summary:

```text
MIPS16 IMPORT SUMMARY calls=5 selectors=0:2,1:1,15:1,17:1
selector 0xf:  call 0x260e5794, delay 0x260e5796
selector 0x11: call 0x260e579e, delay 0x260e57a0
```

The two older common blobs are byte-identical with SHA-256
`4614c31a4175ca7fdf24ae5b2e2266afe063df373d6255cc115eb67d2ff8f323`; the
2024-03-19, 2024-04-24 and 2025-02-17 blobs are byte-identical with SHA-256
`f9d63d68f7d66f8f83f109044d1c7e91e415d9feec49ca4663d5119867aee0b2`; and the
2025-06-26 blob is a third variant with SHA-256
`011f4e6a50738026ac641370f493c5df2e59adc435871d8a213e717604d2576a`.
Despite those byte-level variants, the decoded selector/call boundary is
unchanged across all nine inputs. This is independent instruction-decoder
evidence for the existing Ghidra result, not proof that selectors `0xf` or
`0x11` have identical semantics in every firmware release.

The probe now maps the B3 function together with the extracted resident
wrapper. It verifies that the selector-15 and selector-17 calls use the same
four-argument resident target at `0xbfc09c05`, while the target decompiles to
the trap/status-byte wrapper at `0xbfc09c00`. It still reports selector
numbers only at the M30 execution boundary; it does not model them as
rendering, storage, or bank-loading operations until an M30-specific
dispatcher path is recovered.

The probe also dumps the B3 literal table entries at `0x260e59e8` and
`0x260e59ec`, confirming that the symbolic call target used by both selector
sites is the actual `0xbfc09c05` pointer, while the neighboring system-call
entry is `0xbfc09c01`. This closes the pointer-value gap without assigning
meaning to either selector.

### Public UI-operation ordinal cross-check

The public SDK gives a useful, but deliberately separate, comparison. Its
`ui_cmd_e` enum and `ui_driver_operations` table place
`UI_SCROLLSTRING_EXT` at ordinal `15` and `UI_GET_DC_STATUS` at ordinal `17`.
Those are exactly the two selector values observed in the M30 B3 delay slots.
The public header also shows that the application-facing `ui_op_entry()` call
passes the command as its fourth argument. That matches the M30 call shape
around `0xbfc09c05` in the second B3 function, where the same target is called
with selectors `0xf` and `0x11` and three payload arguments.

This raises confidence that the values are UI-operation selectors rather than
arbitrary rendering constants, but it is not an M30 dispatcher proof: the
public SDK targets a reference product and the M30 resident table is still
unavailable. The host layer therefore exposes these names only through the
reference-only `tools/sim/ui_imports.py` module and keeps the selectors
unresolved for execution.

## B3 trailing pointer table

The second B3 UI function at runtime `0x260e5780` ends at the B3 bank boundary.
The next mapped data area begins at file offset `0x9e80`, runtime
`0x260e5800`. Its first pointer words used by the function are at runtime
`0x260e59e8` (file `0xa068`):

| Runtime address | Value | Current classification |
|---|---:|---|
| `0x260e59e8` | `0xbfc09c05` | resident UI/system entry candidate |
| `0x260e59ec` | `0xbfc09c01` | resident system-operation entry |
| `0x260e59f0` | `0x26209401` | B08-qualified lazy-bank candidate, payload `+0x401` |
| `0x260e59f4` | `0x261c9694` | B07-qualified lazy-bank candidate, payload `+0x694` |
| `0x260e5a10` | `0x26109751` | B04-qualified lazy-bank candidate, payload `+0x751` |

The first two values match the resident call convention already seen in the
B3 literal pool. The other three use the same `0x9000` low-offset encoding as
the earlier A19/B2/B16 candidates, but their payload offsets do not by
themselves prove an entry point or a direct call target. In particular, the
table is evidence for a shared/lazy dispatch data structure, not evidence that
the missing provider banks are present in this M30 `drv_ui.drv`.

The read-only mapping and word dump are reproducible with:

```sh
bash tools/ghidra/run_drvui_b3_table_probe.sh analysis/community/fw/drv_ui.drv
```

## B3 candidate bank bodies

Mapping only the nominal `0x800`-byte bank windows leaves the candidate
functions' literal pools outside the Ghidra memory map. Including the next
`0x800` bytes after each bank produces coherent decompilations for all three
entries referenced by the B3 table:

| Raw pointer | Candidate bank/offset | Public runtime entry | Observed decompilation shape |
|---|---|---:|---|
| `0x26109751` | B04 `+0x751` | `0x26125750` | six-argument UI/text renderer; kernel and filesystem calls |
| `0x261c9694` | B07 `+0x694` | `0x261e5694` | two-argument lookup/dispatch helper returning `ushort` |
| `0x26209401` | B08 `+0x401` | `0x26225400` | descriptor/line renderer with alignment and clipping flags |

The odd low bit is handled as MIPS16 mode metadata: the first and third raw
values enter at the preceding aligned address. This is now a stronger
candidate-body result, not proof that the raw pointer can be called directly
by the host emulator. The provider bank and dispatcher behavior still need a
runtime observation or an extracted resident implementation before execution
is enabled.

The host address model exposes these three derived addresses as
`candidate_runtime_entry`; it deliberately keeps the field separate from an
executable function pointer. This preserves the useful Ghidra/public-window
mapping while keeping unresolved bank dispatch fail-closed.

The reproducible probe is:

```sh
bash tools/ghidra/run_drvui_b3_candidate_probe.sh analysis/community/fw/drv_ui.drv
```
