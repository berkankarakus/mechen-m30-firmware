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

## NOR boot-record observation

The AFI archives already extracted from dated M30 updates contain a
`NORBREC.BIN` member of size `0x28a00`. Its SHA-256 is
`8b11f25209e6a79474559b4b48d3a9d7f29d5f07633d234fe0eada9b8cd4e93d` in the
2022-09-14 and 2025-06-26 images, and the corpus note records the same hash for
the other compared releases.

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
  fixed-ROM address `0xbfc108d9` with `(original a0, 0x9fc27000, original
  a2)`. This establishes the call shape, not the ROM helper's semantics.
- At file offset `0xb48` (candidate runtime address `0xbfc32a48`), another
  MIPS16 routine populates the first 16 bytes of a structure at `0xbfc10124`, then calls
  `0xbfc108d9(0x9fc12000, 0xbfc10124, 0x14)` and
  `0xbfc108d9(0x9fc12014, 0xbfc10138, 0x20)`. The two calls are consistent
  with copying/building a small boot structure in the `0x9fc12000` region,
  but a copy interpretation remains a hypothesis until the ROM helper is
  identified. This is a concrete lead for explaining the later kernel's
  reads from the same address window.
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

This is evidence for a promising next analysis target: identify the NORBREC
wrapper and determine whether it stages or transforms a later boot image. It
does **not** yet identify that code as the active ROM bootstrap, nor prove that
`0xbfc32000` is the runtime address at the relevant boot stage. The repeated
NORBREC hash means decompiling each dated copy would add no independent code
evidence.

## Suggested next work

1. Trace the MIPS16 setup routine's calls involving `0x9fc12000` and determine
   whether it is called on the path that precedes the firmware's `ker_init`.
2. Identify the data and entry fields in the NORBREC header and test candidate
   length/checksum interpretations against all nine local dated AFI copies.
3. Compare `NORBREC.BIN` with `CARDPRDU.BIN`, `NORHWSC.BIN`, `NORFWSC.BIN`,
   and `NORMBREC.BIN` to identify shared header and loader conventions.
4. Keep all analysis offline. Do not execute guessed payloads on the player.
