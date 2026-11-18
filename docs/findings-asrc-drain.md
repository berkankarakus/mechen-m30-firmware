# End-of-track ASRC/EOF branch

This is a static comparison of the stock M30 `V1.101.10` `music.ap` against
the archived `V1.101.11` and community V1.292.00 images. It does not measure
the DAC, ASRC queue, or audible output on a device.

## Confirmed binary delta

The three images use the same `music.ap` bank layout. In the bank beginning at
file offset `0x9c00` / runtime address `0x40494c00`, the six bytes at file
offset `0x9f5c` change as follows:

```text
stock:     58 67 01 5a 22 61
V1.101.11: 24 60 04 72 0a 60
community: 24 60 04 72 0a 60
```

The surrounding code belongs to `FUN_40494e94`; the changed area is reached
through the odd MIPS16 address `0x40494f5d`. Ghidra's containing-function
decompile shows the following control-flow difference:

- stock: mode `3` enters the existing `+11000U` end-of-track branch;
- V1.101.11/community: an additional `mode == 4` case falls through to the
  same advance path before that branch is evaluated.

The reproducible guard is:

```sh
bash tools/ghidra/run_asrc_probe.sh
```

It decompiles stock, V1.101.11, and community images, asserts the mode-4
control-flow difference, and checks the raw six-byte replacement.

## Interpretation and limits

This is strong evidence for the community's end-of-track playback/ASRC
correction and explains why it is the best existing candidate for the reported
Audacity fade-out tail loss. It does not prove that the six-byte change alone
drains every DAC/ASRC sample, nor that every codec uses the same mode. The
host emulator records the narrow control-flow boundary in
`tools/sim/asrc_model.py`: mode `3` takes the existing advance path in both
variants, while mode `4` does so only with the accepted drain fix. It remains
an audibility-neutral model, not an audible playback pass.

The other V1.101.11 `music.ap` changes at offsets around `0x1150c` and
`0x120e0` are not yet assigned a playback meaning. They remain outside this
probe until their callers and device-facing effects are identified.

## Dinamik probe sınırı

`bash tools/ghidra/run_asrc_mode4_dynamic_probe.sh` executes the real
`FUN_40494e94` instructions from hash-pinned stock and community APs in Ghidra
p-code. The follow-up `bash tools/ghidra/run_asrc_music_tick_probe.sh` starts
at the actual music tick wrapper `FUN_400d4edc`. In that same run it decodes
`0x400d4fda` as `lw v0,0xc4(pc)` and `0x400d4fdc` as `jalrc v0`. The executed
load reads `0x40494e95` from callback literal `0x400d509c`; the following
indirect call enters `FUN_40494e94` once and returns to `0x400d4fdf`. The
probe checks both the actual call operand value and the emulated literal before
and after execution. No AP code or callback literal is rewritten. The
resident snapshot callback at `0xbfc164dc` returns a controlled value of 100,
while resident event/UI/end-notification boundaries are captured stubs.
Playback state, index, threshold, and the remote UI event byte are synthetic
RAM inputs. The tested direct callees have MIPS16 context, every callback
pointer is MIPS16-tagged, and every intercepted return address is checked for
its odd MIPS16 tag. Only those tested paths are covered by this mode-preserving
assumption. The runners create disposable Ghidra projects under a temporary
directory; synthetic RAM blocks are discarded when each run exits.

At the last item (index 2 of 3) above the threshold, stock mode 2 wraps to
index 0 and calls the advance/index-update callback with argument 0. Stock
mode 4 instead leaves the index at 3 and takes the end-notification/UI path.
Community mode 4 wraps to index 0 and calls that same callback with argument
0, matching mode 2. The integrated tick probe confirms the literal-mediated
`lw` → `jalrc` edge enters the real handler in both variants. Stock then emits
the end notification, while community invokes the index/UI callback with
argument 0. Below the
threshold (progress 9 against threshold 10),
community mode 4 makes no advance callback; at equality (10) and above (11) it
takes the advance path. These probes confirm the mode-4 end-of-list
control-flow change and literal-mediated caller edge in actual AP
instructions. They do not
execute the advance/index-update callback body, establish what mode 4 means at
the decoder, or prove that the ASRC/DAC drains the fade-out samples.

