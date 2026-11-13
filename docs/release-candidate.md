# M30 flash candidate

## Candidate

`build/MECHEN_M30-community-v1.292-red-back.HEX`

SHA-256:

```text
f78bdf3bb9c2b29f3a9162150cf028aeef3d3f693a9230dc0fc7ee13d90b736c
```

This image is based on community V1.292.00:

```text
5e17d883f697a67d4face6f624ddc30952c5542c918b219be974bf380383ed2c
```

The candidate is based on community V1.292.00. It keeps the community's
accepted metadata, CUE, M3U, long-list, ASRC, artwork, and manual-index
changes. Our additions are limited to `mengine.ap`, `music.sty`, and
`setting.sty`; `common.sty` is unchanged. See
[`community-integration.md`](community-integration.md) for the complete
change map and remaining work.

## Verification

- FWU trailer checksum: passed.
- Resource size: unchanged.
- Repacked FWU trailer checksum: passed.
- Decrypted member comparison: exactly `mengine.ap`, `music.sty`, and
  `setting.sty` differ from community V1.292.00.
- No 24,000-track library patch included.
- Stock rollback source: `MECHEN_M30.HEX`, SHA-256
  `6c7e27c8c90c4942664d66a0d6c9f9e48f8d3bc7d2d24223568255e233551258`.

## Not claimed by this candidate

The following remain separate research items and are not silently presented as
working features: the persistent play counter, additional EQ coefficient
presets, asynchronous artwork decode, true gapless playback, and filename-based
browser ordering. Automatic indexing also needs a fresh physical test on this
combined image, especially for powered card insertion.

The clean-icon change is expected to remove the red rectangle around folder
icons. It does not change the browser's text rectangle or marquee logic, so
long-folder-name clipping still needs a physical check before it can be
called fixed. Song-title scrolling is a useful control observation, not proof
that folder-title scrolling uses the same layout path.

## Install naming

Copy the candidate to a separate staging folder, rename only that copy to
`MECHEN_M30.HEX`, and ensure it is the only `.HEX` update image at the card
root. Keep the stock rollback file off the card until rollback is needed.
