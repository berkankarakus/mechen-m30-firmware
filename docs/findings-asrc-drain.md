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
at the actual music tick wrapper `FUN_400d4edc`; in that same run the program
counter enters `FUN_40494e94` once, with the preceding PC and return address
both inside the wrapper. The callback literal at `0x400d509c` contains the
MIPS16-tagged handler address, verified from emulated memory before and after
execution. The trace has not yet established the literal-load dataflow as the
specific source of that call. No AP code or callback literal is rewritten. The
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
0, matching mode 2. The integrated tick probe confirms the wrapper executes
and the handler is entered once in that run, with an in-wrapper predecessor PC
and return address; the literal's value matches the handler but its
load-to-call dataflow is not yet traced. Stock then emits the end notification,
while community invokes the index/UI callback with argument 0. Below the
threshold (progress 9 against threshold 10),
community mode 4 makes no advance callback; at equality (10) and above (11) it
takes the advance path. These probes confirm the mode-4 end-of-list
control-flow change in actual AP instructions and a dynamic wrapper-to-handler
caller relationship. They do not
execute the advance/index-update callback body, establish what mode 4 means at
the decoder, or prove that the ASRC/DAC drains the fade-out samples.
