# M30 firmware-version corpus comparison

This is a read-only comparison of the install images available in the local
community-firmware archive. Each image was decrypted and extracted with the
Rockbox `atjboottool` before the comparison. The temporary extraction root is
not part of this repository.

## Corpus

The tested versions are:

```text
V1.101.11  V1.101.12  V1.200.00  V1.200.01  V1.201.00  V1.202.00
V1.202.01  V1.202.02  V1.202.03  V1.203.01  V1.287.00  V1.292.00
```

The extracted `drv_ui.drv` SHA-256 is identical for all twelve versions:

```text
011f4e6a50738026ac641370f493c5df2e59adc435871d8a213e717604d2576a
```

The extracted `kernel.drv` SHA-256 is also identical for all twelve:

```text
58f9d0c62bdbdab7cfeee1c5e65bbe8b88ee962f8eecd3dd0515d1a1056d8bd6
```

The application overlays do change between release lines, as expected; this
comparison therefore does not use an application hash as evidence about the
resident UI provider.

## Provider result

The observed UI pointer set was scanned in every extracted `fw/` directory,
excluding the known consumer `drv_ui.drv`:

```text
0x164490a1  A17 + 0x0a1
0x164c9001  A19 + 0x001
0x164c90ed  A19 + 0x0ed
0x26089471  B02 + 0x471
0x260894e9  B02 + 0x4e9
0x26409401  B16 + 0x401
```

All six counts are zero in all twelve versions. The same values do appear in
the outer `FWIMAGE.FW` archive, but those are container copies of the member
bytes, not an additional executable provider. The provider scan must therefore
operate on the extracted member directory, not on the archive container.

The comparison is reproducible with:

```sh
PYTHONPATH=tools/emu python3 tools/emu/compare_firmware_versions.py \
  /path/to/extracted-version-root --require-zero
```

## Consequence

Searching another archived M30 release is unlikely to reveal the missing A17,
A19, B2, or B16 implementation: the resident driver and UI driver are stable
across the available corpus, and no extracted member provides a second copy.
The remaining evidence must come from the fixed ROM/resident dispatch boundary
or from a runtime observation. This keeps the unknown provider out of the
flashable patch and out of the host emulator's executable dispatch path.
