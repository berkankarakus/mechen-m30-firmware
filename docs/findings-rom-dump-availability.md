# Public Mechen ROM-dump search

## Result

The public-source search found Mechen firmware upgrade packages for several
player models, but no independently verifiable raw ROM/NOR dump from another
Mechen device. The [Mechen firmware-upgrade page](https://mechen.com.cn/firmwareupgrade)
is an update-package source; its presence does not establish that those files
are complete flash readbacks.

The available M30 `MECHEN_M30.HEX` is an Actions FWU v3 update image containing
an AFI container and `FWIMAGE.FW`, as described in the
[M30 firmware repository](https://github.com/averagenative/mechen-m30-firmware).
It is not a raw NOR dump and does not provide the missing fixed-ROM contents.

## What this does and does not establish

- No public, verifiable raw dump for another Mechen model was identified in
  the searched manufacturer, GitHub, and forum sources. This is a bounded
  search result, not proof that no private or unindexed dump exists.
- Another model's update package might contain application or driver code, but
  that does not make it safe or useful as a substitute for M30 fixed ROM.
  Matching Actions-family firmware alone does not establish the same board,
  flash map, ROM ABI, or bank placement.
- Do not fill an M30 unmapped ROM range with code from another model unless
  board/SoC identity, address map, calling convention, and the relevant code
  path are independently matched.

## Highest-value next source

The useful missing artifact is a readback of the same M30 board's ROM/NOR, or
an equivalent image whose board and memory map are independently verified.
Until that exists, fixed-ROM service effects remain outside the executable
model and exception/bank dispatch must remain fail-closed.

## Community and cross-model follow-up (2026-11-18)

The Reddit search found evidence of independent M30 reverse engineering, but
no reusable custom firmware, patch source, or raw ROM dump:

- In [a January 2026 M30 thread on r/DigitalAudioPlayer](https://www.reddit.com/r/DigitalAudioPlayer/comments/1qb8phy/help_mechen_m30_custom_playlists_or_better/),
  one owner says they used Ghidra to change the volume step as a proof of
  concept, then abandoned the work. No patch, modified image, or source is
  linked. This confirms a separate firmware-patching attempt, not a public
  firmware project.
- The same thread's original poster guesses the SoC is ATJ2167 from looking at
  update files. This is not a verified identification and conflicts with the
  ATJ2127 basis used by this repository and its public SDK reference. Do not
  use the ATJ2167 guess to select a ROM, ABI, or Rockbox port.
- The [r/rockbox M30 discussion](https://www.reddit.com/r/rockbox/comments/1c3eet9/mechen_m30_support/)
  reports that Mechen support shared an ATJ2167 datasheet and an X-Power AC10
  document through Drive links; later commenters could no longer retrieve
  them. Participants say the M30 lacks the RAM for Rockbox, but provide no
  measurement or working port. Treat both the datasheet identification and
  RAM conclusion as community claims, not device evidence.
- A [MECHEN D50 hardware-hacking post](https://www.reddit.com/r/hardwarehacking/comments/1dwceca/how_can_i_install_some_form_of_linux_or_a_different_os_on_this_mp3_player/)
  links a model-specific `MECHEN_D50.fw` file. The post describes it as
  firmware obtained for that model; it does not establish a full flash/NOR
  readback. D50's board and SoC are not matched to M30, so the file is not an
  M30 ROM substitute. The linked file was not downloaded for this research.
- Mechen's [current firmware-upgrade page](https://mechen.com.cn/firmwareupgrade)
  lists a 2026-10-22, 29.87 MB update-tool archive for M3/M30/M33/V01/V02/V06
  and a separate D53 SP Flash Tool package. A shared updater archive does not
  prove these models share application firmware, SoC, board, or ROM ABI. No
  files were downloaded.

### Practical conclusion

Reddit adds one credible lead that another owner demonstrated a small Ghidra
patch, but no artifact to compare against ours. The only cross-model firmware
lead is the D50 update package, which is not a raw ROM dump and has no verified
hardware match. The official multi-model updater listing may be useful if a
future local analysis of its contents is authorized, but it is not evidence of
cross-flash compatibility. Current public evidence does not change the
priority: continue with M30's own hash-pinned stock/community images and
fail-closed ROM boundaries.
