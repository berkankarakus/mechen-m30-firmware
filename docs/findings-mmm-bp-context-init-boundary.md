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
containing the context pointer is passed through the separate stub pointer at
`0x68061d20` (literal `0xbfc21a3d`) with operation values `0x33` and `0x4a`.
These are not calls via the `0xbfc21a39` pointer discussed here. Their meanings
and any side effects on `0x9fc21bd0` remain unresolved.

The recovered functions contain two explicit reads through context `+0xd0`,
both in `FUN_bfc216a8`, and no explicit store through that expression. Ghidra
references to absolute `0x9fc21bd0` likewise show the two reads and no write.
The total function count reported by `DumpC` can vary with function discovery,
so it is not used as a completeness criterion. This does not rule out a write
through a computed alias or an unresolved service.

## Static call shapes through `0xbfc21a39`

A fresh Ghidra pointer-literal scan of the byte-identical member found exactly
nine slots containing `0xbfc21a39`; Ghidra reports 22 computed-call
references to the aligned stub address `0xbfc21a38` across these nine callers.
The recovered call shapes below show arguments as `(a0,a1,a2,a3)`; repeated
calls in loops and branches are grouped:

| Literal slot | Caller | Recovered call shapes |
| --- | --- | --- |
| `0x68021c7c` | `FUN_68021c00` | `(param+0x92,0,2,1)`; `(param+0x94,0,0x20,1)` |
| `0x68061d18` | `FUN_68061c00` | `(0x9fc21b08,0,0xec,1)`; `(ctx+0x40,0,0,0x17)`; `(ctx+0x44,0,0,0x12)` |
| `0x68061d8c` | `FUN_68061d2c` | `(*(param+0x40),0,0,0x1a)`; same first three arguments with `a3=0x19`; `(param+0x40,0,0,0x18)`; `(param+0x44,0,0,0x13)` |
| `0x680a201c` | `FUN_680a1ed4` | `(param+3,param3,4,0)` in dispatch case `0xb` |
| `0xbfc21464` | `FUN_bfc21430` | `(global+0x4c,0,0,0x16)` |
| `0xbfc21914` | `FUN_bfc218a8` | `(*(param+0x40),0,0,0x19)`; `(param3,param+0x1c,0xc,0)`; cleanup call `(*(param+0x40),0,0,0x1a)` |
| `0xbfc21a18` | `FUN_bfc21964` | `(param[0x11],0,0,0x14)` |
| `0xbfc2751c` | `FUN_bfc274c8` | `(dst,source,chunk_length,0)`; possible wrap remainder `(dst+first_length,base,remainder,0)` |
| `0xbfc277d8` | `FUN_bfc27734` | `(param[0x10],0,0,0x19)`; same with `a3=0x1a`; `(0,0,0,0xc)` |

The zero-initialization hypothesis is materially better supported, but remains
unconfirmed: three calls in two callers use `(destination,0,length,1)`, for
lengths `2`, `0x20`, and `0xec`; the `0xec` extent covers the context `+0xd0`
slot at offset `0xc8` from its supplied base. The explicit caller field stores
in `FUN_68021c00` are consistent with those short-range calls initializing
record fields. However, the same literal is also called with nonzero source
arguments and `a3=0`, and with `(a1,a2)=(0,0)` and `a3` values `0x12`,
`0x13`, `0x14`, and `0x16` through `0x1a`. That variation is evidence for an
overloaded resident service or operation-selector interface, not proof that
`a3=1` means zero-fill. With the resident body absent, the strongest bounded
statement is that the `0xec` call passes a range containing `+0xd0` to a
service whose other callers include zero-fill-shaped calls; the service's
effect on that slot is still unknown.

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
`DumpAt.java`, `DumpWords.java`, `FindPointerRefs.java`, and `DumpRefsTo.java` in
`tools/ghidra`; the observed references are Ghidra static computed-call
references, not dynamic execution. No device, firmware, or SD data was
written.

Next, trace the audio/runtime loader that selects the `MMM_BP  AL` package
member and invokes its header entry, then identify the resident implementation
or ABI contract behind stub `0xbfc21a38`. That is the shortest route to
distinguish a loader-provided status pointer from a resident-service write.
Keep that investigation separate from the `0xbfc164dc` ABI work.
