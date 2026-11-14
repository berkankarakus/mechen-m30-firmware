# Ghidra-guided M30 UI emulator

This is the first layer of the hybrid emulator. It is intentionally small and
deterministic:

1. `FirmwareTrace` parses the real `music.ap` bank table, checks the
   Ghidra-audited shared marquee call at `0x40d55078`, and resolves the
   literal-pool UI/timer pointers around `0x40d5516c`.
2. `MusicStyle` parses the real M30 `music.sty` RU3 control records.
3. `NowPlaying` replays the UI boundary as a trace and renders a 320x240 PPM
   framebuffer using the real textbox geometry and RGB565 colors.
4. `scroll_descriptor.py` models the verified state/event offsets used by
   `FUN_40d54f2c` and `FUN_40d54d80`.
5. `ui_dispatcher.py` provides the conservative host shim for the verified
   dispatcher target `0xbfc16405`.
6. `make_qemu_probe.py` prepares a non-firmware ELF probe that calls the real
   MIPS16 renderer with only the audited literal pointers redirected to test
   stubs.
7. `tools/ghidra/run_scroll_probe.sh` executes that same real-bank renderer in
   Ghidra's MIPS p-code emulator, which is currently the executable path on
   macOS because upstream QEMU has no ATJ2127 machine and user-mode QEMU is
   unavailable here.
8. `driver_banks.py` parses the real `drv_ui.drv` overlay table and exposes
   far-pointer payload candidates without treating every candidate as code.
   It preserves the raw B2 `0x471` provenance while exposing its aligned
   MIPS16 entry offset `0x470`; the unresolved B2 `0x4e9` entry remains
   separate from that validated path.
9. `tools/ghidra/run_kernel_exception_probe.sh` checks the extracted
   `ker_xsys` exception entry and records the boundary where the unavailable
   fixed handler begins.
10. `yqhx.py` parses the resident driver's three copy segments, BSS range,
   entry fields, and the kernel's mode-dependent slot layout. It is a load
   plan only; it never executes raw payload bytes.
11. `driver_loader.py` models the two decompiled resident loader contracts:
   `FUN_bfc0a408` has the mode 6/7 compact-slot branch and entry callback,
   while `FUN_bfc0a578` always uses twelve-byte slots and has no callback.
12. `provider_scan.py` reproduces the negative A19/B16 provider scan across
   extracted `.drv` members. It reports byte occurrences only and does not
   infer executable ownership from a match.
13. `tools/ghidra/run_drvui_pointer_probe.sh` maps the complete UI driver as
   a static MIPS16 corpus and reports each observed far-pointer literal with
   its containing Ghidra function when one is known.
14. `tools/ghidra/run_drvui_b2_probe.sh` remaps the real B02 bank and checks
    the paired `+0x471`/`+0x4e9` candidates: the former decompiles from the
    aligned MIPS16 address while the latter terminates as bad instruction
    data.
15. `bank_runtime.py` models lazy bank selection and load events. It only
    permits explicitly validated entry offsets to become executable; an
    unresolved candidate is recorded but never called. Load events preserve
    both the raw pointer offset and the aligned MIPS16 entry offset.

The kernel-side constant boundary can be reproduced without a device with:

```sh
bash tools/ghidra/run_kernel_bank_boundary_probe.sh \
  analysis/community/fw/kernel.drv
```

Static references to the resident loader candidates can be checked with
`tools/ghidra/run_kernel_loader_refs_probe.sh`; the current extracted image
has zero direct references to all six targets, so their callers remain table
or external-dispatch mediated.

The external-provider scan can be widened from `.drv` members to the complete
extracted firmware tree:

```sh
PYTHONPATH=tools/emu python3 tools/emu/provider_scan.py \
  --all-files analysis/community/fw
```

Run it with extracted firmware resources:

```sh
PYTHONPATH=tools/emu python3 tools/emu/m30_ui.py \
  --music-ap build/qemu-minimal-safe/work/verify/fw/music.ap \
  --music-sty build/qemu-minimal-safe/work/verify/fw/music.sty \
  --title 'LONG TITLE' --artist 'ARTIST' --album 'ALBUM' --file 'FILE' \
  --out /private/tmp/m30-now-playing.ppm \
  --trace /private/tmp/m30-now-playing-trace.json
```

This does not execute the MIPS bank. It is the host-side framebuffer and
trace target for the next QEMU step. A complete ATJ2127 boot still needs the
real bank loader, UI dispatcher, LCD, key, SD and decoder devices; those are
not silently replaced by this renderer.

When `--trace` is supplied, the JSON also contains `observed_dispatch`: the
verified nine-call envelope from the Ghidra real-bank probe. Pointer payloads
are kept as semantic labels until their internal ownership is proven.

## Preparing the real banks for QEMU

`prepare_qemu_banks.py` extracts every bank from `music.ap` and emits an
assembly include, a linker fragment, and a manifest. Each bank remains at the
exact load address recorded in the AP table, including the bank containing
`FUN_40d54f2c`. This is the input boundary for the next user-mode harness:

```sh
PYTHONPATH=tools/emu python3 tools/emu/prepare_qemu_banks.py \
  build/qemu-minimal-safe/work/verify/fw/music.ap /private/tmp/m30-music-banks
```

The generated files are intentionally separate from the firmware build. No
HEX is changed and no new code is flashed by this step.

When assembling the generated include, run the assembler from the generated
directory because the `.incbin` paths are relative to it:

```sh
cd /private/tmp/m30-music-banks
mipsel-linux-gnu-as -EL -mabi=32 -mips32 -o banks.o banks.s
```

The complete probe build/run is automated by
`tools/emu/run_qemu_probe.sh`:

```sh
CROSS=mipsel-linux-gnu- QEMU=qemu-mipsel-static \
  bash tools/emu/run_qemu_probe.sh \
  build/qemu-minimal-safe/work/verify/fw/music.ap /private/tmp/m30-qemu-probe
```

If user-mode QEMU is unavailable, the script still produces `qemu_probe.elf`
and exits with a clear not-executed status.

## Executing the real MIPS16 path in Ghidra

The isolated renderer can be executed without a full SoC model:

```sh
bash tools/ghidra/run_scroll_probe.sh \
  build/qemu-minimal-safe/work/verify/fw/music.ap
```

The script builds the raw stub section when needed, imports the AP with
`LoadAP.java`, initializes the recovered scroll descriptor, and runs
`FUN_40d54f2c` until its controlled return. It uses a temporary project and
does not alter the firmware or create a flashable image.

To exercise one real event transition directly:

```sh
bash tools/ghidra/run_scroll_probe.sh \
  build/qemu-minimal-safe/work/verify/fw/music.ap next
bash tools/ghidra/run_scroll_probe.sh \
  build/qemu-minimal-safe/work/verify/fw/music.ap previous
bash tools/ghidra/run_scroll_probe.sh \
  build/qemu-minimal-safe/work/verify/fw/music.ap redraw
```

The probe asserts the active/previous slot bytes and status after each event.
