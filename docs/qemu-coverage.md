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
| Folder-list acceleration contract | host model mirroring the real blob | PASS; 700 ms boundary modeled; physical event timing unmeasured |
| Folder-list handler contract | Ghidra decompile of browser/music next/previous | PASS; stock one-step and redraw calls present |
| Folder-list handler p-code execution | real browser/music MIPS16 handlers with helper intercepts | PASS; next/previous state assertions in both apps |
| Screen-off media keys | real common key-filter bank, five app contexts | PASS; regression-only, no firmware change retained |
| Library/index sorting | real stock/new index banks, synthetic 6,000-song library | PASS; byte-for-byte reproduction |
| Library scan capacity | `playlist.ap` fixed-array scan loop | PASS; stock 4,000-record stop modeled separately from file-format capacity |
| MUSIC.LIB file layout | documented library header, `tools/library/libmodel.py` sector writer, independent public hex comparison, and real M30 card image | PASS; header, section directories, padded record area, raw nodes, decoded `cluster_no`/`dir_entry` key, and bounded active-record lookup are modeled; primary location blob, record links, and exact duplicate-key tie-break remain unresolved |
| Filename natural-order contract | host model | PASS; deterministic host contract |
| Manual-index policy | host state model + static automatic-index guards | PASS; manual path and tested powered-card automatic-rebuild path are separate; other triggers remain device-specific |
| Artwork audio-first contract | host state model | PASS |
| ASRC/EOF advance boundary | archived `music.ap` delta + host model | host contract present; mode-4 community path modeled, audible drain unverified |
| `mmm_bp` ring/fade boundary | six-corpus `mmm_bp.al` + host model | PASS; wrap-aware source-byte reads, 0x200 refill and fade arithmetic modeled; DSP/callback semantics unresolved |
| Metadata reader boundary | archived `music.ap` delta + host model | host 0x200 split/flush, source-byte reads and trailing-skip arithmetic present; parser/callback ABI unresolved |
| Artwork fallback/cache | community `music.ap` decompile + host models | policy and `ALBUM.PIC` record modeled; JPEG decode, SD/CPU timing and UI render unverified |
| Screen-off key-filter/session path | real common key-filter bank + host folder session | PASS; stock wake and patched five-key navigation modeled |
| USB Audio descriptor/packet contract | six local `usound.drv` corpora + host model | PASS; UAC1 2ch/16-bit/48 kHz, 200-byte isochronous OUT |
| USB Audio ring-consumer/stream boundary | Ghidra `usound.drv` + bounded host stream | PASS; 0x1000-byte wrapped byte reads, firmware's zero-on-wrap read-pointer reset, and 100-short-read reset; decoder/PCM ownership remains separate |
| Real `usound.drv` leaf execution | exact 0xbfc30000 segment + QEMU/MIPS16 JALX wrapper | PASS; `FUN_bfc30cac` byte copy and `FUN_bfc30ce8` 3-to-4 expansion execute in QEMU; globals/peripherals remain outside |
| Real `usound.drv` ring-consumer execution | exact segment + relocated literal-pool state + real MIPS16 callback syscall | PASS; `FUN_bfc31654` consumes linear and wrapped requests, invokes the real `selector=0x10` callback twice on wrap, and resets its read pointer to zero; kernel service/DAC side effect remains unresolved |
| Real `usound.drv` callback syscall | exact segment + QEMU exception-vector shim | PASS; `0xbfc326a9` executes as MIPS16 `li v1,0x10; break 0`, and the four callback arguments survive the trap boundary; kernel service effect remains unresolved |
| USB mass-storage request boundary | Ghidra `uhost.drv` command builder + host model | PASS; request fields and exact sector-byte transfer through the SD device modeled; CBW/CSW framing, status meaning and controller timing unresolved |
| usound MMIO word-port boundary | Ghidra literal pool + generic host model | PASS; modes 1/2/4 and gate are modeled without USB/PCM claims |
| Real `usound.drv` word-port execution | exact segment + relocated bfc3194c/bfc31950/bfc31954 pool | PASS; `FUN_bfc318cc` executes mode 1/2/4 and gate behavior in QEMU; the guest RAM ports are not physical MMIO |
| usound byte-format boundary | Ghidra copy/3-to-4 helpers + host model | PASS; direct copy and complete 3-byte to 4-byte expansion |
| usound software-ring producer | Ghidra `FUN_bfc30dc4` + host model | PASS; 0x6e40 wrap, overrun rule, and 0x1b90/0x3720 ready thresholds |
| Real `usound.drv` producer execution | exact segment + relocated literal-pool state + real MIPS16 leaves | PASS; `FUN_bfc30dc4` executes linear, wrapped, and fixed-point 3-to-4 producer paths in QEMU; callbacks and MMIO are shimmed |
| Real `drv_lcd.drv` window/orientation execution | exact resident segment + relocated command/data pool + MIPS16 callback shims | PASS; `FUN_bfc0a378` emits the verified `0x2a/0x2b/0x2c` path and `FUN_bfc0a438` emits orientation `2 -> 0x48`; physical panel timing remains unresolved |
| LCD-backed now-playing preview | real `music.ap`/`music.sty` host renderer + recovered LCD sink | PASS; visible 320x240 RGB565 round-trip with `0x36,0x2a,0x2b,0x2c` trace; hybrid preview, not full ATJ2127 boot |
| Ghidra-guided now-playing framebuffer | real `music.ap`/`music.sty` inputs + host renderer | PASS; bank/call-site/geometry checks |
| LCD address-window transfer | `drv_lcd.drv` commands `0x36/0x2a/0x2b/0x2c` + host framebuffer sink | PASS; recovered raw orientation values and bounded RGB565 window writes modeled; orientation semantics/controller timing unresolved |
| Real MIPS16 renderer smoke probe | exact `music.ap` banks + 13 verified pointer stubs | PASS in Ghidra p-code; 359 steps; QEMU ELF also links |
| Real MIPS16 event transitions | `FUN_40d54d80`, exact bank + key/UI stubs | PASS; next 94 steps, previous 90, redraw 121 |
| MCG/RU3 resource metadata | six-corpus byte-identical resource members | PASS; immutable node/group catalog, localized names unresolved |
| Decoder write callback | community `mengine.ap` callback boundary | PASS; unconfigured/known callback returns `-1`, unknown pointer fail-closed |
| EQ message/coefficient boundary | `mengine.ap` dispatcher and `music.ap` selector path | PASS; message `0x303`, `{eq_type, selector}` envelope, seven gain rows; DSP calls unresolved |
| FAT32/exFAT extension boundary | six-corpus resident driver table | PASS; shared 31-slot vocabulary and explicit-slot host filter; caller mask/walker unresolved |
| Library extension masks | `playlist.ap` raw mask words at `0x2a20`/`0x2a28` plus resident matcher loop | PASS; MUSIC `0x7e190ea0` (14 bits), M3U `0x00080400` (2 bits); driver slot order is bit 31→slot 0 through bit 1→slot 30 |
| Library tag-reader selector | `playlist.ap` `FUN_40094f2c` mapping | PASS; types 0–7 plus type-8 fallback; reader ABI/metadata parsing unresolved |
| Library fallback record | `playlist.ap` type-8/tag-failure path | PASS; 8.3 title formatting, fixed fallback fields, and bounded track selector |
| MUSIC.LIB record codec | documented 256-byte scan record layout plus `index.c` field accesses | PASS; text/flags/track fields and the `cluster_no`/`dir_entry` key are decoded, while the primary location blob and record links remain opaque |
| Library directory walker | stock `playlist.ap`/playall walker contract | PASS; DFS order, depth 8, `RECORD` skip, target count; filesystem callbacks unresolved |
| SD sector/capacity boundary | `cards.drv` 512-byte transfer and capacity path | PASS; host sector device with card presence, bounds checks and explicit `sector_count * 512` capacity |
| Resident `yqhx` loader materialization | kernel loader copy/BSS evidence + host sparse memory | PASS; declared segments and BSS are applied without entry execution; fixed ROM handoff unresolved |

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

