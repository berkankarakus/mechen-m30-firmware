# QEMU coverage for the M30 work

## What is emulated

The current test setup uses QEMU's MIPS32 little-endian user-mode CPU runner.
It loads real M30 `.ap` banks into freestanding test harnesses and replaces
only the kernel/file-system/timer calls that each harness needs. This is much
closer to executing the firmware code than a browser mockup, but it is not a
complete M30 boot.

## Latest results

| Area | Runner | Result |
| --- | --- | --- |
| Shuffle fix | real `mengine.ap` patch bank | PASS |
| Shuffle-all / play-all | real patched engine units | PASS |
| Scroll acceleration | real `browser.ap` bank, stock vs patched | PASS; 30,000 events, 0 failures |
| Screen-off media keys | real common key-filter bank, five app contexts | PASS; regression-only, no firmware change retained |
| Library/index sorting | real stock/new index banks, synthetic 6,000-song library | PASS; byte-for-byte reproduction |
| Filename natural-order contract | host model | PASS; 11/11 model tests overall |
| Manual-index policy | host state model + static automatic-index guards | PASS |
| Artwork audio-first contract | host state model | PASS |

The latest QEMU library diagnostic was deliberately run as an ephemeral
diagnostic build with the experimental whole-card library enabled. It was not
used as the target firmware and produced no persistent 24K firmware artifact.

## What QEMU cannot boot yet

Homebrew QEMU currently exposes only the generic `malta` and `none` MIPS
machines. The M30 firmware expects the Actions ATJ2127 SoC, its bank-loader,
LCD controller, key controller, SD/FAT driver, DAC and codec/DSP devices. No
upstream machine model provides those peripherals. Passing the encrypted M30
HEX to `qemu-system-mipsel` would therefore not be a valid device test.

The following remain outside direct QEMU coverage:

- complete boot and menu rendering;
- physical SD-card insertion/USB-disconnect/index trigger;
- LCD bitmap output;
- decoder/DSP/ASRC audio tail and audible fade-out behavior;
- EQ coefficient loading and line-out analog routing;
- true gapless PCM handoff.

For those areas, the project keeps separate host contracts and byte/checksum
guards. They must not be reported as hardware-equivalent QEMU passes.

## Re-running the real-bank suite

Inside a Linux environment with the MIPS cross compiler, QEMU user-mode and
Rockbox `atjboottool` available:

```sh
ATJBOOTTOOL=/path/to/atjboottool \
CROSS=mips64-linux-gnu- \
QEMU=qemu-mipsel-static \
PYTHON=python3 \
./build.sh --test MECHEN_M30.HEX build/qemu-run
```

The optional library diagnostic is separate and should not be used for the
minimal-safe release:

```sh
./build.sh --test --library MECHEN_M30.HEX /tmp/m30-library-diagnostic
```

## ATJ2127 peripheral model

The repository now also contains a small register-level model in
`tools/sim/atj2127.py`. It is based on the public ATJ2127 reverse-engineering
notes from [actions_flash](https://github.com/kilicdev/actions_flash): UART
FIFO access, the Bluetooth power GPIO, the channel-1 memory-to-UART DMA path,
and the ADFU recovery marker/watchdog sequence are modeled and tested.

This is an intermediate step toward a full machine model. It lets harnesses
exercise firmware-facing peripheral contracts without pretending that the
M30's LCD, SD controller, decoder/DSP, or overlay loader are already emulated.
The actual `qemu-system-mipsel` binary still has no ATJ2127 machine target; a
full firmware boot remains future work.

The closest public reference is [PD196_ATJ2127](https://github.com/Suber/PD196_ATJ2127),
which includes the original-style browser/common UI sources and an old Win32
`case_simulator`. Its listbox driver confirms that the active directory item
uses a measured text rectangle and an 80 ms refresh callback. For the M30
resources, the extracted `common.sty` gives the directory text rectangle as
`x=35, width=205, height=16`, with the folder icon beginning at `x=5`.
Those values are now represented in `tools/sim/listbox.py` and covered by
tests. The same source defines `LIST_ITEM_BUFFER_LEN` as 52 bytes for each
directory entry, so a name can be truncated before the 205-pixel marquee ever
sees it. This explains why the song/folder text can scroll while the full
folder name is still missing; it also gives us a concrete next target for a
safe buffer-size patch instead of guessing from screenshots.
