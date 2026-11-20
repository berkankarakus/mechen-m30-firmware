# Existing tool source audit and NOR boot-record lead

This note records what the source code already available on the analysis host
can and cannot establish for M30 boot and ROM research. No tool was run against
the device, no firmware was written, and no dependencies were downloaded.

## Rockbox source audit

The local Rockbox tree has useful protocol and disassembly references, but its
ATJ213x assumptions are not proof of ATJ2127/M30 compatibility.

- `utils/atj2137/adfuload/adfuload.c` uploads a stage and can execute a second
  payload. Its memory-read routine is disabled with `#if 0`; it is not a
  working ROM dumper as checked out.
- `utils/hwstub/stub/main.c` implements address-and-length based memory reads,
  writes, and calls, with exception recovery. The target implementation under
  `utils/hwstub/stub/atj213x/` hard-codes an ATJ213x target identity and memory
  map. It requires a running HWStub endpoint. Neither its start-up path nor its
  address map is established for the M30's ATJ2127.
- Installed GNU binutils include MIPS16 assembler/disassembler support, but
  there is no matching MIPS16 C compiler in the current PATH. This is enough
  for small hand-written assembly probes, not for building the Rockbox C
  payloads as MIPS16.
- `utils/atj2137/atjboottool/afi.c` verifies and extracts AFI entries as opaque
  byte ranges. It reports the AFI directory address but does not interpret
  the contents of `NORBREC.BIN`.
- `utils/atj2137/atjboottool/fw.c` extracts firmware members and validates
  their checksums. `fwu.c` handles the outer update-container decryption. The
  source inspected here does not decode the internal NOR boot-record format.

Practical value: reuse Rockbox's existing container and USB protocol
understanding; do not treat its ATJ213x HWStub or disabled ADFU read routine as
a ready M30 ROM-reading solution.

## Installed analysis-tool source audit

The installed Ghidra package includes readable MIPS SLEIGH definitions,
including `mips16.sinc`, plus source archives for the MIPS processor and
emulation framework. These sources clarify what its decoded edges and p-code
probes do. MIPS16 `jal` preserves the current ISA mode, while `jalx` switches
it; the `0xbfc32158` instruction decodes as `jal 0xbfc32001`. That edge cannot
substantiate a call into the even-address MIPS32 entry at `0xbfc32000`. The old
normalized-xref assertion has been removed.

The source also revealed a limit in the original probes:
`MIPSEmulateInstructionStateModifier` handles the `setISAMode` p-code op and
the MIPS ISA context, but `EmulatorHelper.registerCallOtherCallback` overrides
that processor behavior. Its source warns that registering a callback may
bypass processor-module support, and marks `EmulatorHelper` deprecated since
Ghidra 12.1. A new standalone `PcodeEmulator` fixture now exercises a real
MIPS16 `jalx` into MIPS32 and a `jr ra` return to MIPS16; it reaches the MIPS32
body at `0x1008`, returns to MIPS16 at `0x1006`, and verifies the body wrote
`v0=0x1234`. Its assembly source is
[`mips_native_mode_probe.S`](../tools/ghidra/mips_native_mode_probe.S). The
NORBREC reader probe now also uses `PcodeEmulator` and the
native MIPS `setISAMode` userop. It verifies MIPS16 context at both external
edges and requires an odd MIPS16 return address. The NORBREC setup probe has
also been moved to `PcodeEmulator`; it verifies the same native MIPS16 context
and return-address property at all three stubbed ROM edges. This removes the
legacy callback from these NORBREC probes. It does not emulate the unavailable
ROM helpers, and the setup probe does not assert arguments at its first
`0xbfc10a6c` gate.

The QEMU 11.1.3 source archive is already present in the local Homebrew cache
and matches the installed formula's hash, so source review required no network
access. `target/mips/tcg/exception.c` exposes QEMU's general MIPS exception
resume-PC behavior, `target/mips/tcg/translate.c` implements MIPS16 control
flow, and `hw/mips/malta.c` plus `hw/mips/Kconfig` describe the Malta board and
its memory/device map. The QEMU plugin API header documents that exception
discontinuity callbacks run after QEMU prepares the new PC. This supports the
existing passive observer as an independent check of guest-side CP0
observations. QEMU offers generic XBurst CPU models, but its registered
machine is Malta/`none`, not ATJ2127. So QEMU is useful for bounded real-code
probes and exception-vector observation, not full M30 boot, LCD, or DAC
fidelity. A source-level ATJ machine would need evidence-backed memory maps and
peripheral effects before its results would be trustworthy.

