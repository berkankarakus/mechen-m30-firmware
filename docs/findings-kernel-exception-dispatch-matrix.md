# Kernel exception dispatch matrix

The extracted `ker_init.bin` constructor at `0xbfc32bc8` initializes the real
exception table at `0x9fc1a9a4`; the extracted `kernel.drv` vector at
`0xbfc08180` indexes it with `Cause & 0x7c`. I extended the existing composed
Ghidra p-code probe to execute that constructor once, then exercise vector
dispatch for every exception code 0–13 with the corresponding cause bits and
unrelated high/low cause bits set.

The table values and observed dispatch targets are:

| ExcCode | Handler pointer | ISA tag | Frequency in table |
|---:|---:|---|---|
| 0 | `0xbfc19624` | MIPS32 | one slot |
| 1–8 | `0xbfc19a75` | MIPS16 | default handler |
| 9 | `0xbfc06f18` | MIPS32 | one slot |
| 10 | `0xbfc195d4` | MIPS32 | one slot |
| 11–13 | `0xbfc19a75` | MIPS16 | default handler |

For each code, the probe checks the constructor-produced slot against this
table, runs the vector until its selected handler address, and verifies the
saved EPC, RA, and full Cause word at `0x13dcc`, `0x13dd0`, and `0x13dd4`.
The first failed matrix attempt exposed the MIPS16 mode requirement for the
default handler: its tagged pointer is odd (`0xbfc19a75`) while the emulator's
canonical PC is `0xbfc19a74`. The probe now sets the matching Ghidra ISA context
and compares the canonical PC while retaining the tagged pointer in its
reported matrix.

Reproduce against the local 2025-06-26 extracted members:

```sh
bash tools/ghidra/run_kernel_initialized_exception_probe.sh \
  /Users/berkankarakus/Projects/m30-inputs/extracted/2025-06-26/fw/kernel.drv \
  /Users/berkankarakus/Projects/m30-inputs/extracted/2025-06-26/fw/ker_init.bin
```

The observed run passed all 14 cases. The kernel and init members have the
same SHA-256 values in the eight locally checked dated corpora:
`kernel.drv` `58f9d0c6…05d8bd6` and `ker_init.bin`
`f4c62848…47492ec8`. This establishes the matrix for those byte-identical
members, not for every possible M30 firmware revision.

**Limits:** this is Ghidra p-code execution of extracted code with synthetic
CP0 inputs and RAM. It observes dispatch only up to each selected handler;
none of the handlers, fixed ROM, or real exception entry conditions were
executed. It identifies routing, not handler semantics, hardware exception
behavior, or boot-time invocation.

## Extracted five-word exception-frame consumer

The hash-pinned `ker_xsys.bin` also contains MIPS16 function
`FUN_bfc344f4`. Its literal at `0xbfc34554` is `0x00013dcc`; the following
literal at `0xbfc34558` is the tagged callback pointer `0xbfc04841`. A
read-only Ghidra decompile shows a five-iteration loop that calls that pointer
with a descriptor at `0xbfc3454c`, the next 32-bit word beginning at
`0x13dcc`, and argument `2`. The descriptor bytes are `exc:`. The five reads
therefore cover `0x13dcc..0x13ddc`: the three words saved by the kernel
exception vector and the EPC/RA pair saved by the `ker_xsys` entry. The
function checks bit 1 of the word at `0x9fc1aa5c`: clear writes `0x5d` and set
writes `0x69` to MMIO address `0xc012001c`. The kernel-init trace independently
shows a write of `1` to that address, but does not identify the peripheral
function. These byte values' hardware effect is still unknown.

The real MIPS16 function was run in Ghidra p-code with five distinct seeded
words and a synthetic callback stub replacing the unavailable ROM callback.
The probe observed five calls in order, each with the expected frame word,
descriptor, and width argument, and verified canaries immediately before and
after the frame. Two RAM-backed status/MMIO profiles then confirmed the real
code writes `0x5d` when bit 1 is clear and `0x69` when it is set. This models
the address as RAM; it does not simulate the peripheral. Reproduce with:

```sh
bash tools/ghidra/run_ker_xsys_exception_frame_probe.sh \
  /Users/berkankarakus/Projects/m30-inputs/extracted/2025-06-26/fw/ker_xsys.bin
```

This establishes the extracted consumer's frame-reading and callback ABI,
plus its conditional values written to the MMIO address, under synthetic
callback and RAM-backed MMIO. It does **not** establish that the missing fixed
ROM handler calls this function or that it is the ExcCode 9 path. A
direct-pointer scan of the locally extracted members found no reference to
`0xbfc344f4`; an indirect ROM call remains possible.
