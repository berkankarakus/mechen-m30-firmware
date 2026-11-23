# M30 upgrade-screen and updater boundary

This note separates what is proven from the remaining updater state machine.
The six historical local corpora share one `upgrade.ap` SHA-256
(`fdcf3a4facf1321b2727614dc6be4340adf0b555428af1fc274dde084d1876d7`), but
the dated twelve-image corpus contains eight distinct `upgrade.ap` hashes.
The probe below passes against all twelve dated images, so the structural
screen boundary is not specific to one community build or one AP variant.
The dated images also share the same `upgrade.sty` and `common.sty` boundary
used by the host preview.

The dated hash groups are recorded here so a future corpus refresh can detect
which AP variant changed without retaining temporary decompiler projects:

| dated images | `upgrade.ap` SHA-256 prefix |
|---|---|
| 2022-08-05 | `d6376e11cbbf6c05...` |
| 2022-08-16 | `1e0c40e2c380aa6f...` |
| 2022-09-14 | `1cd17d9c572609a0...` |
| 2022-11-17 | `5071cdfc78449f56...` |
| 2022-12-16, 2023-02-20, 2025-02-17 | `1d5f7c93658da21...` |
| 2023-07-26, 2024-03-19, 2025-06-26 | `fdcf3a4facf1321...` |
| 2024-02-28 | `d29f7d33f7b31210...` |
| 2024-04-24 | `7a9bc6d64442e76c...` |

## Reproduce the static boundary

```sh
bash tools/ghidra/run_upgrade_ap_probe.sh analysis/community/fw/upgrade.ap
```

To repeat the cross-version check without retaining temporary Ghidra projects:

```sh
bash tools/ghidra/run_upgrade_ap_corpus_probe.sh \
  /Users/berkan/Projects/mechen-m30-evidence
```

The current run reports `UPGRADE CORPUS PASS images=12`. It verifies the same
entry point, five-iteration screen loop, and `upgrade.sty`/`common.sty`
resource-name literals in every dated image; it does not claim that the
unresolved indirect selectors have the same kernel meaning.

The probe maps the real AP bank table with `LoadAP.java`, decompiles only the
small set of upgrade entry/screen/file-boundary functions, and checks the
resource-name literals. It does not execute the overlay or write a candidate.

## Proven screen facts

- The AP entry is `0x40014c31` (MIPS16; decoded function entry
  `0x40014c30`), from the AP header and `LoadAP.java` mapping.
- `FUN_40014d54` clears with `0x18c3`, clears the display rectangle, submits
  control IDs `0x2001` and `0x2000`, and loops exactly five times before
  submitting the option resources. The loop bound is an instruction-level
  fact; the control-ID user-facing names remain unresolved.
- The same function initializes a host-visible selection state byte to zero in
  its prologue. This supports the preview's default selected option `0`, but
  does not prove which physical key changes it.
- `FUN_40014e40` contains the literal references to `upgrade.sty` and
  `common.sty` at the mapped data words `0x40014e88` and `0x40014e94`.
- `upgrade.sty` supplies the five real radio-like PicBoxes and two real text
  viewports. `tools/emu/upgrade_ui.py` renders those resources with a
  host-selected option and records the boundary explicitly.
- The preview's `SELECT UPGRADE FILE:` and `CONFIRM UPGRADE` values are host
  examples, not literals recovered from the screen entry in `upgrade.ap`.
  The distinct `Confirm upgrade file: [%s]` replacement is stored in
  `setting.sty`. In the setting resource table it is text entry 133 (`0x85`);
  `setting.ap` function `FUN_489146e8` selects that ID and then references
  controls `0x1009` and `0x100a`. `upgrade.ap` contains a pointer to that
  MIPS16 entry at file offset `0x13a0` (`0x489146e9`), connecting the prompt
  path to the updater app. The five-option picker is a separate path:
  `FUN_40014d54` draws controls `0x2001`/`0x2000` and iterates the five option
  resources. This supports a separate confirmation window in the same update
  flow, not a second label on the five-option screen. Static decompilation
  shows `FUN_489146e8` stores the text ID through `FUN_489149c8`; it prepares
  control `0x1009` with state byte `1`, and a later path prepares `0x100a`
  with a 250-byte field. `FUN_489149a8` calls through the pointer at
  `0xbfc16589` with raw argument tuples `(0x18c3,0,0,0x14)` and
  `(0,0,0,0x12)` on its observed call sites. `FUN_489149b0` calls through
  `0x48a14601` with the `0x100a` record and another structure. The resident UI
  API implementations are not in the extracted AP. The validation path
  `FUN_40294cf8` calls `FUN_40294c00`, which
  places `0x85` in a text-format structure and passes structures through
  pointer slots `0x48614601` and `0x48ad47b1` (the latter receives control
  `0x8001`). These raw values narrow the API boundary but do not establish
  display coordinates or reliable API names. The
  `bash tools/ghidra/run_setting_confirm_probe.sh` harness now executes the real
  `FUN_489146e8` path to the confirmation request in 155 steps, with external
  services stubbed. It observes the `0x85` text-ID call, then captures the
  request through `0x48a14601`: the control record is
  `0a 10 01 00 ...` (`id=0x100a`, status `1`), and the data record is
  `fa 00 01 01 80 46 55 48 ...` (capacity `250`, two flag bytes `1`, payload
  pointer `0x48554680`). The AP bank map places `0x48554600..0x48554bff` at
  file offset `0xe100`, so this pointer addresses file offset `0xe180` inside
  `setting.ap`. That address is not executable code or RU3 geometry: the event
  translator `FUN_485547ec` reads six-byte mapping records from it. The table
  begins with `{key=0x04, mask=0x0400, result=0}` and is terminated by a zero
  record. Its fallback table at `0x485547c0` has six entries mapping raw key
  and mask pairs to results `0x24`, `0x21`, `0x21`, `0x2202`, `0x2201`, and
  `0x0108`. The same `0x48554680` address is also passed as the 250-byte data
  pointer in the `0x100a` request. That dual use is confirmed; whether the UI
  mutates or reinterprets the storage at runtime remains unknown.

