# End-of-track ASRC/EOF branch

This is a static comparison of the stock M30 `V1.101.10` `music.ap` against
the archived `V1.101.11` and community V1.292.00 images. It does not measure
the DAC, ASRC queue, or audible output on a device.

## Confirmed binary delta

The three images use the same `music.ap` bank layout. In the bank beginning at
file offset `0x9c00` / runtime address `0x40494c00`, the six bytes at file
offset `0x9f5c` change as follows:

```text
stock:     58 67 01 5a 22 61
V1.101.11: 24 60 04 72 0a 60
community: 24 60 04 72 0a 60
```

The surrounding code belongs to `FUN_40494e94`; the changed area is reached
through the odd MIPS16 address `0x40494f5d`. Ghidra's containing-function
decompile shows the following control-flow difference:

- stock: mode `3` enters the existing `+11000U` end-of-track branch;
- V1.101.11/community: an additional `mode == 4` case falls through to the
  same advance path before that branch is evaluated.

The reproducible guard is:

```sh
bash tools/ghidra/run_asrc_probe.sh
```

It decompiles stock, V1.101.11, and community images, asserts the mode-4
control-flow difference, and checks the raw six-byte replacement.

## Interpretation and limits

This is strong evidence for the community's end-of-track playback/ASRC
correction and explains why it is the best existing candidate for the reported
Audacity fade-out tail loss. It does not prove that the six-byte change alone
drains every DAC/ASRC sample, nor that every codec uses the same mode. The
current emulator therefore records this as a verified firmware boundary, not
as an audible playback pass.

The other V1.101.11 `music.ap` changes at offsets around `0x1150c` and
`0x120e0` are not yet assigned a playback meaning. They remain outside this
probe until their callers and device-facing effects are identified.
