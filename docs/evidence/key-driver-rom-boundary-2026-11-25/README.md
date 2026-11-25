# Manager key-driver ROM-call boundary

This note records the manager-side caller contract for the key driver. The
fixed-ROM implementation is unavailable; the intercept below does not infer
what the ROM operation does.

## Static references

- Hash-matched `manager.ap` SHA-256:
  `d94d2406d5e88efee1ffacff2d399ce7d865410ac7458efdb9f185eae359af7a`.
- Hash-matched `config.bin` SHA-256:
  `900f814711f50446802ee36bcc2d1560df55b9d2fb4e2d964bb35004517b6d19`.
- The string `key.drv` is at file offset `0x1e40`. Its bank maps file
  `0x1e00` to runtime `0x7f056200`, so the string address is `0x7f056240`.
- Ghidra finds one code reference to that address, in `FUN_7f056200`; the
  caller is `FUN_7f056250`.
- `FUN_7f056200` calls in-overlay config getter `FUN_7f0962bc` with IDs
  `0x52`, `0x51`, `0x50` in that order. Decompiled getter code reads an
  indexed config record and returns the first 16-bit field.
- The wrapper then calls the MIPS16 pointer `0xbfc13de1` with
  `(9, packed, 0x7f056240, 10)`. The ROM implementation is not present.

## Config payload and p-code check

In the compared stock and community `config.bin` files, the first 16-bit
values of items `0x50`, `0x51`, and `0x52` are respectively `1`, `2`, and
`2`. The real manager caller was executed with a synthetic config getter and
synthetic fixed-ROM return. It requested getters in order `0x52,0x51,0x50`
and reached the fixed-ROM boundary with arguments
`(0x9,0x01000202,0x7f056240,0xa)`. A second profile supplied getter results
`0x11,0x22,0x33` for items `0x50,0x51,0x52` and produced packed value
`0x11002233`. Both profiles returned through the real caller.

Reproduce with:

```sh
bash tools/ghidra/run_manager_key_driver_rom_call_probe.sh <hash-matching-manager.ap> <matching-config.bin>
```

The probe intercepts `FUN_7f0962bc` and `0xbfc13de0`; their returns are
synthetic. It executes the intervening manager instructions and asserts the
getter order, Ghidra's MIPS16 listing context at both boundaries, tagged
MIPS16 return addresses, fixed-ROM call arguments, return to caller,
manager/config hashes, and config payload values. `EmulatorHelper` does not
expose its active ISA context through `readRegister()`, so this check is the
program's decode context plus the observed return-address tags; it is not an
independent runtime-mode assertion. The probe does not show that the ROM call
installs `key.drv`, reads the config IDs itself, or writes key driver's BSS
table `0x9fc14330..0x9fc14337`.
