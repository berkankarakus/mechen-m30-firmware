# EQ selector writer and Custom event boundary

## Result

The available M30 `music.ap` code does not establish a UI callback that writes
selector value `7` and reaches `FUN_403d4ed0`. The known Custom MCG callback
ends at a rejected type-3 event in `FUN_48ad47b0`. The ordinary EQ row
callbacks write selector values `0..6`; the producer and refresh dispatcher
have a case for `7`, but the selector-7 writer/caller is still missing.

This is a bounded static/p-code conclusion for the extracted community
V1.292.00 APs, not proof that no fixed-ROM or indirect state-copy path exists.
No device, storage medium, or firmware image was written.

## Callback table and known state writers

The community `music.ap` hash is
`662e379602707a9c4b0dcd6b94b591dd77c2b5f7a557fcb03b8c2a5c9b1baac3`.
`music.mcg` hash is
`f1037bc1fa2ae8a72d57400a39b5345a74830e91742ae7d58310a7b6fed597c3`.

The seven callback pointers in the `music.ap` EQ row table at file offsets
`0xdeec..0xdf64` map to `FUN_403d4cec`, `FUN_403d4d18`, `FUN_403d4d44`,
`FUN_403d4d70`, `FUN_403d4d9c`, `FUN_403d4dc8`, and `FUN_403d4df4`. Static
decompilation shows the callbacks send these `{type,selector}` pairs and then
store the selector at `0x9fc156f4 + 0x19 == 0x9fc1570d`:

| Callback | Sent pair | Stored selector |
|---|---:|---:|
| `FUN_403d4cec` | `{0,0}` | 0 |
| `FUN_403d4d18` | `{7,1}` | 1 |
| `FUN_403d4d44` | `{7,2}` | 2 |
| `FUN_403d4d70` | `{7,3}` | 3 |
| `FUN_403d4d9c` | `{7,4}` | 4 |
| `FUN_403d4dc8` | `{7,5}` | 5 |
| `FUN_403d4df4` | `{7,6}` | 6 |

Each returns `0x8201`. Its framework-level meaning is not established. A Ghidra
reference scan of `0x9fc1570d` in `music.ap` found exactly these seven store
references and reads in `FUN_40094dd4` and `FUN_40154ddc`; there was no direct
store reference with value 7. The seven table callbacks therefore explain the
existing Off plus six built-in choices, not Custom.

`FUN_40094dd4` reads `0x9fc1570d` and passes it to `FUN_40094d4c`. That switch
has a `case 7` which calls `FUN_403d4ed0`. The latter copies the seven Custom
gain bytes and sends `{7,7}` through `FUN_403d4e20` / `FUN_40614f08`. This is a
valid downstream case when the state is already 7; it does not explain who
sets it.

## Custom MCG callback stops before a selector write

The Custom row's AP record at file offset `0xdf70` has ID `0x3301` and a
callback pointer `0x40414c01` at `0xdf78`, targeting `FUN_40414c00`. The same
MIPS16 pointer appears in `music.mcg` at offsets `0x3110` and `0x367a`.
`FUN_40414c00` reads state bytes `0x9fc15706..0x9fc15707`; under its tested
helper-result precondition `-0x7fef`, it sends mode `0x8000` with payload
`{type=3,id=5,0xffff,{0x54,0x7e}}` to `FUN_48ad47b0`.

`FUN_48ad47b0` handles payload types 0, 1, and 2; type 4 has its own early
error return, and every other type enters the unsupported-type return. For
the callback's type 3, the function returns `-0x7fec` before entering its
event loop. This is visible in the target's static control flow and reproduced
by the existing static and p-code probes:

- `bash tools/ghidra/run_eq_custom_event_probe.sh <community-music.ap>` —
  pass; type 3 is rejected and the target returns `-0x7fec`.
- `bash tools/ghidra/run_eq_custom_event_dynamic_probe.sh` — pass for
  community V1.292.00 and V1.101.12. The callback's helper return and missing
  resident/shared-app services are stubbed; the real AP instructions form the
  request and execute the target's rejection path. The event loop is not
  reached.
- `bash tools/ghidra/run_eq_custom_selector_trace.sh <community-music.ap>` —
  pass; with synthetic RAM and service stubs, instruction-step sampling sees
  no value change at `0x9fc1570d` along this callback/request path. This
  sampling alone could miss same-value stores, but the static path also
  returns before any selector writer or the producer.

The request reaches the known shared-app target, but it does not reach
`FUN_403d4ed0`, and this path contains no selector-7 store. Therefore the
existing binaries do not support the claim that choosing the Custom row
selects the engine's Custom preset.

## Cross-module reference boundary

Ghidra `DumpRefsTo.java 0x9fc1570d` was run after `LoadAP.java` on all eleven
community APs. `music.ap` contains the reads and seven writes described above.
The other ten (`browser`, `config`, `mainmenu`, `manager`, `mengine`,
`playlist`, `setting`, `udisk`, `upgrade`, and `usound`) produced no direct
references to that address.

This is a direct-reference result, not a proof that no module can alter the
byte. A copy of a larger state block, a register-derived pointer, a resident
service, or fixed-ROM code may write it without an address xref. In
particular, it does not rule out a persisted selector value being restored
into the overlapping RAM region. No selector-7 runtime write was established
by the probes in this report.

## Reproduction boundary and next step

The row-pointer topology is checked by
`PYTHONPATH=tools/emu python3 tools/emu/eq_menu_probe.py <music.ap> <music.mcg>`.
For the selector references, load each AP with `tools/ghidra/LoadAP.java` and
run `tools/ghidra/DumpRefsTo.java 0x9fc1570d`; for the callback body and target,
the existing EQ Custom event/selector probes above reproduce the boundary.

The highest-value remaining step is to resolve the framework callback dispatch
for MCG ID `0x3301` and the selector-state initialization/copy path. The
available callback/receiver path currently terminates at the type-3 rejection;
do not infer a selector-7 write from the existence of the producer's `case 7`.
