# M30 safe UI candidate recipe

There is currently no persistent flashable candidate in this worktree. The
reproducible candidate boundary is the extracted community member tree plus
the two verified resource changes below.

> **Correction (static analysis; not device tested):** The Previous-as-restart
> patch is excluded. The `0x3a64` value is a fast-backward offset, and the
> Previous handler has no elapsed-time threshold. Changing it does not establish
> restart behavior. See [`codex-handoff.md`](codex-handoff.md)
> and [`findings-artwork-start.md`](findings-artwork-start.md#3-previous-key).

## Source and scope

- Source: community V1.292.00, SHA-256
  `5e17d883f697a67d4face6f624ddc30952c5542c918b219be974bf380383ed2c`.
- Changed members: `music.sty` and `setting.sty` only.
- `mengine.ap` and `common.sty` remain byte-identical to the community
  baseline; the unsafe Previous experiment is excluded.
- No 24,000-track experimental library patch is included.
- Physical device acceptance has not been claimed for this candidate.

## Reproduce the extracted candidate

```sh
PYTHONPATH=tools/emu python3 tools/emu/build_safe_ui_members.py \
  analysis/community/fw /private/tmp/m30-safe-ui/fw
```

Then verify the exact delta:

```sh
PYTHONPATH=tools/emu python3 tools/emu/candidate_delta_probe.py \
  analysis/community/fw /private/tmp/m30-safe-ui/fw \
  --changed music.sty --changed setting.sty \
  --manifest /private/tmp/m30-safe-ui/delta.json
```

The optional JSON manifest records every extracted member's baseline/candidate
SHA-256 and size, names the rollback/reference tree, and explicitly marks the
result as `flashable_hex: false`. It is a comparison artifact, not a firmware
image.

The builder emits a PPM preview outside the member directory. It does not
repack a HEX. A repack step may be documented only after the source HEX,
decrypted AFI, container offsets, checksums, and full round-trip extraction
are all available and tested.

## Now-playing-only member candidate

For the narrower now-playing resource boundary, use:

```sh
PYTHONPATH=tools/emu python3 tools/emu/build_now_playing_member.py \
  analysis/community/fw /private/tmp/m30-now-playing-member/fw
```

This candidate changes exactly one extracted member: `music.sty`. It contains
only the verified default-artwork and transport-icon resource edits. The host
metadata rasterizer, EQ spacing, status silhouettes, and footer preview are
not firmware patches and are intentionally excluded. The output is therefore
safe to inspect and compare, but it is still not a flashable HEX until the
complete FWU source and round-trip repacker are available.

## Not claimed

This recipe does not fix folder-name clipping, the red marquee artefact,
filename ordering, persistent play counters, asynchronous artwork decoding,
true Previous-as-restart behavior, or physical card-event indexing.
