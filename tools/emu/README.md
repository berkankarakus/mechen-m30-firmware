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
12. `provider_scan.py` reproduces the negative A17/A19/B16 provider scan across
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
16. `tools/ghidra/run_drvui_pointer_cluster_probe.sh` groups the 16 observed
    far-pointer literals by nearby file offsets; the B3 literal pool is the
    verified five-hit cluster at `0x992c..0x996c`.
17. `tools/ghidra/run_drvui_resident_probe.sh` maps that B3 region together
    with the two resident `drv_ui` segments and verifies the extracted
    `bfc09c00` syscall wrapper plus the `bfc0a8bc`/`bfc0a8c8` state setters.
18. `resident_ui.py` carries those verified resident effects into the host
    model while aligning odd MIPS16 pointers and refusing unknown targets.
19. `scan_mips16_imports.py` parses the real B3 MIPS16 disassembly and reports
    indirect-call delay slots that select an import number. The current M30
    bank proves selector 15/17 pairs, but the tool intentionally does not
    assign semantics to those selectors.
20. `tools/ghidra/run_drvui_b3_table_probe.sh` maps the B3 tail and the
    following data area, then dumps the pointer words consumed by the second
    B3 UI function. It verifies the two resident entries and three
    bank-qualified candidates without treating any candidate as a directly
    executable address.
21. `tools/ghidra/run_drvui_b3_candidate_probe.sh` maps the B04, B07, and B08
    candidate banks together with their post-bank literal areas. The three
    aligned candidate offsets decompile as coherent MIPS16 functions, which is
    stronger evidence than a numeric bank-offset match but still not a proof
    of the hardware dispatcher ABI.
22. `tools/ghidra/run_folder_nav_probe.sh` decompiles the real browser/music
    `next` and `previous` handlers and checks their shared one-step and redraw
    contract before the acceleration candidate is considered applicable.
23. `compare_firmware_versions.py` compares hashes and provider-pointer counts
    across a directory of extracted M30 release images. It excludes the known
    `drv_ui.drv` consumer by default, so repeated pointer literals in the
    container or consumer are not misclassified as provider modules.

`tools/sim/ui_calls.py` carries the resulting safety policy into the host
model: B02 `+0x471` is `lazy-load-then-call`, B02 `+0x4e9` is
`never-direct-call`, and A19/B16 candidates remain `lazy-only` because their
providers are absent from the extracted M30 driver.

`LazyBankRuntime.dispatch()` exposes the same policy in every
`DispatchResult`, so callers do not have to infer safety from the status
string or execute an unresolved candidate accidentally.

`test_real_drv_ui.py` repeats the critical B02/A19/B16 assertions against the
archived community `drv_ui.drv`, in addition to the synthetic unit fixtures.

The complete read-only validation suite is:

```sh
bash tools/emu/run_static_suite.sh
```

Use `--host-only` when Ghidra/MIPS binutils are unavailable; the default mode
also runs the real driver, kernel, exception, and MIPS16 `next`, `previous`,
and `redraw` scroll probes.

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

Repeatable `--pointer 0x...` arguments allow the same tool to scan a custom
provenance set. The known consumer `drv_ui.drv` contains the A17/A19/B16
literal references by design, so a provider-only negative check excludes that
file:

```sh
PYTHONPATH=tools/emu python3 tools/emu/provider_scan.py \
  --all-files analysis/community/fw --exclude-name drv_ui.drv --require-zero
```

That check currently finds zero copies in the other extracted members. The
separate `--require-zero` call in the static suite checks the six resident
loader addresses and `0xbfc06d6c` across the complete tree.

For a corpus of extracted release directories, use the version comparison
tool. Each child directory must contain a `fw/` directory:

```sh
PYTHONPATH=tools/emu python3 tools/emu/compare_firmware_versions.py \
  /private/tmp/m30-version-compare --require-zero
```

The tool reports module SHA-256 values and provider-only pointer counts for
each version. See [`docs/findings-version-corpus.md`](../../docs/findings-version-corpus.md)
for the twelve-image result currently archived locally.

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

## Folder/list visualizer

`folder_ui.py` renders the evidence-based browser/list layer separately from
the now-playing screen. It uses the observed `common.sty` geometry (`x=35`,
205 px by 16 px text viewport, 30 px rows) and applies the browser's 50-byte
UTF-16 name slot before drawing. This is important for the original symptom:
the marquee can move a name that was already truncated by the list buffer, but
it cannot restore discarded characters. The selected row is redrawn as a
solid selection background on every host frame, so a later QEMU shim can be
checked for the red-tail artefact independently of the proprietary font.

Example:

```sh
PYTHONPATH=. python3 tools/emu/folder_ui.py \
  --out /tmp/m30-folder.ppm \
  --trace /tmp/m30-folder.json \
  --selected 1 --offset 7 \
  Music "A very long folder name that is truncated"
```

The output is still a host visualization; it is not evidence that the M30
firmware boots under generic `qemu-system-mipsel`.

When `--trace` is supplied, the JSON also contains `observed_dispatch`: the
verified nine-call envelope from the Ghidra real-bank probe. Pointer payloads
are kept as semantic labels until their internal ownership is proven.

## Preparing the real banks for QEMU

`prepare_qemu_banks.py` extracts every bank from `music.ap` and emits an
assembly include, a linker fragment, and a manifest. Each bank remains at the
exact load address recorded in the AP table, including the bank containing
`FUN_40d54f2c`. This is the input boundary for the next user-mode harness:
the manifest also records the source AP SHA-256, and probe preparation checks
that the source hash is unchanged before and after copying.

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

The B3 import-selector cross-check is read-only and compares MIPS binutils with
Ghidra's mapped instruction list:

```sh
bash tools/ghidra/run_drvui_import_probe.sh analysis/community/fw/drv_ui.drv
```

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

## Folder-list acceleration model

`scroll_accel.py` mirrors the existing `tools/scroll/accel.c` candidate in
the host emulator. It covers the burst gears, direction/pause reset, list
boundaries, and the mode-4/update-2 page-reload contract. The modeled input is
the shared folder-list next/previous callback, so it applies to up/down key
events as well as any other control routed through those callbacks. It is a
model only: it does not patch an AP or claim that the device's physical key
repeat/event rate has been measured.

The burst boundary is explicit in the model: events separated by 700 ms or
less remain in the same burst, while a 701 ms gap resets to one item. Thus a
physical up/down key repeat rate can be checked directly against this contract
without assuming that the control is a wheel.
