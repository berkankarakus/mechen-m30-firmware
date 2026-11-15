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

The same host layer contains `tools/emu/folder_ui.py`. It renders browser/list
slots using the observed 50-byte UTF-16 name slot, the `common.sty` 205x16
text viewport at x=35, 30-pixel rows, and the 80 ms active scroll period. Its
JSON trace records the pre-scroll slot text, truncation, pixel offset, source
row index, and selected-row background restore. The eight allocated list slots
include one title slot, leaving seven visible directory rows; selection stays
inside that viewport and wraps at the list edges, matching the real
browser/music handler boundary matrix. This makes the observed
"scrolls but is cut off" behavior and the folder up/down-navigation contract
testable. `FolderList.move_event()` consumes the same burst gears as the
existing acceleration model and applies the recovered wrapping callback. This
still does not claim that the proprietary
LCD/font/input-timing path is emulated or that physical repeat rates have been
measured.

`FolderList.render_at()` can render successive host frames at the reference
listbox's 80 ms active-scroll tick. The timestamped model is deterministic
and useful for visual regression traces, but it is not evidence that the
M30's LCD timer or font rasterizer has been recovered.

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

The build-only path was rechecked with Homebrew's available
`mipsel-linux-gnu-` binutils. It emits `qemu_probe.elf` and patches only the 13
audited literal-pool pointers; the command then stops with the expected
"QEMU user-mode not found" result. This confirms the real-bank ELF boundary
without presenting an unexecuted ELF as a QEMU runtime pass.

As a working executable fallback, `bash tools/ghidra/run_scroll_probe.sh`
executes the same real MIPS16 bank path in Ghidra 12.2's p-code emulator. The
scroll probe passed at the isolated boundary (359 steps); this raises
confidence in the call/return and state layout, but does not emulate the
ATJ2127 peripherals.

The folder-navigation bridge now has an equivalent p-code probe:
`tools/ghidra/run_folder_nav_pcode_probe.sh`. It executes the real
`browser.ap` and `music.ap` handlers at `0x487144a8` and `0x487146cc`, while
intercepting only their redraw/page-reset helpers. With a seven-row window and
ten-item list, the verified transitions are `next: active 7 -> 8` with a
page redraw and `previous: active 7 -> 6` without a redraw. This is stronger
than the earlier decompile-only contract, but it still does not emulate the
LCD, storage, input timing, or a complete M30 boot.

`tools/ghidra/run_folder_nav_matrix_probe.sh` adds fourteen boundary cases per
bank in one Ghidra import per bank. The real handler was verified for 1-, 2-,
7-, 8-, 9-, and 10-item lists,
including the single-item no-op, small-list wrapping, page-end redraw,
next-at-bottom wrap to the first item, and previous-at-top wrap to the last
page. Browser and music produced identical state tuples. The matrix does not
establish LCD rendering or physical key-repeat behavior.

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

The `drv_ui.drv` static checks are grouped by input as well. Pointer, B2/B3,
resident-forwarder, bank-table, and MIPS16-import assertions now run through
`tools/ghidra/run_drvui_matrix_probe.sh` in one Ghidra import, while the former
single-purpose scripts remain available for focused investigation. The full
suite therefore no longer re-imports the same driver eight times.

## Latest results

| Area | Runner | Result |
| --- | --- | --- |
| Shuffle fix | real `mengine.ap` patch bank | PASS |
| Shuffle-all / play-all | real patched engine units | PASS |
| Scroll acceleration | real `browser.ap` bank, stock vs patched | PASS; 30,000 events, 0 failures |
| Folder-list acceleration contract | host model mirroring the real blob | PASS; 58 emulator tests total, 700 ms boundary modeled; physical event timing unmeasured |
| Folder-list handler contract | Ghidra decompile of browser/music next/previous | PASS; stock one-step and redraw calls present |
| Folder-list handler p-code execution | real browser/music MIPS16 handlers with helper intercepts | PASS; next/previous state assertions in both apps |
| Screen-off media keys | real common key-filter bank, five app contexts | PASS; regression-only, no firmware change retained |
| Library/index sorting | real stock/new index banks, synthetic 6,000-song library | PASS; byte-for-byte reproduction |
| Filename natural-order contract | host model | PASS; 11/11 model tests overall |
| Manual-index policy | host state model + static automatic-index guards | PASS |
| Artwork audio-first contract | host state model | PASS |
| USB Audio descriptor/packet contract | six local `usound.drv` corpora + host model | PASS; UAC1 2ch/16-bit/48 kHz, 200-byte isochronous OUT |
| USB Audio ring-consumer boundary | Ghidra `usound.drv` + generic host model | PASS; 0x1000-byte wrap and 100-short-read reset; producer/PCM ownership unmodeled |
| usound MMIO word-port boundary | Ghidra literal pool + generic host model | PASS; modes 1/2/4 and gate are modeled without USB/PCM claims |
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
