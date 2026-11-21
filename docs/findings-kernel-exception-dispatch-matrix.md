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