## Callback-to-engine message boundary

The mode-4 index callback was followed through the community `music.ap` and
`mengine.ap` dispatchers. `FUN_405151a0` updates the selected-track state and
ends through `FUN_40394eb4(1)`. That helper computes a state flag from
`0x9fc15418` and calls `FUN_40614f30`; its literal-mediated resident call
uses message ID `0x304` (`FUN_40614f30` at `0x40614f30`, resident target
pointer `0xbfc16409`). In `mengine.ap`, `FUN_60090d64` dispatches `0x304`
through pool slot `0x60091024` to `FUN_60110ddc` (`0x60110ddd` MIPS16-tagged
pointer).

The `0x304` handler reads a byte through message `param+4`. The raw word at
`mengine.ap` address `0x60110e94` is the pointer literal `0x9fc15c88`, not the
state object's address. Therefore the effective RAM byte addresses are
`0x9fc15cb3` (`+0x2b`, assigned `input & 0x30`), `0x9fc15cb4` (`+0x2c`,
assigned `input & 0x0f`), and `0x9fc15cb6` (`+0x2e`, assigned `input &
0xc0`). The old value of `0x9fc15cb4` is read before the stores; if the
incoming low nibble is 3 and the old value was not 3, the handler calls an
additional transition helper. It then acknowledges via another indirect
helper. The same handler decompiles identically at the same address in stock
V1.101.10 `mengine.ap` (SHA-256
`1340bac3cb68043f7a9651ee7959c2f502e6759c7debe0626f07ef9231896d4d`); its
pointer pool also contains `0x9fc15c88` at `0x60110e94` and the same resident
call targets. The field meanings and downstream readers remain unknown. The
decompiled handler does not call the `0x311` PLAY dispatcher. This is static
Ghidra evidence; message payload and resident service effects were not
executed in this trace.

Reproduction: independently map the hash-pinned community `music.ap` and
`mengine.ap` with `tools/ghidra/LoadAP.java`. Decompile `0x405151a0`,
`0x40394eb4`, and `0x40614f30` from `music.ap`, and `0x60090d64` and
`0x60110ddc` from `mengine.ap` using `DumpAt.java`. Inspect `mengine.ap` words
at `0x60091010..0x6009106c` and `0x60110e94..0x60110ea8` with `DumpWords.java`
to verify the message dispatch and the RAM base pointer. Repeat the handler
decompile and `0x60110e94..0x60110ea8` word dump against the stock
`mengine.ap` hash recorded above to reproduce the cross-version comparison.

### Independent `0x304` producer in `setting.ap`

`setting.ap` contains a second producer. At `FUN_40154c88`, the incoming byte
is stored at local `s1+0x18`; the function constructs a message whose first
word is `0x304` and whose next word points to that byte, then calls its
literal-mediated service with destination `0x0d`. The manager app-name table
maps entry 13 to `mengine` (the ID-equals-index interpretation is the
documented assumption). `FUN_40155200` ORs `0x10` into the current byte before
calling this wrapper; `FUN_40154cd4` replaces the low nibble while preserving
the high nibble. This independently confirms that `0x304` carries a packed
one-byte state update into the engine. It still does not identify the
user-facing setting or the three fields' semantic names.

The key instruction evidence is `0x40154c8c..0x40154c9e` (copy input byte,
form the payload pointer, store message ID) and `0x40154caa..0x40154cb4`
(destination `0x0d`, payload pointer, indirect service call). Reproduce with
`LoadAP.java` and `DumpInstructions.java` on the hash-pinned community
`setting.ap`, starting at `0x40154c88`; decompile `0x40154c88`,
`0x40154cd4`, and `0x40155200` with `DumpAt.java`.