- The timer callback target at `0x40014e2c` is odd MIPS16 `0xbfc37409`, with
  aligned body `FUN_bfc37408`. It computes
  `((field+0x18 + field+0x08) >> 9)`, scales `field+0x20` by 10, maps raw
  values `1 -> 2` and `9 -> 10`, and emits a callback only when the stored
  value changes to an even value. `normalize_upgrade_progress` mirrors these
  raw offsets and rules without invoking the callback or inventing a
  progress-bar resource.

### setting.ap event-poll path

The alternate `param_1 == 0` path is an interactive event loop, not a failed
confirmation request. `FUN_489146e8` sets state `2`, registers control
`0x1009`, and polls until its event flag changes or the event handler returns a
result. `FUN_48914600` obtains an event through `FUN_bfc164bc`, whose mapped
AP-local trap stub at `0xbfc16584` contains `li v1,0x0f; break` and is called
with `(6, buffer, 0, 0x19)`. The adjacent stub at `0xbfc16588` contains
`li v1,6; break`. These are ABI trap selectors, not resolved service names.
With the probe's service interception, `input=0` reaches this ABI boundary before the
stub executes. The event buffer is zero immediately before the call because
the synthetic RAM starts zeroed; the probe does not observe the call's return,
copy an event, or execute a repeat iteration. Static control flow shows the AP
continues polling until its flag changes or the event handler returns a result,
but that interaction is not yet modeled.
`run_setting_confirm_probe.sh ... 0` now stops at that verified boundary in
178 emulated steps and asserts the poll arguments plus all eight
pre-call-buffer bytes. It does not synthesize a keypress or render the screen.
The probe also accepts `input=2..7`, injects event-buffer tuples matching the
six fallback event-map records at `0x485547c0`, and checks the translated
event code at the real dispatcher entry `FUN_48bd4600`. The observed
synthetic cases are:

| Probe input | Injected key / mask | Dispatcher code | Path observed |
|---:|---|---:|---|
| 2 | `0x05 / 0x0400` | `0x0021` | Enters dispatcher, then reaches an unresolved trap selector `0x10` with `(0,0x10002ea8,3,0x0a)` |
| 3 | `0x06 / 0x0400` | `0x0021` | Same dispatcher and trap boundary |
| 4 | `0x09 / 0x1800` | `0x2202` | Stops at follow-up service call `(1,0,0,0x31)` |
| 5 | `0x08 / 0x1800` | `0x2201` | Stops at follow-up service call `(1,0,0,0x31)` |
| 6 | `0x80 / 0x1000` | `0x0108` | Returns from the emulated entry function |
| 7 | `0x7f / 0x3f00` | `0x0024` | Stops at follow-up service call `(1,0,0,0x31)` |

These are synthetic event records, not observed physical key values. For the
`0x21` path the probe logs an additional uninitialized read at `0x48a947f2`
and stops before executing the selector-`0x10` trap. The trap's service
meaning and the post-trap UI state remain unknown. The no-event path also has
an earlier uninitialized state read in the host setup. No corresponding RU3 TextBox geometry was found in
`setting.sty`, so the prompt rectangle and event result rendering remain
unresolved. The preview trace labels text origin so example wording cannot be
mistaken for device output. Both `input=0` and `input=1` probes also pass against
stock V1.101.10 `setting.ap` (SHA-256
`c0693d3750e1b92ad18b0ed741e893e5cffe3bc4517abdc086c54d539e2eb7d5`); this
confirms the same observed UI boundary shapes in that binary, not byte identity
or physical-device behavior.

