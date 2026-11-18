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
