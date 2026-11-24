# `aud_dev.drv` bank-5 `id=1` group decompile

Read-only Ghidra decompile of candidate bank-5 code:

- Input: community `aud_dev.drv`, SHA-256
  `3349287198faaa90a503353673674d5628e85711db9ee16217db5a803484f09c`
- Candidate mapping: file offset `0x1f00` to VA `0x9400`, size `0x600`
- Routine: `FUN_00009400`, MIPS16
- Decompile: [`auddev-id1-decompile.c`](auddev-id1-decompile.c), SHA-256
  `b156242cf51108370e6d24c4182596bf991bbc43b631542b0f09e109e76f240d`
- Reproduction: `bash tools/ghidra/run_auddev_bank_probe.sh <hash-matching-aud_dev.drv>`

The runner hash-pins the input and verifies that the mapped instructions match
the bytes at file offset `0x1f00`. The decompile directly shows conditional
`id=1` groups: flags at `dae_cfg+7`, `+8`, `+9`, `+0xa`, `+0xb`, `+3`, and
`+0xd` are tested for equality to one. The `+3` group consumes three records
starting at `+0x9e` and writes constants 50 and 500. This corrects the prior
reported flag `+0xc`; `+0xc` is not the gate in this routine.

It also shows a final rate guard comparing the stored state rate against
`0xbb81` (48001); on the higher-rate branch it clears consumer-state fields
at byte offsets `+0x40`, `+0x3a`, and `+0x28`. This proves the branch and writes in the
candidate code, not the higher-level semantics of each state field.

The code window is a candidate bank mapping supported by static correlations
and checked against the file bytes. The absent fixed-ROM dispatcher and device
bank-loader mean that table-index-to-operation assignment and runtime entry
remain unproven. No p-code, device, or audible-output test was performed.
