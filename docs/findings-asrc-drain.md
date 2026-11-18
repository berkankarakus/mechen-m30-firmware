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

The `0x304` handler reads a byte through message `param+4`, writes masked
fields (`& 0x30`, `& 0x0f`, `& 0xc0`) into state at `0x60110e94 +
0x2b/+0x2c/+0x2e`, conditionally calls state-transition helpers, and
acknowledges via another indirect helper. The decompiled handler does not
call the `0x311` PLAY dispatcher. This closes the *message-dispatch edge*
from the mode-4 callback, but not the question of what those state fields
mean or whether another asynchronous consumer later starts playback. This is
static Ghidra evidence; the message payload and resident service effects were
not executed in this trace.

Reproduction: map the hash-pinned community `music.ap` and `mengine.ap` with
`tools/ghidra/LoadAP.java`, then decompile `0x405151a0`, `0x40394eb4`,
`0x40614f30`, `0x60090d64`, and `0x60110ddc` using `DumpAt.java`; inspect
`mengine.ap` words at `0x60091010..0x6009106c` with `DumpWords.java` to verify
the `0x304` dispatch slot.