### Other locally available analysis tools

The local tool survey is focused on tools that can materially inspect or run
these firmware images; it is not an audit of every application installed on
the host.

- GNU MIPS binutils (`as`, `ld`, `objcopy`, `objdump`) are the useful mixed-mode
  path here: they assemble MIPS probes and disassemble both MIPS32 and MIPS16.
- Capstone's installed `cstool` was tested on the extracted kernel vector. Its
  MIPS32 output independently agrees with the vector bytes, but the installed
  Capstone API exposes MicroMIPS mode and no MIPS16 mode. It is therefore a
  cross-check for MIPS32, not a replacement for binutils/Ghidra on MIPS16.
- CodeGraph is available for source-level navigation in this repository. Its
  index can connect callers and dependencies among our scripts and emulator
  code; it does not disassemble firmware blobs or recover firmware semantics.
  The index was synced after the latest probe commit.
- The targeted command/app/module check found no Binary Ninja, radare2, Rizin,
  Unicorn, angr, `mipsel-linux-gnu-gdb`, or `gdb-multiarch`. The current
  combination already covers the demonstrated needs: Ghidra for MIPS16 p-code,
  binutils for mixed-mode assembly/disassembly, and QEMU for MIPS CPU execution.
  No extra tool was installed because none of the absent candidates currently
  offers a demonstrated gap-filling capability for this work.

### Real extracted exception vector under QEMU/Malta

The real `kernel.drv` exception-vector bytes at file offset `0x380` were also
run at their firmware address `0xbfc08180` on QEMU's Malta `24Kf` CPU. The
reproducible harness is `tools/emu/run_malta_exception_vector_probe.py`. It
builds a temporary 4 MiB Malta BIOS image containing the hash-pinned vector, a
handler stub at `0xbfc06f18`, and slot 9 preseeded with that handler value—the
value independently produced by the extracted `ker_init` constructor probe.
It installs the minimum low-memory TLB pair needed for the vector's stores at
`0x13dcc..0x13dd4`, raises a real `break` exception, and checks the vector's
saved EPC, RA, and Cause's ExcCode bits through Malta's FPGA UART. The image
builder accounts for Malta's MIPS little-endian BIOS word swap. A run against
the 2025-06-26 `kernel.drv` emitted `PASS`.

This is new CPU-level evidence for the extracted vector and its table dispatch
under QEMU. A second harness, `tools/emu/run_malta_constructor_vector_probe.py`,
also executes the hash-pinned MIPS32 constructor and its real MIPS16 setter on
Malta. It redirects the setter's table-base literal from BIOS to RAM and the
vector's table-base instruction to the same RAM table. At the audited boundary
`0xbfc32c5c`, the harness redirects control into its slot checks; it verifies
slots 0..13 and untouched sentinels at 14 and 31, then raises ExcCode 9 and
checks the real vector's saved EPC/RA/Cause. Runs passed on QEMU `24Kf` and
`34Kf`. The boundary instrumentation replaces the first two instructions at
that point, and the fixed-ROM handler remains a stub. These probes do not
establish M30 bootloader invocation, ATJ2127 peripheral behavior, or device
fidelity.

## NOR boot-record observation

The AFI archives already extracted from dated M30 updates contain a
`NORBREC.BIN` member of size `0x28a00`. Its SHA-256 is
`8b11f25209e6a79474559b4b48d3a9d7f29d5f07633d234fe0eada9b8cd4e93d` in the
2022-09-14 and 2025-06-26 images, and the corpus note records the same hash for
the other compared releases.

The outer AFI directory entry was also checked directly by decrypting the
already-local 2025-06-26 HEX with Rockbox `atjboottool` in ATJ2127 mode, then
unpacking its AFI. The `NORBREC.BIN` entry has type `B`, AFI address `0`, file
offset `0x34c00`, size `0x28a00`, and additive checksum `0x96b22f89`; the AFI
checksum verifier passes. The extracted member is byte-identical to the
existing local copy (SHA-256 above). Because the AFI address is zero, it does
not explain the internal word `0xbfc32000` at member offset `0x1c` or prove a
runtime load address. It only confirms the outer member boundary and checksum.
This prevents treating the internal address candidate as an AFI directory
load-address field.