Probe `input=8` forces the first event service to return `1` without changing
its buffer. The real AP then takes the alternate branch through
`FUN_bfc16528`; with probe-start bytes `0x9fc15602..03` and `0x9fc15608`
left zero, it reaches a second selector-`0x0f` service boundary at
`0xbfc16585` with
`(a0=0,a1=0x10002f98,a2=0,a3=0x19)`. The eight-byte buffer is still zero. The
wrapper's fixed code reads state at `0x9fc15600` and has a callback pointer at
`0xbfc1656c` (`0x48694899`), but the service's return/data contract and the
runtime writer for callback state at `0x9fc15608` are absent from this isolated
probe; the combined probe below covers that writer. This is a controlled
nonzero-return branch probe, not an observed event or device trace.

### `0x9fc15608` callback-slot writer

`FUN_48494600` is a conditional writer for the callback pointer cell at
`0x9fc15608`. The reproducible p-code probe
`tools/ghidra/run_setting_callback_writer_probe.sh <setting.ap>` executes the
real MIPS16 function against both hash-pinned community v1.292.00 and stock
V1.101.10 `setting.ap` inputs. It seeds a synthetic descriptor pointer in
`0x9fc15600`; when descriptor byte `+2` is zero, the function makes one
selector-`0x1a` service call with `(9,0,0,0x1a)` and leaves the callback slot's
`0xdeadbeef` sentinel unchanged. When byte `+2` is one, it first calls the
same selector with `(6,0,0,0x1a)`, stores the supplied MIPS16 callback pointer
`0x40054d79` into `0x9fc15608`, then makes the `(9,0,0,0x1a)` call. Both cases
return through the seeded sentinel in 17 and 25 steps respectively.

The writer-only probe seeds its descriptor, service results, callback-slot
sentinel, and callback argument. A separate hash-pinned
`run_setting_callback_caller_probe.sh` now executes the real
`FUN_40054f78` initializer in both binaries. Its literal table at
`0x4005507c..80` contains callback pointer `0x40054d79` and writer pointer
`0x48494601`. The first call enters real `FUN_48414600(4,1)`. With resident
service calls intercepted and given zero returns, that function builds a
record at `0x9fc1a1b0`, writes its pointer to `0x9fc15600`, and sets
descriptor bytes `+1=4`, `+2=1`, and `+3=1`. The second outside call receives
a synthetic zero return. The same Ghidra session then enters real
`FUN_48494600` with `a0=0x40054d79`; its `+2=1` branch writes that callback
pointer to `0x9fc15608` and returns to the caller in 212 steps total.
This exact AP instruction path passes on stock and community images.
The same emulator memory then runs real `FUN_48914600`. A synthetic primary
service return of `1` takes its alternate event branch. The observed resident
service request sequence is `(6,buffer,0,0x19)`, `(5,buffer,0,0x19)`,
`(1,buffer,0,0x18)`, and `(1,buffer,0,0x19)`, with one auxiliary trap at
`0xbfc16580` between the latter calls. Supplying synthetic zero returns and
placing event word `0x0102` in the last service buffer causes the real AP to
invoke the pointer stored at `0x9fc15608`: entry `0x40054d78`, with callback
argument `0x9fc1bee0` containing `0x0102`. This takes another 219 p-code
steps in each hash-pinned image. The runner requires both the writer and event
bridge pass markers, since Ghidra can exit successfully after a script error.
Ghidra independently locates the indirect call at `0x40054f9c`, and
`FUN_40055200` calls the initializer at `0x40055214`. Sixteen resident calls
receive synthetic zero returns; their real side effects and whether the
physical boot follows this path remain unknown. The event payload and service
returns are host injections; the physical upgrade screen, event source, and
callback effect remain unproven.

## Proven updater boundary, not yet modeled as firmware behavior

- `FUN_40014c30` performs the entry-side operation sequence with selectors
  `0x10`, `0x33`, and `0x4a`; its failure path issues selectors `0x11` and
  `0x34`. These are real call arguments, but their kernel/API names are not
  resolved, so the host emulator does not label them as “flash”, “confirm”,
  or “reboot”.
- `FUN_40054c60` references the real strings `start decrypt...`,
  `decrypt init over`, `decrypt file err`, and `search file over`, and builds
  three metadata reads plus progress resources. This is strong evidence for a
  file/decryption preflight area, not yet proof of the complete state order.
- `FUN_40094c00` and `FUN_40094e3c` are connected to the upgrade AP's file/config
  boundary. Literal references include `nor_ud.drv` and `MECHE_M30 HEX`; the
  exact filename-selection and validation contract still needs the indirect
  resident-call mapping.

## Trace-only host boundary

`tools/emu/upgrade_flow.py` records the five-option selection, confirmation
request, known entry/failure selector values, and the observed decrypt/search
preflight outcomes. It deliberately does not enforce an AP event order that
the indirect calls have not proved. Its trace includes explicit provenance and
forbids `flash`, `reboot`, and `successful-update` events; it is therefore a
testable boundary model rather than an updater emulator.

## Trace-only emulator boundary

`tools/emu/upgrade_flow.py` is the deliberately limited state model for the
verified screen/preflight boundary. It exposes `select`, `confirm-request`,
`decrypt-error`, and `search-complete`, plus raw known/unknown selector events,
without enforcing an unproven AP event order. It must not emulate a successful
flash, power-off, or reboot from these strings alone.
