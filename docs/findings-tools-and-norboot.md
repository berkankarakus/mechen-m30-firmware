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
- The code does not match the start of the separately extracted, hash-pinned
  `ker_init.bin`, despite both appearing at `0xbfc32000` in the current static
  address model. Their first 32 bytes differ and neither byte prefix occurs
  in the other member.
- The later bytes are not yet classified. The fixed-ROM call body at
  `0xbfc10191`, the NORBREC header semantics, any internal transform, and the
  runtime memory mapping remain unknown.

This is evidence for a promising next analysis target: identify the NORBREC
wrapper and determine whether it stages or transforms a later boot image. It
does **not** yet identify that code as the active ROM bootstrap, nor prove that
`0xbfc32000` is the runtime address at the relevant boot stage. The repeated
NORBREC hash means decompiling each dated copy would add no independent code
evidence.

## Suggested next work

1. Parse the NORBREC header conservatively and test candidate length, entry,
   and checksum fields against all local dated AFI copies.
2. Find the MIPS16/MIPS32 boundary and data ranges in the first `0x100`-mapped
   region; treat `0xbfc10191` as an unresolved call edge.
3. Compare NORBREC with `CARDPRDU.BIN`, `NORHWSC.BIN`, `NORFWSC.BIN`, and
   `NORMBREC.BIN` to locate shared header/payload conventions before trying
   speculative decoders.
4. Keep all analysis offline. Do not execute guessed payloads on the player.
