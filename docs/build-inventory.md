# Local HEX inventory

The files below were decrypted offline and compared member-by-member against
stock V1.101.10 and community V1.292.00. None of these results is a device
test. SHA-256 values are truncated here for identification; use the full hash
from `sha256sum` before flashing anything.

| File | Hash prefix | Members changed from stock | Conclusion |
|---|---:|---|---|
| `build/MECHEN_M30-community-v1.292-red-ui-safe.HEX` | `59959053aac9` | `music.sty`, `setting.sty`, plus community AP fixes | Current offline-verified candidate; not physically tested |
| `/tmp/MECHEN_M30-community-v1.292-now-playing-ui.HEX` | `de1e2cdd9a08` | `music.sty` only: default artwork and four transport icons | Now-playing-only candidate; offline unpack/checksum verified, not physically tested |
| `/tmp/m30-next-ui/MECHEN_M30-community-v1.292-now-playing-layout.HEX` | `a43496b9cc5b` | `music.sty` only: previous now-playing resources plus M30 `0x2005` textbox layout | Experimental right-panel layout; AFI/member/FWU checksums verified, not physically tested |
| `/tmp/m30-next-ui/MECHEN_M30-community-v1.292-now-playing-callpath.HEX` | `95828e0d19de` | `music.ap` one-byte paint-path redirect (`0x2005` → `0x2001`) plus previous now-playing resources | Superseded: wrong/non-visible call path; AFI/member/FWU checksums verified |
| `/tmp/m30-next-ui/MECHEN_M30-community-v1.292-now-playing-scroll.HEX` | `ec3e13189b7` | `music.ap` one-byte shared scroll-renderer redirect at `0x40d55078` (`0x2005` → `0x2001`) plus previous now-playing resources | Corrected visible-marquee candidate; AFI/member/FWU checksums verified, not physically tested |
| `build/MECHEN_M30-community-v1.292-now-playing-scroll.HEX` | `ec3e13189b7` | Same corrected shared scroll-renderer candidate, regenerated from V1.292.00 | Persistent copy; Rockbox FWU/AFI/FWIMAGE checks passed, not physically tested |
| `/tmp/m30-name64.4Eiu04/MECHEN_M30-name64-experiment.HEX` | `9322444d2ae4` | `browser.ap`, `music.ap`: four `50 -> 64` literals each | Static experiment only; overwrites the adjacent `path_info` area and must not be flashed |
| `build/MECHEN_M30-index-off-space-preview.HEX` | `d606f70bdfff` | `config.ap`, `setting.sty`, `udisk.ap` | Index experiment plus prompt; not community baseline |
| `build/MECHEN_M30-red-matched-ui.HEX` | `cf7c76aa01ed` | `common.sty`, `music.sty`, `setting.sty` | UI/resources only; no community playback/index fixes |
| `build/MECHEN_M30-red-ui-index-off-preview.HEX` | `3a68246ed32d` | `config.ap`, `music.sty`, `setting.sty`, `udisk.ap` | Index experiment plus UI; no community baseline |
| `build/MECHEN_M30-red-ui-v2-preview.HEX` | `5649861df4e5` | `music.sty`, `setting.sty` | UI/resources only |
| `build/MECHEN_M30-v5.HEX` | `af999b7bf15e` | `browser.ap`, `mainmenu.ap`, `mengine.ap`, `music.ap`, `playlist.ap`, `setting.ap` | Earlier custom patch set; not community V1.292.00 |

The historical `red-back` candidate is not present in `build/`; its recorded
hash is `f78bdf3b...`. It included the community payload but also the unsafe
Previous patch and is explicitly not a release candidate until regenerated.

## Consequence

The current candidate is generated from the community payload, omits the
unsafe Previous patch, and applies only the explicitly selected UI resources.
Any later candidate must preserve the same member-level verification before a
device test.
