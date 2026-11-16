# M30 upgrade-screen and updater boundary

This note separates what is proven from the remaining updater state machine.
All six local extracted corpora have the same `upgrade.ap` SHA-256
(`fdcf3a4facf1321b2727614dc6be4340adf0b555428af1fc274dde084d1876d7`), and
also share the same `upgrade.sty` and `common.sty`. The evidence below is
therefore not specific to the community build only.

## Reproduce the static boundary

```sh
bash tools/ghidra/run_upgrade_ap_probe.sh analysis/community/fw/upgrade.ap
```

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
- The timer callback target at `0x40014e2c` is odd MIPS16 `0xbfc37409`, with
  aligned body `FUN_bfc37408`. It computes
  `((field+0x18 + field+0x08) >> 9)`, scales `field+0x20` by 10, maps raw
  values `1 -> 2` and `9 -> 10`, and emits a callback only when the stored
  value changes to an even value. `normalize_upgrade_progress` mirrors these
  raw offsets and rules without invoking the callback or inventing a
  progress-bar resource.

## Proven updater boundary, not yet modeled as behavior

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

## Emulator boundary

The next implementation step is a trace-only state model for the verified
screen loop and preflight outcomes. It may expose `select`, `confirm-request`,
`decrypt-error`, and `search-complete` only after the corresponding indirect
call return values are mapped. It must not emulate a successful flash, power
off, or reboot from these strings alone.
