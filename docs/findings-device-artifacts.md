# M30 device-independent artifact research

This note records the web research that can be used to decide whether a new
device artifact is strong enough to extend the host emulator. It does not add
firmware, ROM, vendor payload, or downloaded archive contents to the
repository.

## Sources checked on 2026-11-16

- [MECHEN firmware update page](https://mechen.com.cn/firmwareupgrade): the
  current page lists an update package for M3, M30, M33, V01, V02, and V06,
  but its presentation does not provide a stable M30 version-to-SHA-256
  mapping that can be used as binary evidence.
- [MECHEN M30 manual](https://ae01.alicdn.com/kf/S0d75602fca7a458fbef00b7e4ca728355.pdf):
  documents a 320x240 LCD, a 4,000-track Music view limit, JPEG artwork up to
  640x640, AAC mono playback, and no gapless playback. It also documents the
  `MECHEN_M30.HEX` auto-upgrade workflow and the requirement that exactly one
  file with that name be present.
- [Secondary M30 firmware history](https://www.desertcart.com.au/products/453170286-mechen-m30-hifi-mp3-player-64gb-dac-decoding-dsd-gray):
  reports dated firmware behavior changes, including sorting and lock-screen
  controls. These reports are useful hypotheses only; they are not accepted
  as binary proof without a matching local corpus.
- [MECHEN product information](https://themechen.com/): identifies the M30
  as using a WM8965 DAC with a Texas Instruments amplifier.
- [M30 manual copy with component claims](https://manuals.plus/ae/3256806653844578)
  and [another M30 manual copy](https://manuals.plus/ae/1005006840066890):
  repeat WM8965/TPA6530 in one place, while another listing adds AK4376 and
  JuLi2167. These are mutually inconsistent secondary claims, not a board
  photo or schematic.

## What these sources change

- The 320x240 display and 4,000-track boundary already have corresponding
  local models.
- The 640x640 artwork statement is an external input/display contract. It is
  not merged into the community decoder fallback's independently recovered
  150x150 bound; the two boundaries may belong to different stages.
- The manual's no-gapless statement supports keeping the ASRC/DAC tail
  unresolved. It does not provide a sample-accurate timing model.
- Firmware dates and user-visible claims are not used to label a local binary
  as a specific release until the file and hash are available.

## Still-needed device artifacts

1. A M30-specific firmware file with a version/date mapping and SHA-256.
2. A M30-specific bootloader or ROM capture, if the boot and update path is
   to be emulated rather than kept fail-closed.
3. A PCB-level LCD controller/pinout capture and the physical key ADC ladder.
4. Codec/DAC register tables or a controlled bus trace for volume, mute,
   ramping, and audio tail behavior.

No public source checked here supplied a reliable M30 schematic, LCD
controller identity, ADC ladder, or M30-specific ROM dump. The external
research also does not establish one codec part number: the public claims
conflict. The local `drv_dac.drv` evidence proves only a masked GPIO/serial
byte bus and eight-bit send/receive helpers. It therefore does not justify a
codec register map, audio volume model, or new boot, panel, or key emulator
implementation.

## Scope and safety

- No firmware archive or raw update image was downloaded.
- No device write, recovery payload, or flash operation is part of this
  repository workflow.
- A future artifact is accepted only after its provenance, hash, format, and
  device identity are recorded; only then can byte-level evidence be added to
  the emulator and regression tests.
