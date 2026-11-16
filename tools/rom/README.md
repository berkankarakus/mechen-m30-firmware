# ATJ2127 Boot ROM dump

`dump_bootrom.sh` prepares a read-only dump of the ATJ2127 Boot ROM window.
It is intentionally a dry run unless `--execute` is supplied. The command
sequence contains only:

1. `simple_switch 0xbfc18000 adfus.bin` — upload the ADFU server to RAM;
2. `read_mem2 0x9fc00000 0x40000 ...` — read 256 KiB from the ROM window.

It does not call `write_flash`, `read_lfi`, or any NAND-writing operation.
The player must already be in ADFU mode (`10d6:10d6`). A normal mass-storage
player should be switched separately and explicitly with `adfu_reboot`.

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

The same build is reproducible from this repository and does not access USB:

```sh
bash tools/rom/build_actions_dump.sh /private/tmp/actions_dump
```

The MIPS `adfus.bin` payload is still needed. The source is present in
`actions_flash/payload`; this Mac currently has the MIPS binutils but not a
MIPS C compiler, so the payload has not been rebuilt here.

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

Before loading the payload, the wrapper calls `adfu_info` as a read-only
identity check and refuses to upload unless the client reports
`guess: chip = ATJ2127`. The verifier requires exactly 256 KiB, prints a SHA-256, and shows the bytes
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
