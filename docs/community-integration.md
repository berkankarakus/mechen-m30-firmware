# Community integration and next steps

This note records the community fixes incorporated into the current M30
candidate and the work that remains. It is intentionally separate from the
older experimental 24,000-song library work.


> **Düzeltme (statik analiz, cihazda test edilmedi):** Bu belgedeki "önceki tuş
> eşiği 5.000 ms → 0 ms" değişikliği `mengine.ap` içinde `0x3a64`'teki hızlı
> geri sarma başlangıç ofsetini (−5000 ms) değiştiriyor; motorda Previous için
> bir süre eşiği yok. Bu yama Previous'u "parçayı başa sar" yapmayabilir.
> Ayrıntı: [`codex-handoff.md`](codex-handoff.md) ve
> [`findings-artwork-start.md`](findings-artwork-start.md).

## Firmware inputs

| Input | SHA-256 | Role |
|---|---|---|
| Official MECHEN 2025-06-26 / V1.101.10 | `6c7e27c8c90c4942664d66a0d6c9f9e48f8d3bc7d2d24223568255e233551258` | Rollback source |
| Community V1.292.00 | `5e17d883f697a67d4face6f624ddc30952c5542c918b219be974bf380383ed2c` | Accepted community baseline |
| Historical combined candidate | `f78bdf3bb9c2b29f3a9162150cf028aeef3d3f693a9230dc0fc7ee13d90b736c` | Community baseline plus unsafe Previous experiment |
| Current safe UI candidate | `59959053aac9ed8d58d4ac39129bd988bc92ca1b64d4dddcaf8b28bb32be091d` | Community baseline plus artwork/icon/prompt resources |

The community release is based on the same official V1.101.10 payload. Its
release notes describe hardware acceptance on a Mechen M30, but the testing
scope is limited to the tested device and cases described by that project.

### Automatic-indexing claim scope

The community V1.292 members `config.ap` and `udisk.ap` both contain the same
one-byte change as the manual-index guard used in this repository:
`0x22 -> 0x10` at offsets `0x1e0d` and `0x1909`, respectively. This is strong
evidence that the community image includes an automatic file-list bypass, but
it is not proof that every trigger path is disabled. In particular, the
powered card-insertion and cold-boot paths still require a device test.
The stock-versus-community control-flow comparison is reproducible in
[`findings-index-guards.md`](findings-index-guards.md).

The locally tested `build/MECHEN_M30-index-off-space-preview.HEX` must not be
used as evidence against the community baseline: it was built from the stock
payload with the two guard bytes and an upgrade-prompt resource change, and
did not include the community V1.292 members. Therefore the observation that
this image indexed after card insertion does not establish that V1.292 behaves
the same way.

## Community fixes included

The historical combined candidate took the community payload wholesale, so the
following are included:

- The community's documented/manual-index change targets automatic file-list
  regeneration after USB use, card changes, firmware updates, and the
  dirty-settings path. Manual `Settings -> Update Playlist` remains available;
  the exact coverage of every trigger is still a physical-test item here.
- End-of-track ASRC drain, which is the community fix most relevant to the
  Audacity fade-out clipping report.
- Bounded metadata and artwork parsing with UTF-8/UTF-16 and ID3 fixes.
- CUE Repeat Folder and final-CUE-track backward-seek fixes.
- CRLF, LF, and unterminated-final-entry support for M3U files.
- Decimal track-number fallback and unsigned track ordering.
- Cached long-list navigation.
- Decoder callback safety and ASRC coefficient-loader safety.
- The community's bounded FLAC metadata-block scan for large PICTURE blocks.
- The community's bounded baseline-JPEG artwork fallback.

The accepted community release restores the stock fixed-array 4,000-track
library architecture. The experimental 24,000-track builder is deliberately
not included.

## Our changes layered on top

The historical candidate differed from the community baseline in three
FWIMAGE members:

- `mengine.ap`: an unsafe experiment changed the fast-backward start offset
  at `0x3a64`; it does **not** implement Previous-as-restart and must not be
  carried into the next release candidate.
- `music.sty`: the missing-artwork bitmap remains our red waveform, and only
  transport resources 7, 8, 29, and 30 are recolored to its main red. Their
  pale/white source pixels are mapped to darker red antialiasing tones.
- `setting.sty`: the four padded English upgrade prompts read
  `Confirm upgrade file: [%s]`, with the original UTF-16 terminators intact.

`common.sty` is unchanged. No folder, file, or note icon was changed.

## Verification completed

- Community image decrypted using the official stock plaintext and its
  encrypted-sector key schedule.
- The combined candidate repacked successfully at the original size.
- FWU trailer checksum: passed.
- A second decryption comparison found exactly three changed members:
  `mengine.ap`, `music.sty`, and `setting.sty`.
- All other community members, including `playlist.ap`, `config.ap`,
  `mainmenu.ap`, `udisk.ap`, and `browser.ap`, remain byte-identical to the
  V1.292.00 baseline.
- The historical candidate has not been flashed or physically tested and is
  not a release recommendation because of the unsafe `mengine.ap` experiment.
- The current safe UI candidate keeps `mengine.ap` byte-identical to the
  community baseline. It changes only `music.sty` and `setting.sty`; its FWU
  trailer checksum and member-level diff were verified offline. It has not
  been physically tested.

## Remaining work

### First priority: device checks

1. Flash the combined candidate with the stock HEX kept offline for rollback.
2. Check boot, playback, next/previous, volume, and screen-off controls.
3. Confirm Previous always restarts the current song.
4. Test the four red transport icons against the red default artwork.
5. Cold-boot and manual-update tests remain. On 2026-11-15, the untouched
   community V1.292.00 image was successfully flashed, but removing and
   reinserting the card while powered still started indexing. The card-event
   trigger is therefore not covered by the two known guard sites, or it uses a
   separate builder-start path; see [`findings-index-guards.md`](findings-index-guards.md).
6. Test an Audacity fade-out and a CUE/M3U sample set.

### Play counter

The counter is not in the current candidate. The intended design is a small
`M30PLAY.CNT` sidecar on the card, keyed by disk, directory cluster, and
directory entry, with an increment at successful play start. It does not need
an on-device UI. Before adding it, the write path needs atomic record updates,
card-removal handling, file creation/recovery, and a bounded record limit.

### Later UI and playback work

- Improve folder-name marquee clipping and redrawing after the physical test.
- Add more EQ presets using the existing sample-rate path only.
- Revisit filename-based sorting after the community ordering fixes are
  tested against the user's card.
- Keep true gapless playback and high-rate codec support deferred.
- Keep the 24,000-track library and configurable locked-controls patches out
  until their hardware regressions are resolved.

## Sources

- Community firmware README:
  https://github.com/dev-zetta/mechen-m30-community-firmware
- Community changelog:
  https://github.com/dev-zetta/mechen-m30-community-firmware/blob/main/CHANGELOG.md
- Earlier research firmware:
  https://github.com/averagenative/mechen-m30-firmware