The application-level key filter is now represented by
`tools/sim/key_filter.py`. It is intentionally below the unresolved physical
key-driver/MMIO boundary: normalized events are delivered while the screen is
on, the `WAKE_ONLY` screen-off policy turns non-power events into wake message
`0x106`, and the remembered wake key's long-press/release sequence is
discarded. The changelog-backed `MEDIA_KEYS_PASS` policy routes only
play/pause, previous, next, volume up, and volume down through the normal
delivery path while the screen is off. This is host-emulator behavior with
deterministic tests, not a claim that physical button sampling or repeat timing
has been recovered.

`tools/sim/usb_audio_stream.py` now composes the observed USB Audio
descriptor with the 4 KiB ring-consumer boundary. It accepts only the
descriptor's exact 200-byte stereo packet, preserves packet bytes across the
ring wrap, and rejects over-capacity writes. This is a host stream contract;
it does not promote the unresolved `usound` producer callback into a codec,
DAC, or hardware-DMA implementation.

The recovered packet/ring boundary also has a real QEMU system-CPU smoke probe:
`bash tools/emu/run_qemu_usb_audio_probe.sh`. It links freestanding little-
endian MIPS32 code and runs it on QEMU's Malta machine. The guest queues 32
synthetic 200-byte packets, consumes them in two batches, crosses the 4 KiB
ring wrap, and verifies every byte before reporting
`USB AUDIO QEMU BOUNDARY PASS`. Malta's FPGA UART is used only for the result
line. This is stronger than a host-only test for CPU, guest memory, and ring
arithmetic, but it is not a M30 boot: QEMU still does not model the ATJ2127
USB controller, VBUS/device negotiation, the `usound.drv` callback, codec/DAC
routing, or the physical headphone/line output.

