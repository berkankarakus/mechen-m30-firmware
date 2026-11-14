# QEMU coverage for the M30 work

## What is emulated

The QEMU harness is prepared for QEMU's MIPS32 little-endian user-mode CPU
runner. It loads real M30 `.ap` banks into freestanding test harnesses and
replaces only the kernel/file-system/timer calls that each harness needs. On
this macOS host the equivalent executable check currently runs through
Ghidra's MIPS p-code emulator; neither path is a complete M30 boot.

The first Ghidra-guided UI layer is now in `tools/emu/`.  It consumes the real
`music.ap` bank table and verifies the audited shared marquee instruction at
`0x40d55078`, consumes the real `music.sty` textbox records, and renders a
320x240 host framebuffer plus a JSON UI-dispatch trace.  This gives us a
repeatable target for the eventual QEMU host shim without presenting a static
HTML mockup as firmware execution.  The renderer is deliberately labelled a
host emulator: it does not claim to emulate the proprietary LCD or UI
dispatcher.

`tools/emu/prepare_qemu_banks.py` is the next bridge toward real bank
execution. It extracts all 87 `music.ap` banks and emits exact-address
assembly/linker inputs plus a manifest. The eventual user-mode harness will
add only the dispatcher/timer/resource shims that the traced function reaches;
it will not treat `qemu-system-mipsel -M malta` as an ATJ2127 machine.

The isolated probe is reproducible with `bash tools/emu/run_qemu_probe.sh`. On a
Linux host with MIPS binutils and `qemu-mipsel-static`, it links the real bank
code and runs the cancel-event path. On this macOS host the probe ELF links
successfully, but user-mode QEMU is not installed; `qemu-system-mipsel` cannot
substitute for it because it has no Linux user-mode runner or ATJ2127 machine.

As a working executable fallback, `bash tools/ghidra/run_scroll_probe.sh`
executes the same real MIPS16 bank path in Ghidra 12.2's p-code emulator. The
scroll probe passed at the isolated boundary (359 steps); this raises
confidence in the call/return and state layout, but does not emulate the
ATJ2127 peripherals.

The decompiled function signature and first shim boundary are now confirmed:
`FUN_40d54f2c(ushort event_or_style, int *scroll_state) -> short`. Its
literal-pool targets include the UI dispatcher `0xbfc16405`, backlight/status
helpers in `0x4845xxxx`, and the timer `0xbfc16bb1`. The host harness can now
fail closed on an unexpected AP pointer instead of calling an unverified
address.

For the driver-side marquee path, `tools/sim/ui_calls.py` now adds a second
fail-closed layer: the five observed B3 far pointers are labelled only when
their call shape matches the public UI signature (`fix_switch_fontlib`,
`fixf_get_string_length`, the two Arabic/Hebrew transforms, or
`put_string_line_sdimage`). This improves the host trace without pretending
that the missing ATJ2127 bank manager has been emulated.

The same model now records three additional B3 trailing-table entries. Their
aligned MIPS16 bodies were decompiled after mapping each nominal bank together
with its post-bank literal area: B04 `+0x751`, B07 `+0x694`, and B08 `+0x401`.
They are marked `lazy-load-then-call` only after that static validation; the
host never jumps to the raw far pointer or claims that the hardware dispatcher
has been recovered.

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
| Ghidra-guided now-playing framebuffer | real `music.ap`/`music.sty` inputs + host renderer | PASS; bank/call-site/geometry checks |
| Real MIPS16 renderer smoke probe | exact `music.ap` banks + 13 verified pointer stubs | PASS in Ghidra p-code; 359 steps; QEMU ELF also links |
| Real MIPS16 event transitions | `FUN_40d54d80`, exact bank + key/UI stubs | PASS; next 94 steps, previous 90, redraw 121 |

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
tests. The model now also applies the M30 directory callback's 50-byte UTF-16
slot budget before scrolling: 2 bytes for the BOM and 2 for the terminator
leave 46 payload bytes. The same source defines `LIST_ITEM_BUFFER_LEN` as 52
bytes for each directory entry, so a name can be truncated before the
205-pixel marquee ever sees it. This explains why the song/folder text can
scroll while the full folder name is still missing; it also gives us a concrete
next target for a safe buffer-size patch instead of guessing from screenshots.
