# `mmm_bp.al` decoder context initialization boundary

## Result

The recovered module has a concrete internal entry/initializer chain, but the
available stock and community images do not identify an external caller that
writes the decoder's indirect status pointer. The strongest candidate is an
initialization call that supplies a memory range containing the slot to an
unresolved resident service. Its effect is not proven, so it cannot yet be
called a status-pointer writer.

## Static call/dispatch evidence

The stock and community `fw/mmm_bp.al` members are byte-identical
(SHA-256 `ab5d98b578406c4e04fb7b546317fbec0d36ce4a7c139ef0922b06bb4b753c5b`).
The AP-style header entry at file offset `0x40` is odd MIPS16 pointer
`0xbfc218a9`, aligned entry `FUN_bfc218a8`. In that entry, the operation
dispatcher pointer at `0xbfc21918` is `0x680a1ed5`, aligned
`FUN_680a1ed4`. The dispatcher's operation-0 case makes a computed call through
`0x680a200c`, whose literal is `0x68061c01`, aligned `FUN_68061c00`.
Ghidra's reference report records the computed-call edge from `0x680a1fd6` to
`0x68061c00`.

`FUN_68061c00` uses fixed RAM address `0x9fc21b08` as its context block. Before
its explicit field assignments, it calls the unresolved stub pointer
`0xbfc21a39` with `(a0=0x9fc21b08, a1=0, a2=0xec, a3=1)`. The decoder worker
`FUN_bfc216a8` reads the status pointer from absolute address `0x9fc21bd0`
(`0x9fc21b00 + 0xd0`). That slot is within the range supplied by the earlier
call: it is `0xc8` bytes from `0x9fc21b08`, inside the `0xec`-byte extent.

This is direct evidence for the call tuple and range overlap. Treating the
service call as a zero-fill is an inference from `(buffer, 0, length, mode)`;
the service body is unavailable, so neither zeroing nor ownership of the
status slot is established. Later in `FUN_68061c00`, a registration record
containing the context pointer is passed through the same resident trap path
with operation values `0x33` and `0x4a`. Those operations' meanings and any
side effects on `0x9fc21bd0` remain unresolved.

The whole recovered set (`DumpC: functions=38`) contains two explicit reads
through context `+0xd0`, both in `FUN_bfc216a8`, and no explicit store through
that expression. Ghidra references to absolute `0x9fc21bd0` likewise show the
two reads and no write. This does not rule out a write through a computed
alias or an unresolved service.

## Stock/community caller and loader search

I scanned every file recursively under both `analysis/stock` and
`analysis/community`, deduplicating identical file hashes within each corpus,
for little-endian references to the entry pointer `0xbfc218a9`, the worker
pointer `0xbfc216a9`, context addresses `0x9fc21b00`, `0x9fc21b08`, and status
slot `0x9fc21bd0`, plus the initializer `0x68061c00/0x68061c01`. The entry,
context, and initializer references outside `fw/mmm_bp.al` occur only in the
container copies `afi/FWIMAGE.FW` and `dec.bin`; their offsets correspond to
embedded `mmm_bp.al` content, not separate callers. The firmware package
directory labels the member `MMM_BP  AL`, but that packaging record does not
show who loads it or what arguments the runtime loader supplies.

The corpus container hashes differ (stock `afi/FWIMAGE.FW`:
`edb04f1119f2caa4710dbfad67e3c79eee8fb0a7446c66224768f0cf9dbfd7dc`; community:
`c87035fa32bd83a2c2d36f5564ff4ab049d3f8cdc3ec9a2a75a8eb7a4cb7d745`), while
the `mmm_bp.al` hash is identical. This was a direct-literal scan, not a full
disassembly of every loader or a proof against computed addresses and runtime
registration.

## Reproduction and next probe

The existing static member probe passes against the mounted stock and
community members:

```sh
bash tools/ghidra/run_mmm_bp_fade_probe.sh /Users/berkankarakus/Projects/mechen-m30-firmware/analysis/stock/fw/mmm_bp.al
bash tools/ghidra/run_mmm_bp_fade_probe.sh /Users/berkankarakus/Projects/mechen-m30-firmware/analysis/community/fw/mmm_bp.al
```

The dispatch edge and literals can be rechecked with `LoadAP.java`,
`DumpAt.java`, `DumpWords.java`, and `DumpRefsTo.java` in `tools/ghidra`; the
observed reference is a Ghidra static computed-call reference, not dynamic
execution. No device, firmware, or SD data was written.

Next, trace the audio/runtime loader that selects the `MMM_BP  AL` package
member and invokes its header entry, then follow the context pointer and the
`0xbfc21a39`/operation-`0x4a` side of initialization. That is the shortest
route to distinguish a loader-provided status pointer from a resident-service
write. Keep that investigation separate from the `0xbfc164dc` ABI work.
