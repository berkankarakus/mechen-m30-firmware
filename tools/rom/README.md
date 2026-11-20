# ATJ2127 Boot ROM dump

`dump_bootrom.sh` prepares a 256 KiB readback of the ATJ2127 Boot ROM window.
Its dry run is the default. Execution is not passive: it first
queries ADFU identity, then uploads and runs code in device SRAM before reading
the ROM. The command sequence is:

1. Separate `adfu_info` invocation — query the ADFU chip-family guess;
2. Main invocation selects `chip 2127` and `blk_size 0x4000`;
3. `simple_switch 0xbfc18000 adfus.bin` — upload the ADFU server to SRAM;
4. `read_mem2 0x9fc00000 0x40000 ...` — upload and run its MIPS16 helper at
   `0xbfc1e000`, then read 256 KiB. The helper uses a buffer at `0xbfc1e020`.

The wrapper's command vector does not call `write_flash`, `read_lfi`, or any
NAND-writing operation. The supplied payload is executed, however, and its
safety is not established by this wrapper.
The player must already be in ADFU mode (`10d6:10d6`). Do not assume that
`adfu_reboot` moves this M30 from mass-storage mode into ADFU: a public M30
analysis reports that its attempt returned `ACTIONSUSBD` and left the player
in FlashDisk mode. That report is a diagnostic lead, not a confirmed result
for every unit. This script does not issue `adfu_reboot`; proceed only after
the device is independently observed as `10d6:10d6`. An `ATJ2127` identity
result only checks the chip-family guess; it does not verify the M30 board or
prove that the payload is compatible with it. See
[`related-projects.md`](../../docs/related-projects.md#adfuusb-lead-not-a-working-rom-read-path).

Without `--execute`, the script prints both the identity preflight and ROM
readback command. It sends no USB command and creates no output path. Pass
`--execute --acknowledge-ram-only` only after independently confirming ADFU
mode and accepting that code will be uploaded to and run from SRAM.

## Build the host client on macOS

The repository copy is `<local-workspace>/actions_flash`. With
Homebrew libusb:

```sh
cd <local-workspace>/actions_flash
LIBUSB_PREFIX=$(brew --prefix libusb)
cc -O2 -Wall -Wextra -std=c99 -pedantic -Wno-unused -DUSE_LIBUSB=1 \
  -I"$LIBUSB_PREFIX/include" -L"$LIBUSB_PREFIX/lib" \
  -o /private/tmp/actions_dump actions_dump.c -lusb-1.0
```

The same build is reproducible from this repository and does not access USB.
It locates an adjacent `actions_flash` checkout from the main repository
checkout when possible. Otherwise set `ACTIONS_FLASH_ROOT` or
`ACTIONS_FLASH_SOURCE` explicitly:

```sh
bash tools/rom/build_actions_dump.sh /private/tmp/actions_dump
```

The MIPS `adfus.bin` payload is still needed. Its source is present in
`actions_flash/payload`, but no built payload is present in the local checkout.
The installed Apple Clang has no MIPS target, so this environment cannot build
the payload with its current toolchain. A prebuilt payload from another
ATJ2127 device remains unverified for M30.

## Where the missing payload may come from

The public `actions_flash` notes for another ATJ2127 player document the same
read-only sequence: upload `adfus.bin` to `0xbfc18000`, then read the ROM
window at `0x9fc00000`. They are useful for understanding the transport, but
they do **not** establish that that device's payload is compatible with the
M30. Keep the payload provenance alongside any dump and verify the returned
ADFU identity before loading it.

Some public ATJ2127 SDK packages store `ADFUS.BIN` as a file inside an
embedded SQLite firmware database. If such a package is obtained, extract
only that file and inspect its size and hash before using it; do not flash the
package or run its write-capable utilities. A reference extraction example is
described in [the ATJ21XX research note](https://infosec.press/tildavaan/more-atj21xx-stuff),
while the read-only address sequence is documented in the
[`actions_flash` payload notes](https://github.com/ilyakurdyukov/actions_flash/blob/main/payload/README.md).

No verified M30-specific `adfus.bin` or 256 KiB Boot ROM dump is included in
this repository. Until one is obtained, the emulator intentionally leaves the
fixed `0xbfc06d6c` handler unresolved. A dump from a different ATJ2127
product must not be substituted merely because the chip family matches.

## Dry run

```sh
bash tools/rom/dump_bootrom.sh \
  --actions-dump /private/tmp/actions_dump \
  --adfus /path/to/adfus.bin \
  --out /private/tmp/m30-rom.bin
```

## Execute after ADFU is confirmed

```sh
bash tools/rom/dump_bootrom.sh \
  --actions-dump /private/tmp/actions_dump \
  --adfus /path/to/adfus.bin \
  --out /private/tmp/m30-rom.bin \
  --execute --acknowledge-ram-only
```

Before loading the payload, the wrapper calls `adfu_info` and refuses to
upload unless the client reports `guess: chip = ATJ2127`. This is not a
device-board or payload-compatibility check. The verifier requires exactly
256 KiB, prints a SHA-256, and shows the bytes
at dump offsets `0x5f90` and `0x6d6c`. These are candidates for the
`0xbfc05f90` and `0xbfc06d6c` targets observed in `ker_xsys.bin`; the alias
mapping must be confirmed from the dump, not assumed.

The offline verifier is also covered by the host suite. It rejects partial or
oversized reads before interpreting candidate offsets, and records every
little-endian `0x0003ffff` guard occurrence:

```sh
python3 -m unittest discover -s tools/rom -p 'test_*.py'
```

This test path uses synthetic bytes only; it does not imply that a ROM dump is
available or that the handler has been identified.

When a verified 256 KiB dump is available, map it into Ghidra and inspect the
two candidate handlers with:

```sh
bash tools/ghidra/run_bootrom_probe.sh /private/tmp/m30-rom.bin
```

The probe maps the dump at its `0x9fc00000` alias and decompiles the two
candidate offsets. It intentionally does not add the dump to the firmware
tree or execute it.
