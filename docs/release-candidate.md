# M30 flash candidate


> **Düzeltme (statik analiz, cihazda test edilmedi):** Bu belgedeki "önceki tuş
> eşiği 5.000 ms → 0 ms" değişikliği `mengine.ap` içinde `0x3a64`'teki hızlı
> geri sarma başlangıç ofsetini (−5000 ms) değiştiriyor; motorda Previous için
> bir süre eşiği yok. Bu yama Previous'u "parçayı başa sar" yapmayabilir.
> Ayrıntı: [`codex-handoff.md`](codex-handoff.md) ve
> [`findings-artwork-start.md`](findings-artwork-start.md).

## Candidate

`build/MECHEN_M30-community-v1.292-red-ui-safe.HEX`

SHA-256:

```text
59959053aac9ed8d58d4ac39129bd988bc92ca1b64d4dddcaf8b28bb32be091d
```

This image is based on community V1.292.00:

```text
5e17d883f697a67d4face6f624ddc30952c5542c918b219be974bf380383ed2c
```

The candidate is based on community V1.292.00. It keeps the community's
accepted metadata, CUE, M3U, long-list, ASRC, artwork, and manual-index
changes. Our additions are limited to `music.sty` and `setting.sty`;
`mengine.ap` and `common.sty` are byte-identical to the community baseline.
See
[`community-integration.md`](community-integration.md) for the complete
change map and remaining work.

## Verification

For an extracted candidate, verify the member-level delta before repacking or
staging it:

```sh
PYTHONPATH=tools/emu python3 tools/emu/candidate_delta_probe.py \
  analysis/community/fw analysis/candidate/fw \
  --changed music.sty --changed setting.sty
```

The probe fails if a member is added, removed, changed unexpectedly, or if a
changed member has a different size. Use `--allow-size-change` only when the
candidate design explicitly requires a size change and its container offsets
have separate verification.

The two safe resource patch scripts also have fixture-free regression tests:

```sh
python3 -m unittest tools/emu/test_candidate_patches.py
```

Those tests cover the fixed-width UTF-16 prompt replacement and the declared
transport-icon resource boundaries. They do not replace the member-level
comparison against the actual extracted candidate.

- FWU trailer checksum: passed.
- Resource size: unchanged.
- Repacked FWU trailer checksum: passed.
- Decrypted member comparison: exactly `music.sty` and `setting.sty` differ
  from community V1.292.00.
- `mengine.ap` is byte-identical to the community baseline; the unsafe
  Previous experiment is not included.
- No 24,000-track library patch included.
- Stock rollback source: `MECHEN_M30.HEX`, SHA-256
  `6c7e27c8c90c4942664d66a0d6c9f9e48f8d3bc7d2d24223568255e233551258`.

## Not claimed by this candidate

The following remain separate research items and are not silently presented as
working features: the persistent play counter, additional EQ coefficient
presets, asynchronous artwork decode, true Previous-as-restart behavior, and
filename-based browser ordering. Automatic indexing also needs a fresh
physical test on this combined image, especially for powered card insertion.

The candidate changes only the default artwork, the four transport-icon
colours, and the upgrade prompt. It does not change the browser's text
rectangle or marquee logic, so long-folder-name clipping and its red rectangle
still need a physical check before they can be called fixed.

Folder-list next/previous acceleration is also not included in this image. The
separate research candidate in `tools/scroll/accel.c` has a host model and a
historical 30,000-event QEMU harness result, but its fastest 100-item gear has
not been physically tested on this device.

## Install naming

Copy the candidate to a separate staging folder, rename only that copy to
`MECHEN_M30.HEX`, and ensure it is the only `.HEX` update image at the card
root. Keep the stock rollback file off the card until rollback is needed.
