# Manager key-driver service-stub boundary

This note records the manager-side caller contract and the resident exception
stub used by the key-driver path. The exception handler that services the
stub is unavailable; the probe does not infer selector semantics.

## Static references

- Hash-matched `manager.ap` SHA-256:
  `d94d2406d5e88efee1ffacff2d399ce7d865410ac7458efdb9f185eae359af7a`.
- `config.bin` SHA-256 (community, stock, and V1.101.11; byte-identical):
  `900f814711f50446802ee36bcc2d1560df55b9d2fb4e2d964bb35004517b6d19`.
- The string `key.drv` is at file offset `0x1e40`. Its bank maps file
  `0x1e00` to runtime `0x7f056200`, so the string address is `0x7f056240`.
- Ghidra finds one code reference to that address, in `FUN_7f056200`; the
  caller is `FUN_7f056250`.
- `FUN_7f056200` calls in-overlay config getter `FUN_7f0962bc` with IDs
  `0x52`, `0x51`, `0x50` in that order. Decompiled getter code reads an
  indexed config record and returns the first 16-bit field.
- The wrapper then calls the MIPS16 pointer `0xbfc13de1` with
  `(9, packed, 0x7f056240, 10)`. This pointer targets a 4-byte resident
  exception stub at `0xbfc13de0`, not a known ROM function body.
- The `manager.ap` header maps file bytes `0x200..0x2b7` to
  `0xbfc13de0..0xbfc13e97`. The stub at `0xbfc13de0` loads `v1=15`, then
  executes `break`. Neighboring stubs load `v1=16` at `0xbfc13de4`, `9` at
  `0xbfc13de8`, `0` at `0xbfc13dec`, and `64` at `0xbfc13df0`, each followed
  by `break`. The exception handler that services these selectors is not in
  this segment.

## Config payload and p-code check

In the compared stock, community, and V1.101.11 `config.bin` files, the first
16-bit values of items `0x50`, `0x51`, and `0x52` are respectively `1`, `2`,
and `2`. The real manager caller was executed with a synthetic config getter
and synthetic exception-service return. It requested getters in order
`0x52,0x51,0x50` and ran the resident stub's selector load before reaching
`break` with `v1=0x0f` and arguments
`(0x9,0x01000202,0x7f056240,0xa)`. A second profile supplied getter results
`0x11,0x22,0x33` for items `0x50,0x51,0x52` and produced packed value
`0x11002233`. Both profiles returned through the real caller.

Reproduce with:

```sh
bash tools/ghidra/run_manager_key_driver_service_stub_probe.sh <hash-matching-manager.ap> <matching-config.bin>
```

The probe intercepts `FUN_7f0962bc` and the `break` after the resident stub;
their returns are synthetic. It asserts the resident segment header maps file
`0x200`/size `0xb8` to `0xbfc13de0`, the mapped stub bytes match the
hash-pinned image, execution enters the stub and steps its selector-load
instruction, and the next PC is the `break` with `v1=15`. It also executes the
intervening manager instructions and asserts the getter order,
Ghidra's MIPS16 listing context at both boundaries, tagged MIPS16 return
addresses, call arguments, return to caller, manager/config hashes, config
payload values, and selector 15. `EmulatorHelper` does not expose its active
ISA context through `readRegister()`, so this check is the program's decode
context plus the observed return-address tags; it is not an independent
runtime-mode assertion. It does not show what selector 15 does, whether the
exception handler installs `key.drv`, or whether it writes the driver's BSS
table `0x9fc14330..0x9fc14337`.