`bash tools/emu/run_qemu_usound_leaf_probe.sh` goes one step closer to the
firmware: it extracts the exact 0x26b0-byte resident segment from
`usound.drv`, maps it at a fixed guest address, and enters the real MIPS16
functions `FUN_bfc30cac` and `FUN_bfc30ce8` through `JALX`. The wrapper checks
the copy and `[0,b0,b1,b2]` expansion outputs byte-for-byte. This proves real
driver instructions and their leaf calling convention under QEMU, but it
does not prove the driver entry, its global state, USB controller interrupts,
the callback at `0xbfc326a9`, or DAC/codec output.

`bash tools/emu/run_qemu_usound_ring_probe.sh` now executes the real
`FUN_bfc31654` consumer with its six recovered literal-pool state words
relocated into guest RAM and the actual `0xbfc326a9` callback restored. Two
calls pass: a linear 16-byte read and a wrapped 32-byte read that invokes the
real callback twice. The QEMU result exposed an important exact behavior:
after the read pointer crosses `0x1000`, the firmware stores zero rather than
retaining the remainder. `tools/sim/usb_ring.py` and its tests now follow that
observed behavior. The exception handler records the callback envelope only;
the kernel service, PCM ownership, and DAC output remain outside coverage.

`bash tools/emu/run_qemu_usound_port_probe.sh` executes the real
`FUN_bfc318cc` helper after relocating only its recovered gate, data-port, and
alternate-port literal words. QEMU verifies mode 2 reads, mode 1 writes, mode
4 alternate reads, and the gate byte that suppresses mode-2 reads. These are
guest-RAM stand-ins for the original MMIO addresses; no claim is made about
the physical USB controller, FIFO timing, or codec/DAC routing.

`bash tools/emu/run_qemu_usound_callback_probe.sh` executes the real odd
callback target `0xbfc326a9` (aligned MIPS16 entry `0xbfc326a8`). The guest
redirects CP0 `EBase` to a RAM exception vector, catches the callback's
`break 0`, and returns through the interrupted caller continuation. Across
all six local `usound.drv` corpora, QEMU observes selector `v1=0x10` and the
four arguments used by the ring consumer. This resolves the callback's
syscall envelope, not the kernel service or eventual PCM/DAC side effect.

`bash tools/emu/run_qemu_usound_producer_probe.sh` now executes the real
`FUN_bfc30dc4` producer. Its QEMU guest supplies only the recovered state
words, a no-op poll/fill/port callback, and the exact MIPS16 copy helpers. The
probe passes a linear write, a write split at the `0x6e40` ring end, and the
format-1 fixed-point `0xaaaaaaab` size path. This verifies the producer's
control flow and state arithmetic, but not the USB polling callback, hardware
FIFO, interrupt timing, or DAC/codec output.

`bash tools/emu/run_qemu_lcd_probe.sh` executes the real LCD resident helpers
`FUN_bfc0a378` and `FUN_bfc0a438`. The guest relocates only the driver's
command/data literal words and replaces setup/transfer callbacks with no-op
MIPS16 shims. Across all six local LCD corpora, a window `(x=2,y=3,w=4,h=5)`
reaches the final `0x2c` memory-write command with row-end byte `7`, and
orientation `2` reaches `0x36/0x48` with mode state `2`. This validates the
framebuffer command boundary, not LCD electrical behavior, controller timing,
or pixel visibility on the device.

`tools/emu/lcd_preview.py` composes that boundary with the real-resource
now-playing renderer:

```sh
python3 tools/emu/lcd_preview.py \
  --music-ap build/qemu-minimal-safe/work/verify/fw/music.ap \
  --music-sty build/qemu-minimal-safe/work/verify/fw/music.sty \
  --out /private/tmp/m30-lcd-preview.ppm \
  --trace /private/tmp/m30-lcd-preview.json
```

The resulting PPM is a user-visible 320x240 preview and the trace records the
four recovered LCD commands and all 76,800 pixels. It is intentionally called
a hybrid preview: the actual UI resource renderer is host-side until a
MIPS-user-mode run of the bank path and an ATJ2127 LCD device model are
available.

For one command that first executes the real LCD QEMU probe and then emits the
visible preview, use:

```sh
bash tools/emu/run_lcd_preview.sh
```
