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
cross-flash compatibility. The ATJ2127 ADFU lead below is a separate
acquisition route and does not justify substituting another model's ROM.

## ADFU boot-ROM readback candidate (2026-11-20)

A public ATJ2127 tool documents a possible route to the missing on-chip ROM:
[`kilicdev/actions_flash`](https://github.com/kilicdev/actions_flash) and its
[ATJ2127 payload README](https://github.com/ilyakurdyukov/actions_flash/blob/main/payload/README.md).
From an already-entered ADFU session, the documented sequence loads
`adfus.bin` into SRAM at `0xbfc18000` and switches the command handler to it;
then `read_mem2` copies `0x9fc00000..0x9fc3ffff` to a host-side file. The
project says the ordinary Boot-ROM `read_mem` path returns zeros for the ROM
window. It separately documents entering ADFU from mass-storage mode with
`adfu_reboot` (or a boot-key method). This is a candidate method, not an M30
readback or proof that this exact M30 board accepts that payload/address map.
The original ATJ2127 payload README says the payload was tested only on
ATJ2127; the tool's chip-ID output is described as a guess, not board
identification.

The documented `simple_switch`/`read_mem2` sequence writes and executes code
in volatile device memory, then reads memory. The checked local
`actions_dump.c` implementation of `read_mem2` uploads a MIPS16 byte-copy
helper at `0xbfc1e000` and uses its buffer at `0xbfc1e020`; this clarifies the
SRAM activity beyond the top-level command names. That exact sequence contains no
NAND/SD write command, but it is device execution and has not been run here.
The general `actions_dump` utility also implements flash-writing commands, so
the utility itself is not read-only. Its README warns that a hung payload can
leave some devices difficult to reboot. No device interaction, payload
download, or device/SD/NAND write was performed for this finding.

### Kernel-init offsets worth inspecting in a readback

Static disassembly of `ker_init.bin` references `0x9fc12000`,
`0x9fc12014`, `0x9fc12200`, and `0x9fc12204`. Under the candidate
copy-helper ABI, the first two ranges supply 20 and 32 bytes to RAM structures;
the first copied word is then called as a function pointer. These addresses
fall at offsets `0x12000`, `0x12014`, `0x12200`, and `0x12204` in the
documented ADFU readback window. A ROM dump could therefore resolve the
candidate template bytes and callback value. It would not by itself prove
that normal boot maps these addresses to the same ROM bytes; the runtime map
and `0xbfc04635` behavior still need confirmation.

### What this changes

- It gives us a concrete route to try to obtain the fixed-ROM bytes missing
  from the extracted firmware. A successful readback could let us inspect the
  exception/service dispatch path and replace more emulator stubs with code.
- Applicability depends on confirming the M30's ADFU identity and exact
  ATJ2127 memory map. The public project documents ATJ2127 support but does not
  report an M30 test. Treat M30 compatibility as unverified.
- Before any device use, the SoC/address match and the exact host command path
  need review. The intended command sequence must be constrained to SRAM upload,
  execution, and ROM read; the general utility can issue flash writes. Device
  execution still requires explicit authorization; this finding is not
  authorization to run it.