The local tool invocation was performed with output confined to a unique
temporary directory; no image was downloaded and no device or card was
written. To repeat on another already-local image, run `atjboottool
--fwu --atj2127 -o <temporary-dir>/decoded.afi <input.HEX>`, then run
`atjboottool --afi -o <temporary-dir>/members/ <temporary-dir>/decoded.afi`
after creating the empty `members/` directory. The AFI output reports the
directory entry and verifies its checksum before extracting members.

Observed bytes and disassembly:

- At file offset `0x1c`, the little-endian word is `0xbfc32000`.
- The bytes at file offset `0x100` disassemble as MIPS32 when mapped at
  `0xbfc32000`. The first instructions set SP to `0x9fc3fe00`, move incoming
  arguments, then call `0xbfc10191` at `0xbfc32010`.
- The same bytes are not MIPS16 instructions. Later regions do contain
  readable MIPS16 code; disassembling this mixed-mode member with `-m mips:16`
  is substantially more useful than treating the whole file as MIPS32.
- At file offset `0xa2c` (candidate runtime address `0xbfc3292c` under the
  header's `0xbfc32000` mapping), a MIPS16 routine computes a 512-byte block
  count, calls an indirect routine obtained through `0xbfc02600`, then calls
  the fixed-ROM MIPS16 entry `0xbfc108d9` with `(original a0, 0x9fc27000,
  original a2)`. Ghidra normalizes this MIPS16 target to `0xbfc108d8`. This
  establishes the call shape, not the ROM helper's semantics.
- At candidate address `0xbfc3296c`, a MIPS16 routine reads a directory block
  by passing a sector derived from the word at `0xbfc10138`, destination
  `0x9fc12000`, and count `1` to an indirect helper. It then scans 32-byte
  records in that buffer for `KER_TEXT.BIN`, `KER_DATA.BIN`, `KER_INIT.BIN`,
  and `KER_XSYS.BIN`, and passes matching record fields at offsets `+0x10` and
  `+0x14` to a fixed-ROM helper. This ties the NOR record to selection of the
  extracted kernel components; exact directory and helper semantics remain
  partly unresolved.
- At file offset `0xb48` (candidate runtime address `0xbfc32a48`), another
  MIPS16 routine populates the first 16 bytes of a structure at `0xbfc10124`, then calls
  `0xbfc108d9(0x9fc12000, 0xbfc10124, 0x14)` and
  `0xbfc108d9(0x9fc12014, 0xbfc10138, 0x20)`. The two calls are consistent
  with copying/building a small boot structure in the `0x9fc12000` region,
  but a copy interpretation remains a hypothesis until the ROM helper is
  identified. This is a concrete lead for explaining the later kernel's
  reads from the same address window.
- A separate byte/disassembly cross-check confirms that the reader's literal
  at file offset `0xa64` and the setup routine's literal at `0xb9c` are used
  as bases for pointer loads at `0xbfc02600`. Their use in these two call
  paths is visible in the instructions; the fixed-ROM table contents and the
  runtime value selected by other references remain unknown.
- The code does not match the start of the separately extracted, hash-pinned
  `ker_init.bin`, despite both candidate mappings using `0xbfc32000`. Their
  first 32 bytes differ. The NOR record's early wrapper and the firmware's
  later `ker_init` segment may occupy the same address at different boot
  stages; the actual handoff and mapping are still unverified.

The central MIPS16 call sequence can be reproduced with the installed GNU
binutils (the input path is local to the analysis host):

```sh
mipsel-linux-gnu-objdump -D -b binary -m mips:16 -EL \
  --adjust-vma=0xbfc31f00 \
  --start-address=0xbfc3292c --stop-address=0xbfc32ac0 \
  /path/to/NORBREC.BIN
```

The `0xbfc31f00` adjustment accounts for the observed code at file offset
`0x100` mapping to `0xbfc32000`. It is a candidate mapping derived from the
record, not yet independently verified runtime state. The fixed-ROM bodies at
`0xbfc10191`, `0xbfc108d9`, and the indirect target reached through
`0xbfc02600` remain unavailable; NORBREC's complete header and loader ABI are
not yet decoded.

The Ghidra mapping and decompilation are reproducible with
[`run_norboot_probe.sh`](../tools/ghidra/run_norboot_probe.sh). It pins the
member hash, maps the first `0x18` bytes of the code entry as MIPS32, marks the
observed body from file offset `0x158` as MIPS16, and checks the decompiled
call shapes for `FUN_bfc3292c` and `FUN_bfc32a48`. The entry cross-reference
is deliberately not used as proof of a call into
the MIPS32 entry: binutils decodes the instruction at `0xbfc32158` as a
MIPS16 `jal 0xbfc32001`, while the candidate entry is mapped as MIPS32 at
`0xbfc32000`. Ghidra's normalized even-address xref cannot reconcile that
ISA-mode conflict. No direct references to the directory/setup routines have
been established; that does not rule out ROM or function-pointer dispatch.
Ghidra also warns that decompiling the entry stub across its MIPS32-to-MIPS16
boundary is unresolved. The script runs the extracted `0xbfc32a48` MIPS16
routine in Ghidra p-code with synthetic RAM/ROM state. It records three
external calls: one to `0xbfc10a6c` (its register arguments are not asserted),
followed by two calls to `0xbfc108d8` with arguments
`(0x9fc12000, 0xbfc10124, 0x14)` and
`(0x9fc12014, 0xbfc10138, 0x20)`. It verifies the caller's structure writes
at `0xbfc10124` and metadata stores at `0x9fc12200`/`0x9fc12204`. The ROM
calls return synthetic zero; the probe does not emulate the helper's
copy/transform semantics, so it proves caller behavior only. It also executes
the `0xbfc3292c` reader wrapper with synthetic arguments using the native MIPS
p-code userop. It observes a block-reader call
`(sector=25, scratch=0x9fc27000, count=4)` for a `0x601`-byte input, followed
by the ROM helper with `(0x9fc13000, 0x9fc27000, 0x601)`. The indirect reader
pointer carries the MIPS16 low-bit tag; the native emulator switches mode and
the probe checks the MIPS16 context and tagged return address at each stub.
This validates the wrapper's round-up to four 512-byte blocks for this
non-aligned fixture and its outgoing arguments; the block reader and ROM
helper are synthetic stubs, so their semantics are not modeled. The successful
script prints these observed call edges. It executes no firmware on the player
and assigns no behavior to missing ROM functions.

The candidate MIPS16 bridge at `0xbfc32058` is now also stepped in the same
native p-code run by `RunNorBootCallbackBridgeProbe.java`. With synthetic
external state (`*(0xbfc10118)=0x20`, `*(0xbfc1011c)=0x9fc11000`, and a
halfword value `7` at `0x9fc1100c`), the real code loads a MIPS16-tagged
callback from synthetic slot `0xbfc02608`. For `a2=0x28` (40), it calls that
target with `(a0=0x5400, a1=0x9fc13000, a2=0x5000)` and returns through
`ra=0xbfc32085`; for `a2=0x29` (41), it returns without the indirect call.
The target body is stubbed. This verifies the code's branch and outgoing ABI
under the stated fixture, not the actual fixed-ROM values, callback identity,
parent caller, or boot-time execution.

This narrows the NORBREC callback ABI, but does not identify the bridge's actual
fixed-ROM state or prove that it is called during boot. It also does **not**
identify NORBREC as the active ROM bootstrap, nor prove that `0xbfc32000` is the
runtime address at the relevant boot stage. The repeated NORBREC hash means
decompiling each dated copy would add no independent code evidence.

## Suggested next work

1. Recover the actual caller and fixed-ROM values behind the `0xbfc32058`
   callback bridge; establish whether the `0x9fc12000` setup runs before
   firmware `ker_init`.
2. Identify the internal NORBREC header's data and entry fields. The outer AFI
   record is now known but supplies no load address; the nine local dated
   NORBREC copies are byte-identical, so they cannot independently validate
   candidate field meanings.
3. Treat other AFI members as separate boot components unless code-level
   evidence connects them; their stable hashes alone do not establish shared
   loader conventions.
4. Keep all analysis offline. Do not execute guessed payloads on the player.
