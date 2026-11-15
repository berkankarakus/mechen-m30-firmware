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

The repository copy is `/Users/berkankarakus/Projects/actions_flash`. With
Homebrew libusb:

```sh
cd /Users/berkankarakus/Projects/actions_flash
LIBUSB_PREFIX=$(brew --prefix libusb)
cc -O2 -Wall -Wextra -std=c99 -pedantic -Wno-unused -DUSE_LIBUSB=1 \
  -I"$LIBUSB_PREFIX/include" -L"$LIBUSB_PREFIX/lib" \
  -o /private/tmp/actions_dump actions_dump.c -lusb-1.0
```

The MIPS `adfus.bin` payload is still needed. The source is present in
`actions_flash/payload`; this Mac currently has the MIPS binutils but not a
MIPS C compiler, so the payload has not been rebuilt here.

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
identity check. The verifier requires exactly 256 KiB, prints a SHA-256, and shows the bytes
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
