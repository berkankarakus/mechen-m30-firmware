# M30 firmware flash preflight

This checklist is for the MECHEN M30 running the verified stock release
`V1.101.10` / `MECHEN_M30.HEX` dated 2025-06-26.

## Files

Keep both files on the computer before touching the player:

| Purpose | File | SHA-256 |
| --- | --- | --- |
| Stock rollback source | `MECHEN_M30.HEX` | `6c7e27c8c90c4942664d66a0d6c9f9e48f8d3bc7d2d24223568255e233551258` |
| Current candidate — not physically tested | `build/MECHEN_M30-community-v1.292-red-ui-safe.HEX` | `59959053aac9ed8d58d4ac39129bd988bc92ca1b64d4dddcaf8b28bb32be091d` |
| Historical candidate — do not flash | `build/MECHEN_M30-community-v1.292-red-back.HEX` | `f78bdf3bb9c2b29f3a9162150cf028aeef3d3f693a9230dc0fc7ee13d90b736c` |
| Previous custom candidate | `build/MECHEN_M30-minimal-safe.HEX` | `12ad027900f433b281aa5c181d0cbfb845603eb4d38bb2ae8718c811f1fcd12f` |
| Experimental UI-only candidate | `build/MECHEN_M30-ui-blue-clean-icons.HEX` | `01467cca80ea5b991fee7288394755ae1581c578ff67f2495a645202522564ba` |

The current candidate is community V1.292.00 with only the documented default
artwork, transport-icon colour, and upgrade-prompt resource changes layered on
top. `mengine.ap` is unchanged from community V1.292.00, so the unsafe
Previous experiment is absent. It passed offline member and FWU checksum
verification but has not been physically tested.

The historical `red-back` candidate contains the unsafe Previous experiment;
do not flash it.

The UI-only candidate is not a recommended release. It replaces only the
verified 310x29 selection-highlight bitmap in `common.sty`; it is intended
for a later visual test after the baseline behavior is fully documented.

The folder-name `50 -> 64` experiment is not a release candidate. It is kept
under `/tmp/m30-name64.4Eiu04/` for static analysis only: the expanded eight
slot area reaches into the adjacent `path_info` structure. Do not rename or
flash that file.

Rename only a copy of the candidate to exactly `MECHEN_M30.HEX` when it is
ready to be placed on the player. There must be only one file with that name
in the device root.

## Before flashing

- Confirm the player still reports `V1.101.10`.
- Charge the player fully and use a stable USB cable/connection.
- Keep the original stock file and this candidate outside the player.
- Remove any older `MECHEN_M30.HEX` from the device root.
- Do not disconnect power or USB during the update.
- Do not proceed if the player is freezing, repeatedly rebooting, or showing a
  different firmware version.

## Official update path

The M30 manual instructs copying the HEX file to the device root, then using
`Settings -> Auto upgrade -> Yes`; the player should power off when the update
finishes. See the [firmware update instructions](https://manuals.plus/ae/1005006075793786#firmware-update).

## First boot checks

Do not rebuild the library immediately. Verify, in this order:

1. Power on and confirm the main menu opens.
2. Play one short MP3 and check play/pause, next/previous, and volume.
3. Turn the screen off and repeat next/previous and volume changes.
4. Check the headphone output at a low volume first.
5. Confirm the SD card contents are visible.
6. Only then test `Settings -> Update Playlist` manually.

If any check fails, stop using the modified firmware and preserve the exact
screen state/error message before attempting a rollback.

## Scope caveat

QEMU validates the shuffle, play-all, and scroll patches, plus a separate
regression harness for the key-filter code. The current candidate itself has
not been physically tested, so the first boot checks above are required.
