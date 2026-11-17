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
  display coordinates or reliable API names. The first p-code attempt could
  not locate its temporary script. After moving the probe into Ghidra's
  configured script path, execution entered `FUN_489146e8` and returned from
  the local mode helper, then stopped with an MIPS16 decode failure at
  `0x48914709`, before any UI API call was captured. No corresponding RU3
  TextBox geometry was found in `setting.sty`, so the prompt rectangle and
  event/caller chain remain unresolved. The preview trace labels text origin
  so example wording cannot be mistaken for device output.
- The timer callback target at `0x40014e2c` is odd MIPS16 `0xbfc37409`, with
  aligned body `FUN_bfc37408`. It computes
  `((field+0x18 + field+0x08) >> 9)`, scales `field+0x20` by 10, maps raw
  values `1 -> 2` and `9 -> 10`, and emits a callback only when the stored
  value changes to an even value. `normalize_upgrade_progress` mirrors these
  raw offsets and rules without invoking the callback or inventing a
  progress-bar resource.

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
